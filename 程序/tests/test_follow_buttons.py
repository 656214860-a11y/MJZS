"""stage_flow.follow 改用 tk_timers.repeat 后：按钮跟着阶段状态刷字，拆了就停，不留残余定时器。"""
import time
import unittest

import stage_flow


class FollowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import tkinter
        from tkinter import ttk
        cls.tk, cls.ttk = tkinter, ttk

    def setUp(self):
        self.root = self.tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.quiet_destroy)
        self.addCleanup(stage_flow.RUNNING.pop, 'assets', None)

    def quiet_destroy(self):
        try:
            self.root.destroy()
        except self.tk.TclError:
            pass

    def pump(self, until, seconds=3):
        end = time.monotonic() + seconds
        while time.monotonic() < end and not until():
            self.root.update()
            time.sleep(0.01)
        return until()

    def test_button_text_follows_the_stage_state(self):
        button = self.ttk.Button(self.root)
        button.pack()
        stage_flow.follow(button, 'assets', interval=10)
        self.assertEqual(str(button.cget('text')), stage_flow.manual_label('assets'))   # 挂上时立刻刷一次
        stage_flow.RUNNING['assets'] = 'auto'
        self.assertTrue(self.pump(lambda: str(button.cget('text')) == stage_flow.RUNNING_LABEL))
        self.assertEqual(str(button.cget('state')), 'disabled')
        stage_flow.RUNNING.pop('assets')
        self.assertTrue(self.pump(lambda: str(button.cget('text')) == stage_flow.manual_label('assets')))
        self.assertEqual(str(button.cget('state')), 'normal')

    def test_destroying_the_button_leaves_no_pending_timer(self):
        button = self.ttk.Button(self.root)
        button.pack()
        stage_flow.follow(button, 'assets', interval=10)
        self.root.update()
        before = set(self.root.tk.call('after', 'info'))
        self.assertTrue(before)
        button.destroy()
        self.root.update()
        self.assertEqual(set(self.root.tk.call('after', 'info')), set(), '按钮拆了定时器也要撤掉')

    def test_stop_ends_the_refresh_early(self):
        button = self.ttk.Button(self.root)
        button.pack()
        stop = stage_flow.follow(button, 'assets', interval=10)
        stop()
        stage_flow.RUNNING['assets'] = 'auto'
        self.pump(lambda: False, 0.2)
        self.assertEqual(str(button.cget('text')), stage_flow.manual_label('assets'))


if __name__ == '__main__':
    unittest.main()
