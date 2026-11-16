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
import tkinter as tk
from tkinter import ttk
from ui_tokens import COLORS, FONTS, SPACING
from ui_widgets import EllipsisLabel, SecondaryButton, TextArea, ask_string

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


class _WritingPage:
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
        # R2962：项目文件栏迁出本页——全局入口与右侧停靠面板在 desktop_files_panel；
        # Destroy 兜底改绑 talk（原绑 script_box，随页面销毁清 recon 延后任务）。
        self.talk.bind('<Destroy>',self.cancel_recon_state,add='+')
        from responsive_ui import display_lines,font_linespace
        self.display_lines = display_lines
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
        if event is not None and getattr(event,'widget',None) is not self.talk:
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
