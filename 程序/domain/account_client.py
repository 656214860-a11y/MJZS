"""账号服务端 HTTP 客户端（设计文档 §3.2）：每个接口一个函数，返回 ``service_contract`` 结果。

出站请求只经 ``platform_tools.open_https``；测试期服务端是 IP＋自签证书，这里把证书
本体内置并用 ``ssl.create_default_context(cadata=...)`` 钉住，不关闭校验。备案后改用
域名与系统 CA（去掉 ``PINNED_CERT``）。失败结果的 ``data`` 带服务端稳定错误码
``code``（网络不通时为 ``network``），调用方按 ``code`` 分支，不按文字。
自检与本地 CI 设置 ``DRAMA_SUPPRESS_NETWORK=1`` 时，默认联网入口直接按网络不通返回：
测试里真实 Desktop 会用本机会话续签，多进程并发续签会触发服务端令牌重用检测、吊销真实会话。
本模块不读写本机文件、不导入 Tk；令牌只在入参和返回值里，不写日志。
"""
import base64
import http.client
import json
import os
import re
import ssl
import urllib.error
from datetime import datetime, timezone

import contract.platform_tools as platform_tools
from contract.app_metadata import VERSION
from contract.service_contract import SystemError, UserError, success

BASE_URL = 'https://8.138.223.126'
TIMEOUT = 15
MAX_RESPONSE_BYTES = 8 * 1024 * 1024  # 账号导出也从这个 JSON 客户端读取。
CLIENT_VERSION = VERSION.lstrip('Vv')
TOS_VERSION = '2026-10'
PRIVACY_VERSION = '2026-10'
NETWORK = 'network'
SERVICE_TIMEOUT = 'service_timeout'
CERT_ERROR = 'cert_error'
SUPPORT_PLACEHOLDER = '联系客服：[待用户提供联系渠道]'
# 服务不可达时登录闸的三种人话提示；支持渠道占位待用户提供（见结果文件）。
UNREACHABLE_MESSAGES = {
    NETWORK: '连不上账号服务器，请检查网络后重试；' + SUPPORT_PLACEHOLDER,
    SERVICE_TIMEOUT: '账号服务响应超时，请稍后再试；' + SUPPORT_PLACEHOLDER,
    CERT_ERROR: '账号服务证书校验失败，请确认系统时间与网络环境后重试；' + SUPPORT_PLACEHOLDER,
}
SUPPRESS_NETWORK_ENV = 'DRAMA_SUPPRESS_NETWORK'
# 测试服 IP 自签证书（公开内容，2027-10-22 到期）；域名上线后作废。
PINNED_CERT = '''-----BEGIN CERTIFICATE-----
MIIBljCCATygAwIBAgIUPwWKH3MpjDD+Ty4Gn6MEdz8N+1EwCgYIKoZIzj0EAwIw
GDEWMBQGA1UEAwwNOC4xMzguMjIzLjEyNjAeFw0yNjEwMjIxNDU3MzlaFw0yNzEw
MjIxNDU3MzlaMBgxFjAUBgNVBAMMDTguMTM4LjIyMy4xMjYwWTATBgcqhkjOPQIB
BggqhkjOPQMBBwNCAATdAQTQQFxvxy8VOM11n+64eLMgn+/rqnLLnbQhazh3/nVh
4ABq6Se/sxMXir/2RuaDukZ/AJq4KqZBer8Bonkjo2QwYjAdBgNVHQ4EFgQUzTnp
5roYUost9NkbFaCzMVvuZxAwHwYDVR0jBBgwFoAUzTnp5roYUost9NkbFaCzMVvu
ZxAwDwYDVR0TAQH/BAUwAwEB/zAPBgNVHREECDAGhwQIit9+MAoGCCqGSM49BAMC
A0gAMEUCIQCKrvHcmf/zufpgtzawLfuUHjvoPZVFu9FiRvhXw6jqBAIgFc6nefcI
b6etUR7Flp4yByBxEYfi2aW+oFkJiSphyis=
-----END CERTIFICATE-----
'''
# 钉死证书到期前多少天开始告警（账号页／自检可调本函数展示）。
PINNED_CERT_WARN_DAYS = 60
# ASN.1 UTCTime 标签 0x17 + 长度 0x0d（YYMMDDHHMMSSZ）。
_UTC_TIME_TAG = b'\x17\x0d'
# 服务端错误码 → 给用户看的话；未登记的码用服务端 message。
MESSAGES = {
    'invalid_email': '邮箱格式不正确',
    'code_invalid': '验证码不正确或已过期',
    'too_many_requests': '请求太频繁，请稍后再试',
    'invalid_device': '本机设备标识不合法',
    'mail_unavailable': '验证码邮件暂时发不出去，请稍后再试',
    'age_confirmation_required': '注册须确认已年满 18 周岁',
    'terms_required': '注册须同意用户协议与隐私政策',
    'device_limit': '这个账号已绑定 3 台电脑，请先在已登录的电脑上解绑一台',
    'account_pending_deletion': '账号正在注销冷静期，登录前需要先撤销注销',
    'session_invalid': '登录已失效，请重新登录',
    'client_too_old': '客户端版本过低，请升级漫剧助手',
    'unbind_quota_exceeded': '30 天内最多解绑 2 次，请稍后再试',
    'device_not_found': '设备不存在或已解绑',
    'not_pending_deletion': '账号不在注销冷静期',
    'redeem_invalid': '兑换码无效（格式不对、不存在、已作废或已过兑换期）',
    'redeem_used': '这个兑换码已经被使用过',
    'account_banned': '账号已被停用，如有疑问请联系客服',
    'email_registered': '该邮箱已注册，请直接登录',
    'password_invalid': '邮箱或密码不正确',
    'password_not_set': '这个账号还没设置密码，请用验证码登录，或点“忘记密码”设置',
    'weak_password': '密码须为 8–64 位，并同时包含字母和数字',
}
PASSWORD_MIN, PASSWORD_MAX = 8, 64

# A6（EC-5，盘点报告 §B6）：本地合成 ``data['code']`` 码 → 登记表错误码。
# 21 个服务端业务码（``MESSAGES`` 键集）不进表：EC-Q2 原样显示，已有逐条文案；
# ``session_invalid``／``client_too_old`` 本机也合成（orchestrator/account_controller
# 与 ``_failure`` 的 426 特例）故进表。``http_<N>``（非 426）一族由
# ``http_status_to_code`` 按 ``http_client._classify`` 同口径归一，不进静态表。
ACCOUNT_TO_CODE: dict[str, str] = {
    'network': 'E-NET-UNREACHABLE',
    'service_timeout': 'E-NET-TIMEOUT',    # 表B漏列：语义吻合「服务响应超时」
    'cert_error': 'E-NET-UNREACHABLE',     # 表B漏列：近似，证书校验失败无专码
    'bad_response': 'E-NET-CLIENT',
    'client_error': 'E-NET-CLIENT',
    'client_too_old': 'E-CLIENT-TOO-OLD',
    'session_invalid': 'E-AUTH-REJECTED',  # 近似
    'session_changed': 'E-AUTH-REJECTED',  # 近似
    'write_failed': 'E-IO-WRITE',
    'local_clear_failed': 'E-IO-WRITE',
    # 会话/租约本机维护失败无专码，余量保留
    'lease_unverified': 'E-AUTH-REJECTED',
    'remote_logout_unconfirmed': 'E-AUTH-REJECTED',
}


def http_status_to_code(status):
    """``http_<status>`` 一族 → 登记表码：与 ``http_client._classify`` 同口径；
    426 在 ``_failure`` 里先归 ``client_too_old``，不会走到本函数。"""
    try:
        number = int(status)
    except (TypeError, ValueError):
        return 'E-NET-CLIENT'
    if number == 429:
        return 'E-NET-RATE-LIMIT'
    if number in (401, 403):
        return 'E-AUTH-REJECTED'
    if 500 <= number < 600:
        return 'E-NET-SERVER'
    return 'E-NET-CLIENT'


_context = None


def _ssl_context():
    global _context
    if _context is None:
        _context = ssl.create_default_context(cadata=PINNED_CERT) if PINNED_CERT else ssl.create_default_context()
    return _context


def pinned_cert_not_after(pem=None):
    """解析钉死证书的 ``notAfter``（UTC）；解析失败返回 ``None``。不改地址与证书本身。"""
    text = PINNED_CERT if pem is None else pem
    if not text:
        return None
    body = ''.join(line for line in str(text).splitlines() if line and not line.startswith('-----'))
    try:
        der = base64.b64decode(body)
    except (ValueError, TypeError):
        return None
    times = []
    idx = 0
    while True:
        pos = der.find(_UTC_TIME_TAG, idx)
        if pos < 0:
            break
        stamp = der[pos + 2:pos + 15]
        try:
            times.append(datetime.strptime(stamp.decode('ascii'), '%y%m%d%H%M%SZ').replace(tzinfo=timezone.utc))
        except (ValueError, UnicodeError):
            pass
        idx = pos + 1
    return max(times) if times else None


def pinned_cert_warning(*, now=None, warn_days=PINNED_CERT_WARN_DAYS, pem=None):
    """到期前 ``warn_days`` 天内（含已过期）返回告警文案，否则空串。

    供账号页或自检展示；本函数不改 ``BASE_URL``／``PINNED_CERT``。
    """
    not_after = pinned_cert_not_after(pem)
    if not_after is None:
        return ''
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=timezone.utc)
    remaining = not_after - clock
    limit = max(0, int(warn_days)) * 86400
    if remaining.total_seconds() > limit:
        return ''
    day = not_after.date().isoformat()
    if remaining.total_seconds() < 0:
        return '账号服务钉死证书已于 %s 到期，登录可能失败，请尽快更换域名与系统 CA。' % day
    return '账号服务钉死证书将于 %s 到期（剩余不足 %d 天），到期后登录闸可能无法通过。' % (day, max(0, int(warn_days)))


_EMAIL = re.compile(r'[A-Za-z0-9_.+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+')
_EMAIL_FULL = re.compile(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}')
_OPAQUE = re.compile(r'[A-Za-z0-9_\-]{24,}(?:\.[A-Za-z0-9_\-]+)*')


def valid_email(text):
    """与服务端同一规则的格式检查，发请求前先挡住 ``656214860@qqcom`` 这类笔误。"""
    text = (text or '').strip()
    return len(text) <= 254 and bool(_EMAIL_FULL.fullmatch(text))


def password_problem(password):
    """与服务端同一强度规则；合格返回空串，否则返回给用户看的原因。"""
    password = password or ''
    if not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
        return '密码须为 %d–%d 位' % (PASSWORD_MIN, PASSWORD_MAX)
    if not (re.search(r'[A-Za-z]', password) and re.search(r'\d', password)):
        return '密码须同时包含字母和数字'
    return ''


def _masked(text):
    """服务端原文提示会展示到界面：遮掉邮箱和形似令牌／租约的长串，不让凭据随提示外流。"""
    return _OPAQUE.sub('[已隐藏]', _EMAIL.sub('[邮箱已隐藏]', text))


def _failure(status, body):
    body = body if isinstance(body, dict) else {}
    code = str(body.get('code') or ('client_too_old' if status == 426 else 'http_%d' % status))
    data = {'code': code, 'status': status, 'retry_after': body.get('retry_after')}
    reason = MESSAGES.get(code) or _masked(str(body.get('message') or '账号服务返回错误（%d）' % status))
    return (SystemError if status >= 500 else UserError)(reason, data=data)


def _read_json(response):
    from infra.http_client import read_limited
    headers = getattr(response, 'headers', {}) or {}
    declared = headers.get('Content-Length')
    if declared is not None and not headers.get('Transfer-Encoding'):
        try:
            expected = int(declared)
        except (ValueError, TypeError):
            raise http.client.HTTPException('invalid content length') from None
        if not 0 <= expected <= MAX_RESPONSE_BYTES:
            raise http.client.HTTPException('invalid content length')
    else:
        expected = None
    raw, overflow = read_limited(response, MAX_RESPONSE_BYTES)
    if expected is not None and len(raw) != expected:
        raise http.client.HTTPException('incomplete account response')
    if overflow:
        raise http.client.HTTPException('response too large')
    try:
        data = json.loads(raw.decode('utf-8') or '{}')
    except (ValueError, UnicodeError):
        return None
    return data if isinstance(data, dict) else None


def _unreachable(exc):
    """把出站失败归类：返回 ``(code, message)``；区分网络不通／服务无响应（超时）／证书校验失败。"""
    reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
    if isinstance(reason, ssl.SSLCertVerificationError):
        return CERT_ERROR, UNREACHABLE_MESSAGES[CERT_ERROR]
    if isinstance(reason, TimeoutError) or 'timed out' in str(reason or '').lower():
        return SERVICE_TIMEOUT, UNREACHABLE_MESSAGES[SERVICE_TIMEOUT]
    return NETWORK, UNREACHABLE_MESSAGES[NETWORK]


def request(method, path, body=None, *, token='', opener=None):
    """发一次请求；2xx 返回 success(data=响应对象)，否则失败结果（``data['code']``）。"""
    headers = {'Accept': 'application/json', 'X-Client-Version': CLIENT_VERSION}
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    if token:
        headers['Authorization'] = 'Bearer ' + token
    if opener is None and os.environ.get(SUPPRESS_NETWORK_ENV):
        return SystemError('自检环境不联网（%s）' % SUPPRESS_NETWORK_ENV, data={'code': NETWORK, 'detail': 'suppressed'})
    opener = opener or platform_tools.open_https
    try:
        try:
            with opener(BASE_URL + path, timeout=TIMEOUT, data=data, headers=headers,
                        method=method, context=_ssl_context()) as response:
                payload = _read_json(response)
        except urllib.error.HTTPError as exc:
            with exc:
                return _failure(exc.code, _read_json(exc))
    except http.client.HTTPException:
        return SystemError('账号响应超限或传输不完整，请重试', data={'code': 'bad_response'})
    except (urllib.error.URLError, OSError, ValueError) as exc:
        code, message = _unreachable(exc)
        return SystemError(message, data={'code': code, 'detail': type(exc).__name__})
    if payload is None:
        return SystemError('账号服务返回了无法识别的内容', data={'code': 'bad_response'})
    return success(payload)


def meta(**kw):
    return request('GET', '/v1/meta', **kw)


def send_code(email, purpose='login', **kw):
    """``purpose``：login（验证码登录）、register（注册，已注册返回 email_registered）、reset（忘记密码）。"""
    return request('POST', '/v1/auth/email/code', {'email': email, 'purpose': purpose}, **kw)


def register(email, code, password, device, *, age_confirmed, **kw):
    return request('POST', '/v1/auth/register', {
        'email': email, 'code': code, 'password': password, 'device': device,
        'age_confirmed': bool(age_confirmed), 'tos_version': TOS_VERSION, 'privacy_version': PRIVACY_VERSION}, **kw)


def password_login(email, password, device, **kw):
    return request('POST', '/v1/auth/password/login', {'email': email, 'password': password, 'device': device}, **kw)


def reset_password(email, code, password, **kw):
    return request('POST', '/v1/auth/password/reset', {'email': email, 'code': code, 'password': password}, **kw)


def change_password(lease, password, old_password=None, **kw):
    body = {'password': password}
    if old_password:
        body['old_password'] = old_password
    return request('POST', '/v1/account/password', body, token=lease, **kw)


def verify_code(email, code, device, *, age_confirmed, **kw):
    """``device`` 为 {id, name, os}；首次注册须 ``age_confirmed`` 且带协议版本。"""
    return request('POST', '/v1/auth/email/verify', {
        'email': email, 'code': code, 'device': device, 'age_confirmed': bool(age_confirmed),
        'tos_version': TOS_VERSION, 'privacy_version': PRIVACY_VERSION}, **kw)


def renew(refresh_token, device_id, **kw):
    return request('POST', '/v1/lease/renew', {'refresh_token': refresh_token, 'device_id': device_id}, **kw)


def logout(lease, **kw):
    return request('POST', '/v1/auth/logout', {}, token=lease, **kw)


def me(lease, **kw):
    return request('GET', '/v1/me', token=lease, **kw)


def devices(lease, **kw):
    return request('GET', '/v1/devices', token=lease, **kw)


def unbind_device(lease, device_id, **kw):
    return request('DELETE', '/v1/devices/' + str(device_id), token=lease, **kw)


def delete_code(lease, **kw):
    return request('POST', '/v1/account/delete-code', {}, token=lease, **kw)


def delete_request(lease, code, **kw):
    return request('POST', '/v1/account/delete-request', {'code': code}, token=lease, **kw)


def delete_cancel(email, code, **kw):
    return request('POST', '/v1/account/delete-cancel', {'email': email, 'code': code}, **kw)


def redeem(lease, code, **kw):
    """兑换码开通／续期；码原样提交，空格、横杠、大小写与 O/I/L 由服务端归一。"""
    return request('POST', '/v1/redeem', {'code': code}, token=lease, **kw)


def providers(lease, **kw):
    """推荐线路预设（仅地址与说明，不含 Key）；总开关关闭时服务端返回空列表。"""
    return request('GET', '/v1/providers', token=lease, **kw)


def export(lease, **kw):
    return request('GET', '/v1/account/export', token=lease, **kw)
