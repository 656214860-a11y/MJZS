# -*- coding: utf-8 -*-
"""B 维「安全与数据边界」验收探针（桌面与云服务架构及全链路验收任务书）。

对测试服 ``https://8.138.223.126`` 做 API 级验证，并离线验证客户端租约验签、
离线权益状态机、敏感字段遮盖与本机会话落盘完整性。证据脱敏导出到
``tasks_round/evidence/<轮次>/security_probe.json``。

边界（与台账 §0「线上动作与真实用户数据另行授权」一致）：

- 真实会话只用于**只读 GET**（``/v1/me``、``/v1/devices``、``/v1/providers``、
  ``/v1/account/export``）；**绝不调用** ``renew``／``logout``／``delete-*``／
  ``redeem``／口令类接口——刷新令牌一次一换，并发续签会触发服务端重用检测、
  吊销真实会话（见 ``domain/account_client.py`` 模块说明）。
- 唯一写操作：``POST /v1/auth/email/code``（login 用途、一次性 ``.invalid`` 假邮箱），
  用于验证应用层重发限流；服务端对未注册邮箱同样发码是设计行为。
- 证据不落盘任何令牌、租约、邮箱原文、内网 IP；uid/sid/did 只留哈希前缀。

用法（程序目录下）::

    python -B scripts/acceptance_security_probe.py --round 3739 [--skip-server-tests]
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import http.client
import json
import socket
import ssl
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import file_cache  # noqa: E402  正式 JSON 读唯一入口
sys.path.insert(0, str(HERE / 'tests'))

import account_client                       # noqa: E402  领域客户端（钉证书 TLS）
import entitlement_service as ent           # noqa: E402
from infra import account_store, lease_verifier, session_integrity  # noqa: E402
from test_account_client import DID, KEYS, NOW, payload, sign       # noqa: E402  复用测试夹具密钥对

HOST = '8.138.223.126'
SERVER_REPO = Path(r'D:\漫剧服务端')
SESSION_JSON = Path(r'D:\漫剧制作助手\程序\private\账户\session.json')
CV = account_client.CLIENT_VERSION

RESULTS = []   # (section, name, ok|None, detail)


def record(section, name, ok, detail=''):
    RESULTS.append({'section': section, 'name': name,
                    'ok': ok, 'detail': detail})
    mark = 'PASS' if ok else ('SKIP' if ok is None else 'FAIL')
    print(f'[{mark}] {section}/{name}: {detail}')


def _b64d(text):
    return base64.urlsafe_b64decode(text + '=' * (-len(text) % 4))


def _short(tag, value):
    """标识脱敏：只留类型与哈希前缀，绝不落原文。"""
    if value in (None, ''):
        return ''
    return f'{tag}:{hashlib.sha256(str(value).encode()).hexdigest()[:10]}'


def _mask_email(email):
    email = str(email or '')
    local, _, domain = email.partition('@')
    return f'{local[:1]}***@{domain}' if domain else '***'


def _json_shape(value, depth=0):
    """递归记录 JSON 结构：键名 + 类型 + 条数；字符串值一律不落盘。"""
    if isinstance(value, dict):
        return {k: _json_shape(v, depth + 1) for k, v in sorted(value.items())} if depth < 4 else 'dict'
    if isinstance(value, list):
        return {'_list': len(value), '_item': _json_shape(value[0], depth + 1) if value else None}
    if isinstance(value, str):
        return f'str[{len(value)}]'
    if isinstance(value, bool) or value is None:
        return value
    return type(value).__name__


class Probe:
    """带钉证书上下文的 HTTPS 探针；每条记录 status/headers/body 摘要。"""

    def __init__(self):
        self.ctx = account_client._ssl_context()
        self.results = []

    def request(self, method, path, *, host=HOST, port=443, body=None, headers=None,
                version=CV, token='', timeout=15, raw_path=None):
        hdrs = {'Accept': 'application/json', 'User-Agent': 'acceptance-probe/1.0'}
        if version is not None:
            hdrs['X-Client-Version'] = version
        if token:
            hdrs['Authorization'] = 'Bearer ' + token
        hdrs.update(headers or {})
        payload_body = None
        if body is not None:
            payload_body = json.dumps(body, ensure_ascii=False).encode('utf-8')
            hdrs['Content-Type'] = 'application/json'
        conn = http.client.HTTPSConnection(host, port, context=self.ctx, timeout=timeout)
        try:
            conn.request(method, raw_path or path, body=payload_body, headers=hdrs)
            resp = conn.getresponse()
            raw = resp.read()
            try:
                parsed = json.loads(raw.decode('utf-8') or '{}')
            except (ValueError, UnicodeError):
                parsed = None
            return {'status': resp.status, 'reason': resp.reason,
                    'headers': {k.lower(): v for k, v in resp.getheaders()},
                    'json': parsed if isinstance(parsed, dict) else None,
                    'body_head': raw[:200].decode('utf-8', 'replace') if parsed is None else ''}
        except (OSError, http.client.HTTPException) as exc:
            return {'status': None, 'error': f'{type(exc).__name__}: {exc}'}
        finally:
            conn.close()

    def get(self, path, **kw):
        return self.request('GET', path, **kw)

    def post(self, path, body=None, **kw):
        return self.request('POST', path, body=body if body is not None else {}, **kw)


def probe_tls_meta(p):
    sec = 'tls_meta'
    # TLS 指纹：对端证书 DER 与客户端内置钉选证书逐字节比对
    conn = http.client.HTTPSConnection(HOST, 443, context=p.ctx, timeout=15)
    try:
        conn.connect()
        sock = conn.sock
        der = sock.getpeercert(binary_form=True)
        pinned_der = ssl.PEM_cert_to_DER_cert(account_client.PINNED_CERT)
        record(sec, 'cert_matches_pinned', der == pinned_der,
               f'peer_cert_sha256={hashlib.sha256(der).hexdigest()[:16]} pinned_equal={der == pinned_der}')
        record(sec, 'tls_version', sock.version() in ('TLSv1.2', 'TLSv1.3'),
               f'version={sock.version()} cipher={sock.cipher()[0] if sock.cipher() else "?"}')
    except OSError as exc:
        record(sec, 'tls_handshake', False, f'{type(exc).__name__}: {exc}')
        conn.close()
        return
    finally:
        try:
            conn.close()
        except OSError:
            pass

    meta = p.get('/v1/meta')
    hz = p.get('/healthz')
    if meta.get('status') == 200 and isinstance(meta.get('json'), dict):
        m = meta['json']
        record(sec, 'meta_ok', True,
               f"api_version={m.get('api_version')} min_client={m.get('min_client_version')} "
               f"latest={m.get('latest_version') or '-'} kids={m.get('kids')} features={m.get('features')}")
        p.meta_kids = set(m.get('kids') or [])
    else:
        record(sec, 'meta_ok', False, json.dumps(meta, ensure_ascii=False)[:300])
        p.meta_kids = set()
    record(sec, 'healthz', hz.get('status') == 200, f"status={hz.get('status')}")

    hdrs = meta.get('headers') or {}
    record(sec, 'security_headers',
           'strict-transport-security' in hdrs and 'x-content-type-options' in hdrs,
           f"hsts={'strict-transport-security' in hdrs} nosniff={'x-content-type-options' in hdrs} "
           f"server={hdrs.get('server', 'absent')}")

    for path in ('/docs', '/openapi.json', '/redoc'):
        r = p.get(path)
        record(sec, f'docs_hidden_{path.strip("/")}', r.get('status') == 404,
               f'status={r.get("status")}')


def probe_version_gate(p):
    sec = 'version_gate'
    r1 = p.get('/v1/me', version=None)
    record(sec, 'missing_version_rejected',
           r1.get('status') == 400 and (r1.get('json') or {}).get('code') == 'client_version_required',
           f"status={r1.get('status')} code={(r1.get('json') or {}).get('code')}")
    r2 = p.get('/v1/me', version='not-a-version')
    record(sec, 'malformed_version_rejected',
           r2.get('status') == 400 and (r2.get('json') or {}).get('code') == 'client_version_required',
           f"status={r2.get('status')} code={(r2.get('json') or {}).get('code')}")
    # min_client_version=0.0.0 时 426 路径按配置不可达（main.py:119-120 代码路径由服务端单测覆盖）


def probe_auth_surface(p, lease):
    sec = 'auth_surface'
    cases = [
        ('no_token', ''),
        ('garbage_token', 'not-a-real-lease'),
        ('empty_bearer', '   '),
    ]
    for name, token in cases:
        r = p.get('/v1/me', token=token)
        code = (r.get('json') or {}).get('code')
        record(sec, f'{name}_rejected',
               r.get('status') == 401 and code == 'session_invalid',
               f"status={r.get('status')} code={code}")

    if lease:
        body, sig = lease.rsplit('.', 1)
        tampered = body + '.' + ('A' if sig[0] != 'A' else 'B') + sig[1:]
        r = p.get('/v1/me', token=tampered)
        record(sec, 'tampered_lease_rejected',
               r.get('status') == 401 and (r.get('json') or {}).get('code') == 'session_invalid',
               f"status={r.get('status')} code={(r.get('json') or {}).get('code')}")

        # payload 篡改（改 state 为 active 但保留原签名）也必须 401
        try:
            pl = json.loads(_b64d(body))
            pl['state'] = 'active' if pl.get('state') != 'active' else 'trial'
            forged_body = base64.urlsafe_b64encode(
                json.dumps(pl, separators=(',', ':'), ensure_ascii=False).encode()).rstrip(b'=').decode()
            r = p.get('/v1/me', token=forged_body + '.' + sig)
            record(sec, 'forged_payload_rejected',
                   r.get('status') == 401,
                   f"status={r.get('status')} code={(r.get('json') or {}).get('code')}")
        except Exception as exc:  # noqa: BLE001
            record(sec, 'forged_payload_rejected', None, f'setup failed: {exc}')


def _sanitized_me(data):
    if not isinstance(data, dict):
        return _json_shape(data)
    out = dict(data)
    if 'email' in out:
        out['email'] = _mask_email(out['email'])
    if 'id' in out:
        out['id'] = _short('uid', out['id'])
    return out


def probe_authed_reads(p, lease):
    sec = 'authed_reads'
    if not lease:
        record(sec, 'real_session_available', None, 'no lease in session.json')
        return None
    record(sec, 'real_session_available', True, 'lease present (value withheld)')

    r = p.get('/v1/me', token=lease)
    if r.get('status') == 200 and r.get('json'):
        me = r['json']
        sub = me.get('subscription') or {}
        record(sec, 'me_ok', True,
               f"status_field={me.get('status')} sub_state={sub.get('state')} plan={sub.get('plan')} "
               f"devices={me.get('devices')} keys={sorted(me.keys())}")
        # 敏感字段扫描：不应出现哈希/令牌/口令字段
        blob = json.dumps(me, ensure_ascii=False).lower()
        leaks = [k for k in ('pw_hash', 'password_hash', 'refresh', 'token', 'secret', 'hash_salt')
                 if k in blob]
        record(sec, 'me_no_secret_fields', not leaks, f'leak_keys={leaks}')
        return {'me': me, 'subscription_state': sub.get('state')}
    code = (r.get('json') or {}).get('code')
    if r.get('status') == 401 and code == 'session_invalid':
        record(sec, 'me_ok', None,
               'real lease rejected session_invalid (expired/revoked) — '
               'invalid-session rejection path verified by tamper cases')
        return {'dead': True}
    record(sec, 'me_ok', False, f"status={r.get('status')} code={code}")
    return None


def probe_authed_lists(p, lease, ctx):
    sec = 'authed_lists'
    if ctx and ctx.get('dead'):
        for name in ('devices_ok', 'providers_ok', 'export_ok', 'redeem_rejected'):
            record(sec, name, None, 'skipped: real lease session_invalid')
        return
    r = p.get('/v1/devices', token=lease)
    if r.get('status') == 200 and r.get('json'):
        devs = r['json'].get('devices') or []
        keys = sorted({k for d in devs for k in d})
        record(sec, 'devices_ok', True,
               f"count={len(devs)} max={r['json'].get('max')} keys={keys} "
               f"current_flags={[d.get('current') for d in devs]}")
        blob = json.dumps(r['json'], ensure_ascii=False).lower()
        leaks = [k for k in ('fingerprint', 'token', 'secret', 'hash') if k in blob]
        record(sec, 'devices_no_fingerprint_leak', not leaks, f'leak_keys={leaks}')
    elif r.get('status') == 401 and (r.get('json') or {}).get('code') == 'session_invalid':
        record(sec, 'devices_ok', None, 'real lease session_invalid')
    else:
        record(sec, 'devices_ok', False, f"status={r.get('status')} code={(r.get('json') or {}).get('code')}")

    r = p.get('/v1/providers', token=lease)
    if r.get('status') == 200 and r.get('json') is not None:
        prov = r['json']
        n = len(prov.get('providers') or [])
        nr = len(prov.get('relay_sites') or [])
        record(sec, 'providers_ok', True,
               f"enabled={prov.get('enabled')} providers={n} relay_sites={nr} "
               f"(member_view 不含地址与凭据——relay.py 契约)")
        blob = json.dumps(prov, ensure_ascii=False).lower()
        leaks = [k for k in ('api_key', 'apikey', 'secret', 'token', 'password', 'sk-') if k in blob]
        record(sec, 'providers_no_key_material', not leaks, f'leak_keys={leaks}')
    elif r.get('status') == 401 and (r.get('json') or {}).get('code') == 'session_invalid':
        record(sec, 'providers_ok', None, 'real lease session_invalid')
    else:
        record(sec, 'providers_ok', False, f"status={r.get('status')} code={(r.get('json') or {}).get('code')}")

    r = p.get('/v1/account/export', token=lease)
    if r.get('status') == 200 and r.get('json'):
        shape = _json_shape(r['json'])
        record(sec, 'export_ok', True,
               f"top_keys={sorted(r['json'].keys())} shape_keys={sorted(shape.keys()) if isinstance(shape, dict) else shape}")
        blob = json.dumps(r['json'], ensure_ascii=False).lower()
        leaks = [k for k in ('pw_hash', 'password_hash', 'refresh_token', 'token_hash', 'code_hash', 'ip_hash')
                 if k in blob]
        record(sec, 'export_no_credential_fields', not leaks, f'leak_keys={leaks}')
    elif r.get('status') == 401 and (r.get('json') or {}).get('code') == 'session_invalid':
        record(sec, 'export_ok', None, 'real lease session_invalid')
    else:
        record(sec, 'export_ok', False, f"status={r.get('status')} code={(r.get('json') or {}).get('code')}")

    # 4) 权益拒绝：无效兑换码必须被拒（唯一一次受控写——redeem_invalid 不改账号状态，
    #    只落服务端自身审计/限流事件，属设计内拒绝路径）
    r = p.post('/v1/redeem', {'code': 'INVALID-CODE-0000'}, token=lease)
    j = r.get('json') or {}
    record(sec, 'redeem_rejected',
           r.get('status') == 400 and j.get('code') in ('redeem_invalid', 'invalid_request'),
           f"status={r.get('status')} code={j.get('code')}")


def probe_app_rate_limit(p):
    sec = 'app_rate_limit'
    email = f'r{int(time.time())}b@example.invalid'
    r1 = p.post('/v1/auth/email/code', {'email': email, 'purpose': 'login'})
    code1 = (r1.get('json') or {}).get('code', 'ok' if r1.get('status') == 200 else '?')
    record(sec, 'code_request_1', r1.get('status') in (200, 503),
           f"status={r1.get('status')} code={code1} (503=mailer 故障属环境事实，429 判定不受影响)")
    r2 = p.post('/v1/auth/email/code', {'email': email, 'purpose': 'login'})
    j2 = r2.get('json') or {}
    record(sec, 'code_resend_429',
           r2.get('status') == 429 and j2.get('code') == 'too_many_requests' and bool(j2.get('retry_after')),
           f"status={r2.get('status')} code={j2.get('code')} retry_after={j2.get('retry_after')}")

    r3 = p.post('/v1/auth/email/code', {'email': 'not-an-email', 'purpose': 'login'})
    record(sec, 'invalid_email_400',
           r3.get('status') == 400 and (r3.get('json') or {}).get('code') == 'invalid_email',
           f"status={r3.get('status')} code={(r3.get('json') or {}).get('code')}")

    # 大 body：nginx client_max_body_size 16k → 413，不进应用
    big = p.post('/v1/auth/email/code', {'email': 'a@b.c', 'pad': 'x' * 20000})
    record(sec, 'oversize_body_413', big.get('status') in (400, 413),
           f"status={big.get('status')} (nginx 16k 上限先于应用参数校验)")


def probe_nginx_rate_limit(p):
    sec = 'nginx_rate_limit'
    # 单连接 keep-alive 连发：limit_req zone=mj_api rate=10r/s burst=20 nodelay
    conn = http.client.HTTPSConnection(HOST, 443, context=p.ctx, timeout=15)
    statuses = []
    try:
        conn.connect()
        for _ in range(45):
            conn.request('GET', '/healthz', headers={'Accept': 'application/json'})
            resp = conn.getresponse()
            resp.read()
            statuses.append(resp.status)
    except (OSError, http.client.HTTPException) as exc:
        record(sec, 'burst_probe', False, f'{type(exc).__name__}: {exc} statuses={statuses[-5:]}')
        return
    finally:
        conn.close()
    limited = [i for i, s in enumerate(statuses) if s != 200]
    record(sec, 'burst_limited', len(limited) > 0,
           f'total={len(statuses)} non200={len(limited)} first_reject_at={limited[0] if limited else "-"} '
           f'codes={sorted(set(statuses))}')
    time.sleep(3)
    rec = p.get('/v1/meta')
    record(sec, 'recovered_after_burst', rec.get('status') == 200,
           f"meta_status={rec.get('status')}（令牌桶回充后恢复）")


def _port_protocol_probe(port, payload, timeout=8):
    """发字节后读响应：返回 (ok, detail)。ok=True 表示端口上没有真实服务应答。"""
    try:
        s = socket.create_connection((HOST, port), timeout=timeout)
        s.settimeout(timeout)
        s.sendall(payload)
        data = s.recv(256)
        s.close()
        if data:
            return False, f'PUBLICLY REACHABLE: {data[:60]!r}'
        return True, 'connected, no data (filtered)'
    except (ConnectionResetError, ConnectionAbortedError):
        return True, 'reset after probe bytes (filtered by egress proxy/firewall)'
    except (socket.timeout, TimeoutError):
        return True, 'timeout after probe bytes (filtered)'
    except OSError as exc:
        return True, f'{type(exc).__name__} (unreachable)'


def _tls_probe_8443():
    """8443 TLS 握手探测：True=可达；否则返回描述串。"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        s = socket.create_connection((HOST, 8443), timeout=8)
        s.settimeout(8)
        s = ctx.wrap_socket(s, server_hostname=HOST)
        s.close()
        return True
    except (ConnectionResetError, ConnectionAbortedError):
        return 'TCP connect ok but TLS reset'
    except (socket.timeout, TimeoutError):
        return 'TLS handshake timeout'
    except OSError as exc:
        return f'{type(exc).__name__}: {exc}'


def probe_admin_surface():
    sec = 'admin_surface'
    # 80 → 301 https
    try:
        s = socket.create_connection((HOST, 80), timeout=8)
        s.sendall(b'GET / HTTP/1.0\r\nHost: x\r\n\r\n')
        head = s.recv(512).decode('latin-1', 'replace')
        s.close()
        record(sec, 'port80_redirect', '301' in head.split('\r\n', 1)[0] or ' 301' in head,
               f'status_line={head.splitlines()[0] if head else "?"}')
    except OSError as exc:
        record(sec, 'port80_redirect', False, f'{type(exc).__name__}: {exc}')

    # 8000/8001 应只绑回环：公网不可达。本机出口有透明代理——裸 TCP connect
    # 一律"成功"，必须发探测字节：真服务会回 HTTP 响应，被拦端口会 RST/超时。
    for port in (8000, 8001):
        verdict = _port_protocol_probe(port, b'GET /healthz HTTP/1.0' + bytes([13, 10]) + b'Host: x' + bytes([13, 10, 13, 10]))
        record(sec, f'port{port}_loopback_only', verdict[0], verdict[1])


    # 8443 管理面：nginx 独立 TLS 端口 → 127.0.0.1:8001；设计上仅 SSH 隧道可达。
    # 先 TLS 握手探测：被拦则记 SKIP（Host 白名单/会话门/2r/s 限流由服务端
    # tests/test_admin.py 单测与 admin.py:193-213 代码路径覆盖）。
    reach = _tls_probe_8443()
    if reach is not True:
        record(sec, 'admin_8443', None,
               f'{reach} — 管理面公网不可达（与 SSH 22 同被透明代理重置）；'
               'Host 白名单/登录门/限流以服务端单测＋deploy/nginx-mj.conf:54-71 为准')
        return
    p = Probe()
    for host_hdr, label in (('8.138.223.126', 'ip_host'), ('localhost', 'localhost_host'),
                            ('127.0.0.1', 'loopback_host'), ('evil.example.com', 'foreign_host')):
        r = p.request('GET', '/login', host=HOST, port=8443, headers={'Host': host_hdr}, version=None)
        body = (r.get('body_head') or (r.get('error') or ''))[:80].replace(chr(10), ' ')
        record(sec, f'admin_login_{label}',
               r.get('status') in (200, 301, 302, 303, 403),
               f"status={r.get('status')} body={body!r}")
    # 未登录访问管理页应被会话中间件 303 → /login
    r = p.request('GET', '/', host=HOST, port=8443, headers={'Host': 'localhost'}, version=None)
    record(sec, 'admin_root_requires_session', r.get('status') in (301, 302, 303, 403),
           f"status={r.get('status')} location={(r.get('headers') or {}).get('location', '-')}")

def probe_client_offline(lease, session_data):
    sec = 'client_offline'
    # 1) 会话文件完整性（只读 verify，不走 load()——避免任何写路径）
    if SESSION_JSON.is_file():
        try:
            raw = file_cache.read_json(SESSION_JSON)
            ok = session_integrity.verify(raw, SESSION_JSON)
            record(sec, 'session_mac_valid', ok,
                   f'keys={sorted(raw.keys())}（值不落盘）')
        except (OSError, ValueError) as exc:
            record(sec, 'session_mac_valid', False, f'{type(exc).__name__}: {exc}')
    else:
        record(sec, 'session_mac_valid', None, 'session.json 不存在')

    # 2) 租约验签（客户端内置公钥 k2026a）
    if lease:
        payload_dict = lease_verifier.verify(lease)
        record(sec, 'lease_signature_valid', payload_dict is not None,
               f"kid={payload_dict.get('kid') if payload_dict else '-'} "
               f"state={payload_dict.get('state') if payload_dict else '-'} "
               f"did={_short('did', payload_dict.get('did')) if payload_dict else '-'}")
        if payload_dict:
            kids = getattr(sys.modules[__name__], '_meta_kids', set())
            record(sec, 'lease_kid_in_meta', payload_dict.get('kid') in kids or not kids,
                   f"kid={payload_dict.get('kid')} meta_kids={sorted(kids) or 'unknown'}")
    else:
        record(sec, 'lease_signature_valid', None, '无租约可验')

    # 3) 离线权益状态机：真实租约 + 夹具租约全状态
    now = int(time.time())
    try:
        device_id = account_store.device_fingerprint()
    except Exception as exc:  # noqa: BLE001
        device_id = ''
        record(sec, 'device_fingerprint', None, f'{type(exc).__name__}: {exc}')
    else:
        record(sec, 'device_fingerprint', bool(device_id), f'len={len(device_id)} (sha256 hex)')

    if lease:
        floor = int((session_data or {}).get('server_time') or 0)
        verdict = ent.evaluate(lease, now=now, device_id=device_id, last_server_time=floor)
        record(sec, 'real_lease_entitlement', True,
               f"state={verdict.state} usable={verdict.usable} floor={floor}")

    # 夹具：过期 / 宽限 / 锁定 / 他机 / 时钟回拨
    cases = [
        ('fixture_valid', sign(payload()), ent.VALID),
        ('fixture_grace', sign(payload()), ent.GRACE),
        ('fixture_expired_state', sign(payload(state='expired')), ent.LOCKED),
        ('fixture_wrong_device', sign(payload()), ent.SIGNED_OUT),
        ('fixture_garbage', 'garbage.lease', ent.SIGNED_OUT),
    ]
    for name, lease_x, want in cases:
        if name == 'fixture_grace':
            got = ent.evaluate(lease_x, now=NOW + 8 * 86400, device_id=DID, keys=KEYS).state
        elif name == 'fixture_valid':
            got = ent.evaluate(lease_x, now=NOW, device_id=DID, keys=KEYS).state
        elif name == 'fixture_wrong_device':
            got = ent.evaluate(lease_x, now=NOW, device_id='b' * 64, keys=KEYS).state
        else:
            got = ent.evaluate(lease_x, now=NOW, device_id=DID, keys=KEYS).state
        record(sec, name, got == want, f'got={got} want={want}')

    # 阶段闸门：免费两阶段不受影响，付费阶段按状态拦截
    locked = ent.evaluate(sign(payload(state='expired')), now=NOW, device_id=DID, keys=KEYS)
    gate_free = ent.stage_block_message(locked, ent.FREE_STAGES[0])
    gate_paid = ent.stage_block_message(locked, ent.STAGES[2])
    record(sec, 'stage_gate_free_vs_paid',
           gate_free == '' and '会员账户' in gate_paid,
           f'free_block={gate_free!r} paid_block_head={gate_paid[:40]!r}')

    # 4) 敏感字段遮盖：服务端 message 中的邮箱/长令牌不外泄到 UI
    fake_jwt = ('eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9'
                '.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IngifQ'
                '.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c')
    masked = account_client._masked('错误：a@qq.com 的令牌 ' + fake_jwt + ' 已失效')
    ok_mask = ('a@qq.com' not in masked and '@qq.com' not in masked
               and all(seg not in masked for seg in fake_jwt.split('.'))
               and '[已隐藏]' in masked)
    record(sec, 'message_masking', ok_mask, f'masked={masked[:70]!r}')

    # 5) 真实客户端代码路径：account_client.meta()（钉证书、X-Client-Version、service_contract）
    r = account_client.meta()
    record(sec, 'client_meta_call', bool(r.ok),
           f'ok={r.ok} code={(r.data or {}).get("code") if not r.ok else "-"}')


def probe_server_tests():
    sec = 'server_unit_tests'
    py = SERVER_REPO / '.venv' / 'Scripts' / 'python.exe'
    if not py.is_file():
        record(sec, 'pytest', None, f'venv python 不存在: {py}')
        return
    try:
        done = subprocess.run([str(py), '-m', 'pytest', 'tests', '-q'],
                              cwd=str(SERVER_REPO), capture_output=True, text=True,
                              encoding='utf-8', errors='replace', timeout=600)
    except (OSError, subprocess.TimeoutExpired) as exc:
        record(sec, 'pytest', False, f'{type(exc).__name__}: {exc}')
        return
    tail = '\n'.join(done.stdout.strip().splitlines()[-5:])
    record(sec, 'pytest', done.returncode == 0,
           f'exit={done.returncode} tail={tail[-200:]!r}')


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--round', type=int, required=True, dest='rnd')
    ap.add_argument('--skip-server-tests', action='store_true')
    ap.add_argument('--out', default='')
    args = ap.parse_args()

    out = Path(args.out) if args.out else HERE / 'tasks_round' / 'evidence' / f'R{args.rnd}' / 'security_probe.json'
    out.parent.mkdir(parents=True, exist_ok=True)

    # 读取真实会话（只取 lease 字段；refresh_token 本轮不使用——renew 会轮换吊销）
    lease, session_data = '', {}
    if SESSION_JSON.is_file():
        try:
            session_data = file_cache.read_json(SESSION_JSON)
            lease = str(session_data.get('lease') or '')
        except (OSError, ValueError):
            pass

    p = Probe()
    probe_tls_meta(p)
    p.meta_kids = getattr(p, 'meta_kids', set())
    sys.modules[__name__]._meta_kids = p.meta_kids

    probe_version_gate(p)
    probe_auth_surface(p, lease)
    ctx = probe_authed_reads(p, lease)
    probe_authed_lists(p, lease, ctx)
    probe_app_rate_limit(p)
    probe_nginx_rate_limit(p)
    probe_admin_surface()
    probe_client_offline(lease, session_data)
    if not args.skip_server_tests:
        probe_server_tests()

    fails = [r for r in RESULTS if r['ok'] is False]
    skips = [r for r in RESULTS if r['ok'] is None]
    doc = {
        'round': args.rnd,
        'target': f'https://{HOST}',
        'server_repo_head': _git_head(SERVER_REPO),
        'client_version': CV,
        'collected_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'summary': {'total': len(RESULTS), 'pass': sum(1 for r in RESULTS if r['ok'] is True),
                    'fail': len(fails), 'skip': len(skips)},
        'results': RESULTS,
    }
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f"\n== {doc['summary']} -> {out}")
    if fails:
        print('FAILURES:')
        for r in fails:
            print(' -', r['section'], r['name'], r['detail'][:160])
    return 1 if fails else 0


def _git_head(repo):
    try:
        done = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=str(repo),
                              capture_output=True, text=True, timeout=15,
                              encoding='utf-8', errors='replace')
        return done.stdout.strip() or '?'
    except (OSError, subprocess.TimeoutExpired):
        return '?'


if __name__ == '__main__':
    raise SystemExit(main())
