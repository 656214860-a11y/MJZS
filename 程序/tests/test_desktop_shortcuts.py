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


if __name__ == '__main__':
    unittest.main()
