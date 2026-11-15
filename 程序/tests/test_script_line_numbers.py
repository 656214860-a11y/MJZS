"""REQ-S02-36（R1）：剧本正文左侧行号槽随滚动、换行与字号同步。

用 ``desktop_script_pages._build_script_preview`` 的真实装配（gutter＋正文＋
两条滚动条同一网格），断言行号按逻辑行绘制、随 ``yview`` 同步、软换行不
重复编号、字号变化同步。
"""
import sys
import time
import tkinter as tk
import unittest
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM))

from desktop_script_pages import _build_script_preview
from ui_tokens import SCRIPT_VIEW_FONT
from ui_widgets import TextArea


def _settle(widget, iterations=8):
    for _ in range(iterations):
        widget.update_idletasks()
        widget.update()
        time.sleep(0.02)


def _make(root, text, wrap='word'):
    area = tk.Frame(root)
    area.pack(fill='both', expand=True)
    area.columnconfigure(1, weight=1)
    area.rowconfigure(0, weight=1)
    preview, _horizontal, gutter = _build_script_preview(area)
    preview.insert('1.0', text)
    if wrap != 'word':
        preview.configure(wrap=wrap)
    _settle(root)
    return preview, gutter


def _numbers(gutter):
    return [gutter.itemcget(item, 'text') for item in gutter.find_all()]


class ScriptLineNumberTests(unittest.TestCase):
    def _window(self, width=420, height=320):
        root = tk.Tk()
        root.geometry('%dx%d+40+40' % (width, height))
        root.deiconify()
        root.update()

        def _destroy():
            try:
                if root.winfo_exists():
                    root.destroy()
            except tk.TclError:
                pass
        self.addCleanup(_destroy)
        return root

    def test_line_numbers_match_logical_lines(self):
        """REQ-S02-36：可见范围内每个逻辑行恰好一个号，按行号升序。"""
        root = self._window()
        preview, gutter = _make(root, '第一行\n第二行\n第三行\n第四行\n第五行')
        self.assertEqual(_numbers(gutter), ['1', '2', '3', '4', '5'])
        self.assertGreater(gutter.winfo_width(), 0)

    def test_gutter_follows_vertical_scroll(self):
        """REQ-S02-36：滚动后行号槽首号与正文首个可见逻辑行一致。"""
        root = self._window(height=260)
        text = '\n'.join('内容行%d' % index for index in range(1, 121))
        preview, gutter = _make(root, text)
        preview.yview_moveto(0.5)
        _settle(root)
        top = int(str(preview.index('@0,0')).split('.')[0])
        numbers = _numbers(gutter)
        self.assertTrue(numbers, '滚动后行号槽不应为空')
        self.assertGreater(int(numbers[0]), 1)
        self.assertEqual(int(numbers[0]), top)
        # 行号随正文可见范围连续，不跳号、不重复。
        self.assertEqual(numbers, [str(line) for line in range(top, top + len(numbers))])

    def test_soft_wrap_and_no_wrap_keep_one_number_per_line(self):
        """REQ-S02-36：wrap='word' 软换行与 wrap='none' 都不重复编号。"""
        for wrap in ('word', 'none'):
            with self.subTest(wrap=wrap):
                root = self._window(height=360)
                long_line = '很长的一行内容' * 30
                preview, gutter = _make(root, '首行\n' + long_line + '\n末行', wrap=wrap)
                numbers = _numbers(gutter)
                self.assertEqual(len(numbers), len(set(numbers)), '行号不得重复')
                self.assertEqual(numbers, ['1', '2', '3'])
                root.destroy()

    def test_gutter_font_tracks_zoom(self):
        """REQ-S02-36：set_font 后行号字号与测量字体同步变化。"""
        root = self._window()
        _preview, gutter = _make(root, 'a\nb\nc')
        before = {gutter.itemcget(item, 'font') for item in gutter.find_all()}
        gutter.set_font(('Consolas', 16))
        _settle(root)
        after = {gutter.itemcget(item, 'font') for item in gutter.find_all()}
        self.assertTrue(after, 'set_font 后行号仍应绘制')
        self.assertTrue(any('16' in str(font) for font in after),
                        '行号字体未跟随字号变化：%r' % after)
        self.assertNotEqual(before, after)
        self.assertEqual(int(gutter._measure.cget('size')), 16)


if __name__ == '__main__':
    unittest.main()
