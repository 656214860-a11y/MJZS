# -*- coding: utf-8 -*-
"""离线语音引擎（voice_engine）协议、分句与模型下载解析测试。

全部使用假 VAD/ASR/PUNC 与假 modelscope，不下载真实模型、不依赖第三方包，
可在随附零依赖解释器下运行。
"""

import base64
import contextlib
import importlib
import io
import json
import os
import struct
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

PROGRAM = Path(__file__).resolve().parents[1]
if str(PROGRAM) not in sys.path:
    sys.path.insert(0, str(PROGRAM))

from voice_engine import offline_asr_server as srv  # noqa: E402
from voice_engine import download_models, bootstrap  # noqa: E402

BYTES_PER_MS = srv.BYTES_PER_MS


def pcm_ms(ms, voiced=False):
    """生成 ms 毫秒的 PCM：voiced=True 为有声（非零字节），否则静音。"""
    fill = b"\x01" if voiced else b"\x00"
    return fill * (ms * BYTES_PER_MS)


def build_pcm(regions):
    """regions: [(start_ms, end_ms, voiced), ...] 按序拼出 PCM。"""
    total = max(end for _, end, _ in regions)
    buf = bytearray(total * BYTES_PER_MS)
    for start, end, voiced in regions:
        if voiced:
            buf[start * BYTES_PER_MS:end * BYTES_PER_MS] = b"\x01" * ((end - start) * BYTES_PER_MS)
    return bytes(buf)


def fake_vad_scan(pcm, sample_rate):
    """按 PCM 非零字节扫描语音段，返回 [[start_ms, end_ms], ...]（相对输入）。"""
    total = len(pcm) // BYTES_PER_MS
    segs = []
    start = None
    for ms in range(total):
        voiced = any(pcm[ms * BYTES_PER_MS:(ms + 1) * BYTES_PER_MS])
        if voiced and start is None:
            start = ms
        elif not voiced and start is not None:
            segs.append([start, ms])
            start = None
    if start is not None:
        segs.append([start, total])
    return segs


class FakeBackend:
    """脚本化后端：vad 真实扫描 PCM，asr 按队列出文本，punc 加句号。"""

    def __init__(self, texts=None):
        self.texts = list(texts or [])
        self.calls = []

    def vad(self, pcm, sample_rate):
        return fake_vad_scan(pcm, sample_rate)

    def asr(self, wav_path, hotword=""):
        self.calls.append((wav_path, hotword))
        return self.texts.pop(0) if self.texts else "识别文本"

    def punc(self, text):
        return text + "。"


class WavAndProtocolTests(unittest.TestCase):
    def test_wav_bytes_header(self):
        pcm = b"\x00\x01" * 160
        wav = srv.wav_bytes(pcm, 16000)
        self.assertEqual(wav[:4], b"RIFF")
        self.assertEqual(wav[8:12], b"WAVE")
        self.assertEqual(struct.unpack("<I", wav[40:44])[0], len(pcm))
        self.assertEqual(wav[44:], pcm)
        # 采样率/声道/位深字段
        self.assertEqual(struct.unpack("<H", wav[22:24])[0], 1)
        self.assertEqual(struct.unpack("<I", wav[24:28])[0], 16000)
        self.assertEqual(struct.unpack("<H", wav[34:36])[0], 16)

    def test_decode_audio_roundtrip_and_invalid(self):
        pcm = b"\x01\x02" * 100
        self.assertEqual(srv._decode_audio(base64.b64encode(pcm).decode()), pcm)
        self.assertEqual(srv._decode_audio(base64.b64encode(pcm)), pcm)
        with self.assertRaises(ValueError):
            srv._decode_audio("!!!not-base64!!!")
        with self.assertRaises(ValueError):
            srv._decode_audio(123)

    def test_iter_segment_pairs_nested(self):
        self.assertEqual(list(srv._iter_segment_pairs([[[0, 500], [600, 900]]])),
                         [(0, 500), (600, 900)])
        self.assertEqual(list(srv._iter_segment_pairs([[1000, 2000]])),
                         [(1000, 2000)])
        self.assertEqual(list(srv._iter_segment_pairs([])), [])

    def test_pcm_session_slice_and_ms(self):
        session = srv.PcmSession(16000)
        session.feed(pcm_ms(1500))
        self.assertEqual(session.total_ms, 1500)
        self.assertEqual(len(session.pcm_slice(500, 1000)), 500 * BYTES_PER_MS)
        self.assertEqual(session.pcm_slice(0, 100)[:2], b"\x00\x00")

    def test_parse_line(self):
        self.assertEqual(srv._parse_line('{"cmd":"stop"}'), {"cmd": "stop"})
        self.assertEqual(srv._parse_line("  \n"), {})
        self.assertIn("_invalid", srv._parse_line("not json"))
        self.assertIn("_invalid", srv._parse_line("[1,2]"))
        self.assertIn("_invalid", srv._parse_line("x" * (srv.MAX_LINE_BYTES + 1)))

    def test_zh_error_maps_import_error(self):
        msg = srv._zh_error("模型加载失败", ImportError("No module named 'numpy'"))
        self.assertIn("依赖", msg)
        self.assertIn("bootstrap", msg)
        msg2 = srv._zh_error("命令处理失败", RuntimeError("自定义错误"))
        self.assertIn("自定义错误", msg2)

    def test_emit_message_json_line(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            srv.emit_message({"type": "done"})
        self.assertEqual(json.loads(buf.getvalue().strip()), {"type": "done"})


class SegmenterTests(unittest.TestCase):
    def _session_with(self, regions):
        session = srv.PcmSession(16000)
        session.feed(build_pcm(regions))
        return session

    def _segmenter(self, texts=None, **kwargs):
        backend = FakeBackend(texts)
        return srv.Segmenter(backend.vad, backend.asr, backend.punc,
                             log_fn=lambda _m: None, **kwargs), backend

    def test_sentence_emitted_after_trailing_silence(self):
        # 有声 1000-2000ms，尾随静音到 2600ms（>TRAILING 500）→ 立即出句
        session = self._session_with([(0, 1000, False), (1000, 2000, True),
                                      (2000, 2600, False)])
        seg, _ = self._segmenter(["你好世界"])
        events = seg.poll(session)
        self.assertEqual(len(events), 1)
        ev = events[0]
        self.assertEqual(ev["text"], "你好世界。")
        self.assertEqual((ev["start_ms"], ev["end_ms"]), (1000, 2000))
        self.assertEqual(session.processed_ms, 2000)
        # 再 poll 不重复产出
        self.assertEqual(seg.poll(session), [])

    def test_not_ready_until_trailing_silence(self):
        # 有声段末尾紧贴音频末尾 → 未稳定不出句；补 500ms 静音后出句
        session = self._session_with([(0, 1000, False), (1000, 2000, True)])
        seg, _ = self._segmenter(["第一句"])
        self.assertEqual(seg.poll(session), [])
        session.feed(pcm_ms(500))  # total=2500, limit=2000 → 段尾 2000 达标
        events = seg.poll(session)
        self.assertEqual([e["text"] for e in events], ["第一句。"])

    def test_final_flushes_without_trailing(self):
        session = self._session_with([(0, 1000, False), (1000, 2000, True)])
        seg, _ = self._segmenter(["收尾句"])
        events = seg.poll(session, final=True)
        self.assertEqual([e["text"] for e in events], ["收尾句。"])
        self.assertEqual(session.processed_ms, 2000)

    def test_two_sentences_order_and_dedup(self):
        regions = [(0, 500, False), (500, 1500, True), (1500, 2500, False),
                   (2500, 3500, True), (3500, 4200, False)]
        session = self._session_with(regions)
        seg, _ = self._segmenter(["第一句", "第二句"])
        events = seg.poll(session)
        self.assertEqual([e["text"] for e in events], ["第一句。", "第二句。"])
        self.assertEqual([(e["start_ms"], e["end_ms"]) for e in events],
                         [(500, 1500), (2500, 3500)])
        self.assertEqual(session.processed_ms, 3500)
        self.assertEqual(seg.poll(session), [])

    def test_short_segment_skipped_and_processed_advances(self):
        # 100ms 短段 < MIN_SENTENCE_MS(200) → 丢弃但推进进度
        session = self._session_with([(0, 100, True), (100, 800, False)])
        seg, backend = self._segmenter(["不应出现"])
        self.assertEqual(seg.poll(session, final=True), [])
        self.assertEqual(backend.calls, [])
        self.assertEqual(session.processed_ms, 100)

    def test_empty_asr_result_advances_without_event(self):
        session = self._session_with([(0, 500, False), (500, 1500, True),
                                      (1500, 2200, False)])
        seg, _ = self._segmenter([""])
        self.assertEqual(seg.poll(session), [])
        self.assertEqual(session.processed_ms, 1500)

    def test_punc_failure_tolerated(self):
        session = self._session_with([(0, 500, False), (500, 1500, True),
                                      (1500, 2200, False)])
        backend = FakeBackend(["文本"])
        backend.punc = lambda _t: (_ for _ in ()).throw(RuntimeError("punc bad"))
        seg = srv.Segmenter(backend.vad, backend.asr, backend.punc,
                            log_fn=lambda _m: None)
        events = seg.poll(session)
        self.assertEqual(events[0]["text"], "文本")

    def test_session_hotword_reaches_asr_fn(self):
        session = srv.PcmSession(16000, hotword="漫剧 子进程")
        session.feed(build_pcm([(0, 500, False), (500, 1500, True),
                                (1500, 2200, False)]))
        seg, backend = self._segmenter(["你好"])
        seg.poll(session)
        self.assertEqual(len(backend.calls), 1)
        self.assertEqual(backend.calls[0][1], "漫剧 子进程")
        self.assertTrue(backend.calls[0][0].endswith(".wav"))

    def test_window_clipping_logs_and_caps(self):
        session = self._session_with([(i * 100, i * 100 + 50, True)
                                      for i in range(30)])
        logs = []
        seg, _ = self._segmenter([], window_ms=1000, min_ms=10, max_ms=60000)
        seg.log_fn = logs.append
        seg.poll(session, final=True)
        self.assertTrue(seg._window_clipped)
        self.assertTrue(any("截断" in m for m in logs))


class OfflineAsrEngineTests(unittest.TestCase):
    def _engine(self, texts=None):
        return srv.OfflineAsrEngine(FakeBackend(texts))

    def test_feed_and_stop_protocol_events(self):
        engine = self._engine(["你好"])
        engine.open_session(16000, "热词")
        emitted = []
        pcm = build_pcm([(0, 500, False), (500, 1500, True), (1500, 2300, False)])
        engine.feed(base64.b64encode(pcm).decode(), emitted.append)
        self.assertEqual([e["type"] for e in emitted], ["sentence"])
        self.assertEqual(emitted[0]["text"], "你好。")
        engine.stop(emitted.append)
        self.assertEqual(emitted[-1], {"type": "done"})

    def test_feed_without_session_raises(self):
        engine = self._engine()
        with self.assertRaises(RuntimeError):
            engine.feed("", lambda _e: None)

    def test_audio_after_stop_raises(self):
        engine = self._engine()
        engine.open_session(16000)
        emitted = []
        engine.stop(emitted.append)
        with self.assertRaises(RuntimeError):
            engine.feed("", emitted.append)

    def test_non_16k_rejected(self):
        engine = self._engine()
        with self.assertRaises(ValueError):
            engine.open_session(48000)

    def test_invalid_base64_surfaces_error(self):
        engine = self._engine()
        engine.open_session(16000)
        with self.assertRaises(ValueError):
            engine.feed("!!!", lambda _e: None)

    def test_cancel_discards_session_without_done(self):
        engine = self._engine(["你好"])
        engine.open_session(16000)
        emitted = []
        pcm = build_pcm([(0, 500, False), (500, 1500, True), (1500, 2300, False)])
        engine.feed(base64.b64encode(pcm).decode(), emitted.append)
        engine.cancel_session(emitted.append)
        self.assertEqual(emitted[-1]["type"], "log")
        self.assertNotIn("done", [e["type"] for e in emitted])
        with self.assertRaises(RuntimeError):
            engine.feed("", emitted.append)

    def test_vad_overrides_reach_segmenter(self):
        engine = srv.OfflineAsrEngine(FakeBackend())
        engine.open_session(16000, vad={"trailing_ms": 50, "min_ms": 300,
                                        "bogus": 9, "tick_ms": "x"})
        self.assertEqual(engine.segmenter.trailing_ms, 50)
        self.assertEqual(engine.segmenter.min_ms, 300)
        self.assertEqual(engine.segmenter.tick_ms, srv.VAD_TICK_MS)
        self.assertEqual(engine.segmenter.max_ms, srv.MAX_SENTENCE_MS)


class FunAsrBackendTests(unittest.TestCase):
    def test_asr_result_parsing_onnx_and_torch(self):
        backend = srv.FunAsrBackend(cache_root=tempfile.mkdtemp())
        backend.asr_model = lambda _paths: [{"preds": ("onnx文本", ["t"])}]
        self.assertEqual(backend.asr("x.wav"), "onnx文本")
        backend.asr_model = lambda _paths: [{"text": "torch文本"}]
        self.assertEqual(backend.asr("x.wav"), "torch文本")
        backend.asr_model = lambda _paths: []
        self.assertEqual(backend.asr("x.wav"), "")

    def test_hotword_forwarded_only_to_capable_model(self):
        backend = srv.FunAsrBackend(cache_root=tempfile.mkdtemp())
        seen = {}

        class Contextual:
            proc_hotword = object()

            def __call__(self, paths, **kwargs):
                seen.update(kwargs)
                return [{"text": "文本"}]

        backend.asr_model = Contextual()
        self.assertEqual(backend.asr("x.wav", hotword="漫剧 子进程"), "文本")
        self.assertEqual(seen, {"hotwords": "漫剧 子进程"})

        # 普通模型：不带 proc_hotword → 不传热词，stderr 留一条诊断，识别照常
        backend2 = srv.FunAsrBackend(cache_root=tempfile.mkdtemp())
        backend2.asr_model = lambda paths: [{"text": "普通"}]
        with mock.patch("sys.stderr") as stderr:
            self.assertEqual(backend2.asr("x.wav", hotword="热词"), "普通")
            self.assertTrue(any("热词" in str(call) for call in stderr.write.call_args_list))
        self.assertEqual(backend2.asr("x.wav", hotword="热词"), "普通")

    def test_hotword_typeerror_falls_back_without_kwarg(self):
        backend = srv.FunAsrBackend(cache_root=tempfile.mkdtemp())
        calls = []

        class Picky:
            proc_hotword = object()

            def __call__(self, paths, **kwargs):
                calls.append(kwargs)
                if kwargs:
                    raise TypeError("unexpected keyword 'hotwords'")
                return [{"text": "回退文本"}]

        backend.asr_model = Picky()
        self.assertEqual(backend.asr("x.wav", hotword="热词"), "回退文本")
        self.assertEqual(calls, [{"hotwords": "热词"}, {}])

    def test_punc_tuple_parsing(self):
        backend = srv.FunAsrBackend(cache_root=tempfile.mkdtemp())
        backend.punc_model = lambda _t: ("带标点。", ["p"])
        self.assertEqual(backend.punc("原文"), "带标点。")

    def test_vad_writes_temp_wav_and_returns_raw(self):
        backend = srv.FunAsrBackend(cache_root=tempfile.mkdtemp())
        seen = {}

        def fake_vad_model(path):
            seen["path"] = path
            with open(path, "rb") as handle:
                seen["wav"] = handle.read()
            return [[[0, 500]]]

        backend.vad_model = fake_vad_model
        pcm = pcm_ms(1000)
        result = backend.vad(pcm, 16000)
        self.assertEqual(result, [[[0, 500]]])
        self.assertTrue(seen["wav"].startswith(b"RIFF"))
        self.assertEqual(len(seen["wav"]) - 44, len(pcm))
        # 临时目录已被清理
        self.assertFalse(os.path.exists(os.path.dirname(seen["path"])))

    def test_model_dir_uses_cache_root(self):
        backend = srv.FunAsrBackend(cache_root="D:/cache/root")
        with mock.patch.object(download_models, "get_model_cache_path",
                               return_value="D:/m") as patched:
            self.assertEqual(backend._model_dir("asr"), "D:/m")
            patched.assert_called_once_with(
                backend.model_names["asr"], backend.revision, "D:/cache/root")


class GetModelCachePathTests(unittest.TestCase):
    def test_fast_path_hits_local_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            model_dir = (Path(tmp) / "hub" / "models" / "iic" / "test-model")
            model_dir.mkdir(parents=True)
            (model_dir / "model.onnx").write_bytes(b"onnx")
            got = download_models.get_model_cache_path(
                "iic/test-model", "v2.0.5", cache_root=tmp)
            self.assertEqual(got, str(model_dir))
            self.assertEqual(os.environ.get("MODELSCOPE_CACHE"), tmp)

    def _fake_modelscope(self, behavior):
        """注入假 modelscope.hub.snapshot_download；behavior(**kw)->path 或抛错。"""
        calls = []

        def snapshot_download(model, revision=None, local_files_only=False, **kw):
            calls.append({"model": model, "revision": revision,
                          "local_files_only": local_files_only})
            return behavior(model, revision, local_files_only)

        pkg = types.ModuleType("modelscope")
        hub = types.ModuleType("modelscope.hub")
        sd = types.ModuleType("modelscope.hub.snapshot_download")
        sd.snapshot_download = snapshot_download
        hub.snapshot_download = sd
        pkg.hub = hub
        return {"modelscope": pkg, "modelscope.hub": hub,
                "modelscope.hub.snapshot_download": sd}, calls

    def test_offline_hit_then_online_fallback(self):
        modules, calls = self._fake_modelscope(
            lambda model, rev, local: (_ for _ in ()).throw(RuntimeError("offline miss"))
            if local else "D:/downloaded/model")
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.dict(sys.modules, modules):
            got = download_models.get_model_cache_path(
                "iic/other-model", "v9", cache_root=tmp)
        self.assertEqual(got, "D:/downloaded/model")
        self.assertEqual([c["local_files_only"] for c in calls], [True, False])
        self.assertEqual(calls[0]["revision"], "v9")

    def test_local_files_only_success_no_online(self):
        modules, calls = self._fake_modelscope(
            lambda model, rev, local: "D:/cached/model")
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.dict(sys.modules, modules):
            got = download_models.get_model_cache_path(
                "iic/other-model", "v2.0.5", cache_root=tmp)
        self.assertEqual(got, "D:/cached/model")
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0]["local_files_only"])


class BootstrapTests(unittest.TestCase):
    def test_venv_python_windows_and_posix(self):
        with mock.patch.object(os, "name", "nt"):
            self.assertTrue(bootstrap.venv_python("V").endswith(
                os.path.join("Scripts", "python.exe")))
        with mock.patch.object(os, "name", "posix"):
            self.assertTrue(bootstrap.venv_python("V").endswith(
                os.path.join("bin", "python")))

    def test_version_tuple(self):
        self.assertEqual(bootstrap._version_tuple("3.14.2"), (3, 14))
        self.assertEqual(bootstrap._version_tuple("bad"), (0, 0))

    def test_main_bad_base_python_returns_env_error(self):
        with mock.patch.object(bootstrap, "probe_python",
                               return_value=(False, "", "找不到解释器")):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = bootstrap.main(["--python", "nonexistent-python"])
        self.assertEqual(code, bootstrap.EXIT_ENV_ERROR)
        self.assertEqual(json.loads(buf.getvalue().strip())["type"], "error")

    def test_main_rejects_python_above_max(self):
        with mock.patch.object(bootstrap, "probe_python",
                               return_value=(True, "3.14.7", "")):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = bootstrap.main(["--python", "too-new-python"])
        self.assertEqual(code, bootstrap.EXIT_ENV_ERROR)
        payload = json.loads(buf.getvalue().strip().splitlines()[-1])
        self.assertEqual(payload["type"], "error")
        self.assertIn("3.10", payload["message"])

    def test_ensure_pip_runs_ensurepip_when_missing(self):
        responses = iter([
            types.SimpleNamespace(returncode=1, stdout="", stderr=""),   # pip --version 失败
            types.SimpleNamespace(returncode=0, stdout="", stderr=""),   # ensurepip 成功
            types.SimpleNamespace(returncode=0, stdout="pip 24", stderr=""),  # pip --version 成功
        ])
        with mock.patch.object(bootstrap, "_run",
                               side_effect=lambda *a, **k: next(responses)):
            self.assertIsNone(bootstrap.ensure_pip("py"))

    def test_ensure_pip_fails_without_ensurepip(self):
        responses = iter([
            types.SimpleNamespace(returncode=1, stdout="", stderr=""),
            types.SimpleNamespace(returncode=1, stdout="", stderr="no ensurepip"),
        ])
        with mock.patch.object(bootstrap, "_run",
                               side_effect=lambda *a, **k: next(responses)):
            err = bootstrap.ensure_pip("py")
        self.assertIn("pip", err)


if __name__ == "__main__":
    unittest.main()
