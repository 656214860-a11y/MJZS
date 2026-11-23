# -*- coding: utf-8 -*-
"""voice-emotion-check 程序可核验比对。REQ-S11-14"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

from domain import voice_emotion_check as vec


class TestVoiceEmotionCheck(unittest.TestCase):
    def test_deviation_hit(self):
        script = [{"shot_id": "S1", "index": 1, "text": "你好", "emotion": "愤怒"}]
        tts = [{"shot_id": "S1", "index": 1, "text": "你好", "speed": 0.9, "volume": 0.7,
                "emotion": "calm"}]
        r = vec.check(script, tts)
        self.assertEqual(len(r["deviations"]), 1)
        self.assertIn("语速", r["deviations"][0]["reason"])

    def test_no_deviation(self):
        script = [{"shot_id": "S1", "index": 1, "text": "你好", "emotion": "平静"}]
        tts = [{"shot_id": "S1", "index": 1, "text": "你好", "speed": 1.0, "volume": 0.8,
                "emotion": None}]
        r = vec.check(script, tts)
        self.assertEqual(len(r["deviations"]), 0)

    def test_missing_annotation(self):
        script = [{"shot_id": "S1", "index": 1, "text": "你好"}]
        tts = [{"shot_id": "S1", "index": 1, "text": "你好", "speed": 1.0, "volume": 0.8}]
        r = vec.check(script, tts)
        self.assertEqual(len(r["unverifiable"]), 1)
        self.assertEqual(r["unverifiable"][0]["reason"], "缺标注")

    def test_missing_params(self):
        script = [{"shot_id": "S1", "index": 1, "text": "你好", "emotion": "平静"}]
        tts = [{"shot_id": "S1", "index": 1, "text": "你好"}]
        r = vec.check(script, tts)
        self.assertEqual(len(r["unverifiable"]), 1)
        self.assertEqual(r["unverifiable"][0]["reason"], "缺参数")

    def test_empty_list(self):
        r = vec.check([], [])
        self.assertEqual(r["deviations"], [])
        self.assertEqual(r["unverifiable"], [])

    def test_large_list_linear(self):
        n = 5000
        script = [{"shot_id": f"S{i}", "index": 1, "text": "x", "emotion": "平静"} for i in range(n)]
        tts = [{"shot_id": f"S{i}", "index": 1, "text": "x", "speed": 1.0, "volume": 0.8} for i in range(n)]
        r = vec.check(script, tts)
        self.assertEqual(len(r["deviations"]), 0)

    def test_tts_without_script_unverifiable(self):
        tts = [{"shot_id": "S9", "index": 1, "text": "x", "speed": 1.0, "volume": 0.8}]
        r = vec.check([], tts)
        self.assertTrue(any(u["reason"] == "缺标注" for u in r["unverifiable"]))

    def test_no_tts_calls(self):
        # pure: no import of tts synthesis; module has no generate
        self.assertFalse(hasattr(vec, "synthesize"))


if __name__ == "__main__":
    unittest.main()
