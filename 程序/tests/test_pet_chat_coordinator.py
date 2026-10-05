"""无 Tk 的内存调度／视图 adapter，验证同一协调 interface。"""
import unittest

from pet_chat_coordinator import ChatCoordinator


class CoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.jobs = {}
        self.events = []
        self.visible = False
        self.sequence = 0
        self.schedule_error = None
        self.cancel_error = None
        self.coordinator = ChatCoordinator(
            schedule=self.schedule, cancel=self.cancel, delay=250,
            visible=lambda: self.visible, open_chat=self.open,
            close_chat=self.close, mute=lambda **kw: self.events.append(('mute', kw)),
            on_error=lambda *error: self.events.append(('error', error)))

    def schedule(self, delay, callback):
        if self.schedule_error is not None:
            raise self.schedule_error
        self.sequence += 1
        key = str(self.sequence)
        self.jobs[key] = callback
        self.events.append(('schedule', delay, key))
        return key

    def cancel(self, key):
        if self.cancel_error is not None:
            self.assertIsNone(self.coordinator.pending)
            raise self.cancel_error
        self.events.append(('cancel', key))
        del self.jobs[key]

    def open(self):
        self.events.append('open')
        self.visible = True
        return 'widget'

    def close(self):
        self.events.append('close')
        self.visible = False
        return None

    def test_single_waits_then_opens(self):
        key = self.coordinator.request_single()
        self.assertFalse(self.visible)
        self.assertEqual(self.coordinator.pending, key)
        self.assertEqual(self.jobs.pop(key)(), 'widget')
        self.assertIsNone(self.coordinator.pending)
        self.assertEqual(self.events, [('schedule', 250, key), 'open'])

    def test_double_cancels_before_opening(self):
        key = self.coordinator.request_single()
        self.assertEqual(self.coordinator.request_double(), 'widget')
        self.assertEqual(self.events[-2:], [('cancel', key), 'open'])
        self.assertEqual(self.jobs, {})
        self.assertIsNone(self.coordinator.pending)

    def test_repeated_single_has_one_owner(self):
        first = self.coordinator.request_single()
        second = self.coordinator.request_single()
        self.assertEqual(list(self.jobs), [second])
        self.assertEqual(self.events, [('schedule', 250, first), ('cancel', first),
                                       ('schedule', 250, second)])

    def test_visible_flip_mutes_before_close(self):
        self.visible = True
        self.assertIsNone(self.coordinator.flip(at=12))
        self.assertEqual(self.events, [('mute', {'at': 12}), 'close'])

    def test_toggle_uses_reference_not_visibility_and_does_not_mute(self):
        self.visible = False
        self.assertIsNone(self.coordinator.toggle(True))
        self.visible = True
        self.assertEqual(self.coordinator.toggle(False), 'widget')
        self.assertEqual(self.events, ['close', 'open'])

    def test_guards_close_only_when_blocked_and_visible(self):
        self.assertFalse(self.coordinator.guard(True))
        self.visible = True
        self.assertFalse(self.coordinator.guard(False))
        self.assertTrue(self.coordinator.guard(True))
        self.assertFalse(self.coordinator.guard(True))
        self.assertEqual(self.events, ['close'])

    def test_guard_leaves_pending_click_untouched(self):
        key = self.coordinator.request_single()
        self.visible = True
        self.assertTrue(self.coordinator.guard(True))
        self.assertEqual(self.coordinator.pending, key)
        self.assertIn(key, self.jobs)

    def test_cancel_is_idempotent(self):
        key = self.coordinator.request_single()
        self.assertEqual(self.coordinator.cancel_pending(), key)
        self.assertIsNone(self.coordinator.cancel_pending())
        self.assertEqual(self.events, [('schedule', 250, key), ('cancel', key)])

    def test_schedule_failure_reports_before_immediate_flip(self):
        self.schedule_error = RuntimeError('schedule failed')
        self.assertEqual(self.coordinator.request_single(), 'widget')
        self.assertEqual(self.events, [('error', ('click', 'schedule failed')), 'open'])
        self.assertIsNone(self.coordinator.pending)

    def test_cancel_failure_clears_pending_and_prevents_double_open(self):
        key = self.coordinator.request_single()
        self.cancel_error = ValueError('cancel failed')
        with self.assertRaisesRegex(ValueError, 'cancel failed'):
            self.coordinator.request_double()
        self.assertFalse(self.visible)
        self.assertIsNone(self.coordinator.pending)
        self.assertIn(key, self.jobs)


if __name__ == '__main__':
    unittest.main()
