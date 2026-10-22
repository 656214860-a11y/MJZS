"""视频页真实 tick 边界的结果渲染故障、隐私及轮询恢复回归。"""
from __future__ import annotations

import json
import queue
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app import App


class ResultPollingTests(unittest.TestCase):
    def make_app(self):
        app = App.__new__(App)
        app.local_messages = queue.Queue()
        app.results = queue.Queue()
        app.busy = True
        app.submitting_sid = 'SH001'
        app.local_submit_sid = None
        app.on_success = None
        app.quiet_run = False
        app.next_ui_update = float('inf')
        app.auto_submit_due = float('inf')
        app.closed = False
        app.window = mock.Mock()
        app.window.winfo_ismapped.return_value = True
        app.window.winfo_exists.return_value = True
        app.scheduler = mock.Mock()
        app.write = mock.Mock()
        app.report_done = mock.Mock()
        app.refresh = mock.Mock()
        app.update_progress = mock.Mock()
        app.prompt_results = mock.Mock()
        app.auto_poll = mock.Mock()
        return app

    def test_render_failure_is_observable_and_next_result_recovers(self):
        app = self.make_app()
        app.refresh.side_effect = [RuntimeError('injected render failure'), None]
        app.results.put((True, 'first'))
        with mock.patch('diagnostic_capture.record_degradation') as record:
            app.tick()
            record.assert_called_once()
            self.assertFalse(app.busy)
            self.assertIsNone(app.submitting_sid)
            app.auto_poll.assert_called_once()
            app.scheduler.after.assert_called_once_with(150, app.tick)
            app.results.put((True, 'second'))
            app.tick()
        self.assertEqual(app.refresh.call_count, 2)
        app.update_progress.assert_called_once()
        self.assertEqual(app.auto_poll.call_count, 2)
        self.assertEqual(app.scheduler.after.call_count, 2)
        self.assertTrue(app.results.empty())

    def test_destroyed_interpreter_does_not_escape_or_reschedule(self):
        import tkinter as tk
        app = self.make_app()
        app.window.winfo_exists.side_effect = tk.TclError('application destroyed')
        app.tick()
        app.scheduler.after.assert_not_called()

    def test_diagnostic_contains_location_not_payload_or_exception_text(self):
        import diagnostic_capture
        app = self.make_app()
        app.refresh.side_effect = RuntimeError('token=synthetic-value private-shot-prompt')
        app.results.put((True, 'synthetic-result-material'))
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'diagnostic.json'
            with mock.patch.object(diagnostic_capture, 'STATE_FILE', target):
                app.tick()
            self.assertTrue(target.is_file(), '渲染失败必须留下可定位诊断')
            text = target.read_text(encoding='utf-8')
        row = json.loads(text)['degradations'][-1]
        self.assertEqual(row['page'], '视频生成')
        self.assertEqual(row['stage'], 'app.tick.refresh')
        self.assertIn('RuntimeError', row['message'])
        self.assertEqual(row['project'], '')
        for value in ('synthetic-value', 'private-shot-prompt', 'synthetic-result-material'):
            self.assertNotIn(value, text)

    def test_repeated_failure_is_rate_limited_but_can_report_later(self):
        app = self.make_app()
        app.refresh.side_effect = ValueError('synthetic')
        with mock.patch('diagnostic_capture.record_degradation') as record, \
                mock.patch('app.time.monotonic', return_value=100) as clock:
            for instant in (100, 101, 129, 130):
                clock.return_value = instant
                app.results.put((True, 'done'))
                app.tick()
        self.assertEqual(record.call_count, 2)
        self.assertEqual(app.auto_poll.call_count, 4)
        self.assertEqual(app.scheduler.after.call_count, 4)

    def test_diagnostic_sink_failure_does_not_break_polling(self):
        app = self.make_app()
        app.write.side_effect = RuntimeError('renderer failed')
        with mock.patch('diagnostic_capture.record_degradation', side_effect=OSError('disk unavailable')) as record:
            app.results.put((True, 'done'))
            app.tick()
            record.assert_called_once()
        app.auto_poll.assert_called_once()
        app.scheduler.after.assert_called_once_with(150, app.tick)

    def test_closed_entry_does_not_consume_results_or_touch_widgets(self):
        app = self.make_app()
        app.closed = True
        app.results.put((True, 'late'))
        app.tick()
        self.assertEqual(app.results.qsize(), 1)
        app.window.winfo_ismapped.assert_not_called()
        app.window.winfo_exists.assert_not_called()
        app.auto_poll.assert_not_called()
        app.scheduler.after.assert_not_called()

    def test_destroy_race_during_after_registration_is_safe(self):
        import tkinter as tk
        app = self.make_app()
        app.scheduler.after.side_effect = tk.TclError('destroyed during registration')
        app.tick()
        app.scheduler.after.assert_called_once_with(150, app.tick)

    def test_real_destroyed_tk_interpreter_does_not_rearm(self):
        import tkinter as tk
        app = self.make_app()
        window = tk.Tk()
        window.withdraw()
        window.destroy()
        app.window = window
        app.scheduler = window
        app.tick()
        self.assertNotIn('timer', vars(app))

    def test_successful_quiet_result_keeps_poll_timing_without_diagnostic(self):
        app = self.make_app()
        app.quiet_run = True
        app.polling_sid = 'SH001'
        app.poll_started = 90
        app.poll_wait = 30
        app.last_poll_messages = {}
        app.on_success = mock.Mock()
        callback = app.on_success
        app.results.put((True, 'query complete'))
        with mock.patch('app.time.monotonic', return_value=100), \
                mock.patch('diagnostic_capture.record_degradation') as record:
            app.tick()
        callback.assert_called_once_with('query complete')
        self.assertIsNone(app.on_success)
        self.assertEqual(app.next_poll, 120)
        self.assertEqual(app.last_poll_messages, {'SH001': 'query complete'})
        app.report_done.assert_not_called()
        record.assert_not_called()

    def test_real_widget_destroy_cancels_timer_and_late_tick_is_inert(self):
        import tkinter as tk
        app = self.make_app()
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        window = tk.Frame(root)
        app.window = window
        app.scheduler = root
        window.bind('<Destroy>', app.cancel_timers)
        app.tick()
        timer = app.timer
        self.assertIn(timer, root.tk.call('after', 'info'))
        window.destroy()
        self.assertTrue(app.closed)
        self.assertIsNone(app.timer)
        self.assertNotIn(timer, root.tk.call('after', 'info'))
        app.results.put((True, 'late'))
        app.tick()
        self.assertEqual(app.results.qsize(), 1)


class TickBranchTests(unittest.TestCase):
    make_app = ResultPollingTests.make_app

    def test_local_messages_go_to_progress_line_or_log(self):
        app = self.make_app()
        app.tree = mock.Mock()
        app.tree.selection.return_value = ('SH001',)
        app.progress_text = mock.Mock()
        app.local_messages.put(('SH001', '排队中'))
        app.local_messages.put(('SH002', '下载中'))
        app.tick()
        app.progress_text.set.assert_called_once_with('SH001 · 排队中')
        app.write.assert_called_once_with('后台任务 SH002 · 下载中')

    def test_every_periodic_step_survives_its_own_failure(self):
        import tkinter as tk
        app = self.make_app()
        app.next_ui_update = 0
        app.auto_submit_due = 0
        app.update_prompt_controls = mock.Mock(side_effect=tk.TclError('gone'))
        app.prompt_results.poll.side_effect = OSError('locked')
        app.auto_submit_scan = mock.Mock(side_effect=RuntimeError('扫描坏了'))
        app.auto_poll.side_effect = RuntimeError('查询坏了')
        with mock.patch('app.time.monotonic', return_value=100):
            app.tick()
        self.assertEqual(app.next_ui_update, 101)
        self.assertEqual(app.auto_submit_due, 105)
        self.assertEqual(app.next_poll, 130)
        self.assertEqual([c.args[0] for c in app.write.call_args_list],
                         ['无人值守自动提交检查失败：扫描坏了',
                          '后台跟踪暂时异常，30秒后重试查询，不会重新提交生成：查询坏了'])
        app.scheduler.after.assert_called_once_with(150, app.tick)
        app.write.side_effect = tk.TclError('log gone')
        app.auto_submit_due = 0
        app.tick()
        self.assertEqual(app.scheduler.after.call_count, 2)

    def test_failed_local_submit_is_remembered_and_shown(self):
        app = self.make_app()
        app.local_submit_sid = 'SH009'
        app.local_submit_error = {}
        app.notifier = mock.Mock()
        app.results.put((False, '额度不足'))
        app.tick()
        self.assertEqual(app.local_submit_error, {'SH009': '额度不足'})
        self.assertIsNone(app.local_submit_sid)
        app.notifier.error.assert_called_once_with('额度不足', title='操作未完成')
        app.quiet_run = True
        app.results.put((False, '断网'))
        app.tick()
        app.notifier.error.assert_called_once()
        app.write.assert_called_with('后台查询或下载暂时中断，30秒后自动重试；不会重新提交生成。')

    def test_success_callback_failure_is_logged(self):
        app = self.make_app()
        app.on_success = mock.Mock(side_effect=OSError('没有这个目录'))
        app.results.put((True, '完成'))
        app.tick()
        self.assertEqual(app.write.call_args_list[0].args[0], '成片目录打开失败：没有这个目录')
        app.report_done.assert_called_once_with('完成')


if __name__ == '__main__':
    unittest.main()
