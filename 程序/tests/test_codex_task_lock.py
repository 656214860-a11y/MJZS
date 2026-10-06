"""Codex task locks load only the active platform backend and always release."""
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, call, patch

import codex_tasks


class TaskLockTests(unittest.TestCase):
    def test_posix_backend_is_loaded_only_when_entering_and_unlocks(self):
        for fail_body in (False, True):
            with self.subTest(fail_body=fail_body), tempfile.TemporaryDirectory() as td:
                backend = SimpleNamespace(LOCK_EX=2, LOCK_NB=4, LOCK_UN=8, flock=Mock())
                with patch.object(codex_tasks, 'os', SimpleNamespace(name='posix')), \
                     patch.object(codex_tasks, 'import_module', return_value=backend, create=True) as load:
                    manager = codex_tasks.task_lock(Path(td))
                    load.assert_not_called()
                    try:
                        with manager:
                            load.assert_called_once_with('fcntl')
                            self.assertEqual(len(backend.flock.call_args_list), 1)
                            if fail_body:
                                raise RuntimeError('body failed')
                    except RuntimeError as exc:
                        self.assertTrue(fail_body)
                        self.assertEqual(str(exc), 'body failed')
                    descriptor = backend.flock.call_args_list[0].args[0]
                    self.assertEqual(backend.flock.call_args_list,
                                     [call(descriptor, 6), call(descriptor, 8)])

    def test_posix_busy_lock_rejects_without_yield_or_unlock(self):
        backend = SimpleNamespace(LOCK_EX=2, LOCK_NB=4, LOCK_UN=8,
                                  flock=Mock(side_effect=OSError('busy')))
        with tempfile.TemporaryDirectory() as td, \
             patch.object(codex_tasks, 'os', SimpleNamespace(name='posix')), \
             patch.object(codex_tasks, 'import_module', return_value=backend, create=True):
            with self.assertRaisesRegex(ValueError, '正在打开此项目的Codex任务'):
                with codex_tasks.task_lock(Path(td)):
                    self.fail('busy lock yielded')
            self.assertEqual(backend.flock.call_count, 1)

    def test_posix_missing_backend_is_not_silently_ignored(self):
        with tempfile.TemporaryDirectory() as td, \
             patch.object(codex_tasks, 'os', SimpleNamespace(name='posix')), \
             patch.object(codex_tasks, 'import_module', side_effect=ModuleNotFoundError('fcntl'),
                          create=True) as load:
            with self.assertRaises(ModuleNotFoundError):
                with codex_tasks.task_lock(Path(td)):
                    self.fail('missing lock backend yielded')
            load.assert_called_once_with('fcntl')

    def test_windows_never_loads_posix_backend(self):
        backend = SimpleNamespace(LK_NBLCK=1, LK_UNLCK=2, locking=Mock())
        with tempfile.TemporaryDirectory() as td, \
             patch.object(codex_tasks, 'os', SimpleNamespace(name='nt')), \
             patch.dict('sys.modules', {'msvcrt': backend}), \
             patch.object(codex_tasks, 'import_module', create=True) as load:
            with codex_tasks.task_lock(Path(td)):
                self.assertEqual(backend.locking.call_count, 1)
            load.assert_not_called()
            descriptor = backend.locking.call_args_list[0].args[0]
            self.assertEqual(backend.locking.call_args_list,
                             [call(descriptor, 1, 1), call(descriptor, 2, 1)])

    def test_native_lock_rejects_second_holder_and_releases_after_exception(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            with self.assertRaisesRegex(RuntimeError, 'body failed'):
                with codex_tasks.task_lock(project):
                    with self.assertRaisesRegex(ValueError, '正在打开此项目的Codex任务'):
                        with codex_tasks.task_lock(project):
                            self.fail('second holder acquired')
                    raise RuntimeError('body failed')
            with codex_tasks.task_lock(project):
                pass
            self.assertEqual((project / 'codex_tasks.lock').read_bytes(), b'0')
