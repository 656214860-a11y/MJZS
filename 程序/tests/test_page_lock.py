"""R2048：未登录或授权失效时，侧栏只放「00 会员账户」与免费阶段，其余整页换成锁定页。"""
import unittest

import entitlement_service as ent
import pet_bus
from account_controller import AccountController
from desktop_account_page import AccountPageMixin, NAV_LOCK_MARK
from desktop_page_registry import PAGES, PAGE_SITES, nav_label


class PageBlockMessageTests(unittest.TestCase):
    def test_free_stages_stay_open_and_others_lock_when_unusable(self):
        out = ent.Entitlement(ent.SIGNED_OUT)
        for stage in ent.FREE_STAGES:
            self.assertEqual(ent.page_block_message(out, stage, stage), '')
        self.assertIn('需要登录账号', ent.page_block_message(out, pet_bus.STAGES[2], '初步分镜'))
        self.assertIn('「参考网站」', ent.page_block_message(out, None, '参考网站'))
        expired = ent.Entitlement(ent.LOCKED, {'state': 'expired'})
        self.assertIn('试用或会员已到期', ent.page_block_message(expired, None, '参考网站'))

    def test_usable_entitlement_opens_everything(self):
        ok = ent.Entitlement(ent.VALID, {'state': 'trial'})
        self.assertEqual(ent.page_block_message(ok, None, '参考网站'), '')
        self.assertEqual(ent.page_block_message(ok, pet_bus.STAGES[-1], 'x'), '')

    def test_stage_block_message_unchanged(self):
        out = ent.Entitlement(ent.SIGNED_OUT)
        self.assertEqual(ent.stage_block_message(out, ent.FREE_STAGES[1]), '')
        self.assertIn('不受影响', ent.stage_block_message(out, pet_bus.STAGES[2]))


class PageGateControllerTests(unittest.TestCase):
    def controller(self, state, enforce=True):
        account = AccountController(submit=lambda *args: None, enforce=enforce)
        calls = []
        account.entitlement = lambda: calls.append(1) or ent.Entitlement(state)
        return account, calls

    def test_reads_entitlement_once_and_lists_only_locked_pages(self):
        account, calls = self.controller(ent.SIGNED_OUT)
        pages = [(0, ent.FREE_STAGES[0], 'a'), (2, pet_bus.STAGES[2], 'b'), (13, None, '参考网站')]
        self.assertEqual(set(account.page_gate(pages)), {2, 13})
        self.assertEqual(len(calls), 1)

    def test_switch_off_opens_everything(self):
        account, _ = self.controller(ent.SIGNED_OUT, enforce=False)
        self.assertEqual(account.page_gate([(13, None, '参考网站')]), {})


class FakeButton:
    def __init__(self, text):
        self.text = text

    def cget(self, key):
        return self.text

    def configure(self, text):
        self.text = text


class Host(AccountPageMixin):
    def __init__(self, locked, require_login=True):
        self._require_login = require_login
        self.locked = locked
        self.nav = [FakeButton(nav_label(index)) for index in range(len(PAGES))]
        self.page_index = PAGE_SITES
        self.shown = []
        self._account_controller = self

    def page_gate(self, pages):
        self.pages = pages
        return {index: 'locked' for index, _, _ in pages if index in self.locked}

    def show(self, index):
        self.shown.append(index)


class NavLockTests(unittest.TestCase):
    def test_marks_locked_pages_and_rebuilds_current_page_on_flip(self):
        host = Host(locked={2, PAGE_SITES})
        host.refresh_nav_locks()
        self.assertEqual(host.nav[2].text, nav_label(2) + NAV_LOCK_MARK)
        self.assertEqual(host.nav[1].text, nav_label(1))
        self.assertEqual(host.shown, [PAGE_SITES])
        self.assertEqual(host.pages[PAGE_SITES], (PAGE_SITES, None, '参考网站'))
        host.refresh_nav_locks()
        self.assertEqual(host.shown, [PAGE_SITES], '锁定状态没翻转就不重建')
        host.locked = set()
        host.refresh_nav_locks()
        self.assertEqual(host.nav[2].text, nav_label(2))
        self.assertEqual(host.shown, [PAGE_SITES, PAGE_SITES])

    def test_hosts_that_do_not_require_login_never_lock(self):
        host = Host(locked={2}, require_login=False)
        self.assertEqual(host.page_lock_reasons(), {})
        host.refresh_nav_locks()
        self.assertEqual(host.nav[2].text, nav_label(2))


if __name__ == '__main__':
    unittest.main()
