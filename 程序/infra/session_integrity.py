"""本机账户会话的文件完整性校验。"""

import hashlib
import hmac
import json
import secrets
from pathlib import Path

from agent.core import save_bytes
from agent.publication import access
from infra import model_secrets

__all__ = ['fields', 'seal', 'verify']

_KEY_FILE = '.mac_key.dpapi'
_KEY_SIZE = 32
_METADATA = frozenset(('_mac', '_mac_key_id'))
_LABEL = '账户会话完整性密钥'
_SESSION_LABEL = '账户会话'


def _key_path(path=None):
    directory = Path(path).parent if path is not None else Path(__file__).resolve().parents[1] / 'private' / '账户'
    return directory / _KEY_FILE


def _read_key(target):
    try:
        blob = target.read_bytes()
        if not model_secrets.looks_like_blob(blob):
            return None
        key = model_secrets.protect(blob, decrypt=True, label=_LABEL)
        return key if len(key) == _KEY_SIZE else None
    except (OSError, ValueError):
        return None


def is_sealed_blob(raw):
    """会话文件是否为 DPAPI 密文；account_store 经此入口，不直依赖 model_secrets。"""
    return model_secrets.looks_like_blob(raw)


def protect_session(payload, decrypt=False):
    return model_secrets.protect(payload, decrypt=decrypt, label=_SESSION_LABEL)


def fields(data):
    return {key: value for key, value in data.items() if key not in _METADATA}


def _key_id(key):
    return hashlib.sha256(key).hexdigest()[:16]


def _digest(data, key):
    payload = json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hmac.new(key, payload.encode('utf-8'), hashlib.sha256).hexdigest()


def seal(data, path=None):
    """签署会话。首次保存或重新登录时补建本机密钥。"""
    target = _key_path(path)
    with access():
        key = _read_key(target)
        if key is None:
            key = secrets.token_bytes(_KEY_SIZE)
            target.parent.mkdir(parents=True, exist_ok=True)
            save_bytes(target, model_secrets.protect(key, label=_LABEL))
        payload = fields(data)
        return {**payload, '_mac': _digest(payload, key), '_mac_key_id': _key_id(key)}


def verify(data, path=None):
    """验证会话完整性。校验路径永远不创建密钥。"""
    if not isinstance(data, dict):
        return False
    mac, key_id = data.get('_mac'), data.get('_mac_key_id')
    if not isinstance(mac, str) or not isinstance(key_id, str) or not mac.isascii() or not key_id.isascii():
        return False
    key = _read_key(_key_path(path))
    return key is not None and hmac.compare_digest(key_id, _key_id(key)) and hmac.compare_digest(
        mac, _digest(fields(data), key))
