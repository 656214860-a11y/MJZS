"""R1948：三虎弹窗只在有待办时出现；云朵停留随用户操作疏密伸缩；主动关闭后安静期逐次加长。"""
import unittest
from types import SimpleNamespace
from unittest import mock

import pet_bus
import pet_cloud as pc
from test_pet_ui import PetTestCase
from ui_tokens import (PET_ACTIVITY_BUSY_COUNT, PET_ACTIVITY_WINDOW_SECONDS, PET_CLOUD_AUTO_CLOSE_MS,
                       PET_CLOUD_BUSY_CLOSE_MS, PET_CLOUD_IDLE_CLOSE_MS, PET_DISMISS_MUTE_SECONDS,
                       PET_DISMISS_WINDOW_SECONDS)


class StageTodoTests(PetTestCase):
    """换页没有待办：不播进度、不问、不派发。"""

    def setUp(self):
        super().setUp()
        self.now = 1000.0
        self.pet.clock = lambda: self.now
        self.fake.page_index = 0
        self.spoken = []
        self.pet.broadcast = lambda text, **_kwargs: self.spoken.append(text) or text

    def test_hint_and_semi_stay_silent_without_todo(self):
        for level in ('hint', 'semi'):
            self.pet.agent.set_level(level)
            self.assertFalse(self.pet.stage_has_todo(0))
            self.assertEqual(self.pet.enter_stage(page=0, at=self.now), '')
        self.assertEqual(self.spoken, [])

    def test_failure_or_blocked_state_counts_as_todo(self):
        self.pet.agent.set_level('hint')
        self.pet.agent.failures.append({'stage': 'script', 'category': 'unknown'})
        self.assertTrue(self.pet.stage_has_todo(0))
        self.pet.agent.failures.clear()
        with mock.patch.object(self.pet, 'stage_states', return_value={'script': 'blocked'}):
            self.assertTrue(self.pet.stage_has_todo(0))

    def test_muted_or_paused_suppresses_todo(self):
        self.pet.agent.set_level('hint')
        self.pet.agent.failures.append({'stage': 'script', 'category': 'unknown'})
        self.pet.mute(seconds=60, at=self.now)
        self.assertFalse(self.pet.stage_has_todo(0))
        self.pet._mute_until = 0.0
        self.pet.agent.pause('测试')
        self.assertFalse(self.pet.stage_has_todo(0))

    def test_auto_counts_only_until_dispatched(self):
        self.pet.agent.set_level('auto')
        self.assertTrue(self.pet.stage_has_todo(0))
        self.pet._stage_auto_started.add((str(self.fake.root), pet_bus.STAGES[0]))
        self.assertFalse(self.pet.stage_has_todo(0))


class DwellAndDismissTests(PetTestCase):
    def setUp(self):
        super().setUp()
        self.now = 5000.0
        self.pet.clock = lambda: self.now

    def test_dwell_follows_activity_density(self):
        self.assertEqual(self.pet.cloud_dwell_ms(), PET_CLOUD_IDLE_CLOSE_MS)
        self.pet.note_activity()
        self.assertEqual(self.pet.cloud_dwell_ms(), PET_CLOUD_AUTO_CLOSE_MS)
        for _ in range(PET_ACTIVITY_BUSY_COUNT):
            self.pet.note_activity()
        self.assertEqual(self.pet.cloud_dwell_ms(), PET_CLOUD_BUSY_CLOSE_MS)
        self.now += PET_ACTIVITY_WINDOW_SECONDS + 1
        self.assertEqual(self.pet.cloud_dwell_ms(), PET_CLOUD_IDLE_CLOSE_MS)
        self.assertGreater(PET_CLOUD_IDLE_CLOSE_MS, PET_CLOUD_AUTO_CLOSE_MS)
        self.assertGreater(PET_CLOUD_AUTO_CLOSE_MS, PET_CLOUD_BUSY_CLOSE_MS)

    def test_button_tap_counts_as_activity(self):
        self.pet.tap('测试按钮')
        self.assertEqual(self.pet.cloud_dwell_ms(), PET_CLOUD_AUTO_CLOSE_MS)

    def test_repeated_dismissals_lengthen_mute(self):
        for step in PET_DISMISS_MUTE_SECONDS + (PET_DISMISS_MUTE_SECONDS[-1],):
            self.assertEqual(self.pet.dismissed(at=self.now), self.now + step)
            self.now += 1
        self.now += PET_DISMISS_WINDOW_SECONDS + PET_DISMISS_MUTE_SECONDS[-1]
        self.assertEqual(self.pet.dismissed(at=self.now), self.now + PET_DISMISS_MUTE_SECONDS[0])

    def test_single_click_close_goes_through_dismissed(self):
        with mock.patch.object(self.pet, 'cloud_visible', return_value=True), \
                mock.patch.object(self.pet, 'close_chat'), \
                mock.patch.object(self.pet, 'dismissed') as dismissed:
            self.pet._chat_interaction.flip(at=self.now)
        dismissed.assert_called_once_with(at=self.now)


class CloudHoldTests(unittest.TestCase):
    def cloud(self, pet):
        cloud = pc.Cloud.__new__(pc.Cloud)
        cloud.pet = pet
        cloud.parent = SimpleNamespace(after=mock.Mock(return_value='timer'), after_cancel=mock.Mock())
        cloud.win = SimpleNamespace(focus_get=mock.Mock(return_value=None))
        cloud.reply = object()
        cloud._pointer_inside = mock.Mock(return_value=False)
        cloud._hold = None
        cloud._watching = False
        cloud.visible = True
        cloud.busy = False
        cloud.errors = []
        return cloud

    def test_idle_hold_asks_pet_for_dwell(self):
        c = self.cloud(SimpleNamespace(cloud_dwell_ms=lambda: PET_CLOUD_BUSY_CLOSE_MS))
        c._arm_hold()
        c.parent.after.assert_called_with(PET_CLOUD_BUSY_CLOSE_MS, c._expire)

    def test_hold_falls_back_when_pet_has_no_dwell(self):
        for pet in (SimpleNamespace(), SimpleNamespace(cloud_dwell_ms=mock.Mock(side_effect=ValueError))):
            c = self.cloud(pet)
            c._arm_hold()
            c.parent.after.assert_called_with(PET_CLOUD_AUTO_CLOSE_MS, c._expire)


if __name__ == '__main__':
    unittest.main()
