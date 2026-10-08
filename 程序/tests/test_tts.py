# -*- coding: utf-8 -*-
"""TTS 配置与请求体自检。运行：python test_tts.py"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import tts_api
from project_context import ProjectContext


def _gateway():
    from agent.core import save, save_bytes
    return {"publish_json": save, "publish_bytes": save_bytes}


class TtsValidateTests(unittest.TestCase):
    def test_valid(self):
        v = tts_api.validate("https://api.openai.com/v1", "tts-1", "alloy", "sk-abc")
        self.assertEqual(v["model"], "tts-1")

    def test_local_http_allowed(self):
        v = tts_api.validate("http://127.0.0.1:8000/v1", "m", "v", "k")
        self.assertEqual(v["voice"], "v")

    def test_remote_http_rejected(self):
        with self.assertRaises(ValueError):
            tts_api.validate("http://example.com/v1", "m", "v", "k")

    def test_missing_key_rejected(self):
        with self.assertRaises(ValueError):
            tts_api.validate("https://api.openai.com/v1", "tts-1", "alloy", "")


class TtsPayloadTests(unittest.TestCase):
    def test_payload(self):
        self.assertEqual(tts_api.payload("你好", "tts-1", "alloy", 1.0),
                         {"model": "tts-1", "input": "你好", "voice": "alloy", "speed": 1.0})


class TtsSynthesizeTests(unittest.TestCase):
    def test_synthesize_builds_correct_request(self):
        calls = {}

        class FakeResponse:
            def read(self):
                return b"FAKEAUDIO"
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        class FakeOpener:
            def open(self, req, timeout):
                calls["url"] = req.full_url
                calls["body"] = req.data
                return FakeResponse()

        # 第 34 期第 9 条：build_opener 改成 synthesize 内 import，patch 目标跟着换成 urllib.request。
        with patch.object(tts_api, "read_settings", return_value={"base_url": "https://api.openai.com/v1", "model": "tts-1", "voice": "alloy"}), \
             patch.object(tts_api, "load_key", return_value="sk-test"), \
             patch("urllib.request.build_opener", return_value=FakeOpener()):
            raw = tts_api.synthesize("你好")
        self.assertEqual(raw, b"FAKEAUDIO")
        self.assertEqual(calls["url"], "https://api.openai.com/v1/audio/speech")
        self.assertEqual(json.loads(calls["body"])["input"], "你好")


    def test_synthesize_empty_or_non_string_rejected(self):
        with patch.object(tts_api, "read_settings", return_value={"base_url": "https://api.openai.com/v1", "model": "tts-1", "voice": "alloy"}),              patch.object(tts_api, "load_key", return_value="sk-test"):
            with self.assertRaises(ValueError):
                tts_api.synthesize("")
            with self.assertRaises(ValueError):
                tts_api.synthesize(None)


class TtsBuildLinesTests(unittest.TestCase):
    def test_build_lines_resolves_names(self):
        entries = [("SH001", "CHAR_001", "你好", 1.0, 3.0)]
        assets = {"CHAR_001": {"name": "卡梅隆"}}
        lines = tts_api.build_lines(entries, assets)
        self.assertEqual(lines[0]["name"], "卡梅隆")
        self.assertEqual(lines[0]["text"], "你好")
        self.assertEqual(lines[0]["start"], 1.0)

    def test_build_lines_fallback_speaker(self):
        lines = tts_api.build_lines([("SH001", "CHAR_009", "你好", 1.0, 3.0)], {})
        self.assertEqual(lines[0]["name"], "CHAR_009")

    def test_build_lines_non_string_name_coerced(self):
        lines = tts_api.build_lines([("SH001", "CHAR_001", "你好", 1.0, 3.0)], {"CHAR_001": {"name": 123}})
        self.assertEqual(lines[0]["name"], "123")


class TtsBuildScriptTests(unittest.TestCase):
    def test_build_script(self):
        entries = [("SH001", "CHAR_001", "你好", 1.0, 3.0), ("SH001", "CHAR_002", "再见", 3.0, 5.0)]
        assets = {"CHAR_001": {"name": "卡梅隆"}, "CHAR_002": {"name": "无脸女"}}
        script = tts_api.build_script(entries, assets)
        self.assertEqual(script, "卡梅隆：你好" + "\n" + "无脸女：再见")

    def test_build_script_empty(self):
        self.assertEqual(tts_api.build_script([], {}), "")


class TtsLengthGuardTests(unittest.TestCase):
    def test_too_long_rejected_before_request(self):
        with patch.object(tts_api, "read_settings", return_value={"base_url": "https://api.openai.com/v1", "model": "tts-1", "voice": "alloy"}), \
             patch.object(tts_api, "load_key", return_value="sk-test"):
            with self.assertRaises(ValueError):
                tts_api.synthesize("长" * 4001)


class TtsFullTrackPublicationTests(unittest.TestCase):
    @staticmethod
    def _context(project):
        return ProjectContext.snapshot(project, lambda _stage: Path(project))

    def test_publish_requires_l3_gateway(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(TypeError, "L3"):
                tts_api.publish_full_track(Path(td), 'same-script', b'audio bytes')

    def test_publishes_audio_then_idempotence_marker_and_reuses_it(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            with patch('tts_api.os.urandom', return_value=b'abc'):
                path = tts_api.publish_full_track(self._context(project), 'same-script', b'audio bytes', gateway=_gateway())
            self.assertEqual(path.read_bytes(), b'audio bytes')
            self.assertEqual(tts_api.reusable_full_track(self._context(project), 'same-script'), path)
            self.assertIsNone(tts_api.reusable_full_track(self._context(project), 'changed-script'))

    def test_failed_marker_publish_keeps_completed_audio_without_reuse_marker(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            gateway = _gateway()
            gateway['publish_json'] = lambda *_args: (_ for _ in ()).throw(OSError('磁盘已满'))
            with patch('tts_api.os.urandom', return_value=b'abc'):
                with self.assertRaisesRegex(OSError, '磁盘已满'):
                    tts_api.publish_full_track(self._context(project), 'same-script', b'audio bytes', gateway=gateway)
            audio_dir = project / '11配音与字幕' / '音频'
            self.assertEqual((audio_dir / '配音_616263.mp3').read_bytes(), b'audio bytes')
            self.assertFalse((audio_dir / '整段配音.json').exists())


class TtsReadSettingsTests(unittest.TestCase):
    def test_corrupt_file_returns_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "tts_settings.json"
            p.write_text("not json", encoding="utf-8")
            with patch.object(tts_api, "settings_path", return_value=p):
                self.assertEqual(tts_api.read_settings()["model"], tts_api.DEFAULT_MODEL)

    def test_partial_file_merges_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "tts_settings.json"
            p.write_text(json.dumps({"model": "custom-tts"}), encoding="utf-8")
            with patch.object(tts_api, "settings_path", return_value=p):
                s = tts_api.read_settings()
                self.assertEqual(s["model"], "custom-tts")
                self.assertEqual(s["voice"], "alloy")


class TtsLoadKeyTests(unittest.TestCase):
    def test_corrupt_key_returns_empty(self):
        with patch.object(tts_api, "unified_key", return_value=""), \
             patch.object(tts_api, "read_settings", return_value={"encrypted_key": "not-valid-base64!!"}):
            self.assertEqual(tts_api.load_key(), "")

    def test_missing_key_returns_empty(self):
        with patch.object(tts_api, "unified_key", return_value=""), \
             patch.object(tts_api, "read_settings", return_value={"encrypted_key": ""}):
            self.assertEqual(tts_api.load_key(), "")

    def test_load_key_prefers_the_unified_env(self):
        """第 65 期任务 1：统一那份 .env 里有钥匙就先用它，老密文不再挡在前面。"""
        with patch.object(tts_api, "unified_key", return_value="sk-unified"), \
             patch.object(tts_api, "read_settings", return_value={"encrypted_key": ""}):
            self.assertEqual(tts_api.load_key(), "sk-unified")

    def test_save_key_writes_the_env_and_keeps_it_out_of_the_file(self):
        """第 65 期任务 1：密钥只进统一那份 .env；TTS 设置文件里不再留密钥。"""
        seen = []
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "tts_settings.json"
            with patch.object(tts_api, "settings_path", return_value=path), \
                 patch("model_pool.save_named_key", lambda name, value: seen.append((name, value))):
                tts_api.save_key("https://api.openai.com/v1", "tts-1", "alloy", "sk-tts", gateway=_gateway())
            stored = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(seen, [(tts_api.KEY_ENV, "sk-tts")])
        self.assertNotIn("encrypted_key", stored)
        self.assertEqual(stored["model"], "tts-1")

    def test_strips_audio_speech_suffix(self):
        v = tts_api.validate("https://api.openai.com/v1/audio/speech", "tts-1", "alloy", "sk-abc")
        self.assertEqual(v["base_url"], "https://api.openai.com/v1")


class TtsVoiceMappingTests(unittest.TestCase):
    def test_build_lines_voice_mapping(self):
        entries = [("SH001", "CHAR_001", "你好", 1.0, 3.0)]
        assets = {"CHAR_001": {"name": "卡梅隆"}}
        lines = tts_api.build_lines(entries, assets, {"CHAR_001": "voice_b"})
        self.assertEqual(lines[0]["voice"], "voice_b")

    def test_build_lines_no_voice_defaults_empty(self):
        lines = tts_api.build_lines([("SH001", "CHAR_001", "你好", 1.0, 3.0)], {})
        self.assertEqual(lines[0]["voice"], "")

    def test_synthesize_voice_override(self):
        calls = {}
        class FakeResponse:
            def read(self): return b"X"
            def __enter__(self): return self
            def __exit__(self, *a): return False
        class FakeOpener:
            def open(self, req, timeout):
                calls["body"] = req.data; return FakeResponse()
        with patch.object(tts_api, "read_settings", return_value={"base_url": "https://api.openai.com/v1", "model": "tts-1", "voice": "alloy"}),              patch.object(tts_api, "load_key", return_value="sk"),              patch("urllib.request.build_opener", return_value=FakeOpener()):
            tts_api.synthesize("你好", voice="voice_x")
        self.assertEqual(json.loads(calls["body"])["voice"], "voice_x")

    def test_build_lines_non_dict_voices_safe(self):
        lines = tts_api.build_lines([("SH001", "CHAR_001", "你好", 1.0, 3.0)], {}, "bad-string")
        self.assertEqual(lines[0]["voice"], "")


class TtsSpeedMappingTests(unittest.TestCase):
    def test_build_lines_speed_mapping(self):
        lines = tts_api.build_lines([("SH001", "CHAR_001", "你好", 1.0, 3.0)],
                                    {"CHAR_001": {"name": "卡梅隆"}}, {}, {"CHAR_001": 1.5})
        self.assertEqual(lines[0]["speed"], 1.5)

    def test_build_lines_default_speed(self):
        lines = tts_api.build_lines([("SH001", "CHAR_001", "你好", 1.0, 3.0)], {})
        self.assertEqual(lines[0]["speed"], 1.0)

    def test_coerce_speed_clamps(self):
        self.assertEqual(tts_api.coerce_speed(99), 4.0)
        self.assertEqual(tts_api.coerce_speed(0.01), 0.25)
        self.assertEqual(tts_api.coerce_speed("bad"), 1.0)
        self.assertEqual(tts_api.coerce_speed(None), 1.0)

    def test_coerce_speed_non_finite_falls_back(self):
        self.assertEqual(tts_api.coerce_speed(float("nan")), 1.0)
        self.assertEqual(tts_api.coerce_speed(float("inf")), 1.0)
        self.assertEqual(tts_api.coerce_speed(float("-inf")), 1.0)

    def test_build_lines_non_dict_speeds_safe(self):
        lines = tts_api.build_lines([("SH001", "CHAR_001", "你好", 1.0, 3.0)], {}, {}, "bad")
        self.assertEqual(lines[0]["speed"], 1.0)


class TtsBatchResumeTests(unittest.TestCase):
    """逐句配音批次可断点续跑：已成功的句子不重复合成，不重复扣费。"""

    def lines(self, count=3):
        return [{"shot_id": "SH%03d" % index, "speaker": "CHAR_001", "name": "角色", "text": "第%d句" % index,
                 "start": float(index), "end": float(index) + 1, "voice": "voice_a", "speed": 1.0}
                for index in range(1, count + 1)]

    def test_line_name_keeps_original_format(self):
        self.assertEqual(tts_api.line_name(2, {"shot_id": "SH002", "name": "旁白/角色", "start": 1.5}),
                          "002_SH002_旁白_角色_1.5s.mp3")

    def test_batch_publication_requires_l3_gateway(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(TypeError, "L3"):
                tts_api.run_lines(self.lines(1), Path(td), generate=lambda *_args, **_kwargs: b'audio')

    def test_fresh_run_writes_manifest_and_counts(self):
        calls = []
        def generate(text, speed=1.0, voice=None):
            calls.append(text); return b"audio:" + text.encode()
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            self.assertEqual(tts_api.run_lines(self.lines(3), folder, generate=generate, gateway=_gateway()), (3, 0, 0))
            self.assertEqual(len(calls), 3)
            manifest = json.loads((folder / "时间轴.json").read_text(encoding="utf-8"))
            self.assertEqual([item["state"] for item in manifest], ["ok"] * 3)
            self.assertTrue((folder / manifest[0]["file"]).is_file())

    def test_publish_line_keeps_old_manifest_when_index_write_fails(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td); manifest = [{"state": "old"}]
            old = folder / "时间轴.json"; old.write_text(json.dumps(manifest), encoding="utf-8")
            line = self.lines(1)[0]
            gateway = _gateway(); gateway['publish_json'] = lambda *_args: (_ for _ in ()).throw(OSError("磁盘已满"))
            with self.assertRaises(OSError): tts_api.publish_line(folder, manifest, 1, line, b"audio", gateway=gateway)
            self.assertEqual(json.loads(old.read_text(encoding="utf-8")), [{"state": "old"}])
            self.assertTrue((folder / tts_api.line_name(1, line)).is_file())

    def test_resume_reuses_finished_lines_and_retries_only_failures(self):
        calls = []
        def flaky(text, speed=1.0, voice=None):
            calls.append(text)
            if text == "第2句":
                raise ValueError("网络中断")
            return b"audio"
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            self.assertEqual(tts_api.run_lines(self.lines(3), folder, generate=flaky, gateway=_gateway()), (2, 0, 1))
            self.assertEqual(len(calls), 3)
            calls.clear()
            def generate(text, speed=1.0, voice=None):
                calls.append(text); return b"audio"
            self.assertEqual(tts_api.run_lines(self.lines(3), folder, generate=generate, gateway=_gateway()), (3, 2, 0))
            self.assertEqual(calls, ["第2句"])
            manifest = json.loads((folder / "时间轴.json").read_text(encoding="utf-8"))
            self.assertEqual([item["state"] for item in manifest], ["ok", "ok", "ok"])

    def test_resume_folder_matches_only_same_content(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "配音分句"; folder = root / "20260101_000000"
            tts_api.run_lines(self.lines(2), folder, generate=lambda *a, **k: b"audio", gateway=_gateway())
            self.assertEqual(tts_api.resume_folder(root, self.lines(2)), folder)
            changed = self.lines(2); changed[1]["text"] = "改过的台词"
            self.assertIsNone(tts_api.resume_folder(root, changed))
            changed[1]["text"] = "第2句"; changed[1]["voice"] = "voice_b"
            self.assertIsNone(tts_api.resume_folder(root, changed))
            self.assertIsNone(tts_api.resume_folder(Path(td) / "不存在", self.lines(2)))

    def test_interrupted_batch_continues_without_regenerating(self):
        import threading
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td); stop = threading.Event(); calls = []
            def generate(text, speed=1.0, voice=None):
                calls.append(text); stop.set(); return b"audio"
            self.assertEqual(tts_api.run_lines(self.lines(3), folder, generate=generate, stop=stop, gateway=_gateway()), (1, 0, 0))
            self.assertEqual(len(calls), 1)
            calls.clear()
            def again(text, speed=1.0, voice=None):
                calls.append(text); return b"audio"
            self.assertEqual(tts_api.run_lines(self.lines(3), folder, generate=again, gateway=_gateway()), (3, 1, 0))
            self.assertEqual(len(calls), 2)

    def test_pending_lines_previews_exactly_what_will_be_paid(self):
        """付费预览与实际提交同一口径：预览几 句，付费合成就会被调用几 次。"""
        calls = []
        def flaky(text, speed=1.0, voice=None):
            calls.append(text)
            if text == "第2句":
                raise ValueError("网络中断")
            return b"audio"
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            self.assertEqual(tts_api.pending_lines(self.lines(3), folder), [1, 2, 3])   # 全新批次：三句都要付
            tts_api.run_lines(self.lines(3), folder, generate=lambda *a, **k: b"audio", gateway=_gateway())
            self.assertEqual(tts_api.pending_lines(self.lines(3), folder), [])          # 全部已有成品：零费用
            changed = self.lines(3); changed[0]["text"] = "改过的台词"
            self.assertEqual(tts_api.pending_lines(changed, folder), [1])               # 只有改过的那句要重做
            half = Path(td) / "半成品"
            tts_api.run_lines(self.lines(3), half, generate=flaky, gateway=_gateway())
            self.assertEqual(calls, ["第1句", "第2句", "第3句"])
            calls.clear()
            def again(text, speed=1.0, voice=None):
                calls.append(text); return b"audio"
            preview = tts_api.pending_lines(self.lines(3), half)
            tts_api.run_lines(self.lines(3), half, generate=again, gateway=_gateway())
            self.assertEqual(preview, [2])                                              # 预览指向失败那一句
            self.assertEqual([self.lines(3)[index - 1]["text"] for index in preview], calls)


if __name__ == "__main__":
    unittest.main(verbosity=2)
