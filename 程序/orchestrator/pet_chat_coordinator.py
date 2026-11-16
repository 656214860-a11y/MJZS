"""聊天交互协调：只拥有待单击任务，不持有 Tk、Pet 或云窗状态。

调度与视图动作经回调 adapter 注入；生产由 Pet 装配，测试使用内存队列。
chat 引用和实际可见性刻意分开：菜单按引用，单击与守护按可见性。
"""


class ChatCoordinator:
    def __init__(self, *, schedule, cancel, delay, visible, open_chat,
                 close_chat, mute, on_error):
        self._schedule = schedule
        self._cancel = cancel
        self._delay = delay
        self._visible = visible
        self._open = open_chat
        self._close = close_chat
        self._mute = mute
        self._on_error = on_error
        self._pending = None

    @property
    def pending(self):
        return self._pending

    def cancel_pending(self):
        job, self._pending = self._pending, None
        if job is not None:
            self._cancel(job)
        return job

    def request_single(self):
        self.cancel_pending()
        try:
            self._pending = self._schedule(self._delay, self.flip)
        except Exception as exc:
            self._on_error('click', str(exc))
            return self.flip()
        return self._pending

    def flip(self, at=None):
        # 与旧实现一致：这里只清引用；不假设迟到回调已被 Tk 撤销。
        self._pending = None
        if self._visible():
            self._mute(at=at)
            return self._close()
        return self._open()

    def request_double(self):
        self.cancel_pending()
        return self._open()

    def toggle(self, has_chat):
        return self._close() if has_chat else self._open()

    def guard(self, blocked):
        if not blocked or not self._visible():
            return False
        self._close()
        return True
