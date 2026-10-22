# -*- coding: utf-8 -*-
"""账户会员客户端（R1895，设计文档 说明/账户会员云端设计.md §4、§5、§8）：
租约验签、离线状态机、本机会话落盘、HTTP 客户端错误码、登录续签编排与阶段闸门。"""
import base64
import hashlib
import io
import json
import random
import sys
import tempfile
import unittest
import unittest.mock
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import account_client
import account_controller
import account_store
import entitlement_service as ent
import lease_verifier
import stage_handler_registry
from pet_bus import STAGES
from service_contract import SystemError, UserError, success

NOW = 1_800_000_000
DID = 'a' * 64


def _probable_prime(bits, rng):
    while True:
        n = rng.getrandbits(bits) | (1 << (bits - 1)) | 1
        if all(n % p for p in (3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)) and all(
                pow(a, n - 1, n) == 1 for a in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29)):
            return n


def _keypair():
    rng = random.Random(1895)
    e = 65537
    while True:
        p, q = _probable_prime(512, rng), _probable_prime(512, rng)
        phi = (p - 1) * (q - 1)
        if p != q and phi % e:
            return p * q, e, pow(e, -1, phi)


N, E, D = _keypair()
KEYS = {'t1': (N, E)}


def _b64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b'=').decode()


def _em(body, k, *, digest=None, filler=b''):
    t = lease_verifier._SHA256_PREFIX + (digest or hashlib.sha256(body.encode()).digest()) + filler
    return b'\x00\x01' + b'\xff' * (k - len(t) - 3) + b'\x00' + t


def sign(payload, *, em=None, d=D):
    body = _b64(json.dumps(payload, separators=(',', ':')).encode())
    k = (N.bit_length() + 7) // 8
    m = int.from_bytes(em(body, k) if em else _em(body, k), 'big')
    return body + '.' + _b64(pow(m, d, N).to_bytes(k, 'big'))


def payload(**over):
    data = {'v': 1, 'kid': 't1', 'uid': 'u1', 'sid': 's1', 'did': DID, 'state': 'trial', 'plan': 'trial',
            'trial_ends_at': NOW + 3 * 86400, 'period_end': None, 'issued_at': NOW - 3600,
            'expires_at': NOW + 7 * 86400, 'grace_until': NOW + 10 * 86400, 'nonce': 'n'}
    data.update(over)
    return data


def evaluate(lease, now=NOW, did=DID, last=0):
    return ent.evaluate(lease, now=now, device_id=did, last_server_time=last, keys=KEYS)


class LeaseVerifierTests(unittest.TestCase):
    def test_valid_signature_returns_payload(self):
        self.assertEqual(lease_verifier.verify(sign(payload()), KEYS)['uid'], 'u1')

    def test_tampered_payload_is_rejected(self):
        body, sig = sign(payload()).split('.')
        forged = _b64(json.dumps(payload(state='active', expires_at=NOW + 10 ** 8)).encode())
        self.assertIsNone(lease_verifier.verify(forged + '.' + sig, KEYS))

    def test_unknown_kid_wrong_version_and_garbage_are_rejected(self):
        self.assertIsNone(lease_verifier.verify(sign(payload(kid='other')), KEYS))
        self.assertIsNone(lease_verifier.verify(sign(payload(v=2)), KEYS))
        for junk in ('', 'abc', 'a.b.c', '.', None, 42):
            self.assertIsNone(lease_verifier.verify(junk, KEYS))

    def test_loose_padding_is_rejected(self):
        """§4.2：只接受完整 EM 字节，不接受哈希后夹带垃圾或错误摘要的签名。"""
        def trailing(body, k):
            t = lease_verifier._SHA256_PREFIX + hashlib.sha256(body.encode()).digest() + b'\x00' * 8
            return b'\x00\x01' + b'\xff' * (k - len(t) - 3) + b'\x00' + t
        self.assertIsNone(lease_verifier.verify(sign(payload(), em=trailing), KEYS))
        self.assertIsNone(lease_verifier.verify(sign(payload(), em=lambda b, k: _em(b, k, digest=b'\x00' * 32)), KEYS))

    def test_builtin_key_is_rsa_2048(self):
        n, e = lease_verifier.PUBLIC_KEYS['k2026a']
        self.assertEqual((n.bit_length(), e), (2048, 65537))


class EntitlementStateTests(unittest.TestCase):
    """§4.3 离线状态机全覆盖。"""

    def test_valid_grace_locked_by_time(self):
        lease = sign(payload())
        self.assertEqual(evaluate(lease).state, ent.VALID)
        self.assertEqual(evaluate(lease, now=NOW + 8 * 86400).state, ent.GRACE)
        self.assertEqual(evaluate(lease, now=NOW + 10 * 86400).state, ent.LOCKED)

    def test_expired_membership_is_locked_even_inside_lease(self):
        self.assertEqual(evaluate(sign(payload(state='expired'))).state, ent.LOCKED)

    def test_signed_out_without_lease_bad_signature_or_other_device(self):
        self.assertEqual(evaluate(None).state, ent.SIGNED_OUT)
        self.assertEqual(evaluate(sign(payload()) + 'x').state, ent.SIGNED_OUT)
        self.assertEqual(evaluate(sign(payload()), did='b' * 64).state, ent.SIGNED_OUT)
        self.assertEqual(evaluate(sign(payload()), did='').state, ent.SIGNED_OUT)
        self.assertEqual(evaluate(sign(payload(expires_at='x'))).state, ent.SIGNED_OUT)

    def test_clock_rewind_is_suspect(self):
        """§8：回拨本机时钟重放旧租约不能通过。"""
        lease = sign(payload())
        self.assertEqual(evaluate(lease, now=NOW, last=NOW + 3600).state, ent.CLOCK_SUSPECT)
        self.assertEqual(evaluate(lease, now=NOW - 2 * 3600).state, ent.CLOCK_SUSPECT)   # 早于签发时间
        self.assertEqual(evaluate(lease, now=NOW, last=NOW + ent.CLOCK_TOLERANCE - 1).state, ent.VALID)

    def test_free_stages_are_first_two_stage_keys(self):
        self.assertEqual(ent.FREE_STAGES, tuple(STAGES[:2]))
        signed_out = evaluate(None)
        for stage in STAGES[:2]:
            self.assertEqual(ent.stage_block_message(signed_out, stage), '')
        for stage in STAGES[2:]:
            self.assertIn('00 会员账户', ent.stage_block_message(signed_out, stage))
        self.assertEqual(ent.stage_block_message(signed_out, 'pet_performance'), '')
        self.assertEqual(ent.stage_block_message(evaluate(sign(payload())), STAGES[2]), '')

    def test_block_reasons_are_distinct(self):
        texts = {ent.stage_block_message(e, STAGES[3]) for e in (
            evaluate(None), evaluate(sign(payload()), last=NOW + 86400),
            evaluate(sign(payload(state='expired'))), evaluate(sign(payload()), now=NOW + 11 * 86400))}
        self.assertEqual(len(texts), 4)


class AccountStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='account-store-')
        self.path = Path(self.temp.name) / 'private' / '账户' / 'session.json'

    def tearDown(self):
        self.temp.cleanup()

    def test_save_load_and_server_time_only_grows(self):
        account_store.save_session({'email': 'a@b.c', 'refresh_token': 'r', 'lease': 'l', 'server_time': 100}, self.path)
        account_store.save_session({'lease': 'l2', 'server_time': 50}, self.path)
        data = account_store.load(self.path)
        self.assertEqual((data['lease'], data['refresh_token'], data['server_time']), ('l2', 'r', 100))

    def test_clear_keeps_device_seed_and_clock_floor(self):
        account_store.device_fingerprint(self.path, machine_id='')
        account_store.save_session({'refresh_token': 'r', 'lease': 'l', 'server_time': 100}, self.path)
        account_store.clear_session(self.path)
        data = account_store.load(self.path)
        self.assertNotIn('refresh_token', data)
        self.assertNotIn('lease', data)
        self.assertEqual(data['server_time'], 100)
        self.assertIn('device_seed', data)

    def test_corrupt_file_reads_as_empty(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text('{oops', encoding='utf-8')
        self.assertEqual(account_store.load(self.path), {})
        self.path.write_text('[1]', encoding='utf-8')
        self.assertEqual(account_store.load(self.path), {})

    def test_fingerprint_is_stable_hash(self):
        a = account_store.device_fingerprint(self.path, machine_id='guid-1')
        self.assertEqual(a, account_store.device_fingerprint(self.path, machine_id='guid-1'))
        self.assertNotEqual(a, account_store.device_fingerprint(self.path, machine_id='guid-2'))
        self.assertRegex(a, r'^[0-9a-f]{64}$')
        seeded = account_store.device_fingerprint(self.path, machine_id='')
        self.assertEqual(seeded, account_store.device_fingerprint(self.path, machine_id=''))


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class AccountClientTests(unittest.TestCase):
    def opener(self, reply):
        calls = []

        def fake(url, **kw):
            calls.append((url, kw))
            if isinstance(reply, BaseException):
                raise reply
            return _Response(json.dumps(reply).encode())
        return fake, calls

    def test_request_headers_body_and_pinned_context(self):
        fake, calls = self.opener({'ok': True})
        result = account_client.unbind_device('LEASE', 'dev1', opener=fake)
        self.assertTrue(result.ok)
        url, kw = calls[0]
        self.assertEqual(url, account_client.BASE_URL + '/v1/devices/dev1')
        self.assertEqual(kw['method'], 'DELETE')
        self.assertEqual(kw['headers']['Authorization'], 'Bearer LEASE')
        self.assertEqual(kw['headers']['X-Client-Version'], account_client.CLIENT_VERSION)
        self.assertEqual(kw['context'].verify_mode, __import__('ssl').CERT_REQUIRED)
        self.assertTrue(kw['context'].check_hostname)
        fake, calls = self.opener({'ok': True})
        account_client.verify_code('a@b.c', '123456', {'id': DID}, age_confirmed=True, opener=fake)
        body = json.loads(calls[0][1]['data'])
        self.assertEqual((body['age_confirmed'], body['tos_version']), (True, account_client.TOS_VERSION))

    def test_http_error_maps_stable_code(self):
        err = urllib.error.HTTPError('u', 429, 'x', {}, io.BytesIO(json.dumps(
            {'code': 'unbind_quota_exceeded', 'message': 'm', 'retry_after': 60}).encode()))
        result = account_client.devices('L', opener=self.opener(err)[0])
        self.assertIsInstance(result, UserError)
        self.assertEqual((result.data['code'], result.data['retry_after']), ('unbind_quota_exceeded', 60))
        err = urllib.error.HTTPError('u', 426, 'x', {}, io.BytesIO(b'not json'))
        self.assertEqual(account_client.meta(opener=self.opener(err)[0]).data['code'], 'client_too_old')

    def test_network_failure_is_system_error(self):
        result = account_client.meta(opener=self.opener(urllib.error.URLError('down'))[0])
        self.assertIsInstance(result, SystemError)
        self.assertEqual(result.data['code'], account_client.NETWORK)


class _Store:
    """把 account_store 绑定到临时路径的替身。"""

    def __init__(self, path):
        self.path = path

    def __getattr__(self, name):
        fn = getattr(account_store, name)
        if name == 'device_fingerprint':
            return lambda: DID
        return lambda *a: fn(*a, self.path)


class _Client:
    def __init__(self, **replies):
        self.replies, self.calls = replies, []

    def __getattr__(self, name):
        def call(*a, **kw):
            self.calls.append((name, a))
            return self.replies[name]
        return call


class AccountControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='account-ctl-')
        self.store = _Store(Path(self.temp.name) / 'session.json')
        self.results = []
        self.patch = unittest.mock.patch.object(lease_verifier, 'PUBLIC_KEYS', KEYS)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def controller(self, client):
        return account_controller.AccountController(
            submit=lambda work, done, label: (done or self.results.append)(work()),
            clock=lambda: NOW, store=self.store, client=client, enforce=True)

    def test_login_saves_verified_session_and_opens_gate(self):
        lease = sign(payload())
        ctl = self.controller(_Client(verify_code=success({'refresh_token': 'r1', 'lease': lease, 'server_time': NOW})))
        self.assertIn('00 会员账户', ctl.stage_gate(STAGES[2]))
        ctl.login('a@b.c', '123456', age_confirmed=True, done=self.results.append)
        self.assertTrue(self.results[-1].ok)
        self.assertEqual(ctl.entitlement().state, ent.VALID)
        self.assertEqual(ctl.stage_gate(STAGES[2]), '')
        self.assertEqual(ctl.session()['email'], 'a@b.c')

    def test_unverifiable_or_foreign_lease_is_not_saved(self):
        for bad in (sign(payload()) + 'x', sign(payload(did='b' * 64))):
            ctl = self.controller(_Client(verify_code=success({'refresh_token': 'r', 'lease': bad, 'server_time': NOW})))
            ctl.login('a@b.c', '1', age_confirmed=True, done=self.results.append)
            self.assertFalse(self.results[-1].ok)
            self.assertEqual(ctl.session().get('lease'), None)

    def test_renew_rotates_and_dead_session_clears(self):
        account_store.save_session({'refresh_token': 'r1', 'lease': sign(payload()), 'server_time': NOW}, self.store.path)
        new = sign(payload(nonce='m'))
        ctl = self.controller(_Client(renew=success({'refresh_token': 'r2', 'lease': new, 'server_time': NOW + 5})))
        self.assertTrue(ctl.renew(done=self.results.append))
        self.assertEqual((ctl.session()['refresh_token'], ctl.session()['lease']), ('r2', new))
        ctl = self.controller(_Client(renew=SystemError('x', data={'code': 'network'})))
        ctl.renew(done=self.results.append)
        self.assertEqual(ctl.session()['refresh_token'], 'r2')      # 断网保留旧租约
        ctl = self.controller(_Client(renew=UserError('x', data={'code': 'session_invalid'})))
        ctl.renew(done=self.results.append)
        self.assertNotIn('refresh_token', ctl.session())
        self.assertEqual(ctl.entitlement().state, ent.SIGNED_OUT)
        self.assertFalse(ctl.renew())                                   # 无令牌不再发请求

    def test_switch_off_only_evaluates_without_blocking(self):
        """正式服上线前总开关默认关闭：判定照常，但不拦截付费阶段。"""
        self.assertFalse(ent.GATE_ENFORCED)
        ctl = account_controller.AccountController(submit=None, clock=lambda: NOW, store=self.store, client=_Client())
        self.assertFalse(ctl.enforce)
        self.assertEqual(ctl.entitlement().state, ent.SIGNED_OUT)
        self.assertEqual(ctl.stage_gate(STAGES[2]), '')

    def test_logout_keeps_clock_floor_against_replay(self):
        """§8：退出后把旧租约写回并回拨时钟，仍被识别为时钟可疑。"""
        old = sign(payload())
        account_store.save_session({'refresh_token': 'r', 'lease': old, 'server_time': NOW + 86400}, self.store.path)
        ctl = self.controller(_Client())
        ctl.logout()
        account_store.save_session({'lease': old}, self.store.path)
        self.assertEqual(ctl.entitlement().state, ent.CLOCK_SUSPECT)


class _Desktop:
    def __init__(self, gate):
        self.root = None
        self.account = type('A', (), {'stage_gate': staticmethod(gate)})()
        self.events = []
        self.pet = type('P', (), {'_emit': lambda _s, *a, **kw: self.events.append((a, kw))})()


class StageGateTests(unittest.TestCase):
    """§5.2：闸门在 stage_handler_registry.start() 入口前置，手动与自动一致。"""

    def test_manual_start_returns_block_reason(self):
        desk = _Desktop(lambda stage: '需要登录' if stage == 'storyboard' else '')
        self.assertEqual(stage_handler_registry.start(desk, 'storyboard', trigger='manual'), '需要登录')

    def test_auto_start_emits_stage_failed(self):
        desk = _Desktop(lambda stage: '需要登录')
        fallback = unittest.mock.Mock(return_value='ran')
        self.assertEqual(stage_handler_registry.start(desk, 'keyframe', fallback=fallback), '需要登录')
        fallback.assert_not_called()
        self.assertEqual(desk.events[0][1]['stage'], 'keyframe')

    def test_non_string_gate_result_does_not_block(self):
        desk = _Desktop(lambda stage: unittest.mock.Mock())
        self.assertEqual(stage_handler_registry.start(desk, 'keyframe', fallback=lambda s, t: 'ran'), 'ran')

    def test_open_gate_falls_through(self):
        desk = _Desktop(lambda stage: '')
        self.assertEqual(stage_handler_registry.start(desk, 'keyframe', fallback=lambda s, t: 'ran'), 'ran')


if __name__ == '__main__':
    unittest.main()
