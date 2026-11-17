#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""离线语音识别引擎：独立子进程，经 stdio JSON Lines 与主程序通信。

协议（任务书 §4.1）：
  主程序 -> 引擎（逐行 JSON，音频 base64 分块）：
    {"cmd":"start","sample_rate":16000,"hotword":"..."}
    {"cmd":"audio","data":"<base64 pcm>"} / {"cmd":"stop"} / {"cmd":"cancel"} / {"cmd":"shutdown"}
  引擎 -> 主程序：
    {"type":"ready",...}   模型加载完成（进程启动后发一次）
    {"type":"log","message":"..."}   进度/诊断（可选）
    {"type":"sentence","text":"...","start_ms":n,"end_ms":n}
    {"type":"done"}       stop 处理完毕
    {"type":"error","message":"中文原因"}

音频：16kHz/16bit/mono PCM。FSMN-VAD 对 PCM 尾段逐句断句，每句 Paraformer
ASR + CT-punc 后立即下发；模型常驻内存，进程常驻。第三方依赖全部函数内延迟
导入，本文件顶部只用标准库，主程序零依赖边界不被穿透。
"""

import base64
import binascii
import json
import os
import struct
import sys
import tempfile
import time
import traceback

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from voice_engine import funasr_config, download_models  # noqa: E402

# ---- 协议与音频常量 ----
SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2
BYTES_PER_MS = SAMPLE_RATE * SAMPLE_WIDTH // 1000  # 32
MAX_LINE_BYTES = 8 * 1024 * 1024                    # 单行命令上限（约 6MB 音频）

# ---- 分句参数 ----
VAD_TICK_MS = 300        # 两次 VAD 轮询的最小新音频间隔
TRAILING_MS = 500        # 句末需保留的尾随静音，保证 VAD 分句稳定
VAD_WINDOW_MS = 120000   # 单次 VAD 分析窗口上限（超长未停顿语音截断保护）
MIN_SENTENCE_MS = 200    # 短于该时长的段视为噪声丢弃
MAX_SENTENCE_MS = 60000  # 超长段截断保护
MODEL_LOAD_TIMEOUT = 300  # 模型加载线程 join 超时（秒）

EXIT_OK = 0
EXIT_MODEL_ERROR = 2
EXIT_FATAL = 3


def emit_message(obj):
    """向 stdout 写一行 JSON（stdout 即 IPC 通道，不用 print 诊断）。"""
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _configure_stdio():
    """stdio 固定 UTF-8：主程序按 UTF-8 解码 JSON-Lines，中文 Windows 默认 GBK 会乱码。"""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError, LookupError):
            pass


def _emit_log(message):
    emit_message({"type": "log", "message": str(message)})


def wav_bytes(pcm: bytes, sample_rate: int = SAMPLE_RATE) -> bytes:
    """手写 44 字节 RIFF/WAVE 头（不依赖标准库 wave，兼容裁剪运行时）。"""
    data_size = len(pcm)
    byte_rate = sample_rate * CHANNELS * SAMPLE_WIDTH
    block_align = CHANNELS * SAMPLE_WIDTH
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + data_size, b"WAVE",
        b"fmt ", 16, 1, CHANNELS, sample_rate,
        byte_rate, block_align, SAMPLE_WIDTH * 8,
        b"data", data_size,
    )
    return header + pcm


def _decode_audio(data) -> bytes:
    """base64 字符串/字节 -> PCM bytes；非法输入抛 ValueError（中文原因）。"""
    if isinstance(data, str):
        raw = data.encode("ascii", "ignore")
    elif isinstance(data, (bytes, bytearray)):
        raw = bytes(data)
    else:
        raise ValueError("音频数据必须是 base64 字符串")
    try:
        return base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("音频数据 base64 解码失败") from exc


def _iter_segment_pairs(node):
    """递归提取 [start_ms, end_ms] 数值对（兼容 funasr_onnx 多层嵌套返回）。"""
    if isinstance(node, (list, tuple)):
        if (len(node) == 2
                and all(isinstance(v, (int, float)) and not isinstance(v, bool)
                        for v in node)):
            yield (node[0], node[1])
            return
        for child in node:
            yield from _iter_segment_pairs(child)


def pcm_to_temp_wav(pcm: bytes, sample_rate: int, tmpdir: str) -> str:
    """把 PCM 写成临时 WAV 文件并返回路径（调用方负责目录生命周期）。"""
    path = os.path.join(tmpdir, "segment.wav")
    with open(path, "wb") as handle:
        handle.write(wav_bytes(pcm, sample_rate))
    return path


class PcmSession:
    """一段听写会话的 PCM 缓冲与已处理进度（毫秒制）。"""

    __slots__ = ("sample_rate", "buf", "processed_ms", "hotword", "active")

    def __init__(self, sample_rate=SAMPLE_RATE, hotword=""):
        self.sample_rate = int(sample_rate)
        self.buf = bytearray()
        self.processed_ms = 0
        self.hotword = hotword or ""
        self.active = True

    @property
    def bytes_per_ms(self):
        return self.sample_rate * SAMPLE_WIDTH // 1000

    @property
    def total_ms(self):
        return len(self.buf) // self.bytes_per_ms

    def feed(self, pcm: bytes):
        self.buf += pcm

    def pcm_slice(self, start_ms, end_ms) -> bytes:
        per = self.bytes_per_ms
        return bytes(self.buf[int(start_ms * per):int(end_ms * per)])


class Segmenter:
    """流式 VAD 分句器：尾段交 VAD、稳定段送 ASR+标点、产出句子事件。

    ``vad_fn(pcm_bytes, sample_rate)`` 返回 VAD 原始分段（任意嵌套层级均可）；
    ``asr_fn(wav_path)`` 返回识别文本；``punc_fn(text)`` 返回带标点文本（可为 None）。
    全部注入，便于用假模型做协议级单测。
    """

    def __init__(self, vad_fn, asr_fn, punc_fn=None, *, tick_ms=VAD_TICK_MS,
                 trailing_ms=TRAILING_MS, window_ms=VAD_WINDOW_MS,
                 min_ms=MIN_SENTENCE_MS, max_ms=MAX_SENTENCE_MS,
                 log_fn=None):
        self.vad_fn = vad_fn
        self.asr_fn = asr_fn
        self.punc_fn = punc_fn
        self.tick_ms = tick_ms
        self.trailing_ms = trailing_ms
        self.window_ms = window_ms
        self.min_ms = min_ms
        self.max_ms = max_ms
        self.log_fn = log_fn or (lambda _msg: None)
        self._last_vad_total_ms = -10 ** 9
        self._window_clipped = False

    def poll(self, session: PcmSession, *, final=False):
        """轮询一次，返回本次新产出的句子 ``[{"text","start_ms","end_ms"}]``。"""
        total = session.total_ms
        unprocessed = total - session.processed_ms
        if unprocessed <= 0:
            return []
        if not final:
            if unprocessed < self.trailing_ms + self.tick_ms:
                return []
            if total - self._last_vad_total_ms < self.tick_ms:
                return []
        proc = session.processed_ms
        if total - proc > self.window_ms:
            vad_from = total - self.window_ms
            if not self._window_clipped:
                self._window_clipped = True
                self.log_fn("单段音频超过 %d 秒，超长句可能被截断"
                            % (self.window_ms // 1000))
        else:
            vad_from = proc
        pcm = session.pcm_slice(vad_from, total)
        self._last_vad_total_ms = total
        raw = self.vad_fn(pcm, session.sample_rate)
        segments = self._normalize(raw, vad_from, total)
        ready_limit = total if final else total - self.trailing_ms
        out = []
        for start, end in segments:
            emit_start = max(start, session.processed_ms)
            emit_end = min(end, total)
            if emit_end <= session.processed_ms:
                continue
            if emit_end > ready_limit:
                continue
            if emit_end - emit_start < self.min_ms:
                session.processed_ms = max(session.processed_ms, emit_end)
                continue
            if emit_end - emit_start > self.max_ms:
                emit_end = emit_start + self.max_ms
                self.log_fn("单句超过 %d 秒，已截断" % (self.max_ms // 1000))
            text = self._transcribe(session, emit_start, emit_end)
            session.processed_ms = emit_end
            if text:
                out.append({"text": text, "start_ms": emit_start,
                            "end_ms": emit_end})
        return out

    def _normalize(self, raw, vad_from, total):
        segs = []
        for s_rel, e_rel in _iter_segment_pairs(raw):
            start = vad_from + float(s_rel)
            end = vad_from + float(e_rel)
            start = max(0.0, min(start, total))
            end = max(0.0, min(end, total))
            if end > start:
                segs.append((start, end))
        segs.sort(key=lambda item: item[0])
        return segs

    def _transcribe(self, session: PcmSession, start_ms, end_ms):
        pcm = session.pcm_slice(start_ms, end_ms)
        if not pcm:
            return ""
        with tempfile.TemporaryDirectory(prefix="voice_asr_") as tmpdir:
            wav_path = pcm_to_temp_wav(pcm, session.sample_rate, tmpdir)
            raw_text = self.asr_fn(wav_path, hotword=getattr(session, "hotword", "") or "")
        text = str(raw_text or "").strip()
        if text and self.punc_fn:
            try:
                text = str(self.punc_fn(text) or text).strip()
            except Exception:  # noqa: BLE001 —— 标点失败不阻塞出字
                self.log_fn("标点恢复失败，使用原始文本")
        return text


class FunAsrBackend:
    """加载并持有 FunASR ONNX 模型（仅在独立 ASR 环境内可用）。

    移植自 vocotype-cli ``app/funasr_server.py`` 的成熟点：线程并行加载、
    模型常驻内存、quantize 优先、CPU 默认、``transcription_count`` 每 10 次
    内存清理。模型目录由 ``download_models.get_model_cache_path`` 离线优先解析。
    """

    def __init__(self, model_names=None, revision=None, cache_root=None,
                 device=None, threads=None):
        self.model_names = dict(model_names or {
            key: funasr_config.MODELS[key]["name"] for key in ("asr", "vad", "punc")})
        self.revision = revision or funasr_config.MODEL_REVISION
        self.cache_root = cache_root or download_models.default_cache_root()
        self.device = device or os.environ.get("FUNASR_DEVICE", "cpu")
        self.threads = threads or int(os.environ.get("OMP_NUM_THREADS", "4"))
        self.asr_model = None
        self.vad_model = None
        self.punc_model = None
        self.loaded = False
        self.transcription_count = 0
        self.total_audio_ms = 0

    # ---- 模型加载 ----
    def load(self, progress=None):
        """并行加载 ASR/VAD/PUNC；ASR+VAD 必须成功，PUNC 失败降级为无标点。"""
        if self.loaded:
            return
        import threading

        self._preimport_funasr()
        if progress:
            progress("正在准备语音模型（首次使用需从 ModelScope 下载约 500MB，"
                     "缓存目录：%s）" % self.cache_root)
        results = {}

        def worker(name, func):
            start = time.time()
            try:
                results[name] = func()
            except Exception as exc:  # noqa: BLE001
                results[name] = exc
            if progress:
                progress("模型 %s 加载完成（%.1f 秒）" % (name, time.time() - start))

        jobs = [("asr", self._load_asr_model), ("vad", self._load_vad_model)]
        if os.environ.get("FUNASR_USE_PUNC", "true").lower() not in ("0", "false", "no"):
            jobs.append(("punc", self._load_punc_model))
        threads = [threading.Thread(target=worker, args=job, daemon=True)
                   for job in jobs]
        for thread in threads:
            thread.start()
        deadline = time.time() + MODEL_LOAD_TIMEOUT
        for thread in threads:
            thread.join(max(0.0, deadline - time.time()))
        stuck = [t.name for t in threads if t.is_alive()]
        if stuck:
            raise RuntimeError("模型加载超时（超过 %d 秒）" % MODEL_LOAD_TIMEOUT)

        failed = [name for name, res in results.items()
                  if isinstance(res, Exception) or res is False]
        required_failed = [name for name in ("asr", "vad")
                           if name in failed]
        if required_failed:
            first = results[required_failed[0]]
            detail = first if isinstance(first, Exception) else "模型文件不完整"
            raise RuntimeError("以下模型加载失败：%s（%s）"
                               % ("、".join(required_failed), detail))
        if "punc" in failed:
            detail = results["punc"]
            if progress:
                progress("标点模型不可用，将不使用标点恢复：%s" % detail)
        self.loaded = True

    @staticmethod
    def _preimport_funasr():
        """预导入 funasr_onnx 子模块，避免多线程导入 ModuleLock 死锁。"""
        try:
            import funasr_onnx.utils.utils  # noqa: F401
            import funasr_onnx.utils.frontend  # noqa: F401
            import funasr_onnx.paraformer_bin  # noqa: F401
            import funasr_onnx.vad_bin  # noqa: F401
            import funasr_onnx.punc_bin  # noqa: F401
        except Exception:  # noqa: BLE001 —— 预导入失败不阻塞，交给加载线程报错
            pass

    def _model_dir(self, key):
        return download_models.get_model_cache_path(
            self.model_names[key], self.revision, self.cache_root)

    def _device_id(self):
        if self.device and "cuda" in str(self.device):
            try:
                return int(str(self.device).split(":")[-1])
            except Exception:  # noqa: BLE001
                return 0
        return -1  # CPU

    def _load_asr_model(self):
        from funasr_onnx.paraformer_bin import Paraformer

        model_dir = self._model_dir("asr")
        quant = os.path.join(model_dir, "model_quant.onnx")
        base = os.path.join(model_dir, "model.onnx")
        use_quantize = os.path.exists(quant)
        if not use_quantize and not os.path.exists(base):
            return False
        self.asr_model = Paraformer(
            str(model_dir), batch_size=1, device_id=self._device_id(),
            quantize=use_quantize, intra_op_num_threads=self.threads)
        return True

    def _load_vad_model(self):
        from funasr_onnx.vad_bin import Fsmn_vad

        model_dir = self._model_dir("vad")
        quant = os.path.join(model_dir, "model_quant.onnx")
        base = os.path.join(model_dir, "model.onnx")
        use_quantize = os.path.exists(quant)
        if not use_quantize and not os.path.exists(base):
            return False
        self.vad_model = Fsmn_vad(
            str(model_dir), batch_size=1, device_id=self._device_id(),
            quantize=use_quantize, intra_op_num_threads=self.threads)
        return True

    def _load_punc_model(self):
        from funasr_onnx.punc_bin import CT_Transformer

        model_dir = self._model_dir("punc")
        quant = os.path.join(model_dir, "model_quant.onnx")
        base = os.path.join(model_dir, "model.onnx")
        use_quantize = os.path.exists(quant)
        if not use_quantize and not os.path.exists(base):
            return False
        self.punc_model = CT_Transformer(
            str(model_dir), batch_size=1, device_id=self._device_id(),
            quantize=use_quantize, intra_op_num_threads=self.threads)
        return True

    # ---- 推理 ----
    def vad(self, pcm: bytes, sample_rate: int):
        """对 PCM 片段跑 FSMN-VAD，返回原始分段（交给 Segmenter 归一化）。"""
        with tempfile.TemporaryDirectory(prefix="voice_vad_") as tmpdir:
            wav_path = pcm_to_temp_wav(pcm, sample_rate, tmpdir)
            return self.vad_model(wav_path)

    def asr(self, wav_path: str, hotword: str = "") -> str:
        """对 WAV 文件跑 Paraformer，返回识别文本（兼容 PyTorch/ONNX 返回格式）。

        ``hotword`` 空格分隔的热词串：仅上下文偏置模型（带 ``proc_hotword`` 的
        ContextualParaformer 一系）支持 ``hotwords`` 入参；普通 Paraformer 不具备
        模型级热词能力，忽略并在 stderr 留一条诊断（确定性纠错走主程序替换表）。
        """
        hotword = str(hotword or "").strip()
        kwargs = {}
        if hotword and hasattr(self.asr_model, "proc_hotword"):
            kwargs["hotwords"] = hotword
        elif hotword and not getattr(self, "_hotword_noted", False):
            self._hotword_noted = True
            import sys
            print("[voice-asr] 当前识别模型不支持热词纠偏，热词仅走主程序替换表",
                  file=sys.stderr)
        try:
            result = self.asr_model([wav_path], **kwargs) if kwargs else self.asr_model([wav_path])
        except TypeError:
            if not kwargs:
                raise
            # 模型可调用但不收热词入参：退回无热词识别（确定性纠错走主程序替换表）。
            import sys
            print("[voice-asr] 识别模型不接受热词入参，本次按无热词识别", file=sys.stderr)
            result = self.asr_model([wav_path])
        if isinstance(result, list) and result:
            first = result[0]
            if isinstance(first, dict):
                if "text" in first:
                    return str(first["text"])
                if "preds" in first:
                    preds = first["preds"]
                    if isinstance(preds, (tuple, list)) and preds:
                        return str(preds[0])
                    return str(preds)
            return str(first)
        return str(result or "")

    def punc(self, text: str) -> str:
        """CT-punc 标点恢复；返回带标点文本。"""
        result = self.punc_model(text)
        if isinstance(result, (tuple, list)) and result:
            return str(result[0])
        return str(result or text)

    def note_transcription(self, audio_ms: float):
        """累计转录计数；每 10 次触发一次内存清理（移植 vocotype 成熟点）。"""
        self.transcription_count += 1
        self.total_audio_ms += audio_ms
        if self.transcription_count % 10 == 0:
            self.cleanup_memory()

    @staticmethod
    def cleanup_memory():
        try:
            import gc
            gc.collect()
        except Exception:  # noqa: BLE001
            pass

    def close(self):
        """释放模型引用并回收内存。"""
        self.asr_model = None
        self.vad_model = None
        self.punc_model = None
        self.loaded = False
        self.cleanup_memory()


class OfflineAsrEngine:
    """会话级引擎：管理 PcmSession 与 Segmenter，产出协议事件。"""

    def __init__(self, backend):
        self.backend = backend
        self.session = None
        self.segmenter = None

    def open_session(self, sample_rate=SAMPLE_RATE, hotword="", vad=None, log_fn=None):
        if int(sample_rate) != SAMPLE_RATE:
            raise ValueError("离线引擎仅支持 %d Hz 单声道 16bit PCM" % SAMPLE_RATE)
        overrides = {}
        if isinstance(vad, dict):
            for key in ("tick_ms", "trailing_ms", "window_ms", "min_ms", "max_ms"):
                value = vad.get(key)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    overrides[key] = value
        self.session = PcmSession(sample_rate, hotword)
        self.segmenter = Segmenter(
            self.backend.vad, self.backend.asr, self.backend.punc,
            log_fn=log_fn or _emit_log, **overrides)
        return self.session

    def cancel_session(self, emit):
        """丢弃当前会话缓冲，不产出句子；只发 log 不发 done（done 只属于 stop 收尾）。"""
        self.session = None
        emit({"type": "log", "message": "识别会话已取消"})

    def _require_session(self):
        if self.session is None or not self.session.active:
            raise RuntimeError("没有活动的识别会话，请先发送 start")
        return self.session

    def feed(self, data, emit):
        """喂入一块 base64 PCM 并轮询分句，句子即时经 emit 下发。"""
        session = self._require_session()
        session.feed(_decode_audio(data))
        for event in self.segmenter.poll(session):
            if self.backend is not None and hasattr(self.backend, "note_transcription"):
                self.backend.note_transcription(
                    max(0, event["end_ms"] - event["start_ms"]))
            emit({"type": "sentence", **event})

    def stop(self, emit):
        """结束会话：强制冲刷全部剩余分句，然后发 done。"""
        session = self._require_session()
        for event in self.segmenter.poll(session, final=True):
            if self.backend is not None and hasattr(self.backend, "note_transcription"):
                self.backend.note_transcription(
                    max(0, event["end_ms"] - event["start_ms"]))
            emit({"type": "sentence", **event})
        session.active = False
        emit({"type": "done"})


def _zh_error(prefix, exc):
    """把异常转成中文原因（不含密钥/路径堆栈细节）。"""
    text = str(exc).strip() or exc.__class__.__name__
    lowered = text.lower()
    if "modulenotfounderror" in lowered or "importerror" in lowered or "no module named" in lowered:
        return "%s：ASR 运行环境缺少依赖（%s），请重新运行 voice_engine/bootstrap.py 安装" % (prefix, text[:120])
    if "snapshot" in lowered or "modelscope" in lowered or "download" in lowered or "connection" in lowered or "timeout" in lowered:
        return "%s：模型下载失败，请检查网络后重试（%s）" % (prefix, text[:160])
    return "%s：%s" % (prefix, text[:200])


def _parse_line(raw):
    line = raw.strip()
    if not line:
        return {}
    if len(line) > MAX_LINE_BYTES:
        return {"_invalid": "命令行过长"}
    try:
        msg = json.loads(line)
    except ValueError:
        return {"_invalid": line[:80]}
    return msg if isinstance(msg, dict) else {"_invalid": "命令必须是 JSON 对象"}


def main(argv=None):
    """引擎入口：加载模型 -> ready -> 命令循环 -> shutdown。"""
    _configure_stdio()
    backend = FunAsrBackend(cache_root=download_models.default_cache_root())
    engine = OfflineAsrEngine(backend)
    try:
        backend.load(progress=_emit_log)
    except Exception as exc:  # noqa: BLE001
        emit_message({"type": "error", "message": _zh_error("模型加载失败", exc)})
        return EXIT_MODEL_ERROR
    emit_message({"type": "ready", "device": backend.device,
                  "models": dict(backend.model_names)})

    for raw in sys.stdin:
        msg = _parse_line(raw)
        if not msg:
            continue
        if "_invalid" in msg:
            emit_message({"type": "error",
                          "message": "无法解析的命令：%s" % msg["_invalid"]})
            continue
        cmd = msg.get("cmd")
        try:
            if cmd == "start":
                engine.open_session(
                    msg.get("sample_rate", SAMPLE_RATE),
                    msg.get("hotword", ""), vad=msg.get("vad"), log_fn=_emit_log)
                emit_message({"type": "log", "message": "识别会话已开始"})
            elif cmd == "audio":
                engine.feed(msg.get("data", ""), emit_message)
            elif cmd == "stop":
                engine.stop(emit_message)
            elif cmd == "cancel":
                engine.cancel_session(emit_message)
            elif cmd == "shutdown":
                break
            else:
                emit_message({"type": "error", "message": "未知命令：%s" % cmd})
        except Exception as exc:  # noqa: BLE001 —— 单命令失败不退出进程
            emit_message({"type": "error", "message": _zh_error("命令处理失败", exc)})

    try:
        backend.close()
    except Exception:  # noqa: BLE001
        pass
    return EXIT_OK


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(EXIT_OK)
    except Exception as exc:  # noqa: BLE001 —— 兜底：任何未捕获异常转错误行并非零退出
        try:
            emit_message({"type": "error", "message": _zh_error("引擎异常退出", exc)})
        except Exception:  # noqa: BLE001
            pass
        raise SystemExit(EXIT_FATAL)
