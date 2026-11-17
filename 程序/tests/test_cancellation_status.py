"""取消状态须同时解释本机与远端，迟到结果须隔离且不被静默丢弃。"""
import json
import queue
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import infra.model_pool as model_pool
import script_contract
import stage_config
import writing_api
from desktop_automation_service import BackgroundTaskLifecycle
from writing_api import WritingCancelledError
from stage_execution_service import publish_stage_text
from tests.test_workflow import make_project


class CancellationStatusTests(unittest.TestCase):
    def test_plain_cancel_keeps_legacy_snapshot_and_reports_nothing(self):
        lifecycle = BackgroundTaskLifecycle()
        lifecycle.submit(3)
        self.assertTrue(lifecycle.cancel())
        self.assertEqual(lifecycle.snapshot(), {'ticket': 3, 'state': 'cancelled'})
        self.assertIsNone(lifecycle.cancellation_status())

    def test_costly_cancel_explains_local_remote_and_queryable_ids(self):
        lifecycle = BackgroundTaskLifecycle()
        lifecycle.submit('job-9', remote_task_id='remote-42', costly=True)
        self.assertTrue(lifecycle.cancel())
        status = lifecycle.cancellation_status()
        self.assertEqual(status['local'], 'stopped')
        self.assertEqual(status['remote'], 'not-requested')
        self.assertEqual(status['remote_task_id'], 'remote-42')
        self.assertEqual(status['ticket'], 'job-9')
        self.assertIn('本机已停止等待', status['text'])
        self.assertIn('远端仍可能继续执行', status['text'])
        self.assertIn('不能当作未计费', status['text'])
        self.assertIn('本机批次 job-9', status['text'])
        self.assertIn('远端任务 remote-42', status['text'])

    def test_remote_pending_and_confirmed_are_distinguished(self):
        pending = BackgroundTaskLifecycle()
        pending.submit(1, remote_task_id='r1')
        pending.cancel(remote_cancel_requested=True)
        self.assertEqual(pending.cancellation_status()['remote'], 'pending')
        self.assertIn('尚未收到远端确认', pending.cancellation_status()['text'])

        confirmed = BackgroundTaskLifecycle()
        confirmed.submit(2, costly=True)
        confirmed.cancel(remote_cancel_requested=True, remote_cancel_confirmed=True)
        info = confirmed.cancellation_status()
        self.assertEqual(info['remote'], 'confirmed')
        self.assertIn('远端取消已确认', info['text'])
        self.assertNotIn('不能当作未计费', info['text'])

    def test_unknown_remote_is_never_reported_as_free(self):
        lifecycle = BackgroundTaskLifecycle()
        lifecycle.submit(4, costly=True)
        lifecycle.cancel()
        info = lifecycle.cancellation_status()
        self.assertEqual(info['remote'], 'unknown')
        self.assertIn('无法确认远端状态', info['text'])
        self.assertIn('不能当作未计费', info['text'])
        self.assertNotIn('没有产生费用', info['text'])

    def test_status_is_bound_to_its_own_ticket(self):
        lifecycle = BackgroundTaskLifecycle()
        lifecycle.submit(1, costly=True)
        lifecycle.cancel()
        self.assertIsNotNone(lifecycle.cancellation_status(1))
        self.assertIsNone(lifecycle.cancellation_status(2))


class LateResultIsolationTests(unittest.TestCase):
    def test_rejected_late_result_is_recorded_not_silently_lost(self):
        lifecycle = BackgroundTaskLifecycle()
        lifecycle.submit(5)
        lifecycle.cancel()
        self.assertEqual(lifecycle.snapshot(), {'ticket': 5, 'state': 'cancelled'})
        self.assertFalse(lifecycle.finish(5, succeeded=True))
        self.assertEqual(lifecycle.snapshot(), {'ticket': 5, 'state': 'cancelled'})
        self.assertEqual(lifecycle.late_results(), [{'ticket': 5, 'succeeded': True}])

    def test_late_records_are_bounded(self):
        lifecycle = BackgroundTaskLifecycle()
        for ticket in range(20):
            lifecycle.submit(ticket)
            lifecycle.cancel()
            lifecycle.finish(ticket, succeeded=False)
        records = lifecycle.late_results()
        self.assertEqual(len(records), 8)
        self.assertEqual(records[-1]['ticket'], 19)

    def test_unknown_ticket_is_not_recorded(self):
        lifecycle = BackgroundTaskLifecycle()
        self.assertFalse(lifecycle.finish(404, succeeded=True))
        self.assertEqual(lifecycle.late_results(), [])


class DesktopCancellationNoticeTests(unittest.TestCase):
    def make_desktop(self, values, lifecycle, *, api_active):
        return SimpleNamespace(
            _idea_semantic_pending=None, _idea_requesting=api_active,
            _script_agent_launching=not api_active,
            _async_ticket=7, background_tasks=lifecycle, worker=True,
            busy_state=SimpleNamespace(set_busy=lambda *a, **k: None),
            idea_chat_controller=SimpleNamespace(cancel_request=lambda: None),
            idea_send=None, clear_thinking=lambda: None,
            flow_processes={}, update_script_interrupt_button=lambda: None,
            script_agent_processes=lambda: [], status=SimpleNamespace(set=values.append),
            root=object(),
        )

    def test_api_interrupt_explains_local_remote_and_ids(self):
        from desktop import Desktop
        values = []
        lifecycle = BackgroundTaskLifecycle()
        lifecycle.submit(7)
        desktop = self.make_desktop(values, lifecycle, api_active=True)
        self.assertTrue(Desktop.interrupt_script_agent(desktop))
        message = values[-1]
        self.assertIn('本机已停止等待', message)
        self.assertIn('远端仍可能继续执行', message)
        self.assertIn('可查询编号：本机批次 7', message)
        self.assertIn('归档到 responses/', message)
        self.assertNotIn('没有产生费用', message)

    def test_non_api_interrupt_makes_no_cost_claim(self):
        from desktop import Desktop
        values = []
        lifecycle = BackgroundTaskLifecycle()
        desktop = self.make_desktop(values, lifecycle, api_active=False)
        self.assertTrue(Desktop.interrupt_script_agent(desktop))
        message = values[-1]
        self.assertNotIn('计费', message)
        self.assertNotIn('responses/', message)


class AsyncLateResultDeliveryTests(unittest.TestCase):
    def test_stale_async_result_is_recorded_and_not_delivered(self):
        from desktop import Desktop
        values = []
        lifecycle = BackgroundTaskLifecycle()
        lifecycle.submit(1)
        lifecycle.cancel()
        desktop = SimpleNamespace(
            _brief_load_results=queue.Queue(), q=queue.Queue(),
            _async_ticket=2, background_tasks=lifecycle, worker=True,
            busy_state=SimpleNamespace(set_busy=lambda *a, **k: None),
            status=SimpleNamespace(set=values.append), shutting_down=False,
            _idea_requesting=False, _script_agent_launching=False,
            update_script_interrupt_button=lambda: None, clear_thinking=lambda: None,
            notifier=SimpleNamespace(error=lambda *a, **k: None),
        )
        desktop.q.put((1, True, '旧结果', lambda value: values.append('done:' + str(value))))
        Desktop._tick_async_result(desktop)
        self.assertEqual(values, [])
        self.assertEqual(lifecycle.late_results(), [{'ticket': 1, 'succeeded': True}])
        self.assertTrue(desktop.worker)


class ReturnedResponseArchiveTests(unittest.TestCase):
    """有成本任务的已返回正文在取消后仍要留档，且不改变正式采用状态。"""

    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.project = make_project(temp.name)
        stage_config.put(self.project, 'script', model='gpt-4o',
                         skills=['pipeline-script-preparation'])
        writing = self.project / 'writing'; writing.mkdir(exist_ok=True)
        brief = script_contract.brief_document({
            'story_summary': '雨夜少年发现会说话的底片。', 'main_characters': '少年和老板',
            'genre': '奇幻', 'length': '单集 60 秒'})
        (writing / 'brief_complete.json').write_text(json.dumps(brief), encoding='utf-8')
        from tests.test_writing_api import WritingApiTests
        WritingApiTests.confirmed_preparation(self.project)
        self.text = ('雨夜照相馆，少年推开门。老板说：“底片会告诉你真相。”少年攥紧相机继续追查。\n') * 30
        self.cancelled = threading.Event()
        self.enterContext(patch('writing_api.model_pool.pool', return_value=model_pool.default_pool()))

    def test_cancelled_stage_reply_is_archived_and_reported(self):
        archived = []
        def archive(project, text):
            path = Path(project) / 'writing' / 'responses' / 'late.txt'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf-8')
            archived.append(text)
            return str(path)
        def chat(*args, **kwargs):
            self.cancelled.set()
            return {'ok': True, 'text': self.text}
        with patch('writing_api.PoolAdapter.chat', side_effect=chat):
            with self.assertRaises(WritingCancelledError) as caught:
                writing_api.reply(self.project, '创作', cancelled=self.cancelled.is_set,
                                  publish=publish_stage_text, archive=archive)
        self.assertEqual(archived, [self.text])
        message = str(caught.exception)
        self.assertIn('原始响应已保存', message)
        self.assertIn('不等于正式采用', message)
        self.assertIn('late.txt', message)

    def test_without_archive_channel_publish_stays_untouched(self):
        publish = Mock()
        def chat(*args, **kwargs):
            self.cancelled.set()
            return {'ok': True, 'text': self.text}
        with patch('writing_api.PoolAdapter.chat', side_effect=chat):
            with self.assertRaises(WritingCancelledError):
                writing_api.reply(self.project, '创作', cancelled=self.cancelled.is_set, publish=publish)
        publish.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
