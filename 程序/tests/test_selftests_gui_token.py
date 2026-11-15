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
import selftest_discovery
import selftest_env
import selftest_receipts
import selftest_scheduling

_FACADE_OWNERS = {
    'test_modules': selftest_discovery, 'modules_for_layer': selftest_discovery,
    'gui_test_module': selftest_discovery, 'units': selftest_discovery,
    'import_all': selftest_discovery, 'split_safe_units': selftest_discovery,
    'split_performance_units': selftest_discovery,
    'load_cache': selftest_receipts, 'save_cache': selftest_receipts,
    'incremental': selftest_receipts, 'content_tree': selftest_receipts,
    'load_layer_document': selftest_receipts, 'save_full_safe_verification': selftest_receipts,
    'save_layer_baseline': selftest_receipts, 'verified_tree_record': selftest_receipts,
    'invalidate_verified_tree': selftest_receipts, 'measurement_unchanged': selftest_receipts,
    'receipt_checkout_allowed': selftest_receipts, 'full_safe_preflight': selftest_receipts,
    'latest_completed_round': selftest_receipts, 'record_elapsed': selftest_receipts,
    'auto_full_running': selftest_receipts, 'is_master_checkout': selftest_receipts,
    'run_units': selftest_scheduling, 'run_serial': selftest_scheduling,
    'run_safe_serial': selftest_scheduling, 'acquire_gui_lock': selftest_scheduling,
    'release_gui_lock': selftest_scheduling, 'protect_tk': selftest_scheduling,
    'acquire_full_safe_lock': selftest_scheduling, 'release_full_safe_lock': selftest_scheduling,
    'prioritize_gui_units': selftest_scheduling,
    '_git_text': selftest_env, 'git_common_dir': selftest_env,
}


def _patch(stack, name, **kwargs):
    """同一 mock 同时盖住 re-export 面与定义模块：main 的裸名调用与模块内部调用都命中。"""
    target = mock.MagicMock(**kwargs)
    stack.enter_context(mock.patch.object(runner, name, new=target))
    owner = _FACADE_OWNERS.get(name)
    if owner is not None:
        stack.enter_context(mock.patch.object(owner, name, new=target))
    return target



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
            with mock.patch.object(selftest_env, '_pid_is_alive', return_value=True):
                with self.assertRaisesRegex(RuntimeError, 'PID 123456'):
                    runner.acquire_pid_lock(runner.GUI_LOCK_NAME, common)
            with mock.patch.object(selftest_env, '_pid_is_alive', return_value=False):
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
            with mock.patch.object(selftest_scheduling, 'acquire_pid_lock',
                                   side_effect=[RuntimeError('PID 7'), 'token']) as acquire:
                self.assertEqual(runner.acquire_gui_lock(common, wait=1), 'token')
                self.assertEqual(acquire.call_count, 2)
            runner._GUI_LOCK_DEPTH.pop('token', None)

    def test_wait_succeeds_with_forward_slash_common_dir(self):
        # git rev-parse 给的是 D:/… 正斜杠；mkstemp 返回规范化路径，两者不一致时队首永远认不出自己（R1861）。
        with tempfile.TemporaryDirectory() as common:
            with mock.patch.object(selftest_scheduling, 'acquire_pid_lock',
                                   side_effect=[RuntimeError('PID 7'), 'token']) as acquire:
                self.assertEqual(runner.acquire_gui_lock(common.replace('\\', '/'), wait=1), 'token')
                self.assertEqual(acquire.call_count, 2)
            runner._GUI_LOCK_DEPTH.pop('token', None)

    def test_cli_gui_timeout_lists_names_no_pass_no_cache_for_default_and_k(self):
        for args in ([], ['-k', 'example'], ['--layer', 'gui-e2e']):
            with self.subTest(args=args), contextlib.ExitStack() as stack:
                patches = {
                    'test_modules': ['test_example'], 'modules_for_layer': ['test_example'],
                    'gui_test_module': True, 'acquire_gui_lock': None, 'protect_tk': None,
                    'import_all': [], 'load_cache': {},
                    'incremental': (['test_example'], [], {'tests': {}}),
                    'units': [('test_example', 'test_example', None)],
                    'run_units': [], 'run_serial': [], 'content_tree': '', 'load_layer_document': {},
                    'save_cache': None, 'save_full_safe_verification': None,
                }
                mocks = {name: _patch(stack, name, return_value=value)
                         for name, value in patches.items()}
                output = stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                self.assertEqual(runner.main(args + ['--gui-wait', '0']), 2)
                self.assertIn('[GUI_DEFERRED] 未执行、不计通过：test_example', output.getvalue())
                self.assertIn('GUI 测试 1 个未运行', output.getvalue())
                self.assertNotIn('ALL TESTS PASSED', output.getvalue())
                mocks['save_cache'].assert_not_called()
                mocks['save_full_safe_verification'].assert_not_called()

    def test_gui_module_skipped_by_incremental_never_takes_the_token(self):
        """令牌只在真正跑 GUI 用例时申请；选中的文件被增量跳过不等于要排队。"""
        with contextlib.ExitStack() as stack:
            patches = {
                'test_modules': ['test_gui', 'test_plain'], 'modules_for_layer': ['test_gui', 'test_plain'],
                'gui_test_module': True, 'protect_tk': None, 'import_all': [], 'load_cache': {},
                'incremental': (['test_plain'], ['test_gui'], {'tests': {}}),
                'units': [('plain', 'test_plain', None), ('gui', 'test_gui', None)],
                'run_units': [], 'run_serial': [], 'content_tree': '', 'load_layer_document': {},
                'save_cache': '', 'save_full_safe_verification': None,
            }
            for name, value in patches.items():
                _patch(stack, name, return_value=value)
            stack.enter_context(mock.patch.object(selftest_discovery, 'gui_test_module',
                                                  side_effect=lambda name: name == 'test_gui'))
            acquire = stack.enter_context(mock.patch.object(runner, 'acquire_gui_lock'))
            release = stack.enter_context(mock.patch.object(runner, 'release_gui_lock'))
            output = stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            self.assertEqual(runner.main([]), 0, output.getvalue())
        acquire.assert_not_called()
        release.assert_not_called()
        self.assertNotIn('GUI_DEFERRED', output.getvalue())
        self.assertEqual(runner._GUI_LOCK_DEPTH, {})

    def test_non_gui_units_finish_before_token_and_release_follows_gui(self):
        events = []
        fresh_flags = []

        def run_units(todo, jobs, **kwargs):
            events.append(('run', tuple(unit[1] for unit in todo)))
            fresh_flags.append(kwargs.get('fresh_children'))
            return [(unit[0], unit[1], 1, [], '', 0.1, '', []) for unit in todo]

        def acquire(wait=None):
            events.append('acquire')
            return 'gui-token'

        def release(path):
            events.append('release')

        with contextlib.ExitStack() as stack:
            patches = {
                'test_modules': ['test_gui', 'test_plain'], 'modules_for_layer': ['test_gui', 'test_plain'],
                'protect_tk': None, 'import_all': [],
                'incremental': (['test_gui', 'test_plain'], [], {'tests': {}}),
                'units': [('plain', 'test_plain', None), ('gui', 'test_gui', None)],
                'run_serial': [], 'content_tree': '', 'load_layer_document': {},
                'save_cache': '', 'save_full_safe_verification': None,
            }
            stack.enter_context(mock.patch.object(selftest_discovery, 'gui_test_module',
                                                  side_effect=lambda name: name == 'test_gui'))
            for name, value in patches.items():
                _patch(stack, name, return_value=value)
            stack.enter_context(mock.patch.object(runner, 'run_units', side_effect=run_units))
            stack.enter_context(mock.patch.object(runner, 'acquire_gui_lock', side_effect=acquire))
            stack.enter_context(mock.patch.object(runner, 'release_gui_lock', side_effect=release))
            output = stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            self.assertEqual(runner.main(['--all']), 0, output.getvalue())
        self.assertEqual(events.count('acquire'), 1)
        self.assertEqual(events.count('release'), 1)
        self.assertLess(events.index(('run', ('test_plain',))), events.index('acquire'))
        self.assertLess(events.index('acquire'), events.index(('run', ('test_gui',))))
        self.assertLess(events.index(('run', ('test_gui',))), events.index('release'))
        # GUI 单元必须逐单元新进程：隐藏桌面里同进程第二个起 tk.Tk() 不投递合成按键。
        self.assertEqual(fresh_flags, [None, True])

    def test_serial_mode_keeps_both_pools_on_the_serial_runner(self):
        calls = []

        def serial(units, timeout=None):
            calls.append(tuple(unit[1] for unit in units))
            return [(unit[0], unit[1], 1, [], '', 0.1, '', []) for unit in units]

        with contextlib.ExitStack() as stack:
            patches = {
                'test_modules': ['test_gui', 'test_plain'], 'modules_for_layer': ['test_gui', 'test_plain'],
                'protect_tk': None, 'import_all': [], 'load_cache': {},
                'incremental': (['test_gui', 'test_plain'], [], {'tests': {}}),
                'units': [('plain', 'test_plain', None), ('gui', 'test_gui', None)],
                'acquire_gui_lock': 'gui-token', 'release_gui_lock': None,
                'content_tree': '', 'load_layer_document': {},
                'save_cache': '', 'save_full_safe_verification': None,
            }
            for name, value in patches.items():
                _patch(stack, name, return_value=value)
            stack.enter_context(mock.patch.object(selftest_discovery, 'gui_test_module',
                                                  side_effect=lambda name: name == 'test_gui'))
            par = stack.enter_context(mock.patch.object(runner, 'run_units'))
            stack.enter_context(mock.patch.object(runner, 'run_serial', side_effect=serial))
            output = stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            self.assertEqual(runner.main(['--serial']), 0, output.getvalue())
        par.assert_not_called()
        self.assertEqual(calls, [('test_plain',), ('test_gui',)])

    def test_gui_performance_unit_stays_under_token_before_the_rest(self):
        events = []

        def run_units(todo, jobs, **kwargs):
            events.append(('units', tuple(unit[1] for unit in todo)))
            return [(unit[0], unit[1], 1, [], '', 0.1, '', []) for unit in todo]

        def run_serial(todo, timeout=None):
            events.append(('serial', tuple(unit[1] for unit in todo)))
            return [(unit[0], unit[1], 1, [], '', 0.1, '', []) for unit in todo]

        def acquire(wait=None):
            events.append('acquire')
            return 'gui-token'

        def release(path):
            events.append('release')

        with contextlib.ExitStack() as stack:
            patches = {
                'test_modules': ['test_plain', 'test_gui', 'test_desktop_startup_perf', 'test_perf_baseline'],
                'modules_for_layer': ['test_plain', 'test_gui', 'test_desktop_startup_perf',
                                      'test_perf_baseline'],
                'protect_tk': None, 'import_all': [],
                'incremental': (['test_plain', 'test_gui', 'test_desktop_startup_perf', 'test_perf_baseline'],
                                [], {'tests': {}}),
                'units': [('plain', 'test_plain', None), ('gui', 'test_gui', None),
                          ('perf-gui', 'test_desktop_startup_perf', None),
                          ('perf-plain', 'test_perf_baseline', None)],
                'content_tree': '', 'load_layer_document': {},
                'save_cache': '', 'save_full_safe_verification': None,
            }
            for name, value in patches.items():
                _patch(stack, name, return_value=value)
            stack.enter_context(mock.patch.object(
                selftest_discovery, 'gui_test_module',
                side_effect=lambda name: name in ('test_gui', 'test_desktop_startup_perf')))
            stack.enter_context(mock.patch.object(runner, 'run_units', side_effect=run_units))
            stack.enter_context(mock.patch.object(runner, 'run_serial', side_effect=run_serial))
            stack.enter_context(mock.patch.object(runner, 'acquire_gui_lock', side_effect=acquire))
            stack.enter_context(mock.patch.object(runner, 'release_gui_lock', side_effect=release))
            output = stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            self.assertEqual(runner.main(['--all']), 0, output.getvalue())
        self.assertEqual(events, [
            ('units', ('test_plain',)),
            'acquire',
            ('units', ('test_gui',)),
            ('serial', ('test_desktop_startup_perf',)),
            'release',
            ('serial', ('test_perf_baseline',)),
        ])

    def test_waiting_reports_holder_pid_start_and_elapsed(self):
        with tempfile.TemporaryDirectory() as common:
            path = Path(common) / runner.GUI_LOCK_NAME
            path.write_text(json.dumps({'pid': 123456, 'started_at': time.time() - 45}),
                            encoding='utf-8')
            output = io.StringIO()
            with mock.patch.object(selftest_env, 'GUI_WAIT_NOTICE_SECONDS', 0.05), \
                 mock.patch.object(selftest_env, '_pid_is_alive', return_value=True), \
                 contextlib.redirect_stdout(output):
                self.assertIsNone(runner.acquire_gui_lock(common, wait=0.2))
            text = output.getvalue()
            self.assertIn('[GUI_WAIT]', text)
            self.assertIn('PID 123456', text)
            self.assertIn('已占', text)
            self.assertIn('已等', text)
            self.assertGreaterEqual(text.count('[GUI_WAIT]'), 2)
            self.assertIn('[GUI_DEFERRED]', text)
            self.assertEqual(list(Path(common).rglob('*.ticket')), [], '超时后必须退出排队')

    def test_waiters_are_served_in_arrival_order(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            first, second, common = [root / part for part in ('A', 'B', 'common')]
            for path in (first, second, common):
                path.mkdir()
            holder_script = """
import sys
sys.path.insert(0, sys.argv[1])
import run_selftests as r
p = r.acquire_gui_lock(sys.argv[2], wait=0)
print('READY', flush=True)
sys.stdin.readline()
r.release_gui_lock(p)
"""
            contender_script = """
import sys, time
sys.path.insert(0, sys.argv[1])
import run_selftests as r
p = r.acquire_gui_lock(sys.argv[2], wait=10)
print('GOT', sys.argv[3], time.time_ns(), flush=True)
time.sleep(0.05)
r.release_gui_lock(p)
"""
            holder = subprocess.Popen([sys.executable, '-u', '-c', holder_script,
                                       runner.HERE, str(common)],
                                      cwd=first, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, text=True)
            first_waiter = second_waiter = None
            try:
                self.assertEqual(holder.stdout.readline().strip(), 'READY')
                first_waiter = subprocess.Popen([sys.executable, '-u', '-c', contender_script,
                                                 runner.HERE, str(common), 'A'],
                                                cwd=first, stdout=subprocess.PIPE,
                                                stderr=subprocess.PIPE, text=True)
                queue = common / runner.GUI_QUEUE_NAME
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline and not list(queue.glob('*.ticket')):
                    time.sleep(0.01)
                self.assertTrue(list(queue.glob('*.ticket')), '第一个等待者应已入队')
                second_waiter = subprocess.Popen([sys.executable, '-u', '-c', contender_script,
                                                  runner.HERE, str(common), 'B'],
                                                 cwd=second, stdout=subprocess.PIPE,
                                                 stderr=subprocess.PIPE, text=True)
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline and len(list(queue.glob('*.ticket'))) < 2:
                    time.sleep(0.01)
                self.assertEqual(len(list(queue.glob('*.ticket'))), 2, '两个等待者都应已入队')
                holder.stdin.write('\n')
                holder.stdin.flush()
                holder.communicate(timeout=30)
                out_first, err_first = first_waiter.communicate(timeout=30)
                out_second, err_second = second_waiter.communicate(timeout=30)
                self.assertEqual(first_waiter.returncode, 0, err_first[-1500:])
                self.assertEqual(second_waiter.returncode, 0, err_second[-1500:])
                lines_first = [line for line in out_first.splitlines() if line.startswith('GOT ')]
                lines_second = [line for line in out_second.splitlines() if line.startswith('GOT ')]
                self.assertEqual(len(lines_first), 1, out_first[-1500:])
                self.assertEqual(len(lines_second), 1, out_second[-1500:])
                self.assertLess(int(lines_first[0].split()[2]), int(lines_second[0].split()[2]),
                                '先到者必须先拿到令牌')
            finally:
                try:
                    holder.stdin.close()
                except OSError:
                    pass
                for process in (holder, first_waiter, second_waiter):
                    if process is not None and process.poll() is None:
                        process.kill()
                        process.communicate(timeout=10)

    def test_failure_observes_other_holder_and_retains_red(self):
        class Failing(unittest.TestCase):
            def runTest(self):
                self.fail('real failure')
        output = io.StringIO()
        with mock.patch.object(selftest_scheduling, 'other_gui_holder', return_value=987):
            result = unittest.TextTestRunner(stream=output, resultclass=runner.ConcurrencyResult).run(Failing())
        self.assertEqual(len(result.failures), 1)
        self.assertIn('[SUSPECT_CONCURRENCY]', output.getvalue())
        self.assertIn('987', output.getvalue())

    def test_full_lock_then_gui_and_both_release_on_exception(self):
        with tempfile.TemporaryDirectory() as common, contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(selftest_env, 'git_common_dir', return_value=common))
            for name, value in {'test_modules': ['test_demo'], 'gui_test_module': True,
                                'load_layer_document': {}, 'content_tree': 'tree',
                                'full_safe_preflight': (True, 'tree'), 'protect_tk': None,
                                'import_all': [],
                                '_git_text': 'head', 'latest_completed_round': 965}.items():
                _patch(stack, name, return_value=value)
            def check_order(todo, jobs, **kwargs):
                self.assertTrue((Path(common) / runner.FULL_SAFE_LOCK_NAME).exists())
                self.assertTrue((Path(common) / runner.GUI_LOCK_NAME).exists())
                raise RuntimeError('after both locks')
            stack.enter_context(mock.patch.object(runner, 'run_units', side_effect=check_order))
            with self.assertRaisesRegex(RuntimeError, 'after both locks'):
                runner.main(['--all', '--safe', '--force', '--gui-wait', '0'])
            self.assertFalse((Path(common) / runner.FULL_SAFE_LOCK_NAME).exists())
            self.assertFalse((Path(common) / runner.GUI_LOCK_NAME).exists())
