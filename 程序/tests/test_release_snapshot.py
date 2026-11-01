"""U4／U8：升级前快照留最近几份，回滚演练能判出坏快照。"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM / 'scripts'))
import distribution_build  # noqa: E402
import release_snapshot  # noqa: E402


def fake_build(destination, root=None, manifest=None, allow_undecided=False):
    Path(destination, '程序').mkdir(parents=True)
    Path(destination, '程序', 'a.txt').write_text('x', encoding='utf-8')
    return {'files': 1, 'commit': 'abcdef0123456789', 'round': 7}


class ReleaseSnapshotTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.tmp = Path(folder.name)

    def test_snapshot_keeps_only_latest_and_names_commit(self):
        names = iter('t%d' % n for n in range(10))
        with mock.patch.object(distribution_build, 'build', fake_build), \
                mock.patch.object(distribution_build, 'verify', lambda *a, **k: {'ok': True}), \
                mock.patch.object(distribution_build, '_git_binding', lambda base: {'commit': 'abcdef0123', 'round': 1}), \
                mock.patch('time.strftime', lambda fmt: next(names)):
            for _ in range(5):
                result = release_snapshot.snapshot(self.tmp / 'src', self.tmp / 'snap', keep=3)
        kept = sorted(item.name for item in (self.tmp / 'snap').iterdir())
        self.assertEqual(len(kept), 3)
        self.assertTrue(all('abcdef01' in name for name in kept))
        self.assertEqual(Path(result['path']).name, kept[-1])

    def test_failed_verify_removes_half_built_snapshot(self):
        with mock.patch.object(distribution_build, 'build', fake_build), \
                mock.patch.object(distribution_build, 'verify', lambda *a, **k: {'ok': False}):
            with self.assertRaises(ValueError):
                release_snapshot.snapshot(self.tmp / 'src', self.tmp / 'snap')
        self.assertEqual(list((self.tmp / 'snap').iterdir()), [])

    def test_drill_reports_missing_and_incomplete_snapshots(self):
        self.assertTrue(release_snapshot.drill(self.tmp / '无'))
        bad = self.tmp / 'bad'
        bad.mkdir()
        with mock.patch.object(distribution_build, 'verify', lambda *a, **k: {'ok': True}):
            self.assertEqual(release_snapshot.drill(bad), ['快照缺少随附解释器'])


if __name__ == '__main__':
    unittest.main()
