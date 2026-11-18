# -*- coding: utf-8 -*-
"""R3269：L1 无界增长治理——file_cache/usage_snapshot/pet_llm.calls/request_ledger
索引与 .bak、model_diagnostics 保留期清理、model_router 单调时钟、
temporary_sweep 遗留临时文件清扫（后台线程，不在启动路径）。"""
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import infra.file_cache as file_cache
import infra.model_diagnostics as model_diagnostics
import infra.model_router as model_router
import infra.pet_llm as pet_llm
import infra.request_ledger as request_ledger_module
import infra.temporary_sweep as temporary_sweep
import infra.usage_snapshot as usage_snapshot
from infra.request_ledger import RequestLedger, request_ledger_path


class _Clock:
    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now


def _touch_old(path, seconds=25 * 3600):
    old = time.time() - seconds
    os.utime(path, (old, old))


class FileCacheBoundTests(unittest.TestCase):
    def tearDown(self):
        file_cache.clear()

    def test_text_cache_evicts_oldest_and_reread_stays_correct(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            paths = []
            for i in range(file_cache._CACHE_LIMIT + 8):
                p = root / ('f%02d.txt' % i)
                p.write_text('内容-%d' % i, encoding='utf-8')
                paths.append(p)
            for p in paths:
                file_cache.read_text(p)
            self.assertLessEqual(len(file_cache._TEXT_CACHE), file_cache._CACHE_LIMIT)
            text_key = lambda p: (file_cache._key(p), 'utf-8-sig', None)
            self.assertNotIn(text_key(paths[0]), file_cache._TEXT_CACHE)
            # 被淘汰的项再读仍拿到磁盘真值，并重新成为最近项。
            self.assertEqual(file_cache.read_text(paths[0]), '内容-0')
            self.assertIn(text_key(paths[0]), file_cache._TEXT_CACHE)

    def test_bytes_cache_bounded_and_json_cache_untouched_by_limit(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            paths = [root / ('b%02d.bin' % i) for i in range(file_cache._CACHE_LIMIT + 4)]
            for i, p in enumerate(paths):
                p.write_bytes(b'byte-%d' % i)
                file_cache.read_bytes(p)
            self.assertLessEqual(len(file_cache._BYTES_CACHE), file_cache._CACHE_LIMIT)
            self.assertEqual(file_cache.read_bytes(paths[0]), b'byte-0')
            # _CACHE（正式 JSON）不在本轮限容范围，行为不变。
            j = root / 'a.json'
            j.write_text('{"x": 1}', encoding='utf-8')
            self.assertEqual(file_cache.read_json(j), {'x': 1})


class UsageSnapshotBoundTests(unittest.TestCase):
    def tearDown(self):
        usage_snapshot._snapshots.clear()
        usage_snapshot._null_snapshot = None

    def test_snapshots_evict_oldest_beyond_limit(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            keys = []
            for i in range(usage_snapshot.SNAPSHOT_LIMIT + 4):
                proj = root / ('p%02d' % i)
                proj.mkdir()
                keys.append(proj)
            first = usage_snapshot.get_snapshot(keys[0])
            for proj in keys[1:]:
                usage_snapshot.get_snapshot(proj)
            self.assertLessEqual(len(usage_snapshot._snapshots), usage_snapshot.SNAPSHOT_LIMIT)
            self.assertIsNot(usage_snapshot.get_snapshot(keys[0]), first)
            snapshot = usage_snapshot.get_snapshot(keys[-1])
            self.assertTrue(snapshot.record_call('script', 'm', 10, '0.1', 'CNY', 'r1'))


class PetLlmCallsBoundTests(unittest.TestCase):
    def test_calls_is_bounded_deque(self):
        with tempfile.TemporaryDirectory() as td:
            client = pet_llm.Client(project=None, program=Path(td),
                                   transport=lambda *a, **k: {}, config={})
            self.assertEqual(client.calls.maxlen, pet_llm.CALLS_LIMIT)
            for i in range(pet_llm.CALLS_LIMIT + 20):
                client.calls.append({'i': i})
            self.assertEqual(len(client.calls), pet_llm.CALLS_LIMIT)
            self.assertEqual(client.calls[0]['i'], 20)
            self.assertEqual(client.calls[-1]['i'], pet_llm.CALLS_LIMIT + 19)


class RequestLedgerIndexTests(unittest.TestCase):
    def test_find_uses_index_and_preserves_first_match_order(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = RequestLedger(td, clock=_Clock(10000.0))
            for i in range(120):
                ledger.reserve('rid-%d' % i, 'tokens', 1, at=10000.0)
            ledger.reserve('dup', 'tokens', 1, at=10000.0)
            ledger.reserve('dup', 'images', 1, at=10000.0)
            for i in range(120):
                entry = ledger._find('rid-%d' % i)
                self.assertIsNotNone(entry)
                self.assertEqual(entry['id'], 'rid-%d' % i)
            self.assertEqual(ledger._find('dup')['kind'], 'tokens')
            self.assertEqual(ledger._find('dup', 'images')['kind'], 'images')
            self.assertIsNone(ledger._find('missing'))
            self.assertIsNone(ledger._find('dup', 'videos'))

    def test_index_tracks_direct_append_and_reassignment(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = RequestLedger(td, clock=_Clock(10000.0))
            ledger.reserve('a', 'tokens', 1, at=10000.0)
            ledger._find('a')
            ledger.entries.append({'id': 'manual', 'kind': 'tokens', 'state': 'reserved'})
            self.assertIsNotNone(ledger._find('manual'))
            ledger.entries = [{'id': 'fresh', 'kind': 'requests', 'state': 'settled'}]
            self.assertIsNotNone(ledger._find('fresh'))
            self.assertIsNone(ledger._find('manual'))
            self.assertIsNone(ledger._find('a'))


class RequestLedgerBackupTests(unittest.TestCase):
    def _write_ledger(self, td, clock):
        ledger = RequestLedger(td, clock=clock)
        ledger.reserve('r1', 'tokens', 3, at=clock())
        ledger.save()
        return ledger

    def test_first_successful_load_each_day_refreshes_bak(self):
        with tempfile.TemporaryDirectory() as td:
            day1, day2 = _Clock(1000.0), _Clock(1000.0 + 86400)
            self._write_ledger(td, day1)
            RequestLedger(td, clock=day1).load()
            bak = request_ledger_module.ledger_backup_path(request_ledger_path(td))
            self.assertTrue(bak.is_file())
            first = bak.read_bytes()
            # 同一天第二次加载不再刷新。
            self._write_ledger(td, _Clock(1000.0 + 60))
            RequestLedger(td, clock=_Clock(1000.0 + 120)).load()
            self.assertEqual(bak.read_bytes(), first)
            # 次日第一次成功加载刷新为最新内容。
            RequestLedger(td, clock=day2).load()
            self.assertNotEqual(bak.read_bytes(), first)

    def test_corruption_error_names_path_and_bak(self):
        with tempfile.TemporaryDirectory() as td:
            clock = _Clock(1000.0)
            self._write_ledger(td, clock)
            path = request_ledger_path(td)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('这不是 JSON', encoding='utf-8')
            with self.assertRaises(ValueError) as ctx:
                RequestLedger(td, clock=clock).load()
            message = str(ctx.exception)
            self.assertIn(str(path), message)
            self.assertIn('.bak', message)
            self.assertIn('请求台账', message)

    def test_shape_corruption_also_reports_bak(self):
        with tempfile.TemporaryDirectory() as td:
            clock = _Clock(1000.0)
            path = request_ledger_path(td)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('[1, 2, 3]', encoding='utf-8')
            with self.assertRaises(ValueError) as ctx:
                RequestLedger(td, clock=clock).load()
            self.assertIn('.bak', str(ctx.exception))


class ModelRouterClockTests(unittest.TestCase):
    def test_circuit_uses_monotonic_clock(self):
        model_router._CIRCUITS.clear()
        try:
            for _ in range(model_router.CIRCUIT_FAILURE_THRESHOLD):
                model_router.record_circuit_failure('monotonic-probe')
            state = model_router.circuit_state('monotonic-probe')
            self.assertEqual(state['state'], 'open')
            self.assertAlmostEqual(state['opened_at'], time.monotonic(), delta=30.0)
            self.assertLess(state['opened_at'], time.time() - 1000000)
        finally:
            model_router._CIRCUITS.clear()


class ModelDiagnosticsPruneTests(unittest.TestCase):
    def test_prune_events_removes_only_old_json(self):
        with tempfile.TemporaryDirectory() as td:
            directory = Path(td) / 'model_diagnostics'
            directory.mkdir()
            old = directory / 'old.json'
            fresh = directory / 'fresh.json'
            old.write_text('{}', encoding='utf-8')
            fresh.write_text('{}', encoding='utf-8')
            keep = directory / 'notes.txt'
            keep.write_text('x', encoding='utf-8')
            now = time.time()
            _touch_old(old, 40 * 86400)
            _touch_old(keep, 40 * 86400)
            removed = model_diagnostics.prune_events(directory, now=now, retention_days=30)
            self.assertEqual(removed, 1)
            self.assertFalse(old.exists())
            self.assertTrue(fresh.exists())
            self.assertTrue(keep.exists())

    def test_record_prunes_stale_events_once_per_day(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            directory = folder / 'model_diagnostics'
            directory.mkdir(parents=True)
            old = directory / 'stale.json'
            old.write_text('{}', encoding='utf-8')
            _touch_old(old, 40 * 86400)
            path = model_diagnostics.record(folder, {'ok': True, 'status': 200})
            self.assertTrue(path.is_file())
            self.assertFalse(old.exists())
            count = len(list(directory.glob('*.json')))
            self.assertEqual(count, 1)

    def test_prune_events_default_retention_uses_log_policy(self):
        with tempfile.TemporaryDirectory() as td:
            directory = Path(td)
            old = directory / 'a.json'
            old.write_text('{}', encoding='utf-8')
            _touch_old(old, 40 * 86400)
            removed = model_diagnostics.prune_events(directory, now=time.time())
            self.assertEqual(removed, 1)
            self.assertFalse(old.exists())

    def test_prune_events_glob_failure_returns_zero(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(Path, 'glob', side_effect=OSError('denied')):
                removed = model_diagnostics.prune_events(
                    Path(td), now=time.time(), retention_days=1)
            self.assertEqual(removed, 0)

    def test_prune_events_inner_failure_skips_entry(self):
        with tempfile.TemporaryDirectory() as td:
            directory = Path(td)
            target = directory / 'a.json'
            target.write_text('{}', encoding='utf-8')
            _touch_old(target, 40 * 86400)
            with mock.patch.object(model_diagnostics.file_cache, 'remove_temporary_file',
                                   side_effect=OSError('locked')):
                removed = model_diagnostics.prune_events(
                    directory, now=time.time(), retention_days=30)
            self.assertEqual(removed, 0)
            self.assertTrue(target.exists())

    def test_prune_events_removal_failure_not_counted(self):
        with tempfile.TemporaryDirectory() as td:
            directory = Path(td)
            target = directory / 'a.json'
            target.write_text('{}', encoding='utf-8')
            _touch_old(target, 40 * 86400)
            with mock.patch.object(model_diagnostics.file_cache, 'remove_temporary_file',
                                   return_value=False):
                removed = model_diagnostics.prune_events(
                    directory, now=time.time(), retention_days=30)
            self.assertEqual(removed, 0)
            self.assertTrue(target.exists())

    def test_record_prune_failure_is_swallowed(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            (folder / 'model_diagnostics').mkdir()
            with mock.patch.object(model_diagnostics, 'prune_events',
                                   side_effect=RuntimeError('boom')):
                path = model_diagnostics.record(folder, {'ok': True})
            self.assertTrue(path.is_file())

    def test_record_prunes_at_most_once_per_day(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            calls = []
            real = model_diagnostics.prune_events

            def spy(directory, **kwargs):
                calls.append(directory)
                return real(directory, **kwargs)

            with mock.patch.object(model_diagnostics, 'prune_events', spy):
                model_diagnostics.record(folder, {'ok': True})
                model_diagnostics.record(folder, {'ok': True})
            self.assertEqual(len(calls), 1)


class StorageSweepTests(unittest.TestCase):
    HEX = 'a' * 32

    def _make(self, root, name, age_seconds):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('x', encoding='utf-8')
        _touch_old(path, age_seconds)
        return path

    def test_sweep_deletes_only_matching_aged_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            hex_name = self.HEX
            doomed = [
                self._make(root, 'a.%s.tmp' % hex_name, 25 * 3600),
                self._make(root, 'b.%s.download' % hex_name, 25 * 3600),
                self._make(root, 'c.%s.recover' % hex_name, 25 * 3600),
                self._make(root, 'd.%s.partial.mp4' % hex_name, 25 * 3600),
                self._make(root, 'sub/e.%s.tmp' % hex_name, 25 * 3600),
            ]
            kept = [
                self._make(root, '剧本.tmp', 25 * 3600),
                self._make(root, 'f.%s.tmp' % hex_name, 3600),
                self._make(root, 'g.tmp', 25 * 3600),
                self._make(root, 'h.%s.tmp.bak' % hex_name, 25 * 3600),
                self._make(root, 'i.%s.TMP' % hex_name, 25 * 3600),
            ]
            removed = temporary_sweep.sweep_stale_temporary_files(root)
            self.assertEqual(removed, len(doomed))
            for path in doomed:
                self.assertFalse(path.exists(), path)
            for path in kept:
                self.assertTrue(path.exists(), path)

    def test_sweep_name_predicate(self):
        self.assertTrue(temporary_sweep.is_stale_temporary_name('x.' + self.HEX + '.tmp'))
        self.assertTrue(temporary_sweep.is_stale_temporary_name('x.' + self.HEX + '.partial.mp4'))
        self.assertFalse(temporary_sweep.is_stale_temporary_name('剧本.tmp'))
        self.assertFalse(temporary_sweep.is_stale_temporary_name('x.' + self.HEX[:31] + '.tmp'))
        self.assertFalse(temporary_sweep.is_stale_temporary_name('x.' + self.HEX + '.tmpx'))

    def test_schedule_runs_off_calling_thread(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            target = self._make(root, 'j.%s.tmp' % self.HEX, 25 * 3600)
            seen = {}
            original = temporary_sweep.sweep_stale_temporary_files

            def spy(path, **kwargs):
                seen['thread'] = threading.get_ident()
                return original(path, **kwargs)

            with mock.patch.object(temporary_sweep, 'sweep_stale_temporary_files', spy):
                temporary_sweep.schedule_stale_temporary_sweep(root)
                deadline = time.time() + 10
                while 'thread' not in seen and time.time() < deadline:
                    time.sleep(0.02)
            self.assertIn('thread', seen)
            self.assertNotEqual(seen['thread'], threading.get_ident())
            deadline = time.time() + 10
            while target.exists() and time.time() < deadline:
                time.sleep(0.02)
            self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()
