"""Windows desktop UI using Python standard-library Tkinter."""
# Keep the small built-in hash backend decision ahead of every optional module.
# Several imported services fingerprint files during initialization; doing this
# here avoids loading OpenSSL merely because the desktop shell starts.
import infra.app_logging as app_logging
import infra.hash_backend as hash_backend
hash_backend.install()
import contract.pet_bus as pet_bus
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from contract.storyboard_paths import media_root, project_root
from responsive_ui import FlowBar,QuietVar,configure_check_column,CheckboxColumn,fit_columns_by_content,fit_row_height,row_height_for
from local_video import open_studio,LocalStudio,settings_window
from orchestrator.engine import review_label
from domain.project_naming import dated_path
from domain.video_task_state import assert_prompt_editable,prompt_locked,poll_delay,elapsed_text,submission_block_reason
from ui.video_progress import snapshot as shared_video_snapshot,display as progress_display,summary as progress_summary,LABELS,status_detail
import infra.project_settings as project_settings
import ui.asset_thumbs as asset_thumbs
import infra.ui_plugin_registry as ui_plugin_registry
from contract.platform_tools import open_path
from ui_tokens import CHAR_WIDTH, TEXT_ROWS, WRAPLENGTH, COLORS, FONTS, SPACING
from ui_widgets import (SelectBox, BaseDialog, Card, BusyState, ContextMenu, DataTable, LineInput, NotificationDispatcher,
                        ask_confirmation, ask_string,
                        PrimaryButton, SecondaryButton, TextArea)
from ui.ui_dialogs import FileDialog
from ui.ui_motion import Spinner
from ui.ui_shortcuts import ShortcutRegistry

ROOT=Path(__file__).resolve().parent
# 第 30 期第 2 条：「勾选要上传的镜头资产」改名「选择镜头资产」——线上／本地一个说法。
# 第 33 期第 1 条：这四个字不再单独占一行，改做表格第一列的列头（就排在「资产编号」左边）。
# 第 41 期第 1 条：这一栏整个并进上方的镜头内容框（就排在「内容」右边），一格一镜、
# 点一格弹出可勾选的下拉框——原来单摆的那张表只跟「正在编辑的那一镜」走，全选镜头号
# 之后整栏还是只有一镜的资产亮着（用户报的那条 BUG）。
# 第 45 期：示例／提示文字统一的灰（与「剧本准备」页创意栏那一份同一个色号）。
PLACEHOLDER_INK=COLORS['text_secondary']
ASSET_TITLE='选择资产'
ASSET_FIELD='assets'
# 第 53 期第 5 条：「首帧」那一列要盖一层首帧缩略图（Tk 的 value 格只写得了文字），行高得跟着
# 放大——这一张表单给一个样式，别的内容框照旧 34。可见行数由 6 收到 4，整页高度几乎没变，
# 底下的提示词框与那两行按钮不会被顶出可视区。
SHOT_THUMB_SIZE=27
# 第 58 期第 2 条：行高不再写死——「首帧」那一列摆多大的缩略图，行就有多高（见
# responsive_ui.fit_row_height；这个常量是算出来的期望值，供自检对账）。
SHOT_ROW_HEIGHT=row_height_for(SHOT_THUMB_SIZE)
SHOT_ROWS=4
# 第 57 期第 5 条：「选择资产」那一格改成弹窗（勾选与看图并进同一处）——一行一项资产，
# 缩略图与镜头表那一列同一档，行高跟着它走。
PICK_THUMB_SIZE=27
# 第 57 期第 2 条：这一镜正在制作时点勾选——把原因写在窗里，不弹模态错误框。
LOCKED_NOTE='这一镜正在制作：勾选暂时改不动，可以看图。'
LOCKED_SAY='勾不动：这一镜正在制作，等它做完再改。'

PICK_ROW_HEIGHT=row_height_for(PICK_THUMB_SIZE)      # 第 58 期第 2 条：同上，按图高算
PICK_ROWS=6
# 状态中文名只有 video_progress.LABELS 一份：同一镜头的状态在表格和进度条里说法必须一致。


def pending_checked_shots(studio, checked_ids):
    """从勾选镜头中筛出仍需提交的：只允许首次提交、明确失败重试及需修改成果返工。"""
    st = studio.state(); todo = []
    existing = {s['id'] for s in studio.episode['shots'] if isinstance(s, dict) and s.get('id')}
    for sid in checked_ids:
        if sid not in existing:
            continue
        versions = st['shots'].get(sid, [])
        if submission_block_reason(versions):
            continue
        todo.append(sid)
    return todo


def play_ready(app, selected):
    """选中镜头最近一版的成片文件是否在盘上（播放按钮可用性）。"""
    if app.play_button is None or not selected:
        return False
    versions = app.studio.state()['shots'].get(selected[0], [])
    files = [v for v in versions if v.get('file')]
    return bool(files and (app.root / files[-1]['file']).is_file())

def work_targets(app):
    """「制作／删除」这一类动作的目标（第 47 期第 1 条）：勾选优先，兜底高亮那一行。

    返回 (ids, 来源)：来源是 'checked'／'shown'／''；只算还在本地视频列表里的镜头。
    勾选那份取自 edit_checks（与内容框上的小勾同源），高亮那一行取自 Treeview——
    两套口径从此在这里合流：高亮一行却没勾上时不再回一句「请先勾选」。
    """
    shots=getattr(app.studio,'episode',{}).get('shots',[]) or []
    live={s['id'] for s in shots if not s.get('video_deleted')}
    ids=[sid for sid in live if app.edit_checks.get(sid,False)]
    if ids:return [s['id'] for s in shots if s['id'] in ids],'checked'
    from responsive_ui import shown_row
    row=shown_row(app.tree)
    if row and row in live:return [row],'shown'
    return [],''


def work_hint(ids,how):
    """统一口径下的一句说明（只有按高亮算的时候才有内容）。"""
    from responsive_ui import work_hint as hint
    return hint(ids,how)


class App:
    def __init__(self,window,root=None,settings_callback=None,prompt_callback=None,episode_file=None,footer_parent=None,missing_frame_callback=None,stage_callback=None,report_callback=None,prompt_stage_callback=None,manual_command_factory=None):
        if settings_callback is not None:self.settings=settings_callback
        self.prompt_callback=prompt_callback
        # 第 32 期第 6 条：这一页的「阶段配置」按钮要弹对应的阶段面板，由宿主传进来
        # （本工作台同时服务本地与线上生成，自己不知道页序号）。
        self.stage_callback=stage_callback
        # 「手动制作提示词」属于分镜定稿中的提示词渲染职责，与下面「手动制作视频」
        # 的视频阶段不是同一份配置：两者各开各的面板（宿主传进来）。
        self.prompt_stage_callback=prompt_stage_callback or stage_callback
        # 第 47 期第 5 条：手动提交收了尾由宿主那条出口说给三虎（这一页自己不知道页序号）。
        self.report_callback=report_callback
        # 编排（弹窗、模型检查、自动状态）属于阶段服务；视频视图只接收宿主提供的命令工厂。
        # 独立嵌入或界面测试没有宿主时，保留直接执行这一最小、可预期的降级行为。
        self.manual_command_factory=manual_command_factory or (lambda _host, _stage, action, _parent: action)
        self.missing_frame_callback=missing_frame_callback
        self.root=Path(root or ROOT); self.window=window; self.resize_scheduler=None; self.scheduler=window.winfo_toplevel(); self.studio=open_studio(self.root,episode_file=episode_file); self.busy=False; self.results=queue.Queue()
        self.prompt_buttons=[];self.submitting_sid=None;self.next_ui_update=0;self.last_poll_messages={};self.polling_sid=None;self.poll_wait=5
        self.next_poll=0;self.quiet_run=False;self.poll_cursor=0;self.editing_sid=None;self.edit_checks={};self.local_messages=queue.Queue();self.local_submit_sid=None;self.local_submit_error={}
        self.auto_submitted=set();self.auto_submit_due=0
        self.footer=ttk.Frame(footer_parent or window)
        self.footer.pack(side='bottom',fill='x',pady=SPACING['xs'])
        # Embedded in the shared project workspace.
        # 第 38 期第 1 条：这一行只报本页那一侧，占位文字也别把两侧都写上。
        self.status=tk.StringVar();self.notifier=NotificationDispatcher(self.status, parent=window);self.shortcuts=ShortcutRegistry();self.shared_progress=QuietVar(value='进度读取中…')
        table_shell = self._build_shot_table(window)
        self._build_audio_options(window)
        prompt_box = self._build_prompt_box(window)
        self._build_prompt_actions(window, prompt_box)
        self._build_white_model_cells(table_shell)
        self._build_video_actions()
        self._build_progress_and_log()
        from ui.video_prompt_results import PromptResults
        self.prompt_results=PromptResults()
        # R2942：视频工作台的「阶段配置」按钮＋模型下拉框已删，stage_button 属性只留 None 占位。
        self.closed=False;self.window.bind('<Destroy>',self.cancel_timers,add='+')
        self.refresh();self.timer=self.scheduler.after(150,self.tick)

    def _build_shot_table(self, window):
        """镜头表：表格、行高、勾选列、悬停与首帧缩略图（从 __init__ 原样切出，R1807）。"""
        table_box=ttk.Frame(window);table_box.pack(fill='x',padx=SPACING['lg'])
        table_shell=DataTable(table_box,columns=[
            ('id','镜头号',110),('title','内容',145),(ASSET_FIELD,ASSET_TITLE,145),('seconds','秒数',145),
            ('frame','首帧',145),('state','当前任务',145),('local_progress','本地进度',145),
            ('cloud_progress','线上进度',145),('review','验收',145),('versions','版本数',145),('white_model','白模 · 上传',145),
        ],show='tree headings',height=SHOT_ROWS,selectmode='browse',takefocus=True,
          style='Shot.Treeview',empty_text='暂无镜头')
        self.tree=table_shell.tree
        table_box.columnconfigure(0,weight=1);table_box.rowconfigure(0,weight=1)
        # 第 58 期第 2 条：行高按格子内容现算——「首帧」列是 54 像素的缩略图，
        # 行高就是图高加上下余地；以后图尺寸或字体变了，行高自己跟着走。
        fit_row_height(self.tree,SHOT_THUMB_SIZE,style='Shot.Treeview')
        configure_check_column(self.tree, command=self.toggle_all_edit_checks)
        self.edit_icons=self.scheduler._tick_images[:2]
        self._box=CheckboxColumn(self.tree,self.edit_icons,lambda sid:self.edit_checks.get(sid,False),lambda sid,v:self.edit_checks.__setitem__(sid,v))
        # 第 33 期第 2 条：第二栏（勾选框之后那一栏）显示的就是镜头号，列头补上「镜头号」，
        # 不再是一个没有标题的空格子。
        for k,t in [('id','镜头号'),('title','内容'),(ASSET_FIELD,ASSET_TITLE),('seconds','秒数'),('frame','首帧'),('state','当前任务'),('local_progress','本地进度'),('cloud_progress','线上进度'),('review','验收'),('versions','版本数'),('white_model','白模 · 上传')]:self.tree.heading(k,text=t)
        for k in self.tree['columns']:self.tree.column(k,width=SPACING['sm'] * 18)
        self.tree.column('id',width=SPACING['sm'] * 14);table_shell.grid(row=0,column=0,sticky='ew')
        self.tree.tag_configure('completed',background=COLORS['row_completed'],foreground=COLORS['success'])
        self.tree.bind('<<TreeviewSelect>>',lambda e:self.select())
        from contract.shot_selection import bind_shot_checks
        self.tree.is_shot_checked=lambda sid:bool(self.edit_checks.get(sid,False))
        # 第 41 期第 1 条：「选择资产」那一格点开下拉框，不跟着切换本行勾选。
        bind_shot_checks(self.tree,self.toggle_edit_check,cell_click=self.asset_cell_click)
        self.tree.bind('<Button-3>',self.shot_menu)
        # 第 53 期第 1／5 条：「选择资产」「首帧」两列加悬停高亮，「首帧」那一列再盖一层首帧
        # 缩略图。高亮那层是盖在格子上的 Label，鼠标因此落不到树上——单击与右键照原样重发给树
        # （切勾选、点开「选择资产」那一格全是树自己在管）。
        # 列号：#1 镜头号、#2 内容、#3 选择资产、#4 秒数、#5 首帧（＝那一栏的表头「首帧」）。
        # 第 57 期第 5 条：「选择资产」那一格改成弹窗（勾选与看图并进一处，见 open_asset_picker）；
        # 「首帧」那一格的缩略图改成单击看图 ＋ 停上去放大（与资产页「参考图」那一格同一套）。
        from cell_hover import CellHover,CellImages,ZOOM_SIZE
        def forward_to_tree(event):
            tree=self.tree
            tree.event_generate('<Button-%d>'%int(event.num),
                                x=event.x_root-tree.winfo_rootx(),
                                y=event.y_root-tree.winfo_rooty())
            return 'break'
        def open_shot_cell(sid,column):
            """第 57 期第 5 条：点「首帧」那一格的缩略图＝打开这张首帧（与资产页「参考图」那一格
            同一套：单击看图、右键那菜单里只剩「查看」）。「选择资产」那一格不归它管——那一下
            由 asset_cell_click 认下（见 bind_shot_checks 的 cell_click）。"""
            if column=='#5':self.safe(lambda:self.show_frame(sid))
        # 第 55 期第 2 条：#5（首帧）那一列盖着缩略图，不再走高亮——只有 #3（选择资产）
        # 那一格还是「鼠标停上来亮一下」，所以 cell_image 也用不上了。
        self.tree.cell_hover=CellHover(self.tree,('#3','#5'),open_shot_cell,
                                       hover_only=True,forward=forward_to_tree)
        def frame_image(sid,size):
            """这一镜首帧的缩略图（size 一档）：格子那一张与鼠标停上去放大那一张各解各的。"""
            try:
                shot=self.studio.shot(sid)
                if shot.get('frame_deleted'):return None
                path=self.studio.frame(shot,required=False)
                if not path.is_file():return None
                image=asset_thumbs.thumbnail(self.window,path,size)
            except (ValueError,OSError):
                return None
            return image
        def frame_thumb(sid,column):
            image=frame_image(sid,SHOT_THUMB_SIZE)
            return None if image is None else (image,'')
        def row_background(sid):
            return COLORS['row_completed'] if 'completed' in self.tree.item(sid,'tags') else COLORS['background_card']
        # 第 54 期第 3 条：refresh() 也要用它决定「这一格还写不写字」，所以挂到实例上。
        self.frame_thumb=frame_thumb
        # plain 指那份 CellHover：这一列归图这一层，别再走高亮。
        # 第 57 期第 5 条：单击不再重发给树（原来那一下就切勾选）——换成看这张首帧，与资产页
        # 「参考图」那一格一致；鼠标停上去另弹一张放大图（够看清人物与背景）。
        self.cell_images=CellImages(self.tree,('#5',),frame_thumb,background=row_background,
                                    hover=self.tree.cell_hover,plain=self.tree.cell_hover,
                                    zoom=lambda sid,column:frame_image(sid,ZOOM_SIZE))
        self.tree.cell_images=self.cell_images
        return table_shell

    def _build_audio_options(self, window):
        """本地生成才有的「生成声音 / 音轨」一栏与线上索引（从 __init__ 原样切出，R1807）。"""
        # 第 32 期第 4 条：这一行原本只有一颗「查看首帧」，与视频页标题旁那一行
        # （shared_video_controls）重复，整行删掉；省下的一行留给提示词与镜头表。
        self.toolbar=None
        self.upload_assets=tk.BooleanVar(value=True);self.generate_audio=tk.BooleanVar(value=True)
        # 第 41 期第 1 条：资产勾选一镜一份（asset_sid 是这一份属于哪一镜），下拉框、格子里的字
        # 与写回共用同一套变量。
        self.asset_choices={};self.asset_sid=None
        # 第 41 期第 1 条：原来单摆的「选择资产」表整栏并进上方的镜头内容框（见 asset_cell_text
        # 与 build_asset_menu），这里不再留控件；镜头表与「手动制作提示词」那一行就此挨在一起。
        # 第 33 期第 5 条：线上生成按秒计费、音轨不在这条链路上——这一栏只在本地生成留着。
        if isinstance(self.studio,LocalStudio):
            options=FlowBar(window);options.pack(fill='x',padx=SPACING['lg'],pady=SPACING['xs'])
            sound_item=ttk.Frame(options);sound_item.pack(side='left')
            ttk.Label(sound_item,text='生成声音 / 音轨').pack(side='left',padx=(SPACING['none'],SPACING['xs']))
            self.square_check(sound_item,self.generate_audio)
        if not isinstance(self.studio,LocalStudio):self.studio.cloud_index()

    def _build_prompt_box(self, window):
        """提示词输入框、快捷键与右键菜单（从 __init__ 原样切出，R1807）。"""
        prompt_box=ttk.Frame(window);prompt_box.pack(fill='x',padx=SPACING['lg'])
        self.prompt_box=prompt_box      # 第 58 期第 1 条：量高度要用它的位置与高度
        prompt_scroll=ttk.Scrollbar(prompt_box,orient='vertical')
        prompt_scroll.pack(side='right',fill='y')
        self.prompt=TextArea(prompt_box,bg=COLORS['background_card'],fg=COLORS['text_primary'],insertbackground=COLORS['primary'],
                            height=self.PROMPT_ROWS_MIN,wrap='word',font=FONTS['body'],
                            padx=SPACING['sm'],pady=SPACING['sm'],spacing1=SPACING['xs'],spacing3=SPACING['xs'],
                            undo=True,autoseparators=True,maxundo=100,
                            yscrollcommand=prompt_scroll.set)
        self.prompt.pack(side='left',fill='both',expand=True)
        prompt_scroll.configure(command=self.prompt.yview)
        self.shortcuts.bind(self.prompt, ('<Control-a>', '<Control-A>'),
                            lambda event:(self.prompt.tag_add('sel','1.0','end-1c'),'break')[1],
                            scope='视频生成·提示词', name='全选提示词')
        # 第 48 期第 4 条：提示词框不再写死 7 行，跟着内容多少自己长高或变矮。
        self.prompt_width=None
        self.prompt.bind('<<Modified>>',self.prompt_edited)
        self.prompt.bind('<Configure>',self.prompt_resized,add='+')
        # 第 58 期第 1 条：窗口一变大小，提示词框与日志框的高度就重算一遍（提示词优先）。
        self.window.bind('<Configure>',self.fit_page_heights,add='+')
        prompt_menu=ContextMenu(self.prompt)
        for title,command in [('剪切',lambda:self.prompt.event_generate('<<Cut>>')),
                              ('复制',lambda:self.prompt.event_generate('<<Copy>>')),
                              ('粘贴',lambda:self.prompt.event_generate('<<Paste>>')),
                              ('全选',lambda:self.prompt.tag_add('sel','1.0','end-1c'))]:
            prompt_menu.command(title,command)
        self.prompt.bind('<Button-3>',prompt_menu.popup)
        return prompt_box

    def _build_prompt_actions(self, window, prompt_box):
        """提示词那一行的动作按钮与阶段配置按钮（从 __init__ 原样切出，R1807）。"""
        # 第 35 期第 5 条：这行按钮的上下外边距一起收到 2／4，紧贴下面的提示词内容框。
        prompt_actions=FlowBar(window);prompt_actions.pack(fill='x',padx=SPACING['lg'],pady=(SPACING['xs'],SPACING['xs']),before=prompt_box)
        # 第 29 期第 4 条：原来这里还有一颗「设置model+skill」和一份贴在同行的 Model＋SKILL
        # 控制面板，与「阶段配置」面板重复——一并删掉，本页的编排模型与 SKILL 到那里挑（面板在「剧本准备」页）。
        # 第 32 期第 4 条：主动作改名「手动制作提示词」并用主色按钮突出，其余是辅助动作。
        # 本地生成与线上生成共用这一份工作台，改一处两边都生效。
        # 第 45 期：「MCP 优化」也要醒目——它是要花钱的那一步，样式表里给它留了一档琥珀色。
        # R2942：两行「阶段配置」按钮＋模型下拉框删除，stage_button／prompt_stage_button 只留 None 占位。
        self.stage_button=None;self.prompt_stage_button=None
        for label,action in [('手动制作提示词',self.start_prompt_skill),('MCP 优化',self.make_prompt),('MCP 设置',lambda:ui_plugin_registry.module('agent.prompt_optimizer').settings(self)),('保存提示词',self.save_prompt),('导入提示词',self.import_prompt),('当前提示词目录',self.open_prompt_folder)]:
            # MCP 优化会产生额外调用成本；保留既有警示层级，其余动作统一走 token 组件。
            if label=='MCP 优化':
                btn=PrimaryButton(prompt_actions,text=label,style='Highlight.TButton',
                               command=lambda f=action:self.safe(f))
            else:
                button_type=PrimaryButton if label=='手动制作提示词' else SecondaryButton
                btn=button_type(prompt_actions,text=label,width=16 if label=='手动制作提示词' else 0,
                                command=lambda f=action:self.safe(f))
            btn.pack(side='left',padx=(SPACING['none'],SPACING['xs']),pady=SPACING['xs'])
            if label!='当前提示词目录':self.prompt_buttons.append(btn)
            # R2942：「阶段配置」按钮＋模型下拉框删除（模型/技能走共享输入框）。

    def _build_white_model_cells(self, table_shell):
        """白模勾选格与镜头表滚动联动（从 __init__ 原样切出，R1807）。"""
        self.white_model_status=tk.StringVar(value='白模：未关联')
        self.white_cells={};self.white_ready={}
        self.tree.bind('<Configure>',lambda e:self.layout_white_cells(),add='+')
        # 第 55 期第 1 条：首帧缩略图那一层的重排已经收进它自己（watch_view），这里只管
        # 白模勾选框那一层（它归这一页自己摆）。
        def scroll_white(first,last):
            table_shell.vertical_scrollbar.set(first,last);self.tree.after_idle(self.layout_white_cells)
        def horizontal_white(first,last):
            table_shell.horizontal_scrollbar.set(first,last);self.tree.after_idle(self.layout_white_cells)
        self.tree.configure(yscrollcommand=scroll_white,xscrollcommand=horizontal_white)

    def _build_video_actions(self):
        """页脚的两行主动作按钮与验收备注（从 __init__ 原样切出，R1807）。"""
        actions=ttk.Frame(self.footer);actions.pack(fill='x',padx=SPACING['sm'],pady=SPACING['xs'])
        actions.columnconfigure(0,weight=1)
        # 第 35 期第 5 条：验收那一栏原来占着右边的整列（请求宽 575），主动作那一行只剩 208 像素，
        # 按钮挤成一列一列的（实测 12 颗按钮摊了 311 像素高）。现在验收单独占一行、仍靠右，
        # 主动作这一行拿走整幅宽度——按钮排成两行，底下的进度与日志才露得出来。
        # 第 39 期第 2 条：这一块重排成两行 —— 第一行是主动作与常用动作，第二行从「通过」起头
        # （落在「手动制作视频」正下面）；两颗自动勾选框并到右边一列，自动提交压在自动验收上面。
        controls=FlowBar(actions);controls.grid(row=0,column=0,sticky='ew')
        secondary=FlowBar(actions);secondary.grid(row=1,column=0,sticky='ew',pady=(SPACING['xs'],SPACING['none']))
        self.generate_button=None;self.generate_checked_button=None;self.play_button=None
        self.auto_submit=tk.BooleanVar(value=False)
        def add(bar,title,fn,primary=False):
            """按想要的次序建按钮：FlowBar 是按建控件的先后排的（不是 pack 顺序）。

            第 39 期第 2 条起分成两条 FlowBar：第一行「手动制作视频」→「播放视频」→
            其余常用动作（R2942：原「阶段配置」按钮已删）；第二行「通过」→ 目录与任务 →
            「需修改」→「批量生成勾选镜头」→ 验收备注。
            """
            button=(PrimaryButton if primary else SecondaryButton)(bar,text=title,
                              width=16 if primary else 0,
                              command=lambda f=fn:self.safe(f))
            button.pack(side='left',padx=(SPACING['none'],SPACING['xs']),pady=SPACING['xs'])
            if primary:
                self.generate_button=button
                # 第 32 期第 4／6 条、第 54 期附件二第 3 条：主动作叫「手动制作视频」并突出。
                # R2942：主动作右边不再挂「阶段配置」按钮。
            return button
        # 第 54 期附件二第 3 条：这一页的主动作改名「手动制作视频」（阶段简称＝视频），
        # 并按三虎的跑没跑刷字与置灰。
        _video_button=add(controls,'手动制作视频',
                          self.manual_command_factory(self,'video',self.generate,self.window),True)
        ui_plugin_registry.module('stage_flow').follow(_video_button,'video')
        # R2942：「阶段配置」按钮＋模型下拉框删除（模型/技能走共享输入框）。
        self.play_button=add(controls,'播放视频',self.play)
        add(controls,'查看全部版本',self.versions)
        # 第 35 期第 5 条：线上的「API 设置」与「阶段配置 → 接口 → 线上视频 API」是同一扇窗
        # （desktop 传进来的 settings_callback 就是它），重复的那颗删掉；本地的「本地设置」是
        # ComfyUI 视频设置，留着。
        if isinstance(self.studio,LocalStudio):
            add(controls,'本地设置',self.settings)
        # 第 39 期第 2 条：第二行的次序（用户指定）——「通过」落在主动作正下面，接着是目录与任务，
        # 「需修改」后面是「批量生成勾选镜头」与验收备注；「批量通过勾选」与「自动剪辑勾选镜头」删掉。
        add(secondary,'通过',lambda:self.review('pass'))
        add(secondary,'打开素材目录',lambda:open_path(self.studio.episode_dir))
        add(secondary,'恢复任务编号',self.attach)
        add(secondary,'打开视频目录',self.versions)
        add(secondary,'需修改',lambda:self.review('revise'))
        self.generate_checked_button=add(secondary,'批量生成勾选镜头',self.generate_checked)
        # 第 46 期第 9 条：批量删除与它成对——都只认勾选行，逐个删除走内容框的右键菜单。
        self.delete_checked_button=add(secondary,'删除勾选镜头',self.delete_checked_shots)
        ttk.Label(secondary,text='验收备注：').pack(side='left',padx=(SPACING['sm'],SPACING['xs']))
        self.note=LineInput(secondary,width=CHAR_WIDTH['2xl']);self.note.pack(side='left')
        # 第 39 期第 2 条：验收那一组并进第二行（通过／需修改／验收备注），这一列只剩「自动验收」——
        # 它排在「自动提交」下面（自动提交先建、先 pack）。
        self.auto_review=tk.BooleanVar(value=False)
        self.progress_text=QuietVar(value='请选择镜头')

    def _build_progress_and_log(self):
        """页脚的进度行、忙碌状态与动态日志（从 __init__ 原样切出，R1807）。"""
        # 第 39 期第 2 条：「打开剪辑成片目录」单占一行，摆在「SH0XX」那句状态的正上方（用户指的位置）。
        clip_line=ttk.Frame(self.footer);clip_line.pack(fill='x',padx=SPACING['sm'],pady=(SPACING['xs'],SPACING['none']))
        SecondaryButton(clip_line,text='打开剪辑成片目录',command=lambda:self.safe(self.open_assembled)).pack(side='left')
        # 第 35 期第 5 条：两行进度文字并成一行——「SH0XX…」在左，「本地：…／线上：…」右对齐。
        progress_line=ttk.Frame(self.footer);progress_line.pack(fill='x',padx=SPACING['sm'],pady=(SPACING['xs'],SPACING['none']))
        ttk.Label(progress_line,textvariable=self.shared_progress,style='Muted.TLabel',anchor='e').pack(side='right')
        progress_label=ttk.Label(progress_line,textvariable=self.progress_text,wraplength=WRAPLENGTH['lg'],justify='left');progress_label.pack(side='left',fill='x',expand=True)
        self.busy_state=BusyState(self.progress_text,spinner=Spinner(progress_line,host=progress_label))  # 忙碌时进度文字右端转圈，不用进度条
        log_box=tk.Frame(self.footer,bg=COLORS['background_card'],highlightthickness=1,highlightbackground=COLORS['border_default'])
        log_box.pack(fill='x',padx=SPACING['sm'],pady=SPACING['xs']);self.log_box=log_box
        log_actions=tk.Frame(log_box,bg=COLORS['background_card']);log_actions.pack(fill='x')
        self.log_header=log_actions
        tk.Label(log_actions,text='动态日志',bg=COLORS['background_card'],fg=COLORS['text_secondary'],font=FONTS['caption']).pack(side='left',padx=SPACING['xs'])
        SecondaryButton(log_actions,text='清空日志',command=self.clear_log,
                        cursor='hand2').pack(side='right',padx=SPACING['xs'])
        log_body=tk.Frame(log_box,bg=COLORS['background_card']);log_body.pack(fill='both',expand=True)
        log_scroll=ttk.Scrollbar(log_body,orient='vertical');log_scroll.pack(side='right',fill='y')
        self.log=TextArea(log_body,bg=COLORS['background_card'],fg=COLORS['text_secondary'],height=self.LOG_ROWS_MIN,state='disabled',wrap='word',
                         borderwidth=0,highlightthickness=0,padx=SPACING['sm'],pady=SPACING['xs'],yscrollcommand=log_scroll.set)
        self.log.pack(side='left',fill='both',expand=True);log_scroll.configure(command=self.log.yview)

    def update_prompt_controls(self,periodic=False):
        selected=self.tree.selection()
        locked=bool(selected) and prompt_locked(self,selected[0])
        optimizing=getattr(self,'optimizer_busy',False)
        busy = getattr(self, 'busy', False)
        checked_any = any(self.edit_checks.get(sid, False) for sid in self.tree.get_children())
        ready = play_ready(self, selected)
        signature=(tuple(selected),locked,optimizing,busy,checked_any,ready,len(self.window.winfo_children()))
        if periodic and signature==getattr(self,'_prompt_controls_signature',None):return
        self._prompt_controls_signature=signature
        for button in self.prompt_buttons:button.state(['disabled'] if locked or optimizing else ['!disabled'])
        if hasattr(self,'agent_selector'):self.agent_selector.state(['disabled'] if locked or optimizing else ['!disabled'])
        self.prompt.configure(state='disabled' if locked or optimizing else 'normal')
        def options(widget):
            for child in widget.winfo_children():
                if isinstance(child,ttk.Checkbutton):child.state(['disabled'] if locked or optimizing else ['!disabled'])
                options(child)
        for widget in self.window.winfo_children():
            if isinstance(widget,FlowBar) and widget is not self.toolbar:options(widget)
        def action_state(button, enabled):
            if button is not None:
                button.state(['!disabled'] if enabled else ['disabled'])
        action_state(self.generate_button, bool(selected) and not busy and not optimizing)
        # 第 47 期第 1 条：批量那两颗按钮的可用状态跟 generate_checked／delete_checked_shots
        # 用同一个口径（勾选优先、高亮兜底），不然会出现「按钮是灰的但其实点了也能做」的错配。
        work_ready = bool(checked_any or self.tree.selection())
        action_state(self.generate_checked_button, work_ready and not busy and not optimizing)
        action_state(getattr(self, 'delete_checked_button', None), work_ready and not busy)
        action_state(self.play_button, ready and not busy)

    # 第 48 期第 4 条：「手动提示词」下面那块提示词框按内容多少自适应高度。
    # 一两行字就矮一点，省下页面空间；写得长了自己长高，超过上限才用滚动条。
    # 第 58 期第 1 条：上限不再写死 12 行——提示词框优先显示全部文字，能够多高按这一页
    # 剩下多少地方现算（PROMPT_ROWS_MAX 只作兜底）；最下面那块动态日志让路——先压日志，
    # 日志压到 LOG_ROWS_MIN 行还装不下，提示词才用滚动条。
    PROMPT_ROWS_MIN = 3
    PROMPT_ROWS_MAX = 40
    PROMPT_WIDTH_FALLBACK = 620
    LOG_ROWS_MIN = 3
    LOG_ROWS_MAX = 10

    def prompt_chars_per_row(self):
        """估一行能放几个字：按框的像素宽和字体里的汉字宽度算。"""
        from tkinter import font as tkfont
        try:
            width = self.prompt.winfo_width()
        except tk.TclError:
            width = 0
        try:
            wide = tkfont.Font(root=self.prompt, font=self.prompt.cget('font')).measure('中')
        except Exception:
            wide = 16
        wide = max(6, wide)
        usable = (width if width > 1 else self.PROMPT_WIDTH_FALLBACK) - 24   # 去掉 padx 8*2 和边框
        return max(8, int(usable // wide))

    def prompt_rows(self, text=None):
        """数出这段提示词要占几行：换行照数，长行按一行能放几个字折算。"""
        if text is None:
            text = self.prompt.get('1.0', 'end-1c')
        per_row = self.prompt_chars_per_row()
        rows = 0
        for line in text.split('\n'):
            rows += max(1, -(-len(line) // per_row))
        return max(1, rows)

    def fit_prompt_height(self):
        """提示词框按内容长高（第 58 期第 1 条：优先把全部文字显示出来）。

        这一页本来就摆在一张可滚动的画布上：提示词长了页面跟着长，用户滚一下就能看全，
        不再把它卡在几行高里、让用户在框子里面自己滚。PROMPT_ROWS_MAX 只是兜底上限。
        """
        rows = max(self.PROMPT_ROWS_MIN, min(self.prompt_rows(), self.PROMPT_ROWS_MAX))
        self._set_text_rows(self.prompt, rows)

    def text_row_px(self, widget):
        """这个文字框一行大概多少像素：拿请求高度除以行数现算（行距已经算在里面）。"""
        try:
            rows = max(1, int(widget.cget('height')))
            return max(10, int(widget.winfo_reqheight()) // rows)
        except Exception:
            return 20

    def _set_text_rows(self, widget, rows):
        try:
            if int(widget.cget('height')) != rows:
                widget.configure(height=rows)
        except tk.TclError:
            pass

    def page_viewport_height(self):
        """这一页看得见的高度：页面摆在一张可滚动的画布上，取画布视口的高度。"""
        widget = self.window
        for _ in range(4):
            widget = getattr(widget, 'master', None)
            if widget is None:
                break
            try:
                if widget.winfo_class() == 'Canvas':
                    return widget.winfo_height()
            except tk.TclError:
                break
        try:
            return self.window.winfo_toplevel().winfo_height()
        except tk.TclError:
            return 0

    def log_lines(self):
        """日志现在有几行（按显示行数算，宽窄变化也算得对）。"""
        try:
            return max(1, int(self.log.count('1.0', 'end-1c', 'displaylines')[0]))
        except Exception:
            try:
                return max(1, int(self.log.index('end-1c').split('.')[0]))
            except tk.TclError:
                return 1

    def fit_log_height(self):
        """动态日志跟着内容长高，但最多 LOG_ROWS_MAX 行；提示词框先占够，剩下的才归它。"""
        wanted = max(self.LOG_ROWS_MIN, min(self.log_lines(), self.LOG_ROWS_MAX))
        rows = min(wanted, self.LOG_ROWS_MIN + self.log_room_rows())
        self._set_text_rows(self.log, max(self.LOG_ROWS_MIN, rows))

    def log_room_rows(self):
        """动态日志还能长几行（第 58 期第 1 条：提示词框先占够，视口里剩下的才归它）。

        量的是「提示词框底边到可见区底边还剩多少」减去页脚里不属于日志的那一堆
        （按请求高度算，不受眼下护拥护挤的影响）。地方不够就只给最小那几行。
        """
        per_row = self.text_row_px(self.log)
        try:
            self.window.update_idletasks()      # 提示词框刚改过高度，先把尺寸算到最新
            toplevel = self.window.winfo_toplevel()
            viewport = self.page_viewport_height()
            below = self.prompt_box.winfo_rooty() + self.prompt_box.winfo_height() - toplevel.winfo_rooty()
            used = self.footer.winfo_reqheight() - self.log_box.winfo_reqheight()
        except (tk.TclError, AttributeError):
            return self.LOG_ROWS_MAX
        if viewport <= 0 or below <= 0:
            return 0
        return max(0, (viewport - below - used - 6) // per_row)

    def fit_page_heights(self, event=None):
        """第 58 期第 1 条：这一页两块文字框的高度一起算——提示词优先，日志让路。

        窗口太矮时先压日志（可压到 LOG_ROWS_MIN 行），提示词实在装不下才用滚动条。
        event 是 <Configure> 那一份：只有这一页自己变了才重算（子控件的 Configure 不算）。
        拖动主窗口边框期间并进松手后的整页重排，不逐帧量文字框。
        """
        if event is not None and getattr(event, 'widget', None) is not self.window:
            return
        coalescer = getattr(self, 'resize_scheduler', None)
        if coalescer is not None and coalescer.schedule(self.fit_page_heights, event=event):
            return
        if getattr(self, '_fitting_heights', False):
            return
        self._fitting_heights = True
        try:
            # 量之前先把日志让到最小：第 58 期第 1 条里它的地位就在提示词框下面。
            self._set_text_rows(self.log, self.LOG_ROWS_MIN)
            self.window.update_idletasks()
            self.fit_prompt_height()
            self.fit_log_height()
        finally:
            self._fitting_heights = False

    def prompt_edited(self, event=None):
        """<<Modified>> 是 Tk 的老规矩：读完标志要立刻复位，不然只会响一次。"""
        if not self.prompt.edit_modified():
            return
        self.prompt.edit_modified(False)
        self.fit_page_heights()

    def prompt_resized(self, event=None):
        """只有宽度变了才重算：高度变化会再发一次 <Configure>，不挡一下会自己叫自己。"""
        width = self.prompt.winfo_width()
        if getattr(self, 'prompt_width', None) == width:
            return
        self.prompt_width = width
        self.fit_page_heights()

    def clear_log(self):
        # Display-only action, available even while a generation task is running.
        self.log.configure(state='normal');self.log.delete('1.0','end');self.log.configure(state='disabled')
        self.fit_log_height()       # 第 58 期第 1 条：清空以后框子跟着矮回去

    def safe(self,fn):
        try:
            if self.busy: raise ValueError('正在执行操作，请稍后')
            fn()
        except Exception as e:import contract.error_codes as error_codes;self.notifier.error(error_codes.user_text(e), title='提示')
    def white_model_path(self,sid):
        """这一镜的白模视频（第 54 期第 3 条：「白模 · 上传」那一列右键查看的就是它）。"""
        from ui.white_model import shot_directory,project_for_app,read_record
        try:
            value=read_record(shot_directory(project_for_app(self),sid)).get('preview')
            path=Path(value) if value else None
        except (OSError,ValueError):return None
        if path and path.is_file() and path.stat().st_size and path.suffix.lower() in ('.mp4','.mov','.webm'):
            return path
        return None
    def white_model_ready(self,sid):
        return self.white_model_path(sid) is not None
    def refresh_white_model(self):
        # Re-scan files without changing the selected shot or prompt editor.
        for sid in self.tree.get_children():
            ready=self.white_model_ready(sid);self.white_ready[sid]=ready
            self.tree.set(sid,'white_model','已就绪' if ready else '待制作')
        self.layout_white_cells()
    def set_white_upload(self,sid,var):
        self.tree.focus(sid)
        if self.tree.selection()!=(sid,):self.tree.selection_set(sid)
        previous=bool(self.studio.shot(sid).get('upload_white_model',False))
        try:
            if self.busy:raise ValueError('当前正在提交，请完成后再修改白模选项')
            assert_prompt_editable(self,sid)
            if var.get() and not self.white_model_ready(sid):raise ValueError('白模待制作，请先到'+pet_bus.stage_step('previs')+'生成白模视频，再刷新白模')
            from stage_execution_service import save_stage_white_model_upload
            with self.studio.lock():
                self.studio.episode=save_stage_white_model_upload(self.studio.episode_path,sid,var.get())
        except Exception as exc:
            var.set(previous);self.notifier.error(str(exc), title='白模上传')
    def layout_white_cells(self):
        if not hasattr(self,'white_cells') or not self.tree.winfo_exists():return
        ids=set(self.tree.get_children())
        for sid in list(self.white_cells):
            if sid not in ids:self.white_cells.pop(sid)[0].destroy()
        for sid in ids:
            bbox=self.tree.bbox(sid,'white_model')
            if not bbox or bbox[0]<0 or bbox[0]+bbox[2]>self.tree.winfo_width():
                if sid in self.white_cells:self.white_cells[sid][0].place_forget()
                continue
            if sid not in self.white_cells:
                var=tk.BooleanVar(value=bool(self.studio.shot(sid).get('upload_white_model',False)))
                check=ttk.Checkbutton(self.tree,variable=var,command=lambda s=sid,v=var:self.set_white_upload(s,v))
                self.white_cells[sid]=(check,var)
            check,var=self.white_cells[sid]
            var.set(bool(self.studio.shot(sid).get('upload_white_model',False)))
            check.configure(text='已就绪' if self.white_ready.get(sid) else '待制作')
            check.state(['!disabled'] if self.white_ready.get(sid) or var.get() else ['disabled'])
            x,y,w,h=bbox;check.place(x=x+2,y=y+1,width=w-4,height=h-2)
    def writing_setup(self):
        from domain.writing import STAGES
        from stage_execution_service import prepare_writing_project
        win=BaseDialog(self.window,'剧本准备 · 五阶段编剧技能',geometry='780x540',modal=False,chrome=False);win.attributes('-alpha',0)
        ttk.Label(win,text='填写创意或粘贴已有剧本：').pack(anchor='w',padx=SPACING['md'],pady=SPACING['xs'])
        brief=TextArea(win,height=TEXT_ROWS['3xl'],wrap='word');brief.pack(fill='both',expand=True,padx=SPACING['md'])
        # 第 45 期：这一栏里的示例以前是正常黑字，看着像用户自己写的，一按「生成编剧任务书」才发现
        # 交上去的是软件自带的那几句话。现在示例默认置灰（只是提示）：一动键盘整段让位，
        # 空着再离开焦点就把灰色的示例放回来；真拿着示例去生成会被拦下并说清。
        example='日常搞笑动画。固定机位、简单动作、复用已有角色和场景。\n本次希望制作的故事：'
        def show_example():
            brief.delete('1.0','end');brief.insert('1.0',example)
            brief.tag_add('example','1.0','end-1c');brief.configure(fg=PLACEHOLDER_INK)
        def example_showing():
            return brief.get('1.0','end-1c')==example
        def clear_example(event=None):
            if not example_showing():return
            brief.delete('1.0','end');brief.configure(fg=COLORS['text_primary'])
        def brief_key(event):
            printable=bool(event.char and event.char.isprintable() and not (event.state & 0xC))
            paste=(event.state & 0x4) and event.keysym.lower()=='v'
            if printable or paste or event.keysym in ('Return','KP_Enter'):clear_example()
        def brief_blur(event=None):
            if not brief.get('1.0','end-1c').strip():show_example()
        brief.tag_configure('example',foreground=PLACEHOLDER_INK)
        brief.bind('<KeyPress>',brief_key,add='+');brief.bind('<<Paste>>',clear_example,add='+')
        brief.bind('<FocusOut>',brief_blur,add='+')
        show_example()
        row=ttk.Frame(win);row.pack(fill='x',padx=SPACING['md'],pady=SPACING['sm'])
        stage=SelectBox(row,values=STAGES);stage.current(0);stage.pack(side='left')
        ttk.Label(row,text='目标秒数：').pack(side='left',padx=SPACING['sm']);duration=LineInput(row,width=CHAR_WIDTH['md']);duration.insert(0,'40');duration.pack(side='left')
        def generate():
            try:
                if self.busy:raise ValueError('请等待当前操作完成')
                text=brief.get('1.0','end')
                if not text.strip():raise ValueError('请先填写创意或剧本需求')
                if example_showing():raise ValueError('灰色的只是软件示例，请先改成您自己的创意')
                folder=prepare_writing_project(self.root,text,stage.get(),duration.get())
                self.write('编剧任务书已生成：'+str(folder));open_path(folder)
                self.notifier.success('任务书、技能说明、资产表和JSON模板已保存。\n交给 Codex 执行即可，本按钮不调用模型。', title='已准备', modal=True)
            except Exception as e:self.notifier.error(str(e), title='无法准备')
        PrimaryButton(win,text='生成编剧任务书（离线）',command=generate).pack(pady=SPACING['md'])
    def import_json(self):
        from domain.writing import validate_episode
        from agent.core import read
        from stage_execution_service import import_writing_project
        file=FileDialog(self.window).open_file(title='选择编剧输出的镜头JSON',filetypes=[('镜头JSON','*.json')])
        if not file:return
        source=Path(file);af=source.parent/'assets.json'
        assets=read(af) if af.exists() else read(self.studio.episode_dir/'assets.json')
        report=validate_episode(read(source),media_root(source),assets)
        details=f"校验通过：{report['shot_count']}镜，共{report['total_seconds']}秒。\n"+'\n'.join(report['warnings'])
        details+='\n将建立独立项目，预算0秒、默认离线，不覆盖当前任务。'
        if ask_confirmation(self.window, '导入预览', details+'\n创建新项目？'):
            folder,report=import_writing_project(self.root,file);open_path(folder)
            self.write('新项目已创建：'+str(folder))
            self.notifier.success('新项目已加入漫剧助手，在“我的项目”中选择即可。\n缺失首帧可在首帧管理补齐。', title='导入完成', modal=True)
    def sid(self):
        """当前这一镜（第 47 期第 1 条）：高亮优先；没高亮就用第一个勾选行。

        与「制作／删除」的 work_targets 正好相反——查看、编辑提示词这类动作看的是
        「我正在看的那一行」，勾选只是兜底。
        """
        from responsive_ui import view_row
        sid=view_row(self.tree,lambda shot_id: self.edit_checks.get(shot_id,False))
        if not sid:raise ValueError('请先选择镜头')
        return sid


    def show_frame(self,sid):
        """查看：打开这一镜的首帧图片（第 46 期第 1 条，目标就是右键那一行）。"""
        from agent.core import read
        episode=read(self.studio.episode_path)
        shot=next((s for s in episode['shots'] if s['id']==sid),None)
        if shot is None:raise ValueError('此镜头已从分镜中移除，请刷新列表：'+sid)
        path=self.studio.frame(shot,required=False)
        if shot.get('frame_deleted') or not path.is_file():raise ValueError(sid+' 还没有首帧图片，请先到'+pet_bus.stage_step('keyframe')+'制作')
        open_path(path)
    def video_column(self,name):
        """这一列的表头编号（第 54 期第 3 条：右键要按格子认列，不能写死）。"""
        return '#'+str(list(self.tree['columns']).index(name)+1)
    def cell_actions(self,sid,column):
        """这一格右键能干什么（第 54 期第 3 条）：(查看名, 查看, 删除名, 删除)。

        每列只认本栏自己的那个文件：「选择资产」列开资产图片、「首帧」列开（或删）首帧图片、
        「本地／线上进度」两列只开本页这一侧那一版视频、「白模 · 上传」列开白模视频。纯文字列
        （镜头号／内容／秒数／当前任务／验收／版本数）四项全空，菜单根本不弹。
        """
        empty=(None,None,None,None)
        try:
            if column==self.asset_column():
                # 第 57 期第 5 条：「选择资产」那一格的左键勾选与右键查看已经并进同一扇窗
                # （单击这一格打开，见 open_asset_picker），这一列不再单弹菜单。
                return empty
            if column=='#5':
                # 第 57 期第 5 条：「删除首帧」从这一列撤掉——删首帧统一到 08 首帧管理那一页
                # （那里删的是同一张图，入口留一处），这一列只留「查看首帧图片」。
                shot=self.studio.shot(sid)
                path=self.studio.frame(shot,required=False)
                if shot.get('frame_deleted') or not path.is_file():return empty
                return ('查看首帧图片',lambda:open_path(path),None,None)
            if column in (self.video_column('local_progress'),self.video_column('cloud_progress')):
                side='本地' if isinstance(self.studio,LocalStudio) else '线上'
                if column!=self.video_column('local_progress' if side=='本地' else 'cloud_progress'):
                    return empty                     # 这一列讲的是另一侧，本页没有它的文件
                files=[v for v in self.studio.state()['shots'].get(sid,[]) if v.get('file')]
                if not files:return empty
                path=self.root/files[-1]['file']
                delete=(lambda:self.delete_video_shot(sid)) if side=='本地' else None
                return ('查看'+side+'视频',lambda:open_path(path),
                        '删除此镜头（本地视频）' if delete else None,delete)
            if column==self.video_column('white_model'):
                path=self.white_model_path(sid)
                if path is None:return empty
                return ('查看白模视频',lambda:open_path(path),None,None)
        except (ValueError,KeyError,OSError,tk.TclError):return empty
        return empty
    def shot_menu(self,event):
        """内容框右键（第 46 期第 1／9 条 ＋ 第 54 期第 3 条）：只有鼠标底下这一格真有能打开的
        文件才弹，菜单里只摆这一列自己的那个文件。

        原来在哪儿右键都弹同一组「查看首帧图片／查看视频文件／删除此镜头」——纯文字格上也弹、
        而且「查看」不看你点的是哪一格。路径工具的右键规矩不再回退到「随便弹一个」。
        """
        if self.busy:return
        if self.tree.identify_region(event.x,event.y) not in ('cell','tree'):return
        sid=self.tree.identify_row(event.y)
        if not sid:return
        view_label,view,delete_label,delete=self.cell_actions(sid,self.tree.identify_column(event.x))
        if view is None and delete is None:return
        self.tree.selection_set(sid);self.tree.focus(sid);self.select()
        # 保持该页可替换的菜单工厂，供无窗口的动作逻辑测试注入替身。
        menu=ContextMenu(self.window, menu_factory=tk.Menu)
        if view is not None:menu.command(view_label,lambda:self.safe(view))
        if delete is not None:menu.command(delete_label,lambda:self.safe(delete))
        return menu.popup(event)
    def delete_video_shot(self,sid=None,ask=True,rebuild=True):
        """逐个删除：目标就是传进来的那一镜（右键那一行）；ask／rebuild 给批量删除复用。"""
        sid=sid or self.sid()
        if ask and not ask_confirmation(self.window, '删除本地视频镜头', sid+' 将从本地视频列表及自动剪辑中移除。\n首帧、历史视频和任务记录保留。是否删除？', dangerous=True):return False
        with self.studio.lock():
            versions=self.studio.state()['shots'].get(sid,[])
            from stage_execution_service import mark_stage_video_deleted
            self.studio.episode=mark_stage_video_deleted(self.studio.episode_path,sid,versions)
        if rebuild:
            self.refresh();self.prompt.delete('1.0','end');self.note.delete(0,'end');self.fit_prompt_height()
            self.write(sid+' 已从本地视频制作中删除，历史素材保留。')
        return True
    def delete_checked_shots(self):
        """批量删除（第 46 期第 9 条 ＋ 第 47 期第 1 条）：勾选的那几镜；一个都没勾就按高亮那一行算。

        高亮一行却没勾上时不再回一句「请先勾选」——那一行就是用户在看的镜头，提示里写明按它算。
        """
        if self.busy:raise ValueError('请等待当前任务结束后再删除镜头')
        ids,how=work_targets(self)
        if not ids:raise ValueError('请先在镜头内容框里勾选要删除的镜头')
        if not ask_confirmation(self.window, '批量删除本地视频镜头',
                '以下 %d 个镜头将从本地视频列表及自动剪辑中移除：\n%s\n\n首帧、历史视频和任务记录保留。是否删除？'
                % (len(ids),'、'.join(ids)), dangerous=True):return
        if how=='shown':self.write('没有勾选行：按高亮的那一行 %s 删除。'%ids[0])
        done=[];blocked=[]
        for sid in ids:
            try:self.delete_video_shot(sid,ask=False,rebuild=False)
            except ValueError as exc:blocked.append(sid+'：'+str(exc))
            else:done.append(sid)
        if done:
            self.refresh();self.prompt.delete('1.0','end');self.note.delete(0,'end');self.fit_prompt_height()
            self.write('已从本地视频制作中删除：'+'、'.join(done)+'（历史素材保留）。')
        for item in blocked:self.write('未删除 '+item)
    def refresh(self):
        selected=self.tree.selection();self.tree.delete(*self.tree.get_children());st=self.studio.state()
        for s in self.studio.episode['shots']:
            if s.get('video_deleted'):continue
            vs=st['shots'][s['id']];v=vs[-1] if vs else {}
            ready=self.studio.frame(s,required=False).is_file() and not s.get('frame_deleted')
            state_label=LABELS.get(v.get('state'),'未提交')
            if v.get('state')=='downloaded' and (not v.get('file') or not (self.root/v['file']).is_file()):state_label='视频文件缺失'
            # 第 54 期第 3 条：「首帧」那一格盖得上缩略图就只留图——那句「图与字叠着多余」的活
            # 第 55 期第 3 条起由盖图那一层自己做（盖上收走、撤掉写回）；这里照旧写「已就绪」／
            # 「请回05准备」——原来为了判这一点逐镜解一遍首帧，白解。
            frame_text='已就绪' if ready else '请回05准备'
            self.tree.insert('',tk.END,iid=s['id'],text='',image=self.edit_icons[int(self.edit_checks.setdefault(s['id'],False))],values=(s['id'],s['title'],self.asset_cell_text(s['id']),s['duration'],frame_text,state_label,'未开始','未开始',review_label(v),len(vs),'已就绪' if self.white_model_ready(s['id']) else '待制作'),tags=('completed',) if v.get('state')=='downloaded' else ())
        self.refresh_shared_progress()
        self.fit_shot_columns()
        self.shot_thumbs_refresh()          # 第 53 期第 5 条：行重建之后缩略图跟着重排
        self.refresh_white_model()
        self.update_header_check()
        self.status.set(f"{'联网已开启' if self.studio.cfg['live_enabled'] else '离线模式'}  |  制作可用 {self.studio.remaining()} 秒  |  已占用 {self.studio.used()} 秒（含不确定任务）  |  备用 {self.studio.cfg['reserve_seconds']} 秒")
        if isinstance(self.studio,LocalStudio):self.status.set('本地生成 · 不消耗云端额度')
        if selected and self.tree.exists(selected[0]):self.tree.selection_set(selected[0])
        elif self.tree.get_children():
            ready_ids=[s['id'] for s in self.studio.episode['shots'] if self.tree.exists(s['id']) and self.studio.frame(s,required=False).is_file() and not s.get('frame_deleted')]
            self.tree.selection_set(ready_ids[0] if ready_ids else self.tree.get_children()[0])
    def shot_thumbs_refresh(self):
        """第 53 期第 5 条：行一滚动／列宽一变／重建行，首帧缩略图那一层跟着重排。"""
        images=getattr(self,'cell_images',None)
        if images is not None and self.tree.winfo_exists():images.refresh()
    def refresh_shared_progress(self):
        project=project_root(self.root)
        local,cloud=shared_video_snapshot(project,self.studio.episode_path)
        now=time.time()
        for sid in self.tree.get_children():
            for column,rows in (('local_progress',local),('cloud_progress',cloud)):
                text=progress_display(rows.get(sid),now)
                if self.tree.set(sid,column)!=text:self.tree.set(sid,column,text)
        # 第 38 期第 1 条：本地工作台只报本地进度，线上工作台只报线上进度。
        self.shared_progress.set(progress_summary(local,cloud,'local' if isinstance(self.studio,LocalStudio) else 'cloud'))

    def update_header_check(self):
        self._box.refresh_header()
    def toggle_all_edit_checks(self):
        self._box.toggle_all()
    def toggle_edit_check(self,sid):
        self._box.toggle(sid)
    def select(self):
        try:
            s=self.studio.shot(self.sid())
            self.flush_prompt(s['id'])
            self.refresh_white_model()
            if self.editing_sid!=s['id']:
                self.prompt.configure(state='normal')
                self.prompt.delete('1.0','end');self.prompt.insert('1.0',s['video_prompt']);self.editing_sid=s['id'];self.fit_prompt_height()
                defaults=s.get('checkbox_defaults_version')!=1
                self.upload_assets.set(True if defaults else s.get('upload_assets',True))
                self.generate_audio.set(s.get('generate_audio',True))
                # 第 41 期第 1 条：这一镜的勾选装进它自己那一套变量，下拉框与 save_options 共用。
                self.asset_choices_for(s['id'])
            vs=self.studio.state()['shots'][s['id']];self.note.delete(0,'end')
            if vs:self.note.insert(0,vs[-1].get('review_note',''))
            self.update_progress();self.update_prompt_controls()
        except ValueError as exc:
            # 重建列表时“未选择镜头”是正常状态；其余错误提示到进度栏，避免静默失败。
            if str(exc)!='请先选择镜头':self.progress_text.set(str(exc))
    def shot_asset_rows(self,sid):
        """这一镜声明到的资产（编号／名称／有没有图）。清单读不出来就给空表，不打断刷新。"""
        from agent.shot_assets import assets
        try:return assets(self.studio.episode_path,self.studio.shot(sid))
        except (ValueError,KeyError,TypeError,OSError):return []
    def chosen_asset_ids(self,shot,rows):
        """这一镜该勾哪几项：老镜头沿用「默认全勾」那套口径，一处说了算。

        第 41 期第 1 条：口径与原「选择资产」表一个字没变（线上看 upload_asset_ids，
        本地看 local_asset_ids；还没写过选项的老镜头默认全勾）。
        """
        ids=[a['id'] for a in rows]
        if isinstance(self.studio,LocalStudio):return shot.get('local_asset_ids',ids)
        if shot.get('checkbox_defaults_version')!=1:return ids
        return shot.get('upload_asset_ids',ids) if shot.get('upload_assets',True) else []
    def asset_choices_for(self,sid):
        """这一镜的资产勾选状态：一镜一份，下拉框、格子里的字与写回共用同一套变量。"""
        if getattr(self,'asset_sid',None)!=sid:
            rows=self.shot_asset_rows(sid)
            chosen=self.chosen_asset_ids(self.studio.shot(sid),rows)
            self.asset_choices={a['id']:tk.BooleanVar(value=a['id'] in chosen) for a in rows}
            self.asset_sid=sid
        return self.asset_choices
    def asset_cell_text(self,sid):
        """「选择资产」那一格的字：这一镜勾了哪几项（第 41 期第 1 条）。

        一格写一镜自己的勾选——全选镜头号之后每一行各写各的，不会再只有一镜亮着。
        """
        rows=self.shot_asset_rows(sid)
        if not rows:return '未声明资产'
        declared=[a['id'] for a in rows]
        chosen=[aid for aid in self.chosen_asset_ids(self.studio.shot(sid),rows) if aid in declared]
        if not chosen:return '未选资产 ▾'
        return '、'.join(chosen[:3])+('…' if len(chosen)>3 else '')+'（%d/%d） ▾'%(len(chosen),len(rows))
    def refresh_asset_cell(self,sid):
        if self.tree.exists(sid):self.tree.set(sid,ASSET_FIELD,self.asset_cell_text(sid))
    def asset_column(self):
        return '#'+str(list(self.tree['columns']).index(ASSET_FIELD)+1)
    def asset_cell_at(self,event):
        """鼠标底下是不是「选择资产」那一格：按格子自己画出来的位置判。

        第 41 期第 1 条：多列并排时 identify_column 与 bbox 在列边界上差几个像素
        （实测点格子左边沿会被记成前一列），归属按 bbox 判才准。
        """
        sid=self.tree.identify_row(event.y)
        if not sid:return None
        bounds=self.tree.bbox(sid,ASSET_FIELD)
        if not bounds:return None
        x,y,width,height=bounds
        if x<=event.x<x+width and y<=event.y<y+height:return sid
        return None
    def set_all_assets(self,sid,value):
        for var in self.asset_choices_for(sid).values():var.set(value)
        self.save_options(sid)
    def open_asset_picker(self,sid):
        """「选择资产」那一格：点一下开一扇窗（第 57 期第 5 条）。

        原来左键弹一份勾选下拉框、右键再弹一句「查看资产图片」，同一件事分在两处；现在一格一窗：
        一行一项资产（缩略图 ＋ 勾选状态 ＋ 编号名称 ＋ 这一项有没有图）。单击「选择」那一格＝
        勾上／取消（写回的口径与原来那份下拉框一字不差，见 save_options），双击一行或按「查看图片」
        ＝打开它的图。整页「镜头正在制作」时与原来那张表一样改不动（勾选那一下会说明原因）。

        第 59 期第 11 条：勾选那一列换成与其余内容框一模一样的那一套——首列就是勾选图元（点行／
        点它＝勾上或取消，表头点一下全选），缩略图挪到它右边单独一栏盖一层（树的内容框只有首列
        摆得了图，盖一层是各页通用的做法）。原来这一列写的是 ☑／☐ 两个字符，与别页的勾选框
        看着就不是一套东西；缩略图那一层顺带给了「停上去放大、双击打开」。
        """
        rows=self.shot_asset_rows(sid)
        choices=self.asset_choices_for(sid)
        locked=prompt_locked(self,sid)
        from cell_hover import CellHover,CellImages,ZOOM_SIZE
        from responsive_ui import refresh_check_heading,row_toggle_target
        tick_images=list(getattr(self.scheduler,'_tick_images',None) or ('',''))
        win=BaseDialog(self.window,'选择资产 · '+sid,geometry='720x430',minsize=(520,340),modal=False,chrome=False);win.withdraw()
        ttk.Label(win,wraplength=WRAPLENGTH['lg'],text=(
            LOCKED_NOTE if locked else
            '单击一行＝勾上／取消（勾上的随视频上传）；双击缩略图看它的图片。' if rows else
            '这一镜没有声明资产，或资产清单暂时读不出来。')).pack(anchor='w',padx=SPACING['md'],pady=(SPACING['md'],SPACING['sm']))
        note=tk.StringVar()
        ttk.Label(win,textvariable=note,style='Muted.TLabel',wraplength=WRAPLENGTH['lg']).pack(anchor='w',padx=SPACING['md'],pady=(SPACING['none'],SPACING['sm']))
        table_shell=DataTable(win,columns=[
            ('thumb','缩略图',PICK_THUMB_SIZE+28),('name','资产',300),('state','图片',90),
        ],show='tree headings',height=PICK_ROWS,selectmode='browse',style='Picker.Treeview',
          empty_text='暂无可选资产')
        table=table_shell.tree
        fit_row_height(table,PICK_THUMB_SIZE,style='Picker.Treeview')   # 第 58 期第 2 条
        configure_check_column(table)                                   # 第 59 期第 11 条：首列＝勾选框
        table.heading('thumb',text='缩略图')
        table.column('thumb',width=PICK_THUMB_SIZE+28,minwidth=PICK_THUMB_SIZE+28,stretch=False)
        table.heading('name',text='资产');table.column('name',width=SPACING['sm'] * 38)
        table.heading('state',text='图片');table.column('state',width=SPACING['sm'] * 11,stretch=False)
        thumbs={}
        def checked(aid):return bool(choices.get(aid) and choices[aid].get())
        def row_asset(aid):
            return next((item for item in rows if str(item['id'])==str(aid)),None)
        def mark(aid):
            if table.exists(aid):table.item(aid,image=tick_images[1 if checked(aid) else 0])
        def mark_header():
            refresh_check_heading(table,tick_images,checked)
        def fill():
            table.delete(*table.get_children());thumbs.clear()
            for asset in rows:
                aid=str(asset['id'])
                path=asset.get('path')
                image=asset_thumbs.thumbnail(win,path,PICK_THUMB_SIZE) if path else None
                thumbs[aid]=image                        # 图元得挂住：Tk 一回收，画面上只剩空框
                table.insert('','end',iid=aid,text='',image=tick_images[1 if checked(aid) else 0],
                             values=('',aid+' '+str(asset.get('name',aid)),
                                     '可用' if asset.get('ready') else '缺图'))
        def thumb_image(aid,size):
            """这一行的缩略图（size 一档）：格子那一张与停上去放大那一张各解各的。"""
            asset=row_asset(aid)
            path=asset.get('path') if asset else None
            if not path or not asset.get('ready'):return None
            try:return asset_thumbs.thumbnail(win,path,size)
            except (ValueError,OSError):return None
        def say(text):
            """要说的那一句写在窗里（第 57 期第 2 条）：勾不动、没图看都属于「说一声」，
            不该弹一个模态错误框把人拦在窗口前——那一下看着就是个 BUG 提示。"""
            note.set(str(text))
            return text
        def toggle(aid):
            if locked:return say(LOCKED_SAY)
            if aid not in choices:return
            choices[aid].set(not choices[aid].get())
            self.save_options(sid);mark(aid);mark_header()
            say('已勾选：'+aid if choices[aid].get() else '已取消：'+aid)
        def view(aid):
            asset=row_asset(aid)
            if asset is None:return say('请先点一行资产')
            if not asset.get('ready') or not asset.get('path'):
                return say(str(aid)+' 还没有可看的资产图片')
            open_path(str(asset['path']))
        def set_all(value):
            if locked:return say(LOCKED_SAY)
            for aid in choices:choices[aid].set(value)
            self.save_options(sid)
            for aid in table.get_children():mark(aid)
            mark_header()
            return say('已全部勾选' if value else '已全部取消：这一镜不再上传资产')
        def on_click(event):
            aid=row_toggle_target(table,event.x,event.y)     # 首列那一格也算（与其余内容框同一条口径）
            if aid:self.safe(lambda:toggle(aid))
        bar=FlowBar(win);bar.pack(side='bottom',fill='x',padx=SPACING['md'],pady=(SPACING['none'],SPACING['md']))
        for label,action in (('全选',lambda:set_all(True)),('全不选',lambda:set_all(False)),
                             ('查看图片',lambda:view(table.focus() or '')),('关闭',win.destroy)):
            SecondaryButton(bar,text=label,command=lambda f=action:self.safe(f)).pack(side='left',padx=(SPACING['none'],SPACING['xs']))
        table.bind('<Button-1>',on_click,add='+')
        # 缩略图那一层（第 59 期第 11 条）：双击打开、停上去放大，与资产页「参考图」那一格同一套。
        # 它盖住的那一格落不到树上，所以单击不重发给树——勾选自有点那一行／首列那一下。
        table.cell_hover=CellHover(table,('#1',),lambda row,column:self.safe(lambda:view(row)),
                                    hover_only=True)
        def thumb_value(row,column):
            image=thumb_image(row,PICK_THUMB_SIZE)
            return None if image is None else (image,'')
        table.cell_images=CellImages(table,('#1',),thumb_value,hover=table.cell_hover,
                                    plain=table.cell_hover,
                                    zoom=lambda row,column:thumb_image(row,ZOOM_SIZE))
        # 第 57 期第 5 条：内容框最后 pack 去吃掉剩下的地方（底下那排按钮先按 side='bottom' 落了位，
        # 窗口再矮也是内容框先让步）。少了这一句整张表根本没摆进窗里——窗里只剩说明与按钮，
        # 一行资产都看不见（眼验截图里就是这么一片空白）。
        table_shell.pack(fill='both',expand=True,padx=SPACING['md'],pady=(SPACING['none'],SPACING['sm']))
        fill();mark_header();win.update_idletasks()
        win.geometry('+%d+%d'%(max(0,self.window.winfo_rootx()+(self.window.winfo_width()-win.winfo_width())//2),
                               max(0,self.window.winfo_rooty()+(self.window.winfo_height()-win.winfo_height())//2)))
        win.deiconify()
        return win
    def asset_cell_click(self,event):
        """「选择资产」那一格：点一下开弹窗（第 41 期第 1 条；第 57 期第 5 条改成弹窗）。

        与其余内容框同一条点击规矩：本行没勾就先补勾选再打开，已勾的直接打开。
        """
        sid=self.asset_cell_at(event)
        if not sid:return False
        self.tree.focus_set();self.tree.focus(sid)
        if self.tree.selection()!=(sid,):self.tree.selection_set(sid)
        if not self.edit_checks.get(sid,False):self.toggle_edit_check(sid)
        self.open_asset_picker(sid)
        return True
    def update_progress(self):
        selected=self.tree.selection()
        if not selected:return
        sid=selected[0];versions=self.studio.state()['shots'].get(sid,[]);v=versions[-1] if versions else {}
        self.busy_state.set_busy(False)
        if self.local_submit_sid==sid:
            self.busy_state.set_busy(True);return
        if sid in self.local_submit_error and not v.get('task_id'):
            self.progress_text.set(sid+' · 提交失败：'+self.local_submit_error[sid]);return
        if v.get('state')=='downloaded' and v.get('file') and (self.root/v['file']).is_file():
            from agent.core import read
            qc=(self.root/v['file']).parent/'qc.json'
            errors=read(qc).get('errors',[]) if qc.is_file() else []
            self.progress_text.set('已下载 · '+sid+'\n保存位置：'+str(self.root/v['file'])+('\n质检：'+'；'.join(errors) if errors else ''))
        elif v.get('state') in ('unknown','submitting') and not v.get('task_id'):
            self.progress_text.set(sid+' · 提交结果待核实：未收到任务编号。点“恢复任务编号”，从服务商控制台粘贴编号。不会自动重发。')
        elif v.get('task_id') and v.get('state') in ('queued','running','succeeded','unknown','submitting'):
            self.busy_state.set_busy(True)
            self.progress_text.set(sid+' · '+{'queued':'排队中','running':'生成中','succeeded':'正在下载'}.get(v['state'],'正在恢复查询')+elapsed_text(v,time.time())+'；自动跟踪。任务编号：'+v['task_id'])
        else:
            pending=[shot_id for shot_id,records in self.studio.state()['shots'].items() if shot_id!=sid and records and records[-1].get('state') in ('queued','running','succeeded','unknown','submitting')]
            if self.local_submit_sid and self.local_submit_sid!=sid and self.local_submit_sid not in pending:pending.append(self.local_submit_sid)
            detail=sid+' · '+status_detail(v)
            if pending:detail+='\n后台跟踪：'+'、'.join(pending)+'（切换查看不会提交当前镜头）'
            self.progress_text.set(detail)
    def auto_poll(self):
        if self.busy or time.monotonic()<self.next_poll:return
        self.next_poll=time.monotonic()+5
        if not isinstance(self.studio,LocalStudio) and not self.studio.cfg.get('live_enabled'):return
        st=self.studio.state();pending=[]
        for shot in self.studio.episode['shots']:
            versions=st['shots'].get(shot['id'],[])
            if not versions or shot.get('video_deleted'):continue
            v=versions[-1]
            receipt=self.studio.task_folder(shot['id'],v)/'task_receipt.json'
            if (v.get('task_id') or receipt.is_file()) and v.get('state') in ('queued','running','succeeded','unknown','submitting'):
                pending.append(shot['id'])
        if pending:
            self.poll_wait=poll_delay(len(pending));self.poll_started=time.monotonic()
            sid=pending[self.poll_cursor%len(pending)];self.poll_cursor+=1;self.polling_sid=sid
            studio=self.studio
            self.run(lambda sid=sid,studio=studio:studio.poll(sid),quiet=True)
    def ensure_frame(self,sid):
        # A background image task may have imported a new filename since this
        # page was opened. Refresh only image metadata, preserving prompt edits.
        from agent.core import read
        episode=read(self.studio.episode_path)
        latest=next((s for s in episode['shots'] if s['id']==sid),None)
        if latest is None:raise ValueError('此镜头已从分镜中移除，请刷新列表：'+sid)
        shot=self.studio.shot(sid)
        for field in ('frame','frame_deleted'):
            if field in latest:shot[field]=latest[field]
            else:shot.pop(field,None)
        path=self.studio.frame(shot,required=False)
        if path.is_file() and not shot.get('frame_deleted'):return True
        callback=getattr(self,'missing_frame_callback',None)
        if callback:
            self.write(sid+' 缺少首帧，已转到'+pet_bus.stage_step('keyframe')+'；本次未提交视频生成。')
            callback(sid);return False
        self.studio.frame(shot)
        return False
    def frame(self):
        sid=self.sid()
        if self.ensure_frame(sid):open_path(self.studio.frame(self.studio.shot(sid)))
    def play(self):
        vs=self.studio.state()['shots'][self.sid()]
        files=[v for v in vs if v.get('file')]
        if not files:raise ValueError('没有已下载视频')
        open_path(self.root/files[-1]['file'])
    def versions(self):
        self.studio.cloud_index()
        folder=self.studio.shot_folder(self.sid());folder.mkdir(parents=True,exist_ok=True);open_path(folder)
    def save_options(self,sid=None):
        """把这一镜的资产勾选与声音开关写下（第 41 期第 1 条：可以指名是哪一镜）。

        勾选取自 self.asset_choices——那就是下拉框上那几个变量；没指名镜头时是正在编辑的
        那一镜，切了镜头会按那一镜自己的值重装，不会把上一镜的勾选写到下一镜头上。
        """
        sid=sid or self.sid()
        assert_prompt_editable(self,sid)
        selected=[aid for aid,value in self.asset_choices_for(sid).items() if value.get()]
        from stage_execution_service import save_stage_video_options
        if isinstance(self.studio,LocalStudio):
            self.studio.episode=save_stage_video_options(self.studio.episode_path,sid,selected,
                                                    self.generate_audio.get(),True)
        else:
            self.studio.episode=save_stage_video_options(self.studio.episode_path,sid,selected,
                                                    self.generate_audio.get(),False)
            self.upload_assets.set(bool(selected))
        self.refresh_asset_cell(sid)
    def save_prompt(self):
        assert_prompt_editable(self)
        value=self.prompt.get('1.0','end').strip()
        if not value or len(value)>1500:raise ValueError('提示词须为1–1500个字符')
        from stage_execution_service import publish_video_prompt
        self.save_options()
        publish_video_prompt(self.studio,self.sid(),value)
        self.write('已覆盖当前镜头提示词文件；历史视频的实际提交记录保留。')
    def flush_prompt(self, next_sid):
        """切换镜头前，自动保存当前镜头尚未保存的提示词编辑，避免丢稿。"""
        sid = getattr(self, 'editing_sid', None)
        if not sid or sid == next_sid or self.busy:
            return
        if not getattr(self, 'prompt', None) or not self.tree.exists(sid):
            return
        text = self.prompt.get('1.0', 'end').strip()
        if not text:
            return
        if len(text) > 1500:
            self.write(sid + ' 提示词超过 1500 字，未自动保存，请精简后点“保存提示词”。')
            return
        shot = self.studio.shot(sid)
        if shot.get('video_prompt', '').strip() == text:
            return
        from stage_execution_service import publish_video_prompt
        publish_video_prompt(self.studio, sid, text)
        self.write(sid + ' 提示词已自动保存（切换镜头前）。')
    def review(self,value):
        self.studio.review(self.sid(),value,self.note.get());self.refresh()
    def fit_shot_columns(self):
        fit_columns_by_content(self.tree, {'white_model': lambda w: w + self.edit_icons[0].width() + 8})
    def check_prompt_record(self,record):
        from agent.core import fingerprint
        if not isinstance(record,dict):raise ValueError('提示词 JSON 应为包含 video_prompt 的对象')
        if record.get('shot_id') not in (None,'',self.sid()):
            raise ValueError('提示词属于其他镜头，请选择对应镜头后再读取')
        if record.get('source_signature')!=fingerprint(self.studio.shot(self.sid())):
            self.write('提示：此提示词版本与当前分镜或资产选项不同，仍可读取和优化，请核对人物、动作及对白。')
    def import_prompt(self):
        assert_prompt_editable(self)
        from agent.core import read
        sid=self.sid()
        if getattr(self,'optimizer_busy',False):raise ValueError('请等待 MCP 优化完成后再导入')
        folder=self.studio.media_dir/'video_prompts'
        name=FileDialog(self.window).open_file(title='为 '+sid+' 导入提示词',
            initialdir=str(folder if folder.is_dir() else self.studio.episode_path.parent),
            filetypes=[('提示词文件','*.txt *.md *.json'),('文本','*.txt'),('Markdown','*.md'),('JSON','*.json')])
        if not name:return
        source=Path(name)
        if source.stat().st_size>1024*1024:raise ValueError('请选择小于1MB的单镜头提示词文件')
        if source.suffix.lower()=='.json':
            record=read(source)
            self.check_prompt_record(record)
            text=record.get('video_prompt','')
        else:
            raw=source.read_bytes()
            try:text=raw.decode('utf-8-sig')
            except UnicodeDecodeError:
                try:text=raw.decode('gb18030')
                except UnicodeDecodeError:raise ValueError('无法识别文件编码，请另存为 UTF-8 文本')
        if not isinstance(text,str) or not text.strip():raise ValueError('提示词为空，JSON 需要包含 video_prompt')
        text=text.strip()
        if len(text)>1500:raise ValueError('单镜头提示词不能超过1500字，请精简后导入')
        from stage_execution_service import import_video_prompt
        import_video_prompt(self.studio,sid,text)
        self.prompt.delete('1.0','end');self.prompt.insert('1.0',text);self.editing_sid=sid;self.fit_prompt_height()
        self.write('已导入 '+sid+' 提示词，可继续 MCP 优化；确认后点击保存提示词。原文件保留。')
    def open_prompt_folder(self):
        folder=self.studio.media_dir/'video_prompts'
        folder.mkdir(parents=True,exist_ok=True)
        open_path(str(folder))
    def start_prompt_skill(self):
        assert_prompt_editable(self)
        if getattr(self,'optimizer_busy',False):raise ValueError('请等待 MCP 优化完成')
        if not self.prompt_callback:raise ValueError('请从制作助手的视频生成页面打开 Skill 工作流')
        sid=self.sid();self.save_options()
        initial=self.prompt.get('1.0','end').strip()
        self.prompt_callback(sid)
        from ui.video_prompt_results import PromptResults
        if not hasattr(self,'prompt_results'):self.prompt_results=PromptResults()
        self.prompt_results.begin(sid,initial)
        self.write(sid+' Agent 已调用；生成完成后会自动导入并保存，可切换其他镜头。')
    def make_prompt(self):
        assert_prompt_editable(self)
        from agent.prompt_optimizer import start
        text=self.prompt.get('1.0','end').strip()
        if not text:raise ValueError('请先在上方文字框准备提示词')
        self.save_options()
        start(self,source_prompt=text)
    def confirm_submit(self,title,message,seconds):
        """云端提交确认。开启「自动提交（不弹确认）」且不超剩余预算时直接提交。

        无人值守时不弹窗也不超预算扣费：超出预算直接报错，由用户调整预算或减少勾选。
        """
        from infra.pet_llm import RequestLedger
        estimate = RequestLedger(project_root(self.studio.root)).preview_text(
            self.studio.cfg.get('model', ''), 'videos', {'seconds': seconds})
        message += '\n\n' + estimate
        if ui_plugin_registry.module('pet_ui').should_auto_run(self, self.root, 'auto_submit'):
            remaining=self.studio.remaining()
            if seconds>remaining:
                raise ValueError(title+'已取消：本次需要 '+str(seconds)+' 秒，超过可用预算 '+str(remaining)+
                                 ' 秒。无人值守自动提交不会超预算提交，请调整预算或减少勾选后重试。')
            self.write(title+'：无人值守自动提交，已跳过确认框（'+str(seconds)+' 秒／预算剩余 '+str(remaining)+' 秒）')
            self.write(estimate)
            return True
        return ask_confirmation(self.window, title, message, dangerous=True)
    def auto_submit_scan(self):
        """无人值守自动提交：把从未提交过、首帧已就绪的镜头依次自动提交，一次只提交一个。

        只在联网、云端后端、不超剩余预算时提交；每个镜头在本窗口内最多自动提交一次，
        失败原因写进日志，避免无人值守时反复重试、反复扣费。首帧还没就绪的镜头下一轮再看。
        """
        if not ui_plugin_registry.module('pet_ui').should_auto_run(self, self.root, 'auto_submit') or self.busy:return
        if isinstance(self.studio,LocalStudio) or not self.studio.cfg.get('live_enabled'):return
        st=self.studio.state()
        for shot in self.studio.episode['shots']:
            sid=shot.get('id')
            if not sid or shot.get('video_deleted') or sid in self.auto_submitted or st['shots'].get(sid):continue
            seconds=shot.get('duration') or 0
            if seconds>self.studio.remaining():
                self.write('无人值守自动提交暂停：'+sid+' 需要 '+str(seconds)+' 秒，超过剩余预算 '+str(self.studio.remaining())+' 秒。')
                return
            frame=self.studio.frame(shot,required=False)
            if shot.get('frame_deleted') or not frame.is_file():continue
            if prompt_locked(self,sid):continue
            self.auto_submitted.add(sid)
            self.write('无人值守自动提交：'+sid)
            self.submitting_sid=sid
            self.run(lambda sid=sid:self.studio.submit(sid))
            return
    def generate(self):
        sid=self.sid()
        if not self.edit_checks.get(sid,False):
            # 第 47 期第 1 条：统一「选中」口径——高亮那一行就是用户点名要做的那一镜，
            # 顺手补上勾选再往下走。原来这里直接打回一句「请勾选」，用户看着那一行明明是选中的。
            self.toggle_edit_check(sid)
            self.write(sid+' 未勾选：按高亮的那一行算，已替您勾上。')
        versions=self.studio.state()['shots'].get(sid,[])
        if versions and versions[-1].get('state') in ('queued','running','succeeded','unknown','submitting'):
            self.update_progress();self.next_poll=0
            self.write('此镜头已有提交记录，已继续跟踪；不会重复提交。');return
        blocked=submission_block_reason(versions)
        if blocked:
            self.write(sid+' '+blocked);return
        if getattr(self,'optimizer_busy',False):raise ValueError('MCP 正在优化提示词，请完成后再生成视频')
        assert_prompt_editable(self,sid)
        if not self.ensure_frame(sid):return
        if self.prompt.get('1.0','end').strip()!=self.studio.shot(self.sid())['video_prompt']:
            self.save_prompt()
        if isinstance(self.studio,LocalStudio):
            sid=self.sid();self.save_options();self.local_submit_sid=sid;self.local_submit_error.pop(sid,None)
            self.progress_text.set(sid+' · 正在准备提交…');self.busy_state.set_busy(True)
            self.write('手动提交已锁定镜头：'+sid);studio=self.studio
            self.run(lambda sid=sid,studio=studio:studio.submit(sid,progress=lambda text:self.local_messages.put((sid,text))));return
        self.save_options()
        sid=self.sid();seconds=self.studio.shot(sid)['duration']
        if not self.studio.cfg['live_enabled']:raise ValueError('当前离线模式，请先在设置中开启联网')
        from agent.shot_assets import prepare
        prepared=prepare(self.studio.episode_path,self.studio.shot(sid),self.studio.cfg)
        details='\n'.join(a['id']+' '+a['name'] for a in prepared['_asset_references'])
        mode={'wan':'首帧＋资产参考图','seedance':'多图参考（首帧为构图参考，不严格锁定）','first_frame':'仅上传首帧'}[prepared['_reference_mode']]
        sound='有声' if prepared.get('generate_audio',True) else '无声'
        details=details or '不上传额外资产'
        if self.confirm_submit('提交预览',f'{sid}：{seconds}秒，720P，{sound}。\n模式：{mode}\n上传资产：\n{details}\n另上传本镜首帧。\n本地可用制作预算：{self.studio.remaining()}秒。\n将消耗云端额度，超出免费额度可能计费。\n只提交当前镜头，是否继续？',seconds):
            self.write('手动提交已锁定镜头：'+sid);studio=self.studio
            self.submitting_sid=sid
            self.run(lambda sid=sid,studio=studio:studio.submit(sid))
    def generate_checked(self):
        ids,how=work_targets(self)
        if not ids:raise ValueError('请先勾选需要生成的镜头')
        if how=='shown':self.write('没有勾选行：按高亮的那一行 %s 提交。'%ids[0])
        if getattr(self,'optimizer_busy',False):raise ValueError('MCP 正在优化提示词，请完成后再生成视频')
        # 当前镜头若已编辑提示词但未保存，先保存，避免批量提交用旧稿
        try:
            sid=self.sid()
            if sid in ids and self.prompt.get('1.0','end').strip()!=self.studio.shot(sid).get('video_prompt','').strip():
                self.save_prompt()
        except ValueError:
            pass
        todo=pending_checked_shots(self.studio,ids)
        if not todo:
            self.update_progress();self.next_poll=0
            self.write('勾选镜头均已提交或就绪，无需重复提交。');return
        if not isinstance(self.studio,LocalStudio):
            if not self.studio.cfg['live_enabled']:raise ValueError('当前离线模式，请先在设置中开启联网')
            seconds=sum(self.studio.shot(sid)['duration'] for sid in todo)
            if not self.confirm_submit('批量提交预览',f'将提交 {len(todo)} 个镜头，共 {seconds} 秒。\n本地可用制作预算：{self.studio.remaining()} 秒。\n将消耗云端额度，超出免费额度可能计费。\n只提交勾选镜头，是否继续？',seconds):return
        self.write('批量提交已锁定镜头：'+'、'.join(todo));studio=self.studio
        def work():
            results=[]
            for sid in todo:
                try:
                    results.append(sid+' '+str(studio.submit(sid)))
                except Exception as exc:
                    results.append(sid+' 提交失败：'+str(exc))
            return '批量提交结束：'+'；'.join(results)
        self.run(work)
    def attach(self):
        sid=self.sid();value=ask_string(self.window,'恢复编号','请从控制台核实是该镜头后，粘贴任务ID（不是API Key）：')
        if not value:return
        task_id=value.strip()
        if not task_id:return
        self.studio.attach(sid,task_id)
        self.refresh();self.update_progress();self.next_poll=0
        self.write(sid+' 已恢复任务编号：'+task_id+'，将自动跟踪查询。')
    def settings(self):
        if isinstance(self.studio,LocalStudio):return settings_window(self)
        win=BaseDialog(self.window,'设置',modal=False,chrome=False);win.attributes('-alpha',0)
        body=Card(win,padding=SPACING['lg']);body.pack(fill='both',expand=True);body.columnconfigure(1,weight=1);entries={}
        labels={'project_dir':'密钥.env所在目录','base_url':'阿里云API根地址','model':'模型ID','ffmpeg':'FFmpeg程序','ffprobe':'FFprobe程序','budget_seconds':'本地总预算秒数（含历史占用）','reserve_seconds':'备用秒数'}
        for row,(key,label) in enumerate(labels.items()):
            ttk.Label(body,text=label).grid(row=row,column=0,padx=SPACING['sm'],pady=SPACING['sm'],sticky='w')
            e=LineInput(body,width=CHAR_WIDTH['field_lg']);e.insert(0,str(self.studio.cfg[key]));e.grid(row=row,column=1,padx=SPACING['sm']);entries[key]=e
        live=tk.BooleanVar(value=self.studio.cfg['live_enabled']);ttk.Checkbutton(body,text='开启联网生成与查询（需手动提交）',variable=live).grid(row=len(labels),column=1,sticky='w')
        def commit():
            try:
                if self.busy:raise ValueError('请等待当前操作完成')
                cfg=dict(self.studio.cfg)
                for k,e in entries.items():cfg[k]=int(e.get()) if k.endswith('_seconds') else e.get().strip()
                if not 0<=cfg['reserve_seconds']<=cfg['budget_seconds']:raise ValueError('预算设置无效')
                cfg['live_enabled']=live.get()
                from agent.wan import WanAdapter
                WanAdapter(cfg) # Reject arbitrary credential destinations before saving.
                from stage_execution_service import publish_cloud_video_studio_config
                publish_cloud_video_studio_config(self.root/'config.json',cfg);self.studio.cfg=cfg;win.destroy();self.refresh()
            except Exception as e:self.notifier.error(str(e), title='无法保存')
        PrimaryButton(body,text='保存',command=commit).grid(row=len(labels)+1,column=1,pady=SPACING['md'])
    def open_assembled(self):
        from contract.project_stages import exports
        folder=exports(self.root);folder.mkdir(parents=True,exist_ok=True)
        open_path(str(folder))
    def run(self,fn,quiet=False,on_success=None):
        if self.busy:raise ValueError('任务正在执行')
        self.busy=True;self.quiet_run=quiet;self.on_success=on_success
        self.update_prompt_controls()
        if not quiet:self.write('开始操作…')
        def work():
            try:self.results.put((True,fn()))
            except Exception as e:self.results.put((False,str(e)))
        threading.Thread(target=work,daemon=True).start()
    def _record_result_render_failure(self,exc,phase):
        """限频记录固定位置和异常类型；不采集结果、异常全文或项目路径。"""
        now=time.monotonic()
        if now<getattr(self,'_result_render_report_due',0):return
        self._result_render_report_due=now+30
        try:
            import infra.diagnostic_capture as diagnostic_capture
            diagnostic_capture.record_degradation(
                RuntimeError('视频结果渲染失败：'+type(exc).__name__),
                page='视频生成',stage='app.tick.'+phase)
        except Exception:
            # 诊断磁盘不可用也不能停止查询；同样限频，不另建日志出口。
            app_logging.swallowed()
    def tick(self):
        # Keep network tracking alive even when its panel is hidden or a UI refresh fails.
        if self.closed:return
        try:
            while not self.local_messages.empty():
                sid,text=self.local_messages.get_nowait()
                selection=self.tree.selection()
                if selection and selection[0]==sid:self.progress_text.set(sid+' · '+text)
                else:self.write('后台任务 '+sid+' · '+text)
            try:ok,value=self.results.get_nowait()
            except queue.Empty:pass
            else:self._tick_result(ok,value)
            if time.monotonic()>=self.next_ui_update:
                self.next_ui_update=time.monotonic()+1
                try:
                    self.update_prompt_controls(periodic=True)
                    if self.window.winfo_ismapped():
                        self.update_progress();self.refresh_shared_progress()
                except (tk.TclError,ValueError,OSError):pass
            try:self.prompt_results.poll(self)
            except (OSError,ValueError):pass  # Project temporarily locked; retry next poll.
            if time.monotonic()>=self.auto_submit_due:
                self.auto_submit_due=time.monotonic()+5
                try:self.auto_submit_scan()
                except Exception as exc:
                    try:self.write('无人值守自动提交检查失败：'+str(exc))
                    except tk.TclError:pass
            try:self.auto_poll()
            except Exception as exc:
                self.next_poll=time.monotonic()+30
                try:self.write('后台跟踪暂时异常，30秒后重试查询，不会重新提交生成：'+str(exc))
                except tk.TclError:pass
        finally:
            if not self.closed:
                try:
                    if self.window.winfo_exists():self.timer=self.scheduler.after(150,self.tick)
                except tk.TclError:
                    # Tk 可能在存活检查或注册下一次回调时已退出。
                    pass
    def _tick_result(self,ok,value):
        """收一条提交／轮询结果：复位忙碌状态、回调、写日志、刷新界面与失败提示。"""
        self.busy=False;self.submitting_sid=None
        if self.local_submit_sid:
            if not ok:self.local_submit_error[self.local_submit_sid]=str(value)
            self.local_submit_sid=None
        callback=getattr(self,'on_success',None);self.on_success=None
        if ok and callback:
            try:callback(value)
            except Exception as exc:self.write('成片目录打开失败：'+str(exc))
        self.next_poll=(max(time.monotonic(),getattr(self,'poll_started',0)+self.poll_wait) if self.quiet_run else time.monotonic()) if ok else time.monotonic()+30
        phase='write_result'
        try:
            if not (ok and self.quiet_run and self.last_poll_messages.get(self.polling_sid)==str(value)):self.write(str(value))
            if ok and self.quiet_run:self.last_poll_messages[self.polling_sid]=str(value)
            # 第 47 期第 5 条：手动／批量提交收了尾就说一句；后台轮询的进度不报（太吵）。
            phase='report_done'
            if ok and not self.quiet_run:self.report_done(value)
            phase='window_state'
            if self.window.winfo_ismapped():
                phase='refresh';self.refresh()
                phase='update_progress';self.update_progress()
            phase='failure_notice'
            if not ok:
                if self.quiet_run:
                    self.write('后台查询或下载暂时中断，30秒后自动重试；不会重新提交生成。')
                elif self.window.winfo_ismapped():
                    self.notifier.error(str(value), title='操作未完成')
        except Exception as exc:
            # Results/task IDs are persisted by the engine; rendering must not stop polling.
            self._record_result_render_failure(exc,phase)
    def cancel_timers(self,event=None):
        # 视频页定时器挂在 Tk 主窗口上，窗口销毁后回调会报 invalid command name。
        if event is not None and event.widget is not self.window:return
        self.closed=True
        timer=getattr(self,'timer',None)
        if timer:
            try:self.scheduler.after_cancel(timer)
            except Exception:app_logging.swallowed()
            self.timer=None
    def report_done(self,value):
        """手动提交收了尾：走宿主传进来的那条出口说给三虎；宿主没接就静默返回。"""
        callback=getattr(self,'report_callback',None)
        if not callable(callback):return None
        try:return callback('video',str(value))
        except Exception:return None
    def write(self,text):
        self.log.configure(state='normal');self.log.insert('end',text+'\n');self.log.see('end');self.log.configure(state='disabled')
        # 第 58 期第 1 条：日志框跟着内容自己长高（上限 LOG_ROWS_MAX 行；地方不够时先让提示词框）。
        self.fit_log_height()
    def square_check(self,parent,value):
        ttk.Checkbutton(parent,variable=value,style='TCheckbutton',
            command=lambda:self.safe(self.save_options)).pack(side='left')

if __name__=='__main__':
    # 启动适配器与可嵌入的 App 视图分离：避免 App 被 desktop 使用时形成反向导入。
    # 调试入口不跑启动自检（任务书 G4）：与 启动漫剧制作助手.pyw 的正式启动区分开。
    ui_plugin_registry.module('desktop_launcher').launch(selfcheck=False)
