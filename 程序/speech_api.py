"""REQ-S01-71：剧本准备页语音输入的实时云端识别（边说边出字）。

默认走阿里云百炼 ``qwen3-asr-flash-realtime``（WebSocket，OpenAI Realtime 风格事件）：
录音线程每 0.1 秒推一块 16 kHz PCM，服务端按停顿断句，先回中间结果、再回整句定稿。
服务地址、模型、密钥变量名、语言、断句静音与上限时长都可在 ``data/语音识别.json`` 覆盖
（升级保留；界面入口是模型管理底栏「语音识别…」，经 ``speech_settings_ui`` 调 ``save_settings`` 写入），不改代码即可换同协议的服务；密钥只按变量名从模型池取，不写进设置文件、
日志或事件文字。
"""
import base64
import json
import queue
import threading
from pathlib import Path
from urllib.parse import urlparse

import file_cache
import platform_tools

PROGRAM = Path(__file__).resolve().parent
USER_FILE = PROGRAM / 'data' / '语音识别.json'
DEFAULTS = {
    'base_url': 'wss://dashscope.aliyuncs.com/api-ws/v1/realtime',
    'model': 'qwen3-asr-flash-realtime',
    'key_env': 'DASHSCOPE_API_KEY',
    'language': 'zh',
    'silence_ms': 400,           # 停顿多久算一句说完；服务端默认 800，听写场景 400 出字更快
    'max_seconds': 600,          # 一次开麦的上限，到了自动关麦
    'timeout': 15,               # 建立连接与关麦后等最后一句定稿的上限（秒）
}


def read_settings(path=None):
    """内置默认合并用户覆盖；文件缺失或不是对象时用默认。"""
    try:
        data = file_cache.read_json(Path(path or USER_FILE))
    except (OSError, ValueError):
        data = None
    merged = dict(DEFAULTS)
    if isinstance(data, dict):
        merged.update({key: data[key] for key in DEFAULTS if data.get(key) not in (None, '')})
    return merged


NUMBER_RANGES = {'silence_ms': (100, 2000), 'max_seconds': (10, 3600), 'timeout': (3, 120)}


def save_settings(values, *, publish, path=None):
    """模型管理 › 语音识别弹窗的保存入口：校验后只把与默认不同的字段写进设置文件。

    ``publish(路径, 对象)`` 由界面层注入（如 ``agent.core.save``）。不合法时抛带中文原因的
    ``ValueError``，文件不动；全部等于默认时写空对象。返回合并后的设置。
    """
    merged = dict(DEFAULTS)
    for key in DEFAULTS:
        value = str(values.get(key, DEFAULTS[key])).strip()
        if key in NUMBER_RANGES:
            low, high = NUMBER_RANGES[key]
            if not value.isdigit() or not low <= int(value) <= high:
                raise ValueError('%s 必须是 %d–%d 之间的整数' % (key, low, high))
            value = int(value)
        elif not value:
            raise ValueError('%s 不能为空' % key)
        merged[key] = value
    endpoint(merged)
    target = Path(path or USER_FILE)
    target.parent.mkdir(parents=True, exist_ok=True)
    publish(target, {key: value for key, value in merged.items() if value != DEFAULTS[key]})
    file_cache.invalidate(target)
    return merged


def api_key(settings=None):
    import model_pool
    return model_pool.named_key((settings or read_settings())['key_env'])


def missing_reason(settings=None):
    """能开实时识别时返回空串，否则返回一句给状态栏的原因。"""
    settings = settings or read_settings()
    if not api_key(settings):
        return '没有配置语音识别密钥 %s：请在「模型管理」添加阿里云百炼密钥，或在「模型管理 › 语音识别…」改用其它服务' % settings['key_env']
    return ''


def endpoint(settings):
    base = str(settings['base_url']).strip()
    parsed = urlparse(base)
    local = parsed.scheme == 'ws' and parsed.hostname in ('127.0.0.1', 'localhost', '::1')
    if parsed.scheme != 'wss' and not local:
        raise ValueError('语音识别地址必须是 wss://（本机服务可用 ws://）')
    return base + ('&' if parsed.query else '?') + 'model=' + str(settings['model'])


def session_update(settings):
    return {'type': 'session.update', 'session': {
        'modalities': ['text'], 'input_audio_format': 'pcm', 'sample_rate': platform_tools.RECORD_RATE,
        'input_audio_transcription': {'language': settings['language']},
        'turn_detection': {'type': 'server_vad', 'threshold': 0.2, 'silence_duration_ms': int(settings['silence_ms'])}}}


def _refused(error, settings):
    if error.status in (401, 403):
        return '密钥无效或没有开通 %s（HTTP %d）' % (settings['model'], error.status)
    return '识别服务拒绝连接（HTTP %d）' % error.status


class RealtimeSession:
    """一次开麦对应一个会话。``send`` 与 ``finish`` 可在任意线程调用，结果从 ``events`` 取：

    ``('partial', 句号, 文字)`` 当前句的中间结果（会被后续同句号的事件替换）；
    ``('final', 句号, 文字)`` 整句定稿；``('error', '', 原因)``；最后一定有 ``('closed', '', '')``。
    ``connect`` 是测试注入点，默认 ``platform_tools.open_websocket``。
    """
    def __init__(self, settings, *, key=None, connect=None):
        self.settings, self.key = settings, key
        self.connect = connect or platform_tools.open_websocket
        self.events, self.audio = queue.Queue(), queue.Queue()
        self.socket, self.cancelled, self.thread = None, False, None

    def start(self):
        self.thread = threading.Thread(target=self._run, name='voice-realtime', daemon=True)
        self.thread.start()

    def send(self, pcm):
        self.audio.put(bytes(pcm))

    def finish(self):
        self.audio.put(None)

    def cancel(self):
        self.cancelled = True
        self.audio.put(None)
        if self.socket is not None:
            self.socket.close()

    def _fail(self, reason):
        if not self.cancelled:
            self.events.put(('error', '', reason))

    def _run(self):
        try:
            self._converse()
        finally:
            self.events.put(('closed', '', ''))

    def _converse(self):
        settings = self.settings
        key = self.key or api_key(settings)
        if not key:
            return self._fail(missing_reason(settings))
        try:
            url = endpoint(settings)
            self.socket = self.connect(url, timeout=settings['timeout'],
                                       headers={'Authorization': 'Bearer ' + key, 'OpenAI-Beta': 'realtime=v1'})
        except ValueError as error:
            return self._fail(str(error))
        except platform_tools.WebSocketRefused as error:
            return self._fail(_refused(error, settings))
        except OSError as error:
            return self._fail('连不上识别服务：%s' % (type(error).__name__ if not str(error) else str(error)[:120]))
        if self.cancelled:
            return self.socket.close()
        reader = threading.Thread(target=self._read, name='voice-realtime-read', daemon=True)
        try:
            self.socket.send_text(json.dumps(session_update(settings)))
            reader.start()
            while True:
                pcm = self.audio.get()
                if pcm is None or self.cancelled:
                    break
                self.socket.send_text(json.dumps({'type': 'input_audio_buffer.append',
                                                  'audio': base64.b64encode(pcm).decode('ascii')}))
            if not self.cancelled:
                self.socket.send_text(json.dumps({'type': 'session.finish'}))
                reader.join(settings['timeout'])
        except OSError:
            self._fail('识别连接中断')
        finally:
            self.socket.close()

    def _read(self):
        try:
            while True:
                message = self.socket.recv_text()
                if message is None or self._handle(message):
                    return
        except OSError:
            self._fail('识别连接中断')

    def _handle(self, message):
        """把一条服务端事件转成界面事件；会话结束时返回真。"""
        try:
            event = json.loads(message)
        except ValueError:
            return False
        kind, item = event.get('type', ''), str(event.get('item_id', ''))
        if kind == 'conversation.item.input_audio_transcription.text':
            self.events.put(('partial', item, str(event.get('text', '')) + str(event.get('stash', ''))))
        elif kind == 'conversation.item.input_audio_transcription.completed':
            self.events.put(('final', item, str(event.get('transcript', ''))))
        elif kind == 'error':
            detail = event.get('error') if isinstance(event.get('error'), dict) else {}
            self._fail('识别服务报错：%s' % str(detail.get('message') or detail.get('code') or '未知')[:120])
        return kind == 'session.finished'
