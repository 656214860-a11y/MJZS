"""REQ-S01-71：剧本准备页语音输入的云端识别。

默认走阿里云百炼 ``qwen3-asr-flash``（OpenAI 兼容 ``/chat/completions``，音频以 data URI 内联）。
服务地址、模型、密钥变量名与语言都可在 ``data/语音识别.json`` 覆盖（升级保留），不改代码即可换模型；
密钥只按变量名从模型池取，不写进设置文件、日志或异常文字。
"""
import base64
import json
from pathlib import Path
from urllib.parse import urlparse

import file_cache
import platform_tools

PROGRAM = Path(__file__).resolve().parent
USER_FILE = PROGRAM / 'data' / '语音识别.json'
DEFAULTS = {
    'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    'model': 'qwen3-asr-flash',
    'key_env': 'DASHSCOPE_API_KEY',
    'language': 'zh',
    'max_seconds': 180,          # qwen3-asr-flash 单段上限 5 分钟／10 MB，留足余量
    'timeout': 60,
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


def api_key(settings=None):
    import model_pool
    return model_pool.named_key((settings or read_settings())['key_env'])


def missing_reason(settings=None):
    """能发识别请求时返回空串，否则返回一句给状态栏的原因。"""
    settings = settings or read_settings()
    if not api_key(settings):
        return '没有配置语音识别密钥 %s：请在「模型管理」添加阿里云百炼密钥，或在 data/语音识别.json 改用其它服务' % settings['key_env']
    return ''


def request_body(wav, settings):
    audio = 'data:audio/wav;base64,' + base64.b64encode(bytes(wav)).decode('ascii')
    return {'model': settings['model'], 'stream': False,
            'messages': [{'role': 'user', 'content': [{'type': 'input_audio', 'input_audio': {'data': audio}}]}],
            'asr_options': {'language': settings['language'], 'enable_itn': True}}


def _endpoint(settings):
    base = str(settings['base_url']).strip().rstrip('/')
    parsed = urlparse(base)
    local = parsed.scheme == 'http' and parsed.hostname in ('127.0.0.1', 'localhost', '::1')
    if parsed.scheme != 'https' and not local:
        raise ValueError('语音识别地址必须是 HTTPS（本机服务可用 HTTP）')
    return base if base.endswith('/chat/completions') else base + '/chat/completions'


def _text(payload):
    try:
        content = payload['choices'][0]['message']['content']
    except (KeyError, IndexError, TypeError):
        raise ValueError('识别服务返回格式不对') from None
    if isinstance(content, list):
        content = ''.join(part.get('text', '') for part in content if isinstance(part, dict))
    return str(content or '').strip()


def transcribe(wav, *, settings=None, key=None, opener=None):
    """把 WAV 字节转成文字；失败抛带中文原因的 ValueError。"""
    import urllib.error
    settings = settings or read_settings()
    key = key or api_key(settings)
    if not key:
        raise ValueError(missing_reason(settings))
    url = _endpoint(settings)
    data = json.dumps(request_body(wav, settings)).encode('utf-8')
    headers = {'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'}
    try:
        with (opener or platform_tools.open_https)(url, timeout=settings['timeout'], data=data, headers=headers) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            raise ValueError('密钥无效或没有开通 %s（HTTP %d）' % (settings['model'], error.code)) from None
        raise ValueError('识别服务出错（HTTP %d）' % error.code) from None
    except (urllib.error.URLError, OSError) as error:
        raise ValueError('连不上识别服务：%s' % (getattr(error, 'reason', '') or type(error).__name__)) from None
    except ValueError:
        raise ValueError('识别服务返回的不是 JSON') from None
    return _text(payload)
