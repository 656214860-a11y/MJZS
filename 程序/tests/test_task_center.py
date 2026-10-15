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
        life.finish(3, succeeded=False)
        life.finish(2, succeeded=True)  # 迟到结果不进历史
        rows = life.history()
        self.assertEqual([(r['ticket'], r['state'], r['label']) for r in rows],
                         [(1, 'succeeded', '生成分镜'), (2, 'cancelled', '导出'), (3, 'failed', '')])
        self.assertTrue(all(r['elapsed_s'] is not None for r in rows))
        text = chr(10).join(task_center_service.format_lines(task_center_service.snapshot(life)))
        self.assertIn('生成分镜', text)
        self.assertIn('已取消', text)

    def test_history_is_bounded(self):
        from desktop_automation_service import BackgroundTaskLifecycle, HISTORY_LIMIT
        life = BackgroundTaskLifecycle()
        for n in range(HISTORY_LIMIT + 5):
            life.submit(n)
            life.finish(n, succeeded=True)
        self.assertEqual(len(life.history()), HISTORY_LIMIT)


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

    def test_settings_page_has_entry(self):
        source = (PROGRAM / 'desktop.py').read_text(encoding='utf-8')
        self.assertIn("'运行状况…'", source)
        self.assertIn("module('task_center_ui')", source)


if __name__ == '__main__':
    unittest.main()
