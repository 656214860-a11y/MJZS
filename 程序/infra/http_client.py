"""L1 统一 HTTP 传输：超时必填、有界重试、响应上限、错误码分类、凭据脱敏。

通用请求使用 ``request_json`` 或 ``request_bytes``，旧版 ComfyUI 本机协议使用 ``LocalComfyClient``；
直接 ``urlopen``／``build_opener`` 由 ``tests/architecture/test_http_boundary.py``
拦截（白名单只减不增）。返回 ``service_contract.ServiceResult`` 四字段结果；
错误码取自 ``contract.error_codes``。

第 34 期第 9 条：``urllib.request`` 连 ssl 一起加载（约 4.4 MB 常驻），
网络栈在函数内按需 import，模块导入零成本。
"""
import json as _json
import random as _random
import time as _time
import uuid
from urllib.parse import urlparse

import urllib.parse as _parse

from contract.error_codes import code_data, code_of, lookup
from contract.infra_errors import ConfigError, CorruptDataError, NetworkError
from contract.platform_tools import current_execution
from contract.service_contract import ServiceResult, success

import infra.metrics as metrics

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


def read_limited(response, limit):
    chunks, total = [], 0
    while total <= limit:
        part = response.read(min(65536, limit + 1 - total))
        if not part:
            break
        chunks.append(part)
        total += len(part)
    return b''.join(chunks)[:limit + 1], total > limit


def _default_opener():
    from contract.platform_tools import RequestsJsonOpener
    return RequestsJsonOpener()


def _local_comfy_opener():
    """ComfyUI 本机连接绕过系统代理并拒绝重定向。"""
    from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener

    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            raise ConfigError('拒绝接口跳转')

    return build_opener(ProxyHandler({}), NoRedirect)


class LocalComfyClient:
    def __init__(self,url):
        p=urlparse(url)
        if p.scheme!='http' or p.hostname not in ('127.0.0.1','localhost','::1') or p.username or p.password:raise ConfigError('仅支持本机ComfyUI地址')
        self.url=url.rstrip('/');self.opener=_local_comfy_opener()
    def request(self,path,data=None,raw=False,content_type='application/json'):
        from urllib.error import HTTPError, URLError
        from urllib.request import Request
        from contract.platform_tools import current_execution
        control = current_execution()
        timeout = control.remaining(30) if control is not None else 30
        if isinstance(data,dict):data=_json.dumps(data).encode()
        try:
            with self.opener.open(Request(self.url+path,data=data,headers={'Content-Type':content_type}),timeout=timeout) as r:
                body=r.read(64*1024*1024+1)
        except HTTPError as e:
            hint='请等待ComfyUI启动完成，并核对窗口中的地址与ComfyUI实际服务地址一致。' if e.code in (502,503,504) else '请查看ComfyUI的错误信息。'
            if path=='/prompt':hint+=' 本次提交结果不确定，请先在ComfyUI核实任务，避免重复生成。'
            raise NetworkError(f'ComfyUI返回HTTP {e.code}：{self.url}{path}\n{hint} 本机连接已绕过系统代理。', code='E-NET-SERVER', detail=e.code) from None
        except (URLError,TimeoutError,OSError) as e:
            hint='请确认ComfyUI已经启动，并将此处地址改为它实际使用的本机地址。'
            if path=='/prompt':hint+=' 提交结果不确定，请先核实ComfyUI任务队列。'
            raise NetworkError(f'无法连接ComfyUI：{self.url}\n{hint}', detail=str(e)) from None
        if len(body)>64*1024*1024:raise CorruptDataError('返回文件超过64MB')
        if raw and control is not None:control.checkpoint()
        return body if raw else _json.loads(body)
    def upload(self,path):
        content=path.read_bytes()
        if len(content)>20*1024*1024:raise CorruptDataError('参考图超过20MB：'+path.name, detail=str(path))
        boundary=uuid.uuid4().hex;name='drama_'+uuid.uuid4().hex+path.suffix.lower()
        body=(f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{name}"\r\nContent-Type: application/octet-stream\r\n\r\n').encode()+content+f'\r\n--{boundary}--\r\n'.encode()
        result=self.request('/upload/image',body,content_type='multipart/form-data; boundary='+boundary)
        return '/'.join(x for x in (result.get('subfolder'),result['name']) if x)

_OPTION_KEYS = frozenset({'retries', 'retry_statuses', 'max_bytes',
                          'allow_retry_post', 'opener', 'sleep'})


def _request(method, url, *, headers=None, payload=None, timeout, caller='request', **opts):
    """共用出站内核：超时必填、有界重试、响应上限、错误码分类、凭据脱敏、熔断。

    ``payload`` 非空序列化为 JSON body 并强制 POST；成功返回
    ``success({'status', 'body': bytes, 'headers'})``，失败返回带
    ``error_code`` 的 ``ServiceResult``。``caller`` 仅用于 TypeError 文案。
    """
    import urllib.error
    import urllib.parse
    import urllib.request

    unknown = set(opts) - _OPTION_KEYS
    if unknown:
        raise TypeError('%s() got unexpected keyword arguments: %s'
                        % (caller, ', '.join(sorted(unknown))))
    retries = opts.get('retries', 0)
    retry_statuses = opts.get('retry_statuses', DEFAULT_RETRY_STATUSES)
    max_bytes = opts.get('max_bytes', MAX_BODY_BYTES)
    allow_retry_post = opts.get('allow_retry_post', False)
    opener = opts.get('opener')
    sleep = opts.get('sleep')
    control = current_execution()
    if control is not None:
        control.checkpoint()

    method = (method or 'GET').upper()
    host = _parse.urlparse(url).hostname or ''
    if _circuit_open(host):
        code = 'E-NET-UNREACHABLE'
        return ServiceResult(False, _describe(code), True,
                             code_data(code, status=None, error_body='', retry_count=0))
    body = None if payload is None else _json.dumps(payload, ensure_ascii=False).encode('utf-8')
    effective = method if body is None else 'POST'
    non_replayable_post = effective == 'POST' and not allow_retry_post
    attempts = 1 + (0 if non_replayable_post else retries)
    request_headers = dict(headers or {})
    transport = opener if opener is not None else _default_opener()
    last = None
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(url, data=body, headers=request_headers, method=effective)
        attempt_timeout = timeout if control is None else control.remaining(timeout)
        retry_after = None
        try:
            with transport.open(request, timeout=attempt_timeout) as response:
                status = getattr(response, 'status', 200)
                declared = response.headers.get('Content-Length') if response.headers else None
                if declared and declared.isdigit() and int(declared) > max_bytes:
                    code = 'E-NET-CLIENT'
                    _circuit_record(host, True)
                    return ServiceResult(False, _describe(code), False,
                                         code_data(code, status=status, error_body='响应体超过上限', retry_count=attempt - 1))
                raw, overflow = read_limited(response, max_bytes)
                if overflow:
                    code = 'E-NET-CLIENT'
                    _circuit_record(host, True)
                    return ServiceResult(False, _describe(code), False,
                                         code_data(code, status=status, error_body='响应体超过上限', retry_count=attempt - 1))
                _circuit_record(host, False)
                return success({'status': status, 'body': raw,
                                'headers': _safe_headers(response.headers)})
        except urllib.error.HTTPError as exc:
            status = exc.code
            code = _classify(status)
            error_body = ''
            error_json = None
            try:
                error_body = exc.read(ERROR_BODY_MAX_BYTES).decode('utf-8', errors='replace')
                error_json = _json.loads(error_body)
            except Exception:
                error_body = error_body or ''
            finally:
                exc.close()
            last = (code, status, error_body)
            retryable = lookup(code).retryable and status in retry_statuses
            if not retryable or attempt >= attempts:
                item = lookup(code)
                data = code_data(code, status=status, error_body=error_body, error_json=error_json,
                                 retry_count=attempt - 1, headers=_safe_headers(exc.headers))
                if non_replayable_post and (status == 408 or status >= 500):
                    return _unknown_submission(item, data)
                return ServiceResult(False, f'[{item.code}] {item.user_message}', item.retryable, data)
            from infra.api_endpoints import _retry_after_seconds
            retry_after = _retry_after_seconds(exc.headers)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reason = str(exc).lower()
            code = 'E-NET-TIMEOUT' if 'timed out' in reason or 'timeout' in reason or isinstance(exc, TimeoutError) else 'E-NET-UNREACHABLE'
            last = (code, None, str(exc)[:300])
            _circuit_record(host, True)
            if attempt >= attempts:
                item = lookup(code)
                data = code_data(code, status=None, error_body=last[2], retry_count=attempt - 1)
                if non_replayable_post:
                    return _unknown_submission(item, data)
                return ServiceResult(False, f'[{item.code}] {item.user_message}', item.retryable, data)
        if attempt < attempts:
            delay = (min(retry_after, 30) if retry_after is not None
                     else min(0.5 * (2 ** min(attempt - 1, 4)), 8.0) + _random.uniform(0, 0.25))
            if control is None:
                (sleep or _time.sleep)(delay)
            else:
                control.wait_for_retry(delay, sleep=sleep)
    item = lookup(last[0] if last else 'E-UNKNOWN')
    return ServiceResult(False, f'[{item.code}] {item.user_message}', item.retryable,
                         code_data(item.code, status=last[1] if last else None,
                                   error_body=last[2] if last else '', retry_count=attempts - 1))


def _unknown_submission(item, data):
    data['acceptance'] = 'unknown'
    return ServiceResult(False, f'[{item.code}] 提交结果待核实，请先查询供应商状态或用量。', False, data)


def request_json(method, url, *, headers=None, payload=None, timeout, **opts):
    """发一次 JSON 请求；``timeout`` 必填。``payload`` 非空视为 POST。

    可选项经 ``opts``：``retries``、``retry_statuses``、``max_bytes``、
    ``allow_retry_post``、``opener``、``sleep``。重试只在调用方显式给
    ``retries>0`` 且状态码可重试时发生；带 body 的 POST 默认永不重试
    （计费接口），仅已确认可安全重放的操作可传 ``allow_retry_post=True``。响应体超过
    ``max_bytes`` 视为协议错误，不落盘不解析。
    """
    request_headers = dict(headers or {})
    request_headers.setdefault('Content-Type', 'application/json')
    started = _time.monotonic()
    result = _request(method, url, headers=request_headers, payload=payload,
                      timeout=timeout, caller='request_json', **opts)
    metrics.observe('http.request', (_time.monotonic() - started) * 1000.0,
                    provider=_parse.urlparse(url).hostname or '',
                    outcome='ok' if result.ok else 'error',
                    error_code=code_of(result))
    if not result.ok:
        return result
    data = result.data if isinstance(result.data, dict) else {}
    text = (data.get('body') or b'').decode('utf-8', errors='replace')
    try:
        parsed = _json.loads(text)
    except ValueError:
        parsed = None
    return success({'status': data.get('status', 200), 'json': parsed, 'text': text,
                    'headers': data.get('headers')})


def request_bytes(method, url, *, headers=None, payload=None, timeout, **opts):
    """发一次请求并返回原始响应字节；``timeout`` 必填，不做文本解码。

    与 ``request_json`` 共用同一传输内核（重试／熔断／响应上限／错误码／
    凭据脱敏）；成功 ``data`` 为 ``{'status', 'body': bytes, 'headers'}``，
    供音频等二进制响应使用。``payload`` 非空序列化为 JSON body 并强制
    POST（与 ``request_json`` 同口径），此时 ``Content-Type`` 默认
    ``application/json``（调用方可覆盖）；可选项同 ``request_json``。
    """
    request_headers = dict(headers or {})
    if payload is not None:
        request_headers.setdefault('Content-Type', 'application/json')
    started = _time.monotonic()
    result = _request(method, url, headers=request_headers, payload=payload,
                      timeout=timeout, caller='request_bytes', **opts)
    metrics.observe('http.request', (_time.monotonic() - started) * 1000.0,
                    provider=_parse.urlparse(url).hostname or '',
                    outcome='ok' if result.ok else 'error',
                    error_code=code_of(result))
    return result


def _describe(code):
    item = lookup(code)
    return f'[{item.code}] {item.user_message}'
