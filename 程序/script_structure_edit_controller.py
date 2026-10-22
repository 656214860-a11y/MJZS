# -*- coding: utf-8 -*-
"""剧本结构页「编辑／后退／恢复／保存」的内容状态与撤销栈（无 Tk）。

不依赖 Tk、也不直接写项目文件：落盘由注入的 ``save(text)`` 完成。UI 把文本框的
``<<Modified>>`` 接到 ``record_edit``，把按钮接到 ``begin_edit``／``undo``／``save_now``。

用户 R1862 要求取消自动保存：编辑与后退只改内存里的当前内容并标记未保存，
只有点「保存」（``save_now``）才落盘。

撤销栈语义：每次内容变化前把上一版内容压栈；``undo`` 弹出上一版。连续后退直到栈空
（回到初始内容），此后 ``can_undo`` 为 False，由 UI 禁用「后退」。
"""
from __future__ import annotations


class ScriptStructureEditController:
    """单框编辑会话：内容快照撤销栈 + 手动保存。"""

    def __init__(self, save):
        if not callable(save):
            raise TypeError('save 必须是可调用函数。')
        self._save = save
        self._undo_stack = []
        self._current = None
        self._initial = None
        self._saved = None

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
    def dirty(self):
        """当前内容是否与上次落盘（或进入编辑时）的内容不同。"""
        return self._current is not None and self._current != self._saved

    # ── 生命周期 ──────────────────────────────────────────────────────────
    def begin_edit(self, initial_text):
        """进入编辑态：以 ``initial_text`` 为起点，清空撤销栈。"""
        self._initial = str(initial_text or '')
        self._current = self._saved = self._initial
        self._undo_stack = []

    def record_edit(self, text):
        """内容变化：压入上一版并记录新版（不落盘）；无变化返回 False。"""
        text = str(text or '')
        if text == self._current:
            return False
        self._undo_stack.append(self._current)
        self._current = text
        return True

    def undo(self):
        """后退一步：弹出上一版内容（不落盘）；无可后退时抛 ValueError。"""
        if not self._undo_stack:
            raise ValueError('没有可后退的内容。')
        self._current = self._undo_stack.pop()
        return self._current

    def save_now(self):
        """把当前内容落盘。"""
        if self._current is None:
            raise ValueError('请先点击“编辑”。')
        self._save(self._current)
        self._saved = self._current
