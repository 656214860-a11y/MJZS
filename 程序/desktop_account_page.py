"""「00 会员账户」页：邮箱验证码登录、授权状态、退出、兑换、设备解绑、注销与撤销、数据导出（L4，只放 Tk 控件与事件绑定）。

状态机、网络与落盘都在 L3 ``account_controller.AccountController``；本 Mixin 只注入
后台提交回调（``async_queued`` 经 ``BackgroundTaskLifecycle``）并把结果画到页面上。
首帧之后才后台续签，启动路径不等网络。
"""
import time
import webbrowser
import tkinter as tk
from tkinter import ttk

import entitlement_service
from account_controller import AccountController
from desktop_page_registry import ACCOUNT_TITLE, PAGE_ACCOUNT
from ui_tokens import FONTS, SPACING, TEXT_DESC
from ui_widgets import Card, LineInput, PrimaryButton, SecondaryButton, ask_confirmation

RENEW_DELAY_MS = 3000
RENEW_CHECK_MS = 30 * 60 * 1000
STATE_TEXT = {
    entitlement_service.VALID: '授权有效',
    entitlement_service.GRACE: '离线宽限期内，请尽快联网续签',
    entitlement_service.LOCKED: '授权已失效（试用或会员到期，或离线超过宽限期）',
    entitlement_service.SIGNED_OUT: '未登录',
    entitlement_service.CLOCK_SUSPECT: '本机时间早于服务器时间，请校正系统时间后续签',
}
PLAN_TEXT = {'trial': '免费试用', 'monthly': '月度会员', 'quarterly': '季度会员', 'yearly': '年度会员'}
PROVIDER_NOTICE = '以下为第三方服务，模型费用由对应服务商另行计费，不属于会员；使用时请遵守当地法律与服务商条款，生成内容的合规由使用者自负。软件不提供也不保管任何 Key。'
REDEEM_MAX_LENGTH = 40
EXPORT_NAME = '漫剧助手账号数据_%Y%m%d.json'


def plan_text(payload):
    """租约里的套餐名：到期优先显示「已到期」，未登记的 plan 按会员状态兜底。"""
    if payload.get('state') == 'expired':
        return '已到期'
    return PLAN_TEXT.get(payload.get('plan')) or ('会员' if payload.get('state') == 'active' else '—')


def _when(stamp):
    return time.strftime('%Y-%m-%d %H:%M', time.localtime(int(stamp))) if stamp else '—'


def device_text(device):
    """设备行文字：名称（系统）、本机标记、首次与最近使用时间。"""
    mark = ' · 本机' if device.get('current') else ''
    return '%s（%s）%s  首次 %s · 最近 %s' % (device.get('name') or '—', device.get('os') or '—', mark,
                                         _when(device.get('first_seen')), _when(device.get('last_seen')))


class AccountPageMixin:
    @property
    def account(self):
        controller = self.__dict__.get('_account_controller')
        if controller is None:
            controller = self._account_controller = AccountController(submit=self._account_submit)
        return controller

    def _account_submit(self, work, done, label):
        self.async_queued(work, done, label=label, show_progress=False)

    def account_blocked(self, stage):
        """不经 ``stage_handler_registry.start()`` 的付费动作（如成片导出）在这里过闸门。

        拦截时把原因写进状态栏并返回 True；放行（含总开关关闭）返回 False。
        """
        reason = self.account.stage_gate(stage)
        if isinstance(reason, str) and reason:
            self.status.set(reason)
            self.refresh_account_badge()
            return True
        return False

    def refresh_account_badge(self):
        """侧栏「00 会员账户」按钮后缀：未登录／剩 ≤3 天／已到期时带一句短标记，正常时还原。"""
        button = getattr(self, 'account_button', None)
        if button is None:
            return
        badge = entitlement_service.membership_view(self.account.entitlement(), self.account.now())['badge']
        button.configure(text=ACCOUNT_TITLE + ('（%s）' % badge if badge else ''))

    def start_account_renewal(self):
        """首帧后由周期 tick 调用：到期才续签，失败静默，下一轮再试。"""
        if getattr(self, 'shutting_down', False):
            return
        try:
            self.refresh_account_badge()
            if self.account.renew_due():
                self.account.renew(done=self._account_renewed)
        finally:
            self.win.after(RENEW_CHECK_MS, self.start_account_renewal)

    def start_update_check(self):
        """首帧后检查一次新版本（与续签分开排程）；联网失败静默。"""
        if not getattr(self, 'shutting_down', False):
            self.account.check_update(self._update_checked)

    def _update_checked(self, result):
        """新版提示：账号页常驻显示；软提示每个版本只在状态栏主动提一次，强制升级每次都提。"""
        if not result.ok or getattr(self, 'shutting_down', False):
            return
        notice = result.data or {}
        self.update_notice = notice
        if notice.get('level') == 'none':
            return
        if notice.get('proactive'):
            self.status.set(notice.get('text') or '有新版本')
        if getattr(self, 'page_index', None) == PAGE_ACCOUNT:
            self.show(PAGE_ACCOUNT)

    def _account_update_card(self):
        notice = getattr(self, 'update_notice', None) or {}
        if notice.get('level') not in ('soft', 'hard'):
            return
        card = Card(self.content);card.pack(fill='x',pady=SPACING['xs'])
        title = '必须升级' if notice['level'] == 'hard' else '发现新版本'
        ttk.Label(card,text=title,font=FONTS['heading_2']).pack(anchor='w')
        ttk.Label(card,text=notice.get('text') or '',wraplength=TEXT_DESC['wraplength'],justify='left').pack(anchor='w',pady=SPACING['xs'])
        if notice.get('url'):
            PrimaryButton(card,text='去下载',command=lambda u=notice['url']:webbrowser.open(u)).pack(anchor='w',pady=SPACING['xs'])

    def _account_renewed(self, result):
        if not result.ok and (result.data or {}).get('code') == 'client_too_old':
            self.account.check_update(self._update_checked)
        if getattr(self, 'page_index', None) == PAGE_ACCOUNT:
            self.show(PAGE_ACCOUNT)
        if not result.ok and (result.data or {}).get('code') != 'network':
            self.status.set('会员授权续签未成功：' + result.reason)

    def account_page(self):
        """未登录时显示邮箱登录表单；已登录时显示授权状态、到期时间与退出。"""
        self.note('账号用于试用与会员授权；项目和素材始终留在本机，不上传。')
        entitlement = self.account.entitlement()
        session = self.account.session()
        self._account_update_card()
        status = Card(self.content);status.pack(fill='x',pady=SPACING['xs'])
        ttk.Label(status,text='当前状态：'+STATE_TEXT.get(entitlement.state,entitlement.state),font=FONTS['heading_2']).pack(anchor='w')
        view = entitlement_service.membership_view(entitlement, self.account.now())
        style = {'warn': 'Warn.TLabel', 'expired': 'Expired.TLabel'}.get(view['level'], 'Muted.TLabel')
        for line in view['lines']:
            ttk.Label(status,text=line,style=style,wraplength=TEXT_DESC['wraplength'],justify='left').pack(anchor='w',pady=(SPACING['xs'],SPACING['none']))
        self.refresh_account_badge()
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
                 '套餐：'+plan_text(payload)]
        if payload.get('state') == 'trial':lines.append('试用到期：'+_when(payload.get('trial_ends_at')))
        if payload.get('state') == 'active':lines.append('会员到期：'+_when(payload.get('period_end')))
        lines.append('离线可用至：'+_when(payload.get('grace_until')))
        for line in lines:ttk.Label(card,text=line).pack(anchor='w',pady=SPACING['xs'])
        actions = ttk.Frame(self.content);actions.pack(anchor='w',pady=SPACING['sm'])
        def renew():
            if not self.account.renew(done=self._account_renewed):self.status.set('本机没有可续签的登录会话，请重新登录')
            else:self.status.set('正在续签会员授权…')
        def logout():
            self.account.logout();self.show(PAGE_ACCOUNT);self.status.set('已退出登录（项目和素材不受影响）')
        PrimaryButton(actions,text='立即续签',command=renew).pack(side='left',padx=(SPACING['none'],SPACING['sm']))
        SecondaryButton(actions,text='退出登录',command=logout).pack(side='left')
        self._account_redeem_form()
        self._account_providers_card()
        self._account_devices_card()
        self._account_export_card()
        self._account_delete_card()

    def _account_confirm(self, title, message):
        return ask_confirmation(self.win, title, message, dangerous=True)

    def _account_export_path(self):
        return self.file_dialog.save_file(title='导出账号数据', defaultextension='.json',
                                          initialfile=time.strftime(EXPORT_NAME), filetypes=[('JSON','*.json')])

    def _account_providers_card(self):
        """推荐线路：只展示地址与说明，Key 由用户自己在模型设置的自定义提供方里填写；总开关关闭时不显示内容。"""
        card = Card(self.content);card.pack(fill='x',pady=SPACING['xs'])
        ttk.Label(card,text='推荐模型线路（第三方服务）').pack(anchor='w',pady=SPACING['xs'])
        ttk.Label(card,text=PROVIDER_NOTICE,style='Muted.TLabel',wraplength=TEXT_DESC['wraplength'],
                  justify='left').pack(anchor='w',pady=SPACING['xs'])
        rows = ttk.Frame(card);rows.pack(fill='x')
        message = ttk.Label(card,text='',style='Muted.TLabel',wraplength=TEXT_DESC['wraplength'],justify='left')
        def listed(result):
            if not message.winfo_exists():return
            button.state(['!disabled'])
            for child in rows.winfo_children():child.destroy()
            if not result.ok:message.configure(text=result.reason);return
            items = (result.data or {}).get('providers') or []
            message.configure(text='' if items else '当前没有推荐线路')
            for item in items:self._account_provider_row(rows,item)
        def load():
            button.state(['disabled']);message.configure(text='正在读取…')
            if not self.account.providers(listed):
                button.state(['!disabled']);message.configure(text='本机没有登录会话，请重新登录')
        button = SecondaryButton(card,text='查看推荐线路',command=load);button.pack(anchor='w',pady=SPACING['xs'])
        message.pack(anchor='w',pady=SPACING['xs'])
        self.account_providers_button,self.account_providers_rows,self.account_providers_message = button,rows,message

    def _account_provider_row(self, rows, item):
        row = ttk.Frame(rows);row.pack(fill='x',pady=SPACING['xs'])
        lines = [str(item.get('name') or '—'),'接口地址：'+str(item.get('base_url') or '—')]
        if item.get('models'):lines.append('模型：'+str(item['models']))
        if item.get('note'):lines.append(str(item['note']))
        ttk.Label(row,text=chr(10).join(lines),wraplength=TEXT_DESC['wraplength'],justify='left').pack(side='left')
        def copy():
            if not self.copy_text(str(item.get('base_url') or '')):
                self.status.set('已复制接口地址，请到模型设置的自定义提供方里填写，并填入你自己的 Key')
        SecondaryButton(row,text='复制地址',command=copy).pack(side='right')
        invite = str(item.get('invite_url') or '')
        if invite.startswith('https://'):
            SecondaryButton(row,text='注册／邀请链接',command=lambda u=invite:webbrowser.open(u)).pack(side='right',padx=SPACING['xs'])

    def _account_devices_card(self):
        """已绑定设备：按需联网读取（不在每次画页时请求），可解绑；解绑本机即退出登录。"""
        card = Card(self.content);card.pack(fill='x',pady=SPACING['xs'])
        ttk.Label(card,text='已绑定设备（每个账号最多 3 台，30 天内最多解绑 2 次）').pack(anchor='w',pady=SPACING['xs'])
        rows = ttk.Frame(card);rows.pack(fill='x')
        message = ttk.Label(card,text='',style='Muted.TLabel',wraplength=TEXT_DESC['wraplength'],justify='left')
        message.pack(anchor='w',pady=SPACING['xs'])
        def listed(result):
            if not message.winfo_exists():return
            button.state(['!disabled'])
            if result.ok:self._account_device_rows(rows,message,result.data or {},load)
            else:message.configure(text=result.reason)
        def load():
            button.state(['disabled']);message.configure(text='正在读取设备列表…')
            if not self.account.devices(listed):
                button.state(['!disabled']);message.configure(text='本机没有登录会话，请重新登录')
        button = SecondaryButton(card,text='查看已绑定设备',command=load);button.pack(anchor='w',pady=SPACING['xs'])
        self.account_devices_button,self.account_devices_rows,self.account_devices_message = button,rows,message

    def _account_device_rows(self, rows, message, data, reload):
        for child in rows.winfo_children():child.destroy()
        devices = data.get('devices') or []
        left = int(data.get('unbind_left') or 0)
        summary = '已绑 %d/%s 台，30 天内还可解绑 %d 次'%(len(devices),data.get('max') or 3,left)
        if not left and data.get('next_unbind_at'):summary += '（%s 起可再解绑）'%_when(data.get('next_unbind_at'))
        message.configure(text=summary)
        for device in devices:
            row = ttk.Frame(rows);row.pack(fill='x',pady=SPACING['xs'])
            ttk.Label(row,text=device_text(device)).pack(side='left')
            unbind = SecondaryButton(row,text='解绑',command=lambda d=device:self._account_unbind(d,message,reload))
            unbind.pack(side='right')
            if not left:unbind.state(['disabled'])

    def _account_unbind(self, device, message, reload):
        current = bool(device.get('current'))
        warning = '解绑本机后会退出登录，需要重新登录。' if current else '解绑后那台电脑的登录立即失效。'
        if not self._account_confirm('解绑设备','确定解绑「%s」？%s'%(device.get('name') or '—',warning)):return
        def unbound(result):
            if not message.winfo_exists():return
            if not result.ok:message.configure(text=result.reason);return
            if current:self.show(PAGE_ACCOUNT);self.status.set('已解绑本机并退出登录');return
            self.status.set('已解绑设备');reload()
        message.configure(text='正在解绑…')
        if not self.account.unbind(device.get('id'),unbound,current=current):message.configure(text='本机没有登录会话，请重新登录')

    def _account_export_card(self):
        """导出账号数据（账号、同意记录、设备、会员与兑换记录）到用户选定的 JSON 文件。"""
        card = Card(self.content);card.pack(fill='x',pady=SPACING['xs'])
        ttk.Label(card,text='导出账号数据（账号、同意记录、设备、会员与兑换记录；不含项目和素材）').pack(anchor='w',pady=SPACING['xs'])
        message = ttk.Label(card,text='',style='Muted.TLabel',wraplength=TEXT_DESC['wraplength'],justify='left')
        def exported(result):
            if not message.winfo_exists():return
            button.state(['!disabled'])
            message.configure(text='已导出到 '+result.data['path'] if result.ok else result.reason)
        def export():
            target = self._account_export_path()
            if not target:return
            button.state(['disabled']);message.configure(text='正在导出…')
            if not self.account.export(target,exported):
                button.state(['!disabled']);message.configure(text='本机没有登录会话，请重新登录')
        button = SecondaryButton(card,text='导出账号数据',command=export);button.pack(anchor='w',pady=SPACING['xs'])
        message.pack(anchor='w',pady=SPACING['xs'])
        self.account_export_button,self.account_export_message = button,message

    def _account_delete_card(self):
        """注销：先发注销用途验证码，凭码进入 7 天冷静期；成功后本机退出登录。"""
        card = Card(self.content);card.pack(fill='x',pady=SPACING['xs'])
        ttk.Label(card,text='注销账号：进入 7 天冷静期，期间可在登录页用登录验证码撤销；到期后删除账号数据。本机项目和素材不受影响。',
                  wraplength=TEXT_DESC['wraplength'],justify='left').pack(anchor='w',pady=SPACING['xs'])
        code = LineInput(card,placeholder='6 位注销验证码');code.pack(fill='x',pady=SPACING['xs'])
        message = ttk.Label(card,text='',style='Muted.TLabel',wraplength=TEXT_DESC['wraplength'],justify='left')
        actions = ttk.Frame(card)
        def sent(result):
            if not message.winfo_exists():return
            send.state(['!disabled'])
            if result.ok:confirm.state(['!disabled']);message.configure(text='注销验证码已发送到账号邮箱')
            else:message.configure(text=result.reason)
        def send_code():
            send.state(['disabled']);message.configure(text='正在发送注销验证码…')
            if not self.account.request_delete_code(sent):
                send.state(['!disabled']);message.configure(text='本机没有登录会话，请重新登录')
        def requested(result):
            if not message.winfo_exists():return
            confirm.state(['!disabled'])
            if not result.ok:message.configure(text=result.reason);return
            self.show(PAGE_ACCOUNT);self.status.set('已申请注销，冷静期至 %s；期间可在登录页撤销'%_when((result.data or {}).get('deletion_at')))
        def submit():
            if not code.get().strip():
                code.set_error('请填写注销验证码');return
            code.clear_error()
            if not self._account_confirm('注销账号','确定注销？7 天冷静期内可以撤销，到期后账号数据会被删除。'):return
            confirm.state(['disabled']);message.configure(text='正在申请注销…')
            if not self.account.request_deletion(code.get(),requested):
                confirm.state(['!disabled']);message.configure(text='本机没有登录会话，请重新登录')
        send = SecondaryButton(actions,text='发送注销验证码',command=send_code);send.pack(side='left',padx=(SPACING['none'],SPACING['sm']))
        confirm = PrimaryButton(actions,text='确认注销',style='Tokens.Danger.TButton',command=submit);confirm.pack(side='left')
        confirm.state(['disabled'])              # 先发注销验证码，确认按钮才可用
        actions.pack(anchor='w',pady=SPACING['xs']);message.pack(anchor='w',pady=SPACING['xs'])
        self.account_delete_code_input,self.account_delete_send_button = code,send
        self.account_delete_button,self.account_delete_message = confirm,message

    def _account_redeem_form(self):
        """兑换码开通或续期会员；成功后服务端返回的新租约直接替换本机租约。"""
        form = Card(self.content);form.pack(fill='x',pady=SPACING['xs'])
        ttk.Label(form,text='输入兑换码（开通或续期会员；在原到期时间上顺延）').pack(anchor='w',pady=SPACING['xs'])
        code = LineInput(form,placeholder='XXXX-XXXX-XXXX-XXXX');code.pack(fill='x',pady=SPACING['xs'])
        message = ttk.Label(form,text='',style='Muted.TLabel',wraplength=TEXT_DESC['wraplength'],justify='left')
        message.pack(anchor='w',pady=SPACING['xs'])
        def redeemed(result):
            if not message.winfo_exists():return
            button.state(['!disabled'])
            if result.ok:
                days = (result.data or {}).get('added_days')
                self.show(PAGE_ACCOUNT);self.status.set('兑换成功'+('，会员增加 %s 天'%days if days else ''))
            else:message.configure(text=result.reason)
        def submit():
            value = code.get().strip()
            if not value or len(value) > REDEEM_MAX_LENGTH:
                code.set_error('请填写兑换码');return
            code.clear_error();button.state(['disabled']);message.configure(text='正在兑换…')
            if not self.account.redeem(value,redeemed):
                button.state(['!disabled']);message.configure(text='本机没有登录会话，请重新登录')
        button = PrimaryButton(form,text='兑换',command=submit);button.pack(anchor='w',pady=SPACING['xs'])
        self.account_redeem_input,self.account_redeem_button,self.account_redeem_message = code,button,message

    def _account_login_form(self):
        form = Card(self.content);form.pack(fill='x',pady=SPACING['xs'])
        ttk.Label(form,text='邮箱验证码登录（新账号免费试用 3 天，每个账号最多绑定 3 台电脑）').pack(anchor='w',pady=SPACING['xs'])
        email = LineInput(form,placeholder='邮箱地址');email.pack(fill='x',pady=SPACING['xs'])
        code = LineInput(form,placeholder='6 位验证码');code.pack(fill='x',pady=SPACING['xs'])
        adult = tk.BooleanVar(value=False)
        ttk.Checkbutton(form,text='已满 18 周岁并同意协议',variable=adult).pack(anchor='w',pady=SPACING['xs'])
        ttk.Label(form,text='首次注册必选：确认已年满 18 周岁，并同意用户协议与隐私政策。',
                  style='Muted.TLabel',wraplength=TEXT_DESC['wraplength'],justify='left').pack(anchor='w')
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
                self.show(PAGE_ACCOUNT);self.status.set('登录成功')
            else:
                pending = (result.data or {}).get('code') == 'account_pending_deletion'
                message.configure(text=result.reason+('。被拦下的验证码仍有效，可点「撤销注销」。' if pending else ''))
                if pending:cancel.pack(side='left',padx=(SPACING['sm'],SPACING['none']))
        def cancelled(result):
            if not alive():return
            cancel.state(['!disabled'])
            if not result.ok:message.configure(text=result.reason);return
            cancel.pack_forget();code.delete(0,'end')
            message.configure(text='已撤销注销，请重新发送验证码登录')
        def cancel_deletion():
            cancel.state(['disabled']);message.configure(text='正在撤销注销…')
            self.account.cancel_deletion(email.get(),code.get(),cancelled)
        def submit():
            if not code.get().strip():
                code.set_error('请填写验证码');return
            code.clear_error();login.state(['disabled']);message.configure(text='正在登录…')
            self.account.login(email.get(),code.get(),age_confirmed=adult.get(),done=logged_in)
        send = SecondaryButton(actions,text='发送验证码',command=send_code);send.pack(side='left',padx=(SPACING['none'],SPACING['sm']))
        login = PrimaryButton(actions,text='登录',command=submit);login.pack(side='left')
        login.state(['disabled'])                # 先发验证码，登录按钮才可用
        cancel = SecondaryButton(actions,text='撤销注销',command=cancel_deletion)   # 冷静期内登录被拦时才显示
        self.account_cancel_deletion_button = cancel
        self.account_email_input,self.account_code_input,self.account_login_button = email,code,login
        self.account_send_button,self.account_message = send,message
