"""启动登录闸（L4，只放 Tk 控件与回调注入）。

真实启动（``Desktop(..., require_login=True)``）时，本机没有可用登录会话（``SIGNED_OUT``）就在主窗口上盖一层
全屏登录页：登录成功前不选项目、不检查更新，登录后才走原来的首帧启动流程。已登录但授权失效
（``LOCKED``／``GRACE``／``CLOCK_SUSPECT``）的账号照常进主界面，付费阶段仍由 ``stage_gate`` 拦截。
判定只读本机会话并验签，不联网。显式注入关闭拦截或宿主不要求登录时不建覆盖层。
登录／注册／验证码登录／找回密码表单与「00 会员账户」页共用 ``AccountPageMixin._build_login_form``。
"""
from tkinter import ttk

import account_client
import domain.entitlement_service as entitlement_service
from contract.app_metadata import APP_NAME
from ui.desktop_page_registry import PAGE_ACCOUNT
from ui_tokens import DESKTOP_LAYOUT, FONTS, SPACING

LOGIN_GATE_NOTE = '新账号免费试用 3 天 · 项目与素材仅存本机，不上传'


class LoginGateMixin:
    login_gate = None
    login_gate_active = False
    _require_login = False
    _login_gate_startup_pending = False

    def login_required(self):
        """宿主要求登录和拦截，且本机没有登录会话。"""
        account = self.account
        return bool(self._require_login and account.enforce
                    and account.entitlement().state == entitlement_service.SIGNED_OUT)

    def begin_startup_or_login(self, require_login, start_startup):
        """``Desktop.__init__`` 末段调用：需要登录就显示登录闸，否则直接启动。"""
        self._require_login = bool(require_login)
        self._refresh_nav_locks()
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
        inner.place(relx=0.5, rely=0.46, anchor='center', width=DESKTOP_LAYOUT['login_gate_width'])
        ttk.Label(inner, text=APP_NAME, font=FONTS['heading_1'], anchor='center',
                  justify='center').pack(fill='x', pady=(SPACING['none'], SPACING['xs']))
        ttk.Label(inner, text=LOGIN_GATE_NOTE, style='Muted.TLabel', wraplength=DESKTOP_LAYOUT['login_gate_wrap'],
                  anchor='center', justify='center').pack(fill='x', pady=(SPACING['none'], SPACING['md']))
        self.login_gate, self.login_gate_active = gate, True
        gate.lift()
        pet = getattr(self, 'pet', None)
        if pet is not None and pet.cloud_visible():
            pet.close_chat()               # R2051：闸门出现前已冒出的三虎云朵收掉（R2069 改走公开接口）
        self._build_login_form(inner, self._login_gate_passed, wrap=DESKTOP_LAYOUT['login_gate_wrap'])
        arm = getattr(self, '_arm_gate_unreachable_notice', None)
        if callable(arm):
            arm()

    def _login_gate_passed(self):
        gate, self.login_gate, self.login_gate_active = self.login_gate, None, False
        if gate is not None and gate.winfo_exists():
            gate.destroy()
        self._hide_gate_notice()
        self.status.set('登录成功')
        self._refresh_nav_locks()
        if self._login_gate_startup_pending:
            self._login_gate_startup_pending = False
            self._login_gate_start()
        # R2046：闸门下面那页是登录前画的；停在「会员账户」页就重画，否则露出过期的「未登录」画面。
        if getattr(self, 'page_index', None) == PAGE_ACCOUNT:
            self.show(PAGE_ACCOUNT)
        self._guide_first_model_setup()

    def _arm_gate_unreachable_notice(self):
        """服务不可达时，登录闸叠加人话提示（网络不通／服务无响应／证书校验失败）与重试按钮。"""
        message = getattr(self, 'account_message', None)
        if message is None or not hasattr(message, 'winfo_exists'):
            return
        original = message.configure
        unreachable = set(account_client.UNREACHABLE_MESSAGES.values())

        def patched(*args, **kwargs):
            original(*args, **kwargs)
            try:
                text = str(message.cget('text') or '')
            except Exception:  # noqa: BLE001 —— 读文本失败不影响登录闸本身
                return
            # 提示文本可能带「（N 秒后可重试）」与「；查看帮助：…」后缀，按前缀认。
            if any(text.startswith(item) for item in unreachable):
                self._show_gate_notice()
            else:
                self._hide_gate_notice()

        message.configure = patched

    def _show_gate_notice(self):
        """显示失败提示与「重试」按钮；已显示则只刷新文案、重新置顶并可用。

        按钮复用表单「用验证码登录」的 SecondaryButton 类：本模块不新增 ui_widgets
        同层边（``_layers.SAME_LAYER_EDGES`` 未登记），也不退回裸 ``ttk.Button``
        （按钮边界门禁）。
        """
        if not (self.login_gate is not None and self.login_gate.winfo_exists()):
            return
        text = str(self.account_message.cget('text') or '')
        notice = getattr(self, 'gate_notice', None)
        if notice is not None and notice.winfo_exists():
            self.gate_notice_box.pack(side='bottom', fill='x',
                                      pady=(SPACING['sm'], SPACING['none']))
            notice.configure(text=text)
            self.gate_notice_button.state(['!disabled'])
            return
        box = ttk.Frame(self.login_gate)
        box.pack(side='bottom', fill='x', pady=(SPACING['sm'], SPACING['none']))
        notice = ttk.Label(box, style='Muted.TLabel', justify='left',
                           wraplength=DESKTOP_LAYOUT['login_gate_wrap'], text=text)
        notice.pack(side='left', fill='x', expand=True)
        button = type(self.account_use_code_button)(box, text='重试', command=self._gate_notice_retry)
        button.pack(side='right', padx=(SPACING['sm'], SPACING['none']))
        self.gate_notice, self.gate_notice_button, self.gate_notice_box = notice, button, box

    def _hide_gate_notice(self):
        box = getattr(self, 'gate_notice_box', None)
        if box is not None and box.winfo_exists():
            box.pack_forget()

    def _gate_notice_retry(self):
        """登录闸「重试」：走「用验证码登录」同一条发送路径；失败提示会再次出现。"""
        button = getattr(self, 'account_use_code_button', None)
        if button is not None and button.winfo_exists():
            button.invoke()

    def _guide_first_model_setup(self):
        """任务书 M7：登录通过后模型池存储区仍为空（从未配过模型）时，
        打开既有模型管理并给一行说明——不另建向导窗口。

        密钥只经模型管理 → ``model_pool.env_file``/本机加密通道保存；本函数
        只判空与开门，不读不写密钥，不写配置。
        """
        try:
            import model_pool
            stored = model_pool.raw().get('models')
            if isinstance(stored, dict) and stored:
                return                              # 已有模型：不打扰
            import infra.config_snapshot as config_snapshot
            if config_snapshot.has_usable_cli_engine():
                return                              # 已装命令行引擎：不打扰（REL-03）
        except Exception:  # noqa: BLE001 —— 配置读不出来按已有处理，不拦登录后续
            return
        opener = getattr(self.pet, 'open_model_manager', None)
        if opener is None:
            return
        import infra.model_router as model_router
        self.status.set(model_router.missing_setup_hint())
        try:
            opener()
        except Exception:  # noqa: BLE001 —— 引导失败不影响已通过的登录
            import infra.app_logging as app_logging
            app_logging.swallowed()

    def _refresh_nav_locks(self):
        hook = getattr(self, 'refresh_nav_locks', None)
        if callable(hook):
            hook()

    def recheck_login_gate(self):
        """会话被清（退出登录、解绑本机、注销、续签判定会话已死）后，回到登录闸。"""
        if self._require_login and not getattr(self, 'shutting_down', False) and self.login_gate is None \
                and self.login_required():
            self.show_login_gate()
