"""J19：请求生命周期的判定在无 Tk 的 idea_chat_controller 里，直接断言。"""
import unittest

from orchestrator.idea_chat_controller import (IdeaChatController, has_interruptible, interrupt_notice,
                                  queue_notice, slot_decision)


class SlotDecisionTests(unittest.TestCase):
    def test_granted_queued_and_refused(self):
        self.assertEqual(slot_decision({'state': 'granted', 'slot': 'S'}), ('run', 'S'))
        self.assertEqual(slot_decision({'state': 'queued', 'position': 2}), ('wait', 2))
        self.assertEqual(slot_decision({'state': 'cancelled', 'reason': '已撤销'}), ('refuse', '已撤销'))
        self.assertEqual(slot_decision({'state': 'cancelled'}), ('refuse', '模型请求已取消'))

    def test_queue_notice_shows_position(self):
        self.assertIn('第3位', queue_notice(3))


class InterruptTests(unittest.TestCase):
    def test_nothing_to_interrupt_only_when_all_idle(self):
        self.assertFalse(has_interruptible(False, [], False, False))
        for flags in ((True, [], False, False), (False, [1], False, False),
                      (False, [], True, False), (False, [], False, True)):
            self.assertTrue(has_interruptible(*flags))

    def test_notice_mentions_processes_and_archive_only_when_relevant(self):
        text = interrupt_notice(['12', '34'], True, '后台仍在取消。')
        self.assertIn('已结束进程 12, 34', text)
        self.assertIn('responses/', text)
        self.assertTrue(text.endswith(' 后台仍在取消。'))
        plain = interrupt_notice([], False)
        self.assertNotIn('进程', plain)
        self.assertNotIn('responses/', plain)


class AcceptsTests(unittest.TestCase):
    def test_result_accepted_only_for_live_uncancelled_same_project(self):
        controller = IdeaChatController()
        token, cancelled = controller.begin_request(cancellable=True)
        self.assertTrue(controller.accepts(token, cancelled, 'P', 'P'))
        self.assertFalse(controller.accepts(token, cancelled, 'Q', 'P'))
        cancelled.set()
        self.assertFalse(controller.accepts(token, cancelled, 'P', 'P'))

    def test_finished_request_is_not_accepted(self):
        controller = IdeaChatController()
        token, cancelled = controller.begin_request(cancellable=True)
        controller.finish_request(token)
        self.assertFalse(controller.accepts(token, cancelled, 'P', 'P'))


if __name__ == '__main__':
    unittest.main()
