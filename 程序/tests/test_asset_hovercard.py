# -*- coding: utf-8 -*-
"""资产悬浮卡（R3136）：资产名高亮 + 悬浮弹出/关闭 + 属性展示。

运行：python tests/test_asset_hovercard.py（真 Tk；运行器会切隐藏桌面）
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skip_reasons import PLATFORM_TKINTER
from ui import ui_asset_card


class AssetHovercardTests(unittest.TestCase):
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
        self.box = self.tk.Text(self.win)

    def test_highlight_assets_prefers_longest_name(self):
        assets = {'林黛玉': {'name': '林黛玉'},
                  '林黛玉的扇子': {'name': '林黛玉的扇子'}}
        count = ui_asset_card.highlight_assets(self.box, 'm1', '角色：林黛玉的扇子', assets)
        self.assertEqual(count, 1, '最长资产名优先')
        self.assertIn('林黛玉的扇子', self.box.get('1.0', 'end-1c'))
        self.assertIn('m1_asset_0', self.box.tag_names())

    def test_show_and_hide_hovercard(self):
        window = ui_asset_card.show_asset_hovercard(
            self.box, {'name': '林黛玉', 'fields': {'发色': '黑'}})
        self.assertTrue(window.winfo_exists())
        ui_asset_card.hide_asset_hovercard(self.box)
        self.assertFalse(window.winfo_exists())


if __name__ == '__main__':
    unittest.main()
