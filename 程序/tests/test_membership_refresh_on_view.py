"""R2064：进账号页、窗口回前台时静默续签；后台顺延到期日后不必等 12 小时。"""
import unittest
from types import SimpleNamespace

import entitlement_service as ent
from orchestrator.account_controller import RENEW_INTERVAL, RENEW_VIEW_INTERVAL, AccountController
from desktop_account_page import AccountPageMixin
from desktop_page_registry import PAGE_ACCOUNT


class FakeAccount:
    def __init__(self, due=True):
        self.due, self.renews, self.period_end = due, [], 100

    def renew_due(self, interval=RENEW_INTERVAL):
        self.seen = interval
        return self.due

    def entitlement(self):
        return ent.Entitlement(ent.VALID, {'state': 'active', 'period_end': self.period_end})

    def renew(self, done=None, quiet=False):
        self.renews.append(quiet)
        self.period_end = 200          # 服务端顺延后租约里的到期日变了
        done(SimpleNamespace(ok=True))
        return True


class Host(AccountPageMixin):
    def __init__(self, account):
        self._account_controller, self.win, self.page_index = account, object(), PAGE_ACCOUNT
        self.shown, self.changed = [], 0

    def _account_changed(self):
        self.changed += 1

    def show(self, index):
        self.shown.append(index)


class RefreshOnViewTests(unittest.TestCase):
    def test_due_renews_quietly_and_redraws_only_when_expiry_changed(self):
        host = Host(FakeAccount())
        host.refresh_membership_view()
        self.assertEqual(host.account.renews, [True])
        self.assertEqual(host.account.seen, RENEW_VIEW_INTERVAL)
        self.assertEqual(host.shown, [PAGE_ACCOUNT])

    def test_throttled_when_renewed_recently(self):
        host = Host(FakeAccount(due=False))
        host.refresh_membership_view()
        self.assertEqual(host.account.renews, [])

    def test_focus_event_from_child_widget_is_ignored(self):
        host = Host(FakeAccount())
        host.refresh_membership_view(SimpleNamespace(widget=object()))
        self.assertEqual(host.account.renews, [])
        host.refresh_membership_view(SimpleNamespace(widget=host.win))
        self.assertEqual(host.account.renews, [True])

    def test_no_redraw_off_account_page(self):
        host = Host(FakeAccount())
        host.page_index = 0
        host.refresh_membership_view()
        self.assertEqual(host.shown, [])
        self.assertEqual(host.changed, 1)


class ControllerIntervalTests(unittest.TestCase):
    def test_renew_due_accepts_shorter_interval(self):
        clock = [1000.0]
        account = AccountController(submit=lambda *a: None, clock=lambda: clock[0])
        account.last_renew_at = 1000.0 - RENEW_VIEW_INTERVAL - 1
        self.assertTrue(account.renew_due(RENEW_VIEW_INTERVAL))
        self.assertFalse(account.renew_due())


if __name__ == '__main__':
    unittest.main()
