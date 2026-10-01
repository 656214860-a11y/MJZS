# -*- coding: utf-8 -*-
"""云朵框文本职责不依赖 Tk。"""
import unittest

import pet_cloud_text


class PetCloudTextTests(unittest.TestCase):
    def test_tight_keeps_meaningful_newlines_and_nonbreaking_gap(self):
        self.assertEqual(pet_cloud_text.tight('  第一行  \n\n2.\xa0正文\t '), '第一行\n2.\xa0正文')

    def test_reply_lines_describes_a_blocked_action(self):
        self.assertEqual(
            pet_cloud_text.reply_lines({'reply': '开始 生成', 'decision': {'run': False, 'reason': '需要 确认'}},
                                       '三虎', '暂时不动手——'),
            ['三虎：开始 生成', '三虎：暂时不动手——需要 确认'])


if __name__ == '__main__':
    unittest.main()
