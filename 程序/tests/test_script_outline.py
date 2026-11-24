"""REQ-S02-36（R3）：剧本大纲——纯函数条目提取＋真 Tk 点击跳转。

``outline_entries`` 复用 ``script_view_style.spans`` 的标签常量，不复制
识别正则；``OutlinePanel`` 点击条目 ``see()`` 到正文行并打临时高亮。
"""
import sys
import time
import tkinter as tk
import unittest
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM))

from script_outline import (
    OutlinePanel,
    _HIT_TAG,
    highlight_line,
    outline_entries,
    outline_sections,
)
from ui_widgets import TextArea


def _settle(widget, iterations=6):
    for _ in range(iterations):
        widget.update_idletasks()
        widget.update()
        time.sleep(0.02)


NATURAL = (
    '第 1 集\n\n场景 1：旧站台\n\n阿远：我回来了。\n\n'
    '第 2 集\n\n场景 2：雨夜车站\n\n阿远：又见面了。\n'
)
STRUCTURED = (
    '# 结构化剧本\n\n## 档案区\n\n### 场次 01：旧站台\n\n正文\n\n'
    '### 场次 02：雨夜车站\n\n正文\n'
)


class OutlineEntriesTests(unittest.TestCase):
    def test_natural_episode_and_scene_entries(self):
        """REQ-S02-36：自然剧本按集数/场次标签出条目，行号升序去重。"""
        entries = outline_entries(NATURAL, 'natural')
        self.assertEqual([line for line, _t in entries], [1, 3, 7, 9])
        self.assertEqual(entries[0], (1, '第 1 集'))
        self.assertEqual(entries[1], (3, '场景 1：旧站台'))
        self.assertEqual(entries[2], (7, '第 2 集'))
        self.assertEqual(entries[3], (9, '场景 2：雨夜车站'))

    def test_structured_heading_entries_strip_marks(self):
        """REQ-S02-36：结构剧本按标题层级出条目，去掉 '#' 前缀。"""
        entries = outline_entries(STRUCTURED, 'structured')
        titles = [title for _line, title in entries]
        self.assertIn('结构化剧本', titles)
        self.assertIn('档案区', titles)
        self.assertIn('场次 01：旧站台', titles)
        self.assertIn('场次 02：雨夜车站', titles)
        self.assertFalse(any(title.startswith('#') for title in titles))

    def test_dedup_and_truncation(self):
        """REQ-S02-36：同一行只出一个条目；超长标题截断并加省略号。"""
        long_title = '场景 9：' + '很长的场景标题' * 8
        text = '第 1 集\n' + long_title + '\n普通行\n'
        entries = outline_entries(text, 'natural')
        lines = [line for line, _t in entries]
        self.assertEqual(len(lines), len(set(lines)))
        scene = dict(entries).get(2)
        self.assertIsNotNone(scene)
        self.assertLessEqual(len(scene), 40)
        self.assertTrue(scene.endswith('…'))

    def test_empty_when_no_headings(self):
        """REQ-S02-36：无集数/场次/标题时返回空列表。"""
        self.assertEqual(outline_entries('只是普通正文\n第二行\n', 'natural'), [])
        self.assertEqual(outline_entries('', 'natural'), [])
        self.assertEqual(outline_entries('普通正文', 'structured'), [])


class OutlineSectionsTests(unittest.TestCase):
    """REQ-S02-40：折叠段表——行号、层级与段末（下一个同级或更高级标题行）。"""

    def test_natural_sections_carry_level_and_end(self):
        sections = outline_sections(NATURAL, 'natural')
        self.assertEqual([line for line, _t, _lv, _e in sections], [1, 3, 7, 9])
        self.assertEqual(sections[0], (1, '第 1 集', 1, 7))
        self.assertEqual(sections[1], (3, '场景 1：旧站台', 2, 7))
        self.assertEqual(sections[2], (7, '第 2 集', 1, 13))
        self.assertEqual(sections[3], (9, '场景 2：雨夜车站', 2, 13))

    def test_structured_sections_levels_and_ends(self):
        sections = outline_sections(STRUCTURED, 'structured')
        self.assertEqual([line for line, _t, _lv, _e in sections], [1, 3, 5, 9])
        self.assertEqual({line: level for line, _t, level, _e in sections},
                         {1: 1, 3: 2, 5: 3, 9: 3})
        self.assertEqual({line: end for line, _t, _lv, end in sections},
                         {1: 13, 3: 13, 5: 9, 9: 13})

    def test_sections_empty_when_no_headings(self):
        self.assertEqual(outline_sections('只是普通正文\n第二行\n', 'natural'), [])
        self.assertEqual(outline_sections('', 'natural'), [])


class HighlightLineTests(unittest.TestCase):
    """REQ-S02-43：跳转共用的临时高亮——打 hit 标签并 see() 到该行。"""

    def test_highlight_line_marks_hit_tag(self):
        root = tk.Tk()
        root.geometry('500x300+40+40')
        root.deiconify()
        root.update()
        self.addCleanup(lambda: root.winfo_exists() and root.destroy())
        preview = TextArea(root, wrap='word', font=('Microsoft YaHei UI', 10))
        preview.pack(fill='both', expand=True)
        preview.insert('1.0', NATURAL)
        _settle(root)
        highlight_line(preview, 7)
        _settle(root)
        ranges = preview.tag_ranges(_HIT_TAG)
        self.assertTrue(ranges, '跳转后应在目标行留下高亮')
        self.assertEqual(str(ranges[0]), '7.0')
        self.assertTrue(str(ranges[1]).startswith('7.'))
        highlight_line(preview, 1)
        ranges = preview.tag_ranges(_HIT_TAG)
        self.assertEqual(str(ranges[0]), '1.0', '再次跳转应移动而不是叠加高亮')


class OutlinePanelTests(unittest.TestCase):
    def _make(self, text):
        root = tk.Tk()
        root.geometry('500x320+40+40')
        root.deiconify()
        root.update()
        self.addCleanup(lambda: root.winfo_exists() and root.destroy())
        preview = TextArea(root, wrap='word', font=('Microsoft YaHei UI', 10))
        preview.pack(fill='both', expand=True)
        preview.insert('1.0', text)
        panel = OutlinePanel(root, preview)
        panel.pack(side='right', fill='y')
        _settle(root)
        return root, preview, panel

    def test_click_jumps_and_highlights_line(self):
        """REQ-S02-36：点击条目 see() 到对应行并打临时高亮。"""
        root, preview, panel = self._make(NATURAL)
        panel.set_entries(outline_entries(NATURAL, 'natural'))
        _settle(root)
        self.assertEqual(panel._list.size(), 4)
        panel._list.selection_clear(0, 'end')
        panel._list.selection_set(2)   # 第 7 行「第 2 集」
        panel._list.event_generate('<<ListboxSelect>>')
        # 高负载下虚拟事件处理与 see() 滚动可能滞后：轮询到高亮与可视区就位。
        for _ in range(20):
            _settle(root, 2)
            ranges = preview.tag_ranges(_HIT_TAG)
            if not ranges:
                continue
            top = int(str(preview.index('@0,0')).split('.')[0])
            bottom = int(str(preview.index('@0,%d' % max(1, preview.winfo_height()))).split('.')[0])
            if top <= 7 <= bottom:
                break
        self.assertTrue(ranges, '点击后应在目标行留下高亮')
        self.assertEqual(str(ranges[0]), '7.0')
        # see() 已把第 7 行滚进可视区。
        self.assertLessEqual(top, 7)
        self.assertGreaterEqual(bottom, 7)

    def test_empty_state_label(self):
        """REQ-S02-36：无条目时显示空态文案而不是空列表。"""
        root, preview, panel = self._make('只有正文\n')
        panel.set_entries(())
        _settle(root)
        self.assertEqual(panel._list.size(), 0)
        self.assertEqual(str(panel._empty.cget('text')), '无集数／场次标题')
        self.assertEqual(panel._empty.winfo_manager(), 'pack')


if __name__ == '__main__':
    unittest.main()
