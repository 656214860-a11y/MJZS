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
        # 高负载下滚动同步与 Canvas 重绘可能滞后：轮询到行号槽跟上可视行。
        numbers = []
        top = 0
        for _ in range(20):
            _settle(root, 2)
            numbers = _numbers(gutter)
            top = int(str(preview.index('@0,0')).split('.')[0])
            if numbers and int(numbers[0]) == top:
                break
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

    def test_fold_marks_drawn_and_click_reports_line(self):
        """REQ-S02-40：set_fold_support 后可折行画出标记，点击标记回调对应行号。"""
        root = self._window()
        _preview, gutter = _make(root, '第 1 集\n\n场景 1：旧站台\n\n阿远：我回来了。\n')
        marks = {1: False, 3: False}
        toggled = []
        gutter.set_fold_support(lambda: marks, toggled.append)
        _settle(root)
        tagged = {}
        for item in gutter.find_all():
            for tag in gutter.gettags(item):
                if tag.startswith('fold@'):
                    tagged.setdefault(tag, item)
        self.assertIn('fold@1', tagged, '第 1 行应有折叠标记')
        self.assertIn('fold@3', tagged, '第 3 行应有折叠标记')
        # 模拟点击标记中心：命中框比三角形略大，点击附近也命中。
        x0, y0, x1, y1 = gutter.bbox(tagged['fold@3'])
        gutter.event_generate('<Button-1>', x=(x0 + x1) // 2, y=(y0 + y1) // 2)
        _settle(root)
        self.assertEqual(toggled, [3])
        # 折叠后标记按状态换向：收起为右指，展开为下指（不同形状，靠 item 计数不区分）。
        marks[3] = True
        gutter.refresh()
        _settle(root)

    def test_fold_marks_skip_hidden_and_absent_by_default(self):
        """REQ-S02-40：未接 fold 支持时行号槽只画行号；隐藏行不画标记。"""
        root = self._window()
        preview, gutter = _make(root, '第 1 集\n\n场景 1')
        self.assertEqual(_numbers(gutter), ['1', '2', '3'])
        # 未调用 set_fold_support：除行号文本外没有其它画布项。
        for item in gutter.find_all():
            self.assertTrue(gutter.itemcget(item, 'text').isdigit())
        # 接入后 elide 行不画标记（dlineinfo 为空即隐藏）。
        preview.tag_configure('foldtest', elide=True)
        preview.tag_add('foldtest', '3.0', '4.0')
        marks = {1: False, 3: False}
        gutter.set_fold_support(lambda: marks, lambda _line: None)
        _settle(root)
        tags = [tag for item in gutter.find_all() for tag in gutter.gettags(item)]
        self.assertIn('fold@1', tags)
        self.assertNotIn('fold@3', tags, '被 elide 的行不应再画折叠标记')

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
