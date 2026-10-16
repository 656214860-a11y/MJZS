"""运行状况汇总：只读已有来源、格式可读；弹窗能建出来且不可编辑；设置页有入口。"""
from tests.architecture._scan import desktop_text  # R1505：Desktop 方法分布在 desktop.py 与迁出的 Mixin 模块
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

import app_logging
import task_center_service
import task_center_ui

PROGRAM = Path(__file__).resolve().parents[1]


class FakeLifecycle:
    _last = {'ticket': 7, 'state': 'failed'}


class TaskCenterServiceTests(unittest.TestCase):
    def setUp(self):
        app_logging._metrics.clear()
        app_logging._counters.clear()
        app_logging._recent_swallowed.clear()

    def test_snapshot_collects_existing_sources(self):
        app_logging.count('model.http.ok', 3)
        app_logging.count('model.http.network')
        with app_logging.timed('page.show', 10000):
            pass
        try:
            raise KeyError('缺键 token=Q1')
        except KeyError:
            app_logging.swallowed()
        data = task_center_service.snapshot(FakeLifecycle(), [{'at': 't', 'page': 'p', 'exception': 'E', 'message': 'm'}])
        self.assertEqual(data['last_task']['state'], 'failed')
        self.assertEqual(data['counters']['model.http.ok'], 3)
        self.assertEqual(data['timings']['page.show']['count'], 1)
        self.assertEqual(len(data['swallowed']), 1)
        self.assertNotIn('Q1', data['swallowed'][0])
        text = '\n'.join(task_center_service.format_lines(data))
        for needle in ('失败', 'ok：3 次', 'network：1 次', 'page.show', 'KeyError', 'E：m'):
            self.assertIn(needle, text)

    def test_empty_snapshot_is_readable(self):
        text = '\n'.join(task_center_service.format_lines(task_center_service.snapshot()))
        for needle in ('暂无', '暂无调用', '暂无记录'):
            self.assertIn(needle, text)

    def test_swallowed_ring_buffer_is_bounded(self):
        for _ in range(30):
            try:
                raise ValueError('x')
            except ValueError:
                app_logging.swallowed()
        self.assertEqual(len(app_logging.recent_swallowed()), 20)


    def test_lifecycle_history_records_label_state_and_elapsed(self):
        from desktop_automation_service import BackgroundTaskLifecycle
        life = BackgroundTaskLifecycle()
        life.submit(1, label='生成分镜')
        self.assertTrue(life.finish(1, succeeded=True))
        life.submit(2, label='导出')
        life.submit(3)  # 覆盖提交：2 记为已取消
        life.finish(3, succeeded=False, error='连接超时 token=ZZ9')
        life.finish(2, succeeded=True)  # 迟到结果不进历史
        rows = life.history()
        self.assertEqual([(r['ticket'], r['state'], r['label']) for r in rows],
                         [(1, 'succeeded', '生成分镜'), (2, 'cancelled', '导出'), (3, 'failed', '')])
        self.assertTrue(all(r['elapsed_s'] is not None for r in rows))
        text = chr(10).join(task_center_service.format_lines(task_center_service.snapshot(life)))
        self.assertIn('生成分镜', text)
        self.assertIn('已取消', text)
        self.assertIn('原因：连接超时', text)
        self.assertNotIn('ZZ9', text)

    def test_history_is_bounded(self):
        from desktop_automation_service import BackgroundTaskLifecycle, HISTORY_LIMIT
        life = BackgroundTaskLifecycle()
        for n in range(HISTORY_LIMIT + 5):
            life.submit(n)
            life.finish(n, succeeded=True)
        self.assertEqual(len(life.history()), HISTORY_LIMIT)


    def test_queue_is_fifo_bounded_and_shown_in_panel(self):
        from desktop_automation_service import BackgroundTaskQueue, QUEUE_LIMIT
        queue = BackgroundTaskQueue()
        self.assertEqual(queue.enqueue(lambda: 1, label='甲'), 1)
        self.assertEqual(queue.enqueue(lambda: 2, label='乙'), 2)
        text = chr(10).join(task_center_service.format_lines(task_center_service.snapshot(queue=queue)))
        self.assertIn('1. 甲', text)
        self.assertIn('2. 乙', text)
        self.assertEqual(queue.pop()['label'], '甲')
        for n in range(QUEUE_LIMIT):
            if len(queue.labels()) < QUEUE_LIMIT:
                queue.enqueue(lambda: 0, label=str(n))
        with self.assertRaises(ValueError):
            queue.enqueue(lambda: 0)
        queue.clear()
        self.assertEqual(queue.labels(), [])
        self.assertIsNone(queue.pop())

    def test_desktop_queue_runs_next_after_current_finishes(self):
        import desktop
        ran = []
        class Fake:
            shutting_down = False
            worker = False
            def __init__(self):
                from desktop_automation_service import BackgroundTaskQueue
                self.task_queue = BackgroundTaskQueue()
                self.messages = []
                class S:
                    def set(inner, text):
                        self.messages.append(text)
                self.status = S()
            def async_(self, fn, done=None, show_progress=True, label=None):
                ran.append(label if show_progress else label + '(无进度条)')
                self.worker = True
                return 1
        fake = Fake()
        call = lambda name, *args, **kw: getattr(desktop.Desktop, name)(fake, *args, **kw)
        call('async_queued', lambda: 0, None, '第一个')   # 空闲：立即执行
        call('async_queued', lambda: 0, None, '第二个')   # 忙：排队
        self.assertEqual(ran, ['第一个'])
        self.assertEqual(fake.task_queue.labels(), ['第二个'])
        self.assertIn('已排队（第1个）', fake.messages[-1])
        call('_start_next_queued')                       # 仍忙：不启动
        self.assertEqual(ran, ['第一个'])
        fake.worker = False
        call('_start_next_queued')
        self.assertEqual(ran, ['第一个', '第二个'])
        fake.worker = False
        call('async_queued', lambda: 0, None, '探测', False)
        call('async_queued', lambda: 0, None, '探测2', False)
        fake.worker = False
        call('_start_next_queued')
        self.assertEqual(ran[-1], '探测2(无进度条)')
        self.assertEqual(ran[-2], '探测(无进度条)')
        fake.worker = False
        fake.shutting_down = True
        fake.task_queue.enqueue(lambda: 0, label='不该跑')
        call('_start_next_queued')
        self.assertEqual(ran[-1], '探测2(无进度条)')

    def test_result_tick_starts_next_queued(self):
        source = (PROGRAM / 'desktop.py').read_text(encoding='utf-8')
        tick = source.split('def _tick_async_result', 1)[1].split(chr(10) + '    def ', 1)[0]  # R1505：到下一个 def 为止
        self.assertIn('self._start_next_queued()', tick)


    def test_retry_registry_only_retries_declared_failed_tasks(self):
        from desktop_automation_service import BackgroundTaskLifecycle, RetryRegistry
        life = BackgroundTaskLifecycle()
        registry = RetryRegistry()
        life.submit(1, label='探测')
        life.finish(1, succeeded=False, error='断网')
        life.submit(2, label='写入')          # 未声明可重试
        life.finish(2, succeeded=False, error='x')
        registry.remember(1, ('fn', 'done', '探测', False))
        data = task_center_service.snapshot(life, None, None, registry)
        self.assertEqual(data['retry_ticket'], 1)       # 2 虽然更新，但没登记，不可重试
        text = chr(10).join(task_center_service.format_lines(data))
        self.assertIn('原因：断网（可重试）', text)
        self.assertNotIn('原因：x（可重试）', text)
        self.assertEqual(registry.take_latest_failed(life.history()), ('fn', 'done', '探测', False))
        self.assertIsNone(registry.take_latest_failed(life.history()))   # 取出即删除，不会重复重试

    def test_desktop_retry_replays_a_failed_idempotent_task(self):
        import desktop
        from desktop_automation_service import BackgroundTaskLifecycle, BackgroundTaskQueue, RetryRegistry
        calls = []
        class Fake:
            shutting_down = False
            worker = False
            def __init__(self):
                self.background_tasks = BackgroundTaskLifecycle()
                self.task_queue = BackgroundTaskQueue()
                self.retry_registry = RetryRegistry()
                self.n = 0
                class S:
                    def set(inner, text):
                        pass
                self.status = S()
            def async_(self, fn, done=None, show_progress=True, label=None):
                self.n += 1
                calls.append((self.n, label, show_progress))
                self.background_tasks.submit(self.n, label=label)
                return self.n
        fake = Fake()
        fake.async_queued = lambda *a, **k: desktop.Desktop.async_queued(fake, *a, **k)
        call = lambda name, *a, **k: getattr(desktop.Desktop, name)(fake, *a, **k)
        self.assertFalse(call('retry_failed_task'))                      # 没有失败任务
        call('async_queued', lambda: 0, None, '探测', False, True)
        fake.background_tasks.finish(1, succeeded=False, error='断网')
        self.assertTrue(call('retry_failed_task'))
        self.assertEqual(calls, [(1, '探测', False), (2, '探测', False)])
        self.assertFalse(call('retry_failed_task'))                      # 第 2 次还没失败，不重试
        call('async_queued', lambda: 0, None, '写入')                    # 未声明可重试
        fake.background_tasks.finish(3, succeeded=False, error='x')
        self.assertFalse(call('retry_failed_task'))

    def test_dialog_offers_retry_button_only_when_retryable(self):
        source = (PROGRAM / 'task_center_ui.py').read_text(encoding='utf-8')
        self.assertIn("data.get('retry_ticket') is not None", source)
        self.assertIn('retry_failed_task', source)
        self.assertIn('retryable=True', (PROGRAM / 'cloud_video.py').read_text(encoding='utf-8'))


class TaskCenterUiTests(unittest.TestCase):
    def test_project_recovery_is_shown_from_existing_authorities(self):
        import tempfile
        from types import SimpleNamespace
        from agent.core import save
        import stage_parallel
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            save(project/'config.json', {'project_id': 'project-test'})
            save(project/'data/state.json', {'shots': {'S001': [{'state': 'unknown', 'version': 1}]}})
            win = tk.Tk()
            win.withdraw()
            try:
                with mock.patch.object(stage_parallel, 'evaluate', return_value={'ok': False, 'detail': '等待首帧'}):
                    dialog = task_center_ui.show(SimpleNamespace(win=win, root=project))
                text = next(w for w in dialog._descendants(dialog.content) if isinstance(w, tk.Text)).get('1.0', 'end')
                for value in ('project-test', 'S001', '等待首帧', '未知状态不重提'):
                    self.assertIn(value, text)
                from ui_widgets import LineInput
                query = next(w for w in dialog._descendants(dialog.content) if isinstance(w, LineInput))
                query.insert(0, 'missing-shot')
                for widget in dialog._descendants(dialog):
                    try:
                        if widget.cget('text') == '查询尝试': widget.invoke(); break
                    except tk.TclError:
                        continue
                shown = next(w for w in dialog._descendants(dialog.content) if isinstance(w, tk.Text)).get('1.0', 'end')
                self.assertNotIn('S001', shown)
            finally:
                win.destroy()

    def test_cancel_pending_button_clears_queue(self):
        from desktop_automation_service import BackgroundTaskQueue
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        class Desk:
            win = root
            task_queue = BackgroundTaskQueue()
        desk = Desk()
        desk.task_queue.enqueue(lambda:None, label='pending')
        dialog = task_center_ui.show(desk)
        buttons = [w for w in dialog._descendants(dialog) if w.winfo_class() in ('Button', 'TButton')]
        button = next(w for w in buttons if w.cget('text') == '取消全部待执行任务')
        button.invoke()
        self.assertEqual(desk.task_queue.labels(), [])

    def test_dialog_is_read_only_and_shows_summary(self):
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        class Desk:
            win = root
            background_tasks = FakeLifecycle()
        with mock.patch.object(task_center_ui.diagnostic_capture, '_state', return_value={'degradations': []}):
            dialog = task_center_ui.show(Desk())
        self.addCleanup(dialog.close)
        text = [w for w in dialog._descendants(dialog.content) if isinstance(w, tk.Text)][0]
        self.assertEqual(str(text.cget('state')), 'disabled')
        self.assertIn('最近一次主动任务', text.get('1.0', 'end'))

    def test_cloud_connection_probe_uses_the_queue(self):
        source = (PROGRAM / 'cloud_video.py').read_text(encoding='utf-8')
        self.assertIn("desktop.async_queued(work,", source)
        self.assertNotIn("desktop.async_(work,lambda text:probe_status", source)

    def test_settings_page_has_entry(self):
        source = desktop_text()  # R1505：设置按钮在迁出的项目首页 Mixin 里
        self.assertIn("'运行状况…'", source)
        self.assertIn("module('task_center_ui')", source)


if __name__ == '__main__':
    unittest.main()
