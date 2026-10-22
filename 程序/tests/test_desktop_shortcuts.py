# -*- coding: utf-8 -*-
"""主窗口键盘快捷键：Ctrl+数字跳页、Ctrl+PageUp／PageDown 翻页，文本框里不抢键。"""
import unittest
from types import SimpleNamespace

from desktop_layout import LayoutMixin


def subject(focus_class='Frame', page_index=2, pages=13):
    went = []
    focus = SimpleNamespace(winfo_class=lambda: focus_class)
    stub = SimpleNamespace(win=SimpleNamespace(focus_get=lambda: focus), nav=[None] * pages,
                           page_index=page_index, go_page=went.append)
    return stub, went


def press(stub, key):
    return LayoutMixin.page_shortcut(stub, SimpleNamespace(keysym=key))


class PageShortcutTests(unittest.TestCase):
    def test_ctrl_digit_jumps_to_that_page(self):
        stub, went = subject()
        self.assertEqual(press(stub, '1'), 'break')
        press(stub, '9'); press(stub, '0')
        self.assertEqual(went, [0, 8, 9])

    def test_ctrl_page_keys_step_and_wrap(self):
        stub, went = subject(page_index=0)
        press(stub, 'Prior'); press(stub, 'Next')
        self.assertEqual(went, [12, 1])

    def test_text_inputs_keep_their_own_keys(self):
        for klass in ('Text', 'TEntry', 'Entry'):
            stub, went = subject(focus_class=klass)
            self.assertIsNone(press(stub, '3'))
            self.assertEqual(went, [])

    def test_out_of_range_does_nothing(self):
        stub, went = subject(pages=5)
        self.assertIsNone(press(stub, '8'))
        self.assertEqual(went, [])

    def test_handler_is_bound_on_the_main_window(self):
        import inspect, desktop
        source = inspect.getsource(desktop)
        self.assertIn("self.page_shortcut", source)
        self.assertIn("<Control-Prior>", source)



class GearTooltipTests(unittest.TestCase):
    def test_icon_only_gear_has_a_tooltip(self):
        import tkinter as tk
        from pet_ui_support import GearButton, GEAR_TIP
        root = tk.Tk(); root.withdraw()
        try:
            gear = GearButton(root)
            self.assertIsNotNone(gear.tooltip)
            self.assertEqual(gear.tooltip.text, GEAR_TIP)
        finally:
            root.destroy()


class ReduceMotionTests(unittest.TestCase):
    def setUp(self):
        import os, ui_motion
        self.motion = ui_motion
        self.saved = os.environ.get(ui_motion.REDUCE_MOTION_ENV)
        self.addCleanup(self.restore)

    def restore(self):
        import os
        if self.saved is None:
            os.environ.pop(self.motion.REDUCE_MOTION_ENV, None)
        else:
            os.environ[self.motion.REDUCE_MOTION_ENV] = self.saved

    def test_environment_switch_wins(self):
        import os
        os.environ[self.motion.REDUCE_MOTION_ENV] = '1'
        self.assertTrue(self.motion.reduce_motion())
        os.environ[self.motion.REDUCE_MOTION_ENV] = '0'
        self.assertFalse(self.motion.reduce_motion())

    def test_cloud_fade_out_skips_steps_when_reduced(self):
        import os, inspect, pet_cloud_timing
        source = inspect.getsource(pet_cloud_timing.CloudTimingMixin)
        self.assertIn('reduce_motion()', source)


if __name__ == '__main__':
    unittest.main()
