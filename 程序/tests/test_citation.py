# -*- coding: utf-8 -*-
"""引用溯源（R3136）：[n] 标记着色 + 点击绑定 + source 序号映射。

运行：python tests/test_citation.py（真 Tk；运行器会切隐藏桌面）
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skip_reasons import PLATFORM_TKINTER
from ui import ui_citation


class CitationTests(unittest.TestCase):
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

    def test_insert_citations_marks_each_index(self):
        count = ui_citation.insert_citations(self.box, 'm1', '见 [1] 和 [2]',
                                             on_open=lambda index: None, markers={1: {'doc': 'a'}})
        self.assertEqual(count, 2)
        self.assertIn('见 [1] 和 [2]', self.box.get('1.0', 'end-1c'))
        self.assertIn('m1_cite_1', self.box.tag_names())
        self.assertIn('m1_cite_2', self.box.tag_names())
        script = self.box.tk.call(self.box._w, 'tag', 'bind', 'm1_cite_1')
        self.assertTrue(script, '点击定位必须已绑定')

    def test_citations_of_sources_maps_index(self):
        rows = ui_citation.citations_of([{'title': '剧本'}, {'index': 3, 'title': '设定'}])
        self.assertEqual(set(rows), {1, 3})
        self.assertEqual(rows[3]['title'], '设定')


if __name__ == '__main__':
    unittest.main()
