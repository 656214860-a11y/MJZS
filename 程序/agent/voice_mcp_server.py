# -*- coding: utf-8 -*-
"""MCP stdio 服务：把离线语音识别暴露为 ``voice_transcribe`` 工具（任务书轮 4）。

零第三方依赖：手写 JSON-RPC 2.0 over stdio（``initialize``/``tools/list``/
``tools/call``/``ping``），不走 ``mcp`` 包。agent 侧配置示例::

    {"mcpServers": {"voice-transcribe": {"command": "<程序 Python>",
     "args": ["<程序>/agent/voice_mcp_server.py"]}}}

工具入参二选一：``audio_path``（本地 16-bit PCM 单声道 WAV，采样率自动重采样到
16 kHz）或 ``pcm_base64``＋``sample_rate``（s16le 单声道原始 PCM）。``hotword``
空格分隔热词，缺省取 ``data/语音词典.json`` 的热词；识别文本同样过词典替换表。
后端固定离线 FunASR 子进程（``domain.speech_api`` 路由），与界面听写同一引擎。
"""
import base64
import json
import struct
import sys
import time
from json import loads as _loads
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PROTOCOL_VERSION = '2024-11-05'
SERVER_INFO = {'name': 'voice-transcribe', 'version': '1.0.0'}
TARGET_RATE = 16000
PCM_CHUNK = 6400          # 0.2 秒 @16kHz s16le

_TOOL = {
    'name': 'voice_transcribe',
    'description': ('离线语音识别：把音频转写成文字。优先传 audio_path（16-bit PCM '
                    '单声道 WAV）；或传 pcm_base64（s16le 单声道）＋sample_rate。'
                    '返回逐句定稿拼接的文本；识别文本会按语音词典替换表修正。'),
    'inputSchema': {
        'type': 'object',
        'properties': {
            'audio_path': {'type': 'string', 'description': '本地 WAV 文件路径'},
            'pcm_base64': {'type': 'string', 'description': '原始 PCM 的 base64'},
            'sample_rate': {'type': 'integer', 'description': 'pcm_base64 采样率，默认 16000'},
            'hotword': {'type': 'string', 'description': '空格分隔热词；缺省用词典热词'},
        },
        'additionalProperties': False,
    },
}


def _resample_pcm16(pcm, src_rate, dst_rate=TARGET_RATE):
    """s16le PCM 线性重采样到 ``dst_rate``；同采样率原样返回。"""
    if int(src_rate) == dst_rate:
        return pcm
    count = len(pcm) // 2
    if not count:
        return b''
    samples = struct.unpack('<%dh' % count, pcm[:count * 2])
    ratio = float(src_rate) / float(dst_rate)
    out_count = max(1, int(count / ratio))
    out = []
    for i in range(out_count):
        pos = i * ratio
        j = int(pos)
        frac = pos - j
        a = samples[j] if j < count else samples[-1]
        b = samples[j + 1] if j + 1 < count else a
        out.append(max(-32768, min(32767, int(a + (b - a) * frac))))
    return struct.pack('<%dh' % len(out), *out)


def _pcm_from_wav(path):
    """读 16-bit PCM 单声道 WAV → (pcm_bytes, sample_rate)。

    手写 RIFF chunk 解析：产品运行时是裁剪版 Python，没有 ``wave``/``audioop``
    标准库，只接受 PCM WAV 本来就用得到的最小子集。
    """
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        raise ValueError('音频文件读不到：%s' % exc) from exc
    if len(data) < 12 or data[:4] != b'RIFF' or data[8:12] != b'WAVE':
        raise ValueError('无法解析音频（仅支持 WAV）：文件头不是 RIFF/WAVE')
    fmt, pcm, rate = None, b'', 0
    offset = 12
    while offset + 8 <= len(data):
        chunk_id = data[offset:offset + 4]
        size = struct.unpack('<I', data[offset + 4:offset + 8])[0]
        body = data[offset + 8:offset + 8 + size]
        if chunk_id == b'fmt ':
            fmt = body
        elif chunk_id == b'data':
            pcm = body
        offset += 8 + size + (size & 1)  # chunk 按偶数字节对齐
    if fmt is None or len(fmt) < 16 or not pcm:
        raise ValueError('WAV 缺少 fmt/data 块')
    audio_format, channels, rate = struct.unpack('<HHI', fmt[:8])
    bits_per_sample = struct.unpack('<H', fmt[14:16])[0]
    if audio_format != 1:
        raise ValueError('仅支持 PCM WAV（压缩格式不支持）')
    if bits_per_sample != 16:
        raise ValueError('仅支持 16-bit PCM WAV')
    if channels != 1:
        raise ValueError('仅支持单声道 WAV')
    return pcm, int(rate)


def _load_pcm(arguments):
    """按入参取 PCM：audio_path 或 pcm_base64+sample_rate，二选一。"""
    path = str(arguments.get('audio_path') or '').strip()
    blob = str(arguments.get('pcm_base64') or '').strip()
    if bool(path) == bool(blob):
        raise ValueError('audio_path 与 pcm_base64 必须且只能给一个')
    if path:
        pcm, rate = _pcm_from_wav(path)
    else:
        try:
            rate = int(arguments.get('sample_rate') or TARGET_RATE)
        except (TypeError, ValueError):
            raise ValueError('sample_rate 必须是整数')
        if not 4000 <= rate <= 48000:
            raise ValueError('sample_rate 必须在 4000–48000')
        try:
            pcm = base64.b64decode(blob, validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError('pcm_base64 不是有效的 base64') from exc
    if not pcm:
        raise ValueError('音频内容为空')
    return _resample_pcm16(pcm, rate), TARGET_RATE


def transcribe(arguments, *, session_factory=None, settings=None):
    """一次性离线识别：PCM 分块喂会话，收齐 final 拼接返回文本。

    ``session_factory(settings) -> 会话`` 为测试注入点，默认
    ``domain.speech_api.create_session``（backend 固定 offline）。
    """
    import queue
    import domain.speech_api as speech_api
    pcm, rate = _load_pcm(arguments)
    settings = dict(settings or speech_api.read_settings())
    settings['backend'] = 'offline'
    hotword = str(arguments.get('hotword') or '').strip()
    if hotword:
        offline = dict(settings.get('offline') or {})
        offline['hotword'] = hotword
        settings['offline'] = offline
    factory = session_factory or speech_api.create_session
    session = factory(settings)
    finals, failure = [], ''
    session.start()
    try:
        for offset in range(0, len(pcm), PCM_CHUNK):
            session.send(pcm[offset:offset + PCM_CHUNK])
        session.finish()
        seconds = len(pcm) / 2 / rate
        deadline = time.monotonic() + min(900.0, max(120.0, seconds * 5 + 60))
        while True:
            try:
                kind, _item, text = session.events.get(timeout=0.5)
            except queue.Empty:
                kind, text = '', ''
            if kind == 'final':
                finals.append(str(text))
            elif kind == 'error':
                failure = str(text) or '离线识别失败'
            elif kind == 'closed':
                break
            if failure or time.monotonic() > deadline:
                failure = failure or '识别超时，音频过长或引擎未响应'
                break
    finally:
        try:
            session.cancel()
        except Exception as exc:  # noqa: BLE001 —— 清理失败不挡协议返回，stderr 留痕
            print('[voice-mcp] 会话清理失败：%s' % str(exc)[:120], file=sys.stderr)
    if failure:
        raise ValueError(failure)
    return ''.join(finals)


def _result(request_id, result=None, error=None):
    if error is not None:
        return {'jsonrpc': '2.0', 'id': request_id,
                'error': {'code': -32603, 'message': str(error)[:500]}}
    return {'jsonrpc': '2.0', 'id': request_id, 'result': result}


def handle(message, *, session_factory=None, settings=None):
    """处理一条 JSON-RPC 消息；通知（无 id）返回 None。"""
    request_id = message.get('id')
    method = message.get('method')
    if request_id is None:
        return None
    if method == 'initialize':
        params = message.get('params') or {}
        return _result(request_id, {
            'protocolVersion': params.get('protocolVersion') or PROTOCOL_VERSION,
            'capabilities': {'tools': {}},
            'serverInfo': SERVER_INFO,
        })
    if method == 'ping':
        return _result(request_id, {})
    if method == 'tools/list':
        return _result(request_id, {'tools': [_TOOL]})
    if method == 'tools/call':
        params = message.get('params') or {}
        if params.get('name') != 'voice_transcribe':
            return _result(request_id, error='未知工具：%s' % params.get('name'))
        arguments = params.get('arguments') or {}
        try:
            text = transcribe(arguments, session_factory=session_factory, settings=settings)
        except Exception as exc:  # noqa: BLE001
            return _result(request_id, {
                'content': [{'type': 'text', 'text': '识别失败：%s' % str(exc)[:300]}],
                'isError': True,
            })
        return _result(request_id, {
            'content': [{'type': 'text', 'text': text or '（未识别到语音内容）'}],
            'isError': False,
        })
    return _result(request_id, error='未知方法：%s' % method)


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = _loads(line)
        except ValueError:
            sys.stdout.write(json.dumps(_result(None, error='请求不是有效 JSON'),
                                        ensure_ascii=False) + '\n')
            sys.stdout.flush()
            continue
        if not isinstance(message, dict):
            continue
        response = handle(message)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + '\n')
            sys.stdout.flush()


if __name__ == '__main__':
    main()
