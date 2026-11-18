# -*- coding: utf-8 -*-
"""账户会员客户端（R1895，设计文档 说明/账户会员云端设计.md §4、§5、§8）：
租约验签、离线状态机、本机会话落盘、HTTP 客户端错误码、登录续签编排与阶段闸门。"""
import base64
import hashlib
import io
import json
import random
import sys
import subprocess
import tempfile
import unittest
import unittest.mock
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import account_client
from orchestrator import account_controller
from infra import account_store, model_secrets, session_integrity
import entitlement_service as ent
from infra import lease_verifier
from orchestrator import stage_handler_registry
from pet_bus import STAGES
from contract.service_contract import SystemError, UserError, success

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
        fingerprint = account_store.device_fingerprint(self.path, machine_id='')
        account_store.save_session({'refresh_token': 'r', 'lease': 'l', 'server_time': 100}, self.path)
        account_store.clear_session(self.path)
        data = account_store.load(self.path)
        self.assertNotIn('refresh_token', data)
        self.assertNotIn('lease', data)
        self.assertEqual(data['server_time'], 100)
        self.assertNotIn('device_seed', data)
        self.assertEqual(account_store.device_fingerprint(self.path, machine_id=''), fingerprint)
        self.path.unlink()
        self.assertEqual(account_store.device_fingerprint(self.path, machine_id=''), fingerprint)

    def test_corrupt_file_reads_as_empty(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text('{oops', encoding='utf-8')
        self.assertEqual(account_store.load(self.path), {})
        self.path.write_text('[1]', encoding='utf-8')
        self.assertEqual(account_store.load(self.path), {})

    def test_legacy_seed_migration_keeps_fingerprint(self):
        legacy_seed = 'legacy-device-seed'
        self.path.parent.mkdir(parents=True)
        self.path.write_text(json.dumps({'device_seed': legacy_seed, 'refresh_token': 'old-fixture'}), encoding='utf-8')
        expected = hashlib.sha256(('manju-device-v1:' + legacy_seed).encode('utf-8')).hexdigest()

        self.assertEqual(account_store.device_fingerprint(self.path, machine_id=''), expected)
        self.assertEqual(account_store.load(self.path), {})
        seed_path = account_store._device_seed_path(self.path)
        self.assertEqual(seed_path.read_text(encoding='utf-8'), legacy_seed)
        self.assertEqual(account_store.device_fingerprint(self.path, machine_id=''), expected)

    def test_session_integrity_rejects_tampering_and_recovers(self):
        account_store.save_session({'refresh_token': 'first-fixture'}, self.path)
        stored = json.loads(self.path.read_text(encoding='utf-8'))
        self.assertTrue(session_integrity.verify(stored, self.path))
        key_path = self.path.with_name('.mac_key.dpapi')
        self.assertTrue(model_secrets.looks_like_blob(key_path.read_bytes()[:20]))

        stored['refresh_token'] = 'changed-fixture'
        self.path.write_text(json.dumps(stored), encoding='utf-8')
        self.assertFalse(session_integrity.verify(stored, self.path))
        self.assertEqual(account_store.load(self.path), {})
        self.assertFalse(self.path.exists())

        account_store.save_session({'refresh_token': 'second-fixture'}, self.path)
        key_path.unlink()
        self.assertEqual(account_store.load(self.path), {})
        self.assertFalse(key_path.exists())
        account_store.save_session({'refresh_token': 'third-fixture'}, self.path)
        self.assertEqual(account_store.load(self.path)['refresh_token'], 'third-fixture')

    def test_two_processes_share_first_fallback_seed(self):
        script = (
            "import sys; from infra.account_store import device_fingerprint; "
            "print(device_fingerprint(sys.argv[1], machine_id=''))"
        )
        args = [sys.executable, '-c', script, str(self.path)]
        program = Path(account_store.__file__).resolve().parents[1]
        with subprocess.Popen(args, stdout=subprocess.PIPE, cwd=program) as first:
            with subprocess.Popen(args, stdout=subprocess.PIPE, cwd=program) as second:
                outputs = [process.communicate(timeout=20)[0].strip() for process in (first, second)]
                self.assertEqual([first.returncode, second.returncode], [0, 0])
        fingerprint = account_store.device_fingerprint(self.path, machine_id='')
        self.assertEqual(outputs, [fingerprint.encode('ascii')] * 2)
        self.assertFalse(self.path.exists())

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

    def test_redeem_posts_raw_code_with_bearer_and_maps_used(self):
        """R1898：码原样提交，归一化在服务端；409 redeem_used 有稳定中文提示。"""
        fake, calls = self.opener({'lease': 'x'})
        account_client.redeem('LEASE', 'abcd-efgh ijkl-mnop', opener=fake)
        url, kw = calls[0]
        self.assertEqual((url, kw['method']), (account_client.BASE_URL + '/v1/redeem', 'POST'))
        self.assertEqual(kw['headers']['Authorization'], 'Bearer LEASE')
        self.assertEqual(json.loads(kw['data']), {'code': 'abcd-efgh ijkl-mnop'})
        for status, code in ((409, 'redeem_used'), (400, 'redeem_invalid')):
            err = urllib.error.HTTPError('u', status, 'x', {}, io.BytesIO(json.dumps({'code': code}).encode()))
            result = account_client.redeem('L', 'C', opener=self.opener(err)[0])
            self.assertIsInstance(result, UserError)
            self.assertEqual(result.reason, account_client.MESSAGES[code])

    def test_p2_endpoints_methods_paths_and_auth(self):
        """P2：设备、注销、导出的方法与路径；撤销注销不带 Bearer（会话已全部吊销）。"""
        cases = ((account_client.devices, ('L',), 'GET', '/v1/devices', None),
                 (account_client.delete_code, ('L',), 'POST', '/v1/account/delete-code', {}),
                 (account_client.delete_request, ('L', '123456'), 'POST', '/v1/account/delete-request', {'code': '123456'}),
                 (account_client.delete_cancel, ('a@b.c', '654321'), 'POST', '/v1/account/delete-cancel',
                  {'email': 'a@b.c', 'code': '654321'}),
                 (account_client.export, ('L',), 'GET', '/v1/account/export', None))
        for fn, args, method, path, body in cases:
            fake, calls = self.opener({'ok': True})
            self.assertTrue(fn(*args, opener=fake).ok)
            url, kw = calls[0]
            self.assertEqual((url, kw['method']), (account_client.BASE_URL + path, method))
            self.assertEqual(None if kw['data'] is None else json.loads(kw['data']), body)
            self.assertEqual('Authorization' in kw['headers'], fn is not account_client.delete_cancel)

    def test_network_failure_is_system_error(self):
        result = account_client.meta(opener=self.opener(urllib.error.URLError('down'))[0])
        self.assertIsInstance(result, SystemError)
        self.assertEqual(result.data['code'], account_client.NETWORK)

    def test_password_endpoints_paths_and_bodies(self):
        """R2022：注册、口令登录、重置、修改口令与带用途的发码。"""
        dev = {'id': DID}
        cases = ((account_client.send_code, ('a@b.cn', 'register'), {}, '/v1/auth/email/code',
                  {'email': 'a@b.cn', 'purpose': 'register'}),
                 (account_client.register, ('a@b.cn', '123456', 'abc12345', dev), {'age_confirmed': True}, '/v1/auth/register',
                  {'email': 'a@b.cn', 'code': '123456', 'password': 'abc12345', 'device': dev, 'age_confirmed': True,
                   'tos_version': account_client.TOS_VERSION, 'privacy_version': account_client.PRIVACY_VERSION}),
                 (account_client.password_login, ('a@b.cn', 'abc12345', dev), {}, '/v1/auth/password/login',
                  {'email': 'a@b.cn', 'password': 'abc12345', 'device': dev}),
                 (account_client.reset_password, ('a@b.cn', '654321', 'abc12345'), {}, '/v1/auth/password/reset',
                  {'email': 'a@b.cn', 'code': '654321', 'password': 'abc12345'}),
                 (account_client.change_password, ('L', 'abc12345'), {}, '/v1/account/password', {'password': 'abc12345'}),
                 (account_client.change_password, ('L', 'abc12345', 'old12345'), {}, '/v1/account/password',
                  {'password': 'abc12345', 'old_password': 'old12345'}))
        for fn, args, extra, path, body in cases:
            fake, calls = self.opener({'ok': True})
            self.assertTrue(fn(*args, opener=fake, **extra).ok)
            url, kw = calls[0]
            self.assertEqual((url, kw['method']), (account_client.BASE_URL + path, 'POST'))
            self.assertEqual(json.loads(kw['data']), body)
            self.assertEqual('Authorization' in kw['headers'], fn is account_client.change_password)
        for code in ('email_registered', 'password_invalid', 'password_not_set', 'weak_password'):
            err = urllib.error.HTTPError('u', 401, 'x', {}, io.BytesIO(json.dumps({'code': code}).encode()))
            self.assertEqual(account_client.password_login('a@b.cn', 'x', dev, opener=self.opener(err)[0]).reason,
                             account_client.MESSAGES[code])

    def test_valid_email_and_password_problem_match_server_rules(self):
        for good in ('a@qq.com', ' Name.Tag+x@mail.example.cn '):
            self.assertTrue(account_client.valid_email(good), good)
        for bad in ('656214860@qqcom', 'a@b.c', 'a.qq.com', '', None, 'a@' + 'b' * 250 + '.com'):
            self.assertFalse(account_client.valid_email(bad), bad)
        self.assertEqual(account_client.password_problem('abc12345'), '')
        self.assertIn('字母和数字', account_client.password_problem('abcdefgh'))
        self.assertIn('字母和数字', account_client.password_problem('12345678'))
        self.assertIn('8', account_client.password_problem('a1'))
        self.assertIn('64', account_client.password_problem('a1' * 33))


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
            reply = self.replies[name]
            return reply.pop(0) if isinstance(reply, list) else reply
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

    def _signed_in(self, **over):
        old = sign(payload(**over))
        account_store.save_session({'email': 'a@b.c', 'refresh_token': 'r1', 'lease': old, 'server_time': NOW}, self.store.path)
        return old

    def test_redeem_replaces_lease_and_keeps_refresh_token(self):
        old = self._signed_in(state='expired', plan='trial')
        new = sign(payload(state='active', plan='monthly', period_end=NOW + 30 * 86400, nonce='r'))
        client = _Client(redeem=success({'lease': new, 'state': 'active', 'server_time': NOW + 1, 'added_days': 30}))
        ctl = self.controller(client)
        self.assertIn('00 会员账户', ctl.stage_gate(STAGES[2]))
        self.assertTrue(ctl.redeem(' ABCD-EFGH-JKMN-PQRS ', self.results.append))
        self.assertEqual(self.results[-1].data['added_days'], 30)
        self.assertEqual(client.calls, [('redeem', (old, 'ABCD-EFGH-JKMN-PQRS'))])
        session = ctl.session()
        self.assertEqual((session['lease'], session['refresh_token'], session['email']), (new, 'r1', 'a@b.c'))
        self.assertEqual(ctl.entitlement().payload['plan'], 'monthly')
        self.assertEqual(ctl.stage_gate(STAGES[2]), '')

    def test_redeem_failure_or_bad_lease_keeps_session(self):
        old = self._signed_in()
        for reply in (UserError('x', data={'code': 'redeem_used'}), success({'lease': old + 'x'}), success({})):
            ctl = self.controller(_Client(redeem=reply))
            ctl.redeem('C', self.results.append)
            self.assertFalse(self.results[-1].ok)
            self.assertEqual((ctl.session()['lease'], ctl.session()['refresh_token']), (old, 'r1'))

    def test_redeem_with_stale_lease_renews_once_then_retries(self):
        old = self._signed_in()
        fresh, paid = sign(payload(nonce='f')), sign(payload(state='active', plan='yearly', nonce='p'))
        client = _Client(redeem=[UserError('x', data={'code': 'session_invalid'}), success({'lease': paid, 'added_days': 365})],
                         renew=success({'refresh_token': 'r2', 'lease': fresh, 'server_time': NOW}))
        ctl = self.controller(client)
        ctl.redeem('C', self.results.append)
        self.assertTrue(self.results[-1].ok)
        self.assertEqual([c[0] for c in client.calls], ['redeem', 'renew', 'redeem'])
        self.assertEqual(client.calls[2][1], (fresh, 'C'))
        self.assertEqual((ctl.session()['lease'], ctl.session()['refresh_token']), (paid, 'r2'))

    def test_redeem_stops_when_session_is_dead_or_absent(self):
        self._signed_in()
        client = _Client(redeem=UserError('x', data={'code': 'session_invalid'}),
                         renew=UserError('登录已失效', data={'code': 'session_invalid'}))
        ctl = self.controller(client)
        ctl.redeem('C', self.results.append)
        self.assertEqual(self.results[-1].data['code'], 'session_invalid')
        self.assertEqual([c[0] for c in client.calls], ['redeem', 'renew'])
        self.assertNotIn('lease', ctl.session())
        self.assertFalse(ctl.redeem('C', self.results.append))

    def test_stage_gate_follows_verified_lease_and_explicit_override(self):
        ctl = account_controller.AccountController(
            submit=None, clock=lambda: NOW, store=self.store, client=_Client())
        self.assertTrue(ctl.enforce)
        self.assertEqual([stage for stage in STAGES if not ctl.stage_gate(stage)], list(STAGES[:2]))

        account_store.save_session({'lease': sign(payload(state='active'))}, self.store.path)
        self.assertTrue(all(not ctl.stage_gate(stage) for stage in STAGES))

        account_store.clear_session(self.store.path)
        disabled = account_controller.AccountController(
            submit=None, clock=lambda: NOW, store=self.store, client=_Client(), enforce=False)
        self.assertFalse(disabled.enforce)
        self.assertEqual(disabled.entitlement().state, ent.SIGNED_OUT)
        self.assertTrue(all(not disabled.stage_gate(stage) for stage in STAGES))

    def test_logout_keeps_clock_floor_against_replay(self):
        """§8：退出后把旧租约写回并回拨时钟，仍被识别为时钟可疑。"""
        old = sign(payload())
        account_store.save_session({'refresh_token': 'r', 'lease': old, 'server_time': NOW + 86400}, self.store.path)
        ctl = self.controller(_Client())
        ctl.logout()
        account_store.save_session({'lease': old}, self.store.path)
        self.assertEqual(ctl.entitlement().state, ent.CLOCK_SUSPECT)

    # ---- P2：设备、注销、导出 ----
    def test_devices_and_unbind_other_keeps_session(self):
        old = self._signed_in()
        listing = {'devices': [{'id': 'd1', 'current': True}, {'id': 'd2', 'current': False}], 'unbind_left': 2, 'max': 3}
        client = _Client(devices=success(listing), unbind_device=success({'ok': True, 'unbind_left': 1}))
        ctl = self.controller(client)
        self.assertTrue(ctl.devices(self.results.append))
        self.assertEqual(self.results[-1].data, listing)
        self.assertTrue(ctl.unbind('d2', self.results.append))
        self.assertTrue(self.results[-1].ok)
        self.assertEqual(client.calls, [('devices', (old,)), ('unbind_device', (old, 'd2'))])
        self.assertEqual(ctl.session()['lease'], old)

    def test_providers_use_lease_and_carry_no_key(self):
        old = self._signed_in()
        data = {'enabled': True, 'providers': [{'id': 'p', 'name': 'A', 'base_url': 'https://a.example/v1'}]}
        client = _Client(providers=success(data))
        ctl = self.controller(client)
        self.assertTrue(ctl.providers(self.results.append))
        self.assertEqual(self.results[-1].data, data)
        self.assertEqual(client.calls, [('providers', (old,))])
        self.assertIn('停用', account_client.MESSAGES['account_banned'])

    def test_unbind_current_device_clears_session(self):
        self._signed_in()
        ctl = self.controller(_Client(unbind_device=success({'ok': True})))
        ctl.unbind('d1', self.results.append, current=True)
        self.assertTrue(self.results[-1].ok)
        self.assertNotIn('refresh_token', ctl.session())
        self.assertEqual(ctl.entitlement().state, ent.SIGNED_OUT)

    def test_unbind_quota_exceeded_keeps_session(self):
        old = self._signed_in()
        ctl = self.controller(_Client(unbind_device=UserError('x', data={'code': 'unbind_quota_exceeded', 'retry_after': 60})))
        ctl.unbind('d1', self.results.append, current=True)
        self.assertEqual(self.results[-1].data['code'], 'unbind_quota_exceeded')
        self.assertEqual(ctl.session()['lease'], old)

    def test_lease_calls_renew_once_on_stale_lease(self):
        self._signed_in()
        fresh = sign(payload(nonce='f'))
        client = _Client(devices=[UserError('x', data={'code': 'session_invalid'}), success({'devices': []})],
                         renew=success({'refresh_token': 'r2', 'lease': fresh, 'server_time': NOW}))
        ctl = self.controller(client)
        ctl.devices(self.results.append)
        self.assertTrue(self.results[-1].ok)
        self.assertEqual([c[0] for c in client.calls], ['devices', 'renew', 'devices'])
        self.assertEqual(client.calls[2][1], (fresh,))

    def test_lease_calls_need_session(self):
        ctl = self.controller(_Client())
        for start in (lambda: ctl.devices(self.results.append), lambda: ctl.unbind('d', self.results.append),
                      lambda: ctl.request_delete_code(self.results.append),
                      lambda: ctl.request_deletion('1', self.results.append),
                      lambda: ctl.export(Path(self.temp.name) / 'x.json', self.results.append)):
            self.assertFalse(start())
        self.assertEqual(self.results, [])

    def test_delete_request_clears_session_and_failure_keeps_it(self):
        old = self._signed_in()
        ctl = self.controller(_Client(delete_code=success({'ok': True}),
                                      delete_request=[UserError('x', data={'code': 'code_invalid'}),
                                                      success({'ok': True, 'deletion_at': NOW + 7 * 86400})]))
        ctl.request_delete_code(self.results.append)
        self.assertTrue(self.results[-1].ok)
        ctl.request_deletion(' 123456 ', self.results.append)
        self.assertFalse(self.results[-1].ok)
        self.assertEqual(ctl.session()['lease'], old)
        ctl.request_deletion('123456', self.results.append)
        self.assertEqual(self.results[-1].data['deletion_at'], NOW + 7 * 86400)
        self.assertNotIn('lease', ctl.session())
        self.assertEqual(ctl._client.calls[1], ('delete_request', (old, '123456')))

    def test_cancel_deletion_uses_email_and_login_code_without_lease(self):
        client = _Client(delete_cancel=success({'ok': True}))
        ctl = self.controller(client)
        ctl.cancel_deletion(' a@b.c ', ' 654321 ', self.results.append)
        self.assertTrue(self.results[-1].ok)
        self.assertEqual(client.calls, [('delete_cancel', ('a@b.c', '654321'))])

    def test_request_code_passes_purpose(self):
        client = _Client(send_code=success({'ok': True}))
        ctl = self.controller(client)
        ctl.request_code(' a@b.cn ', self.results.append, purpose='register')
        ctl.request_code('a@b.cn', self.results.append)
        self.assertEqual(client.calls, [('send_code', ('a@b.cn', 'register')), ('send_code', ('a@b.cn', 'login'))])

    def test_password_login_and_register_save_session_with_has_password(self):
        for name, start in (('password_login', lambda ctl: ctl.password_login(' a@b.cn ', 'abc12345', self.results.append)),
                            ('register', lambda ctl: ctl.register(' a@b.cn ', ' 123456 ', 'abc12345', age_confirmed=True,
                                                                  done=self.results.append))):
            self.store.clear_session()
            reply = success({'refresh_token': 'r1', 'lease': sign(payload()), 'server_time': NOW,
                             'user': {'id': 'u1', 'has_password': True}})
            client = _Client(**{name: reply})
            ctl = self.controller(client)
            start(ctl)
            self.assertTrue(self.results[-1].ok, name)
            self.assertEqual(ctl.entitlement().state, ent.VALID)
            self.assertEqual((ctl.session()['email'], ctl.session()['has_password']), ('a@b.cn', True))
            self.assertEqual(client.calls[0][1][:3], ('a@b.cn', 'abc12345', ctl.device()) if name == 'password_login'
                             else ('a@b.cn', '123456', 'abc12345'))

    def test_password_login_failure_keeps_signed_out(self):
        ctl = self.controller(_Client(password_login=UserError('x', data={'code': 'password_invalid'})))
        ctl.password_login('a@b.cn', 'wrong123', self.results.append)
        self.assertEqual(self.results[-1].data['code'], 'password_invalid')
        self.assertEqual(ctl.entitlement().state, ent.SIGNED_OUT)

    def test_reset_password_signs_out_same_account_only(self):
        self._signed_in()
        ctl = self.controller(_Client(reset_password=success({'ok': True})))
        ctl.reset_password('other@b.cn', '1', 'abc12345', self.results.append)
        self.assertIn('refresh_token', ctl.session())
        ctl.reset_password(' A@B.C ', '1', 'abc12345', self.results.append)
        self.assertTrue(self.results[-1].ok)
        self.assertNotIn('refresh_token', ctl.session())

    def test_change_password_uses_lease_and_marks_has_password(self):
        self.assertFalse(self.controller(_Client()).change_password('abc12345', self.results.append))
        old = self._signed_in()
        client = _Client(change_password=success({'ok': True, 'has_password': True}))
        ctl = self.controller(client)
        self.assertTrue(ctl.change_password('abc12345', self.results.append))
        self.assertTrue(self.results[-1].ok)
        self.assertEqual(client.calls, [('change_password', (old, 'abc12345', None))])
        self.assertTrue(ctl.session()['has_password'])
        self.assertEqual(ctl.session()['lease'], old)

    def test_export_writes_chosen_file_with_redemptions(self):
        self._signed_in()
        data = {'account': {'id': 'u1'}, 'redemptions': [{'plan': 'monthly', 'days': 30, 'redeemed_at': NOW}]}
        target = Path(self.temp.name) / '导出' / 'account.json'
        ctl = self.controller(_Client(export=success(data)))
        self.assertTrue(ctl.export(target, self.results.append))
        self.assertEqual(self.results[-1].data, {'path': str(target)})
        self.assertEqual(json.loads(target.read_text(encoding='utf-8')), data)

    def test_export_failure_writes_nothing(self):
        self._signed_in()
        target = Path(self.temp.name) / 'account.json'
        ctl = self.controller(_Client(export=SystemError('x', data={'code': 'network'})))
        ctl.export(target, self.results.append)
        self.assertEqual(self.results[-1].data['code'], 'network')
        self.assertFalse(target.exists())
        blocked = Path(self.temp.name) / 'file'
        blocked.write_text('x', encoding='utf-8')
        ctl = self.controller(_Client(export=success({'redemptions': []})))
        ctl.export(blocked / 'sub.json', self.results.append)
        self.assertEqual(self.results[-1].data['code'], 'write_failed')


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
