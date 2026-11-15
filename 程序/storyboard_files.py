"""Project script/storyboard discovery and the shared in-page file picker."""
import app_logging
from pathlib import Path
import json, os, queue, threading
import tkinter as tk
from tkinter import ttk, messagebox
from agent.core import read
import pet_bus
from contract.storyboard_paths import is_final_dir
from storyboard_catalog_service import (
    IGNORED, discover_files, linked_path as _linked_path, content_preview as _content_preview, is_deliverable as _is_deliverable,
    file_order as _file_order,
    check_adoptable as _check_adoptable, has_synced_assets as _has_synced_assets,
)
from stage_execution_service import (
    storyboard_board_source_script as _board_source_script, storyboard_catalog as _catalog,
    storyboard_default_source as _default_source, storyboard_document_dir as _document_dir,
    storyboard_file_snapshot as _file_snapshot, storyboard_produced_episodes as _produced_episodes,
    storyboard_produced_scripts as _produced_scripts, storyboard_resolve_source as _resolve_source,
    storyboard_working_dir as _working_dir,
    storyboard_adoption_impact as _adoption_impact,
)
from storyboard_selection import (
    remember_many as _remember_many, selected_many as _selected_many,
    sync_structured_script as _sync_structured_script, remember_final_view as _remember_final_view,
    adopted as _adopted, summary as _summary,
    prune_invalid_adoptions as _prune_invalid_adoptions,
)
from storyboard_final_controller import FinalStoryboardController
from script_preview_service import should_load_async, preview_chunks, LOADING_PREVIEW
from storyboard_page_controller import StoryboardPageController
from storyboard_recycle_service import (
    recycle_plan as _recycle_plan, detach_video_refs as _detach_video_refs,
    recycle_files as _recycle_files, latest_recycle_batch as _latest_recycle_batch,
    restore_latest_recycled_files as _restore_latest_recycled_files,
)
from platform_tools import open_path
import tk_timers
from file_cache import read_json, read_text
import project_settings
import ui_plugin_registry
from pet_state import PAGE_OF
from responsive_ui import FlowBar, refresh_check_heading, bind_row_toggle
from storyboard_table_ui import file_table, fit_file_columns, fit_final_columns, insert_entries, tree_columns
from ui_tokens import WRAPLENGTH, COLORS, FONTS, SPACING
from ui_widgets import Card, DataTable, PrimaryButton, SecondaryButton, TextArea, ask_confirmation, notify
from ui_dialogs import FileDialog
confirm = ask_confirmation
# 第 46 期第 1 条：内容框的右键菜单（查看／删除）用的是 cell_hover 那一份实现，两页都要用，
# 所以提到模块头上（原先只在 show() 里 import，show_final 拿不到这个名字）。
from cell_hover import CellHover

# 第 45 期：07 分镜定稿那个文本框的两条体验——滚轮一格滚几行（原来 3 行，用户要「提高文字
# 下滑速度」），以及改完字停多久提醒存盘（用户要「改动文字后自动弹窗提醒是否保存」）。
VIEWER_WHEEL_LINES=9
VIEWER_SAVE_ASK_MS=900

def working_dir(project):
    """Compatibility facade for the headless storyboard workspace path."""
    return _working_dir(project)


def document_dir(project):
    """初步分镜的用户可读文档目录；JSON 工作稿仍由 ``working_dir`` 管理。"""
    return _document_dir(project)

def default_source(project):
    """Compatibility facade for the headless catalog service."""
    return _default_source(project)

def _prefs(path):
    # ui_settings.json 在一次页面重排里会被多个入口重复读取；按文件签名缓存解析结果。
    # 返回的是共享对象：只读可以，要改必须先 _writable_prefs() 取副本。
    from project_settings import read_prefs
    return read_prefs(path,read_json)


def resolve_source(project,path):
    """Compatibility facade for the headless catalog service."""
    return _resolve_source(project,path)


def is_deliverable(path,kind):
    """Compatibility facade for the headless catalog service."""
    return _is_deliverable(path,kind)


def file_order(path,data=None):
    """Compatibility facade for the headless catalog service."""
    return _file_order(path,data)


def check_adoptable(paths):
    """Compatibility facade for the headless catalog service."""
    return _check_adoptable(paths)


def adoption_impact(project,paths):
    """采用前的只读影响预览：不改采用清单、不改文件、不改镜头编号。"""
    return _adoption_impact(project,paths)


def catalog(project,kind):
    """Compatibility facade for the headless catalog service."""
    return _catalog(project,kind,IGNORED)

def produced_scripts(project,entries=None):
    """Compatibility facade that preserves the page's injectable catalog seam."""
    entries=catalog(project,'storyboard') if entries is None else entries
    return _produced_scripts(project,entries)


def board_source_script(project,board):
    """Compatibility facade for the headless catalog service."""
    return _board_source_script(project,board)


def produced_episodes(project,entries=None):
    """Compatibility facade that preserves the page's injectable catalog seam."""
    entries=catalog(Path(project).resolve(),'storyboard') if entries is None else entries
    return _produced_episodes(project,entries)


def remember_many(project,kind,paths):
    """Compatibility facade for the headless selection persistence service."""
    return _remember_many(project,kind,paths)


def remember(project,kind,path):
    remember_many(project,kind,[path] if path else [])


def selected_many(project,kind):
    """Compatibility facade for the headless selection query service."""
    return _selected_many(project,kind)


def selected(project,kind):
    return next(iter(selected_many(project,kind)),None)


def remember_final_view(project,path):
    """Compatibility facade for the headless final-view selection service."""
    return _remember_final_view(project,path)


def sync_structured_script(project):
    """Compatibility facade for the headless structured-script selector."""
    return _sync_structured_script(project)


def recycle_plan(project,kind,path):
    """Compatibility facade for the headless recycle-planning service."""
    return _recycle_plan(project,kind,path)

def detach_video_refs(project,targets):
    """Compatibility facade for the headless recycle service."""
    return _detach_video_refs(project,targets)

def recycle_files(project,kind,paths):
    """Compatibility facade for the headless recycle executor."""
    return _recycle_files(project,kind,paths)


def latest_recycle_batch(project):
    """Compatibility facade for the headless recycle service."""
    return _latest_recycle_batch(project)


def restore_latest_recycled_files(project):
    """Compatibility facade for the headless recycle service."""
    return _restore_latest_recycled_files(project)

def content_preview(path):
    """Compatibility facade for the headless catalog preview service."""
    return _content_preview(path)

def synced_assets(path):
    """Compatibility facade for the headless synced-asset predicate."""
    return _has_synced_assets(path)


def file_snapshot(project):
    """Compatibility facade for the headless catalog change signature."""
    return _file_snapshot(project, IGNORED)

def watch_files(owner,project,refresh,interval=1500):
    """后台观察目录；Tk 主线程只在稳定变更后重建文件列表。"""
    return tk_timers.watch_changes_async(owner,lambda:file_snapshot(project),refresh,interval)

def show_final(desktop):
    return _FinalStoryboardPage(desktop).build()


class _FinalStoryboardPage:
    """分镜定稿页（从 show_final 的闭包原样改写成类，R1813）：共享的局部变量成了实例属性，嵌套函数成了方法。"""
    def __init__(self, desktop):
        self.desktop = desktop

    def build(self):
        self._build_status_bar()
        self._build_final_table()
        self._build_viewer()
        # 第 51 期第 4 条：这一页的内容框原来挂着右键「查看／删除」，两样都去掉——
        # 「查看」与点一下这一行是同一件事，而「删除」在这页删掉的正是用户刚点开在看的那份定稿。
        # 要删分镜 JSON 请回初步分镜页（那一页的右键菜单照旧）。
        # 第 54 期附件二第 3 条：这一页的主动作改名「手动同步资产」（阶段简称＝定稿），
        # 并按三虎的跑没跑刷字与置灰。
        # 第 68 期任务 6：这一行按用户给的顺序重排——「手动同步资产」是执行三虎流程的子 Agent 入口，
        # 放最左并高亮；「阶段配置」紧跟它右边（页标题旁那一颗不再重复摆）；「刷新列表」挪到
        # 「分镜目录」左边；「打开选中 JSON」删掉（要看那份 JSON 点这一行就行，内容框本来在下面）。
        # 第 71 期任务 3：这一行是 FlowBar，它按「控件建出来的先后」排位（见 responsive_ui.FlowBar.
        # layout），不认 pack 顺序——原来「阶段配置」在「刷新列表」「分镜目录」之后才建出来，
        # 画面上就落到了最右边。现在按想要的顺序建：手动同步资产 → 阶段配置 → 刷新列表 → 分镜目录。
        self.row_buttons={}
        self.row_button('手动同步资产',lambda:self.desktop.make_final_storyboard(self.chosen()),'Primary.TButton')
        ui_plugin_registry.module('stage_flow').follow(self.row_buttons['手动同步资产'],'final')
        self.desktop.stage_button=ui_plugin_registry.module('skill_panel').stage_button(self.row,self.desktop,PAGE_OF['final'])
        self.desktop.stage_button.pack(side='left',padx=(SPACING['sm'],SPACING['xs']))
        self.row_button('刷新列表',self.refresh)
        self.row_button('分镜目录',lambda:self.desktop.open_folder(working_dir(self.project)))
        self.desktop.pet.auto_variable('auto_final_var')
        self.desktop.pet.auto_variable('auto_storyboard_var')
        self.tree.bind('<<TreeviewSelect>>',lambda e:self.desktop.safe(lambda:self.choose(e)))
        self.viewer.bind('<Destroy>',lambda _event:self.cancel_preview(),add='+')
        self.note.set('正在后台读取定稿目录…')
        self.refresh(automatic=True)
        tk_timers.repeat(self.row,60,self.apply_background_final_catalog)
        watch_files(self.row,self.project,self.refresh_all)

    def _build_status_bar(self):
        """项目与偏好、自动定稿状态条和去补资产按钮（从 build 原样切出，R1813）。"""
        self.project=Path(self.desktop.root).resolve();self.prefs_file=self.project/'ui_settings.json'
        self.page_content=self.desktop.content
        self.controller=FinalStoryboardController(self.project)
        self.desktop.note('以下仅显示已采用的分镜；选择 JSON → 同步资产生成／更新定稿 → 采用定稿。要取消采用请回'+pet_bus.stage_step('storyboard')+'点「手动取消采用」。')
        self.row=FlowBar(self.desktop.content);self.row.pack(fill='x',pady=(SPACING['xs'],SPACING['xs']))

        # 第 72 期 Round 5「分镜定稿未同步分镜的可见重试」：自动定稿那条状态原来只写状态栏，
        # 用户切到别的页面就再也看不到「还缺什么」，资产补齐了也不知道要不要动手（「无人值守走完
        # 采用分镜就静默停住」那条现象）。这里把它搬到页面上，并配一颗「立即重试」——点一下清掉
        # 签名与失败退避、立刻重跑一轮，不必等下一个 30 秒轮询周期。
        bar=ttk.Frame(self.desktop.content);bar.pack(fill='x',pady=(SPACING['none'],SPACING['xs']))
        self.status_text=tk.StringVar(value='')
        self.desktop.auto_final_banner=self.status_text                 # 页面与自检都读这一个变量
        ttk.Label(bar,textvariable=self.status_text,style='Muted.TLabel',wraplength=WRAPLENGTH['lg'],
                  justify='left').pack(side='left',anchor='w')
        self.retry_button=SecondaryButton(bar,text='立即重试',command=self.retry_now)
        self.retry_button.pack(side='left',padx=(SPACING['sm'],SPACING['xs']))
        self.assets_page=PAGE_OF['assets']
        # 切页走 after_idle：这颗按钮自己就长在要被拆掉的那一页里，事件处理途中重建页面会抖动。
        SecondaryButton(bar,text='去'+pet_bus.stage_step('assets')+'补资产',
                        command=lambda:self.desktop.win.after_idle(
                            lambda:self.desktop.safe(lambda:self.desktop.show(self.assets_page)))).pack(
                                side='left',padx=(SPACING['none'],SPACING['xs']))
        self.refresh_state()
        tk_timers.repeat(bar,1500,self.refresh_state)

    def _build_final_table(self):
        """定稿目录表格、列宽与导航（从 build 原样切出，R1813）。"""
        container=ttk.Frame(self.desktop.content);container.pack(fill='both',expand=True,pady=(SPACING['none'],SPACING['sm']))
        container.columnconfigure(0,weight=1)
        container.rowconfigure(0,weight=0)
        container.rowconfigure(1,weight=1)

        left_box=Card(container,padding=SPACING['sm'])
        left_box.grid(row=0,column=0,sticky='nsew',pady=(SPACING['none'],SPACING['xs']))
        left_box.columnconfigure(0,weight=1); left_box.rowconfigure(0,weight=1)
        # 第 40 期第 2 条：用户要「第一栏改名同步资产分镜」＋「创建时间前面新增一栏是否同步」。
        table_shell=DataTable(left_box,columns=[
            ('file','同步资产分镜',250),('sync','是否同步',80),('time','创建时间',90),('location','项目内位置',150),
        ],show='headings',selectmode='browse',empty_text='暂无分镜文件',auto_hide_scrollbars=True)
        self.tree=table_shell.tree
        for col,label,width in [('file','同步资产分镜',250),('sync','是否同步',80),
                                ('time','创建时间',90),('location','项目内位置',150)]:
            self.tree.heading(col,text=label);self.tree.column(col,width=width,minwidth=60,stretch=col!='time')
        # 第 53 期第 4 条：列宽交给 fit_final_columns（内容量 ＋ 跟窗口收放，见上）——
        # 原来那个 auto_columns 只按「当前列宽」收放，窗口一变宽度几乎全被最后一列吃掉。
        table_shell.grid(row=0,column=0,sticky='nsew')
        self.tree.tag_configure('completed',background=COLORS['row_completed'],foreground=COLORS['success'])

        right_box=Card(container,padding=SPACING['sm'])
        right_box.grid(row=1,column=0,sticky='nsew')
        right_box.columnconfigure(0,weight=1);right_box.rowconfigure(2,weight=1)

        header=ttk.Frame(right_box);header.grid(row=0,column=0,sticky='ew',pady=(SPACING['none'],SPACING['xs']))
        self.path_label=tk.StringVar(value='')
        ttk.Label(header,textvariable=self.path_label,style='Muted.TLabel').pack(side='left')

        self.nav=ttk.Frame(right_box);self.nav.grid(row=1,column=0,sticky='ew',pady=(SPACING['none'],SPACING['xs']))
        self.nav.grid_remove()
        self.nav.columnconfigure(0,weight=1)
        self.nav_canvas=tk.Canvas(self.nav,height=SPACING['sm'] * 8,highlightthickness=0,bg=COLORS['background_primary'])
        self.nav_canvas.grid(row=0,column=0,sticky='ew')
        nav_hbar=ttk.Scrollbar(self.nav,orient='horizontal',command=self.nav_canvas.xview)
        nav_hbar.grid(row=1,column=0,sticky='ew')
        self.nav_canvas.configure(xscrollcommand=nav_hbar.set)
        self.nav_inner=ttk.Frame(self.nav_canvas)
        nav_window=self.nav_canvas.create_window((0,0),window=self.nav_inner,anchor='nw')
        self.nav_inner.bind('<Configure>',self.nav_fit)

        body=ttk.Frame(right_box);body.grid(row=2,column=0,sticky='nsew')
        body.columnconfigure(0,weight=1);body.rowconfigure(0,weight=1)
        self.viewer=TextArea(body,wrap='none',bg=COLORS['background_card'],fg=COLORS['text_primary'],
                       font=FONTS['caption'],padx=SPACING['md'],pady=SPACING['md'],insertwidth=0)
        vscroll=ttk.Scrollbar(body,orient='vertical',command=self.viewer.yview)
        hscroll=ttk.Scrollbar(body,orient='horizontal',command=self.viewer.xview)
        self.viewer.grid(row=0,column=0,sticky='nsew');vscroll.grid(row=0,column=1,sticky='ns');hscroll.grid(row=1,column=0,sticky='ew')
        self.viewer.configure(yscrollcommand=vscroll.set,xscrollcommand=hscroll.set)

    def _build_viewer(self):
        """定稿正文查看／编辑框与后台目录扫描（从 build 原样切出，R1813）。"""
        # 大定稿不能在选择事件里整份读入并一次性塞进 Text：磁盘读取／JSON 解析放后台，
        # 回到 Tk 后每个 idle 只提交少量文本块。generation 让换选、刷新、拆页后的旧结果失效。
        self.preview_state={'generation':0,'poll_id':None,'chunk_id':None,'path':None}
        self.preview_results=queue.Queue()
        # 第 45 期：这个框里现在摆的是「盘上那一份」的原文；用户改过字就与它不一样了。
        self.edit_timer={'id':None}
        self.viewer.bind('<MouseWheel>',self.viewer_wheel,add='+')
        self.viewer.bind('<KeyRelease>',self.ask_save_soon,add='+')
        self.viewer.bind('<<Modified>>',self.viewer_changed,add='+')   # 第 56 期：内容一变就挂去抖
        self.viewer.bind('<FocusOut>',self.ask_save,add='+')
        self.viewer.bind('<Destroy>',self.stop_timer,add='+')          # 这一页拆了，挂着的那一次别再到期

        self.note=tk.StringVar(value='请选择要处理的 JSON')
        ttk.Label(self.desktop.content,textvariable=self.note,style='Muted.TLabel',wraplength=WRAPLENGTH['xl']).pack(anchor='w',pady=SPACING['sm'])

        self.catalog_scan={'busy':False,'revision':0,'pending':False,'stopped':False,'applying':False}
        self.catalog_results=queue.Queue(maxsize=1)

        self.row.bind('<Destroy>',self.stop_catalog,add='+')

    def refresh_state(self):
        try:state=self.desktop.auto_final_state()
        except Exception as exc:state={'text':'自动定稿状态读不出来：'+str(exc),'retry':False}
        self.status_text.set(state['text'])
        self.retry_button.configure(state='normal' if state['retry'] else 'disabled')
        return state

    def retry_now(self):
        self.desktop.status.set('已重试自动定稿。'+self.desktop.retry_auto_final())
        self.refresh_state()

    def nav_fit(self, event=None):
        self.nav_canvas.configure(scrollregion=self.nav_canvas.bbox('all'))

    def cancel_preview(self):
        self.preview_state['generation']+=1
        self.preview_state['path']=None
        for key in ('poll_id','chunk_id'):
            timer=self.preview_state.get(key);self.preview_state[key]=None
            if timer:
                try:self.viewer.after_cancel(timer)
                except Exception:app_logging.swallowed()
        return self.preview_state['generation']

    def viewer_wheel(self, event):
        # 第 45 期：一格滚轮多滚几行（原来 3 行，用户要「提高文字下滑速度」）。
        units=max(1,abs(event.delta)//120)*VIEWER_WHEEL_LINES
        if event.state & 0x0001:
            self.viewer.xview_scroll(-units if event.delta>0 else units,'units')
        else:
            self.viewer.yview_scroll(-units if event.delta>0 else units,'units')
        return 'break'

    def viewer_edited(self):
        return self.controller.is_edited(self.viewer.get('1.0','end-1c'))

    def ask_save_soon(self, event=None):
        """打完字停一会儿再问：不打断输入，也别每一击键都弹一次。"""
        if self.edit_timer['id']:
            try:self.viewer.after_cancel(self.edit_timer['id'])
            except Exception:app_logging.swallowed()
        self.edit_timer['id']=self.viewer.after(VIEWER_SAVE_ASK_MS,self.ask_save)

    def stop_timer(self, event=None):
        """把挂着的那一次去抖撤掉（页面被拆、或者已经被别的路问过了）。"""
        if event is not None and event.widget is not self.viewer:return
        if self.edit_timer['id']:
            try:self.viewer.after_cancel(self.edit_timer['id'])
            except Exception:app_logging.swallowed()
            self.edit_timer['id']=None

    def viewer_changed(self, event=None):
        """框里的字一变，就把那次去抖挂上（第 56 期）。

        原来只认 <KeyRelease>：鼠标右键粘进来的、拖进来的字都不算「改过」，去抖根本没挂；
        而并行自检里造出来的键盘事件又根本送不到这个窗（它不是系统焦点窗，整跑里十来次
        一击不中），那一条用例于是只能偶发见绿。<<Modified>> 是 Tk 自己记的「内容变过没有」，
        与字是怎么进来的无关。读完标志立刻复位（app.prompt_edited 同一条老规矩），不然只会响一次。
        """
        if not self.viewer.edit_modified():return
        self.viewer.edit_modified(False)
        self.ask_save_soon()

    def ask_save(self, event=None):
        """第 45 期：改过字就问一句要不要存盘（用户要的「自动弹窗提醒用户是否保存」）。

        选「否」＝丢掉这次改动，把盘上那一份原样摆回来；写盘之前先按 JSON 解一遍，改坏了只
        提示、不覆盖，用户接着改就是了。别的页面、别的 JSON 一个字都不动。
        """
        self.stop_timer()                              # 去抖与 <FocusOut> 可能都到点：撤掉另一个，别问两遍
        if not self.viewer.winfo_exists():return       # 这一页已经换掉了：这一下什么都不做
        if not self.viewer_edited():return
        # 失焦可能先于排队的 <<Modified>>；本次已处理这次编辑，别再挂一次提醒。
        self.viewer.edit_modified(False)
        path=self.controller.live_path()               # 维护改过名就跟着走，别在旧名字上再写一份
        if not confirm(self.desktop.win, '保存改动',
                '这份 JSON 您改过，要存回项目吗？\n\n'+self.controller.display_name(path)
                +'\n\n选「否」＝丢掉这次改动，恢复成盘上那一份。',
                ):
            self.show_content(path)
            self.desktop.status.set('已放弃这次改动：'+self.controller.display_name(path))
            return
        try:preview=self.controller.save_edited(self.viewer.get('1.0','end-1c'))
        except ValueError as exc:
            notify(self.desktop.win, str(exc)+'\n\n请改回 JSON 格式再存，或点「刷新列表」重新载入。',
                   level='error', title='无法保存', status=self.desktop.status)
            return
        self.render_preview(preview)                   # 存完重新摆一遍：改动状态清零，看到的就是盘上那份
        self.desktop.status.set('已保存改动：'+self.controller.display_name(path))

    def chosen(self):
        if self.catalog_scan['applying']:raise ValueError('定稿列表正在更新，请稍候')
        if not self.tree.selection():raise ValueError('请先在列表中选择 JSON')
        return Path(self.tree.selection()[0])

    def set_viewer_text(self, text,generation=None):
        generation=self.preview_state['generation'] if generation is None else generation
        self.viewer.configure(state='normal');self.viewer.delete('1.0','end')
        chunks=preview_chunks(text)
        def append_chunks():
            self.preview_state['chunk_id']=None
            if generation!=self.preview_state['generation'] or not self.viewer.winfo_exists():return
            try:
                # 两块约 64 KiB：足够快地首屏可读，也会持续让出 Tk 的事件循环。
                for _ in range(2):self.viewer.insert('end',next(chunks))
            except StopIteration:
                self.viewer.see('1.0');return
            self.preview_state['chunk_id']=self.viewer.after_idle(append_chunks)
        append_chunks()

    def jump(self, sid):
        idx=self.viewer.search('"'+sid+'"','1.0',stopindex='end')
        if idx:
            self.viewer.mark_set('insert',idx)
            try:
                line=int(str(self.viewer.index(idx)).split('.')[0])
                total=int(str(self.viewer.index('end-1c')).split('.')[0])
                frac=max(0.0,min(1.0,(line-2)/max(1,total)))
                self.viewer.yview_moveto(frac)
            except (ValueError,ZeroDivisionError):
                self.viewer.see(idx)
            self.viewer.focus_set()

    def select_shot(self, sid):
        self.controller.select_shot(sid)
        for child in self.nav_inner.winfo_children():
            if isinstance(child,ttk.Button):
                child.configure(style='Tokens.Primary.TButton' if str(child.cget('text'))==sid else 'Tokens.Secondary.TButton')
        self.jump(sid)

    def rebuild_nav(self, data):
        ids=self.controller.set_navigation(data)
        # 镜头清单没变就不重建按钮：新建一个按钮约 2.4 毫秒，几十镜的目录每次刷新、每次换选中都要重建。
        if list(ids)==[str(child.cget('text')) for child in self.nav_inner.winfo_children() if isinstance(child,ttk.Button)] and (len(ids)<=1 or self.nav_inner.winfo_children()):
            for child in self.nav_inner.winfo_children():
                if isinstance(child,ttk.Button):child.configure(style='Tokens.Secondary.TButton')
            return
        for child in self.nav_inner.winfo_children():child.destroy()
        if len(ids)<=1:
            self.nav.grid_remove()
            return
        self.nav.grid()
        ttk.Label(self.nav_inner,text='镜头目录').grid(
            row=0,column=0,sticky='w',padx=(SPACING['xs'],SPACING['xs']))
        half=(len(ids)+1)//2
        for index,sid in enumerate(ids):
            button=SecondaryButton(self.nav_inner,text=sid,command=lambda s=sid:self.select_shot(s))
            button.grid(row=index//half,column=index%half+1,
                        padx=(SPACING['none'],SPACING['xs']),pady=SPACING['xs'],sticky='w')
        self.nav_fit()

    def render_preview(self, preview,generation=None):
        self.path_label.set(str(preview.path))
        self.set_viewer_text(preview.text,generation)
        self.rebuild_nav(preview.data)

    def load_content(self, path):
        """按需读取一份定稿；大文件的旧请求只丢弃结果，不触碰当前选择。"""
        path=Path(path)
        generation=self.cancel_preview()
        self.preview_state['path']=path
        def accept(preview,selection_note=''):
            if generation!=self.preview_state['generation'] or not self.viewer.winfo_exists():return
            self.controller.apply_preview(preview)
            if selection_note:self.note.set(selection_note)
            self.render_preview(preview,generation)
        def read_in_background():
            # 用独立控制器读取，避免已取消请求在工作线程覆盖当前页面的选择状态。
            worker=FinalStoryboardController(self.project)
            return worker.load(path),''
        if not should_load_async(path):
            preview,selection_note=read_in_background();accept(preview,selection_note);return
        self.path_label.set(str(path));self.note.set('正在后台加载定稿预览…');self.set_viewer_text(LOADING_PREVIEW,generation)
        def work():
            try:value=(True,read_in_background())
            except (OSError,ValueError,UnicodeError) as exc:value=(False,str(exc))
            self.preview_results.put((generation,value))
        def collect():
            self.preview_state['poll_id']=None
            try:request,value=self.preview_results.get_nowait()
            except queue.Empty:
                if generation==self.preview_state['generation']:
                    self.preview_state['poll_id']=self.viewer.after(30,collect)
                return
            if request!=self.preview_state['generation'] or generation!=request:return
            ok,payload=value
            if ok:accept(*payload)
            else:
                self.note.set('无法读取定稿预览：'+payload);self.set_viewer_text('（无法读取此文件）',generation)
        threading.Thread(target=work,daemon=True,name='final-storyboard-preview').start()
        self.preview_state['poll_id']=self.viewer.after(30,collect)

    def show_content(self, path):
        self.load_content(path)

    def choose(self, event=None):
        if self.catalog_scan['applying'] or getattr(self.tree,'_entries_filling',False):return
        if not self.tree.selection():return
        path=self.chosen()
        if event is not None and self.preview_state['path']==path:return
        _unused,selection_note=self.controller.choose(path,load=False)
        self.note.set(selection_note)
        self.load_content(path)

    def scan_entries(self):
        return [e for e in catalog(self.project,'storyboard') if e['path'].suffix.lower()=='.json' and e.get('done')]

    def apply_entries(self, entries,automatic=False):
        if self.catalog_scan['stopped'] or Path(self.desktop.root).resolve()!=self.project:return False
        from stage_execution_service import normalize_storyboard_for_desktop
        if normalize_storyboard_for_desktop(self.desktop):
            # 规范化会改名和重写采用指针；旧扫描不能再落入列表。
            return self.refresh(automatic=automatic)
        self.tree.configure(height=max(2,min(12,len(entries))))
        previous=self.tree.selection();prefs=_prefs(self.prefs_file)
        current=resolve_source(self.project,previous[0] if previous else prefs.get('frame_json') or prefs.get('final_storyboard_json') or default_source(self.project))
        x,y=self.tree.xview()[0],self.tree.yview()[0]
        self.catalog_scan['applying']=True
        def finished():
            self.catalog_scan['applying']=False
            if self.catalog_scan['stopped'] or Path(self.desktop.root).resolve()!=self.project:return
            selected=self.tree.selection()
            target=selected[0] if selected else str(current)
            if self.tree.exists(target):
                if selected!=(target,):self.tree.selection_set(target)
                if automatic:self.tree.xview_moveto(x);self.tree.yview_moveto(y)
                else:self.tree.see(target)
                # 自动更新目录不能覆盖用户正在编辑的同一份 JSON。
                if not (automatic and self.controller.preview is not None
                        and str(self.controller.preview.path)==target and self.viewer_edited()):self.choose()
            else:
                self.note.set('暂无可用 JSON，请先完成初步分镜' if not entries else '请选择要处理的 JSON')
                self.cancel_preview();self.controller.clear();self.set_viewer_text('');self.path_label.set('');self.rebuild_nav({})
        insert_entries(self.tree,self.project,entries,with_sync=True,batch_size=40,on_complete=finished)
        return True

    def refresh(self, automatic=False):
        if self.catalog_scan['stopped']:return False
        if not automatic:
            self.catalog_scan['revision']+=1
            self.catalog_scan['pending']=False
            return self.apply_entries(self.scan_entries())
        if self.catalog_scan['busy']:
            self.catalog_scan['pending']=True
            return True
        self.catalog_scan['busy']=True
        revision=self.catalog_scan['revision']
        def scan():
            try:value=(True,self.scan_entries())
            except Exception as exc:value=(False,str(exc))
            try:self.catalog_results.put_nowait((revision,*value))
            except queue.Full:pass
        threading.Thread(target=scan,daemon=True,name='final-storyboard-catalog-scan').start()
        return True

    def apply_background_final_catalog(self):
        if self.catalog_scan['stopped']:return
        try:revision,ok,value=self.catalog_results.get_nowait()
        except queue.Empty:return
        self.catalog_scan['busy']=False
        if revision==self.catalog_scan['revision']:
            if ok:
                try:self.apply_entries(value,automatic=True)
                except (OSError,ValueError,KeyError) as exc:
                    self.note.set('定稿目录结果已过期，可点击「刷新列表」重试：'+str(exc))
                    if self.desktop.content is self.page_content:
                        self.desktop.status.set('定稿目录结果已过期，将在下次文件变动后重试：'+str(exc))
            else:
                self.note.set('定稿目录加载失败，可点击「刷新列表」重试：'+value)
                if self.desktop.content is self.page_content:
                    self.desktop.status.set('定稿目录刷新失败，将在下次文件变动后重试：'+value)
        if self.catalog_scan['pending']:
            self.catalog_scan['pending']=False
            self.refresh(automatic=True)

    def stop_catalog(self, event):
        if event.widget is not self.row:return
        self.catalog_scan['stopped']=True
        self.catalog_scan['revision']+=1
        self.cancel_preview()

    def row_button(self, title,action,style='Compact.TButton'):
        button_class=PrimaryButton if style=='Primary.TButton' else SecondaryButton
        button=button_class(self.row,text=title,command=lambda a=action:self.desktop.safe(a))
        button.pack(side='left',padx=(SPACING['none'],SPACING['xs']));self.row_buttons[title]=button
        return button

    def refresh_all(self):
        # 列表刷新（文件快照变了）时顺带把提示条重扫一遍：资产刚补齐那一拍就能看出「已经可以定稿」。
        result=self.refresh(automatic=True)
        self.refresh_state()
        return result

def show(desktop):
    return _StoryboardFilesPage(desktop).build()


class _StoryboardFilesPage:
    """初步分镜文件页（从 show 的闭包原样改写成类，R1813）：共享的局部变量成了实例属性，嵌套函数成了方法。"""
    def __init__(self, desktop):
        self.desktop = desktop

    def build(self):
        self._init_page_state()
        self._build_toolbar()
        self._build_tables()
        self.update_controls()
        for label in self.labels.values():label.set('正在读取文件列表…')
        self.refresh(automatic=True)
        # 自动文件监听只在后台扫描目录；这颗短周期计时器只把已经完整的结果批量写进 Treeview。
        tk_timers.repeat(self.toolbar, 60, self.apply_background_catalog)
        watch_files(self.toolbar,self.project,lambda:self.refresh(automatic=True))
        self.binding=self.desktop.win.bind('<Button-1>',self.outside_click,add='+')
        self.toolbar.bind('<Destroy>',lambda event:self.desktop.win.unbind('<Button-1>',self.binding) if event.widget==self.toolbar else None,add='+')

    def _init_page_state(self):
        """页面控制器、勾选与表格状态（从 build 原样切出，R1813）。"""
        # Selection mutations remain a page-action boundary; the L2 service is
        # imported normally so this L4 page has no unregistered dynamic import.
        self.project=Path(self.desktop.root).resolve()
        self.page_content=self.desktop.content
        self.controller=StoryboardPageController(self.project)
        adopted=self.controller.adopted
        removed=self.controller.prune_invalid_adoptions()
        if removed:
            self.desktop.status.set('已取消采用 '+str(len(removed))+' 份未关联当前分镜初稿的历史 JSON；文件保留')
        self.desktop.note('Ctrl／Shift 多选，Ctrl+A 全选。按集数和镜头顺序排列；已制作剧本、已采用 JSON 排在底部并跳过重复处理。')
        self.tables={};self.labels={};self.loaded=False;self.controls={};self.completed_scripts=set();self.checked={}
        self.tick_images=self.desktop.win._tick_images[:2]
        self.adopted_note=tk.StringVar(value=self.controller.summary())
        self.catalog_scan = {'busy': False, 'revision': 0, 'pending': False, 'stopped': False}
        self.catalog_results = queue.Queue(maxsize=1)
        self.page_content.bind('<Destroy>',self.stop_catalog,add='+')

    def _build_toolbar(self):
        """顶部工具栏：刷新、打开、浏览、目录等按钮（从 build 原样切出，R1813）。"""
        self.toolbar=FlowBar(self.desktop.content);self.toolbar.pack(
            fill='x', pady=(SPACING['none'], SPACING['none']))
        from contract.project_stages import writing
        self.writing = writing
        for text,command in [('刷新列表',self.refresh),('打开选中剧本',lambda:self.open_selected('script')),('选择其他剧本',self.browse),('剧本目录',lambda:self.desktop.open_folder(self.writing(self.project))),('删除选中剧本',lambda:self.delete_selected('script')),('恢复最近删除',self.restore_latest)]:
            button=SecondaryButton(self.toolbar,text=text,command=lambda c=command:self.desktop.safe(c))
            button.pack(side='left',padx=(SPACING['none'], SPACING['xs']))
            if text=='删除选中剧本':self.controls['delete_script']=button

    def _build_tables(self):
        """剧本与分镜初稿两张表格、悬停与勾选绑定（从 build 原样切出，R1813）。"""
        first_labels={'script':'结构剧本','storyboard':'分镜初稿'}
        for kind in ('script','storyboard'):
            # 第 31 期第 4 条：内容框用没有标签行的卡片样式，紧贴上方「刷新列表」那一行。
            box=Card(self.desktop.content,padding=SPACING['sm'])
            box.pack(fill='both',expand=True,pady=(SPACING['none'], SPACING['none']))
            status_label='是否制作' if kind=='script' else '是否采用'
            tree=file_table(box,selectmode='browse',first_label=first_labels[kind],status_label=status_label)
            self.tables[kind]=tree;self.labels[kind]=tk.StringVar()
            tree.heading('#0',command=lambda k=kind:self.toggle_all(k))
            self.content_col='#3'
            cell_cols=('#0',self.content_col)
            def open_cell(k,row,col):
                tree=self.tables[k]
                if col=='#0':
                    self.toggle_check(k,row)
                    tree.selection_remove(*tree.selection());tree.focus('')
                elif col==self.content_col:
                    tree.selection_set(row);tree.focus(row)
                    if Path(row).is_file():open_path(row)
            def is_checked(k,row):return row in self.checked.get(k,set())
            # 第 46 期第 1 条：右键＝查看（打开这一份文件）／删除（只删这一行）。
            # 第 52 期第 2 条：菜单只在带链接的格子上弹（原先靠 menu_column 让哪一格都能查看，
            # 用户要的是「鼠标底下有可查看的文件才弹」）——这一页就是「文件内容」那一格。
            tree.cell_hover=CellHover(tree,cell_cols,lambda row,col,k=kind:self.desktop.safe(lambda k=k,row=row,col=col:open_cell(k,row,col)),cell_image=lambda row,col,k=kind:(self.tick_images[1 if is_checked(k,row) else 0] if col=='#0' else None),checked=lambda row,k=kind:is_checked(k,row),toggle=lambda row,k=kind:self.toggle_check(k,row),delete=lambda row,k=kind:self.desktop.safe(lambda k=k,row=row:self.delete_one(k,row)))
            bind_row_toggle(tree,lambda row,k=kind:self.toggle_check(k,row),cell_cols)
            # 第 47 期第 1 条：高亮那一行也算「选中」，所以高亮一变就把按钮的可用状态重算一遍
            # （current_selection 本来就是「勾选优先、高亮兜底」，按钮的亮灭得跟它同一个口径）。
            tree.bind('<<TreeviewSelect>>',lambda e:self.update_controls())
            if kind=='storyboard':
                label_row=ttk.Frame(box);label_row.pack(fill='x',pady=(SPACING['xs'], SPACING['none']))
                ttk.Label(label_row,textvariable=self.labels[kind],style='Muted.TLabel').pack(side='left')
                ttk.Label(label_row,textvariable=self.adopted_note,style='Muted.TLabel').pack(
                    side='left',padx=(SPACING['md'], SPACING['none']))
                def renumber_shots():
                    """按集号顺序重排镜头编号。批量分镜容易按完成顺序编号（EP002 拿到 SH032-SH050，
                EP003 反而占了 SH017-SH031），这里交给 shot_numbering 统一重排：先预览，确认后
                备份再改，编号之外的内容一律不动。"""
                    import shot_numbering
                    targets=[entry['path'] for entry in catalog(self.project,'storyboard')]
                    if not targets:
                        raise ValueError('还没有分镜 JSON，无需重排编号')
                    plan=shot_numbering.renumber(self.project,targets,apply=False,log=lambda text:None)
                    if not plan['mapping']:
                        problems=shot_numbering.verify(self.project,targets)
                        self.desktop.status.set('镜头编号已按剧本顺序连续，无需重排' if not problems
                                           else '镜头编号检查：'+'；'.join(problems))
                        return
                    preview='、'.join('%s→%s'%(old,new) for old,new in sorted(plan['mapping'].items())[:12])
                    if not confirm(self.desktop.win, '重排镜头编号',
                            f'重排 {len(plan["mapping"])} 个镜头编号：{preview}{"…" if len(plan["mapping"])>12 else ""}\n'
                        f'并改写 {len(plan["contents"])} 个文件里的引用、{len(plan["renames"])} 项文件名。\n'
                        '只改编号，不碰内容；会先备份。是否继续？',
                            dangerous=True):
                        self.desktop.status.set('已取消重排镜头编号')
                        return
                    def work():
                        shot_numbering.renumber(self.project,targets,apply=True,log=lambda text:None)
                        problems=shot_numbering.verify(self.project,targets)
                        return '镜头编号已重排；'+('编号连续' if not problems else '仍有问题：'+'；'.join(problems))
                    def done(result):
                        self.refresh()
                        self.desktop.status.set(result)
                    self.desktop.async_(work,done)
                actions=FlowBar(box);actions.pack(fill='x',pady=(SPACING['xs'], SPACING['none']))
                # 第 59 期第 4 条：两颗「采用／取消采用」改叫「手动采用分镜」「手动取消采用」
                # 并挨在一起，都按高亮按钮（Primary）画——这一页就这两颗是人真正要按的；
                # 其余动作（打开／导入／目录／重排／删除）留在右边。
                action_rows=[('手动采用分镜',self.adopt_selected,'adopt','Primary.TButton'),
                             ('手动取消采用',self.remove_selected,'remove','Primary.TButton'),
                             ('打开选中JSON',lambda:self.open_selected('storyboard'),None,''),
                             ('导入JSON分镜',self.desktop.import_json,None,''),
                             # 这里打开的是用户在本阶段查看、编辑的分镜文档，而不是内部 JSON
                             # 工作稿目录；JSON 的导入、打开与采用仍直接以列表里的文件为准。
                             ('分镜目录',lambda:self.desktop.open_folder(document_dir(self.project)),None,''),
                             ('重排镜头编号',renumber_shots,None,''),
                             ('删除选中分镜',lambda:self.delete_selected('storyboard'),'delete_storyboard','')]
                for text,action,key,style in action_rows:
                    button=(PrimaryButton if style else SecondaryButton)(
                        actions,text=text,command=lambda fn=action:self.desktop.safe(fn))
                    button.pack(side='left',padx=(SPACING['none'], SPACING['xs']))
                    if key:self.controls[key]=button
                self.desktop.pet.auto_variable('auto_adopt_var')
                # 第 67 期任务 2：这一排按钮与那一行说明先从底下占好自己的位置——位置不够时该缩的是
                # 那张会长高的表格（area），不是它们。原来它们是这一格最后两个 slave，表格一长高就被
                # 挤成 0 像素，用户看到的就是「内容框下方的按钮不显示」，而整页又刚好不需要滚动。
                actions.pack_configure(side='bottom',before=tree.master)
                label_row.pack_configure(side='bottom',before=tree.master)
            else:
                # 第 67 期任务 2：这一行先占好自己的位置（表格再缩也不许把它挤掉，见下面 actions 那一处）。
                note=ttk.Label(box,textvariable=self.labels[kind],style='Muted.TLabel',wraplength=WRAPLENGTH['2xl'])
                note.pack(side='bottom',anchor='w',pady=(SPACING['xs'], SPACING['none']),before=tree.master)
                # 第 31 期第 5 条：手动制作与下方内容框贴紧一些。
                center=ttk.Frame(self.desktop.content);center.pack(
                    fill='x',pady=(SPACING['xs'], SPACING['xs']))
                # 第 32 期第 1／5／6 条：改名「手动制作分镜」，与别的阶段页一样左对齐（原来居中），
                # 阶段配置紧挨在它右边。
                row=ttk.Frame(center);row.pack(anchor='w')
                # 第 47 期第 3 条：点「手动制作分镜」先问一句模型配没配（没配就问要不要现在去「阶段配置」）。
                from stage_models import manual_command
                self.manual_command = manual_command
                self.controls['agent']=PrimaryButton(
                    row,text='手动制作分镜',command=lambda:self.desktop.safe(
                        self.manual_command(self.desktop,'storyboard',lambda:self.desktop.open_storyboard_skill(None),self.desktop.win)))
                self.controls['agent'].pack(side='left',padx=(SPACING['none'], SPACING['xs']))
                ui_plugin_registry.module('stage_flow').follow(self.controls['agent'],'storyboard')
                self.desktop.stage_button=ui_plugin_registry.module('skill_panel').stage_button(row,self.desktop,1)
                self.desktop.stage_button.pack(side='left',padx=(SPACING['sm'], SPACING['none']))
                self.controls['agent'].bind('<Button-1>',lambda e: (notify(self.desktop.win, '请先在上方选择需要制作的剧本，或选择要采用的 JSON 分镜。', title='手动制作分镜', status=self.desktop.status) if self.controls['agent'].cget('state')=='disabled' else None),add='+')

    def current_selection(self, kind):
        """这一栏「选中」的那些文件（第 46 期：内容框这份清单为准；第 47 期第 1 条：统一口径）。

        勾选优先；一个都没勾就按高亮那一行算——用户点了那一份看着就是选中的，
        采用／取消采用／删除不该回一句「请先勾选」。
        """
        highlighted=()
        if self.loaded and kind in self.tables:
            tree=self.tables[kind]
            from responsive_ui import work_rows
            highlighted,_how=work_rows(tree,lambda item: item in self.checked.get(kind,set()))
        return self.controller.action_selection(kind,highlighted)

    def update_controls(self):
        states=self.controller.control_states(self.current_selection('script'),self.current_selection('storyboard'))
        for key,enabled in states.items():
            if key in self.controls:self.controls[key].configure(state='normal' if self.loaded and enabled else 'disabled')

    def choose(self, kind,paths,announce=True,*,persist=True):
        paths=self.controller.choose(kind,paths) if persist else paths
        self.checked[kind]=set(str(p) for p in paths)
        label='剧本' if kind=='script' else '分镜'
        self.labels[kind].set(f'已选 {len(paths)} 份{label}：'+'、'.join(p.name for p in paths) if paths else '尚未选择'+label)
        if announce:self.desktop.status.set(f'已选择 {len(paths)} 份{label}' if paths else '已取消选择'+label)
        self.update_controls()
        if kind in self.tables:
            tree=self.tables[kind];sel=self.checked.get(kind,set())
            for item in tree.get_children():tree.item(item,image=self.tick_images[1 if item in sel else 0])
            self.update_header_check(kind)

    def update_header_check(self, kind):
        tree=self.tables.get(kind)
        if tree is None:return
        refresh_check_heading(tree, self.tick_images, lambda i: i in self.checked.get(kind,set()))

    def clear_selection(self, kind):
        self.choose(kind,[],False)

    def stop_catalog(self, event):
        if event.widget is self.page_content:
            self.catalog_scan['stopped']=True
            self.catalog_scan['revision']+=1
            self.catalog_scan['pending']=False

    def apply_catalogs(self, catalogs, automatic=False):
        from stage_execution_service import normalize_storyboard_for_desktop
        if normalize_storyboard_for_desktop(self.desktop):
            if automatic:
                self.catalog_scan['pending']=True
                return False
            catalogs=self.controller.refresh_catalogs()
        if automatic:
            for kind,tree in self.tables.items():
                available={str(entry['path']) for entry in catalogs[kind]}
                if any(Path(item).suffix.lower()=='.json' and Path(item).is_file() and item not in available for item in tree.get_children()):return False
        catalogs=self.controller.apply_catalogs(catalogs)
        self.completed_scripts=self.controller.completed_scripts
        self.loaded=False;self.update_controls()
        remaining=set(self.tables)
        def finished(kind,tree,x,y):
            self.choose(kind,self.controller.selection(kind),False,persist=False)
            if automatic:tree.xview_moveto(x);tree.yview_moveto(y)
            remaining.discard(kind)
            if not remaining:
                self.adopted_note.set(self.controller.summary());self.loaded=True;self.update_controls()
        for kind,tree in self.tables.items():
            entries=catalogs[kind];x=tree.xview()[0];y=tree.yview()[0]
            def status_of(entry,kind=kind):
                if kind=='script':return '✓ 已制作' if entry.get('done') else '未制作'
                return '✓ 已采用' if entry.get('done') else '未采用'
            insert_entries(tree,self.project,entries,status_of=status_of,batch_size=40,
                           on_complete=lambda k=kind,t=tree,x=x,y=y:finished(k,t,x,y))
        return True

    def refresh(self, automatic=False):
        """手动刷新立即扫描；初次与监听在后台读取，Tk 分批应用完整结果。"""
        if self.catalog_scan['stopped']:return False
        if not automatic:
            self.catalog_scan['revision'] += 1
            self.catalog_scan['pending'] = False
            return self.apply_catalogs(self.controller.refresh_catalogs())
        if self.catalog_scan['busy']:
            self.catalog_scan['pending'] = True
            return True
        self.catalog_scan['busy'] = True
        revision = self.catalog_scan['revision']
        def scan():
            try:
                value = (True, self.controller.refresh_catalogs())
            except Exception as exc:
                value = (False, str(exc))
            try:
                self.catalog_results.put_nowait((revision, *value))
            except queue.Full:
                pass
        threading.Thread(target=scan, daemon=True, name='storyboard-catalog-scan').start()
        return True

    def apply_background_catalog(self):
        try:
            revision, ok, value = self.catalog_results.get_nowait()
        except queue.Empty:
            return
        self.catalog_scan['busy'] = False
        if self.catalog_scan['stopped'] or Path(self.desktop.root).resolve()!=self.project:return
        def report_error(message):
            if not self.loaded:
                for label in self.labels.values():label.set('文件列表加载失败，请点击「刷新列表」重试')
            if self.desktop.content is self.page_content:self.desktop.status.set(message)
        if revision != self.catalog_scan['revision']:
            pass
        elif ok:
            try:
                self.apply_catalogs(value, automatic=True)
            except (OSError, ValueError, KeyError) as exc:
                report_error('分镜目录结果已过期，将在下次文件变动后重试：' + str(exc))
        else:
            report_error('分镜目录刷新失败，将在下次文件变动后重试：' + value)
        if self.catalog_scan['pending']:
            self.catalog_scan['pending'] = False
            self.refresh(automatic=True)

    def toggle_all(self, kind):
        tree=self.tables[kind];items=list(tree.get_children());cur=self.checked.get(kind,set())
        if items and all(item in cur for item in items):
            self.choose(kind,[],False)
        else:
            self.choose(kind,[Path(item) for item in items],False)

    def toggle_check(self, kind,item):
        cur=set(self.checked.get(kind,set()))
        if item in cur:cur.remove(item)
        else:cur.add(item)
        self.choose(kind,[Path(i) for i in cur],False)

    def open_selected(self, kind):
        paths=self.current_selection(kind)
        if not paths:raise ValueError('请先选择文件')
        for path in paths:open_path(path)

    def delete_selected(self, kind):
        paths=self.current_selection(kind)
        if not paths:raise ValueError('请先选择文件')
        paths,targets=self.controller.recycle_targets(kind,paths)
        if not confirm(self.desktop.win, '删除选中文件',f'将选中的 {len(paths)} 份文件及关联工作稿共 {len(targets)} 项移入项目回收站？\n\n'+'\n'.join(p.name for p in targets)+'\n\n资产、其他定稿和视频保留；仍引用这些 JSON 的视频任务将解除来源关联。',dangerous=True):return
        folder=self.controller.recycle(kind,paths);self.refresh();self.desktop.status.set('已移入回收站：'+str(folder))

    def delete_one(self, kind,item):
        """逐个删除（第 46 期第 1 条）：目标就是右键点中的那一行——高亮与勾选都不参与。"""
        path=self.controller.removable(kind,Path(item))
        if not confirm(self.desktop.win, '删除此文件',
                '将这一份文件及它带的关联工作稿移入项目回收站？\n\n'+path.name+
                '\n\n资产、其他定稿和视频保留；仍引用它的视频任务将解除来源关联。',
                dangerous=True):return
        folder=self.controller.recycle(kind,[path]);self.refresh()
        self.desktop.status.set('已移入回收站：'+str(folder))

    def restore_latest(self):
        candidate = self.controller.latest_recycle_batch()
        if candidate is None:
            raise ValueError('没有可恢复的剧本或分镜删除记录')
        _folder, names = candidate
        shown = '\n'.join(Path(name).name for name in names[:12])
        more = '\n…' if len(names) > 12 else ''
        if not confirm(self.desktop.win, '恢复最近删除',
                '将恢复最近一次删除的 %d 项关联文件：\n%s%s\n\n若原位置已有同名文件，将安全中止且不恢复任何文件。'
                % (len(names), shown, more)):
            return
        _names, restored = self.controller.restore_latest()
        self.refresh()
        self.desktop.status.set('已恢复 %d 项剧本／分镜文件' % len(restored))

    def browse(self):
        from contract.project_stages import writing
        values=FileDialog(self.desktop.win).open_files(title='选择用于制作分镜的剧本（可多选）',initialdir=writing(self.project),filetypes=[('剧本','*.md *.txt *.docx')])
        if values:self.choose('script',[Path(p).resolve() for p in values]);self.refresh()

    def adopt_selected(self):
        selected_paths=self.current_selection('storyboard');used=self.controller.adopted();incoming=[p for p in selected_paths if p not in used]
        already=[p for p in selected_paths if p in used]
        # 已采用的 JSON 只跳过、不重复采用，无需确认；弹窗会挂住无人值守流程。
        if not incoming:self.desktop.status.set('所选 JSON 均已采用，无需重复采用');return
        check_adoptable(incoming)          # 第 62 期任务 12：不合格的先一次列清，别让用户逐份试
        # 采用前只读预览（O19）：相对同集已采用分镜的新增／删除／改动与将失效首帧／视频，
        # 只展示不改状态；取消采用不会改动正式采用清单，镜头编号也不重排。
        impact=adoption_impact(self.project,selected_paths)
        impact_note=('；影响预览：'+str(impact['summary'])) if impact.get('summary') else ''
        skipped=f'（另有 {len(already)} 份已采用，已跳过）' if already else ''
        self.desktop.adopt_frame_jsons(incoming);self.refresh()
        switched=self.desktop.sync_working_episode()
        self.desktop.status.set(f'新增采用 {len(incoming)} 份{skipped}；'+self.controller.summary()+('；工作集已切到最新采用的分镜' if switched else '；工作集保持不变')+impact_note+self.desktop.final_storyboard_hint()+self.desktop.shot_numbering_hint())

    def remove_selected(self):
        self.desktop.remove_frame_jsons(self.current_selection('storyboard'));self.refresh();self.desktop.status.set('已取消所选分镜的采用；分镜文件与资产保留')

    def outside_click(self, event):
        # 整页缓存后这一页可能只是收起来了：别的页上的点击不能清掉这里的选择。
        if not self.toolbar.winfo_ismapped():return
        widget=event.widget;ancestors=[]
        while widget is not None:
            ancestors.append(widget)
            if widget==self.desktop.content:break
            widget=getattr(widget,'master',None)
        if self.desktop.content not in ancestors:return
        if any(isinstance(w,(ttk.Button,tk.Button,ttk.Scrollbar,tk.Scrollbar,ttk.Entry,tk.Entry,ttk.Combobox)) for w in ancestors):return
        # Selecting another list must preserve the first list's multi-selection.
        if any(tree in ancestors for tree in self.tables.values()):return
        for kind in self.tables:self.clear_selection(kind)
        self.desktop.status.set('已取消选择')
