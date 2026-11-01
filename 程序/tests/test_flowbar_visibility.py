"""FlowBar.set_visible：隐藏的子控件不占位，重新显示回到创建顺序上的原位置（REQ-S01-46 采风显隐的底座）。"""
import unittest
from tkinter import ttk

import tk_test_support
from responsive_ui import FlowBar


class FlowBarVisibilityTests(unittest.TestCase):
    def setUp(self):
        self.win = tk_test_support.make_root()
        self.addCleanup(self.win.destroy)
        self.win.geometry('640x120')
        self.bar = FlowBar(self.win)
        self.bar.pack(fill='x')
        self.buttons = [ttk.Button(self.bar, text=text) for text in ('发送', '刷新', '质检报告', '采风')]
        for button in self.buttons:
            button.pack(side='left')
        self.pump()

    def pump(self):
        tk_test_support.pump(self.win, .15)

    def positions(self):
        return [(button.winfo_x(), button.winfo_y()) for button in self.buttons]

    def test_hidden_child_takes_no_space_and_returns_to_its_place(self):
        before = self.positions()
        self.assertTrue(all(button.winfo_manager() == 'place' for button in self.buttons))
        self.assertEqual(len({y for _x, y in before}), 1, '四个短按钮在 640 宽里应排成一行')
        self.assertEqual(sorted(before), before, '按创建顺序从左到右排')
        refresh, quality = self.buttons[1], self.buttons[2]
        self.bar.set_visible(refresh, False)
        self.pump()
        self.assertEqual(self.bar.hidden_children, {refresh})
        self.assertEqual(refresh.winfo_manager(), '', '隐藏的按钮不再由 place 管理')
        self.assertEqual((quality.winfo_x(), quality.winfo_y()), before[1], '后面的按钮补上隐藏按钮的位置')
        self.bar.set_visible(refresh, True)
        self.pump()
        self.assertEqual(self.bar.hidden_children, set())
        self.assertEqual(refresh.winfo_manager(), 'place')
        self.assertEqual(self.positions(), before, '重新显示后回到原来的创建顺序位置')

    def test_hidden_children_add_no_rows_when_narrow(self):
        self.win.geometry('120x200')
        self.pump()
        tall = int(self.bar.cget('height'))
        for button in self.buttons[1:]:
            self.bar.set_visible(button, False)
        self.pump()
        self.assertLess(int(self.bar.cget('height')), tall, '隐藏的按钮不占行高')
        self.assertEqual(int(self.bar.cget('height')), self.buttons[0].winfo_reqheight())


if __name__ == '__main__':
    unittest.main()
