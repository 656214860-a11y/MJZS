"""启动登录闸（L4，只放 Tk 控件与回调注入）。

真实启动（``Desktop(..., require_login=True)``）时，本机没有可用登录会话（``SIGNED_OUT``）就在主窗口上盖一层
全屏登录页：登录成功前不选项目、不检查更新，登录后才走原来的首帧启动流程。已登录但授权失效
（``LOCKED``／``GRACE``／``CLOCK_SUSPECT``）的账号照常进主界面，付费阶段仍由 ``stage_gate`` 拦截。
判定只读本机会话并验签，不联网；``GATE_ENFORCED`` 关闭或不要求登录的宿主（测试）不建覆盖层。
登录表单与「00 会员账户」页共用 ``AccountPageMixin._build_login_form``。
"""
from tkinter import ttk

import entitlement_service
from app_metadata import APP_NAME
from ui_tokens import DESKTOP_LAYOUT, FONTS, SPACING, TEXT_DESC

LOGIN_GATE_NOTE = '请先登录账号。新账号免费试用 3 天；项目和素材始终留在本机，不上传。'


class LoginGateMixin:
    login_gate = None
    login_gate_active = False
    _require_login = False
    _login_gate_startup_pending = False

    def login_required(self):
        """要求登录、总开关开着，且本机没有可用登录会话。"""
        account = self.account
        return bool(self._require_login and account.enforce
                    and account.entitlement().state == entitlement_service.SIGNED_OUT)

    def begin_startup_or_login(self, require_login, start_startup):
        """``Desktop.__init__`` 末段调用：需要登录就显示登录闸，否则直接启动。"""
        self._require_login = bool(require_login)
        self._login_gate_start = start_startup
        if self.login_required():
            self._login_gate_startup_pending = True
            self.show_login_gate()
        else:
            start_startup()

    def show_login_gate(self):
        if self.login_gate is not None and self.login_gate.winfo_exists():
            self.login_gate.lift()
            return
        gate = ttk.Frame(self.win)
        gate.place(relx=0, rely=0, relwidth=1, relheight=1)
        inner = ttk.Frame(gate)
        inner.place(relx=0.5, rely=0.45, anchor='center', width=DESKTOP_LAYOUT['login_gate_width'])
        ttk.Label(inner, text=APP_NAME, font=FONTS['heading_1']).pack(anchor='w', pady=(SPACING['none'], SPACING['xs']))
        ttk.Label(inner, text=LOGIN_GATE_NOTE, style='Muted.TLabel', wraplength=TEXT_DESC['wraplength'],
                  justify='left').pack(anchor='w', pady=(SPACING['none'], SPACING['sm']))
        self.login_gate, self.login_gate_active = gate, True
        gate.lift()
        self._build_login_form(inner, self._login_gate_passed)

    def _login_gate_passed(self):
        gate, self.login_gate, self.login_gate_active = self.login_gate, None, False
        if gate is not None and gate.winfo_exists():
            gate.destroy()
        self.status.set('登录成功')
        if self._login_gate_startup_pending:
            self._login_gate_startup_pending = False
            self._login_gate_start()

    def recheck_login_gate(self):
        """会话被清（退出登录、解绑本机、注销、续签判定会话已死）后，回到登录闸。"""
        if self._require_login and not getattr(self, 'shutting_down', False) and self.login_gate is None \
                and self.login_required():
            self.show_login_gate()
