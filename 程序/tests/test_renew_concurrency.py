# -*- coding: utf-8 -*-
"""R2066：并发续签不得把正常会话当失效清掉。

服务端每次续签都换新刷新令牌、旧令牌立刻作废（重放即 401 session_invalid）。
窗口回前台续签、定时续签、带租约请求遇到租约过期时的自动续签若同时拿旧令牌发出，
第二个会被拒，本机原先随即清空登录（用户看到「突然退出登录」）。
"""
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orchestrator import account_controller
from tests.test_account_client import DID, KEYS, NOW, payload, sign
from contract.service_contract import UserError, success


class _Store:
    def __init__(self):
        self.data = {'refresh_token': 'r1', 'lease': sign(payload())}
        self.cleared = 0

    def load(self):
        return dict(self.data)

    def save_session(self, fields):
        self.data.update(fields)

    def clear_session(self):
        self.cleared += 1
        self.data = {}

    def device_fingerprint(self):
        return DID


class _Server:
    """只认当前刷新令牌；续签时可卡住，用来制造重叠。"""

    CLIENT_VERSION = '0.6'

    def __init__(self, hold=False):
        self.current, self.n, self.renew_calls = 'r1', 1, 0
        self.entered, self.release = threading.Event(), threading.Event()
        self.hold = hold

    def renew(self, token, device_id):
        self.renew_calls += 1
        self.entered.set()
        if self.hold:
            self.release.wait(5)
        if token != self.current:
            return UserError('x', data={'code': 'session_invalid'})
        self.n += 1
        self.current = 'r%d' % self.n
        return success({'refresh_token': self.current, 'lease': sign(payload(nonce=str(self.n))), 'server_time': 1})

    def devices(self, lease):
        if lease == sign(payload()):
            return UserError('x', data={'code': 'session_invalid'})
        return success({'devices': []})


class RenewConcurrencyTests(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.object(account_controller.lease_verifier, 'PUBLIC_KEYS', KEYS)
        patch.start()
        self.addCleanup(patch.stop)
        self.store, self.server = _Store(), _Server(hold=True)
        self.results, self.threads = [], []
        self.ctl = account_controller.AccountController(
            submit=self._submit, store=self.store, client=self.server, clock=lambda: NOW)

    def _submit(self, work, done, label):
        thread = threading.Thread(target=lambda: self.results.append((label, work())))
        self.threads.append(thread)
        thread.start()

    def _finish(self):
        self.server.release.set()
        for thread in self.threads:
            thread.join(5)

    def test_two_renews_with_same_token_keep_session(self):
        self.assertTrue(self.ctl.renew(quiet=True))
        self.assertTrue(self.server.entered.wait(5))
        self.assertTrue(self.ctl.renew(quiet=True))           # 第一个还在飞，第二个拿的仍是 r1
        time.sleep(0.2)                                        # 让第二个请求真的堵在锁上，再放行第一个
        self._finish()
        self.assertEqual(self.server.renew_calls, 1)           # 第二个发现令牌已换新，不再用旧令牌请求
        self.assertTrue(all(result.ok for _, result in self.results))
        self.assertEqual(self.store.cleared, 0)
        self.assertEqual(self.store.data['refresh_token'], 'r2')

    def test_lease_call_hitting_expired_lease_does_not_replay_old_token(self):
        self.ctl.renew(quiet=True)
        self.assertTrue(self.server.entered.wait(5))
        done = []
        self.assertTrue(self.ctl.devices(done.append))          # 用旧租约 L1 → session_invalid → 自动续签
        time.sleep(0.2)                                        # 让第二个请求真的堵在锁上，再放行第一个
        self._finish()
        self.assertEqual(self.server.renew_calls, 1)
        self.assertEqual(self.store.cleared, 0)
        by_label = dict(self.results)
        self.assertTrue(by_label['读取设备列表'].ok)             # 换新后的租约重试成功

    def test_really_dead_session_is_still_cleared(self):
        self.server.hold = False
        self.server.current = 'other'                          # 服务端已吊销本机令牌
        self.ctl.renew()
        self._finish()
        self.assertEqual(self.store.cleared, 1)
        self.assertFalse(self.results[0][1].ok)


if __name__ == '__main__':
    unittest.main()
