"""R2048：未登录或授权失效时，侧栏只放「00 会员账户」与免费阶段，其余整页换成锁定页。
R2933：图标轨上锁定不再追加 🔒 文字，改为把导航图标换成 lock.png。"""
import re
import tkinter as tk
import unittest
from tkinter import ttk

import entitlement_service as ent
import pet_bus
from account_controller import AccountController
from desktop_account_page import AccountPageMixin, NAV_LOCK_MARK
from desktop_page_registry import (NAV_LOCK_ICON, PAGE_NAV_ICONS, PAGES,
                                   PAGE_SITES)
from ui_icons import IconLoader


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


class Host(AccountPageMixin):
    def __init__(self, root, locked, require_login=True):
        self._require_login = require_login
        self.locked = locked
        # R2933：真图标钮——锁定走 IconLoader 换 lock.png，假按钮过不了 PhotoImage。
        self.nav = []
        for index in range(len(PAGES)):
            b = ttk.Button(root, text='', compound='image')
            b._nav_icon_name = PAGE_NAV_ICONS.get(index)
            self.nav.append(b)
        self.page_index = PAGE_SITES
        self.shown = []
        self._account_controller = self

    def page_gate(self, pages):
        self.pages = pages
        return {index: 'locked' for index, _, _ in pages if index in self.locked}

    def show(self, index):
        self.shown.append(index)


class NavLockTests(unittest.TestCase):
    def setUp(self):
        self.tk = tk.Tk()
        self.tk.withdraw()
        self.addCleanup(self.tk.destroy)

    def icon_of(self, button, name):
        return IconLoader.nav_icon(button, name)

    def image_name(self, widget):
        """ttk cget('image') 回的是 repr 元组串 "('pyimageN',)"，取引号内图像名。"""
        value = str(widget.cget('image'))
        found = re.findall(r"'([^']+)'", value)
        return found[0] if found else value

    def test_marks_locked_pages_and_rebuilds_current_page_on_flip(self):
        host = Host(self.tk, locked={2, PAGE_SITES})
        host.refresh_nav_locks()
        locked_btn, free_btn = host.nav[2], host.nav[1]
        self.assertTrue(locked_btn._nav_locked)
        self.assertEqual(self.image_name(locked_btn), str(self.icon_of(locked_btn, NAV_LOCK_ICON)),
                         '被锁页的图标换成 lock.png')
        self.assertEqual(str(locked_btn.cget('compound')), 'image')
        self.assertFalse(getattr(free_btn, '_nav_locked', False))
        self.assertEqual(host.nav[1].cget('text'), '')
        self.assertEqual(host.shown, [PAGE_SITES])
        self.assertEqual(host.pages[PAGE_SITES], (PAGE_SITES, None, '参考网站'))
        host.refresh_nav_locks()
        self.assertEqual(host.shown, [PAGE_SITES], '锁定状态没翻转就不重建')
        host.locked = set()
        host.refresh_nav_locks()
        self.assertFalse(locked_btn._nav_locked)
        self.assertEqual(self.image_name(locked_btn), str(self.icon_of(locked_btn, PAGE_NAV_ICONS[2])),
                         '授权恢复后换回原阶段图标')
        self.assertEqual(host.shown, [PAGE_SITES, PAGE_SITES])

    def test_lock_mark_text_is_only_a_png_missing_fallback(self):
        """PNG 都在时纯图标（compound=image、不带 🔒）；锁图标加载失败才退回文字锁标。"""
        host = Host(self.tk, locked={2})
        host.refresh_nav_locks()
        button = host.nav[2]
        if self.icon_of(button, NAV_LOCK_ICON) is None:
            self.assertEqual(str(button.cget('compound')), 'text')
            self.assertTrue(button.cget('text').endswith(NAV_LOCK_MARK))
        else:
            self.assertEqual(str(button.cget('compound')), 'image')
            self.assertNotIn('🔒', button.cget('text'))

    def test_hosts_that_do_not_require_login_never_lock(self):
        host = Host(self.tk, locked={2}, require_login=False)
        self.assertEqual(host.page_lock_reasons(), {})
        host.refresh_nav_locks()
        self.assertFalse(getattr(host.nav[2], '_nav_locked', False))


if __name__ == '__main__':
    unittest.main()
