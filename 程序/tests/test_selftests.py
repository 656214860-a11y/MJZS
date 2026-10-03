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
    def test_safe_mode_is_full_serial_but_keeps_chunks(self):
        self.assertEqual(run_selftests.safe_full_options(False, False, False, 8, True),
                         (True, True, False, 1))

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

    def test_parallel_runner_reports_heartbeat_while_waiting(self):
        source = inspect.getsource(run_selftests.run_units)
        self.assertIn('futures.wait(', source)
        self.assertIn('HEARTBEAT_SECONDS', source)
        self.assertIn('并行回归仍在执行', source)

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

    def test_full_safe_counter_only_applies_to_master(self):
        self.assertTrue(run_selftests.full_safe_required(858, 855, True))
        self.assertFalse(run_selftests.full_safe_required(858, 855, False))

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
