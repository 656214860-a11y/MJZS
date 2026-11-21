"""首帧管理页（阶段 keyframe）的页面构建（方法名为 ``Desktop.storyboard``，侧栏第 07 项）。

从 ``desktop.Desktop`` 原样迁出（R1504 拆分步骤 3，一页一轮）：方法体未改，``self`` 语义不变，
``Desktop`` 通过继承 ``StoryboardPageMixin`` 获得。confirm／open_path／FileDialog（R1989 J2）改由实例的
``storyboard_page_services`` 提供，默认服务在 ``Desktop`` 组合入口按调用时取 ``desktop`` 模块的当前值，
测试按 ``desktop.<名字>`` 打补丁照常生效；本模块只从 ``desktop_page_support`` 取页面常量。
"""
import infra.pet_state as pet_state
import contract.pet_bus as pet_bus
from dataclasses import dataclass
from typing import Callable
import ui.asset_thumbs as asset_thumbs
import contract.frame_checks as frame_checks
import tkinter as tk
import infra.ui_plugin_registry as ui_plugin_registry
from agent.core import read
from pathlib import Path
from responsive_ui import CheckboxColumn, FlowBar, MIN_COL, bind_row_toggle, bind_space_toggle, configure_check_column, fit_columns_by_content, fit_row_height, refresh_request_width
from contract.storyboard_paths import media_root
from tkinter import ttk
from ui_tokens import TEXT_ROWS, COLORS, SPACING, TABLE_HEADER_FONT, TABLE_ROW_FONT
from ui_widgets import DataTable, DescriptionBlock, PrimaryButton, SelectBox
from ui.desktop_page_support import ASSET_ROW_HEIGHT, THUMB_SIZE

PAGE = pet_state.PAGE_OF


def _configure_table_style(tree, style, thumb):
    """表格行高与表头共用 ui_tokens，页面只给样式名和缩略图尺寸。"""
    current = ttk.Style(tree)
    current.configure(style, font=TABLE_ROW_FONT)
    current.configure(style + '.Heading', font=TABLE_HEADER_FONT,
                      foreground=COLORS['text_primary'])
    fit_row_height(tree, thumb, style=style)


@dataclass(frozen=True)
class StoryboardPageServices:
    """首帧管理页的外部 UI 能力；由组合入口提供，不携带全局宿主（R1606 模式，J2）。"""
    open_path: Callable
    file_dialog: Callable
    confirm: Callable


class StoryboardPageMixin:
    """Desktop 的首帧管理页构建（见模块说明）。"""
    def storyboard(self):
        try:
            self.current_frame_json()
        except ValueError:
            # 空项目：没有分镜 JSON 时不建表，先说明缺什么、去哪一步补（L4-U6）。
            # 句子与 orchestrator/storyboard_selection.current_source 的提示一致。
            DescriptionBlock(self.content, text='这个项目还没有分镜 JSON，请先到'
                             + pet_bus.stage_step('storyboard') + '采用一份。').pack(
                                 anchor='w', pady=SPACING['xs'])
            PrimaryButton(self.content, text='去第%02d步' % (PAGE['storyboard'] + 1),
                          command=lambda: self.go(PAGE['storyboard'])).pack(
                              anchor='w', pady=SPACING['sm'])
            return
        return _FirstFramePage(self).build()


class _FirstFramePage:
    """首帧管理页（从 StoryboardPageMixin.storyboard 的闭包原样改写成类，R1814）：共享的局部变量成了实例属性，嵌套函数成了方法；原来的 self（桌面主窗）改叫 page。"""
    def __init__(self, page):
        self.page = page

    def build(self):
        watch_list, table_box = self._build_state_and_table()
        self.table.heading('#0',command=self.toggle_all_frames)
        bind_space_toggle(self.table,self.toggle_frame)
        self.table.grid(row=0,column=0,sticky='nsew')
        actions=FlowBar(self.page.content);actions.pack(
            side='bottom', fill='x', pady=SPACING['sm']
        )
        self.target_row.pack(
            side='bottom', fill='x', pady=(SPACING['sm'], SPACING['none'])
        )
        table_box.pack(fill='both',expand=True)
        from orchestrator.stage_models import manual_command
        make_button=self.page.button(actions,'手动制作首帧',manual_command(self.page,'keyframe',self.make_frames,self.page.win))
        make_button.configure(style='Tokens.Primary.TButton')
        make_button.pack_configure(
            padx=(SPACING['none'], SPACING['sm']), pady=SPACING['xs']
        )
        ui_plugin_registry.module('stage_flow').follow(make_button,'keyframe')
        # R2942：「阶段配置」按钮＋模型下拉框删除。

        self.page.pet.auto_variable('auto_first_frame_var')
        self.target.bind('<<ComboboxSelected>>',self.choose_target)
        # 选中镜头右侧：刷新与查看在前，文件维护三键在后（下行内容框改动本地图片，低频且需谨慎）。
        self.secondary_action('刷新首帧列表',self.refresh)
        self.secondary_action('查看首帧提示词',self.prompt_details)
        self.secondary_action('查看镜头资产',lambda:self.page.notifier.info(ui_plugin_registry.module('agent.shot_assets').summary(self.home(self.selected())[0],self.selected()).replace('；','\n'), title='镜头资产', modal=True))
        self.replace_button=self.secondary_action('导入 / 替换选中首帧',self.replace)
        # 第 46 期第 9 条：这颗按钮改名「批量删除首帧」——它删的是勾选那一批（高亮不算数），
        # 只想删一镜时用内容框上的右键菜单「删除」（目标就是右键那一行）。
        self.delete=self.secondary_action('批量删除首帧',lambda:self.delete_checked_frames())
        self.secondary_action('恢复删除的首帧',lambda:self.restore_selected())
        self.table.bind('<<TreeviewSelect>>',self.selection_changed)
        from cell_hover import CellHover
        link_cols=('#0','#5','#6')
        # 第 46 期第 1 条：右键＝查看（这一格）／删除（这一镜的首帧）。
        # 第 55 期第 2 条：#5（图片文件）那一列盖着缩略图，不再走高亮——打勾选框那一格照旧带图。
        self.table.cell_hover=CellHover(self.table,link_cols,lambda sid,col:self.page.safe(lambda:self.open_cell(sid,col)),cell_image=lambda sid,col:(self.page.win._tick_images[int(self.checked.get(sid,False))] if col=='#0' else None),checked=lambda sid:self.checked.get(sid,False),toggle=self.toggle_frame,delete=lambda sid:self.page.safe(lambda:self.delete_one(sid)))
        bind_row_toggle(self.table,self.toggle_frame,link_cols)
        # 第 53 期第 5 条：「图片文件」那一列盖一层首帧缩略图——已导入、Tk 读得出来的才盖；
        # 还没导入／图不在／格式 Tk 不认（jpg 等）就不盖，那一格退回原来写的文件名。
        # 盖住的那一格鼠标落到这层图上，照旧转给 CellHover（单击仍是打开图片，一条没改）。
        from cell_hover import CellImages,ZOOM_SIZE
        self.ZOOM_SIZE = ZOOM_SIZE
        self.table.cell_images=CellImages(self.table,('#5',),self.frame_thumb,hover=self.table.cell_hover,
                                     background=self.frame_row_background,zoom=self.frame_zoom)
        # 第 55 期第 1 条：视图一变就重排已经收进盖图那一层（watch_view），这儿不必再交代一遍。
        self.refresh()
        requested=getattr(self.page,'pending_frame_selection',None)
        if requested and self.table.exists(requested):
            self.table.selection_set(requested);self.table.focus(requested);self.table.see(requested);self.selection_changed()
        self.page.pending_frame_selection=None
        # 第 68 期任务 12：一屏里有几份分镜就盯几份（只有一份时与从前一样，就一个）。
        for _watched in sorted({str(item.resolve()) for _i,_s,item,_b,_e in self.rows}):
            watch_list(table_box,Path(_watched),self.refresh)

    def _build_state_and_table(self):
        """读取分镜与勾选状态，建出首帧表格及其列样式（从 build 原样切出，R1814）。"""
        from ui.keyframe_import import resume,watch_list
        from domain.keyframe_batch import frame_prompt
        self.frame_prompt = frame_prompt
        from orchestrator.keyframe_page_controller import KeyframePageController
        resume(self.page)
        self.source=self.page.current_frame_json()
        self.episode=read(self.source);self.base=media_root(self.source)
        self.rows=self.load_rows()
        self.page_controller=KeyframePageController(self.source,self.episode,self.base,self.rows)
        self.row_ctx=self.page_controller.row_context
        from domain.writing import validate_episode
        validate_episode(self.episode,self.base)
        # 勾选表按行编号记账：只有一份时键就是那一份的路径（与从前同一个键），多份时合成一张。
        self.page._frame_checks_key=self.page_controller.checks_key
        self.page._frame_checks_merged=self.page_controller.merged
        if not hasattr(self.page,'frame_checks'):self.page.frame_checks={}
        self.checked=self.page.frame_checks.get(self.page._frame_checks_key)
        if self.checked is None:self.checked=self.page.frame_checks[self.page._frame_checks_key]=frame_checks.FrameChecks()
        if hasattr(self.page,'set_status_segment'):
            # 「全部分镜」不是一份文件：这一栏写清这一屏列的是哪几份（第 68 期任务 12）。
            # R3016 P2：改挂统一底栏左区段；操作提示进悬停全文。
            total=len({str(item.resolve()) for _i,_s,item,_b,_e in self.rows})
            label=('全部 %d 份已采用分镜'%total) if total>1 else self.source.relative_to(self.page.root).as_posix()
            self.page.set_status_segment('storyboard','当前 JSON：'+label,
                                         tooltip='镜头编号保留；点表头勾选框切换全部，单击镜头行勾选单个。')
        # 底部两行先贴底占位、内容框最后占满剩余高度，主界面缩放时按钮与下拉框始终可见。
        table_box=ttk.Frame(self.page.content)
        self.target_row=FlowBar(self.page.content)
        # 选中镜头一行紧贴镜头内容框下方：左侧是下拉框，右侧依次是刷新、查看与文件维护按钮。
        ttk.Label(self.target_row,text='选中镜头').pack(
            side='left', padx=(SPACING['none'], SPACING['sm'])
        )
        self.available_shots={iid:shot for iid,shot,_item,_bse,_one in self.rows}
        self.target=SelectBox(self.target_row,values=list(self.available_shots));self.target.pack(
            side='left', padx=(SPACING['none'], SPACING['sm'])
        )
        if self.available_shots:self.target.current(0)
        frame_columns=[('id','镜头',155),('title','内容',175),('duration','秒数',60),
                       ('status','首帧状态',120),('file','图片文件(点击查看)',180),
                       ('prompt','首帧图片提示词(点击查看)',480)]
        table_shell=DataTable(table_box, columns=[(key,title,MIN_COL) for key,title,width in frame_columns],
            show='tree headings', height=TEXT_ROWS['xl'], selectmode='browse', style='Frame.Treeview',
            empty_text='暂无镜头', auto_hide_scrollbars=True)
        self.table=table_shell.tree
        _configure_table_style(self.table,'Frame.Treeview',THUMB_SIZE);refresh_request_width(self.table)
        table_shell.grid(row=0,column=0,sticky='nsew')
        table_box.columnconfigure(0,weight=1);table_box.rowconfigure(0,weight=1)
        configure_check_column(self.table)
        for key,title,width in frame_columns:
            self.table.heading(key,text=title);self.table.column(key,width=MIN_COL,minwidth=MIN_COL)
        self.table.tag_configure(
            'completed', background=COLORS['row_completed'], foreground=COLORS['success']
        )
        from responsive_ui import auto_height
        auto_height(self.table, table_box, row_height=ASSET_ROW_HEIGHT)   # 行高了，按 80 算，别再按 34
        self.box=CheckboxColumn(self.table,self.page.win._tick_images,lambda sid:self.checked.get(sid,False),lambda sid,v:self.checked.__setitem__(sid,v))
        return watch_list, table_box

    # 第 68 期任务 12：用户报「全部分镜显示不全」。这一页原来只读当前那一份分镜；现在「选择分镜」
    # 选到「全部分镜」时，把已采用的每一份的镜头一起列出来，每一镜各自认自己那一份的目录与文件。
    # 只有一份（用户选了「只这一份」，或本来就只采用了一份）时，下面与从前一字不差。
    def load_rows(self):
        from domain.storyboard_rows_service import frame_rows
        return frame_rows(self.page.root, self.source, self.episode, self.base, self.page.asset_scope(), self.page.note)

    def use_rows(self):
        """刷新后将每个表格行重新归属到它的分镜来源。"""
        self.page_controller.replace_rows(self.rows)

    def home(self, shot):return self.page_controller.home(shot)

    def iid_of(self, shot):return self.page_controller.iid_of(shot)

    def frame(self, shot,required=True):return self.page_controller.frame_path(shot,required)

    def exists(self, shot):return self.page_controller.frame_exists(shot)

    def fit_frame_columns(self):
        fit_columns_by_content(self.table, {'prompt': lambda w: min(540,max(360,w))})

    def selected(self):
        if not self.table.selection():raise ValueError('请先在镜头内容框中选择一行')
        return self.shot_row(self.table.selection()[0])

    def update_header_check(self):
        self.box.refresh_header()

    def toggle_frame(self, sid):
        self.box.toggle(sid);self.selection_changed()

    def toggle_all_frames(self):
        self.box.toggle_all();self.selection_changed()

    def selection_changed(self, event=None):
        valid=bool(self.table.selection())
        available=valid and self.exists(self.selected()) and not self.selected().get('frame_deleted')
        # 第 46 期第 9 条：删除按钮改成批量——它认的是勾选行，所以按勾选数决定能不能按。
        # 第 47 期第 1 条：「批量删除首帧」按统一口径亮起来——勾选优先，高亮那一行也算
        # （只有一个镜头高亮时按钮不再是灰的，点下去删的就是它，提示里会写明）。
        self.delete.configure(state='normal' if (self.page_checked() or self.table.selection()) else 'disabled')
        self.replace_button.configure(state='normal' if valid else 'disabled')
        if valid:self.target.set(self.table.selection()[0])
        self.update_header_check()

    def refresh(self):
        self.rows=self.load_rows()
        self.use_rows()
        for _i,_s,item,bse,one in self.rows:
            if item.resolve()==self.source.resolve():self.episode,self.base=one,bse;break
        previous=self.table.selection()
        # 重建行以前记住内容框的滚动位置：刷新或无人值守轮询重建后，内容不应跳回顶部。
        offset=0.0;top=''
        try:offset=self.table.yview()[0];top=self.table.identify_row(1)
        except tk.TclError:pass
        self.table.delete(*self.table.get_children())
        # 建行以前先按最新首帧状态对齐勾选：首帧刚就位的镜头自动取消勾选，缺首帧的新镜头默认勾选，
        # 用户手动改过的待生成镜头保持不动——无人值守轮询刷新因此不会悄悄改掉用户的批次。
        states={iid:(self.exists(shot) and not shot.get('frame_deleted'),bool(shot.get('frame_deleted'))) for iid,shot,_i,_b,_e in self.rows}
        available=sum(1 for present,_ in states.values() if present)
        self.checked.sync([(iid,*states[iid]) for iid in states])
        for iid,shot,_i,_b,_e in self.rows:
            present=states[iid][0]
            state='已导入' if present else ('待重新生成' if states[iid][1] else '待生成 / 待导入')
            # 第 54 期第 3 条：这一格盖得上缩略图就只留图——那句「图与字叠着多余」的活
            # 第 55 期第 3 条起由盖图那一层自己做（盖上收走、撤掉写回），这里照旧写文件名与「—」：
            # 原来为了判「这一格还写不写字」在这儿逐镜解一遍缩略图（几十上百镜就是几十上百张），白解。
            file_text=Path(shot['frame']).name if present else '—'
            self.table.insert('','end',iid=iid,text='',image=self.page.win._tick_images[int(self.checked[iid])],values=(shot['id'],shot['title'],shot['duration'],state,file_text,self.frame_prompt(shot).replace('\n',' ') or '待补齐首帧提示词'),tags=('completed',) if present else ())
        self.available_shots.clear();self.available_shots.update({row[0]:row[1] for row in self.rows})
        self.target.set_values(list(self.available_shots))
        self.fit_frame_columns()
        # 第 53 期第 5 条：行重建之后格子全挪了位，缩略图那一层跟着重排一次。
        images=getattr(self.table,'cell_images',None)
        if images is not None:images.refresh()
        if previous and self.table.exists(previous[0]):self.table.selection_set(previous[0])
        if top and self.table.exists(top):self.table.yview_moveto(offset);self.table.see(top)
        self.selection_changed()
        # 这句话按「当下有几镜已就位」说，不按「这一次对齐新取消了几镜」——
        # 原来拿的是 sync 的增量，三虎心跳重拍本页时第二次对齐就没增量了，
        # 状态栏会被改回不带这一句的版本（第 71 期发现的偶发）。
        note=f'；其中 {available} 镜首帧已就位，已自动取消勾选' if available else ''
        self.page.status.set(f'现有首帧 {available} 张；待补图 {len(self.episode["shots"])-available} 镜'+note)

    def page_checked(self):
        ids=self.checked.checked([iid for iid,_s,_i,_b,_e in self.rows])
        return ids or None

    def work_targets(self):
        """第 47 期第 1 条：删除／制作这一类动作的目标——勾选优先，高亮兜底。

            返回 (ids, 来源)；来源为 'shown' 时说明这一行是按高亮算的（文案里由 work_hint 补一句）。
            """
        from responsive_ui import work_rows
        return work_rows(self.table,lambda sid: self.checked.get(sid,False))

    def work_hint(self, ids,how):
        from responsive_ui import work_hint as hint
        return hint(ids,how)

    # 第二行：最高频的生成与查看，选中镜头后即可用；首帧制作用主色按钮突出。
    # 第 47 期第 3 条：点「手动制作首帧」先问一句模型配没配（没配就问要不要现在去「阶段配置」）。
    def pick_batch(self):
        """「手动制作首帧」要提交的那一批：勾选的镜头，按所属分镜分堆。

            第 68 期任务 12：「全部分镜」把几份分镜合成一屏，而首帧制作是一次一份的事——所以一次
            只提交一堆（当前选中的那一堆），其余几堆说清楚让用户切过去再做，不闷声丢掉。
            """
        item,ids,rest=self.page_controller.pick_batch(self.page_checked(),self.table.selection())
        if not ids:return item,None
        if rest:
            self.page.note('「手动制作首帧」一次做一份分镜：先做 %s 那一份的 %d 镜，另有 %d 镜请切到它们那一份再生成。'
                      %(item.stem,len(ids),rest))
        return item,ids

    def make_frames(self):
        item,ids=self.pick_batch()
        return ui_plugin_registry.module('keyframe_comfy').show(self.page,item,ids)

    def restore_selected(self):
        shot=self.selected();item,bse,one=self.home(shot)
        return self.page.restore_keyframe(shot,one,bse,item)

    def secondary_action(self, text, action):
        """Keep the shared safe callback while applying this page's token button contract."""
        button=self.page.button(self.target_row,text,action)
        button.configure(style='Tokens.Secondary.TButton')
        button.pack_configure(
            padx=(SPACING['none'], SPACING['sm']), pady=SPACING['xs']
        )
        return button

    def prompt_details(self):
        from ui.prompt_window import show as show_prompt_window
        shot=self.selected();prompt=self.frame_prompt(shot)
        if not prompt:self.page.status.set(shot['id']+' 还没有首帧图片提示词，请先补齐后再复制')
        show_prompt_window(self.page.win,shot['id']+' · 首帧图片提示词',prompt,status=self.page.status,
                           receipt=shot['id']+' 首帧图片提示词已复制，可直接粘贴到生图或对话工具',
                           empty_text='此镜头尚未填写首帧图片提示词。',
                           empty_hint='没有可复制的首帧图片提示词，请先补齐后再复制')

    def view_frame_image(self, sid):
        shot=next(s for s in self.episode['shots'] if s['id']==sid)
        if self.exists(shot) and not shot.get('frame_deleted'):
            path=(self.base/shot['frame']).resolve()
            if path.is_file():
                self.page.storyboard_page_services.open_path(path);return
        self.page.status.set(sid+' 尚未导入首帧图片，可先导入或生成。')

    def open_cell(self, sid,col):
        self.table.selection_set(sid);self.table.focus(sid);self.selection_changed()
        if col=='#0':self.toggle_frame(sid)
        elif col=='#5':self.view_frame_image(sid)
        elif col=='#6':self.prompt_details()

    # 第 50 期第 1 条：「选择镜头 JSON」按钮按用户要求删除（上一步已经改掉文案）。
    def choose_target(self, event=None):
        if self.table.exists(self.target.get()):self.table.selection_set(self.target.get());self.table.see(self.target.get());self.selection_changed()

    def replace(self, shot=None):
        shot=shot or self.selected();path=self.page.storyboard_page_services.file_dialog(self.page.win).open_file(initialdir=self.base/'frames',filetypes=[('PNG','*.png')])
        if not path:return
        raw=Path(path).read_bytes()
        from stage_execution_service import replace_stage_keyframe
        result=replace_stage_keyframe(self.base,self.source,self.episode,shot,raw)
        if not result.ok:raise ValueError(result.reason)
        if self.source.resolve()==(self.page.studio.episode_dir/'episode.json').resolve():self.page.studio.episode=self.episode
        self.refresh();self.table.selection_set(self.iid_of(shot));self.selection_changed()
        self.page.status.set('首帧已保存为 '+shot['id']+'.png，镜头JSON已同步')

    def shot_row(self, sid):
        row=self.row_ctx.get(sid)
        if row is None:raise ValueError('镜头已被其他操作移除，请刷新首帧列表')
        return row[0]

    def delete_one(self, sid):
        """逐个删除：目标就是右键（或下拉框）点中的那一镜。"""
        shot=self.shot_row(sid);item,bse,one=self.home(shot)
        self.page.delete_keyframe(shot,one,bse,item)

    def delete_checked_frames(self):
        """批量删除：勾选的那些镜头；一个都没勾就按高亮那一行算（第 47 期第 1 条）。

            已删除与没有首帧的镜头自动跳过。
            """
        wanted,how=self.work_targets()
        shots=[shot for iid,shot,_i,_b,_e in self.rows
               if iid in set(wanted) and self.exists(shot) and not shot.get('frame_deleted')]
        if not shots:raise ValueError('先在镜头内容框里勾选要删除首帧的镜头')
        listed='、'.join(shot['id'] for shot in shots[:12])+('…' if len(shots)>12 else '')
        if not self.page.storyboard_page_services.confirm(self.page.win,'批量删除首帧',
                f'删除勾选的 {len(shots)} 镜首帧？\n{listed}\n\n图片将移入首帧回收目录，可恢复；'
                    '镜头记录、已生成视频与未勾选的镜头不受影响。'+self.work_hint(wanted,how),
                dangerous=True):
            return []
        done=[]
        for shot in shots:
            item,bse,one=self.home(shot)
            try:
                if self.page.delete_keyframe(shot,one,bse,item,ask=False,rebuild=False):done.append(shot['id'])
            except (OSError,ValueError,KeyError) as exc:
                self.page.note(shot['id']+' 首帧未删除：'+str(exc))
        self.refresh()
        self.page.status.set('已删除 %d 镜首帧（移入回收站，可恢复）：%s'%(len(done),'、'.join(done)))
        return done

    def frame_thumb(self, sid,column):
        try:
            shot=self.shot_row(sid)
            if shot.get('frame_deleted') or not self.exists(shot):return None
            image=asset_thumbs.thumbnail(self.page.win,self.frame(shot,False),THUMB_SIZE)
        except (ValueError,OSError):
            return None
        return None if image is None else (image,'')

    def frame_row_background(self, sid):
        try:
            return COLORS['row_completed'] if self.exists(self.shot_row(sid)) else COLORS['background_card']
        except (ValueError,OSError):
            return COLORS['background_card']

    def frame_zoom(self, sid,column):
        """鼠标停在缩略图上：另解一张大图（第 57 期第 5 条）——把 72 像素的小图拉大只会糊。"""
        try:
            shot=self.shot_row(sid)
            if shot.get('frame_deleted') or not self.exists(shot):return None
            return asset_thumbs.thumbnail(self.page.win,self.frame(shot,False),self.ZOOM_SIZE)
        except (ValueError,OSError):
            return None
