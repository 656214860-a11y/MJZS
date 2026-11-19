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
import time
from pathlib import Path
from urllib.parse import urlparse

import infra.app_logging as app_logging
import infra.business_log as business_log
import infra.executors as executors
import infra.file_cache as file_cache
import contract.platform_tools as platform_tools

PROGRAM = Path(__file__).resolve().parents[1]
USER_FILE = PROGRAM / 'data' / '语音识别.json'
DICT_FILE = PROGRAM / 'data' / '语音词典.json'
BACKENDS = ('offline', 'cloud')
DICT_DEFAULTS = {
    'hotword': [],                 # 领域热词：随 start.hotword 下发给支持热词的引擎
    'replace': {},                 # 同音替换表 {误识别: 正确词}：final 文本定稿后处理
    'ai': {'enabled': False, 'template': 'fix', 'prompt': ''},  # AI 优化文本（domain.voice_ai 模板）
}
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
    import infra.model_pool as model_pool
    return model_pool.named_key((settings or read_settings())['key_env'])


# ── 语音词典（热词／同音替换／AI 优化），独立文件 data/语音词典.json ──────────

_HOTWORD_SEPARATORS = '，,；;、 \n\r\t'


def _hotword_items(text):
    """把一串热词按中英文逗号/分号/顿号/空白切成列表。"""
    for sep in _HOTWORD_SEPARATORS:
        text = text.replace(sep, ',')
    return [item.strip() for item in text.split(',')]


def _clean_hotword(raw):
    """热词列表：字符串按逗号/分号/顿号/换行切分，列表逐项清洗去重，保序。"""
    if raw in (None, ''):
        items = []
    elif isinstance(raw, str):
        items = _hotword_items(raw)
    elif isinstance(raw, (list, tuple)):
        items = []
        for entry in raw:
            items.extend(_hotword_items(str(entry)))
    else:
        raise ValueError('热词格式不正确')
    seen, result = set(), []
    for item in items:
        word = str(item).strip()
        if not word:
            continue
        if len(word) > 100:
            raise ValueError('热词「%s…」过长（单条不超过 100 字）' % word[:20])
        if word not in seen:
            seen.add(word)
            result.append(word)
    if len(result) > 200:
        raise ValueError('热词最多 200 条')
    return result


def _clean_replace(raw):
    """同音替换表：{误识别: 正确词}，两端去空白、丢弃空键与同值对。"""
    if raw in (None, ''):
        return {}
    if not isinstance(raw, dict):
        raise ValueError('替换词表格式不正确')
    table = {}
    for wrong, right in raw.items():
        key, value = str(wrong).strip(), str(right).strip()
        if not key or not value:
            continue
        if len(key) > 100 or len(value) > 100:
            raise ValueError('替换词「%s」过长（单条不超过 100 字）' % (key or value)[:20])
        if key != value:
            table[key] = value
    if len(table) > 500:
        raise ValueError('替换词最多 500 条')
    return table


def _clean_ai(raw):
    """AI 优化配置：enabled/template/prompt；模板名由 domain.voice_ai 校验。"""
    import domain.voice_ai as voice_ai
    source = raw if isinstance(raw, dict) else {}
    enabled = source.get('enabled', DICT_DEFAULTS['ai']['enabled'])
    if isinstance(enabled, str):
        enabled = enabled.strip().lower() in ('1', 'true', 'on', 'yes', '开')
    template = str(source.get('template') or DICT_DEFAULTS['ai']['template']).strip()
    if template not in voice_ai.TEMPLATES:
        raise ValueError('AI 优化模板必须是 %s 之一' % '／'.join(voice_ai.TEMPLATES))
    prompt = str(source.get('prompt') or '').strip()
    if len(prompt) > 2000:
        raise ValueError('AI 优化自定义提示词过长（不超过 2000 字）')
    return {'enabled': bool(enabled), 'template': template, 'prompt': prompt}


def normalize_dictionary(raw):
    """校验并规整词典对象；不合法抛带中文原因的 ``ValueError``。"""
    source = raw if isinstance(raw, dict) else {}
    return {'hotword': _clean_hotword(source.get('hotword')),
            'replace': _clean_replace(source.get('replace')),
            'ai': _clean_ai(source.get('ai'))}


def read_dictionary(path=None):
    """读 ``data/语音词典.json``：缺文件/坏节回默认，不抛错。"""
    merged = {'hotword': [], 'replace': {},
              'ai': dict(DICT_DEFAULTS['ai'])}
    try:
        data = file_cache.read_json(Path(path or DICT_FILE))
    except (OSError, ValueError):
        data = None
    if isinstance(data, dict):
        for key in merged:
            try:
                merged[key] = normalize_dictionary({key: data[key]})[key]
            except (ValueError, KeyError):
                pass
    return merged


def save_dictionary(values, *, publish, path=None):
    """保存词典：先 ``normalize_dictionary`` 校验，通过后整体写入并失效缓存。

    ``publish(路径, 对象)`` 由界面层注入（如 ``agent.core.save``）。返回规整后的词典。
    """
    normalized = normalize_dictionary(values)
    target = Path(path or DICT_FILE)
    target.parent.mkdir(parents=True, exist_ok=True)
    publish(target, normalized)
    file_cache.invalidate(target)
    return normalized


def hotword_text(dictionary=None):
    """热词列表 → 引擎 ``start.hotword`` 的空格分隔串（FunASR 热词格式）。"""
    return ' '.join((dictionary or read_dictionary()).get('hotword') or ())


def apply_replacements(text, replace=None):
    """按替换表修正识别文本：正则交替按键长降序一次扫描，长键优先且不重复扫
    已替换出的文本（``子进程`` 不会被 ``进程`` 二次改写）；返回新文本。"""
    import re
    text = str(text or '')
    table = replace if replace is not None else (read_dictionary().get('replace') or {})
    items = [(str(k), str(v)) for k, v in table.items() if str(k or '').strip()]
    if not text or not items:
        return text
    items.sort(key=lambda pair: len(pair[0]), reverse=True)
    lookup = dict(items)
    pattern = re.compile('|'.join(re.escape(key) for key, _value in items))
    return pattern.sub(lambda match: lookup[match.group(0)], text)


class _DictionarySession:
    """词典替换表包装：``final`` 事件文本先过 ``apply_replacements`` 再交给消费方。

    与 ``RealtimeSession``/``OfflineAsrSession`` 同一外部接口；另起一个 daemon 线程
    转发事件，``closed`` 之后退出，``cancel`` 置停。仅当替换表非空时由
    ``create_session`` 启用，默认路径零开销。
    """

    def __init__(self, inner, replacements):
        self._inner, self._replacements = inner, dict(replacements)
        self.events = queue.Queue()
        self._stop = threading.Event()
        self._task = None

    def start(self):
        self._inner.start()
        # I11a：事件转发泵改经执行器 io 池；取消标记即 _stop。
        self._task = executors.submit('io', self._pump, cancel=self._stop,
                                      label='voice-dict')

    def send(self, pcm):
        self._inner.send(pcm)

    def finish(self):
        self._inner.finish()

    def cancel(self):
        self._stop.set()
        self._inner.cancel()

    def _pump(self):
        while not self._stop.is_set():
            try:
                kind, item, text = self._inner.events.get(timeout=0.2)
            except queue.Empty:
                continue
            if kind == 'final':
                text = apply_replacements(text, self._replacements)
            self.events.put((kind, item, text))
            if kind == 'closed':
                return


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
    started = time.perf_counter()
    outcome = 'error'
    try:
        settings = settings or read_settings()
        dictionary = read_dictionary()
        if (settings.get('backend') or 'offline') != 'offline':
            session = RealtimeSession(settings, connect=connect)
        else:
            import domain.offline_asr_client as offline_asr_client
            hotwords = hotword_text(dictionary)
            if hotwords:
                settings = dict(settings)
                offline = dict(settings.get('offline') or {})
                existing = str(offline.get('hotword') or '').strip()
                offline['hotword'] = ' '.join(part for part in (existing, hotwords) if part)
                settings['offline'] = offline
            fallback = None
            if api_key(settings):
                fallback = lambda merged: RealtimeSession(merged, connect=connect)
            session = offline_asr_client.OfflineAsrSession(settings, fallback=fallback)
        replace = dictionary.get('replace') or {}
        if replace:
            session = _DictionarySession(session, replace)
        outcome = 'ok'
        return session
    finally:
        # 后端与密钥不进字段；只记成败与耗时。
        business_log.log_event('speech_api.create_session', outcome=outcome,
                               cost_ms=round((time.perf_counter() - started) * 1000.0, 1))


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
        self._stop_event = threading.Event()

    def start(self):
        # I11a：会话主流程改经执行器 io 池提交；取消标记复用 _stop_event。
        self.thread = executors.submit('io', self._run, cancel=self._stop_event,
                                       label='voice-realtime')

    def send(self, pcm):
        self.audio.put(bytes(pcm))

    def finish(self):
        self.audio.put(None)

    def cancel(self):
        self.cancelled = True
        self._stop_event.set()
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
        # I11a：实时收包循环走执行器 stream 池（每任务独占线程）；
        # reader.join(timeout) 语义改经 Future.result(timeout)（join 不传播异常）。
        reader = executors.submit('stream', self._read, cancel=self._stop_event,
                                  label='voice-realtime-read')
        try:
            self.socket.send_text(json.dumps(session_update(settings)))
            while True:
                pcm = self.audio.get()
                if pcm is None or self.cancelled:
                    break
                self.socket.send_text(json.dumps({'type': 'input_audio_buffer.append',
                                                  'audio': base64.b64encode(pcm).decode('ascii')}))
            if not self.cancelled:
                self.socket.send_text(json.dumps({'type': 'session.finish'}))
                try:
                    reader.result(timeout=settings['timeout'])
                except Exception:
                    app_logging.swallowed('speech_api realtime reader wait')
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
