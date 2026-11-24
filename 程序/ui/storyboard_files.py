"""Project script/storyboard discovery and the shared in-page file picker."""
import infra.app_logging as app_logging
from pathlib import Path
import json, os, queue, threading
import tkinter as tk
from tkinter import ttk, messagebox
from agent.core import read
import contract.pet_bus as pet_bus
from contract.storyboard_paths import is_final_dir
from contract import error_codes
from domain.storyboard_catalog_service import (
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
from orchestrator.storyboard_selection import (
    remember_many as _remember_many, selected_many as _selected_many,
    sync_structured_script as _sync_structured_script, remember_final_view as _remember_final_view,
    adopted as _adopted, summary as _summary,
    prune_invalid_adoptions as _prune_invalid_adoptions,
)
from orchestrator.storyboard_final_controller import FinalStoryboardController
from domain.script_preview_service import should_load_async, preview_chunks, LOADING_PREVIEW
from orchestrator.storyboard_page_controller import StoryboardPageController
from orchestrator.storyboard_recycle_service import (
    recycle_plan as _recycle_plan, detach_video_refs as _detach_video_refs,
    recycle_files as _recycle_files, latest_recycle_batch as _latest_recycle_batch,
    restore_latest_recycled_files as _restore_latest_recycled_files,
)
from contract.platform_tools import open_path
import infra.tk_timers as tk_timers
from infra.file_cache import read_json, read_text
import infra.project_settings as project_settings
import infra.ui_plugin_registry as ui_plugin_registry
from infra.pet_state import PAGE_OF
from responsive_ui import FlowBar, refresh_check_heading, bind_row_toggle
from ui.storyboard_table_ui import (
    S03_EMPTY_TEXT, S03_HINT_EDIT, S03_HINT_READ, S03EditorView,
    file_table, fit_file_columns, fit_final_columns, insert_entries,
    pick_default_document, render_document_text, tree_columns,
)
from ui_tokens import WRAPLENGTH, COLORS, FONTS, SPACING
from ui_widgets import (Card, DataTable, PrimaryButton,
                        SecondaryButton, TextArea, ask_confirmation, notify)
from ui.ui_dialogs import FileDialog
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
    from infra.project_settings import read_prefs
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
        # R2942：「阶段配置」按钮＋模型下拉框删除。
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
            notify(self.desktop.win, error_codes.user_text(exc)+'\n\n请改回 JSON 格式再存，或点「刷新列表」重新载入。',
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
    """03 初步分镜单编辑器页：取消顶部按钮与双表，改由右侧文件栏展示结构剧本与分镜，
    主区域为专用分镜文本编辑器，采用／导入／重排／目录等必要功能收进编辑器右键菜单。"""

    def __init__(self, desktop):
        self.desktop = desktop

    def build(self):
        self._init_page_state()
        self._build_editor()
        self._register_storyboard_send_action()
        self._register_files_panel_handler()
        self.refresh(automatic=True)
        tk_timers.repeat(self.editor_frame, 60, self.apply_background_catalog)
        watch_files(self.editor_frame, self.project, lambda: self.refresh(automatic=True))

    def _init_page_state(self):
        self.project, self.page_content = Path(self.desktop.root).resolve(), self.desktop.content
        self.controller = StoryboardPageController(self.project)
        removed = self.controller.prune_invalid_adoptions()
        if removed:
            self.desktop.status.set('已取消采用 %d 份未关联当前分镜初稿的历史 JSON；文件保留' % len(removed))
        self.loaded = self.raw_json_mode = self.editing = False
        self.catalogs = {'script': [], 'storyboard': []}
        self.active_path = self.active_board_json = None
        self.catalog_scan = {'busy': False, 'revision': 0, 'pending': False, 'stopped': False}
        self.catalog_results = queue.Queue(maxsize=1)
        self.desktop.pet.auto_variable('auto_adopt_var')
        self.desktop.storyboard_editor_page = self
        self.page_content.bind('<Destroy>', self.stop_catalog, add='+')

    def _build_editor(self):
        self.editor = S03EditorView(self, wheel_lines=VIEWER_WHEEL_LINES)
        self.editor_frame, self.shortcut_hint = self.editor.frame, self.editor.shortcut_hint
        self.find_bar, self.viewer = self.editor.find_bar, self.editor.viewer
        self.desktop.storyboard_editor_preview = self.viewer
        self.editor_frame.bind('<Map>', self._on_editor_map, add='+')
        self._set_viewer_text(S03_EMPTY_TEXT, editable=False)
        self._update_status_segment()

    def _on_editor_map(self, _event=None):
        if getattr(self.desktop, 'page_index', None) == PAGE_OF['storyboard']:
            self._register_files_panel_handler(default_path=self.active_path)

    def show_find_bar(self): self.editor.show_find_bar()
    def hide_find_bar(self): self.editor.hide_find_bar()
    def zoom_by(self, delta): self.editor.zoom_by(delta)
    def on_context_menu(self, event): return self.editor.popup_context_menu(event, document_dir_fn=document_dir)
    def open_any_document(self): self.editor.open_any_document()
    def _pick_default_document(self, catalogs): return pick_default_document(self.controller.adopted(), catalogs)

    def _register_storyboard_send_action(self):
        """底部发送键承载初步分镜制作；切页／销毁时撤销，避免过期入口。"""
        shared = getattr(self.desktop, 'shared_input', None)
        register = getattr(shared, 'set_stage_action', None)
        if not callable(register):
            return
        def run_send():
            return self.desktop.send_storyboard('')
        register('storyboard', run_send)
        def release(_event=None):
            if shared.stage_action('storyboard') is run_send:
                register('storyboard', None)
        anchor = getattr(self, 'page_content', None) or getattr(self.desktop, 'content', None)
        if anchor is not None:
            anchor.bind('<Destroy>', release, add='+')

    def _register_files_panel_handler(self, default_path=None):
        panel = getattr(self.desktop, 'files_panel', None)
        register = getattr(panel, 'set_select_handler', None)
        if not callable(register):
            return
        default_iid = None
        if default_path is not None:
            try:
                default_iid = Path(default_path).resolve().relative_to(self.project).as_posix()
            except (OSError, ValueError):
                default_iid = None
        register(PAGE_OF['storyboard'], self.show_document, default=default_iid)

    def _set_viewer_text(self, text, *, editable=False):
        self.editing = bool(editable)
        self.editor.set_text(text, editable=self.editing)

    def _matching_board_json(self, path):
        """由选中的分镜 JSON 或同名分镜 Markdown 反查对应的分镜 JSON 路径。"""
        target = Path(path).resolve()
        if target.suffix.lower() == '.json' and is_deliverable(target, 'storyboard'):
            return target
        for entry in self.catalogs.get('storyboard') or ():
            board = Path(entry['path']).resolve()
            if board.stem == target.stem:
                return board
        return None

    def show_document(self, path):
        """右侧文件栏或打开文件选中的文档进主编辑器；结构剧本同步选为当前制作来源。"""
        if not path:
            return
        target = Path(path).resolve()
        if not target.is_file():
            return
        if self.editing:
            self.exit_edit()
        self.active_path = target
        self.active_board_json = self._matching_board_json(target)
        # 若点选的是结构剧本，顺手记作本阶段当前输入，直接点发送即可按这份剧本制作分镜。
        script_paths = {Path(e['path']).resolve() for e in (self.catalogs.get('script') or ())}
        if target in script_paths:
            self.controller.choose('script', [target])
        elif self.active_board_json is not None:
            self.controller.choose('storyboard', [self.active_board_json])
        self._render_active_document()
        self._update_status_segment()

    def _render_active_document(self):
        target = self.active_path
        adopted = bool(target is not None and target in set(self.controller.adopted()))
        text = render_document_text(
            target, raw_json=self.raw_json_mode, adopted=adopted,
            read_json_fn=read, read_text_fn=read_text)
        self._set_viewer_text(text, editable=False)

    def _update_status_segment(self):
        summary = self.controller.summary()
        if self.active_path is not None:
            kind = '分镜' if self.active_board_json is not None else '结构剧本／文档'
            text = '当前：%s（%s）｜%s' % (self.active_path.name, kind, summary)
        else:
            text = summary or '初步分镜'
        setter = getattr(self.desktop, 'set_status_segment', None)
        if callable(setter):
            setter('storyboard_note', text, tooltip=S03_HINT_READ)

    # ── 编辑与保存 ──────────────────────────────────────────────────────
    def begin_edit(self):
        if self.active_path is None or not self.active_path.is_file():
            raise ValueError('请先在右侧文件栏选择要编辑的分镜或剧本文档')
        if self.active_path.suffix.lower() == '.json':
            self.raw_json_mode = True
            self._render_active_document()
        self.viewer.configure(state='normal')
        self.editing = True
        self.shortcut_hint.configure(text=S03_HINT_EDIT)
        self.viewer.focus_set()

    def exit_edit(self):
        if not self.editing:
            return
        self.save_edited()
        self.editing = False
        self._render_active_document()

    def save_edited(self):
        if not self.editing or self.active_path is None:
            return
        content = self.viewer.get('1.0', 'end-1c')
        if not content.strip():
            raise ValueError('文档内容不能为空')
        if self.active_path.suffix.lower() == '.json':
            parsed = json.loads(content)
            from domain.writing import validate_episode
            from contract.storyboard_paths import media_root
            from agent.core import save as save_json
            validate_episode(parsed, media_root(self.active_path))
            save_json(self.active_path, parsed)
        else:
            from agent.core import save_text as write_text
            write_text(self.active_path, content + '\n')
        self.desktop.status.set('已保存：' + self.active_path.name)

    def toggle_json_view(self):
        if self.active_path is None or self.active_path.suffix.lower() != '.json':
            return
        if self.editing:
            self.exit_edit()
        self.raw_json_mode = not self.raw_json_mode
        self._render_active_document()

    # ── 后台目录扫描与默认文档装载 ─────────────────────────────────────
    def stop_catalog(self, event):
        if event.widget is self.page_content:
            self.catalog_scan['stopped'] = True
            self.catalog_scan['revision'] += 1
            self.catalog_scan['pending'] = False

    def apply_catalogs(self, catalogs, automatic=False):
        from stage_execution_service import normalize_storyboard_for_desktop
        if normalize_storyboard_for_desktop(self.desktop):
            if automatic:
                self.catalog_scan['pending'] = True
                return False
            catalogs = self.controller.refresh_catalogs()
        catalogs = self.controller.apply_catalogs(catalogs)
        self.catalogs = catalogs
        if not self.controller.selection('script'):
            sync_structured_script(self.project)
        self.loaded = True
        if self.active_path is None or not self.active_path.is_file():
            chosen = self._pick_default_document(catalogs)
            if chosen is not None:
                self.active_path = chosen
                self.active_board_json = self._matching_board_json(chosen)
                self._register_files_panel_handler(default_path=chosen)
                self._render_active_document()
        elif not self.editing:
            self.active_board_json = self._matching_board_json(self.active_path)
        self._update_status_segment()
        return True

    def refresh(self, automatic=False):
        """手动刷新立即扫描；初次与监听在后台读取，不阻塞 Tk 主线程。"""
        if self.catalog_scan['stopped']:
            return False
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
        if self.catalog_scan['stopped'] or Path(self.desktop.root).resolve() != self.project:
            return
        if revision != self.catalog_scan['revision']:
            pass
        elif ok:
            try:
                self.apply_catalogs(value, automatic=True)
            except (OSError, ValueError, KeyError) as exc:
                if self.desktop.content is self.page_content:
                    self.desktop.status.set('分镜目录结果已过期，将在下次文件变动后重试：' + str(exc))
        else:
            if not self.loaded:
                self._set_viewer_text('分镜目录加载失败，请右键「刷新分镜列表」重试：' + str(value), editable=False)
            if self.desktop.content is self.page_content:
                self.desktop.status.set('分镜目录刷新失败，将在下次文件变动后重试：' + str(value))
        if self.catalog_scan['pending']:
            self.catalog_scan['pending'] = False
            self.refresh(automatic=True)

    # ── 分镜核心动作（右键入口）────────────────────────────────────────
    def renumber_shots(self):
        import ui.shot_numbering as shot_numbering
        targets = [entry['path'] for entry in catalog(self.project, 'storyboard')]
        if not targets:
            raise ValueError('还没有分镜 JSON，无需重排编号')
        plan = shot_numbering.renumber(self.project, targets, apply=False, log=lambda _text: None)
        if not plan['mapping']:
            problems = shot_numbering.verify(self.project, targets)
            self.desktop.status.set('镜头编号已按剧本顺序连续，无需重排' if not problems
                                    else '镜头编号检查：' + '；'.join(problems))
            return
        preview = '、'.join('%s→%s' % (o, n) for o, n in sorted(plan['mapping'].items())[:12])
        if not confirm(self.desktop.win, '重排镜头编号',
                       f'重排 {len(plan["mapping"])} 个镜头编号：{preview}{"…" if len(plan["mapping"]) > 12 else ""}\n'
                       f'并改写 {len(plan["contents"])} 个文件里的引用、{len(plan["renames"])} 项文件名。\n'
                       '只改编号，不碰内容；会先备份。是否继续？', dangerous=True):
            self.desktop.status.set('已取消重排镜头编号')
            return
        def work():
            shot_numbering.renumber(self.project, targets, apply=True, log=lambda _text: None)
            problems = shot_numbering.verify(self.project, targets)
            return '镜头编号已重排；' + ('编号连续' if not problems else '仍有问题：' + '；'.join(problems))
        def done(result):
            self.refresh()
            self.desktop.status.set(result)
        self.desktop.async_(work, done)

    def browse(self):
        from contract.project_stages import writing
        values = FileDialog(self.desktop.win).open_files(
            title='选择用于制作分镜的剧本（可多选）',
            initialdir=writing(self.project),
            filetypes=[('剧本', '*.md *.txt *.docx')])
        if values:
            chosen = [Path(p).resolve() for p in values]
            self.controller.choose('script', chosen)
            self.show_document(chosen[0])
            self.refresh()

    def _target_boards(self):
        if self.active_board_json is not None and self.active_board_json.is_file():
            return [self.active_board_json]
        return [Path(e['path']).resolve() for e in (self.catalogs.get('storyboard') or ())
                if Path(e['path']).is_file()]

    def adopt_selected(self):
        targets = self._target_boards()
        if not targets:
            raise ValueError('当前还没有可采用的分镜 JSON')
        used = self.controller.adopted()
        incoming = [p for p in targets if p not in used]
        already = [p for p in targets if p in used]
        if not incoming:
            self.desktop.status.set('所选 JSON 均已采用，无需重复采用')
            return
        check_adoptable(incoming)
        impact = adoption_impact(self.project, targets)
        impact_note = ('；影响预览：' + str(impact['summary'])) if impact.get('summary') else ''
        skipped = f'（另有 {len(already)} 份已采用，已跳过）' if already else ''
        self.desktop.adopt_frame_jsons(incoming)
        self.refresh()
        self._render_active_document()
        switched = self.desktop.sync_working_episode()
        self.desktop.status.set(
            f'新增采用 {len(incoming)} 份{skipped}；' + self.controller.summary()
            + ('；工作集已切到最新采用的分镜' if switched else '；工作集保持不变')
            + impact_note + self.desktop.final_storyboard_hint() + self.desktop.shot_numbering_hint())

    def remove_selected(self):
        targets = ([self.active_board_json] if self.active_board_json is not None
                   else sorted(self.controller.adopted(), key=lambda p: str(p)))
        if not targets:
            raise ValueError('当前没有已采用的分镜')
        self.desktop.remove_frame_jsons(targets)
        self.refresh()
        self._render_active_document()
        self.desktop.status.set('已取消所选分镜的采用；分镜文件与资产保留')

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
