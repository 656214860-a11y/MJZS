"""剧本准备页（``Desktop.writing``）的页面构建。

从 ``desktop.Desktop`` 原样迁出（R1499 拆分步骤 3，一页一轮）：方法体未改，``self`` 语义不变，
``Desktop`` 通过继承 ``WritingPageMixin`` 获得。``confirm``／``open_path``／``ContextMenu`` 等外部 UI 能力
（R1988 J2）改由实例的 ``writing_page_services`` 提供，默认服务在 ``Desktop`` 组合入口按调用时取 ``desktop`` 模块的
当前值，测试按 ``desktop.<名字>`` 打补丁照常生效；本模块不再读取 ``desktop_page_support`` 的全局宿主。
"""
import pet_state
from dataclasses import dataclass
from typing import Callable
import time
import app_logging
import project_stages
import os
import tkinter as tk
import ui_plugin_registry
from pathlib import Path
from responsive_ui import CheckboxColumn, FlowBar, bind_row_toggle, configure_check_column, fit_row_height, row_toggle_target
from tkinter import ttk
from ui_tokens import BUTTON_GAP_TIGHT, CHAR_WIDTH, COLORS, FONTS, ICON_ADD, ICON_MICROPHONE, ICON_SEND, SCRIPT_ACTION_WIDTH, SCRIPT_FILE_FONT, SCRIPT_FILE_MAX_ROWS, SPACING
from desktop_file_card import TreeRowCard, script_row_card
from ui_widgets import Card, DataTable, EllipsisLabel, PrimaryButton, SecondaryButton, TextArea, Tooltip, ask_string

PAGE = pet_state.PAGE_OF

# 第 71 期任务 5／6：剧本准备页的创意框摆几行——窗口再矮也留 TALK_MIN_LINES 行，
# 字再多、窗口再高也不超过 TALK_MAX_LINES 行（一次铺满半页纸就不好操作了）；
TALK_MIN_LINES=6
TALK_MAX_LINES=15


def _build_layout_scheduler(win):
    """页面刚建好时的两次尺寸修正调度器。

    尺寸修正要登记任务 ID：测试或用户快速关闭项目时，未执行的匿名 after_idle
    回调会在 Tcl 删除窗口后报 ``invalid command name``。返回 (schedule_layout,
    cancel_layout_job) 两个闭包；cancel_layout_job 需绑定到窗口 <Destroy>。
    """
    layout_job = None

    def cancel_layout_job(event=None):
        nonlocal layout_job
        if event is not None and getattr(event, 'widget', None) is not win:
            return None
        job, layout_job = layout_job, None
        if job is not None:
            try:
                win.after_cancel(job)
            except tk.TclError:
                pass
        return None

    def schedule_layout(*callbacks):
        nonlocal layout_job
        cancel_layout_job()
        pending = iter(callbacks)

        def run():
            nonlocal layout_job
            layout_job = None
            callback = next(pending, None)
            if callback is None:
                return None
            try:
                callback()
                # 先让 Tk 应用上一项的请求尺寸，再测量固定空间。
                layout_job = win.after_idle(run)
            except tk.TclError:
                return None
            return None

        try:
            layout_job = win.after_idle(run)
        except tk.TclError:
            layout_job = None
        return layout_job

    return schedule_layout, cancel_layout_job


def _restart_preparation(host, stage, refresh):
    """右键重写：API 模型写重写记录；桌面／命令行模型改为填入可识别的发送指令。"""
    import writing_api
    from stage_execution_service import restart_writing_preparation
    if stage and not writing_api.selected_model(host.root)[0]:
        command = '重新生成' + stage
        box = getattr(host, 'idea_input', None)
        if box is None or not box.winfo_exists():
            raise ValueError('当前页面未找到剧本准备输入框')
        current = box.get('1.0', 'end-1c')
        if current.split('\n', 1)[0].strip() != command:
            box.delete('1.0', 'end')
            box.insert('1.0', command + ('\n' + current if current else ''))
        box.focus_set()
        host.status.set('已在输入框填入「' + command + '」：可在下一行补充修改要求，再点发送')
        return
    restart_writing_preparation(host.root, stage)
    refresh()
    host.status.set(('开始重写' + stage + '：请发送创作要求，新稿定稿前原稿照常可用')
                    if stage else '已放弃重写，恢复原稿')


@dataclass(frozen=True)
class WritingPageServices:
    """剧本准备页的外部 UI 能力；由组合入口提供，不携带全局宿主（R1606 模式，J2）。"""
    open_path: Callable
    context_menu: Callable
    confirm: Callable
    confirm_project_removal: Callable


class WritingPageMixin:
    """Desktop 的剧本准备页构建（见模块说明）。"""
    def writing(self):
        return _WritingPage(self).build()

    def build_script_quality_buttons(self, foot):
        """页脚右侧那组「质检／采风」。创建顺序就是动作栏顺序，调用位置不能挪到「下载文件」之后。"""
        SecondaryButton(foot,text='查看质检报告',command=lambda:self.safe(self.open_script_quality)).pack(side='right')
        SecondaryButton(foot,text='质检目录',command=lambda:self.safe(lambda:self.open_script_quality(folder=True))).pack(side='right')
        self.recon_button=SecondaryButton(foot,text='采风',command=lambda:self.safe(self.collect_recon))
        self.recon_button.pack(side='right',padx=(SPACING['none'],SPACING['xs']))

    def collect_recon(self):
        """采集对标情报：素材来源为③④时把公开情报抓回项目，落《对标情报卡》。

        页面只做「查素材来源 → 问剧名 → 写请求 → 交给后台」，不联网、不写卡片：
        检索与抓取在 L2 `recon_service`，网络在 L1 `model_pool`。
        """
        import recon_service, stage_config, skill_tools
        project = self.root
        if not project:
            return self.status.set('先选项目，再采集对标情报')
        source = str(stage_config.workflow_lock(project).get('material_source') or '')
        if source not in recon_service.MATERIAL_SOURCES:
            self.notifier.notify('当前素材来源是「%s」。先在阶段配置把「素材来源」选成「对标爆款」或「热点速成」，再来采集。'
                                 % (source or '未选'), title='采集对标情报')
            return self.status.set('采集对标情报：素材来源不符（%s）' % (source or '未选'))
        name = ask_string(self.win, '采集对标情报',
                          '对标剧名（填剧名＝对标这一部；留空＝按简报里的题材找方向）：')
        if name is None:
            return self.status.set('已取消采集')
        values = {'material_source': source}
        if name.strip():
            values.update({'name': name.strip(), 'question': '这部剧怎么成的'})
        recon_service.save_request(project, values)
        context = {'project': str(project), 'material_source': source}

        def work():
            try:
                return skill_tools.call('recon.card', context)
            except skill_tools.ToolNeedsInput as exc:
                return {'ok': False, 'needs': str(exc)}
        self.status.set('正在采集公开情报（联网检索，约十几秒）…')
        self.async_(work, self.recon_done, label='采集对标情报')

    def recon_done(self, result):
        """采风结果落状态栏：来源数、未查到、机检待处理都如实说，不吞也不美化。"""
        result = result or {}
        if result.get('needs'):
            return self.status.set('采风需要先给出对标对象：' + str(result['needs']))
        if result.get('skipped'):
            return self.status.set(str(result.get('reason') or '未采集'))
        text = '采风完成：%s 个来源' % (result.get('sources') or 0)
        missing = result.get('not_found') or []
        if missing:
            text += '，还有没查到的 %d 条' % len(missing)
        problems = result.get('problems') or []
        if problems:
            text += '，机检待处理 %d 条' % len(problems)
        return self.status.set(text + '；卡片在 01剧本准备/input/recon_card.json')


class _WritingPage:
    """剧本准备页（从 WritingPageMixin.writing 的闭包原样改写成类，R1817）：共享的局部变量成了实例属性，嵌套函数成了方法；原来的 self（桌面主窗）改叫 page。"""
    def __init__(self, page):
        self.page = page

    def build(self):
        from script_workspace_service import ensure_script_workspace
        result=ensure_script_workspace(self.page.root)
        if not result.ok:raise ValueError(result.reason)
        # 第 69 期任务 4：原来第一行那句「在下面的对话框写想法…」删掉——页面自己会说清怎么走。
        brief, foot = self._build_composer()
        self._build_dialog(brief, foot)
        self.input_box.bind('<Button-3>',self.page.open_idea_paste_menu,add='+')
        self.input_box.bind('<Button-1>',self.expand_composer_for_click,add='+')
        self.input_box.bind('<FocusIn>',self.update_input_hint,add='+')
        self.input_box.bind('<FocusOut>',self.restore_composer_after_blur,add='+')
        self.input_box.bind('<FocusOut>',self.update_input_hint,add='+')
        self.input_box.bind('<KeyRelease>',self.page.show_idea_reference_menu,add='+')
        self.input_box.bind('<Return>',self.send_on_enter,add='+')
        self.input_box.bind('<KP_Enter>',self.send_on_enter,add='+')
        self.input_box.bind('<<Modified>>',self.on_modified)
        self.box.bind('<Configure>',self.page.refit_bubbles,add='+')
        self.page.restore_idea_draft()
        self.update_input_hint()
        # 首绘只放示例气泡；真实历史与附件回填等布局稳定后再补，避免拖住 page.paint。
        self.page.show_example_bubble()
        self.page.defer_idea_page_updates()
        # 下载按钮初始即为禁用；判断历史回复是否可下载会递归扫描旧项目的
        # Markdown，不能占用“打开项目”的首帧。页面仍在当前代次时再补状态。
        self.page_generation=getattr(self.page,'_script_page_generation',0)+1
        self.page._script_page_generation=self.page_generation
        self.script_box=ttk.Frame(self.page.content,padding=(SPACING['xs'],SPACING['xs']));self.script_box.pack(fill='x',expand=False,pady=SPACING['none'])
        self.page.script_box=self.script_box
        try:self.download_state_job=self.page.win.after(250,self.refresh_download_state)
        except tk.TclError:self.download_state_job=None
        self.script_box.bind('<Destroy>',self.cancel_download_state,add='+')
        # 四类文件并排成四列小表（用户 R1862 要求复原）：合成一张整宽表时只有一列文件名，
        # 横向大片留白、纵向却越排越高。每列表头即分类名，各自一个勾选列，组内按修改时间。
        categories=(('setting','项目设定'),('outline','项目大纲'),('character','角色卡'),('script','项目剧本'))
        self.script_box.columnconfigure(0,weight=1);self.script_box.rowconfigure(0,weight=1)
        lists=ttk.Frame(self.script_box);lists.grid(row=0,column=0,sticky='nsew')
        self.script_trees={}
        self.script_row_details={}
        self.script_row_category={}
        tips=lambda item:self.script_row_details.get(item,'')
        self.page.script_file_tips={}
        for column,(category,title) in enumerate(categories):
            lists.columnconfigure(column,weight=1,uniform='script-files')
            table=DataTable(lists,columns=[('name',title,180)],show='tree headings',height=1,
                            selectmode='browse',style='Script.Treeview',auto_hide_scrollbars=True,
                            empty_text='',horizontal=False)
            tree=table.tree
            configure_check_column(tree)
            tree.heading('#0',anchor='center')
            tree.heading('name',text=title,anchor='center')
            tree.column('name',width=SPACING['sm'] * 23,minwidth=100,stretch=True)
            self.page.script_file_tips[category]=TreeRowCard(tree,tips)
            last=column==len(categories)-1
            table.grid(row=0,column=column,sticky='nsew',padx=SPACING['none'] if last else (SPACING['none'],SPACING['xs']))
            self.script_trees[category]=tree
        self.page.script_trees=self.script_trees
        # 测距与样式只需任取一张；旧的外部访问 script_tree 指向「项目剧本」这一列。
        self.script_tree=self.script_trees['script']
        self.page.script_tree=self.script_tree
        self.page.script_row_category=self.script_row_category
        from responsive_ui import display_lines,font_linespace
        self.display_lines = display_lines
        # 状态标记放在文件名前面：列窄时被截掉的是文件名尾巴，不是[已确认]/[待确认]。
        ttk.Style(self.script_tree).configure('Script.Treeview',font=SCRIPT_FILE_FONT)
        fit_row_height(self.script_tree, style='Script.Treeview')
        # 按当前各固定区的请求高度预留空间，避免把建页时的宽度/换行状态缓存下来。
        # 直接加固定兄弟控件，不用父容器减聊天框：后者在 Tk 几何传播中可能跨批次。
        self.talk_line=max(1,font_linespace(self.box,self.box.cget('font'),fallback=19))
        self.box_chrome=2*int(self.box.cget('pady'))+2
        self.page_fixed=0
        self.page._fit_talk=self.fit_talk
        self.talk.bind('<Configure>',self.fit_talk_container,add='+')
        # 框自己变宽变窄也要重算：建页面那一小会儿宽度还是 1 像素，折行数虚高，
        # 等真实宽度下来按文字行数收回去（不然会一直停在最大那一档）。
        self.box.bind('<Configure>',self.fit_talk,add='+')
        self.box.bind('<<Modified>>',lambda event=None:self.fit_talk(),add='+')
        self.page._fit_composer=self.fit_composer
        self.schedule_layout, cancel_layout_job = _build_layout_scheduler(self.page.win)
        self.page.win.bind('<Destroy>', cancel_layout_job, add='+')
        self.schedule_layout(self.fit_composer, self.measure_page_fixed, self.fit_talk)
        self.checked_scripts=set()
        from writing_page_controller import ScriptListLoadController
        self.script_loader=ScriptListLoadController(category for category,_title in categories)
        self.script_load_job=None
        self.script_box.bind('<Destroy>',self.cancel_script_load,add='+')
        self.page.refresh_script_list=self.fill_script_list
        self.page.open_script_file=self.open_script_file
        self.script_checks={}
        for tree in self.script_trees.values():
            tree.bind('<Double-1>',self.open_script_file)
            tree.bind('<Return>',self.open_script_file)
            tree.bind('<<TreeviewSelect>>',lambda event,tree=tree:self.keep_one_selection(tree),add='+')
        for category,tree in self.script_trees.items():
            check=CheckboxColumn(tree,self.page.win._tick_images,
                                 lambda item:item in self.checked_scripts,
                                 lambda item,value:self.checked_scripts.add(item) if value else self.checked_scripts.discard(item),
                                 self.selection_changed)
            tree.heading('#0',command=check.toggle_all)
            self.script_checks[category]=check
        self.fill_script_list()
        for category,tree in self.script_trees.items():
            bind_row_toggle(tree,self.script_checks[category].toggle)
            tree.bind('<Button-3>',lambda event,tree=tree:self.script_menu(tree,event))

    def _build_composer(self):
        """上半区：阶段标题、文件表、想法输入框与附件区。"""
        import idea_chat
        # 先使用不扫描目录的默认路径；历史创意文件由页面建好后在后台发现。
        brief=idea_chat.default_brief_document(self.page.idea_chat_context())
        self.page.idea_template=self.page.idea_example()
        # 聊天记录与发送框分离：记录可滚动，发送框固定停在聊天区域底部。
        self.talk=ttk.Frame(self.page.content,style='Box.TFrame',padding=(SPACING['xs'],SPACING['none']))
        # 标题、聊天框与左侧内容起点同高；不在标题下额外留出一档空白。
        self.talk.pack(fill='both',expand=True,pady=SPACING['none'])
        # 第 69 期任务 2：「发送」挪到创意框左下角；第 69 期任务 3：文件操作挪到右下角。
        # 第 71 期任务 5：这一行先摆下来（pack 先给谁算尺寸，谁就不会被挤掉）——窗口缩小时
        # 收的是上面的创意框，那颗「发送」永远留在看得见的地方。
        # 动作栏与其余制作阶段共用可换行布局。普通 pack 的左右两组按钮会在窗口
        # 变窄时互相挤压，最后把“删除剧本”裁成一个字；FlowBar 会按可用宽度分行，
        # 每颗按钮始终保留自己的完整文字宽度。
        # 用量与会话说明合成页面最底部的单行状态栏：不换行、放不下就截断，悬停看全文，
        # 不再夹在提示与输入框之间把聊天区往上挤。
        status_row=ttk.Frame(self.talk);status_row.pack(side='bottom',fill='x',pady=SPACING['none'])
        status_row.columnconfigure(0,weight=1,uniform='status-summary')
        status_row.columnconfigure(2,weight=2,uniform='status-summary')
        self.page.idea_usage_label = EllipsisLabel(status_row, text='本模型暂无用量记录', style='Muted.TLabel')
        self.page.idea_usage_label.grid(row=0,column=0,sticky='ew')
        self.page.idea_usage_tip = self.page.idea_usage_label.tooltip
        ttk.Label(status_row, text=' · ', style='Muted.TLabel').grid(row=0,column=1)
        self.page.idea_session_label = EllipsisLabel(status_row, text='', style='Muted.TLabel')
        self.page.idea_session_label.grid(row=0,column=2,sticky='ew')
        self.page.idea_session_tip = self.page.idea_session_label.tooltip
        foot=FlowBar(self.talk);foot.pack(side='bottom',fill='x',pady=SPACING['none'])
        # 输入框与操作栏保留极小缓冲带，视觉仍紧凑，同时避免鼠标落点贴边误触发送。
        composer=ttk.Frame(self.talk);composer.pack(side='bottom',fill='x',pady=(SPACING['none'],SPACING['xs']))
        # 仿 Claude Code 桌面版：附件卡片、输入区、「+」上传与发送／终止都收在同一个圆角框里。
        frame=Card(composer,padding=(SPACING['sm'],SPACING['xs']));frame.pack(fill='x')
        self.page.idea_composer_frame=frame
        # 附件卡片行：有附件才 pack 到输入区上方，没有附件不占行。
        self.page.idea_uploaded_panel=FlowBar(frame,style='Composer.TFrame')
        self.input_box=TextArea(frame,bg=COLORS['background_card'],fg=COLORS['text_primary'],insertbackground=COLORS['primary'],height=1,wrap='word',
                          font=FONTS['body'],relief='flat',bd=0,highlightthickness=0,padx=SPACING['xs'],pady=SPACING['xs'],undo=True)
        self.input_box.pack(side='top',fill='x')
        input_row=ttk.Frame(frame,style='Composer.TFrame');input_row.pack(side='top',fill='x')
        attach_button=SecondaryButton(input_row,text=ICON_ADD,width=CHAR_WIDTH['xs'],style='Tokens.Composer.Icon.TButton',
                                 command=lambda:self.page.safe(self.page.choose_idea_attachments))
        attach_button.pack(side='left')
        Tooltip(attach_button,'上传附件')
        if os.name=='nt':
            voice_button=SecondaryButton(input_row,text=ICON_MICROPHONE,width=CHAR_WIDTH['xs'],style='Tokens.Composer.Icon.TButton',
                                         command=lambda:self.page.safe(self.start_voice_input))
            voice_button.pack(side='left',padx=(SPACING['xs'],SPACING['none']))
            Tooltip(voice_button,'语音输入（Win+H）：说话即自动写入输入框')
            self.page.idea_voice_button=voice_button
        submit_button=SecondaryButton(input_row,text=ICON_SEND,width=CHAR_WIDTH['xs'],style='Tokens.Composer.Send.TButton',
                                 command=lambda:self.page.idea_send.invoke())
        submit_button.pack(side='right')
        Tooltip(submit_button,'Enter 发送；Shift+Enter 换行；运行中点击或按 Esc 终止')
        self.page.idea_submit=submit_button
        self.page.idea_attachment_button=attach_button
        self.page.idea_input_row=input_row
        # 附件明细（字数等）只作数据：卡片悬停提示与发送前校验都读它，不再单独占一行。
        self.page.idea_attachment_status=tk.StringVar(value='')
        self.input_hint=ttk.Label(frame,text='输入想法，Enter 发送，＋ 上传附件',style='Composer.Muted.TLabel')
        self.page.idea_input_hint=self.input_hint
        self.input_box.bind('<Destroy>',lambda event:self.stop_input_hint() if event.widget is self.input_box else None,add='+')
        self.page.shortcuts.bind(self.input_box, ('<Escape>',), self.interrupt_from_input,
                            scope='剧本准备·输入框', name='终止当前任务')
        return brief, foot

    def _build_dialog(self, brief, foot):
        """对话区：聊天记录框及其快捷键与右键菜单。"""
        self.dialog=ttk.Frame(self.talk);self.dialog.pack(side='top',fill='both',expand=True,pady=SPACING['none'])
        dialog_scroll=ttk.Scrollbar(self.dialog,orient='vertical')
        dialog_scroll.pack(side='right',fill='y')
        self.box=TextArea(self.dialog,bg=COLORS['background_card'],fg=COLORS['text_primary'],insertbackground=COLORS['primary'],
                    selectbackground=COLORS['primary'],inactiveselectbackground=COLORS['primary'],selectforeground=COLORS['background_card'],height=TALK_MIN_LINES,wrap='word',
                    font=FONTS['body'],relief='flat',padx=SPACING['md'],pady=SPACING['sm'],yscrollcommand=dialog_scroll.set)
        self.box.pack(side='left',fill='both',expand=True)
        dialog_scroll.configure(command=self.box.yview)
        self.page.brief_editor=(brief,self.input_box);self.page.brief_saved_text=''
        self.page.idea_log=self.box
        self.page.idea_scroll=dialog_scroll
        self.page.idea_input=self.input_box
        self.page.queue_initial_brief_document(self.input_box,brief)
        # 先让 Text 用当前布局命中鼠标位置，再在空闲时重算高度；同步重排会让选区偏到上一行。
        self.box.bind('<Button-1>',lambda event:self.box.after_idle(self.refit_talk),add='+')
        # 常态下可长按拖选并 Ctrl+C；单击进入编辑后，写入边界只限这条气泡的正文。
        self.page.shortcuts.bind(self.box, ('<Control-c>', '<Control-C>'), self.page.copy_selected_bubble_text,
                            scope='剧本准备·聊天记录', name='复制选中气泡文本')
        self.box.bind('<Button-3>',self.page.open_bubble_menu,add='+')
        self.box.bind('<ButtonPress-1>',self.page.guard_bubble_edit_pointer,add='+')
        self.box.bind('<B1-Motion>',self.page.guard_bubble_edit_pointer,add='+')
        self.box.bind('<B1-Motion>',self.page.track_bubble_click,add='+')
        self.box.bind('<ButtonRelease-1>',self.page.finish_bubble_click,add='+')
        self.box.bind('<KeyPress>',self.page.guard_bubble_edit_key,add='+')
        self.box.bind('<<Paste>>',self.page.guard_bubble_edit_key,add='+')
        self.box.bind('<FocusOut>',lambda event:self.page.finish_bubble_edit(),add='+')
        self.page.shortcuts.bind(self.box, ('<Control-Return>',), lambda event:self.page.finish_bubble_edit(),
                            scope='剧本准备·聊天记录', name='保存气泡编辑')
        self.page.shortcuts.bind(self.box, ('<Escape>',), lambda event:self.page.finish_bubble_edit(commit=False),
                            scope='剧本准备·聊天记录', name='取消气泡编辑')
        self.page.idea_row=foot
        # 输入框下方的动作统一为紧凑尺寸，避免长旧文案把聊天区挤窄。
        script_action_width=SCRIPT_ACTION_WIDTH
        send_button=PrimaryButton(foot,text='发送',width=script_action_width,
                               command=lambda:self.page.safe(self.page.send_message))
        send_button.pack(side='left',pady=SPACING['none']);self.page.idea_send=send_button
        # 剧本阶段的唯一配置入口贴着发送键：写完想法后就能直接调整模型／SKILL，
        # 不再在对话框上方额外占一行。
        # 阶段按钮属于首帧可交互核心。使用无配置读取的轻量入口，既保持“设置—
        # 中断”原有相邻顺序，也不再把 stage_config.synchronize 塞进建页回调。
        self.panel=ui_plugin_registry.module('skill_panel')
        self.holder={}
        self.page.stage_button=self.panel.stage_button_for(
            foot,lambda:self.panel.open_for_page(self.page,PAGE['script'],self.holder['button']))
        self.holder['button']=self.page.stage_button
        self.page.stage_button.pack(side='left',padx=(BUTTON_GAP_TIGHT,SPACING['none']),pady=SPACING['none'])
        refresh_button=SecondaryButton(foot,text='刷新',width=script_action_width,command=lambda:self.page.safe(self.page.refresh_script_workspace))
        refresh_button.pack(side='left',padx=(BUTTON_GAP_TIGHT,SPACING['none']));self.page.idea_refresh=refresh_button
        # 「删除」紧跟「刷新」：动作栏按子控件创建顺序排列，所以必须在这里创建，不能放到右侧那组。
        delete_button=SecondaryButton(foot,text='删除',width=script_action_width,command=lambda:self.page.safe(self.delete_selected_scripts))
        delete_button.pack(side='left',padx=(BUTTON_GAP_TIGHT,SPACING['none']))
        download_button=SecondaryButton(foot,text='下载文件',width=script_action_width,command=lambda:self.page.safe(self.page.download_script))
        download_button.state(['disabled']);self.page.idea_download=download_button
        SecondaryButton(foot,text='添加剧本',width=script_action_width,
                   command=lambda:self.page.safe(self.page.import_json)).pack(side='right')
        open_folder_button=SecondaryButton(foot,text='剧本目录',width=script_action_width,
                                      command=lambda:self.page.safe(lambda:self.page.open_folder(project_stages.writing(self.page.root))))
        open_folder_button.pack(side='right',padx=(SPACING['none'],SPACING['sm']));self.page.idea_open_folder=open_folder_button
        self.page.build_script_quality_buttons(foot)
        download_button.pack(side='right',padx=(SPACING['none'],BUTTON_GAP_TIGHT))
        for action_button in foot.winfo_children():
            # 不再单独压内边距：样式层的按下态内边距会覆盖控件级 padding，按下时按钮高度会回弹。
            action_button.configure(width=script_action_width)
        self.input_hint.bind('<Button-1>',self.focus_composer_from_hint,add='+')
        # 「中断」并入框内发送键：运行中切换为终止图标，由它统一同步状态。
        self.page.update_script_interrupt_button()

    def stop_input_hint(self):
        self.input_hint.place_forget()

    def update_input_hint(self, event=None):
        try:
            if not self.page.draft_text().strip() and self.input_box.focus_get() is not self.input_box:
                # Text 的 inside 边界已含文字内边距，避免再次累加 padx。
                self.input_hint.place(in_=self.input_box,x=SPACING['none'],rely=0.5,anchor='w')
            else:self.stop_input_hint()
        except tk.TclError:pass

    # 聊天区只读；窗口缩小时只收聊天记录区，底部发送框永远可见。
    def refit_talk(self, event=None):
        fit=getattr(self.page,'_fit_talk',None)
        if fit is None:return
        try:fit()
        except Exception:app_logging.swallowed()

    def on_modified(self, event=None):
        if event is not None and not self.input_box.edit_modified():return
        self.input_box.edit_modified(False)
        # 发送框的高度由实际换行数决定；长创意无需在一行小框里横向／纵向挤着看。
        self.input_box.after_idle(self.fit_composer)
        self.update_input_hint()

    def fit_composer(self, event=None):
        """仅按实际内容撑开输入框，避免点击空框触发布局反馈回路。"""
        if not self.input_box.winfo_exists():return
        try:
            logical_lines=int(self.input_box.index('end-1c').split('.')[0])
            # 空框只保留一行。旧逻辑在点击时按聊天框高度把 Text 放大到半屏，
            # 输入框、聊天框、画布各自的 Configure 又会重新测量对方，形成持续抖动。
            # 文字需要多行时才增长，并设上限以维持操作栏和文件表可见。
            lines=min(8,max(1,logical_lines,self.display_lines(self.input_box)))
            if int(self.input_box.cget('height'))!=lines:
                self.input_box.configure(height=lines)
                self.page.fit_content()
        except (tk.TclError,ValueError):pass

    def expand_composer_for_click(self, event=None):
        """空框点击只取得编辑焦点；高度只由真实输入内容决定。"""
        self.input_box.focus_set()

    def restore_composer_after_blur(self, event=None):
        # 不按焦点收缩：用户输入多行后切换控件，内容高度仍应保持可读。
        return None

    def focus_composer_from_hint(self, event=None):
        """提示层覆盖输入框时，也必须把点击交还给真正的编辑器。

            否则点击会落到 Label，Text 永远拿不到焦点，用户无法立即开始输入。
            """
        self.input_box.focus_set()
        self.expand_composer_for_click()
        # 在失焦/窗口尚未激活的一瞬间，focus_get() 可能仍不是 Text；点击本身
        # 已明确表达要编辑，因此直接撤掉提示，不能等待下一次焦点事件。
        self.stop_input_hint()
        return 'break'

    def start_voice_input(self):
        """REQ-S01-67：先把焦点放进输入框，再调起系统听写，文字才会落到这里。"""
        import platform_tools
        self.input_box.focus_force()
        reason=platform_tools.start_voice_typing()
        if reason:self.page.status.set('语音输入未能调起（%s）；可在输入框内手动按 Win+H。' % reason)
    def interrupt_from_input(self, event=None):
        """运行中在输入框按 Esc 等同点终止；空闲时不拦截，交给其他绑定。"""
        if not self.page.script_task_active():return None
        self.page.safe(self.page.interrupt_script_agent)
        return 'break'

    def send_on_enter(self, event):
        if event.state & 0x1:return None  # Shift+Enter 保留换行
        self.page.safe(self.page.send_message)
        return 'break'

    def refresh_download_state(self):
        if (self.page_generation==getattr(self.page,'_script_page_generation',0)
                and self.page.page_index==PAGE['script'] and self.page.root):
            self.page.update_script_download_button()

    def cancel_download_state(self, event=None):
        """页面已销毁时不再执行下载状态的后台刷新。"""
        if event is not None and getattr(event,'widget',None) is not self.script_box:
            return None
        if self.download_state_job is not None:
            try:self.page.win.after_cancel(self.download_state_job)
            except tk.TclError:pass
        return None

    def measure_page_fixed(self):
        def packed_height(widget):
            pady=widget.pack_info().get('pady',0)
            pady=widget.tk.splitlist(pady) if isinstance(pady,(str,tuple)) else (pady,)
            pads=[widget.winfo_pixels(value) for value in pady]
            return widget.winfo_reqheight()+sum(pads)*(2 if len(pads)==1 else 1)
        self.page_fixed=sum(packed_height(child) for child in self.talk.pack_slaves() if child is not self.dialog)
        self.page_fixed+=sum(packed_height(child) for child in self.page.content.pack_slaves() if child is not self.talk)

    def fit_talk(self, event=None):
        """第 71 期任务 5／6：创意框摆几行＝「窗口还剩多少」「框里有多少字」「上限」三者取小。

            字少就矮下来，字多也不撑过头；下面那一行「发送」与文件框都先算好位置，
            于是窗口怎么缩，它们都还在可视区里。
            """
        if not self.box.winfo_exists():return
        # 拖动主窗口边框期间并进松手后的整页重排；切页、输入引起的重算照旧立即。
        if self.page._join_resize(self.page._layout_all,event):return
        viewport=int(self.page.canvas.winfo_height() or 0)
        if viewport<=1:return                      # 还没量出窗口尺寸：等下一拍
        try:
            self.measure_page_fixed()
            room=viewport-self.page_fixed-self.box_chrome
            floor=min(TALK_MIN_LINES,max(1,room//self.talk_line))
            cap=max(floor,min(TALK_MAX_LINES,room//self.talk_line))
            lines=max(floor,min(cap,self.display_lines(self.box,limit=cap)))
            if int(self.box.cget('height'))!=lines:
                self.box.configure(height=lines)
                # 交给已合并的空闲重排；同步递归扫描整页控件会与本次 Configure
                # 事件嵌套，造成鼠标停留/输入时的布局风暴。
                self.page.fit_content()

        except (tk.TclError,ValueError):pass

    def fit_talk_container(self, event=None):
        if self.page._join_resize(self.page._layout_all,event):return
        self.fit_talk(event)
        # 动作栏换行或聊天请求高度变化后，容器完成几何传播才重新量画布。
        # 即使聊天行数没变也要收敛；固定画布自身不会收到请求高度变化事件。
        self.page.fit_content()

    def keep_script_headers_visible(self):
        """空列表也保留分类标题，表格高度仍按内容压缩。"""
        if not self.script_box.winfo_manager():
            self.script_box.pack(fill='x',expand=False,pady=SPACING['none'])
        self.schedule_layout(self.fit_composer, self.measure_page_fixed, self.fit_talk, self.page._fit_content_now)

    def cancel_script_load(self, event=None):
        """页面销毁时撤销尚未提交的目录批次。"""
        if event is not None and getattr(event,'widget',None) is not self.script_box:return None
        self.script_loader.invalidate()
        if self.script_load_job is not None:
            try:self.page.win.after_cancel(self.script_load_job)
            except tk.TclError:pass
            self.script_load_job=None
        return None

    def fill_script_list(self):
        """渐进加载剧本文件表；新刷新或页面销毁会使旧批次失效。"""
        from script_workspace_service import iter_script_document_rows
        from writing_api import preparation_file_labels
        file_labels=preparation_file_labels(self.page.root)
        generation=self.script_loader.start(iter_script_document_rows(self.page.root))
        if self.script_load_job is not None:
            try:self.page.win.after_cancel(self.script_load_job)
            except tk.TclError:pass
            self.script_load_job=None
        for tree in self.script_trees.values():
            tree.delete(*tree.get_children())
        self.script_row_details.clear()
        self.script_row_category.clear()
        # 首批文件尚未扫描完成时也必须保留三列表的列头。此前这里先隐藏
        # ``script_box``，慢目录扫描期间“项目设定／项目大纲／项目剧本”会完全
        # 消失；空列表与加载完成后也保留标题。
        self.keep_script_headers_visible()
        def alive():
            return self.script_loader.is_current(generation) and all(tree.winfo_exists() for tree in self.script_trees.values())
        def finish():
            """按修改时间恢复既有排序；每个空闲批次只调整有限条目。"""
            order=[(category,iter(rows)) for category,rows in self.script_loader.ordered_rows().items()]
            def place():
                if not alive():return
                moved=0
                while order and moved<24:
                    category,rows=order[0]
                    try:row=next(rows)
                    except StopIteration:
                        order.pop(0);continue
                    self.script_trees[category].move(row.item_id,'','end')
                    moved+=1
                if order:
                    self.script_load_job=self.page.win.after_idle(place)
                    return
                live=self.script_loader.item_ids()
                self.checked_scripts.intersection_update(live)
                for category,tree in self.script_trees.items():
                    tree.configure(height=max(1,min(SCRIPT_FILE_MAX_ROWS,len(tree.get_children()))))
                    self.script_checks[category].refresh_header()
                self.keep_script_headers_visible();self.script_load_job=None
            place()
        def load_batch():
            if not alive():return
            rows,finished=self.script_loader.take_batch(24)
            for row in rows:
                modified=time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(row.modified_at))
                label=file_labels.get(str(Path(row.item_id).resolve()),file_labels.get(row.category,''))
                self.script_row_details[row.item_id]=script_row_card(row,label,modified,self.page.root)
                self.script_row_category[row.item_id]=row.category
                self.script_trees[row.category].insert('', 'end', iid=row.item_id, text='',
                    image=self.page.win._tick_images[int(row.item_id in self.checked_scripts)],
                    values=(('['+label+'] ' if label else '')+row.name,))
            if finished:
                finish();return
            self.keep_script_headers_visible()
            self.script_load_job=self.page.win.after_idle(load_batch)
        # 初次目录扫描必须越过首帧的 event loop；after_idle 会在同一次
        # update() 内被追着执行，等同又把 rglob 塞回启动回调。
        self.script_load_job=self.page.win.after(250,load_batch)

    def all_script_items(self):
        return [item for tree in self.script_trees.values() for item in tree.get_children()]

    def current_script_tree(self):
        return next((tree for tree in self.script_trees.values() if tree.selection()),None)

    def keep_one_selection(self, tree):
        """四张表共用一个「当前行」：选中一张表的行时清掉其余表的高亮。"""
        if not tree.selection():return
        for other in self.script_trees.values():
            if other is not tree:other.selection_remove(other.selection())

    def open_script_file(self, event=None):
        # 表头（分类名/全选）与列宽分隔线也在 Treeview 的 <Double-1> 范围内；
        # 此时 selection() 仍保留着上次勾选/高亮的行，不能直接拿它打开文件。
        # 鼠标双击只认落点所在的行；键盘 Enter 仍打开当前高亮行。
        event_type=getattr(getattr(event,'type',None),'name',getattr(event,'type',None))
        if event_type=='ButtonPress':
            tree=event.widget
            if not isinstance(tree,ttk.Treeview):return
            row=row_toggle_target(tree,event.x,event.y)
        else:
            tree=self.current_script_tree()
            selected=tree.selection() if tree else ()
            row=selected[0] if selected else ''
        if not row:return
        path=Path(row)
        if path.is_file():self.page.writing_page_services.open_path(path)

    def selected_script(self):
        tree=self.current_script_tree()
        selected=tree.selection() if tree else ()
        if not selected:raise ValueError('请先选择剧本文件')
        from script_workspace_service import selected_script_paths
        return selected_script_paths(self.page.root,[selected[0]])[0]

    def selected_scripts(self):
        """批量删除只认勾选项；未勾选时将当前高亮行视作单项操作。"""
        all_items=self.all_script_items()
        tree=self.current_script_tree()
        active=tree.selection() if tree else ()
        from script_workspace_service import script_deletion_selection
        return script_deletion_selection(self.page.root,all_items,self.checked_scripts,active)

    def selection_changed(self):
        count=len(self.checked_scripts)
        self.page.status.set('已勾选 '+str(count)+' 份剧本文件' if count else '已取消剧本文件勾选')

    def rename_script(self):
        path=self.selected_script()
        new=ask_string(self.page.win,'重命名文件','新文件名：',initialvalue=path.name)
        if not new:return
        from script_workspace_service import rename_script_document
        result=rename_script_document(self.page.root,path,new)
        if not result.ok:raise ValueError(result.reason)
        dest=result.data
        if dest==path:return
        self.fill_script_list();self.page.status.set('已重命名：'+dest.name)

    def confirmed_note(self, paths):
        # 删掉已确认阶段文件会让剧本准备的确认失效，删前点明。
        import writing_api
        confirmed=writing_api.confirmed_preparation_files(self.page.root)
        hits=[confirmed[p.resolve()]+'：'+p.name for p in paths if p.resolve() in confirmed]
        if not hits:return ''
        return '\n\n注意：以下是剧本准备已确认的阶段文件，删除后该阶段确认失效，需要恢复或重新确认才能继续：\n'+'\n'.join(hits)

    def delete_script(self):
        path=self.selected_script()
        all_files=self.all_script_items()
        if len(all_files)==1:
            if not self.page.writing_page_services.confirm_project_removal(self.page.win,[path.name]):return
        else:
            prompt=f'确定将 {path.name} 移入项目回收站吗？\n\n可在对应页面恢复最近删除。'+self.confirmed_note([path])
            title='移入回收站'
            if not self.page.writing_page_services.confirm(self.page.win,title,prompt,dangerous=True):return
        if len(all_files)==1:
            item=next((dict(p) for p in self.page.projects.info['projects'] if p['path']==str(self.page.root)),None)
            if item is None:raise ValueError('当前项目未登记，无法安全删除')
            self.page.delete_project(item,confirmed=True);return
        from storage_maintenance import recycle_paths
        if not recycle_paths(self.page.root,[path],'删除项目剧本'):
            raise OSError('文件未能移入回收站，请刷新后重试')
        self.fill_script_list();self.page.status.set('已移入回收站：'+path.name)

    def delete_selected_scripts(self):
        selection=self.selected_scripts()
        paths=list(selection.paths)
        names='\n'.join(path.name for path in paths)
        if selection.deletes_all:
            if not self.page.writing_page_services.confirm_project_removal(self.page.win,[path.name for path in paths]):return
        else:
            title='移入回收站'
            prompt='确定将选中的 '+str(len(paths))+' 份剧本文件移入项目回收站吗？\n\n'+names+'\n\n可在对应页面恢复最近删除。'+self.confirmed_note(paths)
            if not self.page.writing_page_services.confirm(self.page.win,title,prompt,dangerous=True):return
        if selection.deletes_all:
            item=next((dict(p) for p in self.page.projects.info['projects'] if p['path']==str(self.page.root)),None)
            if item is None:raise ValueError('当前项目未登记，无法安全删除')
            self.page.delete_project(item,confirmed=True);return
        from storage_maintenance import recycle_paths
        recycled=recycle_paths(self.page.root,paths,'批量删除项目剧本')
        if len(recycled)!=len(paths):
            raise OSError('部分文件未能移入回收站，请刷新后重试')
        self.fill_script_list()
        self.page.status.set('已移入回收站 '+str(len(paths))+' 份剧本文件')

    def adopt_script(self):
        from stage_execution_service import adopt_natural_script
        adopted=adopt_natural_script(self.page.root,self.selected_script())
        self.fill_script_list()
        self.page.status.set('已采用自然剧本：'+adopted.name+'；后续结构化使用此版本')

    def restart_preparation(self, stage):
        _restart_preparation(self.page,stage,self.fill_script_list)

    def confirm_document(self, stage):
        """把用户改过的当前文件设为该阶段定稿；之后各阶段的定稿会失效。"""
        path=self.selected_script()
        from stage_execution_service import confirm_writing_preparation
        if not self.page.writing_page_services.confirm(self.page.win,'设为'+stage+'定稿',
                       '把这份文件设为「'+stage+'」的定稿？\n\n'+path.name+
                       '\n\n以文件当前内容为准；「'+stage+'」之后已定稿的阶段需要重新确认。'):
            return
        invalidated=confirm_writing_preparation(self.page.root,stage,path)
        self.fill_script_list()
        self.page.status.set('已把'+path.name+'设为「'+stage+'」定稿'+
                        ('；「'+'」「'.join(invalidated)+'」需要重新确认' if invalidated else ''))

    def script_menu(self, tree,event):
        row=tree.identify_row(event.y)
        if not row:return
        tree.selection_set(row);self.keep_one_selection(tree)
        menu=self.page.writing_page_services.context_menu(self.page.win)
        # 第 46 期第 1 条：内容框的右键一律是「查看／…／删除」这一套，剧本表原来只有改名与删除。
        menu.command('查看',lambda:self.page.safe(self.open_script_file))
        menu.command('重命名',lambda:self.page.safe(self.rename_script))
        category=self.script_row_category.get(row,'script')
        if category=='script':
            menu.command('采用此剧本',lambda:self.page.safe(self.adopt_script))
        else:
            stages={'setting':'项目设定','outline':'剧本大纲','character':'角色卡'}
            stage=stages[category]
            menu.command('重写'+stage,lambda:self.page.safe(lambda:self.restart_preparation(stage)))
            menu.command('放弃重写，恢复原稿',lambda:self.page.safe(lambda:self.restart_preparation(None)))
            menu.command('设为'+stage+'定稿',lambda:self.page.safe(lambda:self.confirm_document(stage)))
        menu.command('删除',lambda:self.page.safe(self.delete_script))
        return menu.popup(event)
