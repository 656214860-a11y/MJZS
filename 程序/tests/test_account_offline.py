"""自检不碰账号服务器与真实会话：DRAMA_SUPPRESS_NETWORK=1 时 account_client 默认入口不联网。

起因：测试里构造的真实 Desktop 用默认 AccountController 读本机会话并续签；后台全量多进程
并发拿同一刷新令牌续签，触发服务端令牌重用检测吊销整条会话，用户下次启动要重新登录。
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import account_client
import account_controller
import account_store
import entitlement_service

ROOT = Path(__file__).resolve().parents[1]


class _TempStore:
    """真实 account_store 读写，路径换成临时文件。"""

    def __init__(self, path):
        self.path = path

    def load(self):
        return account_store.load(self.path)

    def save_session(self, fields):
        return account_store.save_session(fields, self.path)

    def clear_session(self):
        return account_store.clear_session(self.path)

    def device_fingerprint(self):
        return 'd' * 64


class SuppressedNetworkTests(unittest.TestCase):
    def setUp(self):
        for patch in (mock.patch.dict('os.environ', {account_client.SUPPRESS_NETWORK_ENV: '1'}),
                      mock.patch.object(account_client.platform_tools, 'open_https',
                                        side_effect=AssertionError('自检不该联网'))):
            patch.start()
            self.addCleanup(patch.stop)

    def test_selftest_runner_sets_the_switch(self):
        source = (ROOT / 'run_selftests.py').read_text(encoding='utf-8')
        self.assertIn('os.environ.setdefault("%s", "1")' % account_client.SUPPRESS_NETWORK_ENV, source)

    def test_default_endpoints_return_network_without_calling_opener(self):
        for call in (lambda: account_client.renew('R', 'd'), lambda: account_client.meta(),
                     lambda: account_client.me('L'), lambda: account_client.devices('L')):
            result = call()
            self.assertFalse(result.ok)
            self.assertEqual(result.data['code'], account_client.NETWORK)
        account_client.platform_tools.open_https.assert_not_called()

    def test_injected_opener_still_used(self):
        calls = []

        def fake(url, **kw):
            calls.append(url)
            raise OSError('down')
        self.assertEqual(account_client.meta(opener=fake).data['code'], account_client.NETWORK)
        self.assertEqual(calls, [account_client.BASE_URL + '/v1/meta'])

    def test_renew_keeps_local_session(self):
        """续签按网络不通处理：不清会话、不换令牌，下次启动仍是登录状态。"""
        patch = mock.patch.object(account_controller.entitlement_service, 'evaluate',
                                  return_value=entitlement_service.Entitlement(entitlement_service.VALID))
        patch.start()
        self.addCleanup(patch.stop)
        with tempfile.TemporaryDirectory(prefix='account-offline-') as temp:
            store = _TempStore(Path(temp) / 'session.json')
            store.save_session({'refresh_token': 'r1', 'lease': 'L1', 'email': 'a@qq.com'})
            results = []
            ctl = account_controller.AccountController(
                submit=lambda work, done, label: results.append(work()), store=store, clock=lambda: 1000)
            self.assertTrue(ctl.renew(quiet=True))
            self.assertEqual(results[0].data['code'], account_client.NETWORK)
            self.assertEqual((store.load()['refresh_token'], store.load()['lease']), ('r1', 'L1'))
        account_client.platform_tools.open_https.assert_not_called()


if __name__ == '__main__':
    unittest.main()
