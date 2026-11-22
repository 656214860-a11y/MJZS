# -*- coding: utf-8 -*-
"""REQ-S01-99：剧本准备页模型回话按排版显示，用户消息与软件示例仍按原文。

只搭环境（``_Harness``、``idea_chat``、``make_minimal_project``），不引入带用例的
测试类；每个用例的 docstring 写 REQ-S01-99，供需求追踪门禁锚定。
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# 直接 `-m unittest` 时程序根与 tests 目录都要可导入：test_idea_chat 在模块顶部
# 就 import skip_reasons（run_selftests 会预先插入 tests 目录）。
HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(HERE / 'tests') not in sys.path:
    sys.path.append(str(HERE / 'tests'))

from tests.test_idea_chat import _Harness, idea_chat
from tests.ui_edges_support import make_minimal_project


MD_PREFIX = 'md_'


def text_of(box):
    return str(box.get('1.0', 'end-1c'))


def md_tags_in(box, start, end):
    """与 [start, end) 有交集的 md_ 标签名。"""
    found = []
    for tag in box.tag_names():
        if not str(tag).startswith(MD_PREFIX):
            continue
        spans = box.tag_ranges(tag)
        for low, high in zip(spans[::2], spans[1::2]):
            if box.compare(low, '<', end) and box.compare(high, '>', start):
                found.append(str(tag))
                break
    return found


class ChatMarkdownTests(_Harness):
    """REQ-S01-99：模型气泡接上排版；用户消息与软件示例保持原文。"""

    def show_with(self, proj, rows):
        """建 Desktop，写入 rows=[(role, text, model)]（也可传接收 d 的函数），再打开 01 页。"""
        d, win = self.desktop(proj)
        for role, text, model in rows(d) if callable(rows) else rows:
            idea_chat.append(proj, role, text, model=model)
        d.show(0)
        self.settle_script_page(win)
        return d, win

    def test_model_reply_is_rendered_instead_of_showing_markdown_marks(self):
        """REQ-S01-99：模型回话按排版显示，加粗与编号列表记号不再原样出现。"""
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, _win = self.show_with(
                proj, lambda page: [('assistant', '**重点**\n1. 第一\n2. 第二',
                                     page.idea_chat_model())])
            box = d.idea_log
            spans = box.tag_ranges('bubble_0')
            self.assertEqual(len(spans), 2, '正文带 bubble_0 且是连续的一段')
            shown = str(box.get(*spans))
            self.assertNotIn('**', shown)
            self.assertIn('1. 第一', shown)
            self.assertIn('md_bold', md_tags_in(box, spans[0], spans[1]))

    def test_user_message_keeps_the_raw_markdown_marks(self):
        """REQ-S01-99：用户消息仍按原文显示，不带任何 md_ 排版标签。"""
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, _win = self.show_with(
                proj, [('user', '**重点**\n1. 第一\n2. 第二', None)])
            box = d.idea_log
            spans = box.tag_ranges('bubble_0')
            self.assertEqual(len(spans), 2)
            shown = str(box.get(*spans))
            self.assertIn('**重点**', shown)
            self.assertEqual(md_tags_in(box, spans[0], spans[1]), [])

    def test_software_example_keeps_the_raw_text(self):
        """REQ-S01-99：软件示例仍按原文显示，不带任何 md_ 排版标签。"""
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, _win = self.show_with(proj, [])
            box = d.idea_log
            self.assertEqual(d._bubble_full['bubble_example']['text'], d.idea_example())
            spans = box.tag_ranges('bubble_example')
            self.assertTrue(spans)
            self.assertEqual(md_tags_in(box, spans[0], spans[-1]), [])

    def test_long_model_reply_folds_and_unfolds_with_markdown_kept(self):
        """REQ-S01-99：长回话先折叠，展开／收起后排版标签仍在，正文连续、sel 最高。"""
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            full = '\n'.join('- 第%d项' % number for number in range(1, 11))
            d, _win = self.show_with(
                proj, lambda page: [('assistant', full, page.idea_chat_model())])
            box = d.idea_log
            self.assertTrue(d._bubble_full['bubble_0']['preview'].endswith('…'))
            self.assertNotIn('第10项', text_of(box), '先显示折叠预览')
            self.assertEqual(str(box.get(*box.tag_ranges('bubble_0_toggle'))).strip(),
                             '展开全文')
            d.toggle_bubble(box, 'bubble_0')
            spans = box.tag_ranges('bubble_0')
            self.assertIn('第10项', str(box.get(*spans)), '展开后是全文的排版结果')
            self.assertIn('md_list', md_tags_in(box, spans[0], spans[-1]))
            self.assertEqual(str(box.get(*box.tag_ranges('bubble_0_toggle'))).strip(), '收起')
            d.toggle_bubble(box, 'bubble_0')
            spans = box.tag_ranges('bubble_0')
            self.assertEqual(len(spans), 2, '收起后正文仍是连续的一段')
            self.assertNotIn('第10项', str(box.get(*spans)))
            self.assertEqual(str(box.get(*box.tag_ranges('bubble_0_toggle'))).strip(),
                             '展开全文')
            self.assertEqual(box.tag_names()[-1], 'sel')

    def test_comment_only_reply_still_shows_its_raw_text(self):
        """REQ-S01-99：排版结果为空时退回原文写入，气泡里不会一个字都没有。"""
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, _win = self.show_with(
                proj, lambda page: [('assistant', '<!-- x -->', page.idea_chat_model())])
            box = d.idea_log
            spans = box.tag_ranges('bubble_0')
            self.assertTrue(spans)
            self.assertIn('<!-- x -->', str(box.get(*spans)))

    def test_copy_still_returns_the_raw_reply(self):
        """REQ-S01-99：「复制这条」仍复制原文，不复制排版后的文字。"""
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            raw = '**原文**'
            d, _win = self.show_with(
                proj, lambda page: [('assistant', raw, page.idea_chat_model())])
            with patch('ui.prompt_window.copy_text', return_value='') as copier:
                copied = d.copy_bubble_message(0)
            self.assertEqual(copied, raw)
            self.assertEqual(copier.call_args.args[1], raw)

    def test_markdown_tags_sit_above_every_bubble_and_below_sel(self):
        """REQ-S01-99：写完两条模型气泡后 sel 最高，md_bold 排在两条气泡标签之上。"""
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, _win = self.show_with(
                proj, lambda page: [('assistant', '**甲**', page.idea_chat_model()),
                                    ('assistant', '**乙**', page.idea_chat_model())])
            box = d.idea_log
            names = list(box.tag_names())
            self.assertEqual(names[-1], 'sel')
            self.assertGreater(names.index('md_bold'), names.index('bubble_0'))
            self.assertGreater(names.index('md_bold'), names.index('bubble_1'))

    def test_redraw_does_not_duplicate_text_and_keeps_markdown_tags(self):
        """REQ-S01-99：重画不报错、同一句话只出现一次，md_ 标签配置仍在。"""
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.show_with(
                proj, lambda page: [('assistant', '**不重复**', page.idea_chat_model())])
            self.assertEqual(text_of(d.idea_log).count('不重复'), 1)
            d.show_conversation()
            self.settle_script_page(win)
            self.assertEqual(text_of(d.idea_log).count('不重复'), 1)
            self.assertTrue(d.idea_log.tag_cget('md_bold', 'font'))

    def test_nested_list_keeps_the_second_level_indent(self):
        """REQ-S01-99：嵌套列表第二项带 md_list_l2，缩进大于 md_list 且不小于气泡边距。"""
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, _win = self.show_with(
                proj, lambda page: [('assistant', '- a\n  - b', page.idea_chat_model())])
            box = d.idea_log
            spans = box.tag_ranges('bubble_0')
            self.assertIn('md_list_l2', md_tags_in(box, spans[0], spans[-1]))
            first = int(float(box.tag_cget('md_list', 'lmargin1')))
            second = int(float(box.tag_cget('md_list_l2', 'lmargin1')))
            body = int(float(box.tag_cget('bubble_0', 'lmargin1')))
            self.assertGreater(second, first)
            self.assertGreaterEqual(first, body)
            self.assertGreaterEqual(second, body)


if __name__ == '__main__':
    unittest.main()
