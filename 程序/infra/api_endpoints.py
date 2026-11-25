"""Shared endpoint validation; editing or saving never contacts a service."""
import hashlib
import random
import time
import threading
import json
import infra.app_logging as app_logging
from datetime import datetime, timezone
from infra.model_metering import REPLAYABLE_RETRY_STATUS
# 第 34 期第 9 条：`urllib.request` 连 ssl 一起加载（约 4.4 MB 常驻），探测函数里再 import。
from urllib.parse import urlparse

def normalize_url(value):
    value=str(value).strip().rstrip('/')
    parsed=urlparse(value)
    try:parsed.port
    except ValueError:raise ValueError('API 地址端口无效') from None
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or any(c.isspace() for c in value):
        raise ValueError('请填写完整 API 根地址，不要包含密钥、空格或查询参数')
    if parsed.scheme!='https' and not (parsed.scheme=='http' and parsed.hostname in ('127.0.0.1','localhost','::1')):
        raise ValueError('请使用 HTTPS 地址；本机服务可使用 HTTP')
    return value

def configured_key(config):
    """Read credentials for this configuration without changing process globals."""
    import os
    from pathlib import Path
    if not isinstance(config, dict):
        raise ValueError('接口配置无效，请在 API 设置中重新保存')
    name=config.get('key_env','VIDEO_API_KEY')
    key=''
    if config.get('key_provider') == 'model_pool':
        # 新会话只保存变量名，不再把程序目录的明文 .env 路径写进项目配置。
        # 这里直接读 DPAPI 存储，避免 model_pool（它兼容读取旧配置时会调用本函数）形成导入环。
        import infra.model_secrets as model_secrets
        key=model_secrets.load(name)
    elif config.get('project_dir'):
        # 项目目录的 .env 只在第一次迁进本机加密存储（文件不删），之后一律读加密存储。
        import infra.model_secrets as model_secrets
        root=config.get('secret_root')
        model_secrets.import_env_keys(Path(config['project_dir'])/'.env',root=root)
        key=model_secrets.load(name,root=root)
    else:
        key=os.environ.get(name,'').strip()
    if not key or key in ('replace_me','<YOUR_API_KEY>') or not key.isascii() or any(c.isspace() for c in key):
        raise ValueError('当前接口缺少有效 API Key，请在 API 设置中填写并保存')
    return key


def probe_endpoint(base_url, timeout=8):
    """无害的连通性探测：只访问根地址，不发送密钥，不提交任务。"""
    from contract.platform_tools import probe_http_endpoint
    return probe_http_endpoint(base_url, timeout=timeout)


def no_redirect():
    """不跟随重定向的处理器实例（唯一实现，R2178 J13）：密钥与请求体不会被带到别处。

    第 34 期第 9 条：惰性建类——只有真要发 HTTP 时才 import urllib.request。
    """
    from urllib.request import HTTPRedirectHandler

    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    return NoRedirect()


def probe_message(base_url):
    """按探测结果区分鉴权、路径与连接错误；探测异常由调用方处理。"""
    result = probe_endpoint(base_url)
    if result.get('reachable') and result.get('code') == 404:
        return '接口可达（HTTP 404，请检查接口地址和路径）'
    if result.get('reachable') and result.get('code') in (401, 403):
        return '接口可达（HTTP %s，需密钥）' % result['code']
    if result.get('reachable'):
        return '接口可达（HTTP %s）' % result['code']
    return '连接失败：' + str(result.get('error', '未知错误'))

# ── model transport helpers moved from model_pool (R2458+) ──
def _http_error_kind(status):
    """HTTP 状态码归成受控错误类别：鉴权／服务端／请求本身，供界面按类给提示。"""
    try:
        code = int(status)
    except (TypeError, ValueError):
        return 'client'
    if code in (401, 403):
        return 'auth'
    if code >= 500:
        return 'server'
    return 'client'


MAX_REPLAY_ATTEMPTS = 3
RETRY_BASE_SECONDS = 0.25
RETRY_MAX_SECONDS = 3.0
RETRY_AFTER_MAX_SECONDS = 60.0
RATE_SLEEP_MAX_SECONDS = 300.0
RATE_SLEEP_SLICE_SECONDS = 0.5
RESPONSE_BODY_MAX_BYTES = 32 * 1024 * 1024
STREAM_BUFFER_MAX_BYTES = 8 * 1024 * 1024
REQUIRE_CERTIFIED_FOR_UNATTENDED = False

_RATE_LIMIT_LOCK = threading.Lock()
_HOST_RATE_LIMITS = {}
_CLOCK = time.monotonic
_SLEEP = time.sleep


def _credential_digest(credential):
    """凭据标识（key_env 名或 Authorization 头值）只以不可逆摘要进入桶键，明文不进内存表。"""
    text = str(credential or '').strip()
    if not text:
        return ''
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]


def _bucket_key(host, credential=None):
    digest = _credential_digest(credential)
    return host + '#' + digest if digest else host


class _RateBucket:
    def __init__(self, requests_per_minute):
        self.interval = 60.0 / max(1, int(requests_per_minute))
        self.next = 0.0

    def set_interval(self, requests_per_minute):
        """rpm 变更只更新间隔，保留已预约的 next，避免重置后突发放行。"""
        self.interval = 60.0 / max(1, int(requests_per_minute))

    def wait(self, now):
        wait = max(0.0, self.next - now)
        self.next = now + wait + self.interval
        return wait


def set_host_rate_limit(host, requests_per_minute, credential=None):
    """按主机名（可叠加凭据摘要）设置每分钟请求上限；0 表示清除限制。这是 LiteLLM RPM 的零依赖等价物。"""
    host_key = str(host or '').strip().lower()
    if not host_key:
        return
    key = _bucket_key(host_key, credential)
    with _RATE_LIMIT_LOCK:
        if int(requests_per_minute) <= 0:
            _HOST_RATE_LIMITS.pop(key, None)
            return
        _HOST_RATE_LIMITS[key] = _RateBucket(requests_per_minute)


def _sleep_rate_delay(delay, control=None):
    """分片睡眠；分片在锁外，片间 checkpoint 保证可取消，等待不再被 RETRY_MAX_SECONDS 截断。"""
    remaining = min(max(0.0, delay), RATE_SLEEP_MAX_SECONDS)
    while remaining > 0:
        if control is not None and hasattr(control, 'checkpoint'):
            control.checkpoint()
        slice_ = min(remaining, RATE_SLEEP_SLICE_SECONDS)
        _SLEEP(slice_)
        remaining -= slice_


def _wait_for_rate_limit(url, control=None, credential=None):
    from urllib.parse import urlsplit
    try:
        host = (urlsplit(url).hostname or '').lower()
    except ValueError:
        return
    if not host:
        return
    with _RATE_LIMIT_LOCK:
        bucket = _HOST_RATE_LIMITS.get(_bucket_key(host, credential))
        delay = bucket.wait(_CLOCK()) if bucket is not None else 0.0
    if delay > 0:
        _sleep_rate_delay(delay, control)


def wait_for_rpm(base_url, rpm, control=None, credential=None):
    """按模型记录里的 rpm 做本地限流；0/空表示不限制。credential 区分同主机不同密钥的桶。"""
    from urllib.parse import urlsplit
    try:
        host = (urlsplit(base_url or '').hostname or '').lower()
    except ValueError:
        return
    rpm = int(rpm or 0)
    if not host or rpm <= 0:
        return
    key = _bucket_key(host, credential)
    with _RATE_LIMIT_LOCK:
        bucket = _HOST_RATE_LIMITS.get(key)
        if bucket is None:
            bucket = _RateBucket(rpm)
            _HOST_RATE_LIMITS[key] = bucket
        else:
            bucket.set_interval(rpm)
        delay = bucket.wait(_CLOCK())
    if delay > 0:
        _sleep_rate_delay(delay, control)


def _retry_after_seconds(headers):
    """读取 Retry-After（秒或 HTTP 日期），读不出来返回 None。"""
    if not headers:
        return None
    get = getattr(headers, 'get', None)
    if not callable(get):
        return None
    value = get('Retry-After') or get('retry-after')
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.isascii() and text.isdigit():
            return int(text)
        from email.utils import parsedate_to_datetime
        from datetime import timezone
        parsed = parsedate_to_datetime(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return max(0, int((parsed - now).total_seconds()))
    except (TypeError, ValueError, OverflowError):
        return None


def _retry_delay(attempt, retry_after=None, jitter=True):
    """有 Retry-After 优先遵守（单独上限 60 秒），否则指数退避加真随机抖动；封顶避免测试与交互卡死。"""
    if retry_after is not None:
        return max(0, min(int(retry_after), RETRY_AFTER_MAX_SECONDS))
    base = RETRY_BASE_SECONDS * (2 ** max(0, attempt - 1))
    spread = base * random.uniform(0.5, 1.5) if jitter else 0.0
    return min(RETRY_MAX_SECONDS, base + spread)


def _wait_before_retry(attempt, retry_after, control=None, jitter=True):
    delay = _retry_delay(attempt, retry_after, jitter=jitter)
    if delay <= 0:
        return
    if control is None:
        _SLEEP(delay)
    else:
        control.wait_for_retry(delay, sleep=None if _SLEEP is time.sleep else _SLEEP)


@app_logging.timed('model.http', 30000)
def http_transport(url, payload, headers, timeout, opener=None, attempt_budget=None):
    """模型供应商通用 HTTP 传输（payload 为 None 时发只读 GET）；按结果种类计数（成功／network／bug／HTTP 状态），不改变返回。"""
    result = _http_transport(url, payload, headers, timeout, opener=opener, attempt_budget=attempt_budget)
    app_logging.count('model.http.' + ('ok' if result.get('ok') else str(result.get('kind') or result.get('status'))))
    return result


HTTP_USER_AGENT = 'ManjuAssistant/1.0'


def _request_headers(headers):
    """补默认 User-Agent；Cloudflare 等网关会以 error 1010 拒绝 urllib 默认签名。"""
    merged = dict(headers or {})
    if not any(str(name).lower() == 'user-agent' for name in merged):
        merged['User-Agent'] = HTTP_USER_AGENT
    return merged


_SECRET_HEADER_HINTS = ('auth', 'key', 'token', 'secret')


def _scrub_error_detail(detail, headers):
    """错误体进 UI／任务 JSON 之前去掉凭据：先按请求头里的真实值替换，再过通用脱敏正则。

    网关可能原样回显请求头；正则只认 ``key=``／``Bearer`` 等写法，裸 ``sk-…`` 命中不了。"""
    for name, value in (headers or {}).items():
        if not any(hint in str(name).lower() for hint in _SECRET_HEADER_HINTS):
            continue
        token = str(value).strip()
        if token.lower().startswith('bearer '):
            token = token[7:].strip()
        if len(token) >= 6:
            detail = detail.replace(token, '[已脱敏]')
    return app_logging.redact(detail)


def _content_length_exceeded(headers, limit):
    """Content-Length 已超过上限时先拒读，避免把超大响应整段读进内存。"""
    if not headers:
        return False
    get = getattr(headers, 'get', None)
    if not callable(get):
        return False
    try:
        length = int(get('Content-Length') or get('content-length') or 0)
    except (TypeError, ValueError):
        return False
    return length > int(limit)


def _declared_content_length(headers):
    """服务端声明的 Content-Length；无头或不是数字时返回 None（如分块编码）。"""
    get = getattr(headers, 'get', None) if headers else None
    if not callable(get):
        return None
    try:
        return int(get('Content-Length') or get('content-length') or 0)
    except (TypeError, ValueError):
        return None


def _limited_read(response, limit):
    """读取响应体，最多 limit 字节；超限立即报错而不是继续读。"""
    raw = response.read(int(limit) + 1)
    if len(raw) > int(limit):
        return raw, False
    return raw, True


def _decode_response_body(raw, headers, limit):
    """仅支持服务端在 Accept-Encoding 下常见的 gzip/deflate；解压后同样受字节上限约束。"""
    if not headers:
        return raw
    get = getattr(headers, 'get', None)
    if not callable(get):
        return raw
    encoding = str(get('Content-Encoding') or get('content-encoding') or '').strip().lower()
    if not encoding or encoding == 'identity':
        return raw
    import gzip
    import io
    import zlib
    if encoding in ('gzip', 'x-gzip'):
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
            data = stream.read(int(limit) + 1)
    elif encoding == 'deflate':
        try:
            decompressor = zlib.decompressobj()
            data = decompressor.decompress(raw, int(limit) + 1)
        except zlib.error:
            decompressor = zlib.decompressobj(-zlib.MAX_WBITS)
            data = decompressor.decompress(raw, int(limit) + 1)
    else:
        return raw
    if len(data) > int(limit):
        raise ValueError('解压后的响应体超过 %d 字节上限' % int(limit))
    return data


def _header_credential(headers):
    """从请求头取 Authorization 值作为凭据标识；只进摘要，不落明文。"""
    if not headers:
        return None
    get = getattr(headers, 'get', None)
    if callable(get):
        return get('Authorization') or get('authorization')
    try:
        for name, value in headers:
            if str(name).lower() == 'authorization':
                return value
    except (TypeError, ValueError):
        pass
    return None


def _http_transport(url, payload, headers, timeout, opener=None, attempt_budget=None):
    """模型供应商通用 HTTP 传输；仅在实际请求时加载网络栈。"""
    import http.client
    import ssl
    import urllib.error
    import urllib.request

    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode('utf-8')
    request = urllib.request.Request(url, data=body, headers=_request_headers(headers), method='GET' if body is None else 'POST')
    from contract.platform_tools import current_execution
    control = current_execution()
    error_detail_cache = {}
    retry_count = 0
    retry_after = None
    if attempt_budget is not None and attempt_budget[0] <= 0:
        return {'ok': False, 'status': 0, 'kind': 'network',
                'error': '请求总尝试次数已达上限', 'retry_count': retry_count,
                'retry_after': retry_after, 'error_class': 'network'}
    limit = MAX_REPLAY_ATTEMPTS if attempt_budget is None else min(MAX_REPLAY_ATTEMPTS, int(attempt_budget[0]))
    credential = _header_credential(headers)
    for attempt in range(1, limit + 1):
        _wait_for_rate_limit(url, control, credential=credential)
        attempt_timeout = timeout if control is None else control.remaining(timeout)
        if attempt_budget is not None:
            attempt_budget[0] -= 1
        try:
            with (opener or _http_opener)().open(request, timeout=attempt_timeout) as response:
                status = getattr(response, 'status', 200)
                if _content_length_exceeded(response.headers, RESPONSE_BODY_MAX_BYTES):
                    return {'ok': False, 'status': status, 'kind': 'client',
                            'error': '响应体超过 %d 字节上限，已拒绝读取' % RESPONSE_BODY_MAX_BYTES,
                            'retry_count': retry_count, 'retry_after': retry_after, 'error_class': 'protocol'}
                raw, ok = _limited_read(response, RESPONSE_BODY_MAX_BYTES)
                if not ok:
                    return {'ok': False, 'status': status, 'kind': 'client',
                            'error': '响应体超过 %d 字节上限，已拒绝读取' % RESPONSE_BODY_MAX_BYTES,
                            'retry_count': retry_count, 'retry_after': retry_after, 'error_class': 'protocol'}
                declared = _declared_content_length(response.headers)
                if declared is not None and len(raw) < declared:
                    if attempt < limit:   # 声明长度没读满＝连接中途断开，按网络故障重放
                        retry_count += 1
                        _wait_before_retry(attempt, None, control)
                        continue
                    return {'ok': False, 'status': 0, 'kind': 'network',
                            'error': 'IncompleteRead：响应体只收到 %d 字节（声明 %d 字节），连接提前断开'
                                     % (len(raw), declared),
                            'retry_count': retry_count, 'retry_after': retry_after,
                            'error_class': 'network'}
                try:
                    raw = _decode_response_body(raw, response.headers, RESPONSE_BODY_MAX_BYTES)
                except ValueError as exc:
                    return {'ok': False, 'status': status, 'kind': 'client', 'error': str(exc),
                            'retry_count': retry_count, 'retry_after': retry_after, 'error_class': 'protocol'}
                if status in REPLAYABLE_RETRY_STATUS and attempt < limit:
                    retry_count += 1
                    retry_after = _retry_after_seconds(response.headers)
                    _wait_before_retry(attempt, retry_after, control)
                    continue
                try:
                    data = json.loads(raw or b'{}')
                except ValueError as exc:
                    # 截断响应体：连接中途断开只读到半截 JSON，与断线同属传输失败，可重试。
                    if attempt < limit:
                        retry_count += 1
                        _wait_before_retry(attempt, None, control)
                        continue
                    return {'ok': False, 'status': 0, 'kind': 'network',
                            'error': type(exc).__name__ + '：' + str(exc),
                            'retry_count': retry_count, 'retry_after': retry_after, 'error_class': 'network'}
                return {'ok': True, 'status': status, 'data': data,
                        'retry_count': retry_count, 'retry_after': retry_after, 'error_class': ''}
        except urllib.error.HTTPError as exc:
            detail = error_detail_cache.get(id(exc))
            if detail is None:
                detail = _scrub_error_detail(exc.read()[:400].decode('utf-8', 'replace'), headers)
                error_detail_cache[id(exc)] = detail
            if exc.code in REPLAYABLE_RETRY_STATUS and attempt < limit:
                retry_count += 1
                retry_after = _retry_after_seconds(exc.headers)
                _wait_before_retry(attempt, retry_after, control)
                continue
            return {'ok': False, 'status': exc.code, 'kind': _http_error_kind(exc.code),
                    'error': 'HTTP ' + str(exc.code) + '：' + detail,
                    'retry_count': retry_count, 'retry_after': retry_after,
                    'error_class': _http_error_kind(exc.code)}
        except (OSError, http.client.HTTPException) as exc:   # 含 URLError；读响应时的超时／断线不经它包装，同属网络问题
            if attempt < limit:
                retry_count += 1
                stable_tls = isinstance(getattr(exc, 'reason', None), ssl.SSLEOFError)
                _wait_before_retry(attempt, None, control, jitter=not stable_tls)
                continue
            return {'ok': False, 'status': 0, 'kind': 'network', 'error': type(exc).__name__ + '：' + str(exc),
                    'retry_count': retry_count, 'retry_after': retry_after, 'error_class': 'network'}
        except Exception as exc:
            return {'ok': False, 'status': 0, 'kind': 'bug',
                    'error': type(exc).__name__ + '：' + str(exc),
                    'retry_count': retry_count, 'retry_after': retry_after, 'error_class': 'bug'}


def http_stream(url, payload, headers, timeout, on_chunk, cancelled=None, opener=None):
    """OpenAI 兼容 SSE 流（include_usage 的用量在最后一个空 choices 分片）；异常由调用方回退普通请求。"""
    import urllib.error
    import urllib.request
    from contract.platform_tools import current_execution
    control = current_execution()
    if control is not None:
        timeout = control.remaining(timeout)
    if cancelled and cancelled():
        return {'ok': False, 'status': 0, 'error': '请求已取消'}
    body = dict(payload or {})
    body['stream'], body['stream_options'] = True, {'include_usage': True}
    stream_headers = dict(_request_headers(headers))
    stream_headers.setdefault('Accept-Encoding', 'identity')
    request = urllib.request.Request(url, data=json.dumps(body, ensure_ascii=False).encode('utf-8'),
                                     headers=stream_headers, method='POST')
    parts, finish_reason, usage = [], '', None
    done = False
    saw_completion = False
    buffered_chars = 0
    try:
        with (opener or _http_opener)().open(request, timeout=timeout) as response:
            for raw in response:
                if control is not None:
                    control.checkpoint()
                if cancelled and cancelled():
                    return {'ok': False, 'status': 0, 'error': '请求已取消'}
                line = raw.decode('utf-8', 'replace').strip()
                if not line.startswith('data:'):
                    continue
                data = line[5:].strip()
                if data == '[DONE]':
                    done = True
                    continue
                try:
                    item = json.loads(data)
                    usage = item['usage'] if isinstance(item.get('usage'), dict) else usage
                    choice = item.get('choices', [{}])[0] if item.get('choices') else {}
                    finish_reason = choice.get('finish_reason') or finish_reason
                    delta = choice.get('delta', {}).get('content') or ''
                except (ValueError, IndexError, AttributeError):
                    continue
                if finish_reason:
                    saw_completion = True
                if delta:
                    text = str(delta)
                    buffered_chars += len(text)
                    if buffered_chars > STREAM_BUFFER_MAX_BYTES:
                        return {'ok': False, 'status': getattr(response, 'status', 200),
                                'error': '流式响应正文超过 %d 字节上限，已拒绝继续读取' % STREAM_BUFFER_MAX_BYTES,
                                'error_class': 'protocol'}
                    parts.append(text); on_chunk(text)
            if not done and not saw_completion:
                return {'ok': False, 'status': getattr(response, 'status', 200),
                        'error': '流式响应未收到完成事件或 finish_reason，可能被中断',
                        'error_class': 'protocol'}
            data = {'choices': [{'finish_reason': finish_reason, 'message': {'content': ''.join(parts)}}]}
            if usage is not None: data['usage'] = usage
            return {'ok': True, 'status': getattr(response, 'status', 200), 'data': data, 'error_class': ''}
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {'ok': False, 'status': 0, 'error': type(exc).__name__ + '：' + str(exc), 'error_class': 'network'}


def elapsed_ms(started):
    """这一趟花了多少毫秒（四舍五入到整数；clock 读不出来就当 0，别让报数把测试连接带崩）。"""
    try:
        return int(round((time.time() - float(started)) * 1000))
    except (TypeError, ValueError):
        return 0


def _http_opener():
    """收敛到 RequestsJsonOpener：不跟随重定向，凭据与请求体不外泄；按需加载。"""
    from contract.platform_tools import RequestsJsonOpener
    return RequestsJsonOpener()


