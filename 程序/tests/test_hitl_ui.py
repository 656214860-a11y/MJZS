# -*- coding: utf-8 -*-
"""HITL 卡片 Tk 渲染（R3119）：审批门三按钮、选择卡单选回填。

运行：python tests/test_hitl_ui.py（真 Tk；运行器会切隐藏桌面）
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from domain import hitl
from skip_reasons import PLATFORM_TKINTER
from ui import ui_hitl


def _buttons(widget):
    found = []
    for child in widget.winfo_children():
        if child.winfo_class() in ('TButton', 'Button'):
            found.append(child)
        else:
            found.extend(_buttons(child))
    return found


class HitlUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def setUp(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        self.win = self.tk.Tk()
        self.win.withdraw()
        self.addCleanup(self.win.destroy)

    def test_approval_gate_three_buttons_emit_decisions(self):
        seen = []
        frame = ui_hitl.build_approval_gate(
            self.win, hitl.make_request('approve', {'title': '确认采用'}), seen.append)
        buttons = _buttons(frame)
        self.assertEqual([button.cget('text') for button in buttons], ['确认采用', '拒绝', '重新生成'])
        buttons[0].invoke()
        buttons[2].invoke()
        self.assertEqual([item['decision'] for item in seen], ['approve', 'regenerate'])

    def test_choice_card_emits_selected_candidate(self):
        seen = []
        frame = ui_hitl.build_choice_card(self.win, hitl.make_request('choice', {
            'title': '选结局', 'candidates': [{'label': '悲剧'}, {'label': '喜剧'}]}), seen.append)
        radios = [child for child in frame.winfo_children()[1].winfo_children()
                  if child.winfo_class() == 'TRadiobutton']
        self.assertEqual([radio.cget('text') for radio in radios], ['悲剧', '喜剧'])
        radios[1].invoke()
        _buttons(frame)[0].invoke()
        self.assertEqual(seen[0]['decision'], 'edit')
        self.assertEqual(seen[0]['payload']['selected'], {'label': '喜剧'})


if __name__ == '__main__':
    unittest.main()
