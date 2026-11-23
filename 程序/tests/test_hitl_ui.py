# -*- coding: utf-8 -*-
"""HITL 卡片 Tk 渲染（R3119）：审批门三按钮、选择卡单选回填。

运行：python tests/test_hitl_ui.py（真 Tk；运行器会切隐藏桌面）
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from domain import hitl
from skip_reasons import PLATFORM_TKINTER
from ui import ui_hitl


def _buttons(widget):
    found = []
    for child in widget.winfo_children():
        if child.winfo_class() in ('TButton', 'Button'):
            found.append(child)
        else:
            found.extend(_buttons(child))
    return found


def _widgets(widget):
    found = []
    for child in widget.winfo_children():
        found.append(child)
        found.extend(_widgets(child))
    return found


def _labels(widget):
    return [child for child in _widgets(widget)
            if child.winfo_class() in ('TLabel', 'Label')]


class ChoiceReplyParseTests(unittest.TestCase):
    """REQ-S01-109：回话末尾 choices 标记段的纯解析。"""

    def test_no_marker_keeps_the_message_unchanged(self):
        parsed = hitl.parse_choice_reply('先结论\n再分点')
        self.assertEqual(parsed['text'], '先结论\n再分点')
        self.assertEqual(parsed['candidates'], [])
        self.assertFalse(parsed['truncated'])
        self.assertFalse(parsed['open'])

    def test_one_four_and_five_candidates(self):
        for count in (1, 4, 5):
            body = '\n'.join('- 选项%d' % number for number in range(1, count + 1))
            raw = '结论\n```choices\n' + body + '\n```\n下一步'
            with self.subTest(count=count):
                parsed = hitl.parse_choice_reply(raw)
                self.assertEqual(parsed['candidates'], ['选项%d' % n for n in range(1, count + 1)])
                self.assertEqual(parsed['truncated'], count > hitl.MAX_CHOICES)
                self.assertNotIn('```', parsed['text'])
                self.assertNotIn('选项1', parsed['text'])
                self.assertIn('下一步', parsed['text'])

    def test_chinese_and_ascii_quotes_are_removed(self):
        raw = ('```choices\n- “悲剧结局”\n- 「喜剧收尾」\n- "第三条"\n'
               '- 1. 第四条\n```')
        parsed = hitl.parse_choice_reply(raw)
        self.assertEqual(parsed['candidates'], ['悲剧结局', '喜剧收尾', '第三条', '第四条'])

    def test_unterminated_marker_is_hidden_and_does_not_offer_choices(self):
        for raw in ('结论\n```choices\n- 悲剧', '结论\n```ch'):
            with self.subTest(raw=raw):
                parsed = hitl.parse_choice_reply(raw)
                self.assertEqual(parsed['candidates'], [])
                self.assertTrue(parsed['open'])
                self.assertNotIn('```', parsed['text'])
                self.assertNotIn('悲剧', parsed['text'])

    def test_empty_marker_is_stripped_without_a_card(self):
        parsed = hitl.parse_choice_reply('结论\n```choices\n\n```')
        self.assertEqual(parsed['candidates'], [])
        self.assertEqual(parsed['text'], '结论')


class HitlUiTests(unittest.TestCase):
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

    def test_approval_gate_three_buttons_emit_decisions(self):
        seen = []
        frame = ui_hitl.build_approval_gate(
            self.win, hitl.make_request('approve', {'title': '确认采用'}), seen.append)
        buttons = _buttons(frame)
        self.assertEqual([button.cget('text') for button in buttons], ['确认采用', '拒绝', '重新生成'])
        buttons[0].invoke()
        buttons[2].invoke()
        self.assertEqual([item['decision'] for item in seen], ['approve', 'regenerate'])

    def test_choice_card_emits_selected_candidate(self):
        seen = []
        frame = ui_hitl.build_choice_card(self.win, hitl.make_request('choice', {
            'title': '选结局', 'candidates': [{'label': '悲剧'}, {'label': '喜剧'}]}), seen.append)
        radios = [child for child in frame.winfo_children()[1].winfo_children()
                  if child.winfo_class() == 'TRadiobutton']
        self.assertEqual([radio.cget('text') for radio in radios], ['悲剧', '喜剧'])
        radios[1].invoke()
        _buttons(frame)[0].invoke()
        self.assertEqual(seen[0]['decision'], 'edit')
        self.assertEqual(seen[0]['payload']['selected'], {'label': '喜剧'})

    def test_pick_card_sends_once_and_locks_every_choice(self):
        """REQ-S01-109：点选即发出，按钮全部置灰，同一张卡不能二次点选。"""
        seen, picked = [], []
        frame = ui_hitl.build_choice_card(
            self.win, hitl.make_request('choice', {
                'title': '选结局', 'candidates': [{'label': '悲剧'}, {'label': '喜剧'}]}),
            seen.append, on_pick=picked.append)
        choice_buttons = [button for button in _buttons(frame)
                          if button.cget('text') in ('悲剧', '喜剧')]
        choice_buttons[0].invoke()
        choice_buttons[1].invoke()
        self.assertEqual(picked, ['悲剧'])
        self.assertEqual([item['payload']['selected'] for item in seen], [{'label': '悲剧'}])
        self.assertEqual([str(button.cget('state')) for button in choice_buttons],
                         ['disabled', 'disabled'])
        self.assertTrue(any(str(label.cget('text')).startswith('已选：悲剧')
                            for label in _labels(frame)))

    def test_pick_card_selected_state_is_read_only(self):
        """REQ-S01-109：重绘时传入选中的选项，按钮直接置灰并显示已选。"""
        frame = ui_hitl.build_choice_card(
            self.win, hitl.make_request('choice', {
                'title': '选结局', 'candidates': [{'label': '悲剧'}, {'label': '喜剧'}]}),
            lambda _item: None, on_pick=lambda _text: None, selected='喜剧')
        choice_buttons = [button for button in _buttons(frame)
                          if button.cget('text') in ('悲剧', '喜剧')]
        self.assertEqual([str(button.cget('state')) for button in choice_buttons],
                         ['disabled', 'disabled'])
        self.assertTrue(any(str(label.cget('text')) == '已选：喜剧' for label in _labels(frame)))

    def test_pick_card_five_candidates_keep_other_input(self):
        """REQ-S01-109：最多 4 个选项；超过时截断并保留「其他…」输入。"""
        picked = []
        frame = ui_hitl.build_choice_card(
            self.win, hitl.make_request('choice', {
                'title': '选一个',
                'candidates': [{'label': str(number)} for number in range(1, 6)]}),
            lambda _item: None, on_pick=picked.append)
        choice_buttons = [button for button in _buttons(frame)
                          if button.cget('text') in ('1', '2', '3', '4', '5')]
        self.assertEqual([button.cget('text') for button in choice_buttons], ['1', '2', '3', '4'])
        entries = [child for child in _widgets(frame) if child.winfo_class() == 'TEntry']
        self.assertEqual(len(entries), 1)
        entries[0].insert(0, '其他结局')
        _buttons(frame)[-1].invoke()
        self.assertEqual(picked, ['其他结局'])


if __name__ == '__main__':
    unittest.main()
