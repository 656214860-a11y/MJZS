"""剧本准备页首绘后的延迟更新（从 ``desktop_idea_chat`` 拆出的桌面方法集）。

示例气泡必须随页面立刻可见；聊天历史与附件回填会改变几何，要等画布布局
稳定后再做。这些方法与 ``IdeaChatMixin`` 共用 ``self`` 状态，同属 L4。
"""
import time
import tkinter as tk

import pet_state

PAGE = pet_state.PAGE_OF

# 首绘后等待布局收敛的轮询间隔（毫秒）。
IDEA_UPDATE_POLL_MS = 16
# 连续稳定拍数：``_fit_pending`` 连续这么多拍为假才回填。
IDEA_UPDATE_STABLE_TICKS = 3
# 最长等待秒数；超时后不再等布局，直接回填。
IDEA_UPDATE_TIMEOUT_SECONDS = 2.0


class IdeaDeferredMixin:
    """首绘后延迟更新方法集；``IdeaChatMixin`` 继承本类。"""

    def show_example_bubble(self):
        """首绘只放软件示例气泡；真实历史等布局稳定后再整体重绘。

        示例是用户填写前唯一的参考，必须随页面立刻可见；历史消息会改变
        聊天框高度，建页当拍插入会与画布的布局收敛互相触发。
        """
        box=getattr(self,'idea_log',None)
        if box is None or not box.winfo_exists():return
        box.configure(state='normal')
        self._bubble_rows=[];self._bubble_full={};self._bubble_width=int(box.winfo_width() or 0)
        for name in [one for one in box.tag_names() if one.startswith('bubble_')]:
            box.tag_delete(name)
        box.delete('1.0','end')
        self.add_bubble(box,{'role':'assistant','model':'示例模板','text':self.idea_template},'example')
        box.configure(state='normal')
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
