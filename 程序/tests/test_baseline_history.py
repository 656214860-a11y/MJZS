# -*- coding: utf-8 -*-
"""R789：离线基准历史的同条件趋势与归档门禁。"""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))
from performance_contract import (LONG_LIST_SCROLL_MEDIAN_MS, MEMORY_DELTA_MB,
                                  STARTUP_FIRST_FRAME_MS)

PROGRAM = Path(__file__).resolve().parent.parent
SCRIPT = PROGRAM / '维护记录' / '基准脚本' / 'benchmark_history.py'
spec = importlib.util.spec_from_file_location('benchmark_history_for_tests', SCRIPT)
benchmark_history = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = benchmark_history
spec.loader.exec_module(benchmark_history)

# 趋势只拦明显回归：中位基线抗抖动，绝对灾难线仍由既有性能门禁负责。
TREND_MULTIPLIERS = {
    'startup_page': 1.50,
    'long_list': 1.50,
    'memory_endurance': 1.35,
}
ABSOLUTE_LIMITS = {
    'first_frame_ms': STARTUP_FIRST_FRAME_MS,
    'scroll_avg_ms': LONG_LIST_SCROLL_MEDIAN_MS,
    'delta_mb': MEMORY_DELTA_MB,
}


def assert_no_trend_regression(testcase, history, current):
    for metric, value in current['metrics'].items():
        if not isinstance(value, (int, float)):
            continue
        baseline = benchmark_history.median_baseline(history, current, metric)
        if baseline is None or baseline <= 0:
            continue
        multiplier = TREND_MULTIPLIERS[current['family']]
        testcase.assertLessEqual(value, baseline * multiplier,
                                 '%s/%s %.3f 超过同条件中位基线 %.3f × %.2f'
                                 % (current['family'], metric, value, baseline, multiplier))


class BenchmarkHistoryTests(unittest.TestCase):
    def _record(self, *, family='startup_page', cache='cold', value=100.0):
        return {'round': 776, 'success': True, 'family': family,
                'condition': {'cache_state': cache, 'first_frame': True,
                              'includes_real_credentials': False},
                'metrics': {'first_frame_ms': value}}

    def test_archive_keeps_recent_records_with_registry_derived_conditions(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / '基准历史.json'
            condition = benchmark_history.measurement_conditions(cache_state='cold', first_frame=True)
            record = benchmark_history.append_history(
                family='startup_page', condition=condition, metrics={'first_frame_ms': 100.0},
                source_result='fixture.json', round_number=776, history_path=target)
            disk = json.loads(target.read_text(encoding='utf-8'))
        self.assertEqual(disk, [record])
        self.assertEqual(record['round'], 776)
        self.assertEqual(record['condition']['project_path_source'], '程序/projects.json')
        self.assertIn('machine', record['condition'])

    def test_archive_keeps_only_the_configured_recent_window(self):
        """历史唯一归档只保留最近 N 条，避免基准结果无限增长。"""
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / '基准历史.json'
            condition = {'cache_state': 'cold', 'first_frame': True,
                         'includes_real_credentials': False}
            for index in range(benchmark_history.MAX_HISTORY + 2):
                benchmark_history.append_history(
                    family='startup_page', condition=condition,
                    metrics={'first_frame_ms': float(index + 1)},
                    source_result='fixture-%s.json' % index,
                    round_number=index, history_path=target)
            disk = json.loads(target.read_text(encoding='utf-8'))
        self.assertEqual(len(disk), benchmark_history.MAX_HISTORY)
        self.assertEqual(disk[0]['round'], 2)
        self.assertEqual(disk[-1]['round'], benchmark_history.MAX_HISTORY + 1)

    def test_same_condition_regression_is_rejected_against_recent_median(self):
        history = [self._record(value=value) for value in (90.0, 100.0, 110.0)]
        current = self._record(value=151.0)
        with self.assertRaises(AssertionError):
            assert_no_trend_regression(self, history, current)

    def test_cold_and_warm_records_are_never_compared(self):
        history = [self._record(cache='cold', value=1.0)]
        current = self._record(cache='warm', value=1000.0)
        self.assertIsNone(benchmark_history.median_baseline(history, current, 'first_frame_ms'))
        assert_no_trend_regression(self, history, current)

    def test_committed_history_is_well_formed_and_obeys_trend_gate(self):
        history_path = PROGRAM / '维护记录' / '基准历史.json'
        history = json.loads(history_path.read_text(encoding='utf-8'))
        self.assertIsInstance(history, list)
        for index, record in enumerate(history):
            with self.subTest(index=index):
                self.assertIsInstance(record.get('round'), int)
                self.assertIn(record.get('family'), TREND_MULTIPLIERS)
                condition = record.get('condition', {})
                self.assertIn(condition.get('cache_state'), ('cold', 'warm'))
                self.assertIn('project_name', condition)
                self.assertIn('machine', condition)
                self.assertIn('first_frame', condition)
                self.assertIn('includes_real_credentials', condition)
                assert_no_trend_regression(self, history[:index], record)
