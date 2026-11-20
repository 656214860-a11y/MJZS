"""授权租约验签：纯 Python 的 RSA-2048 + SHA-256（PKCS#1 v1.5），无网络、无 Tk。

租约格式 ``base64url(payload_json) + "." + base64url(signature)``，由账号服务端签发
（设计文档 `docs/specs/07_业务域规格.md` §4）。标准库没有非对称验签，这里按 RFC 8017
§8.2.2 把 ``pow(sig, e, n)`` 的结果与期望的完整 EM 字节逐字节比对，不做宽松解析，
避免 Bleichenbacher 式填充伪造。公钥内置在本模块，不经网络下发；轮换时新旧 kid 并存。
"""
import base64
import hashlib
import hmac
import json

LEASE_VERSION = 1

# 公钥本体：{kid: (n, e)}。k2026a 为测试服（8.138.223.126）签名密钥，私钥只在服务器。
PUBLIC_KEYS = {
    'k2026a': (int(
        'd44c76a949abe0c7f5cc5ffa87cc6e8dd170b2efc15258d0b4da7f6604b0b6c4'
        '4b1316695b797ebdb97a97c37b873a51bd5c7b5bf278ecca1fcf76ca4a1219c6'
        'a6abeb4c70e763458602e900ff3593186cd43cd9063083bcb8d6162d638bbcdc'
        '942a108b54ee933fff9fa6298ac048d9fdec473f535d1363d94dfd7dc68e741b'
        '40de2f24246713d480f1e871e87dc4bd690ec5fb51ba3c348c2ef235b41240e4'
        '36ee4ad811526ee7594466b4dc7c8afd81515c4170fd627a77dd80feade0bafb'
        '5103efce8ec3edb5a24871ce22388b4f4c6cbd469594748d3704c223388c0fe0'
        '1396d8d9b903eda40b0e115f0356d3deeae358de4e1b026648ae30426c93e387', 16), 65537),
}

# DER 编码的 SHA-256 DigestInfo 前缀（RFC 8017 §9.2 注 1）
_SHA256_PREFIX = bytes.fromhex('3031300d060960864801650304020105000420')


def _b64d(text):
    return base64.urlsafe_b64decode(text + '=' * (-len(text) % 4))


def _signature_matches(body, signature, n, e):
    k = (n.bit_length() + 7) // 8
    if len(signature) != k:
        return False
    s = int.from_bytes(signature, 'big')
    if s >= n:
        return False
    em = pow(s, e, n).to_bytes(k, 'big')
    t = _SHA256_PREFIX + hashlib.sha256(body.encode('ascii')).digest()
    expected = b'\x00\x01' + b'\xff' * (k - len(t) - 3) + b'\x00' + t
    return hmac.compare_digest(em, expected)


def verify(lease, keys=None):
    """验签成功返回 payload 字典，否则 None；不判断时间（时间归 entitlement_service）。

    先按 payload 里声明的 ``kid`` 选公钥，未知 kid、格式版本不符、签名不符一律 None。
    """
    keys = PUBLIC_KEYS if keys is None else keys
    if not isinstance(lease, str) or lease.count('.') != 1:
        return None
    body, sig_text = lease.strip().split('.', 1)
    try:
        payload = json.loads(_b64d(body))
        signature = _b64d(sig_text)
    except (ValueError, UnicodeError):
        return None
    if not isinstance(payload, dict) or payload.get('v') != LEASE_VERSION:
        return None
    key = keys.get(payload.get('kid'))
    if key is None or not _signature_matches(body, signature, *key):
        return None
    return payload
