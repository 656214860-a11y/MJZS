"""账号服务端 HTTP 客户端（设计文档 §3.2）：每个接口一个函数，返回 ``service_contract`` 结果。

出站请求只经 ``platform_tools.open_https``；测试期服务端是 IP＋自签证书，这里把证书
本体内置并用 ``ssl.create_default_context(cadata=...)`` 钉住，不关闭校验。备案后改用
域名与系统 CA（去掉 ``PINNED_CERT``）。失败结果的 ``data`` 带服务端稳定错误码
``code``（网络不通时为 ``network``），调用方按 ``code`` 分支，不按文字。
本模块不读写本机文件、不导入 Tk；令牌只在入参和返回值里，不写日志。
"""
import json
import re
import ssl
import urllib.error

import platform_tools
from app_metadata import VERSION
from service_contract import SystemError, UserError, success

BASE_URL = 'https://8.138.223.126'
TIMEOUT = 15
CLIENT_VERSION = VERSION.lstrip('Vv')
TOS_VERSION = '2026-10'
PRIVACY_VERSION = '2026-10'
NETWORK = 'network'
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
_context = None


def _ssl_context():
    global _context
    if _context is None:
        _context = ssl.create_default_context(cadata=PINNED_CERT) if PINNED_CERT else ssl.create_default_context()
    return _context


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
    try:
        data = json.loads(response.read().decode('utf-8') or '{}')
    except (ValueError, UnicodeError):
        return None
    return data if isinstance(data, dict) else None


def request(method, path, body=None, *, token='', opener=None):
    """发一次请求；2xx 返回 success(data=响应对象)，否则失败结果（``data['code']``）。"""
    headers = {'Accept': 'application/json', 'X-Client-Version': CLIENT_VERSION}
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    if token:
        headers['Authorization'] = 'Bearer ' + token
    opener = opener or platform_tools.open_https
    try:
        with opener(BASE_URL + path, timeout=TIMEOUT, data=data, headers=headers,
                    method=method, context=_ssl_context()) as response:
            payload = _read_json(response)
    except urllib.error.HTTPError as exc:
        try:
            return _failure(exc.code, _read_json(exc))
        finally:
            exc.close()
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return SystemError('连不上账号服务器，请检查网络后重试', data={'code': NETWORK, 'detail': type(exc).__name__})
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
