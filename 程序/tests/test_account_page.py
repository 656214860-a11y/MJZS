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
from desktop_page_registry import ACCOUNT_TITLE, PAGE_ACCOUNT
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
        store.path.unlink(missing_ok=True)      # R2052：会话文件各用例共用；退出登录会留下 last_email，每用例从空白开始
        self.desktop._account_controller=AccountController(
            submit=lambda work,done,label:done(work()),clock=lambda:NOW,store=store,client=client,enforce=True)
        self.desktop._account_controller.last_renew_at=NOW      # R2064：进账号页会静默续签；这里当作刚续过，各用例照旧只数自己的请求
        return store

    def test_login_flow_and_logout(self):
        d=self.desktop
        client=_Client(send_code=success({'ok':True}),
                       verify_code=success({'refresh_token':'r1','lease':sign(payload()),'server_time':NOW}))
        self.use(client)
        d.go_page(PAGE_ACCOUNT);self.pump()
        self.assertIn('当前状态：未登录',_texts(d.content))
        self.assertIn('disabled',d.account_login_button.state())
        d.account_use_code_button.invoke();self.pump()      # 默认是密码登录，先切到验证码登录
        d.account_email_input.insert(0,'a@b.cn');d.account_send_button.invoke();self.pump()
        self.assertNotIn('disabled',d.account_login_button.state())
        self.assertIn('验证码已发送',d.account_message.cget('text'))
        d.account_code_input.insert(0,'123456');d.account_login_button.invoke();self.pump()
        texts=_texts(d.content)
        self.assertIn('当前状态：授权有效',texts)
        self.assertIn('账号：a@b.cn',texts)
        self.assertIn('套餐：免费试用',texts)
        self.assertIn('退出登录',texts)
        self.assertEqual([c[0] for c in client.calls],['send_code','verify_code'])
        logout=[w for w in _walk(d.content) if _safe_text(w)=='退出登录'][0]   # R2025：按钮随状态卡标题行右移，改递归查找
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
        self.assertEqual(d.account_button.cget('text'),ACCOUNT_TITLE,'侧栏入口只显示名称，不带状态后缀')
        import account_store
        account_store.save_session({'email':'a@b.c','refresh_token':'r','server_time':NOW,
            'lease':sign(payload(state='expired',trial_ends_at=NOW-86400))},store.path)
        d.go_page(PAGE_ACCOUNT);self.pump()
        texts=_texts(d.content)
        self.assertTrue(any('已于 ' in t and '到期' in t for t in texts))
        self.assertTrue(any('输入兑换码即可续期' in t for t in texts))   # R2025 契约变更：文案精简
        self.assertEqual(d.account_button.cget('text'),ACCOUNT_TITLE)
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
        d.account_use_code_button.invoke();self.pump()      # 默认是密码登录，先切到验证码登录
        d.account_email_input.insert(0,'a@b.cn');d.account_send_button.invoke();self.pump()
        d.account_code_input.insert(0,'000000');d.account_login_button.invoke();self.pump()
        self.assertEqual(d.account_message.cget('text'),'验证码不正确或已过期')
        self.assertIn('当前状态：未登录',_texts(d.content))

    def test_login_reply_ok_but_still_signed_out_stays_on_form(self):
        """R2046：服务端回了成功，但本机验签后仍是未登录：留在表单报错，不跳转、不报「登录成功」。"""
        import account_store, entitlement_service
        d=self.desktop
        store=self.use(_Client(send_code=success({'ok':True}),
                               verify_code=success({'refresh_token':'r1','lease':sign(payload()),'server_time':NOW})))
        self.addCleanup(account_store.clear_session,store.path)
        d.go_page(PAGE_ACCOUNT);self.pump()
        d.status.set('')
        d.account_use_code_button.invoke();self.pump()
        d.account_email_input.insert(0,'a@b.cn');d.account_send_button.invoke();self.pump()
        with unittest.mock.patch.object(d.account,'entitlement',lambda:entitlement_service.Entitlement(entitlement_service.SIGNED_OUT)):
            d.account_code_input.insert(0,'123456');d.account_login_button.invoke();self.pump()
            self.assertIn('当前状态：未登录',_texts(d.content))
            self.assertIn('登录没有在本机生效',d.account_message.cget('text'))
            self.assertNotEqual(d.status.get(),'登录成功')

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

    def open_tool(self,key):
        """R2040：低频账号功能改为页面底部按钮＋弹窗，先点开弹窗再操作（断言未动）。"""
        self.desktop.account_tool_buttons[key].invoke();self.pump()
        self.addCleanup(self.desktop._account_close_dialog)
        return self.desktop.account_dialog

    def test_low_frequency_tools_are_bottom_buttons_opening_dialogs(self):
        d=self.desktop
        self.signed_in(_Client(devices=success({'devices':[],'max':3,'unbind_left':3})))
        self.assertEqual([d.account_tool_buttons[k].cget('text') for k in ('password','devices','export','delete')],
                         ['设置登录密码','已绑定设备','导出账号数据','注销账号'])
        texts=_texts(d.content)
        self.assertFalse(any('冷静期' in t for t in texts),'注销说明只在弹窗里')
        self.assertNotIn('6 位注销验证码',texts)
        for key,title in (('password','设置登录密码'),('devices','已绑定设备'),('export','导出账号数据'),('delete','注销账号')):
            dialog=self.open_tool(key)
            self.assertEqual(dialog.title(),title)
            self.assertTrue(dialog.winfo_exists())
        d._account_close_dialog();self.pump()
        self.assertIsNone(d.account_dialog)

    def test_devices_list_and_unbind(self):
        d=self.desktop
        listing=lambda left:success({'devices':[{'id':'d1','name':'本机','os':'Windows 11','current':True},
                                                {'id':'d2','name':'笔记本','os':'Windows 10','current':False}],
                                     'max':3,'unbind_left':left,'next_unbind_at':None if left else NOW+86400})
        client=_Client(devices=[listing(2),listing(1)],unbind_device=success({'ok':True,'unbind_left':1}))
        self.signed_in(client)
        self.open_tool('devices')
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
        self.open_tool('devices')
        [w for w in _walk(d.account_devices_rows) if _safe_text(w)=='解绑'][0].invoke();self.pump()
        self.assertIn('当前状态：未登录',_texts(d.content))
        self.assertIn('已解绑本机',d.status.get())

    def test_unbind_quota_disables_buttons(self):
        d=self.desktop
        self.signed_in(_Client(devices=success({'devices':[{'id':'d2','name':'笔记本'}],'max':3,'unbind_left':0,
                                                'next_unbind_at':NOW+86400})))
        self.open_tool('devices')
        button=[w for w in _walk(d.account_devices_rows) if _safe_text(w)=='解绑'][0]
        self.assertIn('disabled',button.state())
        self.assertIn('起可再解绑',d.account_devices_message.cget('text'))

    def test_delete_request_flow(self):
        d=self.desktop
        client=_Client(delete_code=success({'ok':True}),delete_request=success({'ok':True,'deletion_at':NOW+7*86400}))
        self.signed_in(client)
        self.open_tool('delete')
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
        self.open_tool('delete')
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
        self.open_tool('export')
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
        d.account_use_code_button.invoke();self.pump()      # 默认是密码登录，先切到验证码登录
        d.account_email_input.insert(0,'a@b.cn');d.account_send_button.invoke();self.pump()
        d.account_code_input.insert(0,'123456');d.account_login_button.invoke();self.pump()
        self.assertTrue(d.account_cancel_deletion_button.winfo_ismapped())
        self.assertIn('撤销注销',d.account_message.cget('text'))
        d.account_cancel_deletion_button.invoke();self.pump()
        self.assertEqual(client.calls[-1],('delete_cancel',('a@b.cn','123456')))
        self.assertIn('已撤销注销',d.account_message.cget('text'))
        self.assertFalse(d.account_cancel_deletion_button.winfo_ismapped())

    # ---- R2022：密码登录、注册、找回密码、本机校验 ----
    def signed_out_page(self, client):
        self.use(client)
        self.desktop.account.logout()      # 前面的用例可能在同一会话文件里留了登录态
        self.desktop.go_page(PAGE_ACCOUNT);self.desktop.show(PAGE_ACCOUNT);self.pump()   # 同页 go_page 不重画，show 强制重画
        return self.desktop

    def signed_in_reply(self):
        return success({'refresh_token':'r1','lease':sign(payload()),'server_time':NOW,'user':{'has_password':True}})

    def sign_out(self):
        self.desktop.account.logout();self.desktop.show(PAGE_ACCOUNT);self.pump()

    def test_password_login_is_default_and_masks_input(self):
        client=_Client(password_login=self.signed_in_reply())
        d=self.signed_out_page(client)
        self.assertEqual(d.account_login_view['view'],'pw')
        self.assertTrue(d.account_password_input.winfo_ismapped())
        self.assertFalse(d.account_code_input.winfo_ismapped())
        self.assertEqual(str(d.account_password_input.cget('show')),'','占位文字不被遮挡')
        d.account_email_input.insert(0,'a@b.cn');d.account_password_input.insert(0,'abc12345')
        self.assertEqual(str(d.account_password_input.cget('show')),'•')
        d.account_password_login_button.invoke();self.pump()
        self.assertIn('当前状态：授权有效',_texts(d.content))
        self.assertEqual(client.calls[0][0],'password_login')
        self.assertEqual(client.calls[0][1][:2],('a@b.cn','abc12345'))
        self.sign_out()

    def test_malformed_email_is_rejected_locally_with_error_style(self):
        client=_Client()
        d=self.signed_out_page(client)
        d.account_email_input.insert(0,'656214860@qqcom');d.account_password_input.insert(0,'abc12345')
        d.account_password_login_button.invoke();self.pump()
        self.assertIn('漏了',d.account_message.cget('text'))
        self.assertEqual(str(d.account_message.cget('style')),'Expired.TLabel')
        self.assertTrue(d.account_email_input.error_message)
        d.account_register_tab.invoke();d.account_register_send_button.invoke();self.pump()
        self.assertIn('漏了',d.account_message.cget('text'))
        self.assertEqual(client.calls,[],'格式不对不发请求')

    def test_login_failures_show_wait_and_fall_back_when_server_is_old(self):
        from service_contract import UserError
        client=_Client(password_login=[UserError('请求太频繁，请稍后再试',data={'code':'too_many_requests','retry_after':120}),
                                       UserError('账号服务返回错误（404）',data={'code':'http_404'})])
        d=self.signed_out_page(client)
        d.account_email_input.insert(0,'a@b.cn');d.account_password_input.insert(0,'abc12345')
        d.account_password_login_button.invoke();self.pump()
        self.assertIn('120 秒后可重试',d.account_message.cget('text'))
        self.assertEqual(str(d.account_message.cget('style')),'Expired.TLabel')
        d.account_password_login_button.invoke();self.pump()
        self.assertEqual(d.account_login_view['view'],'code')
        self.assertIn('验证码登录',d.account_message.cget('text'))

    def test_register_flow_checks_inputs_and_reports_duplicate(self):
        from service_contract import UserError
        client=_Client(send_code=[UserError('该邮箱已注册，请直接登录',data={'code':'email_registered'}),success({'ok':True})],
                       register=self.signed_in_reply())
        d=self.signed_out_page(client)
        d.account_register_tab.invoke();self.pump()
        self.assertEqual(d.account_login_view['view'],'reg')
        d.account_email_input.insert(0,'a@b.cn');d.account_register_send_button.invoke();self.pump()
        self.assertEqual(d.account_login_view['view'],'pw','已注册的邮箱回到密码登录')
        self.assertIn('已注册',d.account_message.cget('text'))
        d.account_register_tab.invoke();d.account_register_send_button.invoke();self.pump()
        self.assertIn('验证码已发送',d.account_message.cget('text'))
        self.assertIn('垃圾邮件',d.account_message.cget('text'))
        d.account_register_code_input.insert(0,'123456')
        d.account_register_password_input.insert(0,'abc12345');d.account_register_password2_input.insert(0,'abc12346')
        d.account_register_button.invoke();self.pump()
        self.assertIn('不一致',d.account_message.cget('text'))
        d.account_register_password2_input.delete(0,'end');d.account_register_password2_input.insert(0,'abc12345')
        d.account_register_button.invoke();self.pump()
        self.assertIn('18 周岁',d.account_message.cget('text'))
        self.assertEqual([c[0] for c in client.calls],['send_code','send_code'])
        d.account_register_adult.set(True);d.account_register_button.invoke();self.pump()
        self.assertIn('当前状态：授权有效',_texts(d.content))
        self.assertEqual(client.calls[0],('send_code',('a@b.cn','register')))
        self.assertEqual(client.calls[2][0],'register')
        self.sign_out()

    def test_weak_password_is_rejected_before_register(self):
        client=_Client(send_code=success({'ok':True}))
        d=self.signed_out_page(client)
        d.account_register_tab.invoke()
        d.account_email_input.insert(0,'a@b.cn');d.account_register_code_input.insert(0,'123456')
        d.account_register_password_input.insert(0,'abcdefgh');d.account_register_password2_input.insert(0,'abcdefgh')
        d.account_register_adult.set(True);d.account_register_button.invoke();self.pump()
        self.assertIn('字母和数字',d.account_message.cget('text'))
        self.assertTrue(d.account_register_password_input.error_message)
        self.assertEqual(client.calls,[])

    def test_reset_password_returns_to_password_view(self):
        client=_Client(send_code=success({'ok':True}),reset_password=success({'ok':True}))
        d=self.signed_out_page(client)
        d.account_forgot_button.invoke();self.pump()
        self.assertEqual(d.account_login_view['view'],'reset')
        d.account_email_input.insert(0,'a@b.cn');d.account_reset_send_button.invoke();self.pump()
        d.account_reset_code_input.insert(0,'654321')
        d.account_reset_password_input.insert(0,'new12345');d.account_reset_password2_input.insert(0,'new12345')
        d.account_reset_button.invoke();self.pump()
        self.assertEqual(d.account_login_view['view'],'pw')
        self.assertIn('密码已重置',d.account_message.cget('text'))
        self.assertEqual(client.calls,[('send_code',('a@b.cn','reset')),('reset_password',('a@b.cn','654321','new12345'))])

    def test_signed_in_password_card_sets_then_asks_old_password(self):
        client=_Client(change_password=success({'ok':True,'has_password':True}))
        store=self.use(client)
        import account_store
        lease=sign(payload())
        account_store.save_session({'email':'a@b.cn','refresh_token':'r','lease':lease,'server_time':NOW},store.path)
        d=self.desktop
        d.go_page(PAGE_ACCOUNT);self.pump()
        self.open_tool('password')
        self.assertIsNone(d.account_password_old_input,'没设过密码不要原密码')
        d.account_password_new_input.insert(0,'abc');d.account_password_button.invoke();self.pump()
        self.assertTrue(d.account_password_new_input.error_message)
        self.assertEqual(client.calls,[])
        d.account_password_new_input.delete(0,'end');d.account_password_new_input.insert(0,'abc12345')
        d.account_password_again_input.insert(0,'abc12345');d.account_password_button.invoke();self.pump()
        self.assertEqual(client.calls,[('change_password',(lease,'abc12345',None))])
        self.assertIn('密码已保存',d.status.get())
        self.assertIsNone(d.account_dialog,'保存成功后弹窗关闭')
        self.assertEqual(d.account_tool_buttons['password'].cget('text'),'修改登录密码')
        self.open_tool('password')
        self.assertIsNotNone(d.account_password_old_input,'设过密码后改密要原密码')
        self.sign_out()


def _walk(widget):
    for child in widget.winfo_children():
        yield child
        yield from _walk(child)


def _safe_text(widget):
    try:return str(widget.cget('text'))
    except tk.TclError:return ''


if __name__=='__main__':
    unittest.main()
