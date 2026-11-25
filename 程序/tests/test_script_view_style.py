"""R1690 剧本内容阅读排版：行级标签、阈值与原文逐字不变量。"""
import tempfile
import time
import tkinter as tk
import unittest
from tkinter import ttk

import script_contract
import script_view_style as style
from ui_tokens import SCRIPT_VIEW_MAX_CHARS


GOOD_RAW = (
    '第 1 集\n'
    '场景 1：夜，旧书店内\n'
    '林小满：把旧怀表交给我。\n'
    '陆时：先离开这里。\n'
    '道具：旧怀表\n'
    '林小满愤怒地望向门口，身上穿着蓝色连衣裙，黑发齐刘海。\n'
)
STRUCTURED = script_contract.structure_script(GOOD_RAW)
STRUCTURED_EXTRA = (
    '| 列1 | 列2 |\n'
    '| --- | --- |\n'
    '```\n'
    'print(1)\n'
    '```\n'
    '---\n'
)


def _by_line(parts):
    lines = {}
    for start_line, start_col, _end_line, end_col, tag in parts:
        lines.setdefault(start_line, []).append((start_col, end_col, tag))
    return lines


def _tags(parts, line_no):
    return {tag for _start, _end, tag in _by_line(parts).get(line_no, ())}


def _tag_text(text, parts, tag):
    lines = text.split('\n')
    chunks = []
    for start_line, start_col, _end_line, end_col, found in parts:
        if found == tag:
            chunks.append(lines[start_line - 1][start_col:end_col])
    return chunks


class SpanTests(unittest.TestCase):
    def test_natural_lines_get_expected_tags(self):
        parts = style.spans(GOOD_RAW, 'natural')
        self.assertIn(style.EPISODE, _tags(parts, 1))
        self.assertIn(style.SCENE, _tags(parts, 2))
        self.assertIn(style.SPEAKER, _tags(parts, 3))
        self.assertEqual(_tag_text(GOOD_RAW, parts, style.SPEAKER), ['林小满', '陆时'])
        self.assertIn(style.ANNOTATION, _tags(parts, 5))
        self.assertEqual(_tags(parts, 6), {style.BODY})

    def test_structured_headings_markers_fields_and_quotes(self):
        parts = style.spans(STRUCTURED, 'structured')
        self.assertIn(style.HEADING_TAGS[1], _tags(parts, 1))
        self.assertEqual(_tag_text(STRUCTURED, parts, style.MARKER)[0], '#')
        self.assertIn(style.QUOTE, _tags(parts, 3))
        heading_lines = _by_line(parts)
        self.assertTrue(any(style.HEADING_TAGS[2] in {tag for _s, _e, tag in found}
                            for found in heading_lines.values()))
        self.assertTrue(any(style.HEADING_TAGS[3] in {tag for _s, _e, tag in found}
                            for found in heading_lines.values()))
        self.assertIn('别名', _tag_text(STRUCTURED, parts, style.FIELD))

    def test_structured_table_code_and_separator(self):
        parts = style.spans(STRUCTURED_EXTRA, 'structured')
        self.assertIn(style.TABLE, _tags(parts, 1))
        self.assertIn(style.TABLE_SEPARATOR, _tags(parts, 2))
        self.assertIn(style.FENCE, _tags(parts, 3))
        self.assertIn(style.CODE, _tags(parts, 4))
        self.assertIn(style.FENCE, _tags(parts, 5))
        self.assertIn(style.SEPARATOR, _tags(parts, 6))

    def test_unrecognized_lines_are_body_only(self):
        self.assertEqual(_tags(style.spans('普通动作描写。\n', 'natural'), 1), {style.BODY})
        self.assertEqual(_tags(style.spans('普通正文\n', 'structured'), 1), {style.BODY})

    def test_empty_long_and_unclosed_fence_are_safe(self):
        self.assertEqual(style.spans('', 'natural'), [])
        self.assertEqual(style.spans('x' * (SCRIPT_VIEW_MAX_CHARS + 1), 'natural'), [])
        self.assertTrue(style.spans('```\n未闭合\n', 'structured'))

    def test_hundred_kb_scan_is_fast(self):
        text = ('第 1 集\n场景 1：夜\n林小满：把旧怀表交给我。\n' * 2000)[:100_000]
        started = time.monotonic()
        parts = style.spans(text, 'natural')
        self.assertLess(time.monotonic() - started, 1.0)
        self.assertTrue(parts)

    def test_wrap_mode_honours_threshold(self):
        self.assertEqual(style.wrap_mode('x' * SCRIPT_VIEW_MAX_CHARS), 'word')
        self.assertEqual(style.wrap_mode('x' * (SCRIPT_VIEW_MAX_CHARS + 1)), 'none')


class TkApplyTests(unittest.TestCase):
    def test_speaker_names_use_the_current_readable_text_color(self):
        import ui_tokens
        self.addCleanup(ui_tokens.set_theme, ui_tokens.current_theme())
        for theme in ('day', 'night'):
            with self.subTest(theme=theme):
                ui_tokens.set_theme(theme)
                style.apply_tags(self.widget, GOOD_RAW, 'natural')
                self.assertEqual(self.widget.tag_cget(style.SPEAKER, 'foreground'),
                                 ui_tokens.COLORS['primary_text'])

    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.widget = tk.Text(self.root, wrap='word', undo=True)
        self.widget.pack()

    def _assert_text_unchanged(self, text, kind):
        self.widget.configure(state='normal')
        self.widget.delete('1.0', 'end')
        self.widget.insert('1.0', text)
        before = self.widget.get('1.0', 'end-1c')
        style.apply_tags(self.widget, text, kind)
        after = self.widget.get('1.0', 'end-1c')
        self.assertEqual(before, text)
        self.assertEqual(after, text)
        return before, after

    def test_apply_tags_keeps_natural_text_unchanged(self):
        before, after = self._assert_text_unchanged(GOOD_RAW, 'natural')
        self.assertEqual(before, after)
        self.assertTrue(self.widget.tag_ranges(style.SPEAKER))
        self.assertTrue(self.widget.tag_ranges(style.EPISODE))

    def test_apply_tags_keeps_structured_text_unchanged(self):
        text = STRUCTURED + STRUCTURED_EXTRA
        before, after = self._assert_text_unchanged(text, 'structured')
        self.assertEqual(before, after)
        self.assertTrue(self.widget.tag_ranges(style.HEADING_TAGS[1]))
        self.assertTrue(self.widget.tag_ranges(style.MARKER))
        self.assertTrue(self.widget.tag_ranges(style.FIELD))

    def test_apply_tags_skips_text_over_threshold(self):
        text = 'x' * (SCRIPT_VIEW_MAX_CHARS + 1)
        before, after = self._assert_text_unchanged(text, 'natural')
        self.assertEqual(before, after)
        self.assertFalse(self.widget.tag_ranges(style.BODY))

    def test_apply_tags_preserves_disabled_state(self):
        self.widget.insert('1.0', GOOD_RAW)
        self.widget.configure(state='disabled')
        style.apply_tags(self.widget, GOOD_RAW, 'natural')
        self.assertEqual(str(self.widget.cget('state')), 'disabled')
        self.assertEqual(self.widget.get('1.0', 'end-1c'), GOOD_RAW)

    def test_wrap_toggle_shows_and_hides_horizontal_scrollbar(self):
        from desktop_script_pages import _set_script_wrap
        holder = ttk.Frame(self.root)
        holder.pack()
        horizontal = ttk.Scrollbar(holder, orient='horizontal')
        horizontal.grid()
        _set_script_wrap(self.widget, horizontal, True)
        self.assertEqual(str(self.widget.cget('wrap')), 'word')
        self.assertEqual(horizontal.grid_info(), {})
        _set_script_wrap(self.widget, horizontal, False)
        self.assertEqual(str(self.widget.cget('wrap')), 'none')
        self.assertTrue(horizontal.grid_info())


if __name__ == '__main__':
    unittest.main()
