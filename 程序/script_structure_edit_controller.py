# -*- coding: utf-8 -*-
"""剧本结构页「编辑／后退」的内容状态与撤销栈（C8 修复轮，无 Tk）。

把「编辑后自动保存」与「后退一步」从页面回调里抽出来，做成不依赖 Tk、也不直接写项目
文件的控制器：保存动作由注入的 ``save(text)`` 完成，防抖定时由注入的 ``schedule``／
``cancel`` 驱动。UI 只负责把文本框的 ``<<Modified>>`` 事件接到 ``record_edit``，把按钮
接到 ``begin_edit``／``undo``／``save_now``。

撤销栈语义：每次内容变化前把上一版内容压栈；``undo`` 弹出上一版并立即保存。连续后退
直到栈空（回到初始内容），此后 ``can_undo`` 为 False，由 UI 禁用「后退」。
"""
from __future__ import annotations

import threading


class ScriptStructureEditController:
    """单框编辑会话：内容快照撤销栈 + 防抖自动保存。

    ``save(text)`` 是落盘回调；``debounce_ms`` 是编辑后到自动保存的防抖间隔。
    ``schedule(delay_ms, callback)`` 安排一次性回调并返回句柄，``cancel(handle)``
    取消该句柄；默认用 ``threading.Timer``，测试可注入同步调度器直接触发回调。
    """

    def __init__(self, save, debounce_ms, schedule=None, cancel=None):
        if not callable(save):
            raise TypeError('save 必须是可调用函数。')
        self._save = save
        self._debounce_ms = max(0, int(debounce_ms))
        self._schedule = schedule if callable(schedule) else self._default_schedule
        self._cancel = cancel if callable(cancel) else self._default_cancel
        self._undo_stack = []
        self._current = None
        self._initial = None
        self._timer = None

    @staticmethod
    def _default_schedule(delay_ms, callback):
        timer = threading.Timer(max(0, delay_ms) / 1000.0, callback)
        timer.daemon = True
        timer.start()
        return timer

    @staticmethod
    def _default_cancel(timer):
        if timer is not None:
            timer.cancel()

    # ── 只读状态 ──────────────────────────────────────────────────────────
    @property
    def can_undo(self):
        """是否还有可后退的上一步内容。"""
        return bool(self._undo_stack)

    @property
    def current(self):
        return self._current

    @property
    def initial(self):
        return self._initial

    @property
    def pending_save(self):
        """是否还有一次待触发的防抖保存。"""
        return self._timer is not None

    # ── 生命周期 ──────────────────────────────────────────────────────────
    def begin_edit(self, initial_text):
        """进入编辑态：以 ``initial_text`` 为起点，清空撤销栈。"""
        self._cancel_timer()
        self._initial = str(initial_text or '')
        self._current = self._initial
        self._undo_stack = []

    def record_edit(self, text):
        """内容变化：压入上一版、记录新版并安排防抖保存；无变化返回 False。"""
        text = str(text or '')
        if text == self._current:
            return False
        self._undo_stack.append(self._current)
        self._current = text
        self._schedule_save()
        return True

    def undo(self):
        """后退一步：弹出上一版内容并立即保存；无可后退时抛 ValueError。"""
        if not self._undo_stack:
            raise ValueError('没有可后退的内容。')
        self._current = self._undo_stack.pop()
        self._save_now()
        return self._current

    def save_now(self):
        """立即保存当前内容，并取消待触发的防抖。"""
        self._save_now()

    # ── 内部 ──────────────────────────────────────────────────────────────
    def _schedule_save(self):
        self._cancel_timer()
        if self._debounce_ms <= 0:
            self._save_now()
            return
        self._timer = self._schedule(self._debounce_ms, self._on_timer)

    def _on_timer(self):
        self._timer = None
        self._save_now()

    def _save_now(self):
        self._cancel_timer()
        if self._current is not None:
            self._save(self._current)

    def _cancel_timer(self):
        if self._timer is not None:
            self._cancel(self._timer)
            self._timer = None
