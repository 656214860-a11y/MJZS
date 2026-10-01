"""无 Tk 的桌面自动流程调度器。

桌面只注入 ``after`` / ``after_cancel`` 与阶段轮询回调；本模块统一周期任务
的重排、取消、异常兜底，以及各自动流程的到期轮询判断。
"""


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
