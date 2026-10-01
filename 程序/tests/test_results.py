# -*- coding: utf-8 -*-
"""提示词结果解析自检。"""
import json
import unittest

from video_prompt_results import parse_result


SIG = "a" * 64


class ParseResultTests(unittest.TestCase):
    def test_valid(self):
        raw = json.dumps({"shot_id": "SH001", "source_signature": SIG, "video_prompt": "测试画面"}, ensure_ascii=False)
        record, fixed = parse_result(raw)
        self.assertFalse(fixed)
        self.assertEqual(record["video_prompt"], "测试画面")

    def test_invalid_json_raises(self):
        with self.assertRaises(ValueError):
            parse_result('{"shot_id": "SH001"')

    def test_missing_shot_id_raises(self):
        raw = json.dumps({"source_signature": SIG, "video_prompt": "x"})
        with self.assertRaises(ValueError):
            parse_result(raw)

    def test_bad_signature_raises(self):
        raw = json.dumps({"shot_id": "SH001", "source_signature": "nope", "video_prompt": "x"})
        with self.assertRaises(ValueError):
            parse_result(raw)

    def test_repairs_literal_newline_in_prompt(self):
        raw = '{"shot_id": "SH001", "source_signature": "' + SIG + '", "video_prompt": "第1句\n第2句"}'
        record, fixed = parse_result(raw)
        self.assertTrue(fixed)
        self.assertEqual(record["video_prompt"], "第1句\n第2句")

    def test_repair_with_trailing_field_rejected(self):
        raw = '{"shot_id": "SH001", "source_signature": "' + SIG + '", "video_prompt": "第1句\n第2句", "episode_id": "EP001"}'
        with self.assertRaises(ValueError):
            parse_result(raw)
