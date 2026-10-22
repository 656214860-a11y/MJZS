"""desktop_writing_page.WritingPageMixin.writing（剧本准备页）由闭包改写成类：旧方法原样内嵌，用同一份脚本驱动两个真 Desktop，逐步对照整棵控件树。"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import desktop_writing_page as module
import pet_state
from page_diff_support import freeze_times, poke, pump, snapshot
from catalog_page_test_support import show_catalog_page_ready
from skip_reasons import PLATFORM_TKINTER

LEGACY_WRITING = r'''def _legacy_writing(self):
    from script_workspace_service import ensure_script_workspace
    result=ensure_script_workspace(self.root)
    if not result.ok:raise ValueError(result.reason)
    # 第 69 期任务 4：原来第一行那句「在下面的对话框写想法…」删掉——页面自己会说清怎么走。
    import idea_chat
    # 先使用不扫描目录的默认路径；历史创意文件由页面建好后在后台发现。
    brief=idea_chat.default_brief_document(self.idea_chat_context())
    self.idea_template=self.idea_example()
    # 聊天记录与发送框分离：记录可滚动，发送框固定停在聊天区域底部。
    talk=ttk.Frame(self.content,style='Box.TFrame',padding=(SPACING['xs'],SPACING['none']))
    # 标题、聊天框与左侧内容起点同高；不在标题下额外留出一档空白。
    talk.pack(fill='both',expand=True,pady=SPACING['none'])
    # 第 69 期任务 2：「发送」挪到创意框左下角；第 69 期任务 3：文件操作挪到右下角。
    # 第 71 期任务 5：这一行先摆下来（pack 先给谁算尺寸，谁就不会被挤掉）——窗口缩小时
    # 收的是上面的创意框，那颗「发送」永远留在看得见的地方。
    # 动作栏与其余制作阶段共用可换行布局。普通 pack 的左右两组按钮会在窗口
    # 变窄时互相挤压，最后把“删除剧本”裁成一个字；FlowBar 会按可用宽度分行，
    # 每颗按钮始终保留自己的完整文字宽度。
    # 用量与会话说明合成页面最底部的单行状态栏：不换行、放不下就截断，悬停看全文，
    # 不再夹在提示与输入框之间把聊天区往上挤。
    status_row=ttk.Frame(talk);status_row.pack(side='bottom',fill='x',pady=SPACING['none'])
    status_row.columnconfigure(0,weight=1,uniform='status-summary')
    status_row.columnconfigure(2,weight=2,uniform='status-summary')
    self.idea_usage_label = EllipsisLabel(status_row, text='本模型暂无用量记录', style='Muted.TLabel')
    self.idea_usage_label.grid(row=0,column=0,sticky='ew')
    self.idea_usage_tip = self.idea_usage_label.tooltip
    ttk.Label(status_row, text=' · ', style='Muted.TLabel').grid(row=0,column=1)
    self.idea_session_label = EllipsisLabel(status_row, text='', style='Muted.TLabel')
    self.idea_session_label.grid(row=0,column=2,sticky='ew')
    self.idea_session_tip = self.idea_session_label.tooltip
    foot=FlowBar(talk);foot.pack(side='bottom',fill='x',pady=SPACING['none'])
    # 输入框与操作栏保留极小缓冲带，视觉仍紧凑，同时避免鼠标落点贴边误触发送。
    composer=ttk.Frame(talk);composer.pack(side='bottom',fill='x',pady=(SPACING['none'],SPACING['xs']))
    self.idea_composer_label=ttk.Label(composer,text='输入想法/上传附件---->enter/发送',style='Muted.TLabel')
    self.idea_composer_label.pack(anchor='w')
    input_row=ttk.Frame(composer);input_row.pack(fill='x')
    input_box=TextArea(input_row,bg=COLORS['background_card'],fg=COLORS['text_primary'],insertbackground=COLORS['primary'],height=1,wrap='word',
                      font=FONTS['body'],relief='solid',bd=1,padx=SPACING['md'],pady=SPACING['sm'])
    attach_button=SecondaryButton(input_row,text=ICON_FOLDER,width=3,style='Tokens.Icon.TButton',
                             command=lambda:self.safe(self.choose_idea_attachments))
    # 附件入口放在输入框左侧，先占住固定宽度；窄窗口时输入框只使用剩余空间，
    # 既方便点击，也不会把图标挤出可视区。
    attach_button.pack(side='left',padx=(SPACING['none'],SPACING['sm']))
    input_box.pack(side='left',fill='x',expand=True)
    input_box.configure(padx=SPACING['2xl'])
    enter_hint=HintLabel(input_box,text='↵',background=COLORS['background_card'])
    enter_hint.place(relx=1.0,rely=0.5,x=-SPACING['sm'],anchor='e',bordermode='outside')
    Tooltip(enter_hint,'Enter 发送；Shift+Enter 换行')
    self.idea_enter_hint=enter_hint
    self.idea_attachment_button=attach_button
    self.idea_input_row=input_row
    self.idea_attachment_status=tk.StringVar(value='')
    self.idea_attachment_status_label=ttk.Label(composer,textvariable=self.idea_attachment_status,
                                                 style='Muted.TLabel')
    self.idea_uploaded_panel=ttk.Frame(composer)
    self.idea_attachment_delete_button=SecondaryButton(
        self.idea_uploaded_panel,text=ICON_DELETE,width=3,style='Tokens.Icon.TButton',
        command=lambda:self.safe(self.delete_uploaded_idea_attachment))
    self.idea_attachment_delete_button.pack(side='left',padx=(SPACING['none'],SPACING['sm']))
    Tooltip(self.idea_attachment_delete_button,'删除附件（勾选后删除，可多选）')
    self.idea_attachment_delete_button.state(['disabled'])
    uploaded_content=ttk.Frame(self.idea_uploaded_panel)
    uploaded_content.pack(side='left',fill='x',expand=True)
    self.idea_uploaded_table=DataTable(
        uploaded_content,columns=[],height=1,show='',selectmode='none',
        style='Compact.Tokens.DataTable.Treeview',auto_hide_scrollbars=True)
    self.idea_uploaded_table.pack(fill='x',expand=True)
    self.idea_uploaded_table.tree.bind('<Button-1>',lambda event:self.toggle_uploaded_idea_attachment(self.uploaded_idea_attachment_at(event)))
    self.idea_uploaded_table.tree.bind('<Double-Button-1>',lambda event:self.safe(lambda:self.open_uploaded_idea_attachment(event)))
    Tooltip(self.idea_uploaded_table.tree,'单击勾选，可多选；双击打开附件')
    input_hint=ttk.Label(composer,text='可在阶段配置中修改模型和SKILL',style='Muted.TLabel')
    self.idea_input_hint=input_hint
    def stop_input_hint():
        input_hint.place_forget()
    def update_input_hint(event=None):
        try:
            if not self.draft_text().strip() and input_box.focus_get() is not input_box:
                # Text 的 inside 边界已含文字内边距，避免再次累加 padx。
                input_hint.place(in_=input_box,x=SPACING['none'],rely=0.5,anchor='w')
            else:stop_input_hint()
        except tk.TclError:pass
    input_box.bind('<Destroy>',lambda event:stop_input_hint() if event.widget is input_box else None,add='+')
    dialog=ttk.Frame(talk);dialog.pack(side='top',fill='both',expand=True,pady=SPACING['none'])
    dialog_scroll=ttk.Scrollbar(dialog,orient='vertical')
    dialog_scroll.pack(side='right',fill='y')
    box=TextArea(dialog,bg=COLORS['background_card'],fg=COLORS['text_primary'],insertbackground=COLORS['primary'],
                selectbackground=COLORS['primary'],inactiveselectbackground=COLORS['primary'],selectforeground=COLORS['background_card'],height=TALK_MIN_LINES,wrap='word',
                font=FONTS['body'],relief='flat',padx=SPACING['md'],pady=SPACING['sm'],yscrollcommand=dialog_scroll.set)
    box.pack(side='left',fill='both',expand=True)
    dialog_scroll.configure(command=box.yview)
    self.brief_editor=(brief,input_box);self.brief_saved_text=''
    self.idea_log=box
    self.idea_scroll=dialog_scroll
    self.idea_input=input_box
    self.queue_initial_brief_document(input_box,brief)
    # 聊天区只读；窗口缩小时只收聊天记录区，底部发送框永远可见。
    def refit_talk(event=None):
        fit=getattr(self,'_fit_talk',None)
        if fit is None:return
        try:fit()
        except Exception:app_logging.swallowed()
    # 先让 Text 用当前布局命中鼠标位置，再在空闲时重算高度；同步重排会让选区偏到上一行。
    box.bind('<Button-1>',lambda event:box.after_idle(refit_talk),add='+')
    # 常态下可长按拖选并 Ctrl+C；单击进入编辑后，写入边界只限这条气泡的正文。
    self.shortcuts.bind(box, ('<Control-c>', '<Control-C>'), self.copy_selected_bubble_text,
                        scope='剧本准备·聊天记录', name='复制选中气泡文本')
    box.bind('<Button-3>',self.open_bubble_menu,add='+')
    box.bind('<ButtonPress-1>',self.guard_bubble_edit_pointer,add='+')
    box.bind('<B1-Motion>',self.guard_bubble_edit_pointer,add='+')
    box.bind('<B1-Motion>',self.track_bubble_click,add='+')
    box.bind('<ButtonRelease-1>',self.finish_bubble_click,add='+')
    box.bind('<KeyPress>',self.guard_bubble_edit_key,add='+')
    box.bind('<<Paste>>',self.guard_bubble_edit_key,add='+')
    box.bind('<FocusOut>',lambda event:self.finish_bubble_edit(),add='+')
    self.shortcuts.bind(box, ('<Control-Return>',), lambda event:self.finish_bubble_edit(),
                        scope='剧本准备·聊天记录', name='保存气泡编辑')
    self.shortcuts.bind(box, ('<Escape>',), lambda event:self.finish_bubble_edit(commit=False),
                        scope='剧本准备·聊天记录', name='取消气泡编辑')
    self.idea_row=foot
    # 输入框下方的动作统一为紧凑尺寸，避免长旧文案把聊天区挤窄。
    script_action_width=SCRIPT_ACTION_WIDTH
    send_button=PrimaryButton(foot,text='发送',width=script_action_width,
                           command=lambda:self.safe(self.send_message))
    send_button.pack(side='left',pady=SPACING['none']);self.idea_send=send_button
    # 剧本阶段的唯一配置入口贴着发送键：写完想法后就能直接调整模型／SKILL，
    # 不再在对话框上方额外占一行。
    # 阶段按钮属于首帧可交互核心。使用无配置读取的轻量入口，既保持“设置—
    # 中断”原有相邻顺序，也不再把 stage_config.synchronize 塞进建页回调。
    panel=ui_plugin_registry.module('skill_panel')
    holder={}
    self.stage_button=panel.stage_button_for(
        foot,lambda:panel.open_for_page(self,PAGE['script'],holder['button']))
    holder['button']=self.stage_button
    self.stage_button.pack(side='left',padx=(SPACING['xs'],SPACING['none']),pady=SPACING['none'])
    interrupt_button=SecondaryButton(foot,text='中断',width=script_action_width,command=self.interrupt_script_agent)
    interrupt_button.pack(side='left',padx=(SPACING['xs'],SPACING['none']));interrupt_button.state(['disabled']);self.idea_interrupt=interrupt_button
    self.update_script_interrupt_button()
    refresh_button=SecondaryButton(foot,text='刷新',width=script_action_width,command=lambda:self.safe(self.refresh_script_workspace))
    refresh_button.pack(side='left',padx=(SPACING['xs'],SPACING['none']));self.idea_refresh=refresh_button
    # 「删除」紧跟「刷新」：动作栏按子控件创建顺序排列，所以必须在这里创建，不能放到右侧那组。
    delete_button=SecondaryButton(foot,text='删除',width=script_action_width,command=lambda:self.safe(delete_selected_scripts))
    delete_button.pack(side='left',padx=(SPACING['xs'],SPACING['none']))
    download_button=SecondaryButton(foot,text='下载文件',width=script_action_width,command=lambda:self.safe(self.download_script))
    download_button.state(['disabled']);self.idea_download=download_button
    SecondaryButton(foot,text='添加剧本',width=script_action_width,
               command=lambda:self.safe(self.import_json)).pack(side='right')
    open_folder_button=SecondaryButton(foot,text='剧本目录',width=script_action_width,
                                  command=lambda:self.safe(lambda:self.open_folder(project_stages.writing(self.root))))
    open_folder_button.pack(side='right',padx=(SPACING['none'],SPACING['sm']));self.idea_open_folder=open_folder_button
    self.build_script_quality_buttons(foot)
    download_button.pack(side='right',padx=(SPACING['none'],SPACING['xs']))
    for action_button in foot.winfo_children():
        action_button.configure(width=script_action_width,padding=SCRIPT_ACTION_PADDING)
    def on_modified(event=None):
        if event is not None and not input_box.edit_modified():return
        input_box.edit_modified(False)
        # 发送框的高度由实际换行数决定；长创意无需在一行小框里横向／纵向挤着看。
        input_box.after_idle(fit_composer)
        update_input_hint()
    def fit_composer(event=None):
        """仅按实际内容撑开输入框，避免点击空框触发布局反馈回路。"""
        if not input_box.winfo_exists():return
        try:
            logical_lines=int(input_box.index('end-1c').split('.')[0])
            # 空框只保留一行。旧逻辑在点击时按聊天框高度把 Text 放大到半屏，
            # 输入框、聊天框、画布各自的 Configure 又会重新测量对方，形成持续抖动。
            # 文字需要多行时才增长，并设上限以维持操作栏和文件表可见。
            lines=min(8,max(1,logical_lines,display_lines(input_box)))
            if int(input_box.cget('height'))!=lines:
                input_box.configure(height=lines)
                self.fit_content()
        except (tk.TclError,ValueError):pass
    def expand_composer_for_click(event=None):
        """空框点击只取得编辑焦点；高度只由真实输入内容决定。"""
        input_box.focus_set()
    def restore_composer_after_blur(event=None):
        # 不按焦点收缩：用户输入多行后切换控件，内容高度仍应保持可读。
        return None
    def focus_composer_from_hint(event=None):
        """提示层覆盖输入框时，也必须把点击交还给真正的编辑器。

        否则点击会落到 Label，Text 永远拿不到焦点，用户无法立即开始输入。
        """
        input_box.focus_set()
        expand_composer_for_click()
        # 在失焦/窗口尚未激活的一瞬间，focus_get() 可能仍不是 Text；点击本身
        # 已明确表达要编辑，因此直接撤掉提示，不能等待下一次焦点事件。
        stop_input_hint()
        return 'break'
    input_hint.bind('<Button-1>',focus_composer_from_hint,add='+')
    enter_hint.bind('<Button-1>',focus_composer_from_hint,add='+')
    input_box.bind('<Button-3>',self.open_idea_paste_menu,add='+')
    input_box.bind('<Button-1>',expand_composer_for_click,add='+')
    input_box.bind('<FocusIn>',update_input_hint,add='+')
    input_box.bind('<FocusOut>',restore_composer_after_blur,add='+')
    input_box.bind('<FocusOut>',update_input_hint,add='+')
    input_box.bind('<KeyRelease>',self.show_idea_reference_menu,add='+')
    def send_on_enter(event):
        if event.state & 0x1:return None  # Shift+Enter 保留换行
        self.safe(self.send_message)
        return 'break'
    input_box.bind('<Return>',send_on_enter,add='+')
    input_box.bind('<KP_Enter>',send_on_enter,add='+')
    input_box.bind('<<Modified>>',on_modified)
    box.bind('<Configure>',self.refit_bubbles,add='+')
    self.restore_idea_draft()
    update_input_hint()
    # 首绘只放示例气泡；真实历史与附件回填等布局稳定后再补，避免拖住 page.paint。
    self.show_example_bubble()
    self.defer_idea_page_updates()
    # 下载按钮初始即为禁用；判断历史回复是否可下载会递归扫描旧项目的
    # Markdown，不能占用“打开项目”的首帧。页面仍在当前代次时再补状态。
    page_generation=getattr(self,'_script_page_generation',0)+1
    self._script_page_generation=page_generation
    def refresh_download_state():
        if (page_generation==getattr(self,'_script_page_generation',0)
                and self.page_index==PAGE['script'] and self.root):
            self.update_script_download_button()
    script_box=ttk.Frame(self.content,padding=(SPACING['xs'],SPACING['xs']));script_box.pack(fill='x',expand=False,pady=SPACING['none'])
    self.script_box=script_box
    try:download_state_job=self.win.after(250,refresh_download_state)
    except tk.TclError:download_state_job=None
    def cancel_download_state(event=None):
        """页面已销毁时不再执行下载状态的后台刷新。"""
        if event is not None and getattr(event,'widget',None) is not script_box:
            return None
        if download_state_job is not None:
            try:self.win.after_cancel(download_state_job)
            except tk.TclError:pass
        return None
    script_box.bind('<Destroy>',cancel_download_state,add='+')
    # 四类文件合并成一张整宽的表（用户 R1776 要求）：只留一个勾选列（表头即全选），
    # 窄「类别」列标明归属，其余宽度全给文件名，尽量显示全名。行按类别分组、组内按修改时间。
    categories=(('setting','项目设定'),('outline','项目大纲'),('character','角色卡'),('script','项目剧本'))
    script_box.columnconfigure(0,weight=1);script_box.rowconfigure(0,weight=1)
    table=DataTable(script_box,columns=[('kind','类别',SCRIPT_KIND_COLUMN_WIDTH),('name','文件名',180)],
                    show='tree headings',height=1,selectmode='browse',style='Script.Treeview',
                    auto_hide_scrollbars=True,empty_text='',horizontal=False)
    table.grid(row=0,column=0,sticky='nsew')
    script_tree=table.tree
    configure_check_column(script_tree)
    script_tree.heading('#0',anchor='center')
    script_tree.heading('kind',text='类别',anchor='center')
    script_tree.heading('name',text='文件名',anchor='center')
    script_tree.column('kind',width=SCRIPT_KIND_COLUMN_WIDTH,minwidth=SCRIPT_KIND_COLUMN_WIDTH,stretch=False,anchor='center')
    script_tree.column('name',width=180,minwidth=100,stretch=True)
    script_row_details={}
    script_row_category={}
    self.script_file_tips=TreeRowTooltip(script_tree,lambda item:script_row_details.get(item,''))
    self.script_tree=script_tree
    self.script_row_category=script_row_category
    from responsive_ui import display_lines,font_linespace
    # 状态标记放在文件名前面：列窄时被截掉的是文件名尾巴，不是[已确认]/[待确认]。
    ttk.Style(script_tree).configure('Script.Treeview',font=SCRIPT_FILE_FONT)
    fit_row_height(script_tree, style='Script.Treeview')
    # 按当前各固定区的请求高度预留空间，避免把建页时的宽度/换行状态缓存下来。
    # 直接加固定兄弟控件，不用父容器减聊天框：后者在 Tk 几何传播中可能跨批次。
    talk_line=max(1,font_linespace(box,box.cget('font'),fallback=19))
    box_chrome=2*int(box.cget('pady'))+2
    page_fixed=0
    def measure_page_fixed():
        nonlocal page_fixed
        def packed_height(widget):
            pady=widget.pack_info().get('pady',0)
            pady=widget.tk.splitlist(pady) if isinstance(pady,(str,tuple)) else (pady,)
            pads=[widget.winfo_pixels(value) for value in pady]
            return widget.winfo_reqheight()+sum(pads)*(2 if len(pads)==1 else 1)
        page_fixed=sum(packed_height(child) for child in talk.pack_slaves() if child is not dialog)
        page_fixed+=sum(packed_height(child) for child in self.content.pack_slaves() if child is not talk)
    def fit_talk(event=None):
        """第 71 期任务 5／6：创意框摆几行＝「窗口还剩多少」「框里有多少字」「上限」三者取小。

        字少就矮下来，字多也不撑过头；下面那一行「发送」与文件框都先算好位置，
        于是窗口怎么缩，它们都还在可视区里。
        """
        if not box.winfo_exists():return
        # 拖动主窗口边框期间并进松手后的整页重排；切页、输入引起的重算照旧立即。
        if self._join_resize(self._layout_all,event):return
        viewport=int(self.canvas.winfo_height() or 0)
        if viewport<=1:return                      # 还没量出窗口尺寸：等下一拍
        try:
            measure_page_fixed()
            room=viewport-page_fixed-box_chrome
            floor=min(TALK_MIN_LINES,max(1,room//talk_line))
            cap=max(floor,min(TALK_MAX_LINES,room//talk_line))
            lines=max(floor,min(cap,display_lines(box,limit=cap)))
            if int(box.cget('height'))!=lines:
                box.configure(height=lines)
                # 交给已合并的空闲重排；同步递归扫描整页控件会与本次 Configure
                # 事件嵌套，造成鼠标停留/输入时的布局风暴。
                self.fit_content()

        except (tk.TclError,ValueError):pass
    self._fit_talk=fit_talk
    def fit_talk_container(event=None):
        if self._join_resize(self._layout_all,event):return
        fit_talk(event)
        # 动作栏换行或聊天请求高度变化后，容器完成几何传播才重新量画布。
        # 即使聊天行数没变也要收敛；固定画布自身不会收到请求高度变化事件。
        self.fit_content()
    talk.bind('<Configure>',fit_talk_container,add='+')
    # 框自己变宽变窄也要重算：建页面那一小会儿宽度还是 1 像素，折行数虚高，
    # 等真实宽度下来按文字行数收回去（不然会一直停在最大那一档）。
    box.bind('<Configure>',fit_talk,add='+')
    box.bind('<<Modified>>',lambda event=None:fit_talk(),add='+')
    self._fit_composer=fit_composer
    schedule_layout, cancel_layout_job = _build_layout_scheduler(self.win)
    self.win.bind('<Destroy>', cancel_layout_job, add='+')
    schedule_layout(fit_composer, measure_page_fixed, fit_talk)
    checked_scripts=set()
    def keep_script_headers_visible():
        """空列表也保留分类标题，表格高度仍按内容压缩。"""
        if not script_box.winfo_manager():
            script_box.pack(fill='x',expand=False,pady=SPACING['none'])
        schedule_layout(fit_composer, measure_page_fixed, fit_talk, self._fit_content_now)
    from writing_page_controller import ScriptListLoadController
    script_loader=ScriptListLoadController(category for category,_title in categories)
    script_load_job=None
    def cancel_script_load(event=None):
        """页面销毁时撤销尚未提交的目录批次。"""
        nonlocal script_load_job
        if event is not None and getattr(event,'widget',None) is not script_box:return None
        script_loader.invalidate()
        if script_load_job is not None:
            try:self.win.after_cancel(script_load_job)
            except tk.TclError:pass
            script_load_job=None
        return None
    script_box.bind('<Destroy>',cancel_script_load,add='+')
    def fill_script_list():
        """渐进加载剧本文件表；新刷新或页面销毁会使旧批次失效。"""
        nonlocal script_load_job
        from script_workspace_service import iter_script_document_rows
        from writing_api import preparation_file_labels
        file_labels=preparation_file_labels(self.root)
        generation=script_loader.start(iter_script_document_rows(self.root))
        if script_load_job is not None:
            try:self.win.after_cancel(script_load_job)
            except tk.TclError:pass
            script_load_job=None
        script_tree.delete(*script_tree.get_children())
        script_row_details.clear()
        script_row_category.clear()
        # 首批文件尚未扫描完成时也必须保留三列表的列头。此前这里先隐藏
        # ``script_box``，慢目录扫描期间“项目设定／项目大纲／项目剧本”会完全
        # 消失；空列表与加载完成后也保留标题。
        keep_script_headers_visible()
        def alive():
            return script_loader.is_current(generation) and script_tree.winfo_exists()
        def finish():
            """按修改时间恢复既有排序；每个空闲批次只调整有限条目。"""
            order=[(category,iter(rows)) for category,rows in script_loader.ordered_rows().items()]
            def place():
                nonlocal script_load_job
                if not alive():return
                moved=0
                while order and moved<24:
                    category,rows=order[0]
                    try:row=next(rows)
                    except StopIteration:
                        order.pop(0);continue
                    script_tree.move(row.item_id,'','end')
                    moved+=1
                if order:
                    script_load_job=self.win.after_idle(place)
                    return
                live=script_loader.item_ids()
                checked_scripts.intersection_update(live)
                script_tree.configure(height=max(1,min(SCRIPT_FILE_MAX_ROWS,len(script_tree.get_children()))))
                script_check.refresh_header()
                keep_script_headers_visible();script_load_job=None
            place()
        def load_batch():
            nonlocal script_load_job
            if not alive():return
            rows,finished=script_loader.take_batch(24)
            for row in rows:
                modified=time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(row.modified_at))
                script_row_details[row.item_id]=row.name+'\n修改时间：'+modified
                label=file_labels.get(str(Path(row.item_id).resolve()),file_labels.get(row.category,''))
                script_row_category[row.item_id]=row.category
                script_tree.insert('', 'end', iid=row.item_id, text='',
                    image=self.win._tick_images[int(row.item_id in checked_scripts)],
                    values=(SCRIPT_KIND_LABELS.get(row.category,''),('['+label+'] ' if label else '')+row.name))
            if finished:
                finish();return
            keep_script_headers_visible()
            script_load_job=self.win.after_idle(load_batch)
        # 初次目录扫描必须越过首帧的 event loop；after_idle 会在同一次
        # update() 内被追着执行，等同又把 rglob 塞回启动回调。
        script_load_job=self.win.after(250,load_batch)
    self.refresh_script_list=fill_script_list
    def current_script_tree():
        return script_tree if script_tree.selection() else None
    def open_script_file(event=None):
        # 表头（分类名/全选）与列宽分隔线也在 Treeview 的 <Double-1> 范围内；
        # 此时 selection() 仍保留着上次勾选/高亮的行，不能直接拿它打开文件。
        # 鼠标双击只认落点所在的行；键盘 Enter 仍打开当前高亮行。
        event_type=getattr(getattr(event,'type',None),'name',getattr(event,'type',None))
        if event_type=='ButtonPress':
            tree=event.widget
            if not isinstance(tree,ttk.Treeview):return
            row=row_toggle_target(tree,event.x,event.y)
        else:
            tree=current_script_tree()
            selected=tree.selection() if tree else ()
            row=selected[0] if selected else ''
        if not row:return
        path=Path(row)
        if path.is_file():open_path(path)
    self.open_script_file=open_script_file
    script_tree.bind('<Double-1>',open_script_file)
    script_tree.bind('<Return>',open_script_file)
    def selected_script():
        tree=current_script_tree()
        selected=tree.selection() if tree else ()
        if not selected:raise ValueError('请先选择剧本文件')
        from script_workspace_service import selected_script_paths
        return selected_script_paths(self.root,[selected[0]])[0]
    def selected_scripts():
        """批量删除只认勾选项；未勾选时将当前高亮行视作单项操作。"""
        all_items=list(script_tree.get_children())
        tree=current_script_tree()
        active=tree.selection() if tree else ()
        from script_workspace_service import script_deletion_selection
        return script_deletion_selection(self.root,all_items,checked_scripts,active)
    def selection_changed():
        count=len(checked_scripts)
        self.status.set('已勾选 '+str(count)+' 份剧本文件' if count else '已取消剧本文件勾选')
    script_check=CheckboxColumn(script_tree,self.win._tick_images,
                                lambda item:item in checked_scripts,
                                lambda item,value:checked_scripts.add(item) if value else checked_scripts.discard(item),
                                selection_changed)
    script_tree.heading('#0',command=script_check.toggle_all)
    fill_script_list()
    bind_row_toggle(script_tree,script_check.toggle)
    def rename_script():
        path=selected_script()
        new=ask_string(self.win,'重命名文件','新文件名：',initialvalue=path.name)
        if not new:return
        from script_workspace_service import rename_script_document
        result=rename_script_document(self.root,path,new)
        if not result.ok:raise ValueError(result.reason)
        dest=result.data
        if dest==path:return
        fill_script_list();self.status.set('已重命名：'+dest.name)
    def confirmed_note(paths):
        # 删掉已确认阶段文件会让剧本准备的确认失效，删前点明。
        import writing_api
        confirmed=writing_api.confirmed_preparation_files(self.root)
        hits=[confirmed[p.resolve()]+'：'+p.name for p in paths if p.resolve() in confirmed]
        if not hits:return ''
        return '\n\n注意：以下是剧本准备已确认的阶段文件，删除后该阶段确认失效，需要恢复或重新确认才能继续：\n'+'\n'.join(hits)
    def delete_script():
        path=selected_script()
        all_files=list(script_tree.get_children())
        if len(all_files)==1:
            if not confirm_project_removal_from_last_script(self.win,[path.name]):return
        else:
            prompt=f'确定将 {path.name} 移入项目回收站吗？\n\n可在对应页面恢复最近删除。'+confirmed_note([path])
            title='移入回收站'
            if not confirm(self.win,title,prompt,dangerous=True):return
        if len(all_files)==1:
            item=next((dict(p) for p in self.projects.info['projects'] if p['path']==str(self.root)),None)
            if item is None:raise ValueError('当前项目未登记，无法安全删除')
            self.delete_project(item,confirmed=True);return
        from storage_maintenance import recycle_paths
        if not recycle_paths(self.root,[path],'删除项目剧本'):
            raise OSError('文件未能移入回收站，请刷新后重试')
        fill_script_list();self.status.set('已移入回收站：'+path.name)
    def delete_selected_scripts():
        selection=selected_scripts()
        paths=list(selection.paths)
        names='\n'.join(path.name for path in paths)
        if selection.deletes_all:
            if not confirm_project_removal_from_last_script(self.win,[path.name for path in paths]):return
        else:
            title='移入回收站'
            prompt='确定将选中的 '+str(len(paths))+' 份剧本文件移入项目回收站吗？\n\n'+names+'\n\n可在对应页面恢复最近删除。'+confirmed_note(paths)
            if not confirm(self.win,title,prompt,dangerous=True):return
        if selection.deletes_all:
            item=next((dict(p) for p in self.projects.info['projects'] if p['path']==str(self.root)),None)
            if item is None:raise ValueError('当前项目未登记，无法安全删除')
            self.delete_project(item,confirmed=True);return
        from storage_maintenance import recycle_paths
        recycled=recycle_paths(self.root,paths,'批量删除项目剧本')
        if len(recycled)!=len(paths):
            raise OSError('部分文件未能移入回收站，请刷新后重试')
        fill_script_list()
        self.status.set('已移入回收站 '+str(len(paths))+' 份剧本文件')
    def adopt_script():
        from stage_execution_service import adopt_natural_script
        adopted=adopt_natural_script(self.root,selected_script())
        fill_script_list()
        self.status.set('已采用自然剧本：'+adopted.name+'；后续结构化使用此版本')
    def restart_preparation(stage):
        _restart_preparation(self,stage,fill_script_list)
    def confirm_document(stage):
        """把用户改过的当前文件设为该阶段定稿；之后各阶段的定稿会失效。"""
        path=selected_script()
        from stage_execution_service import confirm_writing_preparation
        if not confirm(self.win,'设为'+stage+'定稿',
                       '把这份文件设为「'+stage+'」的定稿？\n\n'+path.name+
                       '\n\n以文件当前内容为准；「'+stage+'」之后已定稿的阶段需要重新确认。'):
            return
        invalidated=confirm_writing_preparation(self.root,stage,path)
        fill_script_list()
        self.status.set('已把'+path.name+'设为「'+stage+'」定稿'+
                        ('；「'+'」「'.join(invalidated)+'」需要重新确认' if invalidated else ''))
    def script_menu(tree,event):
        row=tree.identify_row(event.y)
        if not row:return
        tree.selection_set(row)
        menu=ContextMenu(self.win)
        # 第 46 期第 1 条：内容框的右键一律是「查看／…／删除」这一套，剧本表原来只有改名与删除。
        menu.command('查看',lambda:self.safe(open_script_file))
        menu.command('重命名',lambda:self.safe(rename_script))
        # 合并表后按所点行的类别给阶段动作，不再按「点的是哪一列表」判断。
        category=script_row_category.get(row,'script')
        if category=='script':
            menu.command('采用此剧本',lambda:self.safe(adopt_script))
        else:
            stages={'setting':'项目设定','outline':'剧本大纲','character':'角色卡'}
            stage=stages[category]
            menu.command('重写'+stage,lambda:self.safe(lambda:restart_preparation(stage)))
            menu.command('放弃重写，恢复原稿',lambda:self.safe(lambda:restart_preparation(None)))
            menu.command('设为'+stage+'定稿',lambda:self.safe(lambda:confirm_document(stage)))
        menu.command('删除',lambda:self.safe(delete_script))
        return menu.popup(event)
    script_tree.bind('<Button-3>',lambda event:script_menu(script_tree,event))
'''

PAGES = {'writing': 'script'}
OWNER = 'WritingPageMixin'



TARGET = getattr(module, OWNER) if OWNER else module


def _open_app(tk, td):
    import test_ui_edges
    from desktop import Desktop
    from local_video import open_studio
    win = tk.Tk()
    win.withdraw()
    app = Path(td) / 'app'
    app.mkdir()
    desktop = Desktop(win, root=app)
    desktop.startup_controller.cancel()
    desktop.root = test_ui_edges.make_populated_project(td)
    desktop.studio = open_studio(desktop.root)
    freeze_times(desktop.root)
    return win, desktop


class WritingPageEquivalence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter
            root = tkinter.Tk()
            root.destroy()
            cls.tk = tkinter
        except Exception:
            cls.tk = None

    def setUp(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        self.namespace = dict(vars(module))
        exec(compile(LEGACY_WRITING, 'legacy_writing', 'exec'), self.namespace)

    def _session(self, name, impl):
        page = pet_state.PAGE_OF[PAGES[name]]
        # 路径要在两次运行里逐字相同（请求宽度随字形变化），所以用按进程号固定的目录，而不是随机临时目录
        td = Path(tempfile.gettempdir()) / ('drama_page_diff_%d' % os.getpid())
        shutil.rmtree(td, ignore_errors=True)
        td.mkdir(parents=True)
        try:
            win, desktop = _open_app(self.tk, td)
            roots = sorted({str(td), Path(td).as_posix(), str(Path(td).resolve()), Path(td).resolve().as_posix()},
                           key=len, reverse=True)
            steps = []
            try:
                with mock.patch.object(TARGET, name, impl):
                    show_catalog_page_ready(desktop, page)
                    poke(desktop, name + '#1', steps, roots)
                    desktop.go_page(pet_state.PAGE_OF['assets'])
                    pump(win, 0.1)
                    steps.append(('left', snapshot(desktop.content, roots)))
                    show_catalog_page_ready(desktop, page)
                    poke(desktop, name + '#2', steps, roots)
            finally:
                desktop.cancel_timers()
                win.destroy()
            return steps
        finally:
            shutil.rmtree(td, ignore_errors=True)

    def test_writing_is_identical(self):
        self._session('writing', self.namespace['_legacy_writing'])   # 预热：进程里第一次建窗的布局与之后不同，先跑一遍丢掉
        old = self._session('writing', self.namespace['_legacy_writing'])
        new = self._session('writing', getattr(TARGET, 'writing'))
        self.assertEqual(len(new), len(old))
        for a, b in zip(new, old):
            self.assertEqual(a, b, a[0])
        widgets = max(len(step[1]) if isinstance(step[1], list) else 0 for step in new)
        self.assertGreater(widgets, 15)   # 对照不能是空对空：页面真的建出了一棵控件树


if __name__ == '__main__':
    unittest.main()
