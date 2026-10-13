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
FIXTURE = TESTS / 'fixtures' / 'benchmark_history_r776_with_r1373_regressions.json'
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

    def _history_fixture(self):
        """固定历史只验证门禁算法，不是当前性能验收凭据。

        .gitignore 从 R796 起将本机基准历史限定为本地诊断，不能把它当作
        已提交输入。fixture 的 R776 九条与受控的启动改前/改后、页面改后、
        长列表改后和内存 1min 结果一致；R1373 两条负例来自 full_改前结果。
        项目与机器元数据已替换成 fixture 标识，三项同条件分组值保持不变。
        当前实测仍由 test_perf_baseline / test_desktop_startup_perf 负责。
        """
        return json.loads(FIXTURE.read_text(encoding='utf-8'))

    def _assert_history_record_is_well_formed(self, record):
        self.assertIsInstance(record.get('round'), int)
        self.assertIn(record.get('family'), TREND_MULTIPLIERS)
        condition = record.get('condition', {})
        self.assertIn(condition.get('cache_state'), ('cold', 'warm'))
        self.assertIn('project_name', condition)
        self.assertIn('machine', condition)
        self.assertIn('first_frame', condition)
        self.assertIn('includes_real_credentials', condition)

    def _assert_history_is_well_formed_and_obeys_trend_gate(self, history):
        self.assertIsInstance(history, list)
        for index, record in enumerate(history):
            with self.subTest(index=index):
                self._assert_history_record_is_well_formed(record)
                assert_no_trend_regression(self, history[:index], record)

    def test_fixed_history_is_well_formed_and_obeys_trend_gate(self):
        history = self._history_fixture()['history']
        self.assertEqual(len(history), 9, '固定历史不得替换为空列表绕过趋势门禁')
        self._assert_history_is_well_formed_and_obeys_trend_gate(history)

    def test_recorded_r1373_regressions_are_rejected_for_the_affected_metric(self):
        fixture = self._history_fixture()
        expected = ('asset_page_300_ms', 'asset_page_300_warm_ms')
        self.assertEqual(len(fixture['regressions']), len(expected))
        for record, metric in zip(fixture['regressions'], expected):
            with self.subTest(metric=metric):
                self.assertEqual(record['round'], 1373)
                with self.assertRaisesRegex(AssertionError, 'startup_page/' + metric + ' '):
                    assert_no_trend_regression(self, fixture['history'], record)

    def test_unconfigured_hotspot_family_is_rejected(self):
        # R1373 探针会采集该族，但原门禁未给它趋势策略；本轮不发明阈值。
        record = self._record(family='hotspot_paths')
        with self.assertRaisesRegex(AssertionError, 'hotspot_paths'):
            self._assert_history_record_is_well_formed(record)
