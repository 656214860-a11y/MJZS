# -*- coding: utf-8 -*-
"""侧栏「00 会员账户」入口：排在 01 之上、不挤动阶段页序号、没项目也能进。"""
import tempfile
import time
import unittest
import tk_test_support
import tkinter as tk
import sys
from pathlib import Path

HERE=str(Path(__file__).resolve().parents[1])
sys.path.insert(0,HERE)
sys.path.insert(0,str(Path(__file__).resolve().parent))

import pet_bus
from account_controller import AccountController
from desktop import Desktop, PAGES
from desktop_page_registry import ACCOUNT_TITLE, PAGE, PAGE_ACCOUNT, PAGE_SITES, nav_label, page_title
from skip_reasons import PLATFORM_TK_DISPLAY
import test_desktop_startup_perf as startup_fixtures
from test_account_client import NOW, _Client, _Store


class AccountRegistryTests(unittest.TestCase):
    def test_account_page_does_not_shift_stage_pages(self):
        self.assertEqual(PAGES[0][:2],'01')
        self.assertEqual(len(PAGES),len(pet_bus.STAGES)+1)
        self.assertEqual(PAGE_SITES,len(PAGES)-1)
        self.assertNotIn(PAGE_ACCOUNT,PAGE.values())
        self.assertNotIn(ACCOUNT_TITLE,PAGES)
        self.assertEqual(page_title(PAGE_ACCOUNT),'00  会员账户')
        self.assertEqual(page_title(0),PAGES[0])


class AccountEntryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.win=tk_test_support.make_root()
        cls.temp=tempfile.TemporaryDirectory(prefix='account-entry-')
        app,_project=startup_fixtures.DesktopStartupPerfTests._startup_app(cls.temp.name,remembered=False)
        original=Desktop.choose_project
        Desktop.choose_project=lambda self:None
        try:cls.desktop=Desktop(cls.win,root=app)
        finally:Desktop.choose_project=original
        cls.desktop.startup_controller.cancel()
        cls.desktop._startup_project_choice=False
        cls.desktop.root=None
        # R2042：账号存储绑到临时目录，不读本机 private/账户/session.json 里的真实登录会话
        store=_Store(Path(cls.temp.name)/'acct'/'session.json')
        cls.desktop._account_controller=AccountController(
            submit=lambda work,done,label:done(work()),clock=lambda:NOW,store=store,client=_Client(),enforce=True)
        cls.pump(1.0)

    @classmethod
    def pump(cls,seconds=.3):
        tk_test_support.pump(cls.win,seconds)

    @classmethod
    def tearDownClass(cls):
        cls.desktop.cancel_timers()
        cls.win.destroy()
        cls.temp.cleanup()

    def test_account_button_sits_above_first_stage(self):
        d=self.desktop
        self.assertEqual(d.account_button.cget('text'),nav_label(PAGE_ACCOUNT))
        self.assertNotIn(d.account_button,d.nav)
        self.assertEqual(len(d.nav),len(PAGES))
        self.assertLess(d.account_button.winfo_y(),d.nav[0].winfo_y())

    def test_account_page_opens_without_project(self):
        d=self.desktop
        d.go_page(PAGE_ACCOUNT);self.pump()
        self.assertEqual(d.page_index,PAGE_ACCOUNT)
        self.assertEqual(d.title.cget('text'),ACCOUNT_TITLE)
        # R2933：导航纯图标轨，选中态走 RailIcon 样式（原 Nav.TButton 胶囊样式退役）。
        self.assertEqual(d.account_button.cget('style'),'Selected.RailIcon.TButton')
        self.assertTrue(all(b.cget('style')=='RailIcon.TButton' for b in d.nav))
        self.assertIn('disabled',d.account_login_button.state())
        d.go_page(PAGE_SITES);self.pump()
        self.assertEqual(d.account_button.cget('style'),'RailIcon.TButton')
        self.assertEqual(d.nav[PAGE_SITES].cget('style'),'Selected.RailIcon.TButton')


if __name__=='__main__':
    unittest.main()
