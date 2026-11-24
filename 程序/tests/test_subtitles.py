# -*- coding: utf-8 -*-
"""字幕时间轴生成自检。运行：python test_subtitles.py"""
import os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

from domain.subtitle_timing import calibrate_entries, srt_rows, timed_entries, stamp, _split_string


def shot(sid, dialogue, duration=10):
    return {"id": sid, "title": "镜头", "duration": duration, "dialogue": dialogue}


class SplitStringTests(unittest.TestCase):
    def test_fullwidth_slash_and_colon(self):
        self.assertEqual(_split_string("卡梅隆：你好／无脸女：再见"), [("卡梅隆", "你好"), ("无脸女", "再见")])
    def test_ascii_colon_and_slash(self):
        self.assertEqual(_split_string("A:hello/B:bye"), [("A", "hello"), ("B", "bye")])
    def test_no_speaker(self):
        self.assertEqual(_split_string("无说话人台词"), [("", "无说话人台词")])


class StampTests(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(stamp(0), "00:00:00,000")
    def test_non_finite_falls_back(self):
        self.assertEqual(stamp(float("nan")), "00:00:00,000")
        self.assertEqual(stamp(float("inf")), "00:00:00,000")
        self.assertEqual(stamp(-1), "00:00:00,000")
    def test_non_numeric_falls_back(self):
        self.assertEqual(stamp("1.5"), "00:00:01,500")
        self.assertEqual(stamp(None), "00:00:00,000")
        self.assertEqual(stamp("bad"), "00:00:00,000")

    def test_half_second(self):
        self.assertEqual(stamp(1.5), "00:00:01,500")
    def test_minute(self):
        self.assertEqual(stamp(60), "00:01:00,000")
    def test_hour_plus(self):
        self.assertEqual(stamp(3661.25), "01:01:01,250")


class SrtRowsTests(unittest.TestCase):
    def test_dialogue_none_ignored(self):
        ep = {"shots": [{"id": "SH001", "title": "镜头", "duration": 5, "dialogue": None}]}
        rows, estimated = srt_rows(ep)
        self.assertEqual(rows, [])
        self.assertFalse(estimated)

    def test_dialogue_non_list_ignored(self):
        ep = {"shots": [{"id": "SH001", "title": "镜头", "duration": 5, "dialogue": "不是数组"}]}
        rows, estimated = srt_rows(ep)
        self.assertEqual(rows, [])
        self.assertFalse(estimated)

    def test_timed_entries_preserved(self):
        ep = {"shots": [shot("SH001", [{"speaker": "A", "text": "你好", "start": 1, "end": 3}])]}
        rows, estimated = srt_rows(ep)
        self.assertFalse(estimated)
        self.assertEqual(len(rows), 1)
        self.assertIn("00:00:01,000 --> 00:00:03,000", rows[0])

    def test_untimed_string_distributed(self):
        ep = {"shots": [shot("SH001", ["卡梅隆：你好", "无脸女：再见"], duration=10)]}
        rows, estimated = srt_rows(ep)
        self.assertTrue(estimated)
        self.assertEqual(len(rows), 2)
        self.assertIn("你好", rows[0])
        self.assertIn("再见", rows[1])

    def test_multi_shot_untimed_distributed(self):
        ep = {"shots": [shot("SH001", ["A：一", "B：二"], duration=5),
                        shot("SH002", ["C：三"], duration=5)]}
        entries, estimated = timed_entries(ep)
        self.assertTrue(estimated)
        self.assertEqual(entries, [("SH001", "A", "一", 0.0, 2.5), ("SH001", "B", "二", 2.5, 5.0),
                                   ("SH002", "C", "三", 5.0, 10.0)])

    def test_mixed_timing_raises(self):
        ep = {"shots": [shot("SH001", [{"text": "已标注", "start": 1, "end": 3}, {"text": "未标注"}])]}
        with self.assertRaises(ValueError):
            srt_rows(ep)

    def test_non_dict_episode_empty(self):
        self.assertEqual(timed_entries(None), ([], False))
        self.assertEqual(timed_entries(["不是对象"]), ([], False))
        rows, estimated = srt_rows(["不是对象"])
        self.assertEqual(rows, [])
        self.assertFalse(estimated)

    def test_non_list_shots_ignored(self):
        self.assertEqual(timed_entries({"shots": None}), ([], False))
        self.assertEqual(timed_entries({"shots": "不是数组"}), ([], False))

    def test_no_dialogue_empty(self):
        ep = {"shots": [shot("SH001", [])]}
        rows, estimated = srt_rows(ep)
        self.assertEqual(rows, [])
        self.assertFalse(estimated)

    def test_timed_entries_speaker_and_shot(self):
        ep = {"shots": [shot("SH001", [{"speaker": "CHAR_001", "text": "你好", "start": 1, "end": 3}])]}
        entries, estimated = timed_entries(ep)
        self.assertFalse(estimated)
        self.assertEqual(entries, [("SH001", "CHAR_001", "你好", 1.0, 3.0)])

    def test_timed_entries_string_speaker(self):
        ep = {"shots": [shot("SH001", ["卡梅隆：你好"], duration=10)]}
        entries, estimated = timed_entries(ep)
        self.assertTrue(estimated)
        self.assertEqual(entries[0][0], "SH001")
        self.assertEqual(entries[0][1], "卡梅隆")
        self.assertEqual(entries[0][2], "你好")

    def test_multi_shot_offset_accumulates(self):
        ep = {"shots": [shot("SH001", [{"speaker": "A", "text": "一", "start": 1, "end": 3}], duration=5),
                        shot("SH002", [{"speaker": "A", "text": "二", "start": 1, "end": 3}], duration=5)]}
        entries, estimated = timed_entries(ep)
        self.assertFalse(estimated)
        self.assertEqual(entries[0], ("SH001", "A", "一", 1.0, 3.0))
        self.assertEqual(entries[1], ("SH002", "A", "二", 6.0, 8.0))

    def test_offset_skips_no_dialogue_shot(self):
        ep = {"shots": [shot("SH001", [{"speaker": "A", "text": "一", "start": 1, "end": 2}], duration=5),
                        shot("SH002", [], duration=5),
                        shot("SH003", [{"speaker": "B", "text": "三", "start": 0, "end": 1}], duration=5)]}
        entries, estimated = timed_entries(ep)
        self.assertFalse(estimated)
        self.assertEqual(entries, [("SH001", "A", "一", 1.0, 2.0), ("SH003", "B", "三", 10.0, 11.0)])

    def test_nan_start_rejected(self):
        ep = {"shots": [shot("SH001", [{"speaker": "A", "text": "x", "start": float("nan"), "end": 3}])]}
        with self.assertRaisesRegex(ValueError, r"SH001 第 1 句.*不是有限值"):
            srt_rows(ep)

    def test_non_string_text_coerced(self):
        ep = {"shots": [shot("SH001", [{"speaker": "A", "text": 123}])]}
        entries, estimated = timed_entries(ep)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0][2], "123")

    def test_empty_text_dict_skipped(self):
        ep = {"shots": [shot("SH001", [{"speaker": "A", "text": ""}, {"speaker": "B", "text": "你好"}])]}
        entries, estimated = timed_entries(ep)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0][1], "B")

    def test_explicit_end_beyond_shot_clamped(self):
        ep = {"shots": [shot("SH001", [{"speaker": "A", "text": "越界", "start": 12, "end": 15}], duration=10)]}
        entries, estimated = timed_entries(ep)
        self.assertFalse(estimated)
        start, end = entries[0][3], entries[0][4]
        self.assertLessEqual(start, 10.0)
        self.assertLessEqual(end, 10.0)
        self.assertGreater(end - start, 0.19)

    def test_reversed_times_rejected(self):
        ep = {"shots": [shot("SH001", [{"speaker": "A", "text": "反向", "start": 8, "end": 6}], duration=10)]}
        with self.assertRaisesRegex(ValueError, r"SH001 第 1 句.*不大于开始时间"):
            srt_rows(ep)

    def test_negative_start_rejected(self):
        ep = {"shots": [shot("SH001", [{"speaker": "A", "text": "负起点", "start": -2, "end": 2}], duration=10)]}
        with self.assertRaisesRegex(ValueError, r"SH001 第 1 句.*负数"):
            srt_rows(ep)

    def test_invalid_duration_string_falls_back(self):
        ep = {"shots": [{"id": "SH001", "title": "镜头", "duration": "abc", "dialogue": ["A：你好"]}]}
        entries, estimated = timed_entries(ep)
        self.assertEqual(entries[0][4], 5.0)

    def test_non_finite_duration_falls_back(self):
        ep = {"shots": [{"id": "SH001", "title": "镜头", "duration": "nan", "dialogue": ["A：你好"]}]}
        entries, estimated = timed_entries(ep)
        self.assertEqual(entries[0][4], 5.0)

    def test_srt_multiline_text_collapsed(self):
        ep = {"shots": [shot("SH001", [{"speaker": "A", "text": "第一行\n第二行", "start": 1, "end": 3}])]}
        rows, estimated = srt_rows(ep)
        self.assertEqual(len(rows), 1)
        self.assertIn("第一行 第二行", rows[0])
        self.assertNotIn("\n第二行", rows[0])

    def test_srt_full_format_numbering_and_blank_lines(self):
        ep = {"shots": [shot("SH001", [{"speaker": "A", "text": "一", "start": 1, "end": 2},
                                      {"speaker": "B", "text": "二", "start": 2, "end": 3}])]}
        rows, estimated = srt_rows(ep)
        text = "\n".join(rows)
        self.assertIn("1\n00:00:01,000 --> 00:00:02,000\n一\n", text)
        self.assertIn("2\n00:00:02,000 --> 00:00:03,000\n二\n", text)
        self.assertTrue(text.count("-->") == 2)

    def test_non_numeric_author_time_rejected(self):
        ep = {"shots": [shot("SH001", [{"speaker": "A", "text": "坏时间", "start": "abc", "end": 3}])]}
        with self.assertRaisesRegex(ValueError, r"SH001 第 1 句.*不是数字"):
            srt_rows(ep)

    def test_dense_dialogue_exports_without_overlap(self):
        ep = {"shots": [shot("SH001", [{"speaker": "A", "text": "长" * 100},
                                      {"speaker": "B", "text": "短"}], duration=5)]}
        entries, _report = calibrate_entries(ep)
        self.assertEqual(len(entries), 2)
        self.assertGreaterEqual(entries[1][3], entries[0][4] - 1e-9)
        self.assertGreaterEqual(entries[1][4] - entries[1][3], 0.19)
        rows, estimated = srt_rows(ep)
        self.assertTrue(estimated)
        self.assertEqual(len(rows), 2)

    def test_shot_too_short_for_lines_raises_clear_error(self):
        ep = {"shots": [shot("SH001", ["A：一", "B：二", "C：三", "D：四"], duration=0.5)]}
        with self.assertRaisesRegex(ValueError, r"SH001.*4 句.*0\.8 秒"):
            srt_rows(ep)

    def test_explicit_out_of_range_still_clamped_on_export(self):
        ep = {"shots": [shot("SH001", [{"speaker": "A", "text": "越界", "start": 12, "end": 15}], duration=10)]}
        rows, estimated = srt_rows(ep)
        self.assertFalse(estimated)
        self.assertEqual(len(rows), 1)
        self.assertIn("00:00:09,800 --> 00:00:10,000", rows[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
