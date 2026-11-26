"""R1976：提示浮层不抢 grab、自动云朵框不在用户拖窗时弹出。"""
import sys
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ui import pet_cloud as pc
from ui import pet_cloud_move_guard as guard
import tk_test_support
import ui_theme
from ui_widgets import Tooltip


class TooltipPassiveTests(unittest.TestCase):
    def test_tooltip_keeps_geometry_alpha_and_takes_no_grab(self):
        root = tk_test_support.make_root()
        self.addCleanup(root.destroy)
        root.geometry('600x400+0+0')
        ui_theme.install_window_placement(root)
        label = tk.Label(root, text='x')
        label.pack()
        tip = Tooltip(label, '说明文字', delay_ms=0)
        tip._position = (30, 40)
        root.update()
        window = tip.show()
        tk_test_support.pump(root, .3)
        self.assertIs(tip._window, window)
        self.assertIsNone(window.grab_status(), '提示浮层不得持有 grab')
        self.assertEqual(float(window.attributes('-alpha')), 1.0)
        self.assertTrue(window.geometry().endswith('+30+40'), window.geometry())
        window.destroy()


class CloudMoveGuardTests(unittest.TestCase):
    def cloud(self, moving):
        cloud = pc.Cloud.__new__(pc.Cloud)
        cloud.parent = Mock()
        cloud.parent.after = Mock(return_value='job')
        cloud.win = None
        cloud.visible = False
        cloud.build = Mock()
        cloud.move_probe = Mock(return_value=moving)
        return cloud

    def test_auto_show_waits_while_window_is_dragged(self):
        c = self.cloud(True)
        self.assertIsNone(c.show(pinned=True, hold=5, focus=False))
        c.build.assert_not_called()
        c.parent.after.assert_called_once_with(guard.MOVE_RETRY_MS, c._move_callback)
        c.show(pinned=True, hold=9, focus=False)           # 后来的覆盖先来的，不重复挂定时器
        c.parent.after.assert_called_once()
        self.assertEqual(c._move_pending['hold'], 9)

    def test_user_opened_cloud_is_not_deferred(self):
        c = self.cloud(True)
        c.build.return_value = None
        c.show(focus=True)
        c.build.assert_called_once()
        c.parent.after.assert_not_called()

    def test_released_drag_replays_latest_show(self):
        c = self.cloud(True)
        c.show(pinned=True, hold=7, focus=False, shape='puff')
        c.move_probe.return_value = False
        c.show = Mock(return_value='shown')
        self.assertEqual(c._move_retry(), 'shown')
        c.show.assert_called_once_with(pinned=True, hold=7, focus=False, shape='puff')
        self.assertIsNone(c._move_pending)

    def test_still_dragging_polls_again_and_cap_forces_show(self):
        c = self.cloud(True)
        c.show(pinned=True, hold=1, focus=False)
        c._move_retry()
        self.assertEqual(c.parent.after.call_count, 2, '还在拖就继续等')
        c._move_waits = guard.MOVE_RETRY_MAX
        c.build.return_value = None
        c._move_retry()
        c.build.assert_called_once()                       # 封顶后不再排队，直接走正常显示

    def test_cancel_clears_pending_and_timer(self):
        c = self.cloud(True)
        c.show(pinned=True, hold=1, focus=False)
        c._cancel_move_wait()
        c.parent.after_cancel.assert_called_once_with('job')
        self.assertIsNone(c._move_pending)

    def test_probe_is_false_off_windows_or_when_query_fails(self):
        self.assertIn(guard.in_move_size(), (True, False))
        self.assertFalse(guard.in_move_size() and sys.platform != 'win32')


if __name__ == '__main__':
    unittest.main()
