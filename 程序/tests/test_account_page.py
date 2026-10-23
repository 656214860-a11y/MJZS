# -*- coding: utf-8 -*-
"""「00 会员账户」页（R1895）：登录表单发码后才能登录，登录成功切到已登录视图，退出回到表单。"""
import tempfile
import time
import unittest
import tk_test_support
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
from widget_test_support import widget_texts as _texts



class AccountPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.win=tk_test_support.make_root()
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
        tk_test_support.pump(cls.win,seconds)

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

    def test_membership_visibility_logged_out_and_expired(self):
        d=self.desktop
        store=self.use(_Client())
        d.go_page(PAGE_ACCOUNT);self.pump()
        self.assertTrue(any('永久免费' in t for t in _texts(d.content)))
        self.assertIn('（未登录）',d.account_button.cget('text'))
        import account_store
        account_store.save_session({'email':'a@b.c','refresh_token':'r','server_time':NOW,
            'lease':sign(payload(state='expired',trial_ends_at=NOW-86400))},store.path)
        d.go_page(PAGE_ACCOUNT);self.pump()
        texts=_texts(d.content)
        self.assertTrue(any('已于 ' in t and '到期' in t for t in texts))
        self.assertTrue(any('请联系发放兑换码的渠道' in t for t in texts))
        self.assertIn('（已到期）',d.account_button.cget('text'))
        d.account.logout();d.show(PAGE_ACCOUNT);self.pump()          # 还原成未登录页，不影响后续用例

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

    # ---- P2：设备、注销、导出 ----
    def signed_in(self,client):
        store=self.use(client)
        import account_store
        account_store.save_session({'email':'a@b.c','refresh_token':'r','lease':sign(payload()),'server_time':NOW},store.path)
        self.addCleanup(account_store.clear_session,store.path)   # 会话文件各用例共用，留着会污染未登录用例
        d=self.desktop
        d._account_confirm=lambda title,message:True
        self.addCleanup(d.__dict__.pop,'_account_confirm',None)
        d.go_page(PAGE_ACCOUNT);self.pump()
        return store

    def test_devices_list_and_unbind(self):
        d=self.desktop
        listing=lambda left:success({'devices':[{'id':'d1','name':'本机','os':'Windows 11','current':True},
                                                {'id':'d2','name':'笔记本','os':'Windows 10','current':False}],
                                     'max':3,'unbind_left':left,'next_unbind_at':None if left else NOW+86400})
        client=_Client(devices=[listing(2),listing(1)],unbind_device=success({'ok':True,'unbind_left':1}))
        self.signed_in(client)
        d.account_devices_button.invoke();self.pump()
        texts=_texts(d.account_devices_rows)
        self.assertTrue(any('本机（Windows 11） · 本机' in t for t in texts))
        self.assertIn('还可解绑 2 次',d.account_devices_message.cget('text'))
        unbind=[w for w in _walk(d.account_devices_rows) if _safe_text(w)=='解绑']
        self.assertEqual(len(unbind),2)
        unbind[1].invoke();self.pump()
        self.assertEqual([c[0] for c in client.calls],['devices','unbind_device','devices'])
        self.assertEqual(client.calls[1][1][1],'d2')
        self.assertIn('当前状态：授权有效',_texts(d.content))
        self.assertIn('还可解绑 1 次',d.account_devices_message.cget('text'))

    def test_providers_card_lists_without_key(self):
        d=self.desktop
        item={'id':'p','name':'线路A','base_url':'https://a.example/v1','models':'gpt-x','invite_url':'https://a.example/?aff=1','note':''}
        client=_Client(providers=success({'enabled':True,'providers':[item]}))
        self.signed_in(client)
        self.assertTrue(any('第三方服务' in t for t in _texts(d.content)))
        d.account_providers_button.invoke();self.pump()
        texts=_texts(d.account_providers_rows)
        self.assertTrue(any('https://a.example/v1' in t for t in texts))
        self.assertIn('注册／邀请链接',[_safe_text(w) for w in _walk(d.account_providers_rows)])

    def test_providers_card_empty_when_switched_off(self):
        d=self.desktop
        self.signed_in(_Client(providers=success({'enabled':False,'providers':[]})))
        d.account_providers_button.invoke();self.pump()
        self.assertEqual(d.account_providers_message.cget('text'),'当前没有推荐线路')

    def test_unbind_current_device_signs_out(self):
        d=self.desktop
        client=_Client(devices=success({'devices':[{'id':'d1','name':'本机','current':True}],'max':3,'unbind_left':1}),
                       unbind_device=success({'ok':True}))
        self.signed_in(client)
        d.account_devices_button.invoke();self.pump()
        [w for w in _walk(d.account_devices_rows) if _safe_text(w)=='解绑'][0].invoke();self.pump()
        self.assertIn('当前状态：未登录',_texts(d.content))
        self.assertIn('已解绑本机',d.status.get())

    def test_unbind_quota_disables_buttons(self):
        d=self.desktop
        self.signed_in(_Client(devices=success({'devices':[{'id':'d2','name':'笔记本'}],'max':3,'unbind_left':0,
                                                'next_unbind_at':NOW+86400})))
        d.account_devices_button.invoke();self.pump()
        button=[w for w in _walk(d.account_devices_rows) if _safe_text(w)=='解绑'][0]
        self.assertIn('disabled',button.state())
        self.assertIn('起可再解绑',d.account_devices_message.cget('text'))

    def test_delete_request_flow(self):
        d=self.desktop
        client=_Client(delete_code=success({'ok':True}),delete_request=success({'ok':True,'deletion_at':NOW+7*86400}))
        self.signed_in(client)
        self.assertIn('disabled',d.account_delete_button.state())
        d.account_delete_send_button.invoke();self.pump()
        self.assertNotIn('disabled',d.account_delete_button.state())
        d.account_delete_button.invoke();self.pump()
        self.assertTrue(d.account_delete_code_input.error_message)
        d.account_delete_code_input.insert(0,'123456');d.account_delete_button.invoke();self.pump()
        self.assertEqual([c[0] for c in client.calls],['delete_code','delete_request'])
        self.assertIn('当前状态：未登录',_texts(d.content))
        self.assertIn('已申请注销',d.status.get())

    def test_delete_request_cancelled_by_confirm(self):
        d=self.desktop
        client=_Client(delete_code=success({'ok':True}))
        self.signed_in(client)
        d._account_confirm=lambda title,message:False
        d.account_delete_send_button.invoke();self.pump()
        d.account_delete_code_input.insert(0,'123456');d.account_delete_button.invoke();self.pump()
        self.assertEqual([c[0] for c in client.calls],['delete_code'])
        self.assertIn('当前状态：授权有效',_texts(d.content))

    def test_export_writes_chosen_file(self):
        d=self.desktop
        data={'account':{'id':'u1'},'redemptions':[{'plan':'monthly','days':30,'redeemed_at':NOW}]}
        self.signed_in(_Client(export=success(data)))
        target=Path(self.temp.name)/'export'/'account.json'
        d._account_export_path=lambda:''
        self.addCleanup(d.__dict__.pop,'_account_export_path',None)
        d.account_export_button.invoke();self.pump()
        self.assertFalse(target.exists())                     # 取消选择不导出
        d._account_export_path=lambda:str(target)
        d.account_export_button.invoke();self.pump()
        import json
        self.assertEqual(json.loads(target.read_text(encoding='utf-8')),data)
        self.assertIn(str(target),d.account_export_message.cget('text'))

    def test_pending_deletion_login_offers_cancel(self):
        d=self.desktop
        from service_contract import UserError
        client=_Client(send_code=success({'ok':True}),
                       verify_code=UserError('账号正在注销冷静期，登录前需要先撤销注销',data={'code':'account_pending_deletion'}),
                       delete_cancel=success({'ok':True}))
        self.use(client)
        d.go_page(PAGE_ACCOUNT);self.pump()
        self.assertFalse(d.account_cancel_deletion_button.winfo_ismapped())
        d.account_email_input.insert(0,'a@b.c');d.account_send_button.invoke();self.pump()
        d.account_code_input.insert(0,'123456');d.account_login_button.invoke();self.pump()
        self.assertTrue(d.account_cancel_deletion_button.winfo_ismapped())
        self.assertIn('撤销注销',d.account_message.cget('text'))
        d.account_cancel_deletion_button.invoke();self.pump()
        self.assertEqual(client.calls[-1],('delete_cancel',('a@b.c','123456')))
        self.assertIn('已撤销注销',d.account_message.cget('text'))
        self.assertFalse(d.account_cancel_deletion_button.winfo_ismapped())


def _walk(widget):
    for child in widget.winfo_children():
        yield child
        yield from _walk(child)


def _safe_text(widget):
    try:return str(widget.cget('text'))
    except tk.TclError:return ''


if __name__=='__main__':
    unittest.main()
