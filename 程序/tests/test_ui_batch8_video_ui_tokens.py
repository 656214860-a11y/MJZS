# -*- coding: utf-8 -*-
"""UI 批次 8：视频工作台与零散弹窗的令牌化棘轮（hex／数字 padding 只降不升）。

覆盖 `app.py`／`keyframe_comfy.py`／`reference_wall.py`／`white_model.py` 四个文件：

- 内联 hex 颜色字面量必须为 0（与 `tests/architecture/test_token_boundary.py` 同口径）；
- 数字 `padx/pady/ipadx/ipady` 字面量必须为 0，全部改取 `ui_tokens.SPACING`；
- `SPACING` 的值全部落在 4px 刻度上（本批把 2/5/6/7/10/14 等贴到这条刻度）；
- 真 Tk 根窗口验证 `white_model` 现在消费的 `FONTS['title']` 令牌能解出期望字体。

没有可用 Tk 时，字体几何用例如实 `skipTest`（与既有 GUI 用例一致）。
"""
from __future__ import annotations

import unittest

from skip_reasons import PLATFORM_TKINTER
from tests.architecture._scan import ROOT, parse
from tests.architecture.test_token_boundary import hex_color_count, numeric_padding_count

# 本批开工前的实测基数（`tests/architecture/test_token_boundary.py` 同口径）：
# hex、数字 padding 均由探针实测，改后应下降（hex 本就是 0，只要求不升）。
TARGETS = ('app.py', 'keyframe_comfy.py', 'reference_wall.py', 'white_model.py')
HEX_BEFORE = {'app.py': 0, 'keyframe_comfy.py': 0, 'reference_wall.py': 0, 'white_model.py': 0}
PADDING_BEFORE = {'app.py': 7, 'keyframe_comfy.py': 26, 'reference_wall.py': 0, 'white_model.py': 8}


class Batch8TokenTests(unittest.TestCase):
    def test_inline_hex_does_not_increase(self):
        for name in TARGETS:
            with self.subTest(file=name):
                actual = hex_color_count(parse(ROOT / name))
                self.assertLessEqual(actual, HEX_BEFORE[name],
                                     '{0} 内联 hex 颜色只能减少，实际 {1}'.format(name, actual))

    def test_numeric_padding_falls_to_zero(self):
        for name in TARGETS:
            with self.subTest(file=name):
                actual = numeric_padding_count(parse(ROOT / name))
                self.assertLessEqual(actual, PADDING_BEFORE[name],
                                     '{0} 数字 padding 只许减少'.format(name))
                self.assertEqual(actual, 0,
                                 '{0} 仍有 {1} 处数字 padx/pady，须改取 ui_tokens.SPACING'.format(name, actual))

    def test_spacing_values_are_on_the_four_px_grid(self):
        from ui_tokens import SPACING
        off_grid = {key: value for key, value in SPACING.items() if value % 4}
        self.assertEqual(off_grid, {}, 'SPACING 必须落在 4px 刻度：' + str(off_grid))

    def test_white_model_title_font_token_measures_in_real_tk(self):
        try:
            import tkinter as tk
            from tkinter import font as tkfont
            root = tk.Tk()
        except Exception as exc:  # 无可用 Tkinter
            self.skipTest(PLATFORM_TKINTER)
        try:
            root.withdraw()
            from ui_tokens import FONTS
            resolved = tkfont.Font(root=root, font=FONTS['title']).actual()
            self.assertIn('YaHei', resolved['family'])
            self.assertEqual(int(resolved['size']), 14)
            self.assertEqual(resolved['weight'], 'bold')
            label = tk.Label(root, text='SH001 · 白模预演', font=FONTS['title'])
            self.assertGreater(label.winfo_reqheight(), 0, '页标题字体必须量得到高度')
        finally:
            root.destroy()


if __name__ == '__main__':
    unittest.main()
