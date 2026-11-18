# -*- coding: utf-8 -*-
"""CPU 参考活校准：量化时钟下仍按原一百万圈单位和三次最快判据。"""
import math
import unittest
from unittest import mock

import test_perf_baseline as baseline


class QuantizedClock:
    def __init__(self, reference_ms, phase_ms=0.0):
        self.reference_ms = reference_ms
        self.reference_samples = reference_ms if isinstance(reference_ms, tuple) else (reference_ms,) * 3
        self.elapsed_ms = phase_ms
        self.work_items = 0
        self.quantum_ms = 15.625

    def now(self):
        return math.floor(self.elapsed_ms / self.quantum_ms) * self.quantum_ms / 1000

    def work_range(self, count):
        if count == 10:
            for index in range(count):
                sample = min(self.work_items // (8 * count), 2)
                self.elapsed_ms += self.reference_samples[sample] / count
                self.work_items += 1
                yield index
        else:
            yield from range(count)


class ReferenceCalibration(unittest.TestCase):
    def measure(self, reference_ms, phase_ms=0.0):
        clock = QuantizedClock(reference_ms, phase_ms)
        with mock.patch.object(baseline, 'REFERENCE_LOOP', 10), \
             mock.patch.object(baseline, 'range', clock.work_range, create=True), \
             mock.patch.object(baseline.time, 'process_time', clock.now):
            measured = baseline.machine_speed_ms()
        return measured, clock

    def test_quantization_cannot_turn_a_within_budget_page_into_a_failure(self):
        """真实343.75/44=7.8125；原短窗最快31.25造成假红11，阈值仍为10。"""
        measured, clock = self.measure(44.0)
        self.assertLess(343.75 / measured, baseline.PAGE_OPEN_CPU_RATIO)
        self.assertEqual(baseline.PAGE_OPEN_CPU_RATIO, 10.0)
        self.assertLessEqual(abs(measured - 44.0), clock.quantum_ms / 8)
        self.assertEqual(clock.work_items, 3 * 8 * 10)

    def test_normalization_keeps_the_original_work_unit_at_both_speeds(self):
        for actual in (2.0, 15.625, 44.0, 88.0, 160.0):
            for phase in (step * 15.625 / 64 for step in range(64)):
                with self.subTest(actual=actual, phase=phase):
                    measured, clock = self.measure(actual, phase)
                    self.assertLessEqual(abs(measured - actual), clock.quantum_ms / 8)
                    self.assertEqual(clock.work_items, 3 * 8 * 10)

    def test_frequency_changes_keep_fastest_sample_without_load_compensation(self):
        for samples in ((44.0, 88.0, 66.0), (88.0, 66.0, 44.0), (66.0, 44.0, 88.0)):
            with self.subTest(samples=samples):
                measured, clock = self.measure(samples, 3.0)
                self.assertLessEqual(abs(measured - min(samples)), clock.quantum_ms / 8)
                self.assertEqual(clock.work_items, 3 * 8 * 10)

    def test_a_real_over_budget_page_still_fails_after_calibration(self):
        measured, _ = self.measure(44.0)
        self.assertGreater(500.0 / measured, baseline.PAGE_OPEN_CPU_RATIO)


if __name__ == '__main__':
    unittest.main()
