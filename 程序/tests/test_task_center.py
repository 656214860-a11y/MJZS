"""运行状况汇总：只读已有来源、格式可读；弹窗能建出来且不可编辑；设置页有入口。"""
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
        tick = source.split('def _tick_async_result', 1)[1].split('def _project_result_data', 1)[0]
        self.assertIn('self._start_next_queued()', tick)


class TaskCenterUiTests(unittest.TestCase):
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
        source = (PROGRAM / 'desktop.py').read_text(encoding='utf-8')
        self.assertIn("'运行状况…'", source)
        self.assertIn("module('task_center_ui')", source)


if __name__ == '__main__':
    unittest.main()
