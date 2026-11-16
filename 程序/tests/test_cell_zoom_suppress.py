# -*- coding: utf-8 -*-
"""R3012：缩略图悬停放大——点击选择行后抑制放大，直到指针离开再进入（不再点完又弹）。"""
import time
import tkinter as tk
from tkinter import ttk
import unittest

from cell_hover import CellImages


def _image(root):
    return tk.PhotoImage(master=root, width=16, height=16)


class CellZoomSuppressTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.geometry('400x260+0+0')
        self.addCleanup(self.root.destroy)
        self.tree = ttk.Treeview(self.root, columns=('#1', '#2'), show='tree headings', height=6)
        self.tree.pack(fill='both', expand=True)
        self.tree.insert('', 'end', iid='r1', text='', values=('', '甲'))
        self.root.update_idletasks()
        self.root.update()
        self.root.focus_force()
        self.images = CellImages(self.tree, ('#1',), provider=lambda row, column: (_image(self.root), None),
                                 zoom=lambda row, column: _image(self.root))
        self.images.refresh()
        self.root.update()
        self.label = self.images.labels[('r1', '#1')]

    def pump(self, seconds=0.2):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.root.update()

    def test_click_suppresses_zoom_until_leave_and_reenter(self):
        self.label.event_generate('<Enter>')
        self.root.update()
        self.assertEqual(self.images.zoom_key, ('r1', '#1'))
        self.label.event_generate('<Button-1>')
        self.root.update()
        self.assertIsNone(self.images.zoom_key)         # 点击即收
        self.assertTrue(self.images._zoom_suppress)
        self.label.event_generate('<Enter>')
        self.root.update()
        self.assertIsNone(self.images.zoom_key)         # 指针没离开过：仍抑制
        self.label.event_generate('<Leave>')
        self.root.update()
        self.assertFalse(self.images._zoom_suppress)
        self.label.event_generate('<Enter>')
        self.root.update()
        self.assertEqual(self.images.zoom_key, ('r1', '#1'))   # 离开再进入：恢复放大


if __name__ == '__main__':
    unittest.main()
