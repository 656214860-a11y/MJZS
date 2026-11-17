# -*- coding: utf-8 -*-
"""长任务进度卡（R3136）：进度推进、完成回调、转后台按钮。

运行：python tests/test_background_task.py（真 Tk；运行器会切隐藏桌面）
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skip_reasons import PLATFORM_TKINTER
from ui import ui_task_progress


class BackgroundTaskTests(unittest.TestCase):
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

    def test_progress_updates_and_finishes_once(self):
        background, finished = [], []
        frame, update = ui_task_progress.build_task_progress(
            self.win, title='批量首帧', total=10,
            on_background=lambda: background.append(True),
            on_finish=lambda: finished.append(True))
        self.assertEqual(update(5), 5)
        self.assertEqual(finished, [])
        self.assertEqual(update(10), 10)
        self.assertEqual(finished, [True])
        buttons = {child.cget('text'): child for child in frame.winfo_children()[-1].winfo_children()
                   if child.winfo_class() == 'TButton'}
        buttons['转后台运行'].invoke()
        self.assertEqual(background, [True])


if __name__ == '__main__':
    unittest.main()
