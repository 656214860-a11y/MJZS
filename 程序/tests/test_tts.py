# -*- coding: utf-8 -*-
"""TTS 配置与请求体自检。运行：python test_tts.py"""
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import Mock, patch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

from domain import tts_api
from contract.project_context import ProjectContext


def _gateway():
    from agent.core import save, save_bytes
    return {"publish_json": save, "publish_bytes": save_bytes}


_AUDIO_SETTINGS = {"base_url": "https://api.openai.com/v1", "model": "tts-1", "voice": "alloy"}


class _AudioResponse:
    """http_client 视角的音频响应：有界 read、status/headers、上下文管理。"""

    def __init__(self, body):
        self._body = io.BytesIO(body)
        self.status = 200
        self.headers = {}

    def read(self, n=-1):
        return self._body.read(n)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _AudioOpener:
    """``infra.http_client._default_opener`` 的替身：记录 urllib Request 并回放固定结果。"""

    def __init__(self, calls, body=b"FAKEAUDIO", error=None):
        self._calls, self._body, self._error = calls, body, error

    def open(self, request, timeout):
        self._calls["url"] = request.full_url
        self._calls["body"] = request.data
        self._calls["headers"] = dict(request.header_items())
        self._calls["timeout"] = timeout
        if self._error is not None:
            raise self._error
        return _AudioResponse(self._body)


def _synthesize_patches(calls, **opener_kwargs):
    """synthesize 的出站补丁组：走 http_client 默认 opener；urllib 自建 opener 出现即红。"""
    return (
        patch.object(tts_api, "read_settings", return_value=dict(_AUDIO_SETTINGS)),
        patch.object(tts_api, "load_key", return_value="sk-test"),
        patch("infra.http_client._default_opener",
              return_value=_AudioOpener(calls, **opener_kwargs)),
        patch("urllib.request.build_opener",
              side_effect=AssertionError("tts_api 不得自建 opener（规则 42）")),
    )


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
        # R3320：synthesize 改走 infra.http_client.request_bytes，patch 目标是其默认 opener；
        # 断言（URL/body/返回 bytes）与直连时代一致，另加 urllib 自建 opener 守卫。
        patches = _synthesize_patches(calls)
        with patches[0], patches[1], patches[2], patches[3]:
            raw = tts_api.synthesize("你好")
        self.assertEqual(raw, b"FAKEAUDIO")
        self.assertEqual(calls["url"], "https://api.openai.com/v1/audio/speech")
        self.assertEqual(calls["timeout"], 120)
        self.assertEqual(json.loads(calls["body"])["input"], "你好")
        sent = {key.lower(): value for key, value in calls["headers"].items()}
        self.assertEqual(sent.get("authorization"), "Bearer sk-test")
        self.assertEqual(sent.get("content-type"), "application/json")

    def test_synthesize_http_error_exposes_only_status(self):
        calls = {}
        error = urllib.error.HTTPError("https://api.openai.com/v1/audio/speech", 500, "err", {},
                                       io.BytesIO(b'{"error": "upstream bad"}'))
        patches = _synthesize_patches(calls, error=error)
        with patches[0], patches[1], patches[2], patches[3]:
            with self.assertRaises(ValueError) as caught:
                tts_api.synthesize("你好")
        self.assertEqual(str(caught.exception), 'TTS 请求失败（HTTP 500）')

    def test_synthesize_empty_audio_rejected(self):
        calls = {}
        patches = _synthesize_patches(calls, body=b"")
        with patches[0], patches[1], patches[2], patches[3]:
            with self.assertRaises(ValueError) as caught:
                tts_api.synthesize("你好")
        self.assertEqual(str(caught.exception), "TTS 未返回音频")

    def test_synthesize_timeout_and_unreachable_keep_transport_errors(self):
        """超时/连不上与直连时代同类：TimeoutError／URLError 原样抛出，不包装成 ValueError。"""
        calls = {}
        patches = _synthesize_patches(calls, error=TimeoutError("timed out"))
        with patches[0], patches[1], patches[2], patches[3]:
            with self.assertRaises(TimeoutError):
                tts_api.synthesize("你好")
        calls = {}
        patches = _synthesize_patches(calls, error=urllib.error.URLError("connection refused"))
        with patches[0], patches[1], patches[2], patches[3]:
            with self.assertRaises(urllib.error.URLError):
                tts_api.synthesize("你好")

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
        # FIX-S11-E5 契约有意变更：整段配音只念台词，不再带「角色名：」前缀。
        # 原断言（旧拼接口径）：script == "卡梅隆：你好" + "\n" + "无脸女：再见"
        entries = [("SH001", "CHAR_001", "你好", 1.0, 3.0), ("SH001", "CHAR_002", "再见", 3.0, 5.0)]
        assets = {"CHAR_001": {"name": "卡梅隆"}, "CHAR_002": {"name": "无脸女"}}
        script = tts_api.build_script(entries, assets)
        self.assertEqual(script, "你好" + "\n" + "再见")

    def test_build_script_empty(self):
        self.assertEqual(tts_api.build_script([], {}), "")

    def test_build_script_speaks_only_dialogue(self):
        """FIX-S11-E5：整段配音文本只含台词——不念角色名、角色编号，也不出现「未注明角色」。"""
        entries = [("SH001", "CHAR_001", "你好", 1.0, 3.0), ("SH002", "CHAR_002", "再见", 3.0, 5.0)]
        assets = {"CHAR_001": {"name": "卡梅隆"}, "CHAR_002": {"name": "无脸女"}}
        script = tts_api.build_script(entries, assets)
        self.assertEqual(script.split("\n"), ["你好", "再见"])   # 句数与对白条数一致
        for gone in ("卡梅隆", "无脸女", "CHAR_001", "CHAR_002", "未注明角色", "："):
            self.assertNotIn(gone, script)

    def test_build_script_without_character_assets(self):
        """FIX-S11-E5：没有角色资料的对白同样只念台词，不出现角色编号或「未注明角色」。"""
        entries = [("SH001", "CHAR_009", "只有台词", 1.0, 3.0)]
        script = tts_api.build_script(entries, {})
        self.assertEqual(script, "只有台词")
        self.assertNotIn("CHAR_009", script)
        self.assertNotIn("未注明角色", script)

    def test_build_script_skips_empty_text(self):
        """FIX-S11-E5：空文本（含纯空白）的句子不进整段配音文本。"""
        entries = [("SH001", "CHAR_001", "你好", 1.0, 3.0),
                   ("SH001", "CHAR_001", "", 3.0, 4.0),
                   ("SH001", "CHAR_001", "   ", 4.0, 5.0),
                   ("SH002", "CHAR_002", "再见", 5.0, 7.0)]
        script = tts_api.build_script(entries, {})
        self.assertEqual(script, "你好\n再见")


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
            with patch('domain.tts_api.os.urandom', return_value=b'abc'):
                path = tts_api.publish_full_track(self._context(project), 'same-script', b'audio bytes', gateway=_gateway())
            self.assertEqual(path.read_bytes(), b'audio bytes')
            self.assertEqual(tts_api.reusable_full_track(self._context(project), 'same-script'), path)
            self.assertIsNone(tts_api.reusable_full_track(self._context(project), 'changed-script'))

    def test_failed_marker_publish_keeps_completed_audio_without_reuse_marker(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            gateway = _gateway()
            gateway['publish_json'] = lambda *_args: (_ for _ in ()).throw(OSError('磁盘已满'))
            with patch('domain.tts_api.os.urandom', return_value=b'abc'):
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
        patches = _synthesize_patches(calls)
        with patches[0], patches[1], patches[2], patches[3]:
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

    def test_line_name_neutralizes_unsafe_shot_id(self):
        for shot in ("SH001/extra", "SH001\\extra", "../up", "..\\up", "a:b", "x\x00y", "SH*?<>|\"1"):
            with self.subTest(shot=shot):
                name = tts_api.line_name(1, {"shot_id": shot, "name": "角色", "start": 1.0})
                self.assertEqual(Path(name).name, name)
                self.assertNotRegex(name, r'[<>:"/\\|?*\x00-\x1f]')
                self.assertTrue(name.startswith("001_") and name.endswith("_角色_1.0s.mp3"), name)

    def test_line_name_keeps_format_for_missing_or_numeric_shot_id(self):
        self.assertEqual(tts_api.line_name(1, {"name": "角色", "start": 0}), "001_None_角色_0.0s.mp3")
        self.assertEqual(tts_api.line_name(3, {"shot_id": 7, "name": "角色", "start": 2}), "003_7_角色_2.0s.mp3")

    def test_line_name_limits_shot_id_length(self):
        self.assertEqual(tts_api.line_name(1, {"shot_id": "S" * 300, "name": "角色", "start": 1.0}),
                         "001_" + "S" * 40 + "_角色_1.0s.mp3")

    def test_run_lines_keeps_audio_inside_batch_folder_for_unsafe_shot_id(self):
        line = {**self.lines(1)[0], "shot_id": "SH001/extra"}
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / "batch"
            self.assertEqual(tts_api.run_lines([line], folder, generate=lambda *_a, **_k: b"audio", gateway=_gateway()),
                             (1, 0, 0))
            manifest = json.loads((folder / "时间轴.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest[0]["state"], "ok")
            self.assertEqual(manifest[0]["shot_id"], "SH001/extra")
            self.assertEqual(manifest[0]["file"], "001_SH001_extra_角色_1.0s.mp3")
            files = [path for path in Path(td).rglob("*") if path.is_file()]
            self.assertTrue(files)
            self.assertTrue(all(path.parent == folder for path in files), files)

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

    def test_changing_one_line_reuses_the_rest(self):
        """FIX-S11-E3：改一句台词后同集续跑——指纹失配按集标识找回最近批次，只重做变了的那句。"""
        calls = []
        def generate(text, speed=1.0, voice=None):
            calls.append(text)
            return b"audio"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "配音分句"
            folder = root / "配音批次_20260101"
            tts_api.run_lines(self.lines(3), folder, generate=generate,
                              gateway=_gateway(), episode="EP01")
            calls.clear()
            changed = self.lines(3)
            changed[1]["text"] = "改过的台词"
            out = tts_api.resume_folder(root, changed, "EP01")
            self.assertEqual(out, folder, "整批指纹失配应按集标识找回该集最近的批次")
            quote = tts_api.batch_cost_preview(Path(td), changed, out)
            self.assertEqual(quote["pending"], [2], "预览只报真变了的那句")
            self.assertEqual(
                tts_api.run_lines(changed, out, generate=generate,
                                  gateway=_gateway(), episode="EP01"),
                (3, 2, 0))
            self.assertEqual(calls, ["改过的台词"], "其余句子沿用不重复付费")

    def test_inserted_line_reuses_surrounding_lines(self):
        """FIX-S11-E3：中间插入一句——位置平移不连坐后面的句子，只重做新插入的那句。"""
        calls = []
        def generate(text, speed=1.0, voice=None):
            calls.append(text)
            return b"audio"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "配音分句"
            folder = root / "配音批次_20260101"
            tts_api.run_lines(self.lines(3), folder, generate=generate,
                              gateway=_gateway(), episode="EP01")
            calls.clear()
            original = self.lines(3)
            inserted = [original[0],
                        {**original[1], "shot_id": "SH999", "text": "新插入的台词"},
                        original[1], original[2]]
            out = tts_api.resume_folder(root, inserted, "EP01")
            self.assertEqual(out, folder)
            self.assertEqual(tts_api.pending_lines(inserted, out), [2])
            self.assertEqual(
                tts_api.run_lines(inserted, out, generate=generate,
                                  gateway=_gateway(), episode="EP01"),
                (4, 3, 0))
            self.assertEqual(calls, ["新插入的台词"])

    def test_changed_shot_timing_reuses_everything(self):
        """FIX-S11-E3：只调镜头时长（起止时间）一句都不重做——起止时间不属于句子身份。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "配音分句"
            folder = root / "配音批次_20260101"
            tts_api.run_lines(self.lines(3), folder, generate=lambda *a, **k: b"audio",
                              gateway=_gateway(), episode="EP01")
            retimed = [{**line, "start": line["start"] + 10, "end": line["end"] + 10}
                       for line in self.lines(3)]
            out = tts_api.resume_folder(root, retimed, "EP01")
            self.assertEqual(out, folder)
            self.assertEqual(tts_api.pending_lines(retimed, out), [], "只改时长不重做")
            def forbidden(*args, **kwargs):
                raise AssertionError("只改时长的句子不该重新合成")
            self.assertEqual(
                tts_api.run_lines(retimed, out, generate=forbidden,
                                  gateway=_gateway(), episode="EP01"),
                (3, 3, 0))
            manifest = json.loads((folder / "时间轴.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest[0]["state"], "ok")
            self.assertEqual(manifest[0]["start"], 11.0, "沿用句的起止时间要更新为当前值")

    def test_same_shot_same_text_pairs_in_order(self):
        """FIX-S11-E3：同镜同文本的两句按出现次序配对——第一处对第一处，不共用同一个文件。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "配音分句"
            folder = root / "配音批次_20260101"
            first = dict(self.lines(1)[0], start=1.0, end=2.0)
            second = dict(first, start=2.0, end=3.0)     # 同一身份，不同起止
            tts_api.run_lines([first, second], folder, generate=lambda *a, **k: b"audio",
                              gateway=_gateway(), episode="EP01")
            before = json.loads((folder / "时间轴.json").read_text(encoding="utf-8"))
            name_first, name_second = before[0]["file"], before[1]["file"]
            self.assertNotEqual(name_first, name_second)
            retimed = [{**line, "start": line["start"] + 10, "end": line["end"] + 10}
                       for line in (first, second)]
            out = tts_api.resume_folder(root, retimed, "EP01")
            self.assertEqual(out, folder)
            def forbidden(*args, **kwargs):
                raise AssertionError("同文本两句应各自沿用，不该重新合成")
            self.assertEqual(
                tts_api.run_lines(retimed, out, generate=forbidden,
                                  gateway=_gateway(), episode="EP01"),
                (2, 2, 0))
            manifest = json.loads((folder / "时间轴.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest[0]["file"], name_first)
            self.assertEqual(manifest[1]["file"], name_second)

    def test_manifest_non_object_entry_names_file_and_index(self):
        """FIX-S11-LOW E-14：时间轴清单混入非对象条目时报出清单文件与第几项，
        报价与逐句配音同口径，不静默续跑、不自动修清单。"""
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            lines = self.lines(3)
            entries = [dict(lines[0], state="ok", file=""), "坏条目",
                       dict(lines[2], state="ok", file="")]
            (folder / "时间轴.json").write_text(json.dumps(entries, ensure_ascii=False),
                                                encoding="utf-8")
            with self.assertRaises(ValueError) as preview:
                tts_api.batch_cost_preview(folder, lines, folder)
            message = str(preview.exception)
            self.assertIn("时间轴.json", message)
            self.assertIn("第 2 项", message)
            self.assertIn("不是对象", message)
            generate = Mock(return_value=b"audio")
            with self.assertRaises(ValueError) as rerun:
                tts_api.run_lines(lines, folder, generate=generate, gateway=_gateway())
            self.assertIn("时间轴.json", str(rerun.exception))
            self.assertIn("第 2 项", str(rerun.exception))
            generate.assert_not_called()


class TtsBatchIdentityTests(unittest.TestCase):
    """O12：批次身份含端点／模型／音色／语速，开批冻结，换配置不算旧缓存，损坏音频不续用。"""

    ENTRIES = [("SH001", "CHAR_001", "你好", 0.0, 1.0)]

    def _settings(self, model="tts-a", endpoint="https://a.example/v1"):
        return {"base_url": endpoint, "model": model, "voice": "alloy"}

    def test_build_lines_records_the_request_identity(self):
        lines = tts_api.build_lines(self.ENTRIES, {}, settings=self._settings())
        self.assertEqual(lines[0]["model"], "tts-a")
        self.assertEqual(lines[0]["endpoint"], "https://a.example/v1")
        self.assertEqual(lines[0]["voice"], "")
        self.assertEqual(lines[0]["speed"], 1.0)

    def test_mid_batch_settings_change_does_not_mix_configs(self):
        state = {"settings": self._settings()}
        seen = []

        def fake_synthesize(text, speed=1.0, voice=None, *, settings=None):
            current = settings if isinstance(settings, dict) else tts_api.read_settings()
            seen.append(current.get("model"))
            state["settings"] = self._settings(model="tts-b", endpoint="https://b.example/v1")
            return b"audio"

        lines = tts_api.build_lines(self.ENTRIES * 2, {}, settings=state["settings"])
        with tempfile.TemporaryDirectory() as td:
            with patch.object(tts_api, "read_settings", side_effect=lambda: dict(state["settings"])), \
                 patch.object(tts_api, "synthesize", side_effect=fake_synthesize):
                self.assertEqual(tts_api.run_lines(lines, Path(td), gateway=_gateway()), (2, 0, 0))
        self.assertEqual(seen, ["tts-a", "tts-a"], "开批时冻结的配置说了算，中途改设置不影响这一批")

    def test_switching_the_model_or_endpoint_invalidates_the_cache(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td); folder = base / "批一"
            first = tts_api.build_lines(self.ENTRIES, {}, settings=self._settings())
            tts_api.run_lines(first, folder, generate=lambda *a, **k: b"audio", gateway=_gateway())
            self.assertEqual(tts_api.pending_lines(first, folder), [])
            self.assertEqual(tts_api.resume_folder(base, tts_api.build_lines(
                self.ENTRIES, {}, settings=self._settings())), folder, "同配置同内容仍可续跑")
            other_model = tts_api.build_lines(self.ENTRIES, {}, settings=self._settings(model="tts-b"))
            self.assertIsNone(tts_api.resume_folder(base, other_model), "换模型就是另一份缓存")
            self.assertEqual(tts_api.pending_lines(other_model, folder), [1], "旧成品不算新模型的成品")
            other_endpoint = tts_api.build_lines(self.ENTRIES, {},
                                                 settings=self._settings(endpoint="https://b.example/v1"))
            self.assertIsNone(tts_api.resume_folder(base, other_endpoint), "换服务商也是另一份缓存")

    def test_a_corrupted_line_is_not_reused(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            lines = tts_api.build_lines(self.ENTRIES, {}, settings=self._settings())
            tts_api.run_lines(lines, folder, generate=lambda *a, **k: b"audio-bytes", gateway=_gateway())
            self.assertEqual(tts_api.pending_lines(lines, folder), [])
            name = json.loads((folder / "时间轴.json").read_text(encoding="utf-8"))[0]["file"]
            (folder / name).write_bytes(b"truncated")
            self.assertEqual(tts_api.pending_lines(lines, folder), [1], "摘要对不上就要重新合成")
            (folder / name).write_bytes(b"")
            self.assertEqual(tts_api.pending_lines(lines, folder), [1], "空文件不算成品")

    def test_a_legacy_manifest_without_digest_still_counts_when_non_empty(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            lines = tts_api.build_lines(self.ENTRIES, {}, settings=self._settings())
            name = tts_api.line_name(1, lines[0])
            (folder / name).write_bytes(b"old-audio")
            self.assertEqual(tts_api.pending_lines(lines, folder), [1], "没有清单就还没成品")
            tts_api._save(folder / "时间轴.json", [{**lines[0], "file": name, "state": "ok"}],
                          gateway=_gateway())
            self.assertEqual(tts_api.pending_lines(lines, folder), [], "旧清单没记摘要，文件非空即沿用")
            (folder / name).write_bytes(b"")
            self.assertEqual(tts_api.pending_lines(lines, folder), [1], "旧清单也要文件非空")

    def test_no_secret_enters_the_signature_manifest_or_batch_record(self):
        settings = dict(self._settings(), encrypted_key="CIPHER", api_key="sk-secret", voices={"CHAR_001": "v"})
        lines = tts_api.build_lines(self.ENTRIES, {}, settings=settings)
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            tts_api.run_lines(lines, folder, generate=lambda *a, **k: b"audio", gateway=_gateway())
            batch = json.loads((folder / "批次.json").read_text(encoding="utf-8"))
        blob = json.dumps({"lines": lines, "batch": batch}, ensure_ascii=False)
        self.assertNotIn("sk-secret", blob)
        self.assertNotIn("CIPHER", blob)
        self.assertEqual(batch["identity"]["models"], ["tts-a"])
        self.assertEqual(batch["identity"]["endpoints"], ["https://a.example/v1"])
        plain = tts_api.script_signature("你好", self._settings())
        self.assertEqual(plain, tts_api.script_signature("你好", settings), "密钥不参与整段指纹")
        self.assertNotEqual(plain, tts_api.script_signature("你好", self._settings(model="tts-b")))
        self.assertNotEqual(plain, tts_api.script_signature(
            "你好", self._settings(endpoint="https://b.example/v1")))


class TtsRejectAndReleaseTests(unittest.TestCase):
    """AUD-US05 E-1：4xx／连不上记 failed；超时仍 uncertain；写盘失败 unsaved；人工放开。"""

    def test_synthesize_http_4xx_raises_tts_rejected(self):
        calls = {}
        error = urllib.error.HTTPError(
            "https://api.openai.com/v1/audio/speech", 401, "err", {},
            io.BytesIO(b'{"error": "invalid key"}'))
        patches = _synthesize_patches(calls, error=error)
        with patches[0], patches[1], patches[2], patches[3]:
            with self.assertRaises(tts_api.TTSRejected) as caught:
                tts_api.synthesize("你好")
        self.assertIsInstance(caught.exception, ValueError)
        self.assertEqual(str(caught.exception), 'TTS 请求失败（HTTP 401）')

    def test_upstream_details_never_reach_time_line_or_progress(self):
        marker = 'synthetic-private-value'
        errors = (urllib.error.HTTPError(_AUDIO_SETTINGS['base_url'], 408, 'timeout', {},
                                         io.BytesIO(marker.encode())),
                  urllib.error.URLError('connection refused ' + marker),
                  TimeoutError('timed out ' + marker))
        for error in errors:
            with self.subTest(kind=type(error).__name__), tempfile.TemporaryDirectory() as td:
                folder, progress = Path(td), []
                patches = _synthesize_patches({}, error=error)
                with patches[0], patches[1], patches[2], patches[3]:
                    tts_api.run_lines([{'shot_id': 'S1', 'text': '甲'}], folder,
                                      report=progress.append, gateway=_gateway())
                timeline = (folder / '时间轴.json').read_text(encoding='utf-8')
                self.assertNotIn(marker, timeline)
                self.assertNotIn(marker, ''.join(progress))
                self.assertTrue(json.loads(timeline)[0]['error'])

    def test_http_408_blocks_resume_without_sending_another_request(self):
        for metered in (True, False):
            with self.subTest(metered=metered), tempfile.TemporaryDirectory() as td:
                project = Path(td) if metered else None
                folder = Path(td) / "audio"
                lines = [{"shot_id": "S1", "text": "你好", "speed": 1.0}]
                error = urllib.error.HTTPError(_AUDIO_SETTINGS["base_url"], 408, "timeout", {}, io.BytesIO(b""))
                patches = _synthesize_patches({}, error=error)
                with patches[0], patches[1], patches[2] as opener, patches[3]:
                    for attempt in range(2):
                        self.assertEqual(tts_api.run_lines(lines, folder, gateway=_gateway(), project=project),
                                         (0, 0, 1))
                        entry = json.loads((folder / "时间轴.json").read_text(encoding="utf-8"))[0]
                        self.assertEqual(entry["state"], "uncertain")
                        self.assertFalse(entry.get("not_submitted"))
                        if attempt == 0 and metered:
                            request_id = entry["request_id"]
                        elif metered:
                            self.assertEqual(entry["request_id"], request_id)
                    self.assertEqual(opener.call_count, 1)

    def test_old_failed_http_408_requires_explicit_release(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            lines = [{"shot_id": "S1", "text": "你好", "speed": 1.0}]
            entry = dict(lines[0], state="failed", error="TTS 请求失败（HTTP 408）：timeout",
                         not_submitted=True, request_id="tts:old", file="")
            _gateway()["publish_json"](folder / "时间轴.json", [entry])
            gen = Mock(return_value=b"audio")
            self.assertEqual(tts_api.unknown_line_indexes(lines, folder), [1])
            self.assertEqual(tts_api.run_lines(lines, folder, generate=gen, gateway=_gateway(), project=folder),
                             (0, 0, 1))
            gen.assert_not_called()
            self.assertNotIn('：timeout', (folder / '时间轴.json').read_text(encoding='utf-8'))
            self.assertEqual(tts_api.release_unknown(folder, [1], gateway=_gateway()), [1])
            self.assertEqual(tts_api.run_lines(lines, folder, generate=gen, gateway=_gateway(), project=folder),
                             (1, 0, 0))
            gen.assert_called_once()

    def test_run_lines_http_reject_marks_failed_and_resends(self):
        with tempfile.TemporaryDirectory() as td:
            project, folder = Path(td), Path(td) / "audio"
            lines = [{"shot_id": "S1", "text": "你好", "speed": 1.0}]
            generate = Mock(side_effect=tts_api.TTSRejected("TTS 请求失败（HTTP 401）：x"))
            self.assertEqual(
                tts_api.run_lines(lines, folder, generate=generate, gateway=_gateway(), project=project),
                (0, 0, 1))
            entry = json.loads((folder / "时间轴.json").read_text(encoding="utf-8"))[0]
            self.assertEqual(entry["state"], "failed")
            self.assertTrue(entry.get("not_submitted"))
            self.assertEqual(entry['error'], 'TTS 请求失败（HTTP 401）')
            generate.side_effect = None
            generate.return_value = b"audio"
            self.assertEqual(
                tts_api.run_lines(lines, folder, generate=generate, gateway=_gateway(), project=project),
                (1, 0, 0))
            self.assertEqual(generate.call_count, 2)

    def test_run_lines_urlerror_marks_failed_timeout_stays_uncertain(self):
        with tempfile.TemporaryDirectory() as td:
            project, folder = Path(td), Path(td) / "audio"
            lines = [{"shot_id": "S1", "text": "你好", "speed": 1.0}]
            gen = Mock(side_effect=urllib.error.URLError("connection refused"))
            tts_api.run_lines(lines, folder, generate=gen, gateway=_gateway(), project=project)
            self.assertEqual(json.loads((folder / "时间轴.json").read_text(encoding="utf-8"))[0]["state"], "failed")
            folder2 = Path(td) / "audio2"
            gen2 = Mock(side_effect=TimeoutError("timed out"))
            tts_api.run_lines(lines, folder2, generate=gen2, gateway=_gateway(), project=project)
            self.assertEqual(json.loads((folder2 / "时间轴.json").read_text(encoding="utf-8"))[0]["state"], "uncertain")
            self.assertEqual(
                tts_api.run_lines(lines, folder2, generate=gen2, gateway=_gateway(), project=project),
                (0, 0, 1))
            self.assertEqual(gen2.call_count, 1)

    def test_urlerror_wrapped_timeout_is_uncertain_and_never_resent(self):
        """FIX-S11-E1B：URLError 包裹的超时＝结果未知，不许标 failed 自动重发（重复扣费）。"""
        with tempfile.TemporaryDirectory() as td:
            project, folder = Path(td), Path(td) / "audio"
            lines = [{"shot_id": "S1", "text": "你好", "speed": 1.0}]
            gen = Mock(side_effect=urllib.error.URLError(TimeoutError("timed out")))
            self.assertEqual(
                tts_api.run_lines(lines, folder, generate=gen, gateway=_gateway(), project=project),
                (0, 0, 1))
            entry = json.loads((folder / "时间轴.json").read_text(encoding="utf-8"))[0]
            self.assertEqual(entry["state"], "uncertain")
            self.assertFalse(entry.get("not_submitted"))
            self.assertEqual(
                tts_api.run_lines(lines, folder, generate=gen, gateway=_gateway(), project=project),
                (0, 0, 1))
            self.assertEqual(gen.call_count, 1)

    def test_urlerror_wrapped_reset_is_uncertain_and_never_resent(self):
        """FIX-S11-E1B：URLError 底层是连接重置（类型化或文案形态）＝结果未知，不自动重发。"""
        errors = (
            urllib.error.URLError(ConnectionResetError(10054, "远程主机强迫关闭了一个现有的连接")),
            urllib.error.URLError("<urlopen error [WinError 10054] 远程主机强迫关闭了一个现有的连接。>"),
            urllib.error.URLError("connection reset by peer"),
        )
        for error in errors:
            with self.subTest(error=error), tempfile.TemporaryDirectory() as td:
                project, folder = Path(td), Path(td) / "audio"
                lines = [{"shot_id": "S1", "text": "你好", "speed": 1.0}]
                gen = Mock(side_effect=error)
                tts_api.run_lines(lines, folder, generate=gen, gateway=_gateway(), project=project)
                entry = json.loads((folder / "时间轴.json").read_text(encoding="utf-8"))[0]
                self.assertEqual(entry["state"], "uncertain")
                self.assertFalse(entry.get("not_submitted"))
                self.assertEqual(
                    tts_api.run_lines(lines, folder, generate=gen, gateway=_gateway(), project=project),
                    (0, 0, 1))
                self.assertEqual(gen.call_count, 1)

    def test_reset_and_interrupted_read_stay_uncertain(self):
        """连接重置／响应读取中断直达 run_lines：结果未知且不自动重发。"""
        import http.client
        for error in (ConnectionResetError(10054, "reset"), http.client.IncompleteRead(b"partial")):
            with self.subTest(error=error), tempfile.TemporaryDirectory() as td:
                project, folder = Path(td), Path(td) / "audio"
                lines = [{"shot_id": "S1", "text": "你好", "speed": 1.0}]
                gen = Mock(side_effect=error)
                tts_api.run_lines(lines, folder, generate=gen, gateway=_gateway(), project=project)
                entry = json.loads((folder / "时间轴.json").read_text(encoding="utf-8"))[0]
                self.assertEqual(entry["state"], "uncertain")
                self.assertEqual(
                    tts_api.run_lines(lines, folder, generate=gen, gateway=_gateway(), project=project),
                    (0, 0, 1))
                self.assertEqual(gen.call_count, 1)

    def test_reset_after_payment_is_uncertain_not_unsaved(self):
        """网络层 OSError 先于「已付费写盘失败」判定：付费后连接重置仍是结果未知。"""
        with tempfile.TemporaryDirectory() as td:
            project, folder = Path(td), Path(td) / "audio"
            lines = [{"shot_id": "S1", "text": "你好", "speed": 1.0}]
            broken = {**_gateway(), "publish_bytes": Mock(side_effect=ConnectionResetError(10054, "reset"))}
            self.assertEqual(
                tts_api.run_lines(lines, folder, generate=Mock(return_value=b"audio"),
                                  gateway=broken, project=project),
                (0, 0, 1))
            entry = json.loads((folder / "时间轴.json").read_text(encoding="utf-8"))[0]
            self.assertEqual(entry["state"], "uncertain")
            again = Mock(return_value=b"audio")
            self.assertEqual(
                tts_api.run_lines(lines, folder, generate=again, gateway=_gateway(), project=project),
                (0, 0, 1))
            again.assert_not_called()

    def test_unreachable_stays_failed_and_resends(self):
        """连接没建立（refused／DNS 解析失败一类）仍是确定失败：记 failed，允许自动重发。"""
        import socket
        errors = (
            urllib.error.URLError("connection refused"),
            urllib.error.URLError(ConnectionRefusedError(111, "Connection refused")),
            urllib.error.URLError(socket.gaierror(-2, "Name or service not known")),
        )
        for error in errors:
            with self.subTest(error=error), tempfile.TemporaryDirectory() as td:
                project, folder = Path(td), Path(td) / "audio"
                lines = [{"shot_id": "S1", "text": "你好", "speed": 1.0}]
                gen = Mock(side_effect=error)
                tts_api.run_lines(lines, folder, generate=gen, gateway=_gateway(), project=project)
                entry = json.loads((folder / "时间轴.json").read_text(encoding="utf-8"))[0]
                self.assertEqual(entry["state"], "failed")
                self.assertTrue(entry.get("not_submitted"))
                gen.side_effect = None
                gen.return_value = b"audio"
                self.assertEqual(
                    tts_api.run_lines(lines, folder, generate=gen, gateway=_gateway(), project=project),
                    (1, 0, 0))
                self.assertEqual(gen.call_count, 2)

    def _manifest_with_states(self, folder, lines, states):
        folder.mkdir(parents=True, exist_ok=True)
        entries = [{**line, "state": state, "file": "", "request_id": "rid-%d" % index}
                   for index, (line, state) in enumerate(zip(lines, states), 1)]
        (folder / "时间轴.json").write_text(json.dumps(entries), encoding="utf-8")

    def test_release_prompt_uncertain_lines_keep_checked_wording(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            lines = [{"shot_id": "S1", "text": "第一句", "speed": 1.0}]
            self._manifest_with_states(folder, lines, ["uncertain"])
            tip = tts_api.unknown_release_prompt(lines, folder)
            self.assertEqual(tip["indexes"], [1])
            self.assertIn("已核对服务商后台，这些请求没有扣费，重新发送", tip["text"])
            self.assertNotIn("重新发送会再付一次", tip["text"])

    def test_release_prompt_unsaved_lines_tell_repaid_truth(self):
        """unsaved 句已付费：放开文案如实说明重发会再付一次，不说「没有扣费」。"""
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            lines = [{"shot_id": "S1", "text": "第一句", "speed": 1.0}]
            self._manifest_with_states(folder, lines, ["unsaved"])
            tip = tts_api.unknown_release_prompt(lines, folder)
            self.assertEqual(tip["indexes"], [1])
            self.assertIn("这些句子上次已付费但没有保存成功，重新发送会再付一次", tip["text"])
            self.assertNotIn("这些请求没有扣费", tip["text"])
            self.assertIn("S1", tip["text"])
            self.assertIn("rid-1", tip["text"])

    def test_release_prompt_mixed_batch_groups_each_state(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            lines = [{"shot_id": "S1", "text": "第一句", "speed": 1.0},
                     {"shot_id": "S2", "text": "第二句", "speed": 1.0},
                     {"shot_id": "S3", "text": "第三句", "speed": 1.0}]
            self._manifest_with_states(folder, lines, ["sending", "uncertain", "unsaved"])
            tip = tts_api.unknown_release_prompt(lines, folder)
            self.assertEqual(tip["indexes"], [1, 2, 3])
            self.assertIn("已核对服务商后台，这些请求没有扣费，重新发送", tip["text"])
            self.assertIn("这些句子上次已付费但没有保存成功，重新发送会再付一次", tip["text"])
            unknown_part, unsaved_part = tip["text"].split("已付费但没有保存成功", 1)
            self.assertIn("S1", unknown_part)
            self.assertIn("S2", unknown_part)
            self.assertNotIn("S3", unknown_part)
            self.assertIn("S3", unsaved_part)
            self.assertNotIn("S1", unsaved_part)

    def test_publish_failure_marks_unsaved_and_blocks_resend(self):
        with tempfile.TemporaryDirectory() as td:
            project, folder = Path(td), Path(td) / "audio"
            lines = [{"shot_id": "S1", "text": "你好", "speed": 1.0}]
            gateway = _gateway()
            broken = {**gateway, "publish_bytes": Mock(side_effect=OSError("disk full"))}
            self.assertEqual(
                tts_api.run_lines(lines, folder, generate=lambda *a, **k: b"audio",
                                  gateway=broken, project=project),
                (0, 0, 1))
            entry = json.loads((folder / "时间轴.json").read_text(encoding="utf-8"))[0]
            self.assertEqual(entry["state"], "unsaved")
            self.assertIn("已付费未保存", entry.get("error", ""))
            quote = tts_api.batch_cost_preview(project, lines, folder)
            self.assertEqual((quote["pending"], quote["unknown"]), ([], 1))
            again = Mock(return_value=b"audio")
            self.assertEqual(
                tts_api.run_lines(lines, folder, generate=again, gateway=_gateway(), project=project),
                (0, 0, 1))
            again.assert_not_called()

    def test_release_unknown_only_resends_released_indexes(self):
        with tempfile.TemporaryDirectory() as td:
            project, folder = Path(td), Path(td) / "audio"
            lines = [
                {"shot_id": "S1", "text": "第一句", "speed": 1.0},
                {"shot_id": "S2", "text": "第二句", "speed": 1.0},
            ]
            folder.mkdir(parents=True)
            manifest = [
                {**lines[0], "state": "uncertain", "file": "", "request_id": "a"},
                {**lines[1], "state": "sending", "file": "", "request_id": "b"},
            ]
            (folder / "时间轴.json").write_text(json.dumps(manifest), encoding="utf-8")
            released = tts_api.release_unknown(folder, [1], gateway=_gateway())
            self.assertEqual(released, [1])
            data = json.loads((folder / "时间轴.json").read_text(encoding="utf-8"))
            self.assertEqual(data[0]["state"], "failed")
            self.assertIn("released_at", data[0])
            self.assertEqual(data[1]["state"], "sending")
            calls = []
            def generate(text, speed=1.0, voice=None):
                calls.append(text)
                return b"x"
            self.assertEqual(
                tts_api.run_lines(lines, folder, generate=generate, gateway=_gateway(), project=project),
                (1, 0, 1))
            self.assertEqual(calls, ["第一句"])


class TtsRecoveryIdentityTests(unittest.TestCase):
    def test_run_lines_records_shared_run_attempt_and_cost_request(self):
        lines = [{"shot_id": "S1", "text": "第一句", "speed": 1.0},
                 {"shot_id": "S1", "text": "第二句", "speed": 1.0}]
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            self.assertEqual(tts_api.run_lines(lines, folder, generate=lambda *a, **k: b"audio",
                                               gateway=_gateway()), (2, 0, 0))
            manifest = json.loads((folder / "时间轴.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest), 2)
        runs = {entry["execution"]["run_id"] for entry in manifest}
        self.assertEqual(len(runs), 1)
        self.assertNotEqual(manifest[0]["execution"]["attempt_id"], manifest[1]["execution"]["attempt_id"])
        for index, entry in enumerate(manifest, 1):
            self.assertEqual(entry["execution"]["attempt_id"], entry["request_id"])
            self.assertEqual(entry["cost_request_id"], entry["request_id"])
            self.assertEqual(entry["execution"]["task_id"], "S1#%03d" % index)

    def test_key_account_switch_invalidates_sentence_cache(self):
        entries = [("S1", "CHAR_001", "你好", 1.0, 2.0)]
        settings_a = {"base_url": "https://a.example/v1", "model": "tts-a", "voice": "alloy",
                      "key_account": "account-a"}
        settings_b = dict(settings_a, key_account="account-b")
        lines_a = tts_api.build_lines(entries, {}, settings=settings_a)
        lines_b = tts_api.build_lines(entries, {}, settings=settings_b)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "配音分句"
            folder = root / "批一"
            tts_api.run_lines(lines_a, folder, generate=lambda *a, **k: b"audio", gateway=_gateway())
            stored = json.loads((folder / "时间轴.json").read_text(encoding="utf-8"))[0]
            self.assertEqual(stored["key_account"], "account-a")
            self.assertEqual(tts_api.pending_lines(lines_a, folder), [])
            self.assertEqual(tts_api.pending_lines(lines_b, folder), [1])
            self.assertIsNone(tts_api.resume_folder(root, lines_b))

    def test_unmarked_legacy_success_is_not_resent_after_account_marking(self):
        entries = [("S1", "CHAR_001", "你好", 1.0, 2.0)]
        settings_legacy = {"base_url": "https://a.example/v1", "model": "tts-a", "voice": "alloy"}
        settings_marked = dict(settings_legacy, key_account="account-a")
        legacy = tts_api.build_lines(entries, {}, settings=settings_legacy)
        marked = tts_api.build_lines(entries, {}, settings=settings_marked)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "配音分句"
            folder = root / "配音批次_20260101"
            tts_api.run_lines(legacy, folder, generate=lambda *a, **k: b"audio", gateway=_gateway())
            self.assertEqual(tts_api.resume_folder(root, marked), folder)
            self.assertEqual(tts_api.pending_lines(marked, folder), [])
            generate = Mock(return_value=b"audio")
            self.assertEqual(tts_api.run_lines(marked, folder, generate=generate, gateway=_gateway()), (1, 1, 0))
            generate.assert_not_called()

    def test_save_key_keeps_random_account_only_for_same_key(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "tts_settings.json"
            seen = []
            with patch.object(tts_api, "settings_path", return_value=path), \
                 patch.object(tts_api, "load_key", return_value=""), \
                 patch("model_pool.save_named_key", lambda name, value: seen.append((name, value))):
                tts_api.save_key("https://api.openai.com/v1", "tts-1", "alloy", "sk-one", gateway=_gateway())
            first = json.loads(path.read_text(encoding="utf-8"))["key_account"]
            with patch.object(tts_api, "settings_path", return_value=path), \
                 patch.object(tts_api, "load_key", return_value="sk-one"), \
                 patch("model_pool.save_named_key", lambda name, value: seen.append((name, value))):
                tts_api.save_key("https://api.openai.com/v1", "tts-1", "alloy", "sk-one", gateway=_gateway())
            same = json.loads(path.read_text(encoding="utf-8"))["key_account"]
            with patch.object(tts_api, "settings_path", return_value=path), \
                 patch.object(tts_api, "load_key", return_value="sk-one"), \
                 patch("model_pool.save_named_key", lambda name, value: seen.append((name, value))):
                tts_api.save_key("https://api.openai.com/v1", "tts-1", "alloy", "sk-two", gateway=_gateway())
            stored_text = path.read_text(encoding="utf-8")
            changed = json.loads(stored_text)["key_account"]
        self.assertEqual(first, same)
        self.assertNotEqual(first, changed)
        self.assertNotIn("sk-one", stored_text)
        self.assertNotIn("sk-two", stored_text)
        self.assertEqual([key for key, _value in seen], [tts_api.KEY_ENV] * 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
