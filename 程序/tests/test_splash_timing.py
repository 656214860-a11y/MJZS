"""启动画面耗时：只记录、不挡路（R1777 审计第 27 项）。不起 Tk，直接测 Splash 的计时方法。"""
import time
import unittest

from ui_widgets import Splash


def bare_splash():
    splash = Splash.__new__(Splash)   # 绕开 Tk 窗口创建
    splash.start = time.perf_counter()
    splash.marks = {}
    splash.on_finish = None
    return splash


class SplashTimingTests(unittest.TestCase):
    def test_mark_keeps_the_first_time_for_a_name(self):
        splash = bare_splash()
        splash._mark('ready')
        first = splash.marks['ready']
        time.sleep(0.01)
        splash._mark('ready')
        self.assertEqual(splash.marks['ready'], first)

    def test_report_delivers_marks_once(self):
        splash = bare_splash()
        got = []
        splash.on_finish = got.append
        splash._mark('total')
        splash._report()
        splash._report()
        self.assertEqual(len(got), 1)
        self.assertIn('total', got[0])

    def test_a_failing_callback_does_not_propagate(self):
        splash = bare_splash()

        def boom(_marks):
            raise RuntimeError('诊断目录不可写')
        splash.on_finish = boom
        splash._report()   # 不抛


class SplashCapTests(unittest.TestCase):
    def test_wait_caps_the_cover_time(self):
        """启动画面最长盖 SPLASH_MAX_SECONDS：页面没建完也强制揭开，不再一路等到 15 秒。"""
        import inspect
        import ui_tokens
        default = inspect.signature(Splash.wait).parameters['timeout'].default
        self.assertEqual(default, ui_tokens.SPLASH_MAX_SECONDS)
        self.assertLessEqual(default, 2.5)


if __name__ == '__main__':
    unittest.main()
