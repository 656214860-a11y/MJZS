"""跨树 GUI 调度契约；只用临时目录，不启动 Tk。"""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import run_selftests as runner


class GuiTokenTests(unittest.TestCase):
    def test_full_lock_allows_same_process_reentry(self):
        with tempfile.TemporaryDirectory() as common:
            first = runner.acquire_full_safe_lock(common, 965)
            self.assertEqual(runner.acquire_full_safe_lock(common, 965), first)
            runner.release_full_safe_lock(first)
            self.assertTrue(Path(first).exists())
            runner.release_full_safe_lock(first)
            self.assertFalse(Path(first).exists())

    def test_active_holder_rejected_dead_holder_reclaimed_and_reentry(self):
        with tempfile.TemporaryDirectory() as common:
            path = Path(common) / runner.GUI_LOCK_NAME
            path.write_text(json.dumps({'pid': 123456}), encoding='utf-8')
            with mock.patch.object(runner, '_pid_is_alive', return_value=True):
                with self.assertRaisesRegex(RuntimeError, 'PID 123456'):
                    runner.acquire_pid_lock(runner.GUI_LOCK_NAME, common)
            with mock.patch.object(runner, '_pid_is_alive', return_value=False):
                token = runner.acquire_gui_lock(common, wait=0)
            self.assertEqual(runner.lock_holder(token)['pid'], os.getpid())
            self.assertEqual(runner.acquire_gui_lock(common, wait=0), token)
            runner.release_gui_lock(token)
            self.assertTrue(path.exists())
            runner.release_gui_lock(token)
            self.assertFalse(path.exists())

    def test_two_directories_share_live_token_wait_timeout_then_acquire(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            first, second, common = [root / part for part in ('A', 'B', 'common')]
            for path in (first, second, common):
                path.mkdir()
            script = """
import sys, time
sys.path.insert(0, sys.argv[1])
import run_selftests as r
p = r.acquire_gui_lock(sys.argv[2], wait=0)
print('READY', flush=True)
sys.stdin.readline()
r.release_gui_lock(p)
"""
            process = subprocess.Popen([sys.executable, '-u', '-c', script, runner.HERE, str(common)],
                                       cwd=first, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True)
            try:
                self.assertEqual(process.stdout.readline().strip(), 'READY')
                contender = "import sys; sys.path.insert(0, sys.argv[1]); import run_selftests as r; assert r.acquire_gui_lock(sys.argv[2], wait=0.15) is None"
                started = time.monotonic()
                result = subprocess.run([sys.executable, '-c', contender, runner.HERE, str(common)],
                                        cwd=second, capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertGreaterEqual(time.monotonic() - started, 0.14)
                self.assertIn('[GUI_DEFERRED]', result.stdout)
                process.communicate('\n', timeout=10)
                token = runner.acquire_gui_lock(str(common), wait=1)
                self.assertIsNotNone(token)
                runner.release_gui_lock(token)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate(timeout=10)

    def test_wait_succeeds_when_holder_exits(self):
        with tempfile.TemporaryDirectory() as common:
            with mock.patch.object(runner, 'acquire_pid_lock', side_effect=[RuntimeError('PID 7'), 'token']), \
                 mock.patch.object(runner.time, 'sleep') as sleep:
                self.assertEqual(runner.acquire_gui_lock(common, wait=1), 'token')
                self.assertEqual(sleep.call_count, 1)
            runner._GUI_LOCK_DEPTH.pop('token', None)

    def test_cli_gui_timeout_lists_names_no_pass_no_cache_for_default_and_k(self):
        for args in ([], ['-k', 'example'], ['--layer', 'gui-e2e']):
            with self.subTest(args=args), contextlib.ExitStack() as stack:
                patches = {
                    'test_modules': ['test_example'], 'modules_for_layer': ['test_example'],
                    'gui_test_module': True, 'acquire_gui_lock': None, 'protect_tk': None,
                    'import_all': [], 'load_cache': {},
                    'incremental': ([], [], {'tests': {}}), 'units': [],
                    'run_units': [], 'run_serial': [], 'content_tree': '', 'load_layer_document': {},
                    'save_cache': None, 'save_full_safe_verification': None,
                }
                mocks = {name: stack.enter_context(mock.patch.object(runner, name, return_value=value))
                         for name, value in patches.items()}
                output = stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                self.assertEqual(runner.main(args + ['--gui-wait', '0']), 2)
                self.assertIn('[GUI_DEFERRED] 未执行、不计通过：test_example', output.getvalue())
                self.assertNotIn('ALL TESTS PASSED', output.getvalue())
                mocks['save_cache'].assert_not_called()
                mocks['save_full_safe_verification'].assert_not_called()

    def test_failure_observes_other_holder_and_retains_red(self):
        class Failing(unittest.TestCase):
            def runTest(self):
                self.fail('real failure')
        output = io.StringIO()
        with mock.patch.object(runner, 'other_gui_holder', return_value=987):
            result = unittest.TextTestRunner(stream=output, resultclass=runner.ConcurrencyResult).run(Failing())
        self.assertEqual(len(result.failures), 1)
        self.assertIn('[SUSPECT_CONCURRENCY]', output.getvalue())
        self.assertIn('987', output.getvalue())

    def test_full_lock_then_gui_and_both_release_on_exception(self):
        with tempfile.TemporaryDirectory() as common, contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(runner, 'git_common_dir', return_value=common))
            for name, value in {'test_modules': ['test_demo'], 'gui_test_module': True,
                                'load_layer_document': {}, 'content_tree': 'tree',
                                '_git_text': 'head', 'latest_completed_round': 965}.items():
                stack.enter_context(mock.patch.object(runner, name, return_value=value))
            def check_order():
                self.assertTrue((Path(common) / runner.FULL_SAFE_LOCK_NAME).exists())
                self.assertTrue((Path(common) / runner.GUI_LOCK_NAME).exists())
                raise RuntimeError('after both locks')
            stack.enter_context(mock.patch.object(runner, 'protect_tk', side_effect=check_order))
            with self.assertRaisesRegex(RuntimeError, 'after both locks'):
                runner.main(['--all', '--safe', '--force', '--gui-wait', '0'])
            self.assertFalse((Path(common) / runner.FULL_SAFE_LOCK_NAME).exists())
            self.assertFalse((Path(common) / runner.GUI_LOCK_NAME).exists())
