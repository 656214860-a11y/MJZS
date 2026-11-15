"""自检临时目录沙盒：本轮临时根、子进程 tempfile 重定向、超期残留回收。

用例锚定行为而不是实现：只有本模块前缀的目录会被回收，未超期与外来目录原样保留；
子进程里 `Tk`／业务模块照常用 `tempfile`，落点必须在本轮根里；收尾删不掉时要留到下一轮。
"""
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import selftest_env as env


class TempSandboxTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix='sandbox-base-'))
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)

    def make(self, name, *, age_seconds=0.0, files=()):
        folder = self.base / name
        folder.mkdir()
        for relative, text in files:
            target = folder / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding='utf-8')
        moment = time.time() - age_seconds
        os.utime(folder, (moment, moment))
        return folder

    def test_sweep_removes_only_expired_prefixed_dirs(self):
        old = self.make('drama-test-old', age_seconds=3 * 86400, files=(('a.txt', 'x' * 10),))
        fresh = self.make('drama-test-fresh', age_seconds=60)
        foreign = self.make('tmp-foreign-old', age_seconds=3 * 86400)
        near_miss = self.make('drama-test', age_seconds=3 * 86400)

        report = env.sweep_stale_temp(self.base)

        self.assertFalse(old.exists(), '超期的本轮前缀目录应该被回收')
        self.assertTrue(fresh.exists(), '未超期的目录不能动')
        self.assertTrue(foreign.exists(), '不是本模块前缀的目录一律不动')
        self.assertTrue(near_miss.exists(), '前缀必须整段匹配，drama-test 不算')
        self.assertEqual(report['removed'], 1)
        self.assertEqual(report['failed'], 0)
        self.assertGreaterEqual(report['bytes'], 10)

    def test_sweep_keeps_directory_whose_removal_fails(self):
        locked = self.make('drama-test-locked', age_seconds=3 * 86400)
        with mock.patch.object(env.shutil, 'rmtree', side_effect=PermissionError('locked')):
            report = env.sweep_stale_temp(self.base)
        self.assertTrue(locked.exists())
        self.assertEqual(report['removed'], 0)
        self.assertEqual(report['failed'], 1)

    def test_install_sandbox_redirects_tempfile_into_root(self):
        root = self.base / 'drama-test-worker'
        original = tempfile.tempdir
        self.addCleanup(setattr, tempfile, 'tempdir', original)
        installed = env.install_temp_sandbox(root)
        self.assertEqual(installed, root)
        self.assertTrue(root.is_dir())
        self.assertTrue(Path(tempfile.mkdtemp()).is_relative_to(root))
        with tempfile.TemporaryDirectory() as folder:
            self.assertTrue(Path(folder).is_relative_to(root))
        with tempfile.NamedTemporaryFile() as handle:
            self.assertTrue(Path(handle.name).is_relative_to(root))

    def test_install_sandbox_without_root_is_noop(self):
        original = tempfile.tempdir
        self.addCleanup(setattr, tempfile, 'tempdir', original)
        self.addCleanup(os.environ.pop, env.TEST_TEMP_ENV, None)
        os.environ.pop(env.TEST_TEMP_ENV, None)
        self.assertIsNone(env.install_temp_sandbox())
        self.assertEqual(tempfile.tempdir, original)

    def test_begin_run_creates_root_and_points_children_at_it(self):
        self.addCleanup(os.environ.pop, env.TEST_TEMP_ENV, None)
        original = tempfile.tempdir
        self.addCleanup(setattr, tempfile, 'tempdir', original)

        state = env.begin_temp_run(self.base)

        root = state['root']
        self.assertTrue(root.is_dir())
        self.assertTrue(root.name.startswith(env.TEST_TEMP_PREFIX))
        self.assertTrue(root.is_relative_to(self.base))
        self.assertEqual(os.environ.get(env.TEST_TEMP_ENV), str(root))
        self.assertEqual(Path(tempfile.gettempdir()), root)
        self.assertEqual(state['swept']['removed'], 0)

    def test_begin_run_sweeps_older_runs_first(self):
        stale = self.make('drama-test-20260101', age_seconds=5 * 86400)
        self.addCleanup(os.environ.pop, env.TEST_TEMP_ENV, None)
        original = tempfile.tempdir
        self.addCleanup(setattr, tempfile, 'tempdir', original)

        state = env.begin_temp_run(self.base)

        self.assertFalse(stale.exists(), '上一轮遗留的临时根应在开跑前回收')
        self.assertEqual(state['swept']['removed'], 1)

    def test_finish_retries_transient_failure(self):
        root = self.base / 'drama-test-run'
        root.mkdir()
        (root / 'x.txt').write_text('x', encoding='utf-8')
        real = shutil.rmtree
        attempts = []

        def flaky(path, *args, **kwargs):
            attempts.append(path)
            if len(attempts) == 1:
                raise PermissionError('短暂占用')
            return real(path, *args, **kwargs)

        with mock.patch.object(env.shutil, 'rmtree', side_effect=flaky), \
                mock.patch.object(env.time, 'sleep'):
            self.assertTrue(env.finish_temp_run(root, retries=3))

        self.assertEqual(len(attempts), 2, '第一次失败后应重试，而不是直接放弃')
        self.assertFalse(root.exists())

    def test_finish_leaves_tree_for_next_sweep_when_still_locked(self):
        root = self.base / 'drama-test-locked-run'
        root.mkdir()
        with mock.patch.object(env.shutil, 'rmtree', side_effect=PermissionError('仍被占用')), \
                mock.patch.object(env.time, 'sleep'):
            self.assertFalse(env.finish_temp_run(root, retries=2))
        self.assertTrue(root.exists(), '删不掉就要留着，下一轮 sweep 按超期回收')


if __name__ == '__main__':
    unittest.main()
