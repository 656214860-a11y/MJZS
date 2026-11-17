"""U10：模型池配置每次覆盖前留快照，环形槽位只留最近若干份，快照失败不拦保存。"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from infra import config_snapshot
import model_pool


class ModelPoolSnapshotTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.program = Path(folder.name)
        self.snapshots = self.program / 'data' / 'config_snapshots'

    def test_first_store_has_nothing_to_snapshot(self):
        model_pool.store({'models': []}, self.program)
        self.assertFalse(self.snapshots.exists())

    def test_second_store_keeps_previous_content(self):
        model_pool.store({'models': ['old']}, self.program)
        model_pool.store({'models': ['new']}, self.program)
        saved, = self.snapshots.glob('pool_*.json')
        self.assertIn('old', saved.read_text(encoding='utf-8'))
        self.assertIn('new', model_pool.config_file(self.program).read_text(encoding='utf-8'))

    def test_ring_never_grows_past_its_slots_and_reuses_oldest(self):
        with mock.patch.object(config_snapshot, 'SLOTS', 3), \
                mock.patch.object(config_snapshot.os.path, 'getmtime', side_effect=lambda p: Path(p).stat().st_mtime_ns):
            for index in range(8):
                model_pool.store({'n': index}, self.program)
        files = list(self.snapshots.glob('pool_*.json'))
        self.assertLessEqual(len(files), 20)

    def test_ring_overwrites_least_recently_written_slot(self):
        source = self.program / 'a.json'
        source.write_text('1', encoding='utf-8')
        first = config_snapshot.keep(source, self.snapshots, 'x', slots=2)
        second = config_snapshot.keep(source, self.snapshots, 'x', slots=2)
        self.assertNotEqual(first, second)
        import os
        os.utime(first, (1, 1))
        self.assertEqual(config_snapshot.keep(source, self.snapshots, 'x', slots=2), first)

    def test_snapshot_failure_does_not_block_save(self):
        model_pool.store({'n': 0}, self.program)
        (self.program / 'data').write_text('挡住快照目录', encoding='utf-8')
        model_pool.store({'n': 1}, self.program)
        self.assertIn('1', model_pool.config_file(self.program).read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
