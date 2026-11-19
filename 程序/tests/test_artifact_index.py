import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract.infra_errors import ConfigError, StorageError
from infra import artifact_index as ai


class _IndexCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name) / 'project'
        self.project.mkdir()
        self.index = ai.open_index(self.project)
        self.addCleanup(self.index.close)

    def _file(self, name, data=b'x'):
        path = self.project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path


class TestRegisterAndVersions(_IndexCase):
    def test_register_candidate_and_versions_lineage(self):
        first = self._file('a.png')
        second = self._file('b.png')
        i1 = self.index.register(first, stage='keyframe', kind='image')
        i2 = self.index.register(second, stage='keyframe', kind='image', parents=(i1,))
        versions = self.index.versions(i1)
        self.assertEqual([v['id'] for v in versions], [i1, i2])
        self.assertEqual(versions[0]['state'], ai.CANDIDATE)
        self.assertEqual(versions[1]['logical_id'], i1)

    def test_duplicates_by_digest(self):
        same_a = self._file('a.png', b'same')
        same_b = self._file('b.png', b'same')
        self._file('c.png', b'other')
        self.index.register(same_a, stage='s', kind='image')
        self.index.register(same_b, stage='s', kind='image')
        dups = self.index.duplicates()
        self.assertEqual(len(dups), 1)
        self.assertEqual(len(dups[0]), 2)


class TestStateMachine(_IndexCase):
    def test_legal_chain_and_restore(self):
        path = self._file('a.png')
        aid = self.index.register(path, stage='s', kind='image')
        self.index.set_state(aid, ai.ADOPTED)
        self.index.set_state(aid, ai.ARCHIVED)
        with mock.patch('infra.storage_maintenance.recycle_paths',
                        return_value=True) as recycle:
            self.index.set_state(aid, ai.RECYCLED)
        recycle.assert_called_once()
        self.index.set_state(aid, ai.CANDIDATE)
        self.assertEqual(self.index.get(aid)['state'], ai.CANDIDATE)

    def test_illegal_transitions_raise(self):
        path = self._file('a.png')
        aid = self.index.register(path, stage='s', kind='image')
        for bad in (ai.ARCHIVED, 'bogus'):
            with self.assertRaises(ConfigError):
                self.index.set_state(aid, bad)
        self.index.set_state(aid, ai.ADOPTED)
        with self.assertRaises(ConfigError):
            self.index.set_state(aid, ai.CANDIDATE)

    def test_recycle_failure_blocks_transition(self):
        path = self._file('a.png')
        aid = self.index.register(path, stage='s', kind='image')
        with mock.patch('infra.storage_maintenance.recycle_paths',
                        return_value=False):
            with self.assertRaises(StorageError):
                self.index.set_state(aid, ai.RECYCLED)
        self.assertEqual(self.index.get(aid)['state'], ai.CANDIDATE)

    def test_recycle_uses_storage_maintenance(self):
        path = self._file('a.png')
        aid = self.index.register(path, stage='s', kind='image')
        with mock.patch('infra.storage_maintenance.recycle_paths',
                        return_value=True) as recycle:
            self.index.set_state(aid, ai.RECYCLED)
        recycle.assert_called_once()
        args = recycle.call_args[0]
        self.assertEqual(Path(args[0]), self.project)
        self.assertIn(str(path), [str(p) for p in args[1]])


class TestRebuild(_IndexCase):
    def test_rebuild_after_index_loss_matches(self):
        self._file('frames/a.png', b'1')
        self._file('frames/b.png', b'2')
        self._file('v.mp4', b'3')
        first = self.index.rebuild()
        self.index.close()
        ai.index_path(self.project).unlink()
        self.index = ai.open_index(self.project)
        second = self.index.rebuild()
        keep = ('path', 'logical_id', 'stage', 'kind', 'digest', 'state')
        self.assertEqual(
            [[row[k] for k in keep] for row in first],
            [[row[k] for k in keep] for row in second])

    def test_rebuild_runs_on_executor(self):
        self._file('a.png')
        calls = []

        def spy_submit(pool, fn, **kw):
            calls.append(pool)
            class _F:
                def result(self):
                    return fn()
            return _F()

        self.index.rebuild(executor=spy_submit)
        self.assertEqual(calls, ['io'])


class TestPlacement(_IndexCase):
    def test_index_file_not_in_project_dir(self):
        path = ai.index_path(self.project)
        self.assertFalse(path.is_relative_to(self.project))
        self.assertTrue(path.is_relative_to(ai.PROGRAM / 'data' / 'artifact_index'))


if __name__ == '__main__':
    unittest.main()
