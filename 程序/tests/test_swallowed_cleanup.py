# -*- coding: utf-8 -*-
"""T5 静默异常核销：清理路径的故障必须经 app_logging.swallowed 留痕。"""
import unittest

import app_logging
import smoke_test


class SwallowedCleanupTests(unittest.TestCase):
    def test_widget_check_destroy_failure_leaves_trace(self):
        """check_tkinter_widget 收尾销毁失败不得无声吞掉。"""
        import tkinter as tk
        original = tk.Tk.destroy
        app_logging._recent_swallowed.clear()
        before = len(app_logging._recent_swallowed)
        try:
            def boom(_root):
                raise RuntimeError('simulated destroy failure')
            tk.Tk.destroy = boom
            smoke_test.check_tkinter_widget('tkinter', 'Frame')
        finally:
            tk.Tk.destroy = original
        self.assertGreater(len(app_logging._recent_swallowed), before)


if __name__ == '__main__':
    unittest.main()
