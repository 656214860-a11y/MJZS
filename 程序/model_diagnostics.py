"""模型调用的安全诊断事件。

诊断用于定位空正文、协议与配置问题，绝不能变成另一份创作内容或密钥副本。每次调用写入
独立事件文件，避免并发请求竞争 JSONL 追加；文件通过 ``agent.core.save`` 原子落盘。
"""
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from agent.core import save
from diagnostic_capture import redact


_USAGE_KEYS = ('prompt_tokens', 'completion_tokens', 'cached_tokens', 'cache_creation_tokens', 'total_tokens')


def _scrub(meta):
    """服务端回显的字符串一律先脱敏再落盘：诊断文件不能变成凭据副本。"""
    return {str(key): (redact(value) if isinstance(value, str) else value)
            for key, value in dict(meta).items()}


def _metadata(result):
    """补齐兼容调用的响应结构信息，始终不复制任何正文。"""
    meta = dict(result.get('response_meta') or {})
    data = result.get('data')
    if not isinstance(data, dict):
        return meta
    meta.setdefault('response_id', str(data.get('id') or data.get('request_id') or ''))
    meta.setdefault('response_shape', sorted(str(key) for key in data.keys()))
    choices = data.get('choices')
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        choice = choices[0]
        meta.setdefault('finish_reason', str(choice.get('finish_reason') or ''))
        message = choice.get('message') if isinstance(choice.get('message'), dict) else {}
        meta.setdefault('message_fields', sorted(str(key) for key in message.keys()))
        fields = [key for key in ('reasoning_content', 'reasoning', 'analysis')
                  if message.get(key) not in (None, '', [], {})]
        meta.setdefault('reasoning_fields', fields)
        meta.setdefault('reasoning_lengths', {key: len(str(message.get(key) or '')) for key in fields})
    return meta


def event(result, context=None, at=None):
    """从路由结果提取白名单元数据；不返回或保存请求/响应/推理正文。"""
    result = dict(result or {})
    meta = _scrub(_metadata(result))
    usage = dict(result.get('usage') or {})
    stamp = at or datetime.now()
    return {
        'at': stamp.strftime('%Y-%m-%dT%H:%M:%S'),
        'context': {str(key): redact(value) for key, value in dict(context or {}).items()
                    if value not in (None, '')},
        'ok': bool(result.get('ok')),
        'status': result.get('status'),
        'model': str(result.get('model') or meta.get('requested_model') or ''),
        'error_class': str(result.get('error_class') or ''),
        'wire_api': str(meta.get('wire_api') or ''),
        'response_id': str(meta.get('response_id') or ''),
        'finish_reason': str(meta.get('finish_reason') or ''),
        'response_shape': list(meta.get('response_shape') or ()),
        'message_fields': list(meta.get('message_fields') or ()),
        'reasoning_fields': list(meta.get('reasoning_fields') or ()),
        'reasoning_lengths': {str(key): int(value) for key, value in
                              dict(meta.get('reasoning_lengths') or {}).items()},
        'content_length': int(meta.get('content_length') or len(str(result.get('text') or ''))),
        'usage': {key: usage[key] for key in _USAGE_KEYS if key in usage},
    }


def record(folder, result, context=None, at=None):
    """原子保存一条安全事件并返回路径。"""
    stamp = at or datetime.now()
    path = (Path(folder) / 'model_diagnostics'
            / (stamp.strftime('%Y%m%d_%H%M%S_%f') + '_' + uuid4().hex[:8] + '.json'))
    save(path, event(result, context=context, at=stamp))
    return path
