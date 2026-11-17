"""Pet 播报状态容器（R1983 J5）：判重、压住、推进节流只在 PetBroadcastState 一处。"""
from __future__ import annotations

import unittest

from orchestrator.pet_broadcast_state import PetBroadcastAliasesMixin, PetBroadcastState, PetOfferState


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
    def test_public_names_forward_and_lazy_state(self):
        class Holder(PetBroadcastAliasesMixin):
            pass
        holder = Holder()
        holder.last_status = 'x'
        holder.notice = 'n'
        self.assertEqual((holder.bstate.last_status, holder.bstate.notice), ('x', 'n'))
        holder.bstate.notice = 'm'
        self.assertEqual(holder.notice, 'm')

    def test_retired_underscore_names_are_gone(self):
        class Holder(PetBroadcastAliasesMixin):
            pass
        for name in ('_announced', '_last_broadcast', '_held_broadcast', '_advance_at'):
            with self.subTest(name=name), self.assertRaises(AttributeError):
                getattr(Holder(), name)
        with self.assertRaises(AttributeError):
            Holder().nothing

    def test_offer_state_defaults_match_the_old_attributes(self):
        offer = PetOfferState()
        self.assertEqual((offer.at, offer.sig, offer.open, offer.backoff, offer.declined),
                         (None, (), False, 1, None))

    def test_offer_state_is_created_on_demand_for_bare_pets(self):
        class Holder(PetBroadcastAliasesMixin):
            pass
        holder = Holder()
        holder.offer.open = True
        self.assertTrue(holder.offer.open)
        self.assertIs(holder.offer, holder.offer)

    def test_cloud_hint_state_defaults_match_the_old_attributes(self):
        from ui import pet_cloud_hint
        state = pet_cloud_hint.CloudHintState()
        self.assertEqual((state.job, state.on, state.x, state.user_focus),
                         (None, False, pet_cloud_hint.HINT_X, False))


if __name__ == '__main__':
    unittest.main()
