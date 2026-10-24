"""Pet 播报状态容器（R1983 J5）：判重、压住、推进节流只在 PetBroadcastState 一处。"""
from __future__ import annotations

import unittest

from pet_broadcast_state import PetBroadcastAliasesMixin, PetBroadcastState


class StateTests(unittest.TestCase):
    def test_status_dedupe(self):
        state = PetBroadcastState()
        self.assertTrue(state.remember_status('a'))
        self.assertFalse(state.remember_status('a'))
        self.assertTrue(state.remember_status('b'))

    def test_repeat_and_forget(self):
        state = PetBroadcastState()
        state.spoke('x')
        state.announced = ('s',)
        self.assertTrue(state.is_repeat('x'))
        state.forget_spoken()
        self.assertFalse(state.is_repeat('x'))
        self.assertEqual(state.announced, ())

    def test_failure_batch(self):
        state = PetBroadcastState()
        self.assertFalse(state.new_failure_batch(()))
        self.assertTrue(state.new_failure_batch(('a',)))
        self.assertFalse(state.new_failure_batch(('a',)))
        self.assertFalse(state.new_failure_batch(()))
        self.assertEqual(state.announced, ())
        self.assertTrue(state.new_failure_batch(('a',)))

    def test_hold_and_take(self):
        state = PetBroadcastState()
        state.hold('话')
        self.assertEqual(state.take_held(), '话')
        self.assertEqual(state.take_held(), '')

    def test_advance_throttle(self):
        state = PetBroadcastState()
        self.assertFalse(state.advance_throttled(10, 5))
        state.mark_advance(10)
        self.assertTrue(state.advance_throttled(12, 5))
        self.assertFalse(state.advance_throttled(15, 5))
        state.reset_advance()
        self.assertIsNone(state.advance_at)


class AliasTests(unittest.TestCase):
    def test_legacy_names_forward_and_lazy_state(self):
        class Holder(PetBroadcastAliasesMixin):
            pass
        holder = Holder()
        holder._last_broadcast = 'x'
        holder.notice = 'n'
        holder._advance_at = 3
        self.assertEqual((holder.bstate.last_broadcast, holder.bstate.notice, holder.bstate.advance_at), ('x', 'n', 3))
        with self.assertRaises(AttributeError):
            holder.nothing


if __name__ == '__main__':
    unittest.main()
