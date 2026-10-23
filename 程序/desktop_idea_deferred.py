"""剧本准备页首绘后的延迟更新（从 ``desktop_idea_chat`` 拆出的桌面方法集）。

示例气泡必须随页面立刻可见；聊天历史与附件回填会改变几何，要等画布布局
稳定后再做。这些方法与 ``IdeaChatMixin`` 共用 ``self`` 状态，同属 L4。
"""
import time
import tkinter as tk

import app_logging
import pet_state
from ui_tokens import COLORS, FONTS

PAGE = pet_state.PAGE_OF

# 首绘后等待布局收敛的轮询间隔（毫秒）。
IDEA_UPDATE_POLL_MS = 16
# 连续稳定拍数：``_fit_pending`` 连续这么多拍为假才回填。
IDEA_UPDATE_STABLE_TICKS = 3
# 最长等待秒数；超时后不再等布局，直接回填。
IDEA_UPDATE_TIMEOUT_SECONDS = 2.0
# 有聊天记录时首绘的读取提示（R1949）；标签不以 bubble_example 命名，复制／编辑都不把它当示例。
IDEA_HISTORY_LOADING_TEXT = '正在读取聊天记录…'
IDEA_HISTORY_LOADING_TAG = 'bubble_loading'


class IdeaDeferredMixin:
    """首绘后延迟更新方法集；``IdeaChatMixin`` 继承本类。"""

    def show_example_bubble(self, loading=None):
        """首绘只放一条占位：没有聊天记录放软件示例，有记录放“正在读取”提示。

        示例是用户填写前唯一的参考，必须随页面立刻可见；历史消息会改变
        聊天框高度，建页当拍插入会与画布的布局收敛互相触发，所以等布局稳定后
        再整体重绘。R1949：有记录的项目若先放示例，重绘时会从示例跳成历史，
        改为放一行安静的读取提示，重绘只是把它换成历史。
        """
        box=getattr(self,'idea_log',None)
        if box is None or not box.winfo_exists():return
        if loading is None:loading=self.idea_history_expected()
        box.configure(state='normal')
        self._bubble_rows=[];self._bubble_full={};self._bubble_width=int(box.winfo_width() or 0)
        for name in [one for one in box.tag_names() if one.startswith('bubble_')]:
            box.tag_delete(name)
        box.delete('1.0','end')
        if loading:
            left,right=self.bubble_margins(box,IDEA_HISTORY_LOADING_TEXT,False)
            box.tag_configure(IDEA_HISTORY_LOADING_TAG,justify='left',foreground=COLORS['text_secondary'],
                              lmargin1=left,lmargin2=left,rmargin=right,font=FONTS['hint'])
            box.insert('end',IDEA_HISTORY_LOADING_TEXT+'\n',IDEA_HISTORY_LOADING_TAG)
        else:
            self.add_bubble(box,{'role':'assistant','model':'示例模板','text':self.idea_template},'example')
        box.configure(state='normal')
    def idea_history_expected(self):
        """当前项目是否已有聊天记录；同一项目本次运行内只问一次盘，之后以重绘结果为准。"""
        root=self.root
        if not root:return False
        known=getattr(self,'_idea_history_known',None)
        if not isinstance(known,dict):known=self._idea_history_known={}
        if root not in known:
            import idea_chat
            try:known[root]=idea_chat.has_history(self.idea_chat_context(),gateway=self.idea_chat_gateway())
            except Exception:
                app_logging.swallowed()
                known[root]=False
        return known[root]
    def defer_idea_page_updates(self):
        """把附件回填与聊天重绘放到剧本页首绘之后。

        两者都会改变输入区／聊天框几何；建页当拍执行会与画布的布局收敛互相
        触发，真实项目上 page.paint.script 因此从约 0.5s 拖到 1.1s。等
        ``_fit_pending`` 连续几拍稳定（与页面指标同一判定）再回填。
        """
        job=getattr(self,'_idea_page_update_job',None)
        if job is not None:
            try:self.win.after_cancel(job)
            except tk.TclError:pass
        self._idea_page_update_job=None
        deadline=time.monotonic()+IDEA_UPDATE_TIMEOUT_SECONDS
        def check(stable=0):
            self._idea_page_update_job=None
            if getattr(self,'shutting_down',False) or self.page_index!=PAGE['script']:
                return
            stable=0 if getattr(self,'_fit_pending',False) else stable+1
            if stable<IDEA_UPDATE_STABLE_TICKS and time.monotonic()<deadline:
                try:self._idea_page_update_job=self.win.after(IDEA_UPDATE_POLL_MS,lambda:check(stable))
                except tk.TclError:self._idea_page_update_job=None
                return
            self.update_idea_attachment_status()
            self.show_conversation()
        try:self._idea_page_update_job=self.win.after(IDEA_UPDATE_POLL_MS,check)
        except tk.TclError:self._idea_page_update_job=None
