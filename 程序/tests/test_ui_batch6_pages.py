"""UI 批次 6：资产／连贯性／分镜页的表格、卡片、空态与 800×600 窄窗。

真 Tk 根窗口量几何：资产页与首帧页主容器 800×600 下 requested width 不超过窗口宽，
表格实际宽度跟随内容区；卡片内边距与表头字体取自 ui_tokens。
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM))

import asset_detail
import pet_state
from desktop_page_registry import PAGE_SITES
from skip_reasons import PLATFORM_TKINTER
from ui_tokens import (FONTS, SPACING, TABLE_EMPTY_PADDING, TABLE_HEADER_FONT,
                       TABLE_ROW_FONT)
from ui_widgets import Card


def _make_project(root, shots=1):
    project = Path(root) / 'p'
    (project / 'episode' / 'frames').mkdir(parents=True)
    (project / 'episode' / 'assets.json').write_text('{}', encoding='utf-8')
    rows = []
    if shots:
        rows.append({'id': 'SH001', 'title': '镜头', 'duration': 5,
                     'characters': ['CHAR_001'], 'location': 'LOC_001',
                     'frame': 'frames/SH001.png', 'video_prompt': '画面',
                     'frame_prompt': '窗边的猫', 'dialogue': []})
    episode = {'episode_id': 'EP001', 'title': 'T', 'shots': rows}
    (project / 'episode' / 'episode.json').write_text(
        json.dumps(episode, ensure_ascii=False), encoding='utf-8')
    (project / 'config.json').write_text(json.dumps({
        'episode_dir': str(project / 'episode'),
        'episode_file': str(project / 'episode' / 'episode.json'),
        'budget_seconds': 0, 'reserve_seconds': 0, 'live_enabled': False,
    }), encoding='utf-8')
    storyboard = project / 'storyboard' / '分镜拆分'
    storyboard.mkdir(parents=True)
    (storyboard / 'episode.json').write_text(
        json.dumps(episode, ensure_ascii=False), encoding='utf-8')
    (project / 'ui_settings.json').write_text(json.dumps({
        'adopted_storyboards': ['storyboard/分镜拆分/episode.json'],
        'frame_json': 'storyboard/分镜拆分/episode.json',
    }, ensure_ascii=False), encoding='utf-8')
    return project


def _descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from _descendants(child)


def _font_shape(widget, declared):
    actual = tkfont.Font(root=widget, font=declared).actual()
    return actual['family'], int(actual['size']), actual['weight']


def _expected_font(declared):
    return declared[0], int(declared[1]), declared[2] if len(declared) > 2 else 'normal'


class PageLayoutTests(unittest.TestCase):
    """用同一个临时项目量资产页、首帧页；不打开用户真实项目。"""

    @classmethod
    def setUpClass(cls):
        try:
            cls.win = tk.Tk()
        except Exception:
            raise unittest.SkipTest(PLATFORM_TKINTER)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.project = _make_project(cls.tmp.name)
        import desktop as desktop_module
        cls._original_choose = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        from desktop import Desktop
        from local_video import open_studio
        cls.desktop = Desktop(cls.win, root=PROGRAM)
        cls.desktop.root = cls.project
        cls.desktop.studio = open_studio(cls.project)

    @classmethod
    def tearDownClass(cls):
        import desktop as desktop_module
        desktop_module.Desktop.choose_project = cls._original_choose
        if getattr(cls, 'win', None) is not None and cls.win.winfo_exists():
            cls.win.destroy()
        if getattr(cls, 'tmp', None) is not None:
            cls.tmp.cleanup()

    def _show_at_800(self, page):
        self.win.deiconify()
        self.desktop.show(page)
        self.win.update()
        self.win.geometry('800x600+30+30')
        for _ in range(6):
            self.win.update_idletasks()
            self.win.update()
        self.assertEqual((self.win.winfo_width(), self.win.winfo_height()), (800, 600))

    def _assert_table_fonts(self, tree):
        style = tree.cget('style') or 'Treeview'
        current = ttk.Style(tree)
        self.assertEqual(_font_shape(tree, current.lookup(style + '.Heading', 'font')),
                         _expected_font(TABLE_HEADER_FONT))
        self.assertEqual(_font_shape(tree, current.lookup(style, 'font')),
                         _expected_font(TABLE_ROW_FONT))

    def test_asset_page_fits_window_at_800(self):
        self._show_at_800(pet_state.PAGE_OF['assets'])
        content = self.desktop.content
        self.assertLessEqual(content.winfo_reqwidth(), self.win.winfo_width())
        table = self.desktop.asset_table
        self.assertLessEqual(table.winfo_width(), content.winfo_width() + 1)
        self.assertLessEqual(table.winfo_reqwidth(), self.win.winfo_width())
        self._assert_table_fonts(table)

    def test_storyboard_page_fits_window_at_800(self):
        self._show_at_800(pet_state.PAGE_OF['keyframe'])
        content = self.desktop.content
        self.assertLessEqual(content.winfo_reqwidth(), self.win.winfo_width())
        trees = [widget for widget in _descendants(content)
                 if widget.winfo_class() == 'Treeview']
        self.assertTrue(trees)
        for tree in trees:
            self.assertLessEqual(tree.winfo_width(), content.winfo_width() + 1)
            self.assertLessEqual(tree.winfo_reqwidth(), self.win.winfo_width())
            self._assert_table_fonts(tree)
            shell = tree._data_table
            self.assertEqual(shell.empty_label.cget('text'), '暂无镜头')
            self.assertEqual(shell.empty_label.cget('style'), 'Muted.TLabel')
            self.assertEqual(tuple(int(value) for value in shell.empty_label.cget('padding')),
                             (TABLE_EMPTY_PADDING,))

    def test_cards_use_the_same_inner_padding_token(self):
        self.win.deiconify()
        self.desktop.show(PAGE_SITES)
        self.win.update()
        site_cards = [widget for widget in _descendants(self.desktop.content)
                      if isinstance(widget, Card)]
        self.assertGreater(len(site_cards), 0)
        for card in site_cards:
            self.assertEqual(tuple(int(value) for value in card.cget('padding')),
                             (SPACING['lg'],))
        self.desktop.video_mode = None
        self.desktop.show(pet_state.PAGE_OF['video'])
        self.win.update()
        video_cards = [widget for widget in _descendants(self.desktop.content)
                       if isinstance(widget, Card)]
        self.assertGreater(len(video_cards), 0)
        for card in video_cards:
            self.assertEqual(tuple(int(value) for value in card.cget('padding')),
                             (SPACING['lg'],))

    def test_asset_and_storyboard_empty_states_share_the_data_table_label(self):
        episode_paths = [self.project / 'episode' / 'episode.json',
                         self.project / 'storyboard' / '分镜拆分' / 'episode.json']
        saved = {path: path.read_text(encoding='utf-8') for path in episode_paths}
        try:
            empty = json.dumps({'episode_id': 'EP001', 'title': 'T', 'shots': []},
                               ensure_ascii=False)
            for path in episode_paths:
                path.write_text(empty, encoding='utf-8')
            self._show_at_800(pet_state.PAGE_OF['assets'])
            shell = self.desktop.asset_table._data_table
            self.assertEqual(shell.empty_label.cget('text'), '暂无资产')
            self.assertEqual(shell.empty_label.cget('style'), 'Muted.TLabel')
            self.assertEqual(tuple(int(value) for value in shell.empty_label.cget('padding')),
                             (TABLE_EMPTY_PADDING,))
        finally:
            for path, text in saved.items():
                path.write_text(text, encoding='utf-8')

    def test_asset_detail_heading_uses_the_heading_token(self):
        host = ttk.Frame(self.win)
        self.addCleanup(host.destroy)
        desktop = SimpleNamespace(win=self.win, content=host)
        asset_detail._header(desktop, 'CHAR_001', {'name': '猫'})
        labels = [widget for widget in _descendants(host)
                  if widget.winfo_class() == 'TLabel'
                  and 'CHAR_001' in str(widget.cget('text'))]
        self.assertTrue(labels)
        self.assertEqual(_font_shape(labels[0], labels[0].cget('font')),
                         _expected_font(FONTS['heading_3']))


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        try:
            self.win = tk.Tk()
        except Exception:
            self.skipTest(PLATFORM_TKINTER)
        self.win.withdraw()
        self.addCleanup(lambda: self.win.winfo_exists() and self.win.destroy())

    def test_recoverable_asset_error_is_non_modal(self):
        desktop = SimpleNamespace(
            win=self.win,
            status=tk.StringVar(master=self.win),
            asset_requirements=lambda: {'CHAR_001': {'name': '猫'}},
            root=Path(tempfile.gettempdir()),
        )
        with mock.patch.object(asset_detail, 'ask_string', return_value=''), \
                mock.patch.object(asset_detail, 'notify') as notify:
            self.assertIsNone(asset_detail.edit_anchor(desktop, 'CHAR_001'))
        notify.assert_called_once()
        self.assertFalse(notify.call_args.kwargs.get('modal', True))

    def test_variant_delete_keeps_modal_confirmation(self):
        asset = {'state_variants': [
            {'state_id': 'CST-01', 'name': '雨衣', 'override': '蓝色雨衣'}]}
        desktop = SimpleNamespace(
            win=self.win,
            status=tk.StringVar(master=self.win),
            asset_requirements=lambda: {'CHAR_001': asset},
        )
        with mock.patch.object(asset_detail, 'ask_confirmation', return_value=False) as ask:
            self.assertIsNone(asset_detail.delete_variant(desktop, 'CHAR_001', 'CST-01'))
        ask.assert_called_once()
        self.assertTrue(ask.call_args.kwargs.get('dangerous'))


if __name__ == '__main__':
    unittest.main()
