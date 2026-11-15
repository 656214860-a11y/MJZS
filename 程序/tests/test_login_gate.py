# -*- coding: utf-8 -*-
"""启动登录闸：未登录先盖登录页，登录后才启动；已登录（含到期）直接进。"""
import tempfile
import unittest
import unittest.mock
import tk_test_support
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))

import account_store
import lease_verifier
from account_controller import AccountController
from desktop import Desktop
from service_contract import success
import test_desktop_startup_perf as startup_fixtures
from test_account_client import KEYS, NOW, _Client, _Store, payload, sign

DAY=86400


class LoginGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.win=tk_test_support.make_root()
        cls.temp=tempfile.TemporaryDirectory(prefix='login-gate-')
        app,_project=startup_fixtures.DesktopStartupPerfTests._startup_app(cls.temp.name,remembered=False)
        original=Desktop.choose_project
        Desktop.choose_project=lambda self:None
        try:cls.desktop=Desktop(cls.win,root=app)
        finally:Desktop.choose_project=original
        cls.desktop.startup_controller.cancel()
        cls.desktop._startup_project_choice=False
        cls.desktop.root=None
        cls.keys=unittest.mock.patch.object(lease_verifier,'PUBLIC_KEYS',KEYS);cls.keys.start()
        tk_test_support.pump(cls.win,1.0)

    @classmethod
    def tearDownClass(cls):
        cls.keys.stop()
        cls.desktop.cancel_timers()
        cls.win.destroy()
        cls.temp.cleanup()

    def setUp(self):
        d=self.desktop
        d.login_gate=None;d.login_gate_active=False;d._login_gate_startup_pending=False;d._require_login=False

    def tearDown(self):
        gate=self.desktop.login_gate
        if gate is not None and gate.winfo_exists():gate.destroy()
        self.desktop.login_gate=None;self.desktop.login_gate_active=False
        self.desktop._require_login=False

    def use(self,client,*,enforce=True,lease=None):
        self._stores=getattr(self,'_stores',0)+1
        store=_Store(Path(self.temp.name)/('gate%d'%id(self))/('s%d'%self._stores)/'session.json')
        if lease is not None:
            account_store.save_session({'email':'a@b.c','refresh_token':'r','lease':lease,'server_time':NOW},store.path)
        self.desktop._account_controller=AccountController(
            submit=lambda work,done,label:done(work()),clock=lambda:NOW,store=store,client=client,enforce=enforce)
        return store

    def pump(self,seconds=.3):
        tk_test_support.pump(self.win,seconds)

    def test_not_required_builds_no_overlay_and_starts(self):
        self.use(_Client())
        started=[]
        self.desktop.begin_startup_or_login(False,lambda:started.append(1))
        self.assertIsNone(self.desktop.login_gate)
        self.assertEqual(started,[1])

    def test_signed_out_shows_gate_and_defers_startup(self):
        self.use(_Client())
        started=[]
        self.desktop.begin_startup_or_login(True,lambda:started.append(1))
        self.pump()
        self.assertTrue(self.desktop.login_gate_active)
        self.assertTrue(self.desktop.login_gate.winfo_exists())
        self.assertEqual(started,[])

    def test_gate_closes_visible_cloud_via_public_pet_api(self):
        class Pet:                                   # 只有公开接口，没有 _cloud
            closed=0
            def cloud_visible(self,sticker_only=False):return True
            def close_chat(self,event=None):Pet.closed+=1
        self.use(_Client())
        with unittest.mock.patch.object(self.desktop,'pet',Pet(),create=True):
            self.desktop.begin_startup_or_login(True,lambda:None)
        self.assertEqual(Pet.closed,1)

    def test_enforce_off_never_forces_login(self):
        self.use(_Client(),enforce=False)
        started=[]
        self.desktop.begin_startup_or_login(True,lambda:started.append(1))
        self.assertIsNone(self.desktop.login_gate)
        self.assertEqual(started,[1])

    def test_signed_in_states_pass_straight_through(self):
        cases={'valid':sign(payload()),
               'locked':sign(payload(state='expired',trial_ends_at=NOW-DAY)),
               'grace':sign(payload(expires_at=NOW-DAY,grace_until=NOW+DAY))}
        for name,lease in cases.items():
            with self.subTest(name):
                self.use(_Client(),lease=lease)
                started=[]
                self.desktop.begin_startup_or_login(True,lambda:started.append(1))
                self.assertIsNone(self.desktop.login_gate)
                self.assertEqual(started,[1])

    def test_login_through_gate_removes_overlay_and_runs_startup(self):
        client=_Client(send_code=success({'ok':True}),
                       verify_code=success({'refresh_token':'r1','lease':sign(payload()),'server_time':NOW}))
        self.use(client)
        started=[]
        d=self.desktop
        d.begin_startup_or_login(True,lambda:started.append(1))
        self.pump()
        d.account_email_input.insert(0,'a@b.cn');d.account_use_code_button.invoke();self.pump()      # 点「用验证码登录」直接发码并切到验证码视图
        d.account_code_input.insert(0,'123456');d.account_login_button.invoke();self.pump()
        self.assertFalse(d.login_gate_active)
        self.assertIsNone(d.login_gate)
        self.assertEqual(started,[1])

    def test_gate_login_redraws_account_page_underneath(self):
        """R2046：闸门下停着登录前画的「会员账户」页；闸门登录后须重画，不能露出旧的「未登录」。"""
        from desktop_page_registry import PAGE_ACCOUNT
        from widget_test_support import widget_texts
        client=_Client(send_code=success({'ok':True}),
                       verify_code=success({'refresh_token':'r1','server_time':NOW,
                                            'lease':sign(payload(state='expired',trial_ends_at=NOW-DAY))}))
        self.use(client)
        d=self.desktop
        d.show(PAGE_ACCOUNT);self.pump()
        self.assertIn('当前状态：未登录',widget_texts(d.content))
        d.begin_startup_or_login(True,lambda:None);self.pump()
        d.account_email_input.insert(0,'a@b.cn');d.account_use_code_button.invoke();self.pump()      # 点「用验证码登录」直接发码并切到验证码视图
        d.account_code_input.insert(0,'123456');d.account_login_button.invoke();self.pump()
        texts=widget_texts(d.content)
        self.assertIsNone(d.login_gate)
        self.assertIn('当前状态：授权已失效',texts)
        self.assertNotIn('当前状态：未登录',texts)
        d.account.logout()

    def test_logout_brings_gate_back(self):
        self.use(_Client(),lease=sign(payload()))
        d=self.desktop
        d.begin_startup_or_login(True,lambda:None)
        self.assertIsNone(d.login_gate)
        d.account.logout()
        d._account_changed();self.pump()
        self.assertTrue(d.login_gate_active)
        self.assertFalse(hasattr(d,'membership_badge'))   # R2027：侧栏到期小字已删

    def test_unlicensed_pages_are_locked_and_unlock_after_renewal(self):
        """R2048：授权失效时只放会员页与免费阶段，其余页整页锁定、侧栏挂锁；授权恢复后解锁并重建当前页。"""
        from desktop_account_page import NAV_LOCK_MARK
        from desktop_page_registry import PAGE, PAGE_ACCOUNT, PAGE_SITES, nav_label
        d=self.desktop
        store=self.use(_Client(),lease=sign(payload(state='expired',trial_ends_at=NOW-DAY)))
        d._require_login=True;d.refresh_nav_locks()
        def locked():
            return any(getattr(w,'cget',None) and _text(w)=='需要登录或授权' for w in _walk(d.content))
        try:
            self.assertEqual(d.nav[PAGE['storyboard']].cget('text'),nav_label(PAGE['storyboard'])+NAV_LOCK_MARK)
            self.assertEqual(d.nav[PAGE_SITES].cget('text'),nav_label(PAGE_SITES)+NAV_LOCK_MARK)
            self.assertEqual(d.nav[PAGE['script_structure']].cget('text'),nav_label(PAGE['script_structure']))
            d.show(PAGE_SITES);self.pump()
            self.assertTrue(locked())
            self.assertIn('试用或会员已到期',d.status.get())
            d.show(PAGE_ACCOUNT);self.pump()
            self.assertFalse(locked())
            d.show(PAGE_SITES);self.pump()
            account_store.save_session({'email':'a@b.c','refresh_token':'r','lease':sign(payload()),'server_time':NOW},store.path)
            d._account_changed();self.pump()
            self.assertEqual(d.nav[PAGE_SITES].cget('text'),nav_label(PAGE_SITES))
            self.assertFalse(locked())
        finally:
            d._require_login=False;d.refresh_nav_locks()


    def test_gate_prefills_the_last_login_email_even_after_logout(self):
        """R2052：登录框默认显示上一次登录的邮箱；退出登录后也保留，从没登录过则留空显示占位。"""
        d=self.desktop
        store=self.use(_Client())
        d.begin_startup_or_login(True,lambda:None);self.pump()
        self.assertEqual(d.account_email_input.get(),'','从没登录过：不预填')
        d.login_gate.destroy();d.login_gate=None;d.login_gate_active=False
        account_store.save_session({'email':'me@example.com','refresh_token':'r','lease':sign(payload()),'server_time':NOW},store.path)
        account_store.clear_session(store.path)
        self.assertEqual(account_store.last_email(store.path),'me@example.com')
        self.assertEqual(account_store.load(store.path).get('refresh_token'),None)
        d.begin_startup_or_login(True,lambda:None);self.pump()
        self.assertEqual(d.account_email_input.get(),'me@example.com')


def _walk(widget):
    for child in widget.winfo_children():
        yield child
        yield from _walk(child)


def _text(widget):
    try:return str(widget.cget('text'))
    except Exception:return ''

if __name__=='__main__':
    unittest.main()
