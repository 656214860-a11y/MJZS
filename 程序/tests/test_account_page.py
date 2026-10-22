# -*- coding: utf-8 -*-
"""「00 会员账户」页（R1895）：登录表单发码后才能登录，登录成功切到已登录视图，退出回到表单。"""
import tempfile
import time
import unittest
import unittest.mock
import tkinter as tk
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))

import lease_verifier
from account_controller import AccountController
from desktop import Desktop
from desktop_page_registry import PAGE_ACCOUNT
from service_contract import success
from skip_reasons import PLATFORM_TK_DISPLAY
import test_desktop_startup_perf as startup_fixtures
from test_account_client import KEYS, NOW, _Client, _Store, payload, sign


def _texts(widget):
    out=[]
    for child in widget.winfo_children():
        try:out.append(str(child.cget('text')))
        except tk.TclError:pass
        out.extend(_texts(child))
    return out


class AccountPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:cls.win=tk.Tk()
        except tk.TclError as exc:raise unittest.SkipTest(PLATFORM_TK_DISPLAY+': '+str(exc))
        cls.temp=tempfile.TemporaryDirectory(prefix='account-page-')
        app,_project=startup_fixtures.DesktopStartupPerfTests._startup_app(cls.temp.name,remembered=False)
        original=Desktop.choose_project
        Desktop.choose_project=lambda self:None
        try:cls.desktop=Desktop(cls.win,root=app)
        finally:Desktop.choose_project=original
        cls.desktop.startup_controller.cancel()
        cls.desktop._startup_project_choice=False
        cls.desktop.root=None
        cls.keys=unittest.mock.patch.object(lease_verifier,'PUBLIC_KEYS',KEYS);cls.keys.start()
        cls.pump(1.0)

    @classmethod
    def pump(cls,seconds=.3):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            cls.win.update_idletasks();cls.win.update();time.sleep(.005)

    @classmethod
    def tearDownClass(cls):
        cls.keys.stop()
        cls.desktop.cancel_timers()
        cls.win.destroy()
        cls.temp.cleanup()

    def use(self,client):
        store=_Store(Path(self.temp.name)/'acct'/'session.json')
        self.desktop._account_controller=AccountController(
            submit=lambda work,done,label:done(work()),clock=lambda:NOW,store=store,client=client,enforce=True)
        return store

    def test_login_flow_and_logout(self):
        d=self.desktop
        client=_Client(send_code=success({'ok':True}),
                       verify_code=success({'refresh_token':'r1','lease':sign(payload()),'server_time':NOW}))
        self.use(client)
        d.go_page(PAGE_ACCOUNT);self.pump()
        self.assertIn('当前状态：未登录',_texts(d.content))
        self.assertIn('disabled',d.account_login_button.state())
        d.account_email_input.insert(0,'a@b.c');d.account_send_button.invoke();self.pump()
        self.assertNotIn('disabled',d.account_login_button.state())
        self.assertIn('验证码已发送',d.account_message.cget('text'))
        d.account_code_input.insert(0,'123456');d.account_login_button.invoke();self.pump()
        texts=_texts(d.content)
        self.assertIn('当前状态：授权有效',texts)
        self.assertIn('账号：a@b.c',texts)
        self.assertIn('套餐：免费试用',texts)
        self.assertIn('退出登录',texts)
        self.assertEqual([c[0] for c in client.calls],['send_code','verify_code'])
        logout=[w for w in d.content.winfo_children() for w in [w,*w.winfo_children()] if _safe_text(w)=='退出登录'][0]
        logout.invoke();self.pump()
        self.assertIn('当前状态：未登录',_texts(d.content))

    def test_redeem_from_signed_in_view(self):
        d=self.desktop
        store=self.use(_Client(redeem=success({'lease':sign(payload(state='active',plan='quarterly',nonce='q')),'added_days':90})))
        import account_store
        account_store.save_session({'email':'a@b.c','refresh_token':'r','lease':sign(payload()),'server_time':NOW},store.path)
        d.go_page(PAGE_ACCOUNT);self.pump()
        self.assertIn('套餐：免费试用',_texts(d.content))
        d.account_redeem_button.invoke();self.pump()
        self.assertTrue(d.account_redeem_input.error_message)
        d.account_redeem_input.insert(0,'ABCD-EFGH-JKMN-PQRS');d.account_redeem_button.invoke();self.pump()
        self.assertIn('套餐：季度会员',_texts(d.content))
        self.assertIn('90 天',d.status.get())

    def test_plan_text(self):
        from desktop_account_page import plan_text
        self.assertEqual(plan_text({'state':'active','plan':'yearly'}),'年度会员')
        self.assertEqual(plan_text({'state':'active','plan':'lifetime'}),'会员')
        self.assertEqual(plan_text({'state':'expired','plan':'monthly'}),'已到期')
        self.assertEqual(plan_text({'state':'trial','plan':'trial'}),'免费试用')

    def test_failed_login_shows_reason_and_stays_on_form(self):
        d=self.desktop
        from service_contract import UserError
        self.use(_Client(send_code=success({'ok':True}),verify_code=UserError('验证码不正确或已过期',data={'code':'code_invalid'})))
        d.go_page(PAGE_ACCOUNT);self.pump()
        d.account_email_input.insert(0,'a@b.c');d.account_send_button.invoke();self.pump()
        d.account_code_input.insert(0,'000000');d.account_login_button.invoke();self.pump()
        self.assertEqual(d.account_message.cget('text'),'验证码不正确或已过期')
        self.assertIn('当前状态：未登录',_texts(d.content))


def _safe_text(widget):
    try:return str(widget.cget('text'))
    except tk.TclError:return ''


if __name__=='__main__':
    unittest.main()
