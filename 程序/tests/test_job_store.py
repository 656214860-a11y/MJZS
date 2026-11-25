import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract.infra_errors import ConfigError
from infra import job_store as js
from domain import asset_resume


class _StoreCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name) / 'project'
        self.project.mkdir()
        self.store = js.open_store(self.project)
        self.addCleanup(self.store.close)


class TestJobStore(_StoreCase):
    def test_enqueue_idempotent_and_transition_chain(self):
        job = self.store.enqueue('a1', 'asset_resume', payload={'x': 1})
        again = self.store.enqueue('a1', 'asset_resume')
        self.assertEqual(job['id'], again['id'])
        self.assertEqual(job['state'], js.QUEUED)
        self.store.transition(job['id'], js.RUNNING)
        self.store.transition(job['id'], js.RETRYING)
        self.assertEqual(self.store.get(job['id'])['state'], js.RETRYING)

    def test_illegal_transition_raises(self):
        job = self.store.enqueue('a1', 'k')
        with self.assertRaises(ConfigError):
            self.store.transition(job['id'], js.SUCCEEDED)
        with self.assertRaises(ConfigError):
            self.store.transition(job['id'], 'bogus')

    def test_note_attempt_backoff_and_stop(self):
        job = self.store.enqueue('a1', 'k')
        self.store.transition(job['id'], js.RUNNING)
        first = self.store.note_attempt(job['id'], step=60, at=1000.0)
        self.assertEqual(first['attempts'], 1)
        self.assertEqual(first['next_try'], 1060.0)
        second = self.store.note_attempt(job['id'], step=60, limit=2, at=2000.0)
        self.assertEqual(second['state'], js.STOPPED)
        self.assertIsNone(second['next_try'])

    def test_checkpoint_roundtrip(self):
        job = self.store.enqueue('a1', 'k')
        self.store.checkpoint(job['id'], {'stage': 'x', 'step': 2}, digest='d1')
        row = self.store.get(job['id'])
        self.assertEqual(json.loads(row['checkpoint'])['step'], 2)
        self.assertEqual(row['digest'], 'd1')

    def test_crash_recovery_last_committed_state(self):
        # 新连接只观察；持有者租约到期后才允许显式恢复。
        job = self.store.enqueue('a1', 'k')
        self.store.transition(job['id'], js.RUNNING)
        self.store.checkpoint(job['id'], {'resume': 7})
        revived = js.open_store(self.project)
        self.addCleanup(revived.close)
        with mock.patch.object(js.time, 'time', return_value=1000.0):
            self.store.renew_lease(job['id'])
        with mock.patch.object(js.time, 'time', return_value=1001.0):
            self.assertEqual(revived.get(job['id'])['state'], js.RUNNING)
            self.assertEqual(revived.recover_expired(), 0)
        with mock.patch.object(js.time, 'time', return_value=1001.0 + js.LEASE_SECONDS):
            self.assertEqual(revived.recover_expired(), 1)
            with self.assertRaises(ConfigError):
                self.store.checkpoint(job['id'], {'stale': True})
            revived.transition(job['id'], js.RUNNING)
            with self.assertRaises(ConfigError):
                self.store.transition(job['id'], js.SUCCEEDED)
        row = revived.get(job['id'])
        self.assertEqual(row['state'], js.RUNNING)
        self.assertEqual(json.loads(row['checkpoint'])['resume'], 7)

    def test_legacy_ledger_migration_preserves_ids_and_only_recovers_confirmed_jobs(self):
        project = self.project / 'legacy'
        db = sqlite3.connect(js.store_path(project))
        with db:
            db.execute('CREATE TABLE jobs(id INTEGER PRIMARY KEY,key TEXT UNIQUE,kind TEXT,payload TEXT,'
                       'state TEXT,attempts INTEGER,last_try REAL,next_try REAL,checkpoint TEXT,digest TEXT,'
                       'created_at REAL,updated_at REAL)')
            db.execute("INSERT INTO jobs VALUES (9,'A1','video',NULL,'running',2,10,NULL,'{}','d',1,10)")
        db.close()
        with js.open_store(project) as store:
            self.assertEqual(store.recover_expired(), 0)
            other = store.enqueue('A1', 'asset_resume')
            self.assertNotEqual(other['id'], 9)
            self.assertEqual(store.recover_expired(confirmed_legacy_ids=[9]), 1)
            self.assertEqual((store.get(9)['digest'], store.get(9)['state']), ('d', js.RETRYING))
            self.assertEqual(store.get(other['id'])['state'], js.QUEUED)

    def test_mirror_upsert_and_list_and_by_key(self):
        first = self.store.mirror('a1', 'k', attempts=1, next_try=10.0, state='retrying')
        second = self.store.mirror('a1', 'k', attempts=3, next_try=None, state='stopped')
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(second['attempts'], 3)
        self.assertEqual(self.store.by_key('a1')['kind'], 'k')
        self.assertEqual([j['key'] for j in self.store.list(state='stopped')], ['a1'])
        self.assertEqual(len(self.store.list()), 1)
        with self.assertRaises(ConfigError):
            self.store.mirror('b1', 'k', attempts=0, next_try=None, state='bogus')

    def test_reconcile_field_diffs(self):
        self.store.mirror('a1', 'k', attempts=1, next_try=10.0, state='stopped')
        report = self.store.reconcile(
            {'a1': {'attempts': 2, 'next_try': 99.0, 'state': 'waiting'}},
            state_map={'waiting': 'retrying'})
        diff = report['field_diffs']['a1']
        self.assertEqual(diff['attempts']['ledger'], 2)
        self.assertEqual(diff['state']['store'], 'stopped')

    def test_get_missing_raises(self):
        with self.assertRaises(ConfigError):
            self.store.get(999)
        with self.assertRaises(ConfigError):
            self.store.transition(999, 'running')

    def test_reconcile_reports_diffs(self):
        self.store.mirror('a1', 'k', attempts=2, next_try=100.0, state='retrying')
        report = self.store.reconcile(
            {'a1': {'attempts': 2, 'next_try': 100.0, 'state': 'waiting'},
             'a2': {'attempts': 1, 'next_try': 50.0, 'state': 'waiting'}},
            state_map={'waiting': 'retrying'})
        self.assertEqual(report['missing_in_store'], ['a2'])
        self.assertEqual(report['missing_in_ledger'], [])
        self.assertEqual(report['field_diffs'], {})


class TestAssetResumeDualWrite(_StoreCase):
    def test_clear_and_reconcile_only_own_assets_even_at_same_key(self):
        other = self.store.enqueue('A1', 'video')
        asset_resume.note_round(self.project, ['A1', 'A2'], publish=self._publish())
        asset_resume.note_round(self.project, ['A1'], publish=self._publish())
        self.store.mirror('orphan', 'asset_resume', attempts=2, next_try=1, state=js.RETRYING)
        self.assertEqual(asset_resume.consistency_report(self.project)['missing_in_ledger'], ['orphan'])
        self.assertTrue(asset_resume.clear(self.project).ok)
        self.assertEqual(self.store.get(other['id'])['state'], js.QUEUED)
        self.assertEqual(self.store.by_key('A1', kind='asset_resume')['state'], js.SUCCEEDED)
        self.assertEqual(self.store.by_key('A2', kind='asset_resume')['state'], js.SUCCEEDED)
        self.assertFalse(any(asset_resume.consistency_report(self.project).values()))

    def _publish(self):
        writes = {}
        def publish(p, data):
            writes[str(p)] = json.loads(json.dumps(data, ensure_ascii=False))
            Path(p).parent.mkdir(parents=True, exist_ok=True)
            Path(p).write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        return publish

    def test_dual_write_keeps_ledger_reads_and_consistent_store(self):
        # I19-2：双写期间旧台账读取口径不变；作业库与台账一致性报告零差异。
        publish = self._publish()
        result = asset_resume.note_round(self.project, ['A1', 'A2'], limit=3,
                                         now=1000.0, publish=publish)
        self.assertTrue(result.ok)
        ledger = asset_resume.load(self.project)
        self.assertEqual(ledger['A1']['attempts'], 1)
        self.assertEqual(ledger['A1']['state'], 'waiting')
        self.assertEqual(asset_resume.delay(self.project, now=1000.0), 60.0)
        report = asset_resume.consistency_report(self.project)
        self.assertEqual(report['missing_in_store'], [])
        self.assertEqual(report['missing_in_ledger'], [])
        self.assertEqual(report['field_diffs'], {})

    def test_dual_write_survives_store_failure(self):
        publish = self._publish()
        with mock.patch('infra.job_store.open_store',
                        side_effect=OSError('no disk')):
            result = asset_resume.note_round(self.project, ['A1'], now=1000.0,
                                             publish=publish)
        self.assertTrue(result.ok)
        self.assertEqual(asset_resume.load(self.project)['A1']['attempts'], 1)


if __name__ == '__main__':
    unittest.main()
