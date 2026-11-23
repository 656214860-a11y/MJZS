# -*- coding: utf-8 -*-
"""版本更新提示：宽松版本比较、三种状态判定、软提示每版本只主动提一次。"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orchestrator import account_controller
from infra import account_store
from infra import update_notice as un
from contract.service_contract import success


class FakeClient:
    CLIENT_VERSION = '0.6-20260918'

    def __init__(self, meta):
        self.body = meta

    def meta(self):
        return success(self.body)


class UpdateNoticeTests(unittest.TestCase):
    def test_lenient_parse_and_compare(self):
        self.assertEqual(un.parse_version('V0.7'), (0, 7))
        self.assertEqual(un.parse_version('0.6-20260918'), (0, 6))
        self.assertIsNone(un.parse_version('beta'))
        self.assertEqual(un.evaluate({'latest_version': '0.6.0'}, '0.6')['level'], un.NONE)

    def test_three_states(self):
        self.assertEqual(un.evaluate({'min_client_version': '0.0.0'}, '0.6')['level'], un.NONE)
        soft = un.evaluate({'latest_version': '1.0', 'download_url': 'https://e.com/d', 'release_notes': '修复'}, '0.6')
        self.assertEqual((soft['level'], soft['url']), (un.SOFT, 'https://e.com/d'))
        hard = un.evaluate({'min_client_version': '0.8', 'latest_version': '1.0'}, '0.6')
        self.assertEqual(hard['level'], un.HARD)

    def test_unsafe_url_dropped_and_bad_input_ignored(self):
        self.assertEqual(un.evaluate({'latest_version': '1.0', 'download_url': 'http://e.com'}, '0.6')['url'], '')
        self.assertEqual(un.evaluate(None, '0.6')['level'], un.NONE)
        self.assertEqual(un.evaluate({'latest_version': '1.0'}, 'dev')['level'], un.NONE)

    def test_soft_prompt_once_per_version_hard_always(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'session.json'

            class Store:
                update_seen = staticmethod(lambda: account_store.update_seen(path))
                mark_update_seen = staticmethod(lambda v: account_store.mark_update_seen(v, path))

            def run(meta):
                got = []
                ctl = account_controller.AccountController(
                    submit=lambda work, done, label: done(work()), store=Store, client=FakeClient(meta))

                def done(result):
                    got.append(result)
                    notice = result.data or {}
                    # 展示回调成功后才记「已见」（与桌面 _update_checked 同契约）
                    if notice.get('level') == un.SOFT and notice.get('proactive'):
                        ctl.mark_update_seen(notice['version'])

                ctl.check_update(done)
                return got[0].data
            soft = {'latest_version': '1.0'}
            self.assertTrue(run(soft)['proactive'])
            self.assertFalse(run(soft)['proactive'])
            self.assertTrue(run({'latest_version': '1.1'})['proactive'])
            hard = {'min_client_version': '0.9'}
            self.assertTrue(run(hard)['proactive'] and run(hard)['proactive'])

    def test_soft_seen_not_marked_when_display_callback_crashes(self):
        """展示前回写已见会导致崩溃后该版本软提示永久丢失（AUD-BOOT D4）。"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'session.json'

            class Store:
                update_seen = staticmethod(lambda: account_store.update_seen(path))
                mark_update_seen = staticmethod(lambda v: account_store.mark_update_seen(v, path))

            soft = {'latest_version': '1.0'}
            ctl = account_controller.AccountController(
                submit=lambda work, done, label: done(work()), store=Store, client=FakeClient(soft))

            def crash(_result):
                raise RuntimeError('display failed')

            with self.assertRaises(RuntimeError):
                ctl.check_update(crash)
            self.assertEqual(account_store.update_seen(path), '')
            got = []
            ctl.check_update(got.append)
            self.assertTrue(got[0].ok and got[0].data['proactive'])

    def test_update_checked_marks_soft_only_after_status(self):
        """桌面展示回调：状态栏写成功后才 mark；写失败则不 mark。"""
        from desktop_account_page import AccountPageMixin

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'session.json'

            class Store:
                update_seen = staticmethod(lambda: account_store.update_seen(path))
                mark_update_seen = staticmethod(lambda v: account_store.mark_update_seen(v, path))

            ctl = account_controller.AccountController(
                submit=lambda work, done, label: done(work()), store=Store, client=FakeClient({'latest_version': '1.0'}))
            notice = {'level': un.SOFT, 'version': '1.0', 'proactive': True, 'text': '有新版本 1.0', 'url': '', 'notes': ''}

            class StatusOk:
                def set(self, text):
                    self.text = text

            host = type('Host', (), {})()
            host.shutting_down = False
            host.page_index = None
            host.account = ctl
            host.status = StatusOk()
            host.update_notice = None
            AccountPageMixin._update_checked(host, success(notice))
            self.assertEqual(account_store.update_seen(path), '1.0')

            account_store.mark_update_seen('', path)
            self.assertEqual(account_store.update_seen(path), '')

            class StatusBoom:
                def set(self, text):
                    raise RuntimeError('status failed')

            host.status = StatusBoom()
            with self.assertRaises(RuntimeError):
                AccountPageMixin._update_checked(host, success(notice))
            self.assertEqual(account_store.update_seen(path), '')

    def test_clear_session_keeps_update_seen(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 's.json'
            account_store.save_session({'email': 'a@b.c'}, path)
            account_store.mark_update_seen('1.0', path)
            account_store.clear_session(path)
            self.assertEqual(account_store.update_seen(path), '1.0')


if __name__ == '__main__':
    unittest.main()
