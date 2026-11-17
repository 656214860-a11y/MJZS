# -*- coding: utf-8 -*-
"""图片/分镜缩略图卡（R3124）：多候选切换 + 收藏 + Lightbox。

运行：python tests/test_media_render.py（真 Tk；运行器会切隐藏桌面）
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skip_reasons import PLATFORM_TKINTER
from ui import ui_media


class MediaRenderTests(unittest.TestCase):
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

    def test_thumbnail_card_switches_candidates_and_favorites(self):
        opened, favorites = [], []
        frame = ui_media.build_thumbnail_card(self.win, ['a.png', 'b.png', 'c.png'],
                                              title='分镜候选', on_favorite=favorites.append,
                                              on_open=opened.append)
        labels = [child for child in frame.winfo_children() if child.winfo_class() == 'TLabel']
        self.assertEqual(labels[0].cget('text'), '分镜候选')
        preview = labels[1]
        self.assertIn('候选 1/3：a.png', preview.cget('text'))
        actions = frame.winfo_children()[-1]
        buttons = {child.cget('text'): child for child in actions.winfo_children()
                   if child.winfo_class() == 'TButton'}
        buttons['下一张'].invoke()
        self.assertIn('候选 2/3：b.png', preview.cget('text'))
        buttons['收藏入库'].invoke()
        self.assertEqual(favorites, ['b.png'])
        self.assertEqual(opened[0], 'a.png')
        self.assertEqual(opened[-1], 'b.png')

    def test_lightbox_opens_and_closes(self):
        window = ui_media.open_lightbox(self.win, 'missing.png')
        self.assertTrue(window.winfo_exists())
        window.destroy()


if __name__ == '__main__':
    unittest.main()
