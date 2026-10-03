"""无 Tk 的桌面自动流程调度器。

桌面只注入 ``after`` / ``after_cancel`` 与阶段轮询回调；本模块统一周期任务
的重排、取消、异常兜底，以及各自动流程的到期轮询判断。
"""


# 后台任务生命周期的唯一迁移清单。每一项都必须证明同一代次覆盖提交、替换、
# 取消、成功、失败和迟到交付拒绝；含连续进度消息的入口还必须把进度与最终结果
# 绑定到同一 ticket。状态只记录已落地的事实，待迁移项不得借清单宣称已收口。
BACKGROUND_TASK_MIGRATION = (
    {'entry': 'Desktop.async_', 'category': 'final-result', 'state': 'migrated'},
    {'entry': 'auto_edit', 'category': 'final-result', 'state': 'migrated'},
    {'entry': 'auto_handoff', 'category': 'final-result', 'state': 'migrated'},
    {'entry': 'auto_video', 'category': 'progress-and-result', 'state': 'migrated'},
    {'entry': 'auto_asset', 'category': 'progress-and-result', 'state': 'migrated'},
    {'entry': 'auto_keyframe', 'category': 'progress-and-result', 'state': 'migrated'},
    {'entry': 'previs_jobs', 'category': 'special-process', 'state': 'migrated'},
    {'entry': 'cloud_monitor', 'category': 'cross-page-monitor', 'state': 'migrated'},
)


class DesktopAutomationScheduler:
    """管理桌面拥有的周期回调，不持有窗口或阶段状态。"""

    def __init__(self, *, schedule_after, cancel_scheduled, is_stopping):
        self._schedule_after = schedule_after
        self._cancel_scheduled = cancel_scheduled
        self._is_stopping = is_stopping
        self._tasks = {}

    def start(self, name, interval_ms, callback, *, on_error, remember_timer):
        self.cancel(name)
        self._tasks[name] = {
            'interval_ms': interval_ms,
            'callback': callback,
            'on_error': on_error,
            'remember_timer': remember_timer,
            'timer': None,
        }
        self._schedule(name)

    def cancel(self, name):
        task = self._tasks.pop(name, None)
        if task is None:
            return
        timer = task['timer']
        if timer:
            try:
                self._cancel_scheduled(timer)
            except Exception:
                pass
        task['remember_timer'](None)

    def cancel_all(self):
        for name in tuple(self._tasks):
            self.cancel(name)

    def run_due(self, *, now, due_at, delay_seconds, allowed, set_due, poll,
                on_error, handled_exceptions):
        """到期且允许时才轮询；先推进下次到期时间，失败也保留节流。"""
        if not allowed() or now < due_at():
            return False
        set_due(now + delay_seconds)
        try:
            poll()
        except handled_exceptions as exc:
            on_error(exc)
            return False
        return True

    def _schedule(self, name):
        task = self._tasks.get(name)
        if task is None or self._is_stopping():
            return
        timer = self._schedule_after(task['interval_ms'], lambda: self._run(name))
        task['timer'] = timer
        task['remember_timer'](timer)

    def _run(self, name):
        task = self._tasks.get(name)
        if task is None:
            return
        task['timer'] = None
        task['remember_timer'](None)
        try:
            task['callback']()
        except Exception as exc:
            task['on_error'](exc)
        finally:
            if name in self._tasks:
                self._schedule(name)


class BackgroundTaskLifecycle:
    """桌面单一主动后台任务的代次、取消与收尾判定。

    任意线程都可能在逻辑取消后才返回；本对象不尝试强杀 Python 线程，
    而是让主线程只接纳当前代次的结果，避免关闭窗口或中断请求后触发迟到 UI 回调。
    """

    def __init__(self):
        self._active_ticket = None
        self._last = None

    def submit(self, ticket):
        self.cancel()
        self._active_ticket = ticket
        self._last = {'ticket': ticket, 'state': 'running'}
        return ticket

    def accepts(self, ticket):
        return self._active_ticket == ticket

    def finish(self, ticket, *, succeeded):
        if not self.accepts(ticket):
            return False
        self._active_ticket = None
        self._last = {'ticket': ticket, 'state': 'succeeded' if succeeded else 'failed'}
        return True

    def cancel(self, ticket=None):
        if self._active_ticket is None or (ticket is not None and ticket != self._active_ticket):
            return False
        cancelled = self._active_ticket
        self._active_ticket = None
        self._last = {'ticket': cancelled, 'state': 'cancelled'}
        return True

    def snapshot(self):
        return dict(self._last) if self._last is not None else None
