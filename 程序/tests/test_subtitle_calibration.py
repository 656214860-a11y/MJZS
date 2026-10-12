import json
import tempfile
import unittest
from pathlib import Path

from subtitle_timing import (calibrate_entries, line_weight, rows_from_entries,
                             srt_rows, validate_entries)
from subtitle_export_service import (export_calibration, export_srt,
                                     pending_calibration)


def shot(sid, dialogue, duration=10):
    return {'id': sid, 'title': '镜头', 'duration': duration, 'dialogue': dialogue}


SHORT = '短'
LONG = '这是一句明显更长的台词'


class LineWeightTests(unittest.TestCase):
    def test_ignores_whitespace(self):
        self.assertEqual(line_weight(' 你好 世界 '), 4.0)

    def test_minimum_one(self):
        self.assertEqual(line_weight(''), 1.0)
        self.assertEqual(line_weight(None), 1.0)


class CalibrateTests(unittest.TestCase):
    def test_length_weighting_gives_longer_line_more_time(self):
        entries, report = calibrate_entries({'shots': [shot('SH001', ['A：' + SHORT, 'B：' + LONG])]})
        self.assertEqual([e[0] for e in entries], ['SH001', 'SH001'])
        first, second = entries[0], entries[1]
        self.assertLess(first[4] - first[3], second[4] - second[3])
        self.assertAlmostEqual(entries[-1][4], 10.0, places=6)
        self.assertEqual(report['mode'], 'length')
        self.assertTrue(report['estimated'])
        self.assertEqual(len(report['uncalibrated']), 2)

    def test_audio_seconds_used_as_real_axis(self):
        ep = {'shots': [shot('SH001', ['A：' + SHORT, 'B：' + LONG])]}
        entries, report = calibrate_entries(ep, audio=[1.2, 3.4])
        self.assertEqual([(round(e[3], 3), round(e[4], 3)) for e in entries],
                         [(0.0, 1.2), (1.2, 4.6)])
        self.assertEqual(report['mode'], 'audio')
        self.assertEqual(report['audio'], 2)
        self.assertFalse(report['estimated'])
        self.assertEqual(report['uncalibrated'], [])

    def test_alignment_span_uses_its_length(self):
        ep = {'shots': [shot('SH001', ['A：一', 'B：二'])]}
        entries, report = calibrate_entries(ep, audio=[(0.5, 2.0), (2.0, 2.75)])
        self.assertAlmostEqual(entries[0][4] - entries[0][3], 1.5, places=6)
        self.assertAlmostEqual(entries[1][4] - entries[1][3], 0.75, places=6)
        self.assertEqual(report['audio'], 2)

    def test_missing_audio_marks_uncalibrated(self):
        ep = {'shots': [shot('SH001', ['A：一', 'B：二'])]}
        entries, report = calibrate_entries(ep, audio=[2.0, None])
        self.assertEqual(report['mode'], 'mixed')
        self.assertEqual(len(report['uncalibrated']), 1)
        self.assertEqual(report['uncalibrated'][0]['shot'], 'SH001')
        self.assertTrue(report['estimated'])

    def test_overflow_is_flagged_and_compressed(self):
        ep = {'shots': [shot('SH001', ['A：一', 'B：二'])]}
        entries, report = calibrate_entries(ep, audio=[8.0, 8.0])
        self.assertTrue(report['overflow'])
        self.assertTrue(all(e[4] > e[3] for e in entries))
        self.assertLessEqual(entries[-1][4], 10.0 + 1e-6)

    def test_explicit_times_are_preserved(self):
        ep = {'shots': [shot('SH001', [{'speaker': 'A', 'text': '已标注', 'start': 1, 'end': 3}])]}
        entries, report = calibrate_entries(ep)
        self.assertEqual(entries[0][3], 1.0)
        self.assertEqual(entries[0][4], 3.0)
        self.assertEqual(report['mode'], 'explicit')
        self.assertFalse(report['estimated'])

    def test_mixed_timing_still_raises(self):
        ep = {'shots': [shot('SH001', [{'text': '已标注', 'start': 1, 'end': 3}, {'text': '未标注'}])]}
        with self.assertRaises(ValueError):
            calibrate_entries(ep)

    def test_text_change_does_not_reuse_old_times(self):
        first = {'shots': [shot('SH001', ['A：' + SHORT, 'B：' + LONG])]}
        swapped = {'shots': [shot('SH001', ['A：' + LONG, 'B：' + SHORT])]}
        original, _ = calibrate_entries(first)
        changed, _ = calibrate_entries(swapped)
        self.assertNotAlmostEqual(original[0][4] - original[0][3],
                                  changed[0][4] - changed[0][3], places=3)

    def test_non_dict_episode_empty(self):
        entries, report = calibrate_entries(None)
        self.assertEqual(entries, [])
        self.assertEqual(report['mode'], 'estimate')
        self.assertFalse(report['estimated'])


class ValidateTests(unittest.TestCase):
    def test_non_finite_rejected(self):
        with self.assertRaisesRegex(ValueError, '有限值'):
            validate_entries([('SH001', 'A', 'x', 0.0, float('inf'))])

    def test_negative_rejected(self):
        with self.assertRaisesRegex(ValueError, '负数'):
            validate_entries([('SH001', 'A', 'x', -1.0, 2.0)])

    def test_reversed_rejected(self):
        with self.assertRaisesRegex(ValueError, '不大于开始时间'):
            validate_entries([('SH001', 'A', 'x', 5.0, 3.0)])

    def test_overlap_rejected(self):
        with self.assertRaisesRegex(ValueError, '重叠'):
            validate_entries([('SH001', 'A', 'x', 0.0, 2.0), ('SH001', 'B', 'y', 1.0, 3.0)])

    def test_out_of_range_rejected(self):
        with self.assertRaisesRegex(ValueError, '越界'):
            validate_entries([('SH001', 'A', 'x', 4.0, 6.0)], total=5.0)

    def test_clean_timeline_passes(self):
        self.assertIsNone(validate_entries([('SH001', 'A', 'x', 0.0, 2.0)], total=5.0))


class SrtRowsTests(unittest.TestCase):
    def test_rows_use_calibrated_axis(self):
        ep = {'shots': [shot('SH001', ['A：' + SHORT, 'B：' + LONG])]}
        rows, estimated = srt_rows(ep)
        self.assertTrue(estimated)
        self.assertEqual(len(rows), 2)
        self.assertIn('00:00:00,000 -->', rows[0])

    def test_rows_from_entries_shape(self):
        rows = rows_from_entries([('SH001', 'A', '猫', 0.0, 1.5)])
        self.assertEqual(rows[0].split('\n')[0], '1')
        self.assertIn('00:00:00,000 --> 00:00:01,500', rows[0])


class CalibrationExportTests(unittest.TestCase):
    def publisher(self, written):
        def publish(target, text, validate, update_index, encoding='utf-8'):
            path = Path(target)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding=encoding)
            written.append(path)
            return path
        return publish

    def test_pending_calibration_lists_uncalibrated(self):
        ep = {'shots': [shot('SH001', ['A：一', 'B：二'])]}
        pending = pending_calibration(ep)
        self.assertEqual(len(pending), 2)
        self.assertEqual(pending_calibration(ep, audio=[1.0, 1.0]), [])

    def test_export_calibration_writes_json_with_source(self):
        ep = {'shots': [shot('SH001', ['A：一'])]}
        with tempfile.TemporaryDirectory() as folder:
            written = []
            result = export_calibration(folder, ep, publish=self.publisher(written))
            self.assertTrue(result.ok)
            target, report = result.data
            self.assertEqual(target.name, '字幕校准.json')
            self.assertTrue(target.is_file())
            saved = json.loads(target.read_text(encoding='utf-8'))
            self.assertEqual(saved['source']['uncalibrated'], 1)
            self.assertEqual(saved['mode'], 'length')

    def test_export_srt_writes_srt_and_calibration(self):
        ep = {'shots': [shot('SH001', ['A：一'])]}
        with tempfile.TemporaryDirectory() as folder:
            written = []
            result = export_srt(folder, ep, publish=self.publisher(written))
            self.assertTrue(result.ok)
            target, report = result.data
            self.assertEqual(target.suffix, '.srt')
            self.assertTrue(report['estimated'])
            self.assertTrue(any(p.name == '字幕校准.json' for p in written))

    def test_export_srt_rejects_bad_audio_alignment(self):
        ep = {'shots': [shot('SH001', ['A：一'])]}
        with tempfile.TemporaryDirectory() as folder:
            # 非法对齐（end<=start）会被忽略并回退句长，不产生负数/零长度时间。
            result = export_srt(folder, ep, publish=self.publisher([]), audio=[(2.0, 1.0)])
            self.assertTrue(result.ok)
            _target, report = result.data
            self.assertEqual(report['audio'], 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
