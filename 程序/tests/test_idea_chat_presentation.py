# -*- coding: utf-8 -*-
"""O46：创意对话气泡的纯展示逻辑搬到 L3 后，实现与 L4 入口都要有回归。"""
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

import idea_chat_controller as icc
from desktop import Desktop


class BubbleTimestampTests(unittest.TestCase):
    def test_reads_both_supported_stamp_shapes(self):
        self.assertEqual(icc.bubble_timestamp('20261012_081530'), '10-12 08:15')
        self.assertEqual(icc.bubble_timestamp('20261012_081530_123456'), '10-12 08:15')

    def test_unrecognised_stamp_is_blank(self):
        for value in ('', None, 'nope', 20261012):
            with self.subTest(value=value):
                self.assertEqual(icc.bubble_timestamp(value), '')


class CollapsePreviewTests(unittest.TestCase):
    def test_short_message_is_returned_whole(self):
        self.assertEqual(icc.collapse_preview('  hi  '), ('hi', False))

    def test_overlong_message_is_folded_to_the_char_budget(self):
        preview, folded = icc.collapse_preview('x' * 500)
        self.assertTrue(folded)
        self.assertEqual(preview, 'x' * icc.BUBBLE_COLLAPSE_CHARS + '…')

    def test_too_many_lines_are_folded_to_the_line_budget(self):
        preview, folded = icc.collapse_preview('\n'.join('行%d' % i for i in range(20)))
        self.assertTrue(folded)
        self.assertEqual(preview, '\n'.join('行%d' % i for i in range(icc.BUBBLE_COLLAPSE_LINES)) + '…')


class SpeakerNameTests(unittest.TestCase):
    def test_user_is_addressed_as_you(self):
        self.assertEqual(icc.speaker_name({'role': 'user', 'model': 'X'}), '您')

    def test_assistant_uses_model_name_with_fallback(self):
        self.assertEqual(icc.speaker_name({'role': 'assistant', 'model': ' DeepSeek V4 Pro '}),
                         '对话AI · DeepSeek V4 Pro')
        self.assertEqual(icc.speaker_name({'role': 'assistant'}), '对话AI · AI 助手')


class ModelBarTests(unittest.TestCase):
    """REQ-S01-77：模型目录条的纯去重／排序／选中回落逻辑。"""

    def test_items_dedup_and_order_by_first_appearance(self):
        rows = [
            {'role': 'assistant', 'model': '乙', 'at': '20260102_000000_000000'},
            {'role': 'user', 'model': '甲', 'at': '20260101_000000_000000'},
            {'role': 'assistant', 'model': '乙', 'at': '20260103_000000_000000'},
            {'role': 'assistant', 'model': '  '},
            {'role': 'assistant'},
            {'role': 'user', 'model': '甲', 'at': '20260104_000000_000000'},
            'not-a-row',
        ]
        self.assertEqual(icc.model_bar_items(rows), ['甲', '乙'])
        self.assertEqual(icc.model_bar_items([]), [])
        self.assertEqual(icc.model_bar_items(None), [])

    def test_items_without_at_go_after_timestamped(self):
        rows = [
            {'role': 'user', 'model': '无时间'},
            {'role': 'user', 'model': '有时间', 'at': '20260101_000000_000000'},
        ]
        self.assertEqual(icc.model_bar_items(rows), ['有时间', '无时间'])

    def test_selection_without_all_tab_falls_back_to_current_then_first(self):
        """R2350 取消「全部」标签：选中项总是有记录的模型，清空后回落当前模型或第一个标签。"""
        items = ['甲', '乙']
        self.assertEqual(icc.model_bar_selection(None, items, '乙'), '乙')
        self.assertEqual(icc.model_bar_selection(None, items, '丙'), '甲')
        self.assertEqual(icc.model_bar_selection(None, [], '甲'), icc.ALL_MODELS)
        self.assertEqual(icc.model_bar_selection(icc.ALL_MODELS, items, '乙'), '乙')
        self.assertEqual(icc.model_bar_selection('乙', items, '甲'), '乙')
        self.assertEqual(icc.model_bar_selection('丙', items, '甲'), '甲')


class DesktopDelegationTests(unittest.TestCase):
    """L4 只保留入口：搬到 L0/L3 的实现换了，口径也不能变（无 self 的裸入口可直呼）。"""

    view = object()

    def test_bubble_helpers_match_the_l3_functions(self):
        row = {'role': 'assistant', 'model': 'M'}
        self.assertEqual(Desktop.bubble_time(self.view, '20261012_081530'),
                         icc.bubble_timestamp('20261012_081530'))
        self.assertEqual(Desktop.bubble_preview(self.view, 'x' * 500), icc.collapse_preview('x' * 500))
        self.assertEqual(Desktop.model_name(self.view, row), icc.speaker_name(row))

    def test_open_folder_delegates_to_the_platform_adapter(self):
        import desktop
        with patch.object(desktop, 'open_directory') as open_directory:
            Desktop.open_folder(self.view, Path('somewhere'))
        open_directory.assert_called_once_with(Path('somewhere'))

    def test_shortcut_lookup_delegates_to_the_platform_adapter(self):
        import desktop
        sentinel = Path('C:/found.lnk')
        # R1995：入口经 media_page_services 转发；服务按名字晚绑定 desktop.find_editor_shortcut，补丁照常生效。
        view = SimpleNamespace(media_page_services=SimpleNamespace(find_editor_shortcut=desktop._late('find_editor_shortcut')))
        with patch.object(desktop, 'find_editor_shortcut', return_value=sentinel) as find:
            self.assertEqual(Desktop.find_editor_shortcut(view), sentinel)
        find.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()

