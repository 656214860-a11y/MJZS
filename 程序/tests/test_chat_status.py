# -*- coding: utf-8 -*-
"""对话状态机（R3103）：ChatStatus、取消令牌、继续/重新生成、消息队列、副作用幂等。

运行：python tests/test_chat_status.py
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orchestrator.idea_chat_controller import ChatStatus, IdeaChatController


class ChatStatusTests(unittest.TestCase):
    def test_submitted_streaming_ready_transitions(self):
        controller = IdeaChatController()
        self.assertEqual(controller.status, ChatStatus.READY)
        token, _ = controller.begin_request(cancellable=True, request={'text': 'hi'})
        self.assertEqual(controller.status, ChatStatus.SUBMITTED)
        self.assertTrue(controller.mark_streaming(token))
        self.assertEqual(controller.status, ChatStatus.STREAMING)
        self.assertTrue(controller.finish_request(token))
        self.assertEqual(controller.status, ChatStatus.READY)
        self.assertEqual(controller.stop_reason, '')
        self.assertFalse(controller.can_continue)

    def test_finish_error_sets_error_status(self):
        controller = IdeaChatController()
        token, _ = controller.begin_request(cancellable=True)
        controller.finish_request(token, error=True)
        self.assertEqual(controller.status, ChatStatus.ERROR)
        self.assertEqual(controller.stop_reason, 'error')

    def test_cancel_uses_token_and_allows_continue(self):
        controller = IdeaChatController()
        token, event = controller.begin_request(cancellable=True, request={'text': 'hi'})
        controller.cancel_request()
        self.assertTrue(event.is_set(), '停止必须真正置取消令牌')
        self.assertEqual(controller.status, ChatStatus.READY)
        self.assertEqual(controller.stop_reason, 'cancelled')
        self.assertTrue(controller.can_continue)
        self.assertFalse(controller.finish_request(token), '旧 token 不得再结算新状态')

    def test_max_tokens_marks_can_continue(self):
        controller = IdeaChatController()
        token, _ = controller.begin_request(cancellable=True, request={'text': 'hi'})
        controller.finish_request(token, stop_reason='max_tokens')
        self.assertTrue(controller.can_continue)

    def test_regenerate_reuses_last_request(self):
        controller = IdeaChatController()
        token, _ = controller.begin_request(cancellable=True,
                                            request={'text': 'hi', 'model': 'm'})
        controller.finish_request(token)
        self.assertEqual(controller.regenerate_plan(), {'text': 'hi', 'model': 'm'})

    def test_continue_plan_requires_can_continue(self):
        controller = IdeaChatController()
        token, _ = controller.begin_request(cancellable=True, request={'text': 'hi'})
        controller.finish_request(token)
        self.assertIsNone(controller.continue_plan(partial_text='半'))
        token2, _ = controller.begin_request(cancellable=True, request={'text': 'hi'})
        controller.cancel_request()
        self.assertEqual(controller.continue_plan(partial_text='半'),
                         {'text': 'hi', 'partial': '半'})

    def test_progress_callback_marks_streaming(self):
        controller = IdeaChatController()
        token, _ = controller.begin_request(cancellable=True)
        events = []
        report = controller.progress_callback(token, 7, lambda *event: events.append(event))
        self.assertEqual(controller.status, ChatStatus.SUBMITTED)
        report('角色', 3)
        self.assertEqual(controller.status, ChatStatus.STREAMING)
        self.assertEqual(events, [(7, '角色', 3)])
        controller.finish_request(token)

    def test_pending_send_queue(self):
        controller = IdeaChatController()
        controller.begin_request(cancellable=True)
        self.assertEqual(controller.enqueue_send('一'), 1)
        self.assertEqual(controller.enqueue_send('二'), 2)
        self.assertEqual([item['text'] for item in controller.pending_sends()], ['一', '二'])
        self.assertEqual(controller.pop_pending_send()['text'], '一')
        self.assertEqual(controller.undo_pending_send()['text'], '二')
        self.assertEqual(controller.pending_sends(), [])
        controller.enqueue_send('三')
        controller.clear_pending_sends()
        self.assertEqual(controller.pending_sends(), [])

    def test_side_effects_flag_resets_per_request(self):
        controller = IdeaChatController()
        token, _ = controller.begin_request(cancellable=True)
        self.assertFalse(controller.side_effects_done())
        controller.mark_side_effects_done()
        self.assertTrue(controller.side_effects_done())
        controller.finish_request(token)
        token2, _ = controller.begin_request(cancellable=True)
        self.assertFalse(controller.side_effects_done(), '新请求不得继承上一轮的副作用标记')
        controller.finish_request(token2)


if __name__ == '__main__':
    unittest.main()
