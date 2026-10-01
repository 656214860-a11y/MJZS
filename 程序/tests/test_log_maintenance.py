# -*- coding: utf-8 -*-
"""程序自有日志的保留、轮转与容量上限回归。"""
import os
import tempfile
import time
import unittest
from pathlib import Path

import log_maintenance as logs


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


if __name__ == '__main__':
    unittest.main(verbosity=2)
