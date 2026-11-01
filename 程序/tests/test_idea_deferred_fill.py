"""J18：首绘后「布局稳定」判定在无 Tk 的 DeferredFill 里，时钟注入，不必真等。"""
import unittest

from idea_chat_controller import DeferredFill


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


class DeferredFillTests(unittest.TestCase):
    def test_fills_after_consecutive_stable_ticks(self):
        fill = DeferredFill(Clock(), ticks=3, timeout=2.0)
        self.assertEqual([fill.ready(False) for _ in range(3)], [False, False, True])

    def test_pending_layout_resets_the_stable_count(self):
        fill = DeferredFill(Clock(), ticks=3, timeout=2.0)
        self.assertEqual([fill.ready(p) for p in (False, False, True, False, False, False)],
                         [False, False, False, False, False, True])

    def test_timeout_fills_even_while_layout_keeps_changing(self):
        clock = Clock()
        fill = DeferredFill(clock, ticks=3, timeout=2.0)
        self.assertFalse(fill.ready(True))
        clock.now += 2.0
        self.assertTrue(fill.ready(True))


if __name__ == '__main__':
    unittest.main()
