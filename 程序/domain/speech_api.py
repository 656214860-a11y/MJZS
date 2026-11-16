"""REQ-S01-71：语音输入的后端抽象与设置（离线 FunASR 为主，阿里云云端可选）。

``backend`` 默认 ``offline``：PCM 交给 ``domain.offline_asr_client`` 的常驻子进程引擎
（``voice_engine/offline_asr_server.py``，FSMN-VAD 逐句定稿即出字）；``cloud`` 走阿里云
百炼 ``qwen3-asr-flash-realtime``（WebSocket，OpenAI Realtime 风格事件）：录音线程每
0.1 秒推一块 16 kHz PCM，服务端按停顿断句，先回中间结果、再回整句定稿。
两种后端对界面暴露同一事件接口 ``('partial'|'final'|'error'|'closed'|'log', item, text)``，
由 ``create_session()`` 按设置分流；离线引擎不可用且已配云端密钥时自动降级云端。

服务地址、模型、密钥变量名、语言、断句静音与上限时长都可在 ``data/语音识别.json`` 覆盖
（升级保留；界面入口是模型管理底栏「语音识别…」，经 ``speech_settings_ui`` 调 ``save_settings`` 写入），不改代码即可换同协议的服务；密钥只按变量名从模型池取，不写进设置文件、
日志或事件文字。``offline`` 节保存离线引擎的解释器、模型缓存目录、线程数与 VAD 断句参数。
"""
import base64
import json
import queue
import threading
from pathlib import Path
from urllib.parse import urlparse

import file_cache
import contract.platform_tools as platform_tools

PROGRAM = Path(__file__).resolve().parents[1]
USER_FILE = PROGRAM / 'data' / '语音识别.json'
BACKENDS = ('offline', 'cloud')
DEFAULTS = {
    'backend': 'offline',
    'base_url': 'wss://dashscope.aliyuncs.com/api-ws/v1/realtime',
    'model': 'qwen3-asr-flash-realtime',
    'key_env': 'DASHSCOPE_API_KEY',
    'language': 'zh',
    'silence_ms': 400,           # 停顿多久算一句说完；服务端默认 800，听写场景 400 出字更快
    'max_seconds': 600,          # 一次开麦的上限，到了自动关麦
    'timeout': 15,               # 建立连接与关麦后等最后一句定稿的上限（秒）
    'offline': {                 # 离线引擎（voice_engine）专属设置；空串=自动探测
        'python': '',            # ASR venv 解释器；空=data/voice_asr_venv
        'cache_dir': '',         # 模型缓存根；空=data/voice_models
        'threads': '',           # OMP 线程数；空=引擎默认
        'vad_trailing_ms': 500,  # VAD 句末静音时长，越小出字越快越易断句
    },
}
OFFLINE_NUMBER_RANGES = {'vad_trailing_ms': (200, 5000)}


def read_settings(path=None):
    """内置默认合并用户覆盖；文件缺失或不是对象时用默认。"""
    try:
        data = file_cache.read_json(Path(path or USER_FILE))
    except (OSError, ValueError):
        data = None
    merged = dict(DEFAULTS)
    merged['offline'] = dict(DEFAULTS['offline'])
    if isinstance(data, dict):
        merged.update({key: data[key] for key in DEFAULTS
                       if key != 'offline' and data.get(key) not in (None, '')})
        offline = data.get('offline')
        if isinstance(offline, dict):
            merged['offline'].update({key: offline[key] for key in merged['offline']
                                      if offline.get(key) not in (None, '')})
    return merged


def _clean_offline(raw):
    """校验 ``offline`` 节：只认已知键，数值键按范围转 int，字符串键去空白。"""
    if raw in (None, ''):
        source = {}
    elif isinstance(raw, dict):
        source = raw
    else:
        raise ValueError('离线识别设置格式不正确')
    merged = {}
    for key, default in DEFAULTS['offline'].items():
        value = source.get(key, default)
        if key in OFFLINE_NUMBER_RANGES:
            text = str(value).strip()
            low, high = OFFLINE_NUMBER_RANGES[key]
            if not text.isdigit() or not low <= int(text) <= high:
                raise ValueError('离线识别 %s 必须是 %d–%d 之间的整数' % (key, low, high))
            merged[key] = int(text)
        else:
            merged[key] = str(value if value is not None else '').strip()
    return merged


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
    merged['offline'] = dict(DEFAULTS['offline'])
    for key in DEFAULTS:
        if key == 'offline':
            continue
        value = str(values.get(key, DEFAULTS[key])).strip()
        if key == 'backend':
            if value not in BACKENDS:
                raise ValueError('识别后端必须是 %s 之一' % '／'.join(BACKENDS))
        elif key in NUMBER_RANGES:
            low, high = NUMBER_RANGES[key]
            if not value.isdigit() or not low <= int(value) <= high:
                raise ValueError('%s 必须是 %d–%d 之间的整数' % (key, low, high))
            value = int(value)
        elif not value:
            raise ValueError('%s 不能为空' % key)
        merged[key] = value
    merged['offline'] = _clean_offline(values.get('offline'))
    endpoint(merged)
    target = Path(path or USER_FILE)
    target.parent.mkdir(parents=True, exist_ok=True)
    publish(target, {key: value for key, value in merged.items() if value != DEFAULTS[key]})
    file_cache.invalidate(target)
    return merged


def api_key(settings=None):
    import model_pool
    return model_pool.named_key((settings or read_settings())['key_env'])


def cloud_missing_reason(settings):
    """云端后端缺密钥时的原因；``RealtimeSession`` 内部固定走这里，不看 ``backend``。"""
    if not api_key(settings):
        return ('没有配置语音识别密钥 %s：请在「模型管理」添加阿里云百炼密钥，'
                '或在「模型管理 › 语音识别…」改用其它服务' % settings['key_env'])
    return ''


def missing_reason(settings=None):
    """能开识别时返回空串，否则返回一句给状态栏的原因（按 ``backend`` 分流）。"""
    settings = settings or read_settings()
    backend = settings.get('backend') or 'offline'
    if backend == 'cloud':
        return cloud_missing_reason(settings)
    import domain.offline_asr_client as offline_asr_client
    problem = offline_asr_client.environment_problem(settings)
    if problem and api_key(settings):
        return ''   # 引擎缺失但已配云端密钥：会话层自动降级，不拦截
    return problem


def create_session(settings, *, connect=None):
    """按 ``backend`` 路由到离线子进程或云端实时会话；两者暴露同一事件接口。

    ``connect`` 是 ``RealtimeSession`` 的测试注入点（WebSocket 工厂）；离线路径不用它，
    但降级到云端时原样传递。离线引擎不可用且已配云端密钥时，``OfflineAsrSession``
    内部自动降级并先发一条 ``('log', ...)`` 通知。
    """
    settings = settings or read_settings()
    if (settings.get('backend') or 'offline') != 'offline':
        return RealtimeSession(settings, connect=connect)
    import domain.offline_asr_client as offline_asr_client
    fallback = None
    if api_key(settings):
        fallback = lambda merged: RealtimeSession(merged, connect=connect)
    return offline_asr_client.OfflineAsrSession(settings, fallback=fallback)


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
            return self._fail(cloud_missing_reason(settings))
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
