# -*- coding: utf-8 -*-
"""程序自有日志的保留、轮转与容量上限回归。"""
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from infra import log_maintenance as logs


class LogMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.log_dir = self.root / 'logs'
        self.log_dir.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def _file(self, name, size=1, age_days=0):
        path = self.log_dir / name
        path.write_bytes(b'x' * size)
        stamp = time.time() - age_days * 24 * 60 * 60
        os.utime(path, (stamp, stamp))
        return path

    def test_retention_only_scans_exact_log_directory(self):
        old = self._file('old.log', age_days=31)
        protected = self.root / 'project' / 'logs' / 'agent.jsonl'
        protected.parent.mkdir(parents=True); protected.write_text('keep', encoding='utf-8')
        logs.maintain_program_logs(self.root)
        self.assertFalse(old.exists())
        self.assertEqual(protected.read_text(encoding='utf-8'), 'keep')

    def test_oversize_log_rotates_to_three_copies(self):
        old_limit = logs.SINGLE_MAX_BYTES
        logs.SINGLE_MAX_BYTES = 4
        try:
            (self.log_dir / 'live.log').write_text('fresh', encoding='utf-8')
            (self.log_dir / 'live.log.1').write_text('one', encoding='utf-8')
            (self.log_dir / 'live.log.2').write_text('two', encoding='utf-8')
            (self.log_dir / 'live.log.3').write_text('discard', encoding='utf-8')
            logs.maintain_directory(self.log_dir)
        finally:
            logs.SINGLE_MAX_BYTES = old_limit
        self.assertEqual((self.log_dir / 'live.log').stat().st_size, 0)
        self.assertEqual((self.log_dir / 'live.log.1').read_text(encoding='utf-8'), 'fresh')
        self.assertEqual((self.log_dir / 'live.log.2').read_text(encoding='utf-8'), 'one')
        self.assertEqual((self.log_dir / 'live.log.3').read_text(encoding='utf-8'), 'two')
        self.assertTrue((self.log_dir / 'live.log.1').is_file())
        self.assertTrue((self.log_dir / 'live.log.2').is_file())
        self.assertTrue((self.log_dir / 'live.log.3').is_file())
        self.assertFalse((self.log_dir / 'live.log.4').exists())

    def test_directory_cap_removes_oldest_managed_logs_first(self):
        old_limit = logs.DIR_MAX_BYTES
        logs.DIR_MAX_BYTES = 6
        try:
            oldest = self._file('oldest.log', size=4, age_days=3)
            middle = self._file('middle.log', size=4, age_days=2)
            newest = self._file('newest.log', size=4, age_days=1)
            (self.log_dir / 'keep.txt').write_text('not a log', encoding='utf-8')
            logs.maintain_directory(self.log_dir)
        finally:
            logs.DIR_MAX_BYTES = old_limit
        self.assertFalse(oldest.exists())
        self.assertFalse(middle.exists())
        self.assertTrue(newest.exists())
        self.assertTrue((self.log_dir / 'keep.txt').is_file())

    def test_dry_run_does_not_change_files(self):
        old = self._file('old.log', age_days=31)
        result = logs.maintain_directory(self.log_dir, dry_run=True)
        self.assertTrue(old.exists())
        self.assertEqual(result['removed_files'], 1)

    def test_expired_oversize_preview_matches_execution(self):
        old = self._file('old.log', size=16, age_days=31)
        with mock.patch.object(logs, 'SINGLE_MAX_BYTES', 4), mock.patch.object(logs, 'DIR_MAX_BYTES', 6):
            preview = logs.maintain_directory(self.log_dir, dry_run=True)
            self.assertTrue(old.exists())
            actual = logs.maintain_directory(self.log_dir)
        self.assertEqual(preview, actual)
        self.assertEqual(preview['removed_files'], 1)
        self.assertEqual(preview['removed_bytes'], 16)
        self.assertEqual(preview['rotated_files'], 0)

    def test_rotation_capacity_preview_matches_execution(self):
        for name, size in [('live.log', 8), ('live.log.1', 3), ('live.log.2', 2), ('live.log.3', 20)]:
            self._file(name, size=size, age_days=1)
        before = {p.name: p.read_bytes() for p in self.log_dir.iterdir()}
        with mock.patch.object(logs, 'SINGLE_MAX_BYTES', 4), mock.patch.object(logs, 'DIR_MAX_BYTES', 10):
            preview = logs.maintain_directory(self.log_dir, dry_run=True)
            self.assertEqual(before, {p.name: p.read_bytes() for p in self.log_dir.iterdir()})
            actual = logs.maintain_directory(self.log_dir)
        self.assertEqual(preview, actual)

    def test_junction_is_rejected_before_directory_scan(self):
        with mock.patch.object(Path, 'is_junction', return_value=True), mock.patch.object(logs, 'log_files') as scan:
            result = logs.maintain_directory(self.log_dir)
        scan.assert_not_called()
        self.assertEqual(result['removed_files'], 0)

    def test_capacity_keeps_new_empty_live_log_after_rotation(self):
        now = time.time() - 10
        for name, size in [('a.log', 13), ('b.log', 17)]:
            path = self._file(name, size=size)
            os.utime(path, (now, now))
        with mock.patch.object(logs, 'SINGLE_MAX_BYTES', 8), mock.patch.object(logs, 'DIR_MAX_BYTES', 25):
            preview = logs.maintain_directory(self.log_dir, now=now, dry_run=True)
            actual = logs.maintain_directory(self.log_dir, now=now)
        self.assertTrue((self.log_dir / 'a.log').exists())
        self.assertEqual(actual['removed_files'], 1)
        self.assertEqual(preview, actual)

    def test_junction_ancestor_is_rejected_before_directory_scan(self):
        with mock.patch.object(Path, 'is_junction', autospec=True, side_effect=lambda p: p == self.root), mock.patch.object(logs, 'log_files') as scan:
            logs.maintain_directory(self.log_dir)
        scan.assert_not_called()

    def test_scan_permission_error_is_reported_without_mutation(self):
        old = self._file('old.log', age_days=31)
        with mock.patch.object(Path, 'iterdir', side_effect=PermissionError('denied')):
            result = logs.maintain_directory(self.log_dir)
        self.assertGreater(result['errors'], 0)
        self.assertTrue(old.exists())

    def test_cli_scan_failure_returns_nonzero(self):
        with mock.patch.object(logs, 'PROGRAM', self.root), mock.patch.object(Path, 'iterdir', side_effect=PermissionError('denied')):
            self.assertNotEqual(logs.main(['--dry-run']), 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
