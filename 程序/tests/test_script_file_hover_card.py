# -*- coding: utf-8 -*-
"""R1964：剧本准备页文件表悬停预览卡片——列窄截断文件名时，悬停读到磁盘上的完整文件名。"""
import builtins
import os
import sys
import tkinter as tk
from tkinter import ttk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from desktop_file_card import TreeRowCard, script_row_card


class CardWidgetTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.geometry('480x260+0+0')
        self.addCleanup(self.root.destroy)
        self.tree = ttk.Treeview(self.root, show='tree', height=4)
        self.tree.pack(fill='x')
        self.details = {'a': '摄影侠_项目设定_Google_20261024.md\n状态：已确认\n位置：x'}
        self.tree.insert('', 'end', iid='a', text='a')
        self.card = TreeRowCard(self.tree, self.details.get)
        self.card.delay_ms = 0
        self.root.update()

    def hover(self):
        _x, y, _w, h = self.tree.bbox('a')
        self.tree.event_generate('<Motion>', x=10, y=y + h // 2)
        self.root.update()

    def test_card_shows_full_name_as_title_and_details_below(self):
        denied = AssertionError('悬停只能使用已加载数据，不得读取磁盘')
        with mock.patch.object(builtins, 'open', side_effect=denied), \
                mock.patch.object(os, 'scandir', side_effect=denied):
            self.hover()
        labels = self.card._window.winfo_children()
        self.assertEqual(len(labels), 2)
        self.assertEqual(labels[0].cget('text'), '摄影侠_项目设定_Google_20261024.md')
        self.assertIn('bold', str(labels[0].cget('font')))
        self.assertEqual(labels[1].cget('text'), '状态：已确认\n位置：x')

    def test_card_without_detail_has_title_only_and_hides_on_leave(self):
        self.details['a'] = '只有标题.md'
        self.hover()
        self.assertEqual(len(self.card._window.winfo_children()), 1)
        self.tree.event_generate('<Leave>')
        self.root.update()
        self.assertIsNone(self.card._window)

    def test_card_stays_visible_under_app_window_placement(self):
        """R1982：真实程序给每个新窗口装 Map→grab／透明；卡片弹出后须保持显示、可见、不抢 grab。"""
        import time
        import ui_theme
        ui_theme.install_window_placement(self.root)
        self.hover()
        shown = self.card._window
        self.assertIsNotNone(shown)
        end = time.monotonic() + .3
        while time.monotonic() < end:  # 让 Map、grab 与随之补发的 Leave/Enter 都跑完
            self.root.update()
        self.assertIs(self.card._window, shown, '卡片弹出后被自身引发的离开事件收掉')
        self.assertTrue(shown.winfo_exists())
        self.assertIsNone(shown.grab_status(), '卡片不得持有 grab')
        self.assertEqual(float(shown.attributes('-alpha')), 1.0, '卡片仍是透明的')


class CardTextTests(unittest.TestCase):
    def card(self, row, label='', root='D:/proj'):
        return script_row_card(row, label, '2026-10-24 00:25:00', Path(root))

    def test_title_is_real_file_name_and_display_name_shown_when_different(self):
        path = 'D:/proj/创意_a/Google/Gemini/项目设定/摄影侠_项目设定_gemini-4_20261024.md'
        row = SimpleNamespace(item_id=path, name='摄影侠_项目设定_Google_20261024.md')
        lines = self.card(row, '已确认').split('\n')
        self.assertEqual(lines[0], '摄影侠_项目设定_gemini-4_20261024.md')
        self.assertEqual(lines[1], '列表显示：摄影侠_项目设定_Google_20261024.md')
        self.assertIn('状态：已确认', lines)
        self.assertIn('修改时间：2026-10-24 00:25:00', lines)
        self.assertEqual(lines[-1], '位置：创意_a/Google/Gemini/项目设定')

    def test_same_name_and_no_label_skip_optional_lines(self):
        row = SimpleNamespace(item_id='D:/proj/剧本_甲.md', name='剧本_甲.md')
        lines = self.card(row).split('\n')
        self.assertEqual(lines, ['剧本_甲.md', '修改时间：2026-10-24 00:25:00', '位置：.'])

    def test_path_outside_project_falls_back_to_absolute_folder(self):
        row = SimpleNamespace(item_id='E:/other/x.md', name='x.md')
        self.assertTrue(self.card(row).split('\n')[-1].startswith('位置：'))


if __name__ == '__main__':
    unittest.main()
