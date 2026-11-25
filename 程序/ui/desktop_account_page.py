"""「00 会员账户」页：密码登录／注册／验证码登录／找回密码、设置密码、授权状态、退出、兑换、设备解绑、注销与撤销、数据导出；低频账号功能在页面底部点开弹窗（L4，只放 Tk 控件与事件绑定）。

状态机、网络与落盘都在 L3 ``account_controller.AccountController``；本 Mixin 只注入
后台提交回调（``async_queued`` 经 ``BackgroundTaskLifecycle``）并把结果画到页面上。
首帧之后才后台续签，启动路径不等网络；自动续签与版本检查走 ``_account_background``，
不占独占后台、不写状态栏。
"""
import errno
import queue
import threading
import time
from pathlib import Path
from types import SimpleNamespace
import webbrowser
import tkinter as tk
from tkinter import ttk

import domain.account_client as account_client
import domain.entitlement_service as entitlement_service
from orchestrator.account_controller import RENEW_VIEW_INTERVAL, AccountController
import contract.pet_bus as pet_bus
from contract.app_metadata import VERSION
from infra.file_cache import read_json
from ui.desktop_page_registry import (NAV_LOCK_ICON, PAGE_ACCOUNT, PAGE_NAV_ICONS, PAGES,
                                   nav_label, page_title)
from ui.ui_icons import IconLoader
from ui_tokens import (DESKTOP_LAYOUT, DIALOG_CONTENT_PADDING, DIALOG_MIN_HEIGHT,
                       FONTS, SPACING, TEXT_DESC, TEXT_ROWS)
from account_inputs import EmailInput, PASSWORD_MASK, PasswordInput
from ui_widgets import (BaseDialog, Card, LineInput, PrimaryButton, SecondaryButton, TextArea,
                        ask_confirmation)

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
LOGIN_VIEWS = {'pw': '欢迎登录', 'reg': '创建新账号', 'code': '验证码登录', 'reset': '找回密码'}
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


NOTICES_NAME = 'THIRD_PARTY_NOTICES.txt'
DIGEST_NAME = '分发清单.json'
APP_ROOT = Path(__file__).resolve().parents[2]


def about_info(root=None):
    """「关于与开源许可」只读数据：版本、构建提交、随包开源许可全文（无 Tk 依赖）。"""
    root = Path(root) if root is not None else APP_ROOT
    info = {'version': str(VERSION), 'commit': '',
            'notices_path': str(root / NOTICES_NAME), 'notices_text': ''}
    try:
        data = read_json(root / DIGEST_NAME)
        if isinstance(data, dict):
            info['commit'] = str(data.get('commit') or '')
    except (OSError, ValueError):
        pass
    try:
        info['notices_text'] = Path(info['notices_path']).read_text(encoding='utf-8')
    except OSError:
        pass
    return info


def about_lines(info):
    """关于页展示行：版本、构建与开源许可入口说明。"""
    lines = ['版本：' + (info.get('version') or '未知'),
             '构建：' + (info.get('commit') or '开发副本')]
    if info.get('notices_text'):
        lines.append('开源许可：随包 THIRD_PARTY_NOTICES.txt，点下方按钮查看')
    else:
        lines.append('开源许可：本副本未携带 THIRD_PARTY_NOTICES.txt（未打包的开发副本）')
    return lines


def about_card(parent, info):
    """「关于与开源许可」块：版本、构建提交，以及随包 THIRD_PARTY_NOTICES.txt 的页内展开入口。"""
    card = Card(parent);card.pack(fill='x',pady=SPACING['xs'])
    ttk.Label(card,text='关于与开源许可').pack(anchor='w')
    for line in about_lines(info):
        ttk.Label(card,text=line,style='Muted.TLabel',wraplength=TEXT_DESC['wraplength'],justify='left').pack(anchor='w',pady=(SPACING['xs'],SPACING['none']))
    if not info['notices_text']:
        return card
    body = ttk.Frame(card)
    area = TextArea(body,height=TEXT_ROWS['xl'],wrap='word')
    scroll = ttk.Scrollbar(body,orient='vertical',command=area.yview)
    area.configure(yscrollcommand=scroll.set)
    area.insert('1.0',info['notices_text']);area.set_readonly()
    scroll.pack(side='right',fill='y');area.pack(side='left',fill='x',expand=True)
    def show():
        body.pack(fill='x',pady=SPACING['xs']);button.pack_forget()
    button = SecondaryButton(card,text='查看开源许可',command=show);button.pack(anchor='w',pady=SPACING['xs'])
    return card


HELP_GUIDE_NAME = '环境类错误指引'
HELP_DOCS = (('使用说明', '程序/docs/process/制作失败与人工替代.md'),
             (HELP_GUIDE_NAME, '程序/docs/guides/用户手册/环境类错误指引.md'),
             ('已知问题', '程序/docs/guides/用户手册/已知问题.md'))
ENV_HELP_PAGES = {
    'E-TOOL-MISSING': 'FFmpeg 缺失',
    'E-IO-WRITE': '磁盘满',
    'E-AUTH-MISSING': '模型 Key 无效', 'E-AUTH-REJECTED': '模型 Key 无效',
    'E-QUOTA-EXCEEDED': '模型 Key 无效',
    'E-NET-UNREACHABLE': '网络不可达', 'E-NET-TIMEOUT': '网络不可达', 'E-NET-SERVER': '网络不可达',
    'network': '账号服务不可达', 'service_timeout': '账号服务不可达', 'cert_error': '账号服务不可达',
}


def help_topics(root=None):
    """「帮助」入口列出的用户文档：[(页名, 绝对路径)]；root 供测试注入临时目录。"""
    base = Path(root) if root is not None else APP_ROOT
    return [(title, str(base / rel)) for title, rel in HELP_DOCS]


def help_doc_text(path):
    """读用户文档全文（UTF-8）；文件缺失或读不到时返回空串。"""
    try:
        return Path(path).read_text(encoding='utf-8')
    except OSError:
        return ''


def with_help_hint(text, error):
    """环境类错误提示末尾补「查看帮助：环境类错误指引 · <页名>」；认不出的原样返回。

    ``error`` 接受带 ``code`` 属性的异常、含 ``code`` 的结果字典（账号服务用
    ``network``／``service_timeout``／``cert_error``），以及 ``errno`` 为 ``ENOSPC`` 的 ``OSError``。
    """
    code = getattr(error, 'code', None)
    if code is None and isinstance(error, dict):
        code = error.get('code')
    if code is None and getattr(error, 'errno', None) == errno.ENOSPC:
        code = 'E-IO-WRITE'
    page = ENV_HELP_PAGES.get(str(code or ''))
    return text + '；查看帮助：' + HELP_GUIDE_NAME + ' · ' + page if page else text


def help_card(parent, topics=None):
    """「帮助」块：使用说明／环境类错误指引／已知问题三个页内展开入口；缺文档给一句话说明。"""
    topics = help_topics() if topics is None else topics
    card = Card(parent);card.pack(fill='x',pady=SPACING['xs'])
    ttk.Label(card,text='帮助').pack(anchor='w')
    ttk.Label(card,text='使用说明、环境类错误指引与已知问题清单，点按钮在页内展开。',
              style='Muted.TLabel',wraplength=TEXT_DESC['wraplength'],justify='left').pack(anchor='w',pady=(SPACING['xs'],SPACING['none']))
    row = ttk.Frame(card);row.pack(fill='x',pady=SPACING['xs'])
    body = ttk.Frame(card)
    area = TextArea(body,height=TEXT_ROWS['xl'],wrap='word')
    scroll = ttk.Scrollbar(body,orient='vertical',command=area.yview)
    area.configure(yscrollcommand=scroll.set)
    scroll.pack(side='right',fill='y');area.pack(side='left',fill='x',expand=True)
    shown = {'title': None}
    def show(title, path):
        if shown['title'] == title:
            body.pack_forget();shown['title'] = None;return
        text = help_doc_text(path) or '这份文档还没有随本副本提供，请升级到最新版本。'
        area.set_readonly(False);area.delete('1.0','end');area.insert('1.0',text);area.set_readonly()
        body.pack(fill='x',pady=SPACING['xs']);shown['title'] = title
    for title, path in topics:
        SecondaryButton(row,text='查看'+title,
                        command=lambda t=title,p=path:show(t,p)).pack(side='left',padx=(SPACING['none'],SPACING['sm']))
    return card


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
        """新版提示：账号页常驻显示；软提示每个版本只在状态栏主动提一次，强制升级每次都提。

        软提示的「已见」必须在状态栏展示成功之后再记，避免展示前崩溃永久丢失该版本提示。
        """
        if not result.ok or getattr(self, 'shutting_down', False):
            return
        notice = result.data or {}
        self.update_notice = notice
        if notice.get('level') == 'none':
            return
        if notice.get('proactive'):
            self.status.set(notice.get('text') or '有新版本')
            if notice.get('level') == 'soft':
                self.account.mark_update_seen(notice.get('version'))
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

    def _account_cert_warning_card(self):
        """钉死证书临期/过期提醒：pinned_cert_warning() 返回空串或空白时不建控件、不占位。"""
        warning = account_client.pinned_cert_warning()
        if not warning or not warning.strip():
            return
        card = Card(self.content);card.pack(fill='x',pady=SPACING['xs'])
        ttk.Label(card,text='证书到期提醒',style='Warn.TLabel').pack(anchor='w')
        ttk.Label(card,text=warning,style='Warn.TLabel',wraplength=TEXT_DESC['wraplength'],justify='left').pack(anchor='w',pady=SPACING['xs'])

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
        self._account_cert_warning_card()
        status = Card(self.content);status.pack(fill='x',pady=SPACING['xs'])
        head = ttk.Frame(status);head.pack(fill='x')
        ttk.Label(head,text='当前状态：'+STATE_TEXT.get(entitlement.state,entitlement.state),font=FONTS['heading_2']).pack(side='left')
        view = entitlement_service.membership_view(entitlement, self.account.now())
        style = {'warn': 'Warn.TLabel', 'expired': 'Expired.TLabel'}.get(view['level'], 'Muted.TLabel')
        lines = list(view['lines'])
        if self.account.clock_backup_available() is False:
            notice = '注册表时钟基线不可用，会员授权暂使用本机会话基线。'
            lines.append(notice)
            self.status.set(notice)
        if not self.account.enforce:lines.append('测试期暂不拦截。')
        for line in lines:
            ttk.Label(status,text=line,style=style,wraplength=TEXT_DESC['wraplength'],justify='left').pack(anchor='w',pady=(SPACING['xs'],SPACING['none']))
        if session.get('refresh_token') or entitlement.payload:
            self._account_signed_in(status, head, entitlement, session)
        else:
            self._account_login_form()
        self._account_about_card()
        self._account_help_card()

    def _account_about_card(self):
        """账户页挂「关于与开源许可」块：构建细节在模块级 ``about_card``（类体积棘轮上限 600 行）。"""
        about_card(self.content, about_info())

    def _account_help_card(self):
        """账户页挂「帮助」块（与「关于」同处）：文档清单与读文在模块级 ``help_card``。"""
        help_card(self.content)

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
        def logout_done(result):
            if (result.data or {}).get('local_cleared'):
                self.show(PAGE_ACCOUNT)
                self._account_changed()
            self.status.set('已退出登录（项目和素材不受影响）' if result.ok else result.reason)

        def logout():
            self.account.logout(done=logout_done)

        SecondaryButton(actions,text='退出登录',command=logout,style='Tokens.Text.TButton').pack(side='right')
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
        # 危险操作单独一组：分隔线下另起一排（REQ-UI-L5-1）。
        ttk.Separator(card,orient='horizontal').pack(fill='x',pady=(SPACING['sm'],SPACING['xs']))
        danger = ttk.Frame(card);danger.pack(fill='x')
        ttk.Label(danger,text='危险操作',style='Muted.TLabel').pack(side='left')
        for key, title, build in reversed(tools):
            parent,style = (danger,'Tokens.Danger.TButton') if key == 'delete' else (row,'Tokens.Text.TButton')
            button = SecondaryButton(parent,text=title,style=style,
                                     command=lambda t=title,b=build:self._account_open_dialog(t,b))
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
        button = SecondaryButton(row,text='兑换',command=submit,style='Tokens.Text.TButton')
        button.pack(side='right',padx=(SPACING['sm'],SPACING['none']))
        code.pack(side='left',fill='x',expand=True)
        self.account_redeem_input,self.account_redeem_button,self.account_redeem_message = code,button,message

    def _account_login_form(self):
        holder = ttk.Frame(self.content); holder.pack(fill='x', pady=SPACING['sm'])
        holder.columnconfigure(0, weight=1)
        holder.columnconfigure(1, minsize=DESKTOP_LAYOUT['login_gate_width'], weight=0)
        holder.columnconfigure(2, weight=1)
        box = ttk.Frame(holder); box.grid(row=0, column=1, sticky='ew')
        self._build_login_form(box, lambda: (self.show(PAGE_ACCOUNT), self.status.set('登录成功'), self._account_changed()),
                               wrap=DESKTOP_LAYOUT['login_gate_wrap'])

    def _build_login_form(self, parent, on_success, *, wrap=None):
        """账号页与启动登录闸共用：居中定宽单卡承载密码登录／注册／验证码登录／找回密码四视图。"""
        _build_auth_card(self, parent, on_success, wrap=wrap)


def _auth_field_label(parent, text, *, top='sm'):
    """极简登录卡的弱化字段标签（固定用 Muted.TLabel，不手写字体／颜色）。"""
    label = ttk.Label(parent, text=text, style='Muted.TLabel')
    label.pack(anchor='w', pady=(SPACING[top], SPACING['xs']))
    return label


def _auth_code_row(parent, placeholder, button_text, command):
    """验证码输入框与发送按钮同行排布：左框占主宽，右按钮紧凑自适应。"""
    row = ttk.Frame(parent); row.pack(fill='x', pady=(SPACING['none'], SPACING['xs']))
    code = LineInput(row, placeholder=placeholder); code.pack(side='left', fill='x', expand=True)
    send = SecondaryButton(row, text=button_text, width=0, style='Tokens.Secondary.TButton', command=command)
    send.pack(side='right', padx=(SPACING['xs'], SPACING['none']))
    return code, send


def _auth_pw_view(account, kit):
    """密码登录视图：密码框＋全宽主按钮＋单行底部极简文字链接。"""
    field_box, action_box = kit.fields['pw'], kit.actions['pw']
    _auth_field_label(field_box, '登录密码')
    password = PasswordInput(field_box, placeholder='密码')
    password.pack(fill='x', pady=(SPACING['none'], SPACING['xs']))
    def password_login():
        value = kit.checked_email()
        if not value or not kit.required(password, '请填写密码'): return
        pw_login.state(['disabled']); kit.say('正在登录…')
        account.password_login(value, password.get(), kit.finished(pw_login))
    password.bind('<Return>', lambda _event: password_login())
    pw_login = PrimaryButton(action_box, text='登录', command=password_login)
    pw_login.pack(fill='x', pady=(SPACING['md'], SPACING['xs']))
    links = ttk.Frame(action_box); links.pack(fill='x', pady=(SPACING['xs'], SPACING['none']))
    # 点「用验证码登录」直接发验证码：邮箱不合法就留在密码页报错，发出后才切到验证码视图并放开登录键
    use_code = SecondaryButton(links, text='用验证码登录', width=0, style='Tokens.Text.TButton',
                               command=lambda: kit.send('login', use_code, after=kit.open_code_login))
    use_code.pack(side='left')
    forgot = SecondaryButton(links, text='忘记密码', width=0, style='Tokens.Text.TButton',
                             command=lambda: kit.show_view('reset'))
    forgot.pack(side='right')
    return password, pw_login, forgot, use_code


def _auth_reg_view(account, kit):
    """注册视图：内联验证码行＋设置／确认密码＋年满 18 周岁勾选＋全宽主按钮。"""
    field_box, action_box = kit.fields['reg'], kit.actions['reg']
    _auth_field_label(field_box, '邮箱验证码')
    reg_code, reg_send = _auth_code_row(field_box, '6 位验证码', '发送验证码',
                                        lambda: kit.send('register', reg_send))
    _auth_field_label(field_box, '设置密码')
    reg_password = PasswordInput(field_box, placeholder='设置密码（8–64 位，含字母和数字）')
    reg_password.pack(fill='x', pady=(SPACING['none'], SPACING['xs']))
    reg_again = PasswordInput(field_box, placeholder='再次输入密码')
    reg_again.pack(fill='x', pady=(SPACING['none'], SPACING['xs']))
    reg_adult = tk.BooleanVar(master=kit.form, value=False)
    ttk.Checkbutton(field_box, text=AGE_CONFIRM_TEXT, variable=reg_adult).pack(
        anchor='w', pady=(SPACING['xs'], SPACING['none']))
    def register():
        value = kit.checked_email()
        if not value or not kit.required(reg_code, '请填写验证码') or not kit.checked_password(reg_password, reg_again): return
        if not reg_adult.get(): kit.say('请先勾选「已满 18 周岁，并同意用户协议与隐私政策」', True); return
        reg_button.state(['disabled']); kit.say('正在注册…')
        account.register(value, reg_code.get(), reg_password.get(), age_confirmed=True, done=kit.finished(reg_button))
    reg_button = PrimaryButton(action_box, text='注册并登录', command=register)
    reg_button.pack(fill='x', pady=(SPACING['md'], SPACING['xs']))
    return reg_send, reg_code, reg_password, reg_again, reg_adult, reg_button


def _auth_reset_view(account, kit):
    """找回密码视图：内联验证码行＋新密码／确认密码＋全宽主按钮＋单行返回链接。"""
    field_box, action_box = kit.fields['reset'], kit.actions['reset']
    _auth_field_label(field_box, '重置验证码')
    reset_code, reset_send = _auth_code_row(field_box, '6 位验证码', '发送验证码',
                                            lambda: kit.send('reset', reset_send))
    _auth_field_label(field_box, '新密码')
    reset_password = PasswordInput(field_box, placeholder='新密码（8–64 位，含字母和数字）')
    reset_password.pack(fill='x', pady=(SPACING['none'], SPACING['xs']))
    reset_again = PasswordInput(field_box, placeholder='再次输入新密码')
    reset_again.pack(fill='x', pady=(SPACING['none'], SPACING['xs']))
    def reset_done():
        kit.clear_password(); kit.show_view('pw', '密码已重置，请用新密码登录')
    def reset():
        value = kit.checked_email()
        if not value or not kit.required(reset_code, '请填写验证码') or not kit.checked_password(reset_password, reset_again): return
        reset_button.state(['disabled']); kit.say('正在重置密码…')
        account.reset_password(value, reset_code.get(), reset_password.get(), kit.finished(reset_button, reset_done))
    reset_button = PrimaryButton(action_box, text='重置密码', command=reset)
    reset_button.pack(fill='x', pady=(SPACING['md'], SPACING['xs']))
    links = ttk.Frame(action_box); links.pack(fill='x', pady=(SPACING['xs'], SPACING['none']))
    SecondaryButton(links, text='返回密码登录', width=0, style='Tokens.Text.TButton',
                    command=lambda: kit.show_view('pw')).pack(side='left')
    return reset_send, reset_code, reset_password, reset_again, reset_button


def _login_code_view(account, kit):
    """验证码登录视图（没设过密码的旧账号也能进；邮箱未注册时服务端顺带建号），返回 (验证码框, 登录, 发码, 撤销注销)。"""
    field_box, action_box = kit.fields['code'], kit.actions['code']
    _auth_field_label(field_box, '邮箱验证码')
    code, code_send = _auth_code_row(field_box, '6 位验证码', '发送验证码',
                                     lambda: kit.send('login', code_send, after=lambda: login.state(['!disabled'])))
    adult = tk.BooleanVar(master=kit.form, value=False)
    ttk.Checkbutton(field_box, text=AGE_CONFIRM_TEXT, variable=adult).pack(
        anchor='w', pady=(SPACING['xs'], SPACING['none']))
    ttk.Label(field_box, text='未注册邮箱将自动建号，须勾选确认已满 18 周岁并同意协议。',
              style='Muted.TLabel', wraplength=kit.wrap, justify='left').pack(anchor='w')
    def logged_in(result):
        if not kit.alive(): return
        login.state(['!disabled'])
        if result.ok: kit.on_success()
        elif (result.data or {}).get('code') == 'account_pending_deletion':
            kit.say(result.reason + '。被拦下的验证码仍有效，可点「撤销注销」。', True); kit.show_cancel()
        else: kit.fail(result)
    def cancelled(result):
        if not kit.alive(): return
        cancel.state(['!disabled'])
        if not result.ok: kit.fail(result); return
        cancel.pack_forget(); code.delete(0, 'end'); kit.say('已撤销注销，请重新发送验证码登录')
    def cancel_deletion():
        value = kit.checked_email()
        if not value or not kit.required(code, '请填写验证码'): return
        cancel.state(['disabled']); kit.say('正在撤销注销…'); account.cancel_deletion(value, code.get(), cancelled)
    def code_login():
        value = kit.checked_email()
        if not value or not kit.required(code, '请填写验证码'): return
        login.state(['disabled']); kit.say('正在登录…'); account.login(value, code.get(), age_confirmed=adult.get(), done=logged_in)
    login = PrimaryButton(action_box, text='登录', command=code_login)
    login.pack(fill='x', pady=(SPACING['md'], SPACING['xs']))
    login.state(['disabled'])                # 先发验证码，登录按钮才可用
    cancel_slot = ttk.Frame(action_box); cancel_slot.pack(fill='x')
    cancel = SecondaryButton(cancel_slot, text='撤销注销', command=cancel_deletion)   # 冷静期内登录被拦时才显示
    links = ttk.Frame(action_box); links.pack(fill='x', pady=(SPACING['xs'], SPACING['none']))
    SecondaryButton(links, text='返回密码登录', width=0, style='Tokens.Text.TButton',
                    command=lambda: kit.show_view('pw')).pack(side='left')
    return code, login, code_send, cancel


def _auth_kit(host, email, message, show_view, on_success):
    """登录卡四视图共享的校验、提示与发码回调集合。"""
    def alive(): return bool(message.winfo_exists())
    def say(text, error=False): message.configure(text=text, style='Expired.TLabel' if error else 'Muted.TLabel')
    def invalid(field, text): field.set_error(text); say(text, True)
    def checked_email():
        value = email.get().strip()
        if not value: invalid(email, '请填写邮箱'); return None
        if not account_client.valid_email(value):
            invalid(email, '邮箱格式不正确，请检查是否漏了「.」或「@」（例如 name@qq.com）'); return None
        email.clear_error(); return value
    def checked_password(field, again):
        problem = account_client.password_problem(field.get())
        if problem: invalid(field, problem); return False
        field.clear_error()
        if again.get() != field.get(): invalid(again, '两次输入的密码不一致'); return False
        again.clear_error(); return True
    def required(field, text):
        if field.get().strip(): field.clear_error(); return True
        invalid(field, text); return False
    def fail(result):
        data = result.data or {}
        if data.get('code') == 'http_404': show_view('code', '账号服务暂不支持密码登录，请先用验证码登录', True); return
        if data.get('code') == 'account_pending_deletion':
            show_view('code', result.reason + '。请发送验证码后点「撤销注销」。', True); kit.show_cancel(); return
        wait = data.get('retry_after')
        say(with_help_hint(result.reason + ('（%s 秒后可重试）' % wait if wait else ''), data), True)
    def send(purpose, button, after=None):
        value = checked_email()
        if not value: return
        def sent(result):
            if not alive(): return
            button.state(['!disabled'])
            if result.ok:
                if after: after()
                say(CODE_SENT_TEXT)
            elif (result.data or {}).get('code') == 'email_registered':
                show_view('pw', result.reason + '。忘了密码或没设过密码，可点「忘记密码」。')
            else: fail(result)
        button.state(['disabled']); say('正在发送验证码…'); host.account.request_code(value, sent, purpose=purpose)
    def signed_in():
        # R2046：只认本机会话验签后的状态；仍是未登录就留在表单上，不报「登录成功」。
        if host.account.entitlement().state != entitlement_service.SIGNED_OUT: on_success()
        else: say('登录没有在本机生效，请重新登录；多次失败请检查本机时间或联系客服', True)
    def finished(button, success=None):
        def done(result):
            if not alive(): return
            button.state(['!disabled'])
            if not result.ok: fail(result)
            elif success: success()
            else: signed_in()
        return done
    kit = SimpleNamespace(alive=alive, say=say, fail=fail, send=send, checked_email=checked_email,
                          checked_password=checked_password, required=required, show_view=show_view,
                          on_success=signed_in, finished=finished)
    return kit


def _build_auth_card(host, parent, on_success, *, wrap=None):
    """极简居中登录卡：等宽双段式胶囊页签＋共享邮箱框＋四视图输入区＋错误提示位＋全宽主按钮区。"""
    inner_wrap = max(SPACING['2xl'], (wrap or DESKTOP_LAYOUT['login_gate_wrap']) - SPACING['xl'])
    form = Card(parent, padding=(SPACING['xl'], SPACING['lg'])); form.pack(fill='x', pady=SPACING['xs'])
    tabs = ttk.Frame(form); tabs.pack(fill='x', pady=(SPACING['none'], SPACING['md']))
    tabs.columnconfigure(0, weight=1, uniform='auth_tab'); tabs.columnconfigure(1, weight=1, uniform='auth_tab')
    title = ttk.Label(form, text='', font=FONTS['heading_2'], wraplength=inner_wrap, justify='left')
    title.pack(anchor='w', pady=(SPACING['none'], SPACING['sm']))
    _auth_field_label(form, '邮箱地址', top='none')
    email = EmailInput(form); email.pack(fill='x', pady=(SPACING['none'], SPACING['xs']))
    remembered = host.account.last_email()
    if remembered: email.insert(0, remembered)          # R2052：默认显示上一次登录的邮箱，无需再输
    fields_body = ttk.Frame(form); fields_body.pack(fill='x')
    message = ttk.Label(form, text='', style='Muted.TLabel', wraplength=inner_wrap, justify='left')
    message.pack(fill='x', pady=(SPACING['xs'], SPACING['none']))
    actions_body = ttk.Frame(form); actions_body.pack(fill='x')
    fields = {key: ttk.Frame(fields_body) for key in LOGIN_VIEWS}
    actions = {key: ttk.Frame(actions_body) for key in LOGIN_VIEWS}
    current = {'view': 'pw'}
    def show_view(key, text='', error=False):
        for frame in fields.values(): frame.pack_forget()
        for frame in actions.values(): frame.pack_forget()
        fields[key].pack(fill='x'); actions[key].pack(fill='x')
        title.configure(text=LOGIN_VIEWS[key]); current['view'] = key
        login_tab.configure(style='Selected.RailIcon.TButton' if key == 'pw' else 'RailIcon.TButton')
        register_tab.configure(style='Selected.RailIcon.TButton' if key == 'reg' else 'RailIcon.TButton')
        message.configure(text=text, style='Expired.TLabel' if error else 'Muted.TLabel')
    kit = _auth_kit(host, email, message, show_view, on_success)
    kit.form, kit.fields, kit.actions, kit.wrap = form, fields, actions, inner_wrap
    code, login, code_send, cancel = _login_code_view(host.account, kit)
    kit.show_cancel = lambda: cancel.pack(fill='x', pady=(SPACING['xs'], SPACING['none']))
    kit.open_code_login = lambda: (show_view('code'), login.state(['!disabled']))
    password, pw_login, forgot, use_code = _auth_pw_view(host.account, kit)
    kit.clear_password = lambda: password.delete(0, 'end')
    reg_send, reg_code, reg_password, reg_again, reg_adult, reg_button = _auth_reg_view(host.account, kit)
    reset_send, reset_code, reset_password, reset_again, reset_button = _auth_reset_view(host.account, kit)
    login_tab = SecondaryButton(tabs, text='登录', width=0, style='Selected.RailIcon.TButton',
                                command=lambda: show_view('pw'))
    register_tab = SecondaryButton(tabs, text='注册', width=0, style='RailIcon.TButton',
                                   command=lambda: show_view('reg'))
    login_tab.grid(row=0, column=0, sticky='ew', padx=(SPACING['none'], SPACING['xs']))
    register_tab.grid(row=0, column=1, sticky='ew', padx=(SPACING['xs'], SPACING['none']))
    show_view('pw')
    host.account_login_view, host.account_show_login_view = current, show_view
    host.account_email_input, host.account_message = email, message
    host.account_login_tab, host.account_register_tab = login_tab, register_tab
    host.account_password_input, host.account_password_login_button = password, pw_login
    host.account_forgot_button, host.account_use_code_button = forgot, use_code
    host.account_register_send_button, host.account_register_code_input = reg_send, reg_code
    host.account_register_password_input, host.account_register_password2_input = reg_password, reg_again
    host.account_register_adult, host.account_register_button = reg_adult, reg_button
    host.account_code_input, host.account_login_button, host.account_send_button = code, login, code_send
    host.account_cancel_deletion_button = cancel
    host.account_reset_send_button, host.account_reset_code_input = reset_send, reset_code
    host.account_reset_password_input, host.account_reset_password2_input = reset_password, reset_again
    host.account_reset_button = reset_button
