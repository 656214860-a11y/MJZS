"""R3694 运行入口容量与重启保护。"""
import json
import logging
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

from agent import publication
from infra import app_logging, workflow_process_registry as registry
from orchestrator.desktop_automation_service import BackgroundTaskLifecycle


class HistoryOutputBoundsTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.enterContext(mock.patch.object(publication, 'ROOT', self.root / 'tx'))

    def test_event_with_multibyte_and_newlines(self):
        formatter = app_logging._EventFormatter(app_logging.FORMAT)
        record = logging.makeLogRecord({'msg': '诊断\n' * 100000, 'name': 'engine'})
        rendered = formatter.format(record)
        self.assertLessEqual(len((rendered + '\n').replace('\n', '\r\n').encode()), 65536)
        self.assertIn('截断', rendered)

    def test_concurrent_unicode_events_rotate_real_handler(self):
        script = """
import logging, sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from infra import app_logging as log
log.LOGS = Path(sys.argv[1])
log.APP_LOG = log.LOGS / 'app.log'
log.FAULT_LOG = log.LOGS / 'fault.log'
log.PERF_FILE = log.LOGS / 'perf.json'
assert log.install()
with ThreadPoolExecutor(12) as pool:
    list(pool.map(lambda n: logging.warning('编号%s %s', n, '界'*70000), range(400)))
"""
        subprocess.run([sys.executable, '-c', script, str(self.root)], check=True, timeout=30,
                       cwd=Path(__file__).resolve().parents[1])
        files = list(self.root.glob('app.log*'))
        self.assertEqual(len(files), 4)
        for path in files:
            self.assertLessEqual(path.stat().st_size, 5 * 1024 * 1024 + 65536)
            for line in path.read_bytes().splitlines(keepends=True):
                self.assertLessEqual(len(line), 65536)
            self.assertIn('截断', path.read_text(encoding='utf-8'))

    def test_subprocess_combined_streams_flood(self):
        path = self.root / 'run.log'
        script = "import sys;sys.stdout.write('x'*2000000+'\\n');sys.stdout.flush();sys.stderr.write('y\\n'*100000)"
        with mock.patch.object(registry, 'DIAGNOSTIC_BYTES', 100000, create=True):
            with path.open('w', encoding='utf-8') as log:
                code = registry.run_registered([sys.executable, '-c', script], self.root, '',
                                               (log, log), 30, timeout_label='timeout')
        self.assertEqual(code, 0)
        self.assertLessEqual(path.stat().st_size, 100000)
        self.assertIn('达到容量上限', path.read_text(encoding='utf-8'))

    def test_structured_stdout_survives_diagnostic_flood(self):
        out = self.root / 'response'
        err = self.root / 'diagnostic'
        script = "import sys;print('x'*200000);sys.stderr.write('z'*200000+'\\n')"
        with mock.patch.object(registry, 'DIAGNOSTIC_BYTES', 1024):
            with out.open('w', encoding='utf-8') as response, err.open('w', encoding='utf-8') as log:
                registry.run_registered([sys.executable, '-c', script], self.root, '',
                                        (response, log), 10, timeout_label='timeout')
        self.assertEqual(out.read_text().strip(), 'x' * 200000)
        self.assertIn('达到容量上限', err.read_text(encoding='utf-8'))

    def test_cancel_unknown_concurrent_late_units_and_reopen(self):
        path = self.root / 'history.json'
        unknowns = [dict(id=str(i), state='unknown', request_id=str(i), cost=i) for i in range(40)]
        path.write_text(json.dumps(dict(version=1, tasks=unknowns)))
        life = BackgroundTaskLifecycle(path)
        life.submit(1, costly=True, label='长' * 100000)
        control = life.execution_control(1)
        control.report(event='remote', remote_task_id='remote', operation_id='op', request_id='req',
                       provider='p', model='m', status='unknown', fee=1)
        life.cancel()
        with ThreadPoolExecutor(8) as pool:
            list(pool.map(lambda n: control.report(event='late', unit=str(n), stage='s', succeeded=False), range(48)))
        rows = BackgroundTaskLifecycle(path).unresolved_records()
        self.assertEqual(rows[:-1], unknowns)
        row = rows[-1]
        self.assertEqual(row['state'], 'late')
        self.assertEqual((row['operation_id'], row['request_id'], row['provider'], row['model'], row['status'],
                          row['fee'], row['remote_task_id']), ('op', 'req', 'p', 'm', 'unknown', 1, 'remote'))
        self.assertTrue('截断' in row['label'])
        self.assertLess(len(row['late_units']), 48)
        self.assertEqual(len(row['late_units']) + row['late_units_omitted'], 48)

    def test_old_receipts_survive_completed_history_pressure(self):
        path = self.root / 'history'
        receipt = {'stage': 's', 'unit': 'u', 'operation_id': 'op', 'request_id': 'req'}
        pending = {'id': 'legacy', 'state': 'failed', 'billing_status': 'unknown',
                   'late_units': [receipt] + [{'unit': str(i)} for i in range(40)]}
        rows = [pending] + [dict(id=str(i), state='succeeded') for i in range(40)]
        path.write_text(json.dumps(dict(version=1, tasks=rows)))
        BackgroundTaskLifecycle(path).submit(1)
        saved = json.loads(path.read_text(encoding='utf-8'))['tasks']
        self.assertEqual(sum(row['state'] == 'succeeded' for row in saved), 20)
        self.assertIn(receipt, saved[0]['late_units'])
        self.assertEqual(saved[0]['late_units_omitted'], 20)
        self.assertEqual(saved[0]['billing_status'], 'unknown')

    def test_failed_quarantine_preserves_original(self):
        path = self.root / 'history'
        path.write_bytes(b'{incomplete')
        with mock.patch('agent.core.replace', side_effect=PermissionError), self.assertRaises(PermissionError):
            BackgroundTaskLifecycle(path).submit(1)
        self.assertEqual(path.read_bytes(), b'{incomplete')

    def test_successive_corrupt_histories_survive(self):
        path = self.root / 'history'
        for data in (b'{first', b'{second'):
            path.write_bytes(data)
            BackgroundTaskLifecycle(path).submit(1)
        self.assertEqual({p.read_bytes() for p in self.root.glob('history.corrupt*')}, {b'{first', b'{second'})

