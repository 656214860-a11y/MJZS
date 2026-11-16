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
import contract.project_stages as project_stages
import os
import tkinter as tk
import ui_plugin_registry
from pathlib import Path
from responsive_ui import FlowBar, fit_row_height, row_toggle_target
from tkinter import ttk
from ui_tokens import BUTTON_GAP_TIGHT, CHAR_WIDTH, COLORS, FONTS, ICON_ADD, ICON_MICROPHONE, ICON_SEND, SCRIPT_ACTION_WIDTH, VOICE_POLL_MS, SCRIPT_FILE_FONT, SCRIPT_FILE_MAX_ROWS, SPACING
from desktop_file_card import TreeRowCard, script_row_card
from ui_widgets import Card, DataTable, EllipsisLabel, PrimaryButton, SecondaryButton, TextArea, Tooltip, ask_string
from desktop_writing_snapshots import WritingSnapshotsMixin

PAGE = pet_state.PAGE_OF

# 第 71 期任务 5／6：剧本准备页的创意框摆几行——窗口再矮也留 TALK_MIN_LINES 行，
# 字再多、窗口再高也不超过 TALK_MAX_LINES 行（一次铺满半页纸就不好操作了）；
TALK_MIN_LINES=6
TALK_MAX_LINES=15
# 输入框空框时的行数与按内容撑开的上限；空框两行，向上长高。
COMPOSER_MIN_LINES=2
COMPOSER_MAX_LINES=8


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

    def _composer_dispatch(self, name, event):
        """剧本页输入框事件的按名转派：只在剧本页且控制器新鲜时转发。

        R2916：剧本页恢复自有输入框后，绑定随控件每次重建；转派按方法签名容错
        （有的回调不接收 event，如 stop_input_hint），避免每次建页/销毁抛 TypeError。
        """
        if getattr(self, 'page_index', None) != PAGE['script']:
            return None
        controller = getattr(self, '_writing_page_controller', None)
        method = getattr(controller, name, None)
        if method is None:
            return None
        try:
            return method(event)
        except TypeError:
            return method()

    def build_script_quality_buttons(self, foot):
        """动作栏末尾的「质检报告／采风」。动作栏按创建顺序排列，这两颗要最后创建。

        采风只对「对标爆款」「热点速成」有用：建页时先隐藏，由 ``update_recon_button`` 按素材来源补上。
        """
        SecondaryButton(foot,text='质检报告',command=lambda:self.safe(self.open_script_quality)).pack(side='right')
        self.recon_button=SecondaryButton(foot,text='采风',command=lambda:self.safe(self.collect_recon))
        foot.set_visible(self.recon_button,False)

    def update_recon_button(self):
        """素材来源是「对标爆款」「热点速成」时显示采风，其余来源隐藏（REQ-S01-46）。"""
        import recon_service, stage_config
        button=getattr(self,'recon_button',None)
        try:
            if button is None or not button.winfo_exists():return
            source=str(stage_config.workflow_lock(self.root).get('material_source') or '') if self.root else ''
            button.master.set_visible(button,source in recon_service.MATERIAL_SOURCES)
        except tk.TclError:return

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


class VoiceInput:
    """REQ-S01-71：麦克风听写开关。打开后边说边把文字写到输入框光标处，再点一下关闭。

    录音线程每 0.1 秒把 PCM 交给 ``speech_api.RealtimeSession``，服务端按停顿断句：
    当前句的中间结果以浅色写在光标处、随结果替换，整句定稿后恢复正常颜色。关麦后等最后一句
    定稿再结束（最多 ``timeout`` 秒）。会话不走 ``Desktop.async_()``（新票号会作废正在运行的
    剧本请求），而用本输入框自己的 ``BackgroundTaskLifecycle`` 登记代次；页面销毁时停录并取消，
    迟到事件不进界面。
    """
    LISTENING_STYLE, IDLE_STYLE = 'Tokens.Composer.Send.TButton', 'Tokens.Composer.Icon.TButton'
    SILENCE_PEAK, SILENCE_HINT_SECONDS, LEVEL_BARS = 300, 3, 5
    PARTIAL_TAG = 'voice_partial'

    def __init__(self, page, box, button):
        self.page, self.box, self.button = page, box, button
        from desktop_automation_service import BackgroundTaskLifecycle
        self.recorder, self.session, self.settings, self.pending, self.ticket = None, None, None, None, None
        self.spans, self.deadline, self.serial = {}, None, 0
        self.tasks = BackgroundTaskLifecycle()
        box.tag_configure(self.PARTIAL_TAG, foreground=COLORS['text_muted'])
        box.bind('<Destroy>', lambda event: self.stop() if event.widget is box else None, add='+')

    @property
    def listening(self):
        return self.recorder is not None

    @property
    def closing(self):
        return self.session is not None and self.recorder is None

    def toggle(self):
        if self.closing:return self.page.status.set('正在写完最后一句，请稍候…')
        if self.listening:return self.close()
        import contract.platform_tools as platform_tools
        import speech_api
        self.settings = speech_api.read_settings()
        reason = speech_api.missing_reason(self.settings)
        if reason:return self.page.status.set('语音输入未能启动（%s）。' % reason)
        session = speech_api.RealtimeSession(self.settings)
        recorder = platform_tools.MicrophoneRecorder(max_seconds=self.settings['max_seconds'], on_chunk=session.send)
        reason = recorder.start()
        if reason:return self.page.status.set('语音输入未能启动（%s）；请检查麦克风连接与 Windows 设置「隐私和安全性 › 麦克风」。' % reason)
        session.start()
        self.ticket = self.tasks.submit(object(), costly=True, label='语音输入',
                                        timeout=self.settings['max_seconds'] + self.settings['timeout'] + 30)
        self.recorder, self.session, self.spans, self.deadline = recorder, session, {}, None
        self.button.configure(style=self.LISTENING_STYLE)
        self.box.focus_force()
        self.poll()

    def close(self):
        """关麦：停录、通知服务端收尾，等最后一句定稿后由 poll 结束会话。"""
        recorder, self.recorder = self.recorder, None
        self.button.configure(style=self.IDLE_STYLE)
        recorder.stop()
        self.session.finish()
        self.deadline = time.monotonic() + self.settings['timeout']
        self.page.status.set('麦克风已关闭，正在写完最后一句…')
        if recorder.error:self.page.status.set('录音中断（%s），正在写完已说的内容…' % recorder.error)

    def write(self, item, text, final):
        """把一句的最新结果写进它在输入框里的位置；新句子从当前光标开始。"""
        box = self.box
        if item not in self.spans:
            self.serial += 1
            marks = ('voice_start_%d' % self.serial, 'voice_end_%d' % self.serial)
            box.mark_set(marks[0], 'insert');box.mark_gravity(marks[0], 'left')
            box.mark_set(marks[1], 'insert');box.mark_gravity(marks[1], 'right')
            self.spans[item] = marks
        start, end = self.spans[item]
        box.delete(start, end)
        box.insert(start, text, () if final else (self.PARTIAL_TAG,))
        if final:
            box.mark_unset(start, end);del self.spans[item]
        box.see('insert')

    def poll(self):
        import queue
        self.pending = None
        if not self.box.winfo_exists():return self.stop()
        session = self.session
        if session is None:return None
        while True:
            try:kind, item, text = session.events.get_nowait()
            except queue.Empty:break
            if kind in ('partial', 'final'):self.write(item, text, kind == 'final')
            elif kind == 'error':return self.end(False, '语音输入中断（%s）。' % text)
            elif kind == 'closed':return self.end(True, '语音输入已关闭。')
        if self.recorder is not None:
            if self.recorder.finished:self.close()
            elif self.recorder.seconds >= self.SILENCE_HINT_SECONDS and self.recorder.peak < self.SILENCE_PEAK:
                self.page.status.set('没听到声音：请检查麦克风是否静音，以及 Windows 设置「隐私和安全性 › 麦克风」是否允许桌面应用使用麦克风。')
            else:
                bars = min(self.LEVEL_BARS, int(self.recorder.level * self.LEVEL_BARS * 2 + 0.5))
                self.page.status.set('正在听写 %d 秒  %s  说完再点麦克风关闭。' % (
                    self.recorder.seconds, '▮' * bars + '▯' * (self.LEVEL_BARS - bars)))
        elif self.deadline is not None and time.monotonic() > self.deadline:
            return self.end(False, '识别服务没有及时返回最后一句，语音输入已关闭。')
        self.pending = self.box.after(VOICE_POLL_MS, self.poll)

    def end(self, succeeded, message):
        """会话结束（正常关闭、出错或超时）：未定稿的浅色文字原样保留为正常文字。"""
        ticket, self.ticket = self.ticket, None
        self.stop()
        if not self.tasks.finish(ticket, succeeded=succeeded, error='' if succeeded else message):
            return self.page.status.set('语音输入已取消。')
        self.page.status.set(message)

    def stop(self):
        if self.pending is not None:
            try:self.box.after_cancel(self.pending)
            except tk.TclError:pass
            self.pending = None
        recorder, session, ticket = self.recorder, self.session, self.ticket
        self.recorder, self.session, self.ticket, self.deadline = None, None, None, None
        if recorder is not None:recorder.stop()
        if session is not None:session.cancel()
        if ticket is not None and self.tasks.accepts(ticket):self.tasks.cancel(ticket)
        try:
            self.box.tag_remove(self.PARTIAL_TAG, '1.0', 'end')
            for marks in self.spans.values():self.box.mark_unset(*marks)
            self.button.configure(style=self.IDLE_STYLE)
        except tk.TclError:return
        finally:self.spans = {}


class _WritingPage(WritingSnapshotsMixin):
    """剧本准备页（从 WritingPageMixin.writing 的闭包原样改写成类，R1817）：共享的局部变量成了实例属性，嵌套函数成了方法；原来的 self（桌面主窗）改叫 page。"""
    def __init__(self, page):
        self.page = page

    def build(self):
        from script_workspace_service import ensure_script_workspace
        result=ensure_script_workspace(self.page.root)
        if not result.ok:raise ValueError(result.reason)
        # 第 69 期任务 4：原来第一行那句「在下面的对话框写想法…」删掉——页面自己会说清怎么走。
        brief = self._build_composer()
        self._build_dialog(brief)
        self.page._writing_page_controller = self
        # 输入区是共享 Text 时同一控件跨页常驻：绑定按「控件身份」只挂一次，
        # 由 Desktop._composer_dispatch 转派给当前控制器；页内回退 TextArea 每次
        # 重建都是新控件，身份不同会自然重绑（旧绑定随旧控件销毁）。
        bound_box = getattr(self.page, '_composer_bound_box', None)
        if bound_box is not self.input_box:
            self.page._composer_bound_box = self.input_box
            self.input_box.bind('<Button-3>',self.page.open_idea_paste_menu,add='+')
            self.input_box.bind('<KeyRelease>',self.page.show_idea_reference_menu,add='+')
            self.input_box.bind('<Return>',lambda event:self.page._composer_dispatch('send_on_enter',event),add='+')
            self.input_box.bind('<KP_Enter>',lambda event:self.page._composer_dispatch('send_on_enter',event),add='+')
            self.input_box.bind('<<Modified>>',lambda event:self.page._composer_dispatch('on_modified',event))
            # 运行中按 Esc 等同点终止（共享框的 Esc 先关补全，不拦这条）。
            self.input_box.bind('<Escape>',lambda event:self.page._composer_dispatch('interrupt_from_input',event),add='+')
        self.box.bind('<Configure>',self.page.refit_bubbles,add='+')
        self.page.restore_idea_draft()
        self.update_input_hint()
        # 首绘只放示例气泡；真实历史与附件回填等布局稳定后再补，避免拖住 page.paint。
        self.page.show_example_bubble()
        self.page.defer_idea_page_updates()
        self.page.refresh_idea_send_state()
        # 页面仍在当前代次时再补状态。
        self.page_generation=getattr(self.page,'_script_page_generation',0)+1
        self.page._script_page_generation=self.page_generation
        # R2923：文件框改到左侧竖向（工作目录列表右侧、聊天区左侧），四类文件
        # 合成一条竖向列表，每类一个带小标题的分组。
        self.script_box=ttk.Frame(self.page.content,padding=(SPACING['xs'],SPACING['xs']))
        self.script_box.pack(side='left',fill='y',expand=False,pady=SPACING['none'])
        self.page.script_box=self.script_box
        self.script_box.bind('<Destroy>',self.cancel_recon_state,add='+')
        # R2923：四类文件合成左侧一条竖向列表（每类一个带小标题的分组，组内按修改时间；
        # Ctrl／Shift 可多选）。原横向四列小表（R1862 口径）作废。
        categories=(('setting','项目设定'),('outline','项目大纲'),('character','角色卡'),('script','项目剧本'))
        self.script_box.columnconfigure(0,weight=1);self.script_box.rowconfigure(0,weight=1)
        lists=ttk.Frame(self.script_box);lists.grid(row=0,column=0,sticky='nsew')
        self.script_trees={}
        self.script_row_details={}
        self.script_row_category={}
        tips=lambda item:self.script_row_details.get(item,'')
        self.page.script_file_tips={}
        for category,title in categories:
            table=DataTable(lists,columns=[('name',title,180)],show='headings',height=1,
                            selectmode='extended',style='Script.Treeview',auto_hide_scrollbars=True,
                            empty_text='',horizontal=False)
            tree=table.tree
            tree.heading('name',text=title,anchor='center')
            tree.column('name',width=SPACING['sm'] * 23,minwidth=100,stretch=True)
            self.page.script_file_tips[category]=TreeRowCard(tree,tips)
            table.pack(fill='both',expand=True,pady=(SPACING['none'],SPACING['xs']))
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
        from writing_page_controller import ScriptListLoadController
        self.script_loader=ScriptListLoadController(category for category,_title in categories)
        self.script_load_job=None
        self.script_box.bind('<Destroy>',self.cancel_script_load,add='+')
        self.page.refresh_script_list=self.fill_script_list
        self.page.open_script_file=self.open_script_file
        for tree in self.script_trees.values():
            tree.bind('<Double-1>',self.open_script_file)
            tree.bind('<Return>',self.open_script_file)
            tree.bind('<<TreeviewSelect>>',lambda event,tree=tree:self.keep_one_selection(tree),add='+')
            tree.bind('<Button-3>',lambda event,tree=tree:self.script_menu(tree,event))
        self.fill_script_list()

    def _build_composer(self):
        """上半区：聊天区与底部用量/会话状态行；输入、发送、附件、语音、模型与技能
        全部收进底部共享输入框（R2923：13 页同一个输入框）。"""
        import idea_chat
        # 先使用不扫描目录的默认路径；历史创意文件由页面建好后在后台发现。
        brief=idea_chat.default_brief_document(self.page.idea_chat_context())
        self.page.idea_template=self.page.idea_example()
        # 聊天记录与发送框分离：记录可滚动，共享输入框固定停在窗口底部。
        self.talk=ttk.Frame(self.page.content,style='Box.TFrame',padding=(SPACING['xs'],SPACING['none']))
        # 标题、聊天框与左侧内容起点同高；不在标题下额外留出一档空白。
        self.talk.pack(fill='both',expand=True,pady=SPACING['none'])
        # 用量与会话说明合成页面最底部的单行状态栏：不换行、放不下就截断，悬停看全文。
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
        # R2923：输入框=底部共享框里的同一个 Text；无共享实例时页内兜底一张。
        shared_input=getattr(self.page,'shared_input',None)
        shared_box=getattr(shared_input,'input',None)
        if shared_box is not None:
            self.input_box=shared_box
            # 附件卡片行改挂共享输入盒内部（＋ 图标也在共享框里）。
            self.page.idea_uploaded_panel=shared_input.attachment_panel
        else:
            self.input_box=TextArea(self.talk,bg=COLORS['background_card'],fg=COLORS['text_primary'],
                              insertbackground=COLORS['primary'],height=COMPOSER_MIN_LINES,wrap='word',
                              font=FONTS['body'],relief='flat',bd=0,highlightthickness=0,
                              padx=SPACING['xs'],pady=SPACING['xs'],undo=True)
            self.input_box.pack(side='bottom',fill='x',pady=(SPACING['none'],SPACING['xs']))
        self.page.idea_attachment_status=tk.StringVar(value='')
        return brief

    def _build_dialog(self, brief):
        """对话区：聊天记录框及其快捷键与右键菜单（R2923：发送/刷新/添加剧本/剧本目录/
        质检报告/采风/阶段配置按钮已删除，动作统一进底部共享输入框）。"""
        self.dialog=ttk.Frame(self.talk);self.dialog.pack(side='top',fill='both',expand=True,pady=SPACING['none'])
        self.page.build_idea_model_bar(self.dialog)  # 聊天气泡框左上角的模型目录条（先隐藏）
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
        # 聊天记录只读：可长按拖选并 Ctrl+C，不能编辑。
        self.page.shortcuts.bind(self.box, ('<Control-c>', '<Control-C>'), self.page.copy_selected_bubble_text,
                            scope='剧本准备·聊天记录', name='复制选中气泡文本')
        self.box.bind('<Button-3>',self.page.open_bubble_menu,add='+')
        self.box.bind('<KeyPress>',self.page.guard_bubble_key,add='+')
        self.box.bind('<<Paste>>',self.page.guard_bubble_key,add='+')

    def stop_input_hint(self):
        # R2923：输入框并入底部共享框，页面不再自建提示标签；兜底清空。
        hint = getattr(self, 'input_hint', None)
        if hint is not None:
            try:
                hint.place_forget()
            except tk.TclError:
                pass

    def _composer_page_active(self):
        """共享输入框跨页常驻后，composer 的页面级绑定只在剧本准备页生效（任务书轮 4）。"""
        return getattr(self.page,'page_index',None)==PAGE['script']

    def update_input_hint(self, event=None):
        if not self._composer_page_active():
            self.stop_input_hint()
            return
        hint = getattr(self, 'input_hint', None)
        if hint is None:
            return
        try:
            if not self.page.draft_text().strip() and self.input_box.focus_get() is not self.input_box:
                # Text 的 inside 边界已含文字内边距，避免再次累加 padx；纵向对齐首行。
                hint.place(in_=self.input_box,x=SPACING['none'],y=SPACING['none'],anchor='nw')
            else:self.stop_input_hint()
        except tk.TclError:pass

    # 聊天区只读；窗口缩小时只收聊天记录区，底部发送框永远可见。
    def refit_talk(self, event=None):
        fit=getattr(self.page,'_fit_talk',None)
        if fit is None:return
        try:fit()
        except Exception:app_logging.swallowed()

    def on_modified(self, event=None):
        if not self._composer_page_active():
            try:self.input_box.edit_modified(False)
            except tk.TclError:pass
            return
        if event is not None and not self.input_box.edit_modified():return
        self.input_box.edit_modified(False)
        # R2923：共享输入框固定行数、内容在框内滚动，不再按内容撑高。
        if getattr(self.page,'shared_input',None) is None or self.input_box is not self.page.shared_input.input:
            self.input_box.after_idle(self.fit_composer)
        self.update_input_hint()
        self.page.refresh_idea_send_state()

    def fit_composer(self, event=None):
        """仅按实际内容撑开输入框，避免点击空框触发布局反馈回路。"""
        if not self._composer_page_active() or not self.input_box.winfo_exists():return
        try:
            logical_lines=int(self.input_box.index('end-1c').split('.')[0])
            # 空框保留 COMPOSER_MIN_LINES 行。旧逻辑在点击时按聊天框高度把 Text 放大到半屏，
            # 输入框、聊天框、画布各自的 Configure 又会重新测量对方，形成持续抖动。
            # 文字需要多行时才增长，并设上限以维持操作栏和文件表可见。
            lines=min(COMPOSER_MAX_LINES,max(COMPOSER_MIN_LINES,logical_lines,self.display_lines(self.input_box)))
            # 共享输入框的高度归 SharedStageInput 统一管理；页面只在旧的页内
            # TextArea 上按内容撑开，避免剧本页把共享栏高度带到其它阶段。
            if (int(self.input_box.cget('height'))!=lines
                    and getattr(self.page,'shared_input',None) is None):
                self.input_box.configure(height=lines)
                self.page.fit_content()
        except (tk.TclError,ValueError):pass

    def expand_composer_for_click(self, event=None):
        """空框点击只取得编辑焦点；高度只由真实输入内容决定。"""
        self.input_box.focus_set()

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

    def interrupt_from_input(self, event=None):
        """运行中在输入框按 Esc 等同点终止；空闲时不拦截，交给其他绑定。"""
        if not self._composer_page_active() or not self.page.script_task_active():return None
        self.page.safe(self.page.interrupt_script_agent)
        return 'break'

    def send_on_enter(self, event):
        # 共享输入框在时 Enter 由它统一发送（desktop_shared_input._on_return）；
        # 这里只兜底没有共享实例的旧页面。
        if getattr(self.page,'page_index',None)!=PAGE['script']:return None
        if event.state & 0x1:return None  # Shift+Enter 保留换行
        self.page.safe(self.page.send_message)
        return 'break'

    def refresh_recon_state(self):
        if (self.page_generation==getattr(self.page,'_script_page_generation',0)
                and self.page.page_index==PAGE['script'] and self.page.root):
            self.page.update_recon_button()

    def cancel_recon_state(self, event=None):
        """页面已销毁时不再执行采风显隐的延后刷新（R2923：按钮已删，仅兜底清理）。"""
        if event is not None and getattr(event,'widget',None) is not self.script_box:
            return None
        if getattr(self, 'recon_state_job', None) is not None:
            try:self.page.win.after_cancel(self.recon_state_job)
            except tk.TclError:pass
        return None

    def open_stage_panel(self):
        """阶段配置弹窗关掉后，按新的素材来源刷新采风显隐。"""
        panel=self.panel.open_for_page(self.page,PAGE['script'],self.holder['button'])
        if panel is not None:
            panel.bind('<Destroy>',lambda event:self.refresh_recon_state() if event.widget is panel else None,add='+')
        return panel

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
                for tree in self.script_trees.values():
                    tree.configure(height=max(1,min(SCRIPT_FILE_MAX_ROWS,len(tree.get_children()))))
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
        # 表头（分类名）与列宽分隔线也在 Treeview 的 <Double-1> 范围内；
        # 此时 selection() 仍保留着上次高亮的行，不能直接拿它打开文件。
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
        """当前表里选中的各行（Ctrl／Shift 多选），并标出是否选中了列表里的全部文件。"""
        tree=self.current_script_tree()
        from script_workspace_service import script_deletion_selection
        return script_deletion_selection(self.page.root,self.all_script_items(),tree.selection() if tree else ())

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
        """右键「删除」：把选中的各行移入项目回收站；选中的是列表里全部文件时按删项目确认。"""
        selection=self.selected_scripts()
        paths=list(selection.paths)
        if selection.deletes_all:
            if not self.page.writing_page_services.confirm_project_removal(self.page.win,[path.name for path in paths]):return
            item=next((dict(p) for p in self.page.projects.info['projects'] if p['path']==str(self.page.root)),None)
            if item is None:raise ValueError('当前项目未登记，无法安全删除')
            self.page.delete_project(item,confirmed=True);return
        one=len(paths)==1
        if one:
            prompt=f'确定将 {paths[0].name} 移入项目回收站吗？\n\n可在对应页面恢复最近删除。'+self.confirmed_note(paths)
        else:
            names='\n'.join(path.name for path in paths)
            prompt='确定将选中的 '+str(len(paths))+' 份剧本文件移入项目回收站吗？\n\n'+names+'\n\n可在对应页面恢复最近删除。'+self.confirmed_note(paths)
        if not self.page.writing_page_services.confirm(self.page.win,'移入回收站',prompt,dangerous=True):return
        from storage_maintenance import recycle_paths
        recycled=recycle_paths(self.page.root,paths,'删除项目剧本' if one else '批量删除项目剧本')
        self.fill_script_list()                  # 部分成功时已进回收站的那些也要从列表消失：先刷新再报错
        if len(recycled)!=len(paths):
            raise OSError('文件未能移入回收站，请刷新后重试' if one else '部分文件未能移入回收站，请刷新后重试')
        self.page.status.set('已移入回收站：'+paths[0].name if one else '已移入回收站 '+str(len(paths))+' 份剧本文件')

    def adopt_script(self):
        from stage_execution_service import adopt_natural_script
        adopted=adopt_natural_script(self.page.root,self.selected_script())
        self.fill_script_list()
        self.page.status.set('已采用自然剧本：'+adopted.name+'；后续结构化使用此版本')

    def unconfirm_preparation(self, stage):
        """右键「取消已确认」：取消该阶段确认并把准备流程回退到该阶段；只改台账、不删文件。"""
        from writing_api import PREPARATION_STAGES
        from writing_unconfirm import preparation_confirmed_stages
        confirmed = preparation_confirmed_stages(self.page.root)
        if stage not in confirmed:
            return
        index = PREPARATION_STAGES.index(stage)
        downstream = tuple(s for s in confirmed if PREPARATION_STAGES.index(s) > index)
        prompt = ('确定取消「' + stage + '」的确认吗？\n\n'
                  '取消后剧本准备流程回到「' + stage + '」，您需要重新确认该阶段。')
        if downstream:
            prompt += '\n\n已确认的「' + '」「'.join(downstream) + '」会一并取消。'
        prompt += '\n\n不会删除或覆盖任何文件，原稿保留。'
        if not self.page.writing_page_services.confirm(self.page.win, '取消已确认', prompt):
            return
        from stage_execution_service import unconfirm_writing_preparation
        invalidated = unconfirm_writing_preparation(self.page.root, stage)
        self.fill_script_list()
        note = ('，「' + '」「'.join(invalidated) + '」的确认一并取消' if invalidated else '')
        self.page.status.set('已取消「' + stage + '」的确认' + note + '，当前回到「' + stage + '」')

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
        # 右键落在已选中的行上时保留 Ctrl／Shift 多选；落在别的行上改选这一行。
        if row not in tree.selection():tree.selection_set(row)
        self.keep_one_selection(tree)
        menu=self.page.writing_page_services.context_menu(self.page.win)
        if len(tree.selection())>1:
            # 多选时只给「删除」：查看、改名、定稿都只针对一份文件。
            menu.command('删除',lambda:self.page.safe(self.delete_script))
            return menu.popup(event)
        # 第 46 期第 1 条：内容框的右键一律是「查看／…／删除」这一套，剧本表原来只有改名与删除。
        menu.command('查看',lambda:self.page.safe(self.open_script_file))
        menu.command('重命名',lambda:self.page.safe(self.rename_script))
        category=self.script_row_category.get(row,'script')
        if category=='script':
            menu.command('采用此剧本',lambda:self.page.safe(self.adopt_script))
        else:
            stages={'setting':'项目设定','outline':'剧本大纲','character':'角色卡'}
            stage=stages[category]
            from writing_unconfirm import preparation_confirmed_stages
            if stage in preparation_confirmed_stages(self.page.root):
                menu.command('取消已确认',lambda:self.page.safe(lambda:self.unconfirm_preparation(stage)))
            menu.command('设为'+stage+'定稿',lambda:self.page.safe(lambda:self.confirm_document(stage)))
            menu.command('按段落采用…',lambda:self.page.safe(lambda:self.show_partial_adoption(stage)))
            menu.command('历史快照／对比',lambda:self.page.safe(lambda:self.show_preparation_snapshots(stage)))
        menu.command('删除',lambda:self.page.safe(self.delete_script))
        return menu.popup(event)
