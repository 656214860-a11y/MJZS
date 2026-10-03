# -*- coding: utf-8 -*-
"""run_selftests 的回归覆盖：门禁调度必须可恢复、可增量、不可遗留后台助手。"""
import inspect
import os
import tempfile
import unittest
from datetime import datetime
from unittest import mock

import run_selftests
import smoke_test


class SafeRunnerTests(unittest.TestCase):
    def test_parallel_timeout_records_failure_and_terminates_worker(self):
        from concurrent.futures import Future
        pending = Future()
        process = mock.Mock()
        pool = mock.Mock()
        pool.submit.return_value = pending
        pool._processes = {1: process}
        with mock.patch('concurrent.futures.ProcessPoolExecutor', return_value=pool), \
             mock.patch.object(run_selftests, 'HEARTBEAT_SECONDS', 0), \
             mock.patch.object(run_selftests, 'SAFE_UNIT_TIMEOUT', 0):
            result = run_selftests.run_units([('stalled', 'test_demo', None)])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][3], ['stalled'])
        self.assertIn('超时', result[0][4])
        process.terminate.assert_called_once_with()
        pool.shutdown.assert_called_once_with(wait=False, cancel_futures=True)

    def test_safe_mode_keeps_non_gui_parallel_capacity(self):
        self.assertEqual(run_selftests.safe_full_options(False, False, False, 8, True),
                         (True, False, False, 8))

    def test_non_safe_options_are_preserved(self):
        self.assertEqual(run_selftests.safe_full_options(True, False, False, 4, False),
                         (True, False, False, 4))

    def test_serial_runner_has_recoverable_timeout(self):
        source = inspect.getsource(run_selftests.run_serial)
        self.assertIn('result_reader.poll(timeout)', source)
        self.assertIn('process.terminate()', source)

    def test_serial_runner_drains_result_before_waiting_for_child_exit(self):
        source = inspect.getsource(run_selftests.run_serial)
        self.assertLess(source.index('result_reader.poll(timeout)'), source.index('process.join(10)'))

    def test_serial_runner_runs_the_unit_when_windows_cannot_spawn_isolation_process(self):
        payload = ('回退单元', 'test_demo', None)
        expected = ('回退单元', 'test_demo', 1, [], '', 0.0, '')
        with mock.patch('multiprocessing.Process') as process, \
             mock.patch.object(run_selftests, '_run_unit', return_value=expected) as run:
            process.return_value.start.side_effect = PermissionError(5, '拒绝访问')
            self.assertEqual(run_selftests.run_serial([payload]), [expected])
        run.assert_called_once_with(payload)

    def test_safe_serial_runner_never_spawns_an_isolation_process(self):
        payload = ('安全单元', 'test_demo', None)
        expected = ('安全单元', 'test_demo', 1, [], '', 0.0, '')
        with mock.patch.object(run_selftests, '_run_unit', return_value=expected) as run, \
             mock.patch('multiprocessing.Process') as process:
            self.assertEqual(run_selftests.run_safe_serial([payload]), [expected])
        run.assert_called_once_with(payload)
        process.assert_not_called()

    def test_safe_gui_pool_is_capped_at_two_workers(self):
        self.assertEqual(run_selftests.safe_gui_jobs(8), 2)
        self.assertEqual(run_selftests.safe_gui_jobs(1), 1)

    def test_safe_split_identifies_tk_units(self):
        units = [('service', 'test_service', None), ('window', 'test_window', None)]
        with mock.patch.object(run_selftests, 'gui_test_module', side_effect=lambda name: name == 'test_window'):
            self.assertEqual(run_selftests.split_safe_units(units), ([units[0]], [units[1]]))

    def test_parallel_runner_reports_heartbeat_while_waiting(self):
        source = inspect.getsource(run_selftests.run_units)
        self.assertIn('futures.wait(', source)
        self.assertIn('HEARTBEAT_SECONDS', source)
        self.assertIn('并行回归仍在执行', source)

    def test_parallel_runner_recovers_after_no_progress_timeout(self):
        source = inspect.getsource(run_selftests.run_units)
        self.assertIn('SAFE_UNIT_TIMEOUT', source)
        self.assertIn('process.terminate()', source)
        self.assertIn('并行池连续', source)

    def test_slowest_units_are_descending_and_bounded(self):
        first = ('fast', 'test_fast', 1, [], '', 0.2, '')
        second = ('slow', 'test_slow', 1, [], '', 9.0, '')
        third = ('middle', 'test_middle', 1, [], '', 1.5, '')
        self.assertEqual([item[0] for item in run_selftests.slowest_units(
            [first, second, third], limit=2)], ['slow', 'middle'])

    def test_large_suite_is_split_into_small_units(self):
        class Case(unittest.TestCase):
            pass
        cases = []
        for index in range(17):
            case = Case('runTest')
            case._testMethodName = 'case_%d' % index
            cases.append(case)
        groups = [('Case', cases)]
        chunks = run_selftests.chunks_of(groups, limit=8)
        self.assertEqual([sum(len(methods) for _name, methods in chunk) for chunk in chunks], [8, 8, 1])

    def test_gui_short_and_e2e_layers_are_disjoint(self):
        names = ['test_service', 'test_window', 'test_ui_edges', 'test_pet_ui']
        with mock.patch.object(run_selftests, 'gui_test_module',
                               side_effect=lambda name: name != 'test_service'):
            short = run_selftests.modules_for_layer(names, 'gui-short')
            e2e = run_selftests.modules_for_layer(names, 'gui-e2e')
            self.assertEqual(short, ['test_window'])
            self.assertEqual(e2e, ['test_ui_edges', 'test_pet_ui'])
            self.assertEqual(set(short) & set(e2e), set())


class WorkerCleanupTests(unittest.TestCase):
    def test_cleanup_resets_thumbnail_worker(self):
        import asset_thumbs
        with mock.patch.object(asset_thumbs, 'reset_worker') as reset:
            run_selftests.cleanup_unit_helpers()
        reset.assert_called_once_with()

    def test_unit_cleans_worker_after_import_failure(self):
        with mock.patch.object(run_selftests, 'cleanup_unit_helpers') as cleanup:
            with mock.patch.object(run_selftests.importlib, 'import_module',
                                   side_effect=RuntimeError('simulated import failure')):
                result = run_selftests._run_unit(('模拟单元', 'missing_module', None))
        self.assertTrue(result[3])
        cleanup.assert_called_once_with()


class IncrementalTests(unittest.TestCase):
    def test_only_current_full_run_can_defer_receipt_check(self):
        import json
        with tempfile.TemporaryDirectory() as folder, \
             mock.patch.object(run_selftests, 'git_common_dir', return_value=folder), \
             mock.patch.object(run_selftests, '_pid_is_alive', return_value=True):
            path = os.path.join(folder, run_selftests.FULL_SAFE_LOCK_NAME)
            self.assertFalse(run_selftests.participating_full_safe_run(946))
            for pid, round_number, expected in (
                    (os.getpid(), 946, True), (os.getppid(), 946, True),
                    (-100, 946, False), (os.getpid(), 945, False)):
                with open(path, 'w', encoding='utf-8') as handle:
                    json.dump({'pid': pid, 'round': round_number}, handle)
                self.assertEqual(run_selftests.participating_full_safe_run(946), expected)
            with mock.patch.object(run_selftests, '_pid_is_alive', return_value=False):
                self.assertFalse(run_selftests.participating_full_safe_run(945))

    def test_incremental_flag_is_an_explicit_cli_option(self):
        source = inspect.getsource(run_selftests.main)
        self.assertIn("arg == '--incremental'", source)

    def test_new_test_is_scheduled(self):
        with tempfile.TemporaryDirectory() as folder:
            old_here, old_cache = run_selftests.HERE, run_selftests.CACHE_NAME
            try:
                run_selftests.HERE = folder
                run_selftests.CACHE_NAME = os.path.join('维护记录', '自检增量.json')
                with open(os.path.join(folder, 'test_demo.py'), 'w', encoding='utf-8') as handle:
                    handle.write('import unittest\n')
                todo, skipped, _state = run_selftests.incremental(['test_demo'], {})
                self.assertEqual(todo, ['test_demo'])
                self.assertEqual(skipped, [])
            finally:
                run_selftests.HERE, run_selftests.CACHE_NAME = old_here, old_cache

    def test_cache_path_uses_common_git_dir_and_falls_back_locally(self):
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.object(run_selftests, 'git_common_dir', return_value=folder):
                self.assertEqual(run_selftests.cache_path(),
                                 os.path.join(folder, 'selftest-incremental.json'))
        with mock.patch.object(run_selftests, 'git_common_dir', return_value=''):
            self.assertEqual(os.path.relpath(run_selftests.cache_path(), run_selftests.HERE),
                             os.path.join('维护记录', '自检增量.json'))

    def test_cache_write_replaces_file_atomically(self):
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.object(run_selftests, 'git_common_dir', return_value=folder):
                self.assertTrue(run_selftests.save_cache({'tests': {'test_demo': {}}}))
                self.assertEqual(run_selftests.load_cache()['tests'], {'test_demo': {}})

    def test_verified_content_tree_is_reused_for_seven_days(self):
        record = {'tree': 'abc', 'round': 850, 'seconds': 1021, 'at': '2026-10-03T00:00:00'}
        self.assertEqual(run_selftests.verified_tree_record(
            [record], 'abc', datetime(2026, 10, 9, 23, 59)), record)
        self.assertIsNone(run_selftests.verified_tree_record(
            [record], 'abc', datetime(2026, 10, 10, 0, 1)))

    def test_dirty_checkout_cannot_identify_as_verified_head(self):
        def git_response(*args):
            if args[:2] == ('rev-parse', '--show-toplevel'):
                return run_selftests.HERE
            if args[0] == 'status':
                return ' M desktop.py'
            return 'head-tree'
        with mock.patch.object(run_selftests, '_git_text', side_effect=git_response):
            self.assertEqual(run_selftests.content_tree(), '')

    def test_empty_tree_never_matches_a_receipt(self):
        record = {'tree': '', 'at': datetime.now().isoformat()}
        self.assertIsNone(run_selftests.verified_tree_record([record], ''))

    def test_changed_tree_during_run_cannot_publish_receipt(self):
        for current in ('', 'different-tree'):
            with self.subTest(current=current), \
                 mock.patch.object(run_selftests, 'content_tree', return_value=current), \
                 mock.patch.object(run_selftests, 'load_layer_document') as load:
                self.assertEqual(run_selftests.save_full_safe_verification('start-tree', 949, 400), '')
                load.assert_not_called()

    def test_full_safe_counter_only_applies_to_master(self):
        self.assertTrue(run_selftests.full_safe_required(858, 855, True))
        self.assertFalse(run_selftests.full_safe_required(858, 855, False))

    def test_full_safe_lock_rejects_active_holder_and_releases(self):
        with tempfile.TemporaryDirectory() as folder:
            lock = run_selftests.acquire_full_safe_lock(folder, 873)
            self.assertTrue(os.path.exists(lock))
            with self.assertRaisesRegex(RuntimeError, 'PID'):
                run_selftests.acquire_full_safe_lock(folder, 874)
            run_selftests.release_full_safe_lock(lock)
            replacement = run_selftests.acquire_full_safe_lock(folder, 874)
            self.assertTrue(os.path.exists(replacement))
            run_selftests.release_full_safe_lock(replacement)

    def test_elapsed_history_keeps_five_runs_and_uses_the_median(self):
        state = {}
        timings = run_selftests.record_elapsed(
            {'timings': {'recent_seconds': [9, 'bad', 2, 7, 4]}}, state, 6)
        self.assertEqual(timings, {'recent_seconds': [9.0, 2.0, 7.0, 4.0, 6.0],
                                   'median_seconds': 6.0})
        self.assertEqual(state['timings'], timings)

    def test_migrated_test_is_listed_once_and_nested_implementation_wins(self):
        with tempfile.TemporaryDirectory() as folder:
            nested = os.path.join(folder, 'tests')
            os.mkdir(nested)
            for path in (os.path.join(folder, 'test_demo.py'),
                         os.path.join(nested, 'test_demo.py')):
                with open(path, 'w', encoding='utf-8') as handle:
                    handle.write('import unittest\n')
            old_here, old_tests = run_selftests.HERE, run_selftests.TESTS_DIR
            try:
                run_selftests.HERE, run_selftests.TESTS_DIR = folder, nested
                self.assertEqual(run_selftests.test_modules(), ['test_demo'])
                self.assertEqual(run_selftests.test_path('test_demo'), os.path.join(nested, 'test_demo.py'))
            finally:
                run_selftests.HERE, run_selftests.TESTS_DIR = old_here, old_tests


class SmokePolicyTests(unittest.TestCase):
    def test_incremental_gate_stays_serial(self):
        self.assertEqual(smoke_test.gate_args(False), ['--serial'])

    def test_affected_gate_only_passes_requested_modules(self):
        self.assertEqual(smoke_test.gate_args(False, affected=('idea_chat', 'workflow')),
                         ['--serial', '-k', 'idea_chat workflow'])

    def test_runner_source_uses_its_migrated_test_module(self):
        self.assertEqual(smoke_test.gate_args(False, affected=('run_selftests',)),
                         ['--serial', '-k', 'selftests'])
        self.assertEqual(smoke_test.affected_test_filters(('smoke_test', 'run_selftests', 'idea_chat')),
                         ('selftests', 'idea_chat'))

    def test_full_gate_ignores_targeted_filter(self):
        self.assertEqual(smoke_test.gate_args(True, affected=('idea_chat',)),
                         ['--all', '--serial'])


if __name__ == '__main__':
    unittest.main()
