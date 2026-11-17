"""NoticeDialog（R2005）：多行告知窗保留换行、只有一个“知道了”。含 Tk，由运行器自动隐藏桌面执行。"""
from __future__ import annotations

import tkinter as tk
import unittest

from ui_widgets import NoticeDialog


class NoticeDialogTests(unittest.TestCase):
    def test_keeps_lines_and_closes_with_single_action(self):
        root = tk.Tk()
        self.addCleanup(root.destroy)
        dialog = NoticeDialog(root, '提示', '第一行\n第二行')
        root.update()
        labels = [w.cget('text') for w in dialog.content.winfo_children() if 'text' in w.keys()]
        self.assertTrue(any('第一行\n第二行' in text for text in labels), labels)
        buttons = [w for w in dialog.actions.winfo_children() if w.winfo_class() == 'TButton']
        self.assertEqual([b.cget('text') for b in buttons], ['知道了'])
        buttons[0].invoke()
        root.update()
        self.assertFalse(dialog.winfo_exists())


if __name__ == '__main__':
    unittest.main()
