"""Compact UI surfaces keep full text accessible and restore idle progress."""
import builtins
import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from tkinter.font import Font
import unittest
from unittest import mock

from ui_widgets import BusyState, EllipsisLabel, TreeRowTooltip


class CompactWidgetTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.geometry('480x260+0+0')
        self.addCleanup(self.root.destroy)
        self.root.update_idletasks()

    def tooltip_text(self, tooltip):
        self.assertIsNotNone(tooltip._window)
        labels = tooltip._window.winfo_children()
        self.assertEqual(len(labels), 1)
        return str(labels[0].cget('text'))

    def test_ellipsis_tracks_real_width_and_tooltip_keeps_full_text(self):
        full_text = '项目目录：D:/demo/一个完整项目目录/剧本与角色资料'
        label = EllipsisLabel(self.root, text=full_text)
        label.place(x=0, y=0, width=112, height=32)
        self.root.update_idletasks()
        font = Font(root=label, font=label.cget('font') or
                    ttk.Style(label).lookup(label.cget('style') or 'TLabel', 'font'))
        shortened = str(label.cget('text'))
        self.assertTrue(shortened.endswith('…'))
        self.assertNotEqual(shortened, full_text)
        self.assertLessEqual(font.measure(shortened), label.winfo_width())

        label.tooltip.delay_ms = 0
        label.event_generate('<Enter>', x=4, y=4)
        self.root.update()
        self.assertEqual(self.tooltip_text(label.tooltip), full_text)
        label.event_generate('<Leave>')
        self.root.update()
        self.assertIsNone(label.tooltip._window)

        width = font.measure(full_text) + 24
        self.root.geometry(f'{max(480, width)}x260+0+0')
        label.place_configure(width=width)
        self.root.update_idletasks()
        self.assertEqual(str(label.cget('text')), full_text)

        replacement = '新的项目路径：D:/demo/已切换项目/全部附件与人物资料'
        label.place_configure(width=112)
        self.root.update_idletasks()
        label.set_text(replacement)
        self.assertTrue(str(label.cget('text')).endswith('…'))
        self.assertLessEqual(font.measure(str(label.cget('text'))), label.winfo_width())
        label.event_generate('<Enter>', x=4, y=4)
        self.root.update()
        self.assertEqual(self.tooltip_text(label.tooltip), replacement)

        label.place_configure(width=1)
        self.root.update_idletasks()
        self.assertEqual(str(label.cget('text')), '')

    def test_tree_tooltip_changes_rows_without_disk_io_and_hides_on_leave(self):
        details = {'first': '第一个项目：D:/projects/first',
                   'second': '第二个项目：D:/projects/second'}
        tree = ttk.Treeview(self.root, show='tree', height=5)
        tree.pack(fill='x')
        for row in details:
            tree.insert('', 'end', iid=row, text=row)
        lookup = mock.Mock(side_effect=details.get)
        tooltip = TreeRowTooltip(tree, lookup)
        tooltip.delay_ms = 0
        self.root.update_idletasks()

        def hover(row):
            _x, y, _width, height = tree.bbox(row)
            tree.event_generate('<Motion>', x=10, y=y + height // 2)
            self.root.update()

        denied = AssertionError('悬停只能使用已加载数据，不得读取磁盘')
        with mock.patch.object(builtins, 'open', side_effect=denied) as file_open, \
                mock.patch.object(Path, 'open', side_effect=denied) as path_open, \
                mock.patch.object(Path, 'read_text', side_effect=denied) as read_text, \
                mock.patch.object(Path, 'read_bytes', side_effect=denied) as read_bytes, \
                mock.patch.object(os, 'scandir', side_effect=denied) as scandir, \
                mock.patch.object(os, 'listdir', side_effect=denied) as listdir:
            hover('first')
            first_window = tooltip._window
            self.assertEqual(self.tooltip_text(tooltip), details['first'])
            lookup.assert_called_with('first')
            hover('second')
            self.assertEqual(self.tooltip_text(tooltip), details['second'])
            lookup.assert_called_with('second')
            self.assertFalse(first_window.winfo_exists())

            tree.event_generate('<Leave>')
            self.root.update()
            self.assertIsNone(tooltip._window)
            self.assertIsNone(tooltip._job)
            hover('first')
            blank_y = tree.winfo_height() - 2
            self.assertEqual(tree.identify_row(blank_y), '')
            tree.event_generate('<Motion>', x=10, y=blank_y)
            self.root.update()
            self.assertIsNone(tooltip._window)
            self.assertIsNone(tooltip._job)
        for disk_call in (file_open, path_open, read_text, read_bytes, scandir, listdir):
            disk_call.assert_not_called()

    def test_busy_state_restores_spinner_and_controls_each_cycle(self):
        from ui_motion import Spinner
        status = tk.StringVar(self.root, value='就绪')
        spinner = Spinner(self.root)
        button = ttk.Button(self.root, text='执行')
        button.pack()
        busy = BusyState(status, spinner=spinner)
        for cycle in range(2):
            with self.subTest(cycle=cycle):
                self.assertTrue(busy.set_busy(True, message='运行中', controls=(button,)))
                self.root.update_idletasks()
                self.assertTrue(spinner.running)
                self.assertEqual(status.get(), '运行中')
                self.assertTrue(button.instate(['disabled']))
                self.assertTrue(busy.busy)
                self.assertFalse(busy.set_busy(False))
                self.root.update()
                self.assertFalse(spinner.running)
                self.assertTrue(button.instate(['!disabled']))
                self.assertFalse(busy.busy)


if __name__ == '__main__':
    unittest.main()
