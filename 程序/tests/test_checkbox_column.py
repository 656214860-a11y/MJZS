# -*- coding: utf-8 -*-
"""CheckboxColumn 公共勾选组件回归。运行：python test_checkbox_column.py"""
import os, sys, unittest
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); os.chdir(HERE)


class CheckboxColumnTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def test_toggle_and_toggle_all(self):
        if self.tk is None:
            self.skipTest("tkinter 不可用")
        from tkinter import ttk
        from responsive_ui import CheckboxColumn, configure_check_column
        win = self.tk.Tk(); win.withdraw()
        self.addCleanup(win.destroy)
        tree = ttk.Treeview(win, columns=('name',), show='tree headings')
        tree.pack()
        configure_check_column(tree)
        off = self.tk.PhotoImage(width=10, height=10)
        on = self.tk.PhotoImage(width=10, height=10)
        state = {}
        for i in ('A', 'B', 'C'):
            tree.insert('', 'end', iid=i, text='', values=(i,))
        box = CheckboxColumn(tree, [off, on], lambda i: state.get(i, False), lambda i, v: state.__setitem__(i, v))
        self.assertEqual(tree.heading('#0')['image'], '')
        box.toggle('A')
        self.assertTrue(state['A'])
        self.assertEqual(tree.item('A')['image'][0], str(on))
        self.assertEqual(tree.heading('#0')['image'], str(off))  # 仅勾选一项，未全选
        box.toggle_all()
        self.assertTrue(all(state.get(i) for i in ('A', 'B', 'C')))
        self.assertEqual(tree.heading('#0')['image'], str(on))   # 已全选
        box.toggle_all()
        self.assertFalse(any(state.get(i) for i in ('A', 'B', 'C')))
        self.assertEqual(tree.heading('#0')['image'], str(off))  # 已取消全选

    def test_content_box_click_rules(self):
        """文本格单击勾选/再点取消；带链接的格子先勾选再打开，已勾选时只打开不取消。"""
        if self.tk is None:
            self.skipTest("tkinter 不可用")
        from tkinter import ttk
        from responsive_ui import CheckboxColumn, bind_row_toggle, configure_check_column
        from cell_hover import CellHover
        win = self.tk.Tk(); win.geometry('760x220+60+60')
        self.addCleanup(win.destroy)
        tree = ttk.Treeview(win, columns=('file', 'content', 'time'), show='tree headings', height=2, selectmode='browse')
        for column, label in (('file', '文件'), ('content', '文件内容(点击查看)'), ('time', '时间')):
            tree.heading(column, text=label); tree.column(column, width=140)
        tree.pack(fill='both', expand=True)
        configure_check_column(tree)
        off = self.tk.PhotoImage(width=10, height=10)
        on = self.tk.PhotoImage(width=10, height=10)
        state = {}; opened = []
        for item in ('A', 'B'):
            tree.insert('', 'end', iid=item, text='', values=(item, item + ' 正文', '09-19 20:00'))
        box = CheckboxColumn(tree, [off, on], lambda i: state.get(i, False), lambda i, v: state.__setitem__(i, v))
        link_cols = ('#0', '#2')  # #2 是「文件内容(点击查看)」带链接的格子
        def command(row, col):
            if col == '#0':
                box.toggle(row)
            else:
                opened.append((row, col))
        tree.cell_hover = CellHover(tree, link_cols, command, checked=lambda row: state.get(row, False), toggle=lambda row: box.toggle(row))
        bind_row_toggle(tree, lambda row: box.toggle(row), link_cols)
        win.update()
        def click(row, column):
            x, y, width, height = tree.bbox(row, column)
            tree.event_generate('<Button-1>', x=int(x + width // 2), y=int(y + height // 2))
            win.update()
        click('A', '#1')  # 文本格：勾选本行
        self.assertTrue(state.get('A')); self.assertEqual(opened, [])
        click('A', '#1')  # 再次单击同一文本格：取消勾选
        self.assertFalse(state.get('A'))
        click('A', '#3')  # 另一文本格同样可勾选
        self.assertTrue(state.get('A'))
        click('A', '#2')  # 带链接的格子：未勾选 → 先勾选再打开
        self.assertTrue(state.get('A')); self.assertEqual(opened, [('A', '#2')])
        click('A', '#2')  # 已勾选 → 只打开，不取消勾选
        self.assertTrue(state.get('A')); self.assertEqual(len(opened), 2)
        click('B', '#2')  # 另一行未勾选 → 勾选并打开，A 保持不变
        self.assertTrue(state.get('B')); self.assertTrue(state.get('A'))
        click('A', '#0')  # 勾选列：只切换勾选，不当作打开
        self.assertFalse(state.get('A')); self.assertEqual(len(opened), 3)
        click('A', '#0')
        self.assertTrue(state.get('A')); self.assertEqual(len(opened), 3)


if __name__ == '__main__':
    unittest.main(verbosity=2)
