# -*- coding: utf-8 -*-
"""启动登录闸与到期摘要：未登录先盖登录页，登录后才启动；已登录（含到期）直接进；到期文案按状态给出。"""
import tempfile
import unittest
import unittest.mock
import tk_test_support
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))

import account_store
import entitlement_service as ent
import lease_verifier
from account_controller import AccountController
from desktop import Desktop
from service_contract import success
import test_desktop_startup_perf as startup_fixtures
from test_account_client import KEYS, NOW, _Client, _Store, payload, sign, evaluate

DAY=86400


class ExpirySummaryTests(unittest.TestCase):
    def test_trial_shows_date_and_days_left(self):
        text=ent.expiry_summary(evaluate(sign(payload())),NOW)
        self.assertTrue(text.startswith('试用至 '),text)
        self.assertIn('还剩 3 天',text)

    def test_active_membership(self):
        lease=sign(payload(state='active',plan='quarterly',period_end=NOW+40*DAY,expires_at=NOW+40*DAY,grace_until=NOW+43*DAY))
        text=ent.expiry_summary(evaluate(lease),NOW)
        self.assertTrue(text.startswith('会员至 '),text)
        self.assertIn('还剩 40 天',text)

    def test_expired_trial_asks_for_redeem(self):
        lease=sign(payload(state='expired',trial_ends_at=NOW-DAY))
        self.assertIn('到期',ent.expiry_summary(evaluate(lease),NOW))
        self.assertIn('兑换',ent.expiry_summary(evaluate(lease),NOW))

    def test_signed_out_and_missing_expiry_are_blank(self):
        self.assertEqual(ent.expiry_summary(ent.Entitlement(ent.SIGNED_OUT),NOW),'')
        lease=sign(payload(state='active',plan='lifetime',period_end=None))
        self.assertEqual(ent.expiry_summary(evaluate(lease),NOW),'')


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
        d.account_use_code_button.invoke();self.pump()      # 默认是密码登录，先切到验证码登录
        d.account_email_input.insert(0,'a@b.cn');d.account_send_button.invoke();self.pump()
        d.account_code_input.insert(0,'123456');d.account_login_button.invoke();self.pump()
        self.assertFalse(d.login_gate_active)
        self.assertIsNone(d.login_gate)
        self.assertEqual(started,[1])
        self.assertIn('试用至',d.membership_badge.cget('text'))

    def test_logout_brings_gate_back_and_badge_clears(self):
        self.use(_Client(),lease=sign(payload()))
        d=self.desktop
        d.begin_startup_or_login(True,lambda:None)
        self.assertIsNone(d.login_gate)
        self.assertIn('试用至',d.membership_badge.cget('text'))
        d.account.logout()
        d._account_changed();self.pump()
        self.assertTrue(d.login_gate_active)
        self.assertEqual(d.membership_badge.cget('text'),'')
        self.assertFalse(d.membership_badge.winfo_manager())


if __name__=='__main__':
    unittest.main()
