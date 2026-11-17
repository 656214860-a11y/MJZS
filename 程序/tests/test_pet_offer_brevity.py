# -*- coding: utf-8 -*-
"""三虎主动提问要短、用户怎么答都接得上、回答不刷屏。"""
import unittest
from types import SimpleNamespace

import pet_agent
from ui import pet_cloud_text
import pet_ui_voice
from ui.pet_ui_support import OFFER_MAX_CHARS


class OfferTextTests(unittest.TestCase):
    def test_only_the_first_gap_is_spelled_out_and_navigation_is_dropped(self):
        parts = ['3 份分镜 JSON 还没采用（初步分镜 → 手动采用分镜）',
                 '首帧还差 12 个镜头（首帧管理 → 手动制作首帧）', '还有 2 项待确认要收尾']
        text = pet_ui_voice.PetVoiceMixin.offer_text(None, parts)
        self.assertLessEqual(len(text), OFFER_MAX_CHARS)
        self.assertIn('3 份分镜 JSON 还没采用', text)
        self.assertIn('等 3 件事', text)
        self.assertNotIn('→', text)
        self.assertIn('先不用', text)


class OfferVerdictTests(unittest.TestCase):
    def test_loose_answers_are_understood(self):
        for word in ('好', '好啊做吧', '行吧', '可以的', '开始吧'):
            self.assertIs(pet_ui_voice.offer_verdict(word), True, word)
        for word in ('先不用', '不用了谢谢', '算了吧', '回头再说吧'):
            self.assertIs(pet_ui_voice.offer_verdict(word), False, word)

    def test_unrelated_sentences_are_not_taken_as_answers(self):
        for word in ('是什么意思', '帮我把首帧生成一下', '要不要先看看分镜呢'):
            self.assertIsNone(pet_ui_voice.offer_verdict(word), word)


class ReplyClipTests(unittest.TestCase):
    def test_long_reply_is_clipped_in_the_cloud(self):
        lines = pet_cloud_text.reply_lines({'reply': '很' * 300, 'decision': {'run': True}}, '三虎', '需要确认：')
        self.assertLessEqual(len(lines[0]), len('三虎：') + pet_cloud_text.REPLY_MAX_CHARS)
        self.assertTrue(lines[0].endswith(pet_cloud_text.REPLY_MORE))

    def test_short_reply_is_untouched(self):
        lines = pet_cloud_text.reply_lines({'reply': '好的', 'decision': {'run': True}}, '三虎', '需要确认：')
        self.assertEqual(lines, ['三虎：好的'])


class PendingOfferContextTests(unittest.TestCase):
    def test_pending_question_reaches_the_router_context(self):
        agent = SimpleNamespace(machine=None, projects_snapshot=lambda: [], pending_offer='要我一键执行吗？')
        self.assertEqual(pet_agent.Agent.context(agent), {'pending_offer': '要我一键执行吗？'})
        agent.pending_offer = ''
        self.assertEqual(pet_agent.Agent.context(agent), {})


if __name__ == '__main__':
    unittest.main()
