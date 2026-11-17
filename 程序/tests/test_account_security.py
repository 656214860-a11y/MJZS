# -*- coding: utf-8 -*-
"""账户会员客户端对抗测试（设计文档 说明/账户会员云端设计.md §8，R1905）。

每条都按攻击者手法构造本机状态，再看闸门是否放行；端到端走真实 ``account_store``
落盘（临时目录）与 ``AccountController(enforce=True)``，不只测纯函数。已由
``test_account_client`` 覆盖的条目不在这里重复，结果文件逐条引用。
"""
import json
import logging
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import account_client
from orchestrator import account_controller
from infra import account_store
import desktop_account_page
import entitlement_service as ent
from infra import lease_verifier
from orchestrator import stage_handler_registry
from pet_bus import STAGES
from contract.service_contract import SystemError, UserError, success
from test_account_client import D, DID, KEYS, NOW, _Client, _Store, _b64, payload, sign

PAID = [stage for stage in STAGES if ent.is_paid_stage(stage)]
EMAIL, TOKEN, CODE = 'victim.user@example.com', 'rt-SECRET-refresh-token-0123456789', '987654'


class _MachineStore(_Store):
    """另一台电脑：同一份会话文件，设备指纹不同。"""

    def __init__(self, path, did):
        super().__init__(path)
        self.did = did

    def __getattr__(self, name):
        if name == 'device_fingerprint':
            return lambda: self.did
        return super().__getattr__(name)


class _Desktop:
    def __init__(self, account):
        self.root, self.account, self.events = None, account, []
        self.pet = type('P', (), {'_emit': lambda _s, *a, **kw: self.events.append((a, kw))})()


class _Base(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='account-sec-')
        self.path = Path(self.temp.name) / 'private' / '账户' / 'session.json'
        self.results = []
        self.keys = unittest.mock.patch.object(lease_verifier, 'PUBLIC_KEYS', KEYS)
        self.keys.start()

    def tearDown(self):
        self.keys.stop()
        self.temp.cleanup()

    def controller(self, client=None, *, now=NOW, store=None):
        return account_controller.AccountController(
            submit=lambda work, done, label: (done or self.results.append)(work()),
            clock=lambda: now, store=store or _Store(self.path), client=client or _Client(), enforce=True)

    def save(self, lease, server_time=NOW, **extra):
        account_store.save_session(dict({'email': EMAIL, 'refresh_token': TOKEN, 'lease': lease,
                                         'server_time': server_time}, **extra), self.path)

    def assert_paid_blocked(self, ctl, needle='00 会员账户'):
        for stage in PAID:
            self.assertIn(needle, ctl.stage_gate(stage), stage)
        for stage in ent.FREE_STAGES:
            self.assertEqual(ctl.stage_gate(stage), '', stage)


class ClockTamperTests(_Base):
    """§8 第 1 条：改本地钟（回拨、前调）不能通过闸门。"""

    def test_rewound_clock_below_saved_server_time_is_suspect_and_blocked(self):
        self.save(sign(payload()), server_time=NOW + 6 * 3600)
        ctl = self.controller(now=NOW)
        self.assertEqual(ctl.entitlement().state, ent.CLOCK_SUSPECT)
        self.assert_paid_blocked(ctl, '本机时间早于服务器时间')

    def test_rewound_clock_before_issue_time_is_suspect_even_without_floor(self):
        self.save(sign(payload(issued_at=NOW)), server_time=0)
        ctl = self.controller(now=NOW - ent.CLOCK_TOLERANCE - 1)
        self.assertEqual(ctl.entitlement().state, ent.CLOCK_SUSPECT)
        self.assert_paid_blocked(ctl)

    def test_clock_moved_forward_past_grace_is_locked(self):
        self.save(sign(payload(state='active', plan='monthly', period_end=NOW + 30 * 86400)))
        self.assertEqual(self.controller(now=NOW + 8 * 86400).stage_gate(PAID[0]), '')   # 宽限期内仍可用
        ctl = self.controller(now=NOW + 10 * 86400)
        self.assertEqual(ctl.entitlement().state, ent.LOCKED)
        self.assert_paid_blocked(ctl, '宽限期')

    def test_forward_then_back_cannot_reopen_expired_lease(self):
        """前调到期后联网拿到更新的服务器时间，再回拨到旧租约有效期内也不行。"""
        old = sign(payload())
        self.save(old)
        account_store.note_server_time(NOW + 11 * 86400, self.path)
        ctl = self.controller(now=NOW + 3600)
        self.assertEqual(ctl.entitlement().state, ent.CLOCK_SUSPECT)
        self.assert_paid_blocked(ctl)


class FileTamperTests(_Base):
    """§8 第 2 条：手改本机状态文件、换用别的账号的文件，验签失败回到 signed_out。"""

    def _edit_lease(self, **over):
        sig = sign(payload()).split('.')[1]                # 保留原签名，只改正文
        return _b64(json.dumps(payload(**over), separators=(',', ':')).encode()) + '.' + sig

    def test_hand_edited_lease_fields_fail_verification(self):
        for over in ({'state': 'active'}, {'plan': 'yearly', 'state': 'active'},
                     {'expires_at': NOW + 10 ** 8, 'grace_until': NOW + 10 ** 8},
                     {'did': 'f' * 64}, {'kid': 'k2026a'}):
            self.save(self._edit_lease(**over))
            ctl = self.controller()
            self.assertEqual(ctl.entitlement().state, ent.SIGNED_OUT, over)
            self.assert_paid_blocked(ctl, '需要登录')

    def test_expired_lease_with_edited_session_fields_stays_locked(self):
        """会话文件里未签名的字段（邮箱、令牌、服务器时间调大）改了也不影响租约判定。"""
        self.save(sign(payload(state='expired')), server_time=NOW, email='vip@example.com')
        ctl = self.controller()
        self.assertEqual(ctl.entitlement().state, ent.LOCKED)
        self.assert_paid_blocked(ctl, '到期')

    def test_lease_of_wrong_type_or_garbage_file_is_signed_out(self):
        for lease in ({'state': 'active'}, 12345, ['a', 'b'], 'x' * 5000):
            self.save(lease)
            self.assertEqual(self.controller().entitlement().state, ent.SIGNED_OUT, type(lease))
        self.path.write_text('{"lease": "abc', encoding='utf-8')
        self.assert_paid_blocked(self.controller(), '需要登录')

    def test_session_file_from_other_account_on_other_machine_is_signed_out(self):
        self.save(sign(payload(uid='u-other', did='b' * 64, state='active', plan='yearly')))
        ctl = self.controller()
        self.assertEqual(ctl.entitlement().state, ent.SIGNED_OUT)
        self.assert_paid_blocked(ctl, '需要登录')


class ForgeAndReplayTests(_Base):
    """§8 第 3 条：重放旧租约、断网伪造租约（签名不对或 kid 未知）不能通过。"""

    def test_lease_signed_by_attacker_key_under_trusted_kid_is_rejected(self):
        forged = sign(payload(state='active'), d=D + 2)   # 不是那把私钥：签名对不上公钥
        self.save(forged)
        self.assert_paid_blocked(self.controller(), '需要登录')

    def test_test_key_lease_is_rejected_by_builtin_production_keys(self):
        self.keys.stop()
        try:
            for lease in (sign(payload(kid='k2026a')), sign(payload(kid='t1'))):
                self.save(lease)
                self.assertEqual(self.controller().entitlement().state, ent.SIGNED_OUT)
        finally:
            self.keys.start()

    def test_unsigned_and_alg_none_style_leases_are_rejected(self):
        body = _b64(json.dumps(payload(state='active')).encode())
        for lease in (body, body + '.', body + '.' + _b64(b'\x00' * 128), body + '.' + _b64(b'\x00\x01')):
            self.save(lease)
            self.assert_paid_blocked(self.controller(), '需要登录')

    def test_replayed_old_expired_lease_is_locked(self):
        old = sign(payload(issued_at=NOW - 20 * 86400, expires_at=NOW - 13 * 86400, grace_until=NOW - 10 * 86400))
        self.save(old)
        ctl = self.controller()
        self.assertEqual(ctl.entitlement().state, ent.LOCKED)
        self.assert_paid_blocked(ctl)

    def test_replay_after_logout_with_rewound_clock_is_suspect(self):
        self.save(sign(payload()), server_time=NOW + 9 * 86400)
        self.controller().logout()
        self.save(sign(payload()), server_time=0)          # 把旧租约抄回来，服务器时间字段写 0
        ctl = self.controller(now=NOW)
        self.assertEqual(ctl.entitlement().state, ent.CLOCK_SUSPECT)   # 退出时保留的时钟基线只增不减


class DeviceReuseTests(_Base):
    """§8 第 4 条：把租约和刷新令牌拷到另一台电脑，闸门不放行，续签以那台电脑的指纹发出。"""

    def test_copied_session_is_signed_out_on_other_machine(self):
        self.save(sign(payload(state='active', plan='yearly')))
        here = self.controller()
        self.assertEqual(here.stage_gate(PAID[0]), '')
        there = self.controller(store=_MachineStore(self.path, 'c' * 64))
        self.assertEqual(there.entitlement().state, ent.SIGNED_OUT)
        self.assert_paid_blocked(there, '需要登录')

    def test_renew_from_other_machine_sends_its_own_fingerprint_and_clears_on_invalid_device(self):
        self.save(sign(payload()))
        client = _Client(renew=UserError('x', data={'code': 'invalid_device'}))
        there = self.controller(client, store=_MachineStore(self.path, 'c' * 64))
        self.assertTrue(there.renew())
        self.assertEqual(client.calls, [('renew', (TOKEN, 'c' * 64))])
        self.assertNotIn('refresh_token', account_store.load(self.path))

    def test_renewed_lease_for_original_device_is_not_saved_on_copy(self):
        self.save(sign(payload()))
        stolen = sign(payload(nonce='n2'))                 # 服务端若误发原设备的租约，副本也不能落盘
        client = _Client(renew=success({'refresh_token': 'rt2', 'lease': stolen, 'server_time': NOW}))
        there = self.controller(client, store=_MachineStore(self.path, 'c' * 64))
        there.renew()
        self.assertEqual(self.results[-1].data['code'], 'lease_unverified')
        self.assertEqual(account_store.load(self.path)['refresh_token'], TOKEN)


class GateCoverageTests(_Base):
    """§8 第 5 条：从「初步分镜」起每个阶段都拦（手动、自动、三虎同经 start()），免费阶段与非阶段放行。"""

    def test_every_paid_stage_is_blocked_for_manual_and_auto_start(self):
        ctl = self.controller()                            # 未登录
        for stage in PAID:
            fallback = unittest.mock.Mock(return_value='ran')
            desk = _Desktop(ctl)
            self.assertIn('需要登录', stage_handler_registry.start(desk, stage, trigger='manual', fallback=fallback), stage)
            self.assertIn('需要登录', stage_handler_registry.start(desk, stage, trigger='auto', fallback=fallback), stage)
            fallback.assert_not_called()
            self.assertEqual(desk.events[-1][1].get('stage'), stage)

    def test_free_stages_and_non_stage_actions_pass(self):
        ctl = self.controller()
        self.assertEqual(ent.FREE_STAGES, tuple(STAGES[:2]))
        for stage in ent.FREE_STAGES:
            self.assertEqual(ctl.stage_gate(stage), '')
        for action in ('pet_performance', 'pet_test', 'account', 'open_project', ''):
            self.assertEqual(ctl.stage_gate(action), '', action)

    def test_paid_stage_runs_once_signed_in(self):
        self.save(sign(payload()))
        desk = _Desktop(self.controller())
        self.assertEqual(stage_handler_registry.start(desk, 'keyframe', fallback=lambda s, t: 'ran'), 'ran')

    def test_delivery_export_goes_through_gate(self):
        """「质检与交付」的成片导出（后期剪辑页按平台导出）不经 start()，单独过 account_blocked。"""
        source = (Path(__file__).resolve().parents[1] / 'desktop_media_pages.py').read_text(encoding='utf-8')
        line = next(text for text in source.splitlines() if 'controller.export_platform(' in text)
        self.assertIn("self.account_blocked('delivery') or", line)
        host = _Host(self.controller())
        self.assertTrue(host.account_blocked('delivery'))
        self.assertIn('质检与交付', host.statuses[-1])
        self.save(sign(payload()))
        self.assertFalse(_Host(self.controller()).account_blocked('delivery'))

    def test_switch_off_never_blocks_but_still_evaluates(self):
        ctl = account_controller.AccountController(submit=None, clock=lambda: NOW, store=_Store(self.path),
                                                   client=_Client(), enforce=False)
        self.assertEqual(ctl.entitlement().state, ent.SIGNED_OUT)
        self.assertEqual([ctl.stage_gate(stage) for stage in PAID], [''] * len(PAID))
        self.assertFalse(_Host(ctl).account_blocked('delivery'))


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.lines = []

    def emit(self, record):
        self.lines.append(self.format(record))


class SecretLeakTests(_Base):
    """§8 第 6 条：日志、任务标签、错误提示里不出现验证码、刷新令牌、租约或完整邮箱。"""

    def setUp(self):
        super().setUp()
        self.capture = _Capture()
        root = logging.getLogger()
        self.level = root.level
        root.addHandler(self.capture)
        root.setLevel(logging.DEBUG)

    def tearDown(self):
        root = logging.getLogger()
        root.removeHandler(self.capture)
        root.setLevel(self.level)
        super().tearDown()

    def assert_clean(self, *texts):
        lease = account_store.load(self.path).get('lease') or ''
        secrets = [EMAIL, TOKEN, CODE, 'rt-NEW-refresh-token-abcdefghijklmn'] + ([lease] if len(lease) > 8 else [])
        for text in list(texts) + self.capture.lines:
            for secret in secrets:
                self.assertNotIn(secret, str(text))

    def test_every_flow_keeps_secrets_out_of_logs_labels_and_reasons(self):
        labels = []
        fresh = sign(payload(nonce='fresh'))
        fail = UserError('x', data={'code': 'session_invalid'})
        client = _Client(
            send_code=success({}),
            verify_code=[UserError(account_client.MESSAGES['code_invalid'], data={'code': 'code_invalid'}),
                         success({'refresh_token': 'rt-NEW-refresh-token-abcdefghijklmn', 'lease': fresh,
                                  'server_time': NOW})],
            renew=[fail], redeem=UserError(account_client.MESSAGES['redeem_used'], data={'code': 'redeem_used'}),
            devices=success({'devices': []}), delete_code=success({}),
            delete_cancel=UserError(account_client.MESSAGES['code_invalid'], data={'code': 'code_invalid'}))
        ctl = account_controller.AccountController(
            submit=lambda work, done, label: (labels.append(label), self.results.append(work())),
            clock=lambda: NOW, store=_Store(self.path), client=client, enforce=True)
        ctl.request_code(EMAIL, None)
        ctl.login(EMAIL, CODE, age_confirmed=True, done=None)
        ctl.login(EMAIL, CODE, age_confirmed=True, done=None)
        ctl.redeem('ABCD-EFGH-IJKL-MNOP', None)
        ctl.devices(None)
        ctl.request_delete_code(None)
        ctl.cancel_deletion(EMAIL, CODE, None)
        ctl.renew()
        self.assertEqual(len(self.results), 8)
        self.assert_clean(*labels, *[r.reason for r in self.results],
                          *[json.dumps({k: v for k, v in (r.data or {}).items() if k != 'lease'}, ensure_ascii=False)
                            for r in self.results if not r.ok])

    def test_server_message_echoing_secrets_is_masked(self):
        lease = sign(payload())
        result = account_client._failure(400, {'code': 'brand_new_code',
                                                'message': '账号 %s 的令牌 %s 与租约 %s 无效' % (EMAIL, TOKEN, lease)})
        self.assertFalse(result.ok)
        self.assertIn('账号', result.reason)
        for secret in (EMAIL, TOKEN, lease, lease.split('.')[0]):
            self.assertNotIn(secret, result.reason)

    def test_unexpected_exception_does_not_carry_secret_text(self):
        boom = unittest.mock.Mock(side_effect=RuntimeError('refresh_token=%s email=%s' % (TOKEN, EMAIL)))
        client = _Client()
        client.renew = boom
        self.save(sign(payload()))
        ctl = self.controller(client)
        self.assertTrue(ctl.renew())
        result = self.results[-1]
        self.assertFalse(result.ok)
        self.assertEqual(result.data['code'], 'client_error')
        self.assertIn('RuntimeError', result.reason)
        self.assert_clean(result.reason, json.dumps(result.data))

    def test_network_failure_detail_is_only_exception_type(self):
        def opener(*a, **kw):
            raise OSError('connect to %s?refresh_token=%s failed' % (EMAIL, TOKEN))
        result = account_client.renew(TOKEN, DID, opener=opener)
        self.assertEqual(result.data, {'code': account_client.NETWORK, 'detail': 'OSError'})
        self.assert_clean(result.reason)


class _Win:
    def __init__(self):
        self.scheduled = []

    def after(self, ms, fn):
        self.scheduled.append((ms, fn))


class _Host(desktop_account_page.AccountPageMixin):
    """只带续签与闸门所需属性的宿主，不建 Tk 窗口。"""

    def __init__(self, controller):
        self._account_controller = controller
        self.win, self.statuses, self.page_index = _Win(), [], None
        self.status = type('S', (), {'set': lambda _s, text: self.statuses.append(text)})()

    def show(self, page):
        self.page_index = page


class RenewalScheduleTests(_Base):
    """§8 第 7 条（§4.3）：启动后与每 12 小时续签，失败静默、不弹窗，启动路径不等网络。"""

    def test_startup_path_reads_local_lease_without_network(self):
        self.save(sign(payload()))
        client = _Client()                                 # 没有任何预设回复：一旦联网就 KeyError
        ctl = account_controller.AccountController(submit=self.fail, clock=lambda: NOW,
                                                   store=_Store(self.path), client=client, enforce=True)
        self.assertEqual(ctl.entitlement().state, ent.VALID)
        self.assertEqual(ctl.stage_gate(PAID[0]), '')
        self.assertEqual(client.calls, [])
        tick = (Path(__file__).resolve().parents[1] / 'desktop_automation_tick.py').read_text(encoding='utf-8')
        self.assertIn('self.win.after(RENEW_DELAY_MS,self.start_account_renewal)', tick)

    def test_renews_at_startup_then_every_twelve_hours_in_background(self):
        self.save(sign(payload()))
        clock, submitted = [NOW], []
        client = _Client(renew=success({'refresh_token': 'rt2', 'lease': sign(payload(nonce='r')), 'server_time': NOW}))
        ctl = account_controller.AccountController(
            submit=lambda work, done, label: submitted.append((work, done, label)),
            clock=lambda: clock[0], store=_Store(self.path), client=client, enforce=True)
        host = _Host(ctl)
        host.start_account_renewal()
        self.assertEqual(len(submitted), 1)                # 首次检查立即续签
        self.assertEqual(client.calls, [])                 # 只提交后台任务，调用方不等网络
        self.assertEqual(host.win.scheduled[-1][0], desktop_account_page.RENEW_CHECK_MS)
        clock[0] += 11 * 3600
        host.start_account_renewal()
        self.assertEqual(len(submitted), 1)
        clock[0] += 3600
        host.start_account_renewal()
        self.assertEqual(len(submitted), 2)
        self.assertEqual(len(host.win.scheduled), 3)       # 每次检查都排下一次

    def test_failures_are_silent_without_dialogs(self):
        self.save(sign(payload()))
        client = _Client(renew=[SystemError('x', data={'code': 'network'}),
                                UserError(account_client.MESSAGES['session_invalid'], data={'code': 'session_invalid'})])
        ctl = account_controller.AccountController(
            submit=lambda work, done, label: done(work()), clock=lambda: NOW,
            store=_Store(self.path), client=client, enforce=True)
        host = _Host(ctl)
        with unittest.mock.patch('tkinter.messagebox.showerror', side_effect=AssertionError('popup')), \
                unittest.mock.patch('tkinter.messagebox.showwarning', side_effect=AssertionError('popup')), \
                unittest.mock.patch('tkinter.messagebox.showinfo', side_effect=AssertionError('popup')):
            host.start_account_renewal()
            self.assertEqual(host.statuses, [])            # 断网：完全静默，下一轮再试
            ctl.last_renew_at = 0
            host.start_account_renewal()
        self.assertEqual(len(host.statuses), 1)
        self.assertIn('请重新登录', host.statuses[0])


class RevokedSessionTests(_Base):
    """§8 第 8 条：服务端发现旧刷新令牌复用后吊销该账号全部会话，客户端干净回到 signed_out、不反复重试。"""

    def test_revoked_refresh_token_signs_out_and_stops_retrying(self):
        self.save(sign(payload()))
        revoked = UserError(account_client.MESSAGES['session_invalid'], data={'code': 'session_invalid', 'status': 401})
        client = _Client(renew=revoked)
        ctl = self.controller(client)
        host = _Host(ctl)
        host.start_account_renewal()
        self.assertEqual(ctl.entitlement().state, ent.SIGNED_OUT)
        self.assertNotIn('refresh_token', account_store.load(self.path))
        self.assertIn('请重新登录', host.statuses[-1])
        ctl.last_renew_at = 0
        host.start_account_renewal()                       # 下一轮检查：没有令牌，不再发请求
        self.assertFalse(ctl.renew())
        self.assertEqual([c[0] for c in client.calls], ['renew'])
        self.assert_paid_blocked(ctl, '需要登录')

    def test_lease_call_hits_401_then_revoked_renew_stops_after_one_round(self):
        self.save(sign(payload()))
        revoked = UserError('x', data={'code': 'session_invalid', 'status': 401})
        client = _Client(devices=revoked, renew=revoked, redeem=revoked)
        ctl = self.controller(client)
        self.assertTrue(ctl.devices(self.results.append))
        self.assertEqual([c[0] for c in client.calls], ['devices', 'renew'])
        self.assertEqual(self.results[-1].data['code'], 'session_invalid')
        self.assertEqual(ctl.entitlement().state, ent.SIGNED_OUT)
        self.assertFalse(ctl.devices(self.results.append))         # 会话已清：后续调用不再发请求
        self.assertFalse(ctl.redeem('X', self.results.append))
        self.assertEqual(len(client.calls), 2)

    def test_revoked_page_shows_login_form(self):
        self.save(sign(payload()))
        ctl = self.controller(_Client(renew=UserError('x', data={'code': 'session_invalid'})))
        host = _Host(ctl)
        host.page_index = desktop_account_page.PAGE_ACCOUNT
        ctl.renew(done=host._account_renewed)
        session = ctl.session()
        self.assertFalse(session.get('refresh_token') or ctl.entitlement().payload)   # 账号页据此画登录表单


if __name__ == '__main__':
    unittest.main()
