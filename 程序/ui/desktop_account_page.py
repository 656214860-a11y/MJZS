"""「00 会员账户」页：密码登录／注册／验证码登录／找回密码、设置密码、授权状态、退出、兑换、设备解绑、注销与撤销、数据导出；低频账号功能在页面底部点开弹窗（L4，只放 Tk 控件与事件绑定）。

状态机、网络与落盘都在 L3 ``account_controller.AccountController``；本 Mixin 只注入
后台提交回调（``async_queued`` 经 ``BackgroundTaskLifecycle``）并把结果画到页面上。
首帧之后才后台续签，启动路径不等网络；自动续签与版本检查走 ``_account_background``，
不占独占后台、不写状态栏。
"""
import queue
import threading
import time
from types import SimpleNamespace
import webbrowser
import tkinter as tk
from tkinter import ttk

import domain.account_client as account_client
import domain.entitlement_service as entitlement_service
from orchestrator.account_controller import RENEW_VIEW_INTERVAL, AccountController
import contract.pet_bus as pet_bus
from ui.desktop_page_registry import (NAV_LOCK_ICON, PAGE_ACCOUNT, PAGE_NAV_ICONS, PAGES,
                                   nav_label, page_title)
from ui.ui_icons import IconLoader
from ui_tokens import DIALOG_CONTENT_PADDING, DIALOG_MIN_HEIGHT, FONTS, SPACING, TEXT_DESC
from account_inputs import EmailInput, PASSWORD_MASK, PasswordInput
from ui_widgets import BaseDialog, Card, LineInput, PrimaryButton, SecondaryButton, ask_confirmation

RENEW_DELAY_MS = 3000
RENEW_CHECK_MS = 30 * 60 * 1000


def _expiry_key(entitlement):
    payload = entitlement.payload or {}
    return (entitlement.state, payload.get('state'), payload.get('trial_ends_at'), payload.get('period_end'))
BACKGROUND_POLL_MS = 100
STATE_TEXT = {
    entitlement_service.VALID: '授权有效',
    entitlement_service.GRACE: '离线宽限期内，请尽快联网续签',
    entitlement_service.LOCKED: '授权已失效',
    entitlement_service.SIGNED_OUT: '未登录',
    entitlement_service.CLOCK_SUSPECT: '本机时间早于服务器时间',
}
PLAN_TEXT = {'trial': '免费试用', 'monthly': '月度会员', 'quarterly': '季度会员', 'yearly': '年度会员'}
REDEEM_MAX_LENGTH = 40
EXPORT_NAME = '漫剧助手账号数据_%Y%m%d.json'
LOGIN_VIEWS = {'pw': '邮箱密码登录（新账号免费试用 3 天，每个账号最多绑定 3 台电脑）', 'reg': '注册新账号（邮箱验证码＋密码）',
               'code': '邮箱验证码登录', 'reset': '找回密码（用邮箱验证码设置新密码）'}
CODE_SENT_TEXT = '验证码已发送，请查收邮件（10 分钟内有效）；几分钟没收到请看垃圾邮件箱，或稍后重发'
AGE_CONFIRM_TEXT = '已满 18 周岁并同意协议'


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


NAV_LOCK_MARK = ' 🔒'                         # 侧栏上未授权不能进的页


class AccountPageMixin:
    @property
    def account(self):
        controller = self.__dict__.get('_account_controller')
        if controller is None:
            controller = self._account_controller = AccountController(
                submit=self._account_submit, background=self._account_background)
        return controller

    def _account_submit(self, work, done, label):
        """用户点的账号动作：后台空闲走独占后台；别的任务正在跑就改走独立线程，不在队列里干等。"""
        if getattr(self, 'worker', None):
            self._account_background(work, done, label)
        else:
            self.async_queued(work, done, label=label, show_progress=False)

    def _account_background(self, work, done, label):
        """自动续签／版本检查：独立线程执行，结果回 Tk 主线程交付；不置 worker、不改状态栏。"""
        results = queue.Queue(maxsize=1)
        threading.Thread(target=lambda: results.put(work()), name=label, daemon=True).start()

        def deliver():
            if getattr(self, 'shutting_down', False):
                return
            try:
                result = results.get_nowait()
            except queue.Empty:
                schedule()
                return
            if done:
                done(result)

        def schedule():
            try:
                self.win.after(BACKGROUND_POLL_MS, deliver)
            except tk.TclError:
                pass
        schedule()

    def account_blocked(self, stage):
        """不经 ``stage_handler_registry.start()`` 的付费动作（如成片导出）在这里过闸门。

        拦截时把原因写进状态栏并返回 True；放行（含总开关关闭）返回 False。
        """
        reason = self.account.stage_gate(stage)
        if isinstance(reason, str) and reason:
            self.status.set(reason)
            return True
        return False

    def start_account_renewal(self):
        """首帧后由周期 tick 调用：到期才续签，失败静默，下一轮再试。"""
        if getattr(self, 'shutting_down', False):
            return
        try:
            self._account_changed()   # 跨天后刷新到期天数；会话已失效则回登录闸
            if self.account.renew_due():
                self.account.renew(done=self._account_renewed, quiet=True)
        finally:
            self.win.after(RENEW_CHECK_MS, self.start_account_renewal)

    def refresh_membership_view(self, event=None):
        """R2064：进账号页或窗口回到前台时静默续签一次（间隔不足一分钟则跳过），
        后台顺延、补偿天数不必等 12 小时的定时续签；只有到期信息变了才重画账号页。"""
        if getattr(self, 'shutting_down', False):
            return
        if event is not None and event.widget is not getattr(self, 'win', None):
            return
        account = getattr(self, 'account', None)
        if account is None or not account.renew_due(RENEW_VIEW_INTERVAL):
            return
        before = _expiry_key(account.entitlement())

        def done(result):
            self._account_changed()
            changed = _expiry_key(account.entitlement()) != before
            if result.ok and changed and getattr(self, 'page_index', None) == PAGE_ACCOUNT:
                self.show(PAGE_ACCOUNT)
        account.renew(done=done, quiet=True)

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

    def _account_changed(self):
        """登录、续签、兑换、退出、解绑、注销后：会话已清则回到登录闸。

        钩子由 ``LoginGateMixin`` 提供；没有混入它的宿主（如测试替身）直接跳过。
        """
        for name in ('recheck_login_gate', 'refresh_nav_locks'):
            hook = getattr(self, name, None)
            if callable(hook):
                hook()

    def page_lock_reasons(self):
        """页序号 → 锁定原因（只列被锁的页）。只在真实启动（要求登录）时设闸，测试宿主一律放行。"""
        if not getattr(self, '_require_login', False):
            return {}
        stages = pet_bus.STAGES
        return self.account.page_gate([(index, stages[index] if index < len(stages) else None, title.split(None, 1)[-1])
                                       for index, title in enumerate(PAGES)])

    def locked_page(self, reason):
        """未授权时换掉整页：说明原因，给一个去「00 会员账户」的按钮。"""
        card = Card(self.content);card.pack(fill='x',pady=SPACING['xs'])
        ttk.Label(card,text='需要登录或授权',font=FONTS['heading_2']).pack(anchor='w')
        ttk.Label(card,text=reason,wraplength=TEXT_DESC['wraplength'],justify='left').pack(anchor='w',pady=SPACING['xs'])
        PrimaryButton(card,text='去会员账户',command=lambda:self.go_page(PAGE_ACCOUNT)).pack(anchor='w',pady=SPACING['xs'])
        self.status.set(reason)

    def refresh_nav_locks(self):
        """授权变化后给侧栏被锁的页换锁图标／换回原图标（R2933：图标轨不再有文字锁标）；
        PNG 缺失的兜底文字态才保留 🔒 字样。当前页的锁定状态翻转就重建这一页。"""
        reasons = self.page_lock_reasons()
        current, flipped = getattr(self, 'page_index', None), False
        for index, button in enumerate(getattr(self, 'nav', ())):
            locked = index in reasons
            if getattr(button, '_nav_locked', False) == locked:
                continue
            button._nav_locked = locked
            base = getattr(button, '_nav_icon_name', None) or PAGE_NAV_ICONS.get(index)
            image = IconLoader.nav_icon(button, NAV_LOCK_ICON if locked else base)
            compound = 'image' if image is not None else 'text'
            text = nav_label(index) + (NAV_LOCK_MARK if locked and image is None else '')
            button.configure(image=image, compound=compound, text=text)
            tip = getattr(button, '_nav_tooltip', None)
            if tip is not None:
                tip.text = page_title(index) + ('（需要登录或授权）' if locked else '')
            flipped = flipped or index == current
        if flipped and not getattr(self, 'login_gate_active', False):
            self.show(current)

    def _account_renewed(self, result):
        self._account_changed()
        if not result.ok and (result.data or {}).get('code') == 'client_too_old':
            self.account.check_update(self._update_checked)
        if getattr(self, 'page_index', None) == PAGE_ACCOUNT:
            self.show(PAGE_ACCOUNT)
        if not result.ok and (result.data or {}).get('code') != 'network':
            self.status.set('会员授权续签未成功：' + result.reason)

    def account_page(self):
        """未登录时显示登录／注册表单；已登录时显示授权状态、到期时间与退出。"""
        entitlement = self.account.entitlement()
        session = self.account.session()
        self._account_update_card()
        status = Card(self.content);status.pack(fill='x',pady=SPACING['xs'])
        head = ttk.Frame(status);head.pack(fill='x')
        ttk.Label(head,text='当前状态：'+STATE_TEXT.get(entitlement.state,entitlement.state),font=FONTS['heading_2']).pack(side='left')
        view = entitlement_service.membership_view(entitlement, self.account.now())
        style = {'warn': 'Warn.TLabel', 'expired': 'Expired.TLabel'}.get(view['level'], 'Muted.TLabel')
        lines = list(view['lines'])
        if not self.account.enforce:lines.append('测试期暂不拦截。')
        for line in lines:
            ttk.Label(status,text=line,style=style,wraplength=TEXT_DESC['wraplength'],justify='left').pack(anchor='w',pady=(SPACING['xs'],SPACING['none']))
        if session.get('refresh_token') or entitlement.payload:
            self._account_signed_in(status, head, entitlement, session)
        else:
            self._account_login_form()

    def _account_signed_in(self, card, head, entitlement, session):
        payload = entitlement.payload or {}
        parts = ['账号：'+str(session.get('email') or '—'),
                 '套餐：'+plan_text(payload)]
        if payload.get('state') == 'trial':parts.append('试用到期：'+_when(payload.get('trial_ends_at')))
        if payload.get('state') == 'active':parts.append('会员到期：'+_when(payload.get('period_end')))
        info = ttk.Frame(card);info.pack(fill='x',pady=(SPACING['xs'],SPACING['none']))
        for part in parts:ttk.Label(info,text=part).pack(side='left',padx=(SPACING['none'],SPACING['lg']))
        actions = ttk.Frame(head);actions.pack(side='right')
        def renew():
            if not self.account.renew(done=self._account_renewed):self.status.set('本机没有可续签的登录会话，请重新登录')
            else:self.status.set('正在续签会员授权…')
        def logout():
            self.account.logout();self.show(PAGE_ACCOUNT);self.status.set('已退出登录（项目和素材不受影响）');self._account_changed()
        SecondaryButton(actions,text='退出登录',command=logout).pack(side='right')
        PrimaryButton(actions,text='立即续签',command=renew).pack(side='right',padx=(SPACING['none'],SPACING['sm']))
        self._account_redeem_form()
        self._account_tools_card(session)

    def _account_tools_card(self, session):
        """页面底部的低频账号功能：每项一个按钮，点开弹窗操作。

        以后新增的低频账号功能也优先加到这里做成弹窗，不在页面上新开卡片。
        """
        password_title = '修改登录密码' if session.get('has_password') else '设置登录密码'
        tools = (('password', password_title, lambda dialog: self._account_password_form(session, dialog)),
                 ('devices', '已绑定设备', self._account_devices_form),
                 ('export', '导出账号数据', self._account_export_form),
                 ('delete', '注销账号', self._account_delete_form))
        card = Card(self.content);card.pack(fill='x',pady=SPACING['xs'])
        row = ttk.Frame(card);row.pack(fill='x')
        ttk.Label(row,text='账号管理').pack(side='left')
        self.account_tool_buttons = {}
        for key, title, build in reversed(tools):
            button = SecondaryButton(row,text=title,command=lambda t=title,b=build:self._account_open_dialog(t,b))
            button.pack(side='right',padx=(SPACING['sm'],SPACING['none']))
            self.account_tool_buttons[key] = button

    def _account_open_dialog(self, title, build):
        """同一时间只开一个账号弹窗；``build(dialog)`` 把控件画进 ``dialog.content``。"""
        self._account_close_dialog()
        dialog = BaseDialog(self.win, title, minsize=(TEXT_DESC['wraplength'] + 2*DIALOG_CONTENT_PADDING, DIALOG_MIN_HEIGHT),
                            on_close=lambda: setattr(self, 'account_dialog', None))
        self.account_dialog = dialog
        dialog.add_action('关闭', dialog.close)
        build(dialog)
        return dialog

    def _account_close_dialog(self):
        dialog = getattr(self, 'account_dialog', None)
        if dialog is not None:
            dialog.close()

    def _account_confirm(self, title, message):
        dialog = getattr(self, 'account_dialog', None)
        confirmed = ask_confirmation(dialog or self.win, title, message, dangerous=True)
        if dialog is not None and dialog.winfo_exists():
            dialog.grab_set()   # 确认窗关闭时会释放输入锁，收回给账号弹窗
        return confirmed

    def _account_export_path(self):
        return self.file_dialog.save_file(title='导出账号数据', defaultextension='.json',
                                          initialfile=time.strftime(EXPORT_NAME), filetypes=[('JSON','*.json')])

    def _account_devices_form(self, dialog):
        """已绑定设备：打开弹窗时才联网读取（不在每次画页时请求），可解绑；解绑本机即退出登录。"""
        head = ttk.Frame(dialog.content);head.pack(fill='x')
        rows = ttk.Frame(dialog.content);rows.pack(fill='x')
        message = ttk.Label(head,text='',style='Muted.TLabel')
        def listed(result):
            if not message.winfo_exists():return
            button.state(['!disabled'])
            if result.ok:self._account_device_rows(rows,message,result.data or {},load)
            else:message.configure(text=result.reason)
        def load():
            button.state(['disabled']);message.configure(text='正在读取设备列表…')
            if not self.account.devices(listed):
                button.state(['!disabled']);message.configure(text='本机没有登录会话，请重新登录')
        button = SecondaryButton(head,text='刷新',command=load);button.pack(side='right')
        message.pack(side='left')
        self.account_devices_button,self.account_devices_rows,self.account_devices_message = button,rows,message
        load()

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
            if current:
                self._account_close_dialog();self.show(PAGE_ACCOUNT);self.status.set('已解绑本机并退出登录');self._account_changed();return
            self.status.set('已解绑设备');reload()
        message.configure(text='正在解绑…')
        if not self.account.unbind(device.get('id'),unbound,current=current):message.configure(text='本机没有登录会话，请重新登录')

    def _account_export_form(self, dialog):
        """导出账号数据（账号、同意记录、设备、会员与兑换记录）到用户选定的 JSON 文件。"""
        ttk.Label(dialog.content,text='导出账号、设备、会员与兑换记录（不含项目和素材）。').pack(anchor='w')
        message = ttk.Label(dialog.content,text='',style='Muted.TLabel',wraplength=TEXT_DESC['wraplength'],justify='left')
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
        button = dialog.add_action('导出',export,primary=True)
        message.pack(anchor='w',pady=SPACING['xs'])
        self.account_export_button,self.account_export_message = button,message

    def _account_delete_form(self, dialog):
        """注销：先发注销用途验证码，凭码进入 7 天冷静期；成功后本机退出登录。"""
        ttk.Label(dialog.content,text='注销后进入 7 天冷静期，期间可在登录页用登录验证码撤销；到期后删除账号数据。本机项目和素材不受影响。',
                  wraplength=TEXT_DESC['wraplength'],justify='left').pack(anchor='w',pady=SPACING['xs'])
        row = ttk.Frame(dialog.content);row.pack(fill='x',pady=(SPACING['xs'],SPACING['none']))
        code = LineInput(row,placeholder='6 位注销验证码')
        message = ttk.Label(dialog.content,text='',style='Muted.TLabel',wraplength=TEXT_DESC['wraplength'],justify='left')
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
            self._account_close_dialog();self.show(PAGE_ACCOUNT)
            self.status.set('已申请注销，冷静期至 %s；期间可在登录页撤销'%_when((result.data or {}).get('deletion_at')));self._account_changed()
        def submit():
            if not code.get().strip():
                code.set_error('请填写注销验证码');return
            code.clear_error()
            if not self._account_confirm('注销账号','确定注销？7 天冷静期内可以撤销，到期后账号数据会被删除。'):return
            confirm.state(['disabled']);message.configure(text='正在申请注销…')
            if not self.account.request_deletion(code.get(),requested):
                confirm.state(['!disabled']);message.configure(text='本机没有登录会话，请重新登录')
        send = SecondaryButton(row,text='发送注销验证码',command=send_code);send.pack(side='right',padx=(SPACING['sm'],SPACING['none']))
        confirm = dialog.add_action('确认注销',submit,dangerous=True)
        confirm.state(['disabled'])              # 先发注销验证码，确认按钮才可用
        code.pack(side='left',fill='x',expand=True)
        message.pack(anchor='w',pady=SPACING['xs'])
        self.account_delete_code_input,self.account_delete_send_button = code,send
        self.account_delete_button,self.account_delete_message = confirm,message

    def _account_password_form(self, session, dialog):
        """设置或修改登录密码：已有密码须填原密码；成功后其他电脑的登录失效，本机保留。"""
        has_password = bool(session.get('has_password'))
        card = dialog.content
        if not has_password:ttk.Label(card,text='设置后可用邮箱＋密码登录。').pack(anchor='w',pady=SPACING['xs'])
        old = PasswordInput(card,placeholder='原密码') if has_password else None
        if old is not None:old.pack(fill='x',pady=SPACING['xs'])
        new = PasswordInput(card,placeholder='新密码（8–64 位，含字母和数字）');new.pack(fill='x',pady=SPACING['xs'])
        again = PasswordInput(card,placeholder='再次输入新密码');again.pack(fill='x',pady=SPACING['xs'])
        message = ttk.Label(card,text='',style='Muted.TLabel',wraplength=TEXT_DESC['wraplength'],justify='left')
        def say(text, error=False):message.configure(text=text,style='Expired.TLabel' if error else 'Muted.TLabel')
        def invalid(field, text):field.set_error(text);say(text,True)
        def saved(result):
            if not message.winfo_exists():return
            button.state(['!disabled'])
            if not result.ok:say(result.reason,True);return
            self._account_close_dialog();self.show(PAGE_ACCOUNT);self.status.set('密码已保存；其他电脑上的登录需要重新登录')
        def submit():
            if old is not None and not old.get():invalid(old,'请填写原密码');return
            problem = account_client.password_problem(new.get())
            if problem:invalid(new,problem);return
            new.clear_error()
            if again.get() != new.get():invalid(again,'两次输入的密码不一致');return
            again.clear_error();button.state(['disabled']);say('正在保存密码…')
            if not self.account.change_password(new.get(),saved,old_password=old.get() if old is not None else None):
                button.state(['!disabled']);say('本机没有登录会话，请重新登录',True)
        button = dialog.add_action('保存密码',submit,primary=True)
        message.pack(anchor='w',pady=SPACING['xs'])
        self.account_password_old_input,self.account_password_new_input = old,new
        self.account_password_again_input,self.account_password_button,self.account_password_message = again,button,message

    def _account_redeem_form(self):
        """兑换码开通或续期会员；成功后服务端返回的新租约直接替换本机租约。"""
        form = Card(self.content);form.pack(fill='x',pady=SPACING['xs'])
        head = ttk.Frame(form);head.pack(fill='x')
        ttk.Label(head,text='兑换码（开通或续期会员，到期时间顺延）').pack(side='left')
        message = ttk.Label(head,text='',style='Muted.TLabel')
        message.pack(side='right')
        row = ttk.Frame(form);row.pack(fill='x',pady=(SPACING['xs'],SPACING['none']))
        code = LineInput(row,placeholder='XXXX-XXXX-XXXX-XXXX')
        def redeemed(result):
            if not message.winfo_exists():return
            button.state(['!disabled'])
            if result.ok:
                days = (result.data or {}).get('added_days')
                self.show(PAGE_ACCOUNT);self.status.set('兑换成功'+('，会员增加 %s 天'%days if days else ''));self._account_changed()
            else:message.configure(text=result.reason)
        def submit():
            value = code.get().strip()
            if not value or len(value) > REDEEM_MAX_LENGTH:
                code.set_error('请填写兑换码');return
            code.clear_error();button.state(['disabled']);message.configure(text='正在兑换…')
            if not self.account.redeem(value,redeemed):
                button.state(['!disabled']);message.configure(text='本机没有登录会话，请重新登录')
        button = PrimaryButton(row,text='兑换',command=submit)
        button.pack(side='right',padx=(SPACING['sm'],SPACING['none']))
        code.pack(side='left',fill='x',expand=True)
        self.account_redeem_input,self.account_redeem_button,self.account_redeem_message = code,button,message

    def _account_login_form(self):
        self._build_login_form(self.content, lambda: (self.show(PAGE_ACCOUNT), self.status.set('登录成功'), self._account_changed()))

    def _build_login_form(self, parent, on_success, *, wrap=None):
        """账号页与启动登录闸共用：密码登录（默认）／注册／验证码登录／找回密码四个视图共用一个邮箱框。

        发请求前先在本机查邮箱格式、密码强度与两次输入是否一致，错误标在对应输入框并用错误色提示；
        登录或注册成功后只调 ``on_success``。
        """
        wrap = wrap or TEXT_DESC['wraplength']
        form = Card(parent);form.pack(fill='x',pady=SPACING['xs'])
        tabs = ttk.Frame(form);tabs.pack(anchor='w',pady=SPACING['xs'])
        title = ttk.Label(form,text='',font=FONTS['heading_2'],wraplength=wrap,justify='left');title.pack(anchor='w',pady=SPACING['xs'])
        email = EmailInput(form);email.pack(fill='x',pady=SPACING['xs'])
        remembered = self.account.last_email()
        if remembered:email.insert(0,remembered)        # R2052：默认显示上一次登录的邮箱，无需再输
        body = ttk.Frame(form);body.pack(fill='x')
        message = ttk.Label(form,text='',style='Muted.TLabel',wraplength=wrap,justify='left');message.pack(anchor='w',pady=SPACING['xs'])
        views = {key:ttk.Frame(body) for key in LOGIN_VIEWS}
        current = {'view':'pw'}
        def alive():return bool(message.winfo_exists())
        def say(text, error=False):message.configure(text=text,style='Expired.TLabel' if error else 'Muted.TLabel')
        def show_view(key, text='', error=False):
            for frame in views.values():frame.pack_forget()
            views[key].pack(fill='x');title.configure(text=LOGIN_VIEWS[key]);current['view'] = key
            login_tab.state(['disabled'] if key == 'pw' else ['!disabled'])
            register_tab.state(['disabled'] if key == 'reg' else ['!disabled'])
            say(text,error)
        def invalid(field, text):
            field.set_error(text);say(text,True)
        def checked_email():
            value = email.get().strip()
            if not value:invalid(email,'请填写邮箱');return None
            if not account_client.valid_email(value):
                invalid(email,'邮箱格式不正确，请检查是否漏了「.」或「@」（例如 name@qq.com）');return None
            email.clear_error();return value
        def checked_password(field, again):
            problem = account_client.password_problem(field.get())
            if problem:invalid(field,problem);return False
            field.clear_error()
            if again.get() != field.get():invalid(again,'两次输入的密码不一致');return False
            again.clear_error();return True
        def required(field, text):
            if field.get().strip():field.clear_error();return True
            invalid(field,text);return False
        def fail(result):
            data = result.data or {}
            if data.get('code') == 'http_404':
                show_view('code','账号服务暂不支持密码登录，请先用验证码登录',True);return
            if data.get('code') == 'account_pending_deletion':
                show_view('code',result.reason+'。请发送验证码后点「撤销注销」。',True)
                cancel.pack(side='left',padx=(SPACING['sm'],SPACING['none']));return
            wait = data.get('retry_after')
            say(result.reason+('（%s 秒后可重试）'%wait if wait else ''),True)
        def send(purpose, button, after=None):
            value = checked_email()
            if not value:return
            def sent(result):
                if not alive():return
                button.state(['!disabled'])
                if result.ok:
                    if after:after()
                    say(CODE_SENT_TEXT)
                elif (result.data or {}).get('code') == 'email_registered':
                    show_view('pw',result.reason+'。忘了密码或没设过密码，可点「忘记密码」。')
                else:fail(result)
            button.state(['disabled']);say('正在发送验证码…')
            self.account.request_code(value,sent,purpose=purpose)
        def signed_in():
            # R2046：只认本机会话验签后的状态；仍是未登录就留在表单上，不报「登录成功」。
            if self.account.entitlement().state != entitlement_service.SIGNED_OUT:on_success()
            else:say('登录没有在本机生效，请重新登录；多次失败请检查本机时间或联系客服',True)
        def finished(button, success=None):
            def done(result):
                if not alive():return
                button.state(['!disabled'])
                if not result.ok:fail(result)
                elif success:success()
                else:signed_in()
            return done
        def row(view):
            frame = ttk.Frame(views[view]);frame.pack(anchor='w',pady=SPACING['xs']);return frame
        # 密码登录
        password = PasswordInput(views['pw'],placeholder='密码');password.pack(fill='x',pady=SPACING['xs'])
        def password_login():
            value = checked_email()
            if not value or not required(password,'请填写密码'):return
            pw_login.state(['disabled']);say('正在登录…')
            self.account.password_login(value,password.get(),finished(pw_login))
        password.bind('<Return>',lambda _event:password_login())
        actions = row('pw')
        pw_login = PrimaryButton(actions,text='登录',command=password_login);pw_login.pack(side='left',padx=(SPACING['none'],SPACING['sm']))
        forgot = SecondaryButton(actions,text='忘记密码',command=lambda:show_view('reset'));forgot.pack(side='left',padx=(SPACING['none'],SPACING['sm']))
        # 点「用验证码登录」直接发验证码：邮箱不合法就留在密码页报错，发出后才切到验证码视图并放开登录键
        use_code = SecondaryButton(actions,text='用验证码登录',
                                   command=lambda:send('login',use_code,after=lambda:(show_view('code'),login.state(['!disabled']))))
        use_code.pack(side='left')
        # 注册
        reg_send = SecondaryButton(row('reg'),text='发送注册验证码',command=lambda:send('register',reg_send));reg_send.pack(side='left')
        reg_code = LineInput(views['reg'],placeholder='6 位验证码');reg_code.pack(fill='x',pady=SPACING['xs'])
        reg_password = PasswordInput(views['reg'],placeholder='设置密码（8–64 位，含字母和数字）');reg_password.pack(fill='x',pady=SPACING['xs'])
        reg_again = PasswordInput(views['reg'],placeholder='再次输入密码');reg_again.pack(fill='x',pady=SPACING['xs'])
        reg_adult = tk.BooleanVar(master=form,value=False)
        ttk.Checkbutton(views['reg'],text=AGE_CONFIRM_TEXT,variable=reg_adult).pack(anchor='w',pady=SPACING['xs'])
        def register():
            value = checked_email()
            if not value or not required(reg_code,'请填写验证码') or not checked_password(reg_password,reg_again):return
            if not reg_adult.get():say('请先勾选「已满 18 周岁，并同意用户协议与隐私政策」',True);return
            reg_button.state(['disabled']);say('正在注册…')
            self.account.register(value,reg_code.get(),reg_password.get(),age_confirmed=True,done=finished(reg_button))
        reg_button = PrimaryButton(row('reg'),text='注册并登录',command=register);reg_button.pack(side='left')
        kit = SimpleNamespace(view=views['code'],form=form,wrap=wrap,alive=alive,say=say,fail=fail,send=send,
                              checked_email=checked_email,required=required,row=row,show_view=show_view,on_success=signed_in)
        code,login,code_send,cancel = _login_code_view(self.account,kit)
        # 找回密码
        reset_send = SecondaryButton(row('reset'),text='发送重置验证码',command=lambda:send('reset',reset_send));reset_send.pack(side='left')
        reset_code = LineInput(views['reset'],placeholder='6 位验证码');reset_code.pack(fill='x',pady=SPACING['xs'])
        reset_password = PasswordInput(views['reset'],placeholder='新密码（8–64 位，含字母和数字）');reset_password.pack(fill='x',pady=SPACING['xs'])
        reset_again = PasswordInput(views['reset'],placeholder='再次输入新密码');reset_again.pack(fill='x',pady=SPACING['xs'])
        def reset_done():
            password.delete(0,'end');show_view('pw','密码已重置，请用新密码登录')
        def reset():
            value = checked_email()
            if not value or not required(reset_code,'请填写验证码') or not checked_password(reset_password,reset_again):return
            reset_button.state(['disabled']);say('正在重置密码…')
            self.account.reset_password(value,reset_code.get(),reset_password.get(),finished(reset_button,reset_done))
        reset_actions = row('reset')
        reset_button = PrimaryButton(reset_actions,text='重置密码',command=reset);reset_button.pack(side='left',padx=(SPACING['none'],SPACING['sm']))
        SecondaryButton(reset_actions,text='返回密码登录',command=lambda:show_view('pw')).pack(side='left')
        login_tab = SecondaryButton(tabs,text='登录',command=lambda:show_view('pw'));login_tab.pack(side='left',padx=(SPACING['none'],SPACING['sm']))
        register_tab = SecondaryButton(tabs,text='注册',command=lambda:show_view('reg'));register_tab.pack(side='left')
        show_view('pw')
        self.account_login_view,self.account_show_login_view = current,show_view
        self.account_email_input,self.account_message = email,message
        self.account_login_tab,self.account_register_tab = login_tab,register_tab
        self.account_password_input,self.account_password_login_button = password,pw_login
        self.account_forgot_button,self.account_use_code_button = forgot,use_code
        self.account_register_send_button,self.account_register_code_input = reg_send,reg_code
        self.account_register_password_input,self.account_register_password2_input = reg_password,reg_again
        self.account_register_adult,self.account_register_button = reg_adult,reg_button
        self.account_code_input,self.account_login_button,self.account_send_button = code,login,code_send
        self.account_cancel_deletion_button = cancel
        self.account_reset_send_button,self.account_reset_code_input = reset_send,reset_code
        self.account_reset_password_input,self.account_reset_password2_input = reset_password,reset_again
        self.account_reset_button = reset_button


def _login_code_view(account, kit):
    """验证码登录视图（没设过密码的旧账号也能进；邮箱未注册时服务端顺带建号），返回 (验证码框, 登录, 发码, 撤销注销)。"""
    code = LineInput(kit.view,placeholder='6 位验证码');code.pack(fill='x',pady=SPACING['xs'])
    adult = tk.BooleanVar(master=kit.form,value=False)
    ttk.Checkbutton(kit.view,text=AGE_CONFIRM_TEXT,variable=adult).pack(anchor='w',pady=SPACING['xs'])
    ttk.Label(kit.view,text='邮箱未注册时会顺带建号，须勾选：确认已年满 18 周岁，并同意用户协议与隐私政策。',
              style='Muted.TLabel',wraplength=kit.wrap,justify='left').pack(anchor='w')
    actions = kit.row('code')
    def logged_in(result):
        if not kit.alive():return
        login.state(['!disabled'])
        if result.ok:
            kit.on_success()
        elif (result.data or {}).get('code') == 'account_pending_deletion':
            kit.say(result.reason+'。被拦下的验证码仍有效，可点「撤销注销」。',True)
            cancel.pack(side='left',padx=(SPACING['sm'],SPACING['none']))
        else:kit.fail(result)
    def cancelled(result):
        if not kit.alive():return
        cancel.state(['!disabled'])
        if not result.ok:kit.fail(result);return
        cancel.pack_forget();code.delete(0,'end')
        kit.say('已撤销注销，请重新发送验证码登录')
    def cancel_deletion():
        value = kit.checked_email()
        if not value or not kit.required(code,'请填写验证码'):return
        cancel.state(['disabled']);kit.say('正在撤销注销…')
        account.cancel_deletion(value,code.get(),cancelled)
    def code_login():
        value = kit.checked_email()
        if not value or not kit.required(code,'请填写验证码'):return
        login.state(['disabled']);kit.say('正在登录…')
        account.login(value,code.get(),age_confirmed=adult.get(),done=logged_in)
    code_send = SecondaryButton(actions,text='发送验证码',
                                command=lambda:kit.send('login',code_send,after=lambda:login.state(['!disabled'])))
    code_send.pack(side='left',padx=(SPACING['none'],SPACING['sm']))
    login = PrimaryButton(actions,text='登录',command=code_login);login.pack(side='left')
    login.state(['disabled'])                # 先发验证码，登录按钮才可用
    cancel = SecondaryButton(actions,text='撤销注销',command=cancel_deletion)   # 冷静期内登录被拦时才显示
    SecondaryButton(kit.row('code'),text='返回密码登录',command=lambda:kit.show_view('pw')).pack(side='left')
    return code,login,code_send,cancel
