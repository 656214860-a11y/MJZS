"""「00 会员账户」页：邮箱验证码登录、授权状态与退出（L4，只放 Tk 控件与事件绑定）。

状态机、网络与落盘都在 L3 ``account_controller.AccountController``；本 Mixin 只注入
后台提交回调（``async_queued`` 经 ``BackgroundTaskLifecycle``）并把结果画到页面上。
首帧之后才后台续签，启动路径不等网络。
"""
import time
import tkinter as tk
from tkinter import ttk

import entitlement_service
from account_controller import AccountController
from desktop_page_registry import PAGE_ACCOUNT
from ui_tokens import FONTS, SPACING, TEXT_DESC
from ui_widgets import Card, LineInput, PrimaryButton, SecondaryButton

RENEW_DELAY_MS = 3000
RENEW_CHECK_MS = 30 * 60 * 1000
STATE_TEXT = {
    entitlement_service.VALID: '授权有效',
    entitlement_service.GRACE: '离线宽限期内，请尽快联网续签',
    entitlement_service.LOCKED: '授权已失效（试用或会员到期，或离线超过宽限期）',
    entitlement_service.SIGNED_OUT: '未登录',
    entitlement_service.CLOCK_SUSPECT: '本机时间早于服务器时间，请校正系统时间后续签',
}
PLAN_TEXT = {'trial': '免费试用', 'active': '会员', 'expired': '已到期'}


def _when(stamp):
    return time.strftime('%Y-%m-%d %H:%M', time.localtime(int(stamp))) if stamp else '—'


class AccountPageMixin:
    @property
    def account(self):
        controller = self.__dict__.get('_account_controller')
        if controller is None:
            controller = self._account_controller = AccountController(submit=self._account_submit)
        return controller

    def _account_submit(self, work, done, label):
        self.async_queued(work, done, label=label, show_progress=False)

    def start_account_renewal(self):
        """首帧后由周期 tick 调用：到期才续签，失败静默，下一轮再试。"""
        if getattr(self, 'shutting_down', False):
            return
        try:
            if self.account.renew_due():
                self.account.renew(done=self._account_renewed)
        finally:
            self.win.after(RENEW_CHECK_MS, self.start_account_renewal)

    def _account_renewed(self, result):
        if getattr(self, 'page_index', None) == PAGE_ACCOUNT:
            self.show(PAGE_ACCOUNT)
        if not result.ok and (result.data or {}).get('code') != 'network':
            self.status.set('会员授权续签未成功：' + result.reason)

    def account_page(self):
        """未登录时显示邮箱登录表单；已登录时显示授权状态、到期时间与退出。"""
        self.note('账号用于试用与会员授权；项目和素材始终留在本机，不上传。')
        entitlement = self.account.entitlement()
        session = self.account.session()
        status = Card(self.content);status.pack(fill='x',pady=SPACING['xs'])
        ttk.Label(status,text='当前状态：'+STATE_TEXT.get(entitlement.state,entitlement.state),font=FONTS['heading_2']).pack(anchor='w')
        rule = '「01 剧本准备」「02 剧本结构」不登录也能用；从「03 初步分镜」起需要试用或会员。'
        if not self.account.enforce:rule += '（测试期暂不拦截）'
        ttk.Label(status,text=rule,
                  style='Muted.TLabel',wraplength=TEXT_DESC['wraplength'],justify='left').pack(anchor='w',pady=(SPACING['xs'],SPACING['none']))
        if session.get('refresh_token') or entitlement.payload:
            self._account_signed_in(status, entitlement, session)
        else:
            self._account_login_form()

    def _account_signed_in(self, card, entitlement, session):
        payload = entitlement.payload or {}
        lines = ['账号：'+str(session.get('email') or '—'),
                 '套餐：'+PLAN_TEXT.get(payload.get('state'),'—')]
        if payload.get('state') == 'trial':lines.append('试用到期：'+_when(payload.get('trial_ends_at')))
        if payload.get('state') == 'active':lines.append('会员到期：'+_when(payload.get('period_end')))
        lines.append('离线可用至：'+_when(payload.get('grace_until')))
        for line in lines:ttk.Label(card,text=line).pack(anchor='w',pady=SPACING['xs'])
        actions = ttk.Frame(self.content);actions.pack(anchor='w',pady=SPACING['sm'])
        def renew():
            if not self.account.renew(done=self._account_renewed):self.status.set('本机没有可续签的登录会话，请重新登录')
            else:self.status.set('正在续签会员授权…')
        def logout():
            self.account.logout();self.status.set('已退出登录（项目和素材不受影响）');self.show(PAGE_ACCOUNT)
        PrimaryButton(actions,text='立即续签',command=renew).pack(side='left',padx=(SPACING['none'],SPACING['sm']))
        SecondaryButton(actions,text='退出登录',command=logout).pack(side='left')

    def _account_login_form(self):
        form = Card(self.content);form.pack(fill='x',pady=SPACING['xs'])
        ttk.Label(form,text='邮箱验证码登录（新账号免费试用 3 天，每个账号最多绑定 3 台电脑）').pack(anchor='w',pady=SPACING['xs'])
        email = LineInput(form,placeholder='邮箱地址');email.pack(fill='x',pady=SPACING['xs'])
        code = LineInput(form,placeholder='6 位验证码');code.pack(fill='x',pady=SPACING['xs'])
        adult = tk.BooleanVar(value=False)
        ttk.Checkbutton(form,text='我已年满 18 周岁，并同意用户协议与隐私政策（首次注册必选）',variable=adult).pack(anchor='w',pady=SPACING['xs'])
        message = ttk.Label(form,text='',style='Muted.TLabel',wraplength=TEXT_DESC['wraplength'],justify='left')
        message.pack(anchor='w',pady=SPACING['xs'])
        actions = ttk.Frame(self.content);actions.pack(anchor='w',pady=SPACING['sm'])
        def alive():return bool(message.winfo_exists())
        def sent(result):
            if not alive():return
            send.state(['!disabled'])
            if result.ok:
                login.state(['!disabled']);message.configure(text='验证码已发送，请查收邮件（10 分钟内有效）')
            else:message.configure(text=result.reason)
        def send_code():
            if not email.get().strip():
                email.set_error('请填写邮箱');return
            email.clear_error();send.state(['disabled']);message.configure(text='正在发送验证码…')
            self.account.request_code(email.get(),sent)
        def logged_in(result):
            if not alive():return
            login.state(['!disabled'])
            if result.ok:
                self.status.set('登录成功');self.show(PAGE_ACCOUNT)
            else:message.configure(text=result.reason)
        def submit():
            if not code.get().strip():
                code.set_error('请填写验证码');return
            code.clear_error();login.state(['disabled']);message.configure(text='正在登录…')
            self.account.login(email.get(),code.get(),age_confirmed=adult.get(),done=logged_in)
        send = SecondaryButton(actions,text='发送验证码',command=send_code);send.pack(side='left',padx=(SPACING['none'],SPACING['sm']))
        login = PrimaryButton(actions,text='登录',command=submit);login.pack(side='left')
        login.state(['disabled'])                # 先发验证码，登录按钮才可用
        self.account_email_input,self.account_code_input,self.account_login_button = email,code,login
        self.account_send_button,self.account_message = send,message
