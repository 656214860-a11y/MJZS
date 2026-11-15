"""Cancellation stops new work without pretending an in-flight worker stopped."""
import threading
import time
import unittest
import tempfile
from pathlib import Path
from unittest import mock

import contract.platform_tools as platform_tools
import stage_parallel


class ExecutionDeadlineTests(unittest.TestCase):
    def test_local_comfy_exits_before_network_and_expiry_callback_runs_once(self):
        from comfy_service import Comfy
        from local_video import LocalAPI
        from batch_frames_tool.batch_frames import Client
        from desktop_automation_service import BackgroundTaskLifecycle
        control = platform_tools.ExecutionControl()
        control.cancel()
        for client in (Comfy('http://localhost:8188'), LocalAPI('http://localhost:8188'), Client('http://localhost:8188')):
            with platform_tools.execution_scope(control), self.assertRaises(platform_tools.ExecutionStopped):
                method = getattr(client, 'request', None) or client.call
                method('/prompt', {})
        life = BackgroundTaskLifecycle()
        life.submit(1)
        life.execution_control(1).deadline = time.monotonic()-1
        stopped = mock.Mock()
        self.assertFalse(life.finish(1, succeeded=True, on_stopped=stopped))
        self.assertFalse(life.finish(1, succeeded=True, on_stopped=stopped))
        stopped.assert_called_once_with()

    def test_provider_adapters_reject_stopped_submits_but_allow_later_poll(self):
        from agent.volcengine import VolcengineAdapter
        from agent.wan import WanAdapter
        control = platform_tools.ExecutionControl()
        control.cancel()
        for adapter_type, receipt in ((VolcengineAdapter, {'status': 'running'}),
                                      (WanAdapter, {'output': {'task_status': 'RUNNING'}})):
            adapter = adapter_type.__new__(adapter_type)
            adapter.cfg = {}
            adapter.endpoint = adapter.base = 'https://example.invalid'
            with mock.patch('urllib.request.build_opener') as opener:
                with platform_tools.execution_scope(control), self.assertRaises(platform_tools.ExecutionStopped):
                    adapter.call(payload={})
                opener.assert_not_called()
                response = opener.return_value.open.return_value.__enter__.return_value
                import json
                body = json.dumps(receipt).encode()
                response.read.side_effect = [body, b'']
                with mock.patch('api_endpoints.configured_key', return_value='test'):
                    adapter.poll('saved-task')
                request = opener.return_value.open.call_args.args[0]
                self.assertEqual(request.get_method(), 'GET')
                self.assertIn('saved-task', request.full_url)

    def test_remote_receipts_survive_local_failure_and_cancellation(self):
        from desktop_automation_service import BackgroundTaskLifecycle
        from task_center_service import snapshot, format_lines
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'history.json'
            life = BackgroundTaskLifecycle(path)
            life.submit(1)
            control = life.execution_control(1)
            for remote in ('first', 'second'):
                control.report(event='remote', remote_task_id=remote, provider='fake', costly=True)
            life.cancel()
            row = BackgroundTaskLifecycle(path).unresolved_records()[0]
            self.assertEqual(row['remote_task_id'], 'second')
            self.assertTrue(row['costly'])
            self.assertEqual([r['id'] for r in row['remote_tasks']], ['first', 'second'])
            self.assertIn('fake:first, fake:second', '\n'.join(format_lines(snapshot(life))))
            life.submit(2)
            life.execution_control(2).report(event='remote', remote_task_id='unknown', provider='fake')
            life.finish(2, succeeded=False, error='lost response')
            self.assertEqual(life.unresolved_records()[-1]['state'], 'reconcile')

    def test_desktop_hung_callable_has_bounded_wait_and_durable_unknown_state(self):
        from desktop_automation_service import BackgroundTaskLifecycle
        release = threading.Event()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'history.json'
            life = BackgroundTaskLifecycle(path)
            life.submit(1, timeout=1)
            life.execution_control(1).deadline = time.monotonic()+.2
            try:
                with self.assertRaises(platform_tools.ExecutionStopped):
                    life.run(1, lambda:release.wait(2))
                self.assertFalse(life.finish(1, succeeded=False))
                self.assertEqual(life.snapshot()['state'], 'cancelled')
                self.assertEqual(BackgroundTaskLifecycle(path).unresolved_records()[0]['state'], 'stopped')
            finally:
                release.set()
            end = time.monotonic()+2
            while time.monotonic()<end:
                if life.unresolved_records()[0]['state'] == 'late':
                    break
                time.sleep(.01)
            self.assertEqual(life.unresolved_records()[0]['state'], 'late')

    def test_cancel_during_publication_rolls_back_outputs_and_index(self):
        from stage_execution_service import publish_stage_text
        from agent.core import save_text
        control = platform_tools.ExecutionControl()
        with tempfile.TemporaryDirectory() as directory:
            path, index = Path(directory)/'output.txt', Path(directory)/'index.txt'
            path.write_text('old', encoding='utf-8')
            index.write_text('old-index', encoding='utf-8')
            def update(_):
                save_text(index, 'new-index')
                control.cancel()
            with platform_tools.execution_scope(control), self.assertRaises(platform_tools.ExecutionStopped):
                publish_stage_text(path, 'new', lambda _:True, update)
            self.assertEqual(path.read_text(encoding='utf-8'), 'old')
            self.assertEqual(index.read_text(encoding='utf-8'), 'old-index')

    def test_cancel_and_late_result_survive_restart_with_remote_id(self):
        from desktop_automation_service import BackgroundTaskLifecycle
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'history.json'
            life = BackgroundTaskLifecycle(path)
            life.submit(1, remote_task_id='provider-1', costly=True, label='video')
            life.cancel()
            self.assertFalse(life.finish(1, succeeded=True))
            recovered = BackgroundTaskLifecycle(path)
            rows = recovered.unresolved_records()
            self.assertEqual(rows[0]['remote_task_id'], 'provider-1')
            self.assertEqual(rows[0]['state'], 'late')
            self.assertFalse(rows[0]['remote_cancel_confirmed'])
            recovered.submit(1, label='new session')
            self.assertEqual(len(recovered.unresolved_records()), 2)

    def test_cancelled_context_rejects_network_and_process_before_launch(self):
        control = platform_tools.ExecutionControl()
        control.cancel()
        with platform_tools.execution_scope(control), mock.patch('urllib.request.OpenerDirector.open') as send:
            with self.assertRaises(platform_tools.ExecutionStopped):
                platform_tools.open_https('https://example.invalid', data=b'{}')
            send.assert_not_called()
            runner = mock.Mock()
            with self.assertRaises(platform_tools.ExecutionStopped):
                platform_tools.run_process(['tool'], run=runner)
            runner.assert_not_called()

    def test_hung_worker_returns_unknown_and_holds_permit_until_actual_exit(self):
        release, started = threading.Event(), threading.Event()
        governor = stage_parallel.Governor(limit=1)
        late = []
        def worker(item):
            started.set()
            release.wait(3)
            return 'late'
        before = time.monotonic()
        try:
            result = stage_parallel.parallel_map('assets', ['one', 'two'], worker,
                governor=governor, timeout=.1, on_late=lambda *row:late.append(row))
            self.assertLess(time.monotonic()-before, 1)
            self.assertTrue(started.is_set())
            self.assertTrue(result[0][2].started)
            self.assertFalse(result[1][2].started)
            self.assertEqual(governor.running(), 1)
        finally:
            release.set()
        end = time.monotonic()+2
        while (governor.running() or not late) and time.monotonic()<end:
            time.sleep(.01)
        self.assertEqual(governor.running(), 0)
        self.assertEqual(late[0][:2], ('one', 'late'))
        self.assertIsNone(result[0][1])

    def test_cancel_between_units_prevents_later_submission(self):
        control = platform_tools.ExecutionControl()
        calls = []
        def worker(item):
            calls.append(item)
            self.assertIs(platform_tools.current_execution(), control)
            control.cancel()
            return item
        result = stage_parallel.parallel_map('assets', [1,2,3], worker,
            governor=stage_parallel.Governor(limit=1), control=control)
        self.assertEqual(calls, [1])
        self.assertTrue(all(isinstance(row[2], platform_tools.ExecutionStopped) for row in result[1:]))
