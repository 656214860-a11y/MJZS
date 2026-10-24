# -*- coding: utf-8 -*-
"""R1959：启动后自动的版本检查与续签不占独占后台、不写状态栏。

原先两者都走 ``async_queued``：联网期间 ``worker`` 为真，用户点任何按钮都被
“当前操作尚未结束”拦下，状态栏也被改成“检查新版本”。用户手动续签仍走独占后台。
"""
import sys
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import account_controller
from desktop_account_page import AccountPageMixin
from service_contract import success
import tk_test_support


class _Client:
    CLIENT_VERSION = '0.6'

    def meta(self):
        return success({'latest_version': '0.6'})

    def renew(self, token, device_id):
        return success({})


class _Store:
    load = staticmethod(lambda: {'refresh_token': 'r'})
    update_seen = staticmethod(lambda: '')
    mark_update_seen = staticmethod(lambda version: None)
    device_fingerprint = staticmethod(lambda: 'd')


class ControllerRoutingTests(unittest.TestCase):
    def _controller(self):
        self.submitted, self.background = [], []
        return account_controller.AccountController(
            submit=lambda work, done, label: self.submitted.append(label),
            background=lambda work, done, label: self.background.append(label),
            store=_Store, client=_Client())

    def test_automatic_checks_use_background(self):
        ctl = self._controller()
        ctl.check_update(lambda result: None)
        ctl.renew(quiet=True)
        self.assertEqual(self.background, ['检查新版本', '续签会员授权'])
        self.assertEqual(self.submitted, [])

    def test_manual_renew_stays_exclusive(self):
        ctl = self._controller()
        ctl.renew()
        self.assertEqual(self.submitted, ['续签会员授权'])
        self.assertEqual(self.background, [])

    def test_background_defaults_to_submit(self):
        submitted = []
        ctl = account_controller.AccountController(
            submit=lambda work, done, label: submitted.append(label), store=_Store, client=_Client())
        ctl.check_update(lambda result: None)
        self.assertEqual(submitted, ['检查新版本'])


class BackgroundChannelTests(unittest.TestCase):
    def setUp(self):
        self.win = tk.Tk()
        self.win.withdraw()
        self.addCleanup(lambda: self.win.winfo_exists() and self.win.destroy())

    def test_update_check_leaves_worker_and_status_alone(self):
        host = AccountPageMixin()
        host.win, host.worker, host.shutting_down = self.win, False, False
        host.status = mock.Mock()
        host.async_queued = mock.Mock(side_effect=AssertionError('自动检查不得走独占后台'))
        host._account_controller = account_controller.AccountController(
            submit=host._account_submit, background=host._account_background, store=_Store, client=_Client())
        got = []
        host.account.check_update(got.append)
        self.assertFalse(host.worker)
        tk_test_support.pump(self.win, 1.0)
        self.assertEqual(len(got), 1)
        self.assertTrue(got[0].ok)
        self.assertFalse(host.worker)
        host.status.set.assert_not_called()

    def test_no_delivery_after_shutdown(self):
        host = AccountPageMixin()
        host.win, host.shutting_down = self.win, True
        got = []
        host._account_background(lambda: success({}), got.append, '检查新版本')
        tk_test_support.pump(self.win, 0.5)
        self.assertEqual(got, [])


if __name__ == '__main__':
    unittest.main()
