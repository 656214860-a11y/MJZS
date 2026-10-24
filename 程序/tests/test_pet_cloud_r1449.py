"""R1449: deterministic idle timers and popup presentation."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

import pet_cloud as pc
from ui_tokens import FONTS, PET_CLOUD_AUTO_CLOSE_MS


class PopupTests(unittest.TestCase):
    def cloud(self):
        cloud = pc.Cloud.__new__(pc.Cloud)
        cloud.parent = SimpleNamespace(after=Mock(return_value='timer'), after_cancel=Mock())
        cloud.win = SimpleNamespace(focus_get=Mock(return_value=None))
        cloud.reply = object()
        cloud._pointer_inside = Mock(return_value=False)
        cloud._hold = None
        cloud._watching = False
        cloud.visible = True
        cloud.busy = False
        cloud.errors = []
        return cloud

    def test_timer_restart_hover_and_focus(self):
        c = self.cloud()
        c._arm_hold(1)
        c.parent.after.assert_called_with(PET_CLOUD_AUTO_CLOSE_MS, c._expire)
        c._arm_hold()
        c.parent.after_cancel.assert_called_with('timer')
        c._pointer_inside.return_value = True
        c._interaction_changed()
        c.parent.after.assert_called_with(pc.WATCH_RECHECK_MS, c._recheck_hold)
        c._pointer_inside.return_value = False
        c.win.focus_get.return_value = c.reply
        c._recheck_hold()
        c.parent.after.assert_called_with(pc.WATCH_RECHECK_MS, c._recheck_hold)
        c.win.focus_get.return_value = None
        c._recheck_hold()
        c.parent.after.assert_called_with(PET_CLOUD_AUTO_CLOSE_MS, c._expire)

    def test_expiry_keeps_pending_history_and_busy(self):
        c = self.cloud()
        c.choice = 'pending command'
        c.lines = ['pending question'] * 20
        c.busy = True
        for name in ('cancel_deferred_render', '_cancel_position', '_cancel_fade', '_hint_stop'):
            setattr(c, name, Mock())
        c.win.attributes = Mock()
        c.win.withdraw = Mock()
        self.assertFalse(c._expire())
        self.assertTrue(c.visible)
        c.parent.after.assert_called_with(pc.WATCH_RECHECK_MS, c._recheck_hold)
        c.busy = False
        self.assertTrue(c._expire())
        self.assertFalse(c.visible)
        self.assertFalse(c.busy)
        self.assertEqual(c.choice, 'pending command')
        self.assertEqual(len(c.lines), 20)

    def test_destroy_cancels_hold(self):
        c = self.cloud()
        for name in ('_cancel_position', '_cancel_fade', '_hint_stop', 'cancel_deferred_render'):
            setattr(c, name, Mock())
        c._arm_hold()
        c._window_gone()
        self.assertIsNone(c._hold)
        c.parent.after_cancel.assert_called_with('timer')

    def test_tokens_and_exact_deduplication(self):
        self.assertEqual(pc.FONT, FONTS['pet_body'])
        self.assertEqual(pc.HINT_FONT, FONTS['pet_hint'])
        self.assertEqual(pc.FONT[1], FONTS['body'][1] - 1)
        c = self.cloud()
        c.shape = pc.SHAPE_CLOUD
        c.lines = ['same', 'same', 'different', 'same']
        self.assertEqual(c._body_text().count('same'), 1)   # 同一句不分相邻与否只露一次
        self.assertEqual(len(c.lines), 4)

    def test_top_alignment_and_edge_fallback(self):
        c = self.cloud()
        c.shape = pc.SHAPE_CLOUD
        c._body = 160
        c._patch_rect = lambda: (700, 100, 48, 48)
        c.width = lambda: 300
        c.total_width = lambda: 346
        c._screen_height = lambda: 900
        c._work_right = lambda: 1200
        c._anchor = lambda: (714, 130)
        c._inside_window = lambda *args: None
        c._avoid_pet = lambda *args: args
        c._near_pet = lambda *args: args
        self.assertEqual(c._origin()[1] + c._shift(), 100)
        self.assertEqual(c._tip()[1] + c._origin()[1], 130)
        c._patch_rect = lambda: (700, 850, 48, 48)
        self.assertFalse(c._can_align_top())
        c._patch_rect = lambda: (100, 100, 48, 48)
        self.assertFalse(c._can_align_top())
