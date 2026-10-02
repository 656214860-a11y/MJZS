"""统一 Tooltip 的无显示环境回归。"""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from ui_widgets import Tooltip


class _Widget:
    def __init__(self):
        self.bindings = []
        self.cancelled = []
        self._next_job = 0

    def bind(self, sequence, callback, add=None):
        self.bindings.append((sequence, callback, add))

    def after(self, delay, callback):
        self._next_job += 1
        self.last_delay, self.last_callback = delay, callback
        return "job-%d" % self._next_job

    def after_cancel(self, job):
        self.cancelled.append(job)

    def winfo_exists(self): return True
    def winfo_rootx(self): return 100
    def winfo_rooty(self): return 200
    def winfo_height(self): return 20


class _Tip:
    def __init__(self): self.destroyed = False
    def overrideredirect(self, value): self.overrideredirect_value = value
    def configure(self, **kwargs): self.options = kwargs
    def geometry(self, value): self.geometry_value = value
    def destroy(self): self.destroyed = True


class _Label:
    def __init__(self, *_args, **_kwargs): pass
    def pack(self, **kwargs): self.pack_options = kwargs


class TooltipTests(unittest.TestCase):
    def test_mouse_and_keyboard_accessibility_bindings_share_the_component(self):
        widget = _Widget()
        Tooltip(widget, "完整说明")
        self.assertEqual([item[0] for item in widget.bindings],
                         ["<Enter>", "<Leave>", "<FocusIn>", "<FocusOut>", "<Destroy>"])
        self.assertTrue(all(item[2] == "+" for item in widget.bindings))

    def test_reenter_cancels_old_delayed_show_and_leave_cleans_up(self):
        widget = _Widget()
        tooltip = Tooltip(widget, "完整说明")
        tooltip.schedule()
        tooltip.schedule()
        self.assertEqual(widget.cancelled, ["job-1"])
        self.assertEqual(tooltip._job, "job-2")
        tooltip.hide()
        self.assertEqual(widget.cancelled, ["job-1", "job-2"])
        self.assertIsNone(tooltip._job)

    def test_focus_schedule_and_destroyed_widget_remove_the_tip_safely(self):
        widget = _Widget()
        tooltip = Tooltip(widget, "完整说明")
        tooltip._schedule_from_focus()
        self.assertEqual(tooltip._position, (108, 228))
        tip = _Tip()
        tooltip._window = tip
        tooltip._on_widget_destroyed()
        self.assertTrue(tip.destroyed)
        self.assertIsNone(tooltip._window)

    def test_show_creates_non_modal_tip_without_grab(self):
        widget, tip = _Widget(), _Tip()
        tooltip = Tooltip(widget, "完整说明")
        with patch("ui_widgets.tk.Toplevel", return_value=tip), \
             patch("ui_widgets.tk.Label", _Label):
            self.assertIs(tooltip.show(), tip)
        self.assertTrue(tip.overrideredirect_value)
        self.assertEqual(tip.geometry_value, "+108+208")
