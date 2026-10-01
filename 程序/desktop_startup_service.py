"""无 Tk 的桌面首帧启动编排。

窗口创建和事件绑定仍归 ``desktop.Desktop``；这里仅保存由视图注入的
调度器与项目选择回调，从而让首帧时序不依赖 Tk 进行验证。
"""
from __future__ import annotations


class DesktopStartupController:
    """保持“延迟首帧 → 空闲项目选择”的既有启动顺序。"""

    def __init__(self, *, schedule_after, schedule_idle, cancel_scheduled,
                 is_stopping, before_project_choice, choose_project,
                 remember_timer):
        self._schedule_after = schedule_after
        self._schedule_idle = schedule_idle
        self._cancel_scheduled = cancel_scheduled
        self._is_stopping = is_stopping
        self._before_project_choice = before_project_choice
        self._choose_project = choose_project
        self._remember_timer = remember_timer
        self._timer = None

    def start(self, delay_ms=150):
        """在首窗绘制前登记一次项目选择，而不直接执行页面构建。"""
        self._set_timer(self._schedule_after(delay_ms, self._after_first_paint))
        return self._timer

    def cancel(self):
        """收回尚未执行的首帧启动回调；窗口销毁时可安全重复调用。"""
        if self._timer is not None:
            self._cancel_scheduled(self._timer)
        self._set_timer(None)

    def _after_first_paint(self):
        self._set_timer(None)
        if self._is_stopping():
            return
        self._before_project_choice()
        self._set_timer(self._schedule_idle(self._choose_project))

    def _set_timer(self, timer):
        self._timer = timer
        self._remember_timer(timer)
