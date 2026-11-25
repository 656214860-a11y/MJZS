"""设置弹窗「测试连接」共用的两块：后台线程回 Tk 线程交结果，探测文案归 api_endpoints。

从前每个弹窗各自手写线程加轮询，修「跨线程设置 Tk 变量导致状态栏卡在正在检测」要逐个打补丁。
"""
import threading
import time
import unittest
from unittest import mock

import infra.api_endpoints as api_endpoints
import tk_timers


class ProbeMessageTests(unittest.TestCase):
    def message(self, result):
        with mock.patch.object(api_endpoints, 'probe_endpoint', return_value=result):
            return api_endpoints.probe_message('https://api.invalid')

    def test_credential_walls_mean_reachable_but_needs_a_key(self):
        for code in (401, 403):
            with self.subTest(code=code):
                self.assertEqual(self.message({'reachable': True, 'code': code}),
                                 '接口可达（HTTP %d，需密钥）' % code)

    def test_missing_endpoint_points_to_address_and_path(self):
        self.assertEqual(self.message({'reachable': True, 'code': 404}), '接口可达（HTTP 404，请检查接口地址和路径）')

    def test_cloud_probe_recovers_from_full_queue_and_ignores_repeat_clicks(self):
        from ui.cloud_video import _CloudSettingsWindow
        window = _CloudSettingsWindow.__new__(_CloudSettingsWindow)
        window.entries = {'base': mock.Mock(get=lambda: 'https://api.invalid')}
        window.probe_status = mock.Mock()
        window.win = mock.Mock(winfo_exists=lambda: True)
        window.desktop = mock.Mock()
        submit = window.desktop.async_queued
        submit.side_effect = ValueError('队列已满')
        window.probe_endpoint_now()
        self.assertIn('队列已满', window.probe_status.set.call_args.args[0])
        submit.side_effect = None
        window.probe_endpoint_now()
        window.probe_endpoint_now()
        self.assertEqual(submit.call_count, 2)
        work, done = submit.call_args.args
        with mock.patch.object(api_endpoints, 'probe_endpoint', return_value={'reachable': True, 'code': 404}):
            done(work())
        self.assertIn('检查接口地址', window.probe_status.set.call_args.args[0])
        window.probe_endpoint_now()
        self.assertEqual(submit.call_count, 3)

    def test_cancelled_queued_probe_can_run_again_in_the_same_window(self):
        from types import SimpleNamespace
        from ui.cloud_video import _CloudSettingsWindow
        from ui.desktop_async_tasks import AsyncTasksMixin
        from orchestrator.desktop_automation_service import BackgroundTaskQueue
        class Desk(AsyncTasksMixin):
            pass
        desk = Desk()
        desk.worker = True
        desk.task_queue = BackgroundTaskQueue()
        desk.status = mock.Mock()
        desk.win = mock.Mock()
        window = _CloudSettingsWindow(desk)
        window.entries = {'base': SimpleNamespace(get=lambda: 'https://api.invalid')}
        window.probe_status = mock.Mock()
        window.win = mock.Mock(winfo_exists=lambda: True)
        window.probe_endpoint_now()
        window.probe_endpoint_now()
        self.assertEqual(len(desk.task_queue.labels()), 1)
        first = desk.task_queue.pop()
        desk.task_queue.enqueue(first['fn'], first['done'])
        desk.task_queue.clear()
        desk.win.after.call_args.args[1]()
        self.assertIn('已取消', window.probe_status.set.call_args.args[0])
        window.probe_endpoint_now()
        self.assertEqual(len(desk.task_queue.labels()), 1)
        first['done']('旧探测')
        self.assertNotEqual(window.probe_status.set.call_args.args[0], '旧探测')
        second = desk.task_queue.pop()
        desk._active_async_fn = second['fn']
        desk._async_ticket = 7
        desk.background_tasks = SimpleNamespace(accepts=lambda ticket: ticket == 7)
        window.probe_endpoint_now()
        self.assertFalse(desk.task_queue.labels())
        window.win.winfo_exists = lambda: False
        second['done']('窗口已销毁')
        self.assertNotEqual(window.probe_status.set.call_args.args[0], '窗口已销毁')

    def test_other_answers_are_plainly_reachable(self):
        self.assertEqual(self.message({'reachable': True, 'code': 200}), '接口可达（HTTP 200）')

    def test_unreachable_carries_the_error_text(self):
        self.assertEqual(self.message({'reachable': False, 'error': '超时'}), '连接失败：超时')
        self.assertEqual(self.message({'reachable': False}), '连接失败：未知错误')

    def test_probe_failure_is_left_to_the_caller(self):
        with mock.patch.object(api_endpoints, 'probe_endpoint', side_effect=OSError('x')):
            with self.assertRaises(OSError):
                api_endpoints.probe_message('https://api.invalid')


class RunInBackgroundTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import tkinter
        cls.tk = tkinter

    def window(self):
        win = self.tk.Tk()
        win.withdraw()

        def quiet_destroy():
            try:
                win.destroy()
            except self.tk.TclError:
                pass                                       # 用例里已经销毁过了
        self.addCleanup(quiet_destroy)
        return win

    def pump(self, win, until, seconds=5):
        end = time.monotonic() + seconds
        while time.monotonic() < end and not until():
            win.update()
            time.sleep(0.01)

    def test_result_is_delivered_once_on_the_tk_thread(self):
        win = self.window()
        main = threading.get_ident()
        got = []
        worker = []
        tk_timers.run_in_background(
            win, lambda: worker.append(threading.get_ident()) or 'ok',
            lambda value: got.append((value, threading.get_ident())), lambda exc: got.append(exc), interval=10)
        self.pump(win, lambda: got)
        self.pump(win, lambda: False, 0.2)                 # 再等几轮，确认不重复回调
        self.assertEqual(got, [('ok', main)])
        self.assertNotEqual(worker[0], main)

    def test_failure_goes_to_on_error_instead_of_leaving_the_ui_waiting(self):
        win = self.window()
        got = []

        def boom():
            raise KeyError('x')
        tk_timers.run_in_background(win, boom, lambda value: got.append(('done', value)),
                                    lambda exc: got.append(('error', type(exc).__name__)), interval=10)
        self.pump(win, lambda: got)
        self.assertEqual(got, [('error', 'KeyError')])

    def test_destroyed_window_gets_no_callback(self):
        win = self.window()
        got = []
        gate = threading.Event()
        tk_timers.run_in_background(win, lambda: gate.wait(5) and 'late', got.append, got.append, interval=10)
        win.destroy()
        gate.set()
        time.sleep(0.2)
        self.assertEqual(got, [])


if __name__ == '__main__':
    unittest.main()
