# -*- coding: utf-8 -*-
"""剧本结构页「编辑」的内容基线与自动保存判定（无 Tk）。

不依赖 Tk、也不直接写项目文件：落盘由注入的 ``save(text)`` 完成。UI 把文本框的
``<<Modified>>`` 接到防抖调度，把「立即保存／复原全文／退出」接到 ``save``。

R2724 反转 R1862 的手动保存契约：编辑改为停止输入后自动落盘，撤销栈改用 Tk 原生
``edit_undo``／``edit_redo``（一步一步，与文本框一致），本控制器只保留「进入编辑时
的原文」「上次落盘内容」与「是否真的变化」三个事实，不再持有内容快照栈。
"""
from __future__ import annotations


class ScriptStructureEditController:
    """单框编辑会话：初始原文 + 落盘基线 + 变化判断（无 Tk）。"""

    def __init__(self, save):
        if not callable(save):
            raise TypeError('save 必须是可调用函数。')
        self._save = save
        self._initial = None
        self._saved = None

    # ── 只读状态 ──────────────────────────────────────────────────────────
    @property
    def initial(self):
        """进入编辑时的原文；未进入编辑为 None（供「复原全文」与禁用判断）。"""
        return self._initial

    @property
    def saved(self):
        """最近一次落盘（未落盘过则为进入编辑时）的内容。"""
        return self._saved

    def dirty(self, text):
        """``text`` 与上次落盘内容是否不同（未进入编辑恒为 False）。"""
        return self._saved is not None and str(text or '') != self._saved

    # ── 生命周期 ──────────────────────────────────────────────────────────
    def begin_edit(self, initial_text):
        """进入编辑态：记录初始原文与已落盘基线。"""
        self._initial = str(initial_text or '')
        self._saved = self._initial

    def save(self, text):
        """把 ``text`` 落盘并更新基线；与上次落盘相同则不写盘，返回 False。"""
        if self._saved is None:
            raise ValueError('请先点击“编辑”。')
        text = str(text or '')
        if text == self._saved:
            return False
        self._save(text)
        self._saved = text
        return True
