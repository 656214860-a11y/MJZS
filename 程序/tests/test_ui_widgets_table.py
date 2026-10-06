"""统一表格组件的 Tk 行为回归。"""
from __future__ import annotations

import tkinter as tk
import unittest

from skip_reasons import PLATFORM_TK_DISPLAY
from ui_widgets import DataTable


class DataTableTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
            self.root.withdraw()
        except tk.TclError as exc:
            self.skipTest(PLATFORM_TK_DISPLAY + ': ' + str(exc))

    def tearDown(self):
        if hasattr(self, 'root'):
            self.root.destroy()

    def test_columns_scrollbars_empty_state_and_selection_use_one_component(self):
        selected = []
        table = DataTable(self.root, columns=[('name', '名称', 120)],
                          empty_text='暂无项目', on_select=selected.append)
        table.pack(fill='both', expand=True)
        self.root.update()
        self.assertEqual(list(table.tree['columns']), ['name'])
        self.assertEqual(table.vertical_scrollbar.winfo_manager(), 'grid')
        self.assertEqual(table.horizontal_scrollbar.winfo_manager(), 'grid')
        self.assertEqual(table.empty_label.winfo_manager(), 'grid')
        table.tree.insert('', 'end', iid='two', values=('beta',))
        table.tree.insert('', 'end', iid='one', values=('alpha',))
        table.refresh_empty_state()
        table.tree.selection_set('one')
        table.tree.event_generate('<<TreeviewSelect>>')
        self.root.update()
        self.assertEqual(table.empty_label.winfo_manager(), '')
        self.assertEqual(selected[-1], ('one',))

    def test_heading_sort_reorders_rows_and_toggles_direction(self):
        table = DataTable(self.root, columns=[('name', '名称', 120)])
        table.pack()
        table.tree.insert('', 'end', iid='two', values=('beta',))
        table.tree.insert('', 'end', iid='one', values=('alpha',))
        table.sort_by('name')
        self.assertEqual(table.tree.get_children(), ('one', 'two'))
        table.sort_by('name')
        self.assertEqual(table.tree.get_children(), ('two', 'one'))

    def test_empty_text_disables_overlay_without_hiding_header(self):
        table = DataTable(self.root, columns=[('name', '项目剧本', 120)], empty_text='')
        table.pack()
        for populated in (False, True, False):
            if populated:
                table.tree.insert('', 'end', iid='script', values=('剧本.md',))
            else:
                table.tree.delete(*table.tree.get_children())
            table.refresh_empty_state()
            self.root.update()
            self.assertEqual(table.empty_label.winfo_manager(), '')
            self.assertEqual(table.tree.winfo_manager(), 'grid')
            self.assertEqual(table.tree.heading('name')['text'], '项目剧本')
