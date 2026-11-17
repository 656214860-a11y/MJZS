# -*- coding: utf-8 -*-
"""参数微调面板（R3136）：温度/步数/画面比例读取与写回。

运行：python tests/test_param_panel.py（真 Tk；运行器会切隐藏桌面）
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skip_reasons import PLATFORM_TKINTER
from ui import ui_param_panel


class ParamPanelTests(unittest.TestCase):
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

    def test_panel_reads_initial_and_reflects_writes(self):
        frame, state = ui_param_panel.build_param_panel(
            self.win, {'temperature': 1.5, 'steps': 30, 'aspect': '9:16'})
        self.assertEqual(state['values'](), {'temperature': 1.5, 'steps': 30, 'aspect': '9:16'})
        state['steps'].set(15)
        self.assertEqual(state['values']()['steps'], 15)
        state['aspect'].set('1:1')
        self.assertEqual(state['values']()['aspect'], '1:1')
        self.assertEqual(len(frame.winfo_children()), 3, '温度/步数/比例各一行')


if __name__ == '__main__':
    unittest.main()
