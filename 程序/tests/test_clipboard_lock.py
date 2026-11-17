# -*- coding: utf-8 -*-
"""跨进程剪贴板锁的无 GUI 回归。"""
import unittest

from infra import clipboard_lock


class ClipboardLockTests(unittest.TestCase):
    def test_same_thread_may_reenter_without_releasing_the_process_lock(self):
        with clipboard_lock.hold(timeout=0) as outer:
            self.assertTrue(outer)
            with clipboard_lock.hold(timeout=0) as inner:
                self.assertTrue(inner)
            self.assertIsNone(clipboard_lock._acquire(0, 0))

    def test_second_nonblocking_acquire_is_rejected_until_first_releases(self):
        first = clipboard_lock._acquire(0, 0)
        self.assertIsNotNone(first)
        try:
            self.assertIsNone(clipboard_lock._acquire(0, 0))
        finally:
            clipboard_lock._release(first)
        second = clipboard_lock._acquire(0, 0)
        self.assertIsNotNone(second)
        clipboard_lock._release(second)


if __name__ == '__main__':
    unittest.main(verbosity=2)
