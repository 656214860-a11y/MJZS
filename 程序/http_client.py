"""L1 统一 HTTP 传输：超时必填、有界重试、响应上限、错误码分类、凭据脱敏。

所有调用方经 ``request_json`` 发请求；直接 ``urlopen``／``build_opener`` 由
``tests/architecture/test_http_boundary.py`` 拦截（白名单只减不增）。
返回 ``service_contract.ServiceResult`` 四字段结果；错误码取自 ``error_codes``。

第 34 期第 9 条：``urllib.request`` 连 ssl 一起加载（约 4.4 MB 常驻），
网络栈在函数内按需 import，模块导入零成本。
"""
import json as _json
import random as _random
import time as _time

from error_codes import code_data, lookup
from service_contract import ServiceResult, success

MAX_BODY_BYTES = 32 * 1024 * 1024
ERROR_BODY_MAX_BYTES = 64 * 1024
DEFAULT_RETRY_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})
_CIRCUIT_THRESHOLD = 5
_CIRCUIT_COOLDOWN = 30.0
_HOST_FAILURES = {}

_SENSITIVE_HEADERS = frozenset({'authorization', 'proxy-authorization', 'cookie', 'set-cookie'})


def _classify(status):
    if status == 429:
        return 'E-NET-RATE-LIMIT'
    if status in (401, 403):
        return 'E-AUTH-REJECTED'
    if 500 <= status < 600:
        return 'E-NET-SERVER'
    return 'E-NET-CLIENT'


def _safe_headers(headers):
    return {k: ('[REDACTED]' if str(k).lower() in _SENSITIVE_HEADERS else v)
            for k, v in (headers or {}).items()}


def _circuit_open(host):
    entry = _HOST_FAILURES.get(host)
    return bool(entry and entry['count'] >= _CIRCUIT_THRESHOLD
                and _time.monotonic() - entry['at'] < _CIRCUIT_COOLDOWN)


def _circuit_record(host, failed):
    entry = _HOST_FAILURES.setdefault(host, {'count': 0, 'at': 0.0})
    if failed:
        entry['count'] += 1
        entry['at'] = _time.monotonic()
    else:
        entry['count'] = 0


def _read_limited(response, limit):
    chunks, total = [], 0
    while total <= limit:
        part = response.read(min(65536, limit + 1 - total))
        if not part:
            break
        chunks.append(part)
        total += len(part)
    return b''.join(chunks)[:limit + 1], total > limit


def _default_opener():
    import urllib.request
    from api_endpoints import no_redirect
    return urllib.request.build_opener(no_redirect())


def request_json(method, url, *, headers=None, payload=None, timeout,
                 retries=0, retry_statuses=DEFAULT_RETRY_STATUSES,
                 max_bytes=MAX_BODY_BYTES, allow_retry_post=False,
                 opener=None, sleep=_time.sleep):
    """发一次 JSON 请求；``timeout`` 必填。``payload`` 非空视为 POST。

    重试只在调用方显式给 ``retries>0`` 且状态码可重试时发生；带 body 的
    POST 默认永不重试（计费接口），需 ``allow_retry_post=True`` 显式放行。
    响应体超过 ``max_bytes`` 视为协议错误，不落盘不解析。
    """
    import urllib.error
    import urllib.parse
    import urllib.request

    method = (method or 'GET').upper()
    host = urllib.parse.urlparse(url).hostname or ''
    if _circuit_open(host):
        code = 'E-NET-UNREACHABLE'
        return ServiceResult(False, _describe(code), True,
                             code_data(code, status=None, error_body='', retry_count=0))
    body = None if payload is None else _json.dumps(payload, ensure_ascii=False).encode('utf-8')
    effective = method if body is None else 'POST'
    attempts = 1 + (retries if (allow_retry_post or effective != 'POST') else 0)
    request_headers = dict(headers or {})
    request_headers.setdefault('Content-Type', 'application/json')
    transport = opener if opener is not None else _default_opener()
    last = None
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(url, data=body, headers=request_headers, method=effective)
        try:
            with transport.open(request, timeout=timeout) as response:
                status = getattr(response, 'status', 200)
                declared = response.headers.get('Content-Length') if response.headers else None
                if declared and declared.isdigit() and int(declared) > max_bytes:
                    code = 'E-NET-CLIENT'
                    _circuit_record(host, True)
                    return ServiceResult(False, _describe(code), False,
                                         code_data(code, status=status, error_body='响应体超过上限', retry_count=attempt - 1))
                raw, overflow = _read_limited(response, max_bytes)
                if overflow:
                    code = 'E-NET-CLIENT'
                    _circuit_record(host, True)
                    return ServiceResult(False, _describe(code), False,
                                         code_data(code, status=status, error_body='响应体超过上限', retry_count=attempt - 1))
                _circuit_record(host, False)
                text = raw.decode('utf-8', errors='replace')
                try:
                    parsed = _json.loads(text)
                except ValueError:
                    parsed = None
                return success({'status': status, 'json': parsed, 'text': text,
                                'headers': _safe_headers(response.headers)})
        except urllib.error.HTTPError as exc:
            status = exc.code
            code = _classify(status)
            try:
                error_body = exc.read(ERROR_BODY_MAX_BYTES).decode('utf-8', errors='replace')
            except Exception:
                error_body = ''
            last = (code, status, error_body)
            retryable = lookup(code).retryable and status in retry_statuses
            if not retryable or attempt >= attempts:
                item = lookup(code)
                return ServiceResult(False, f'[{item.code}] {item.user_message}', item.retryable,
                                     code_data(code, status=status, error_body=error_body,
                                               retry_count=attempt - 1, headers=_safe_headers(exc.headers)))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reason = str(exc).lower()
            code = 'E-NET-TIMEOUT' if 'timed out' in reason or 'timeout' in reason or isinstance(exc, TimeoutError) else 'E-NET-UNREACHABLE'
            last = (code, None, str(exc)[:300])
            _circuit_record(host, True)
            if attempt >= attempts:
                item = lookup(code)
                return ServiceResult(False, f'[{item.code}] {item.user_message}', item.retryable,
                                     code_data(code, status=None, error_body=last[2], retry_count=attempt - 1))
        if attempt < attempts:
            sleep(min(0.5 * (2 ** (attempt - 1)), 8.0) + _random.uniform(0, 0.25))
    item = lookup(last[0] if last else 'E-UNKNOWN')
    return ServiceResult(False, f'[{item.code}] {item.user_message}', item.retryable,
                         code_data(item.code, status=last[1] if last else None,
                                   error_body=last[2] if last else '', retry_count=attempts - 1))


def _describe(code):
    item = lookup(code)
    return f'[{item.code}] {item.user_message}'
