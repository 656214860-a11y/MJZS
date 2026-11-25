# -*- coding: utf-8 -*-
"""启动登录闸：未登录先盖登录页，登录后才启动；已登录（含到期）直接进。"""
import contextlib
import os
import re
import shutil
import tempfile
import unittest
import unittest.mock
import tk_test_support
import sys
from tkinter import ttk
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))

from infra import account_store
from infra import lease_verifier
from orchestrator.account_controller import AccountController
from desktop import Desktop
from contract.service_contract import SystemError, success
import account_client
import test_desktop_startup_perf as startup_fixtures
from test_account_client import KEYS, NOW, _Client, _Store, payload, sign

DAY=86400


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

    def test_gate_form_compact_contract(self):
        """REQ-UI-L5-1：登录面板——邮箱＋口令、一个强调色主按钮、文字式次要入口；
        错误提示在输入框下方。"""
        d=self.desktop
        self.use(_Client())
        started=[]
        d.begin_startup_or_login(True,lambda:started.append(1));self.pump()
        gate=d.login_gate
        self.assertTrue(gate.winfo_exists())
        primaries=[w for w in _walk(gate) if isinstance(w,ttk.Button)
                   and str(w.cget('style'))=='Tokens.Primary.TButton'
                   and w.winfo_ismapped()]
        self.assertEqual([str(b.cget('text')) for b in primaries],['登录'],
                         '登录面板只保留一个强调色主按钮')
        for name in ('account_forgot_button','account_use_code_button'):
            self.assertEqual(str(getattr(d,name).cget('style')),'Tokens.Text.TButton',
                             '%s 是次要入口，用文字样式' % name)
        self.assertGreater(d.account_message.winfo_rooty(),
                           d.account_password_input.winfo_rooty(),
                           '错误提示在输入框下方一行')

    def test_gate_auth_card_segmented_tabs_full_width_primary_and_inline_code_row(self):
        """UX-LOGIN-CLEAN：极简居中登录卡——等宽双段胶囊页签、全宽主按钮、底部同行链接、内联验证码行与精简标题。"""
        from ui.desktop_account_page import LOGIN_VIEWS
        d=self.desktop
        self.use(_Client())
        d.begin_startup_or_login(True,lambda:None);self.pump()
        gate=d.login_gate
        # ① 顶部等宽双段式胶囊页签（不再置灰当前页签）
        self.assertEqual(str(d.account_login_tab.cget('style')),'Selected.RailIcon.TButton')
        self.assertNotIn('disabled',d.account_login_tab.state())
        self.assertEqual(str(d.account_register_tab.cget('style')),'RailIcon.TButton')
        self.assertLessEqual(abs(d.account_login_tab.winfo_width()-d.account_register_tab.winfo_width()),4,
                             '登录／注册胶囊页签应等宽')
        self.assertLessEqual(abs(d.account_login_tab.winfo_rooty()-d.account_register_tab.winfo_rooty()),4)
        # ② 主按钮铺满卡片主体宽度，底部文字链接位于主按钮下方同一水平行
        email_w=d.account_email_input.winfo_width()
        self.assertGreater(email_w,0)
        self.assertGreaterEqual(d.account_password_login_button.winfo_width(),email_w*0.85,
                                '主登录按钮应全宽铺满卡片主体')
        primary_y=d.account_password_login_button.winfo_rooty()
        code_link_y=d.account_use_code_button.winfo_rooty()
        forgot_link_y=d.account_forgot_button.winfo_rooty()
        self.assertLessEqual(abs(code_link_y-forgot_link_y),4,'底部辅助链接应在同一水平行')
        self.assertGreater(code_link_y,primary_y,'底部辅助链接应位于主按钮下方')
        self.assertGreater(forgot_link_y,primary_y,'底部辅助链接应位于主按钮下方')
        # ⑤ 视图标题简洁（无超过 12 字的冗长括号说明）
        for key,heading in LOGIN_VIEWS.items():
            self.assertLessEqual(len(heading),12,f'视图 {key} 标题过长：{heading!r}')
            self.assertNotIn('（',heading,f'视图 {key} 标题不应含冗长括号说明：{heading!r}')
        self.assertIn(LOGIN_VIEWS['pw'],[_text(w) for w in _walk(gate) if isinstance(w,ttk.Label) and w.winfo_ismapped()])
        # ③ 切到注册视图：胶囊切换且验证码框与发码钮同一水平行
        d.account_register_tab.invoke();self.pump()
        self.assertEqual(str(d.account_register_tab.cget('style')),'Selected.RailIcon.TButton')
        self.assertNotIn('disabled',d.account_register_tab.state())
        self.assertEqual(str(d.account_login_tab.cget('style')),'RailIcon.TButton')
        self.assertLessEqual(
            abs(d.account_register_code_input.winfo_rooty()-d.account_register_send_button.winfo_rooty()),8,
            '注册视图验证码框与发码按钮应在同一水平行')
        self.assertGreater(d.account_register_send_button.winfo_rootx(),d.account_register_code_input.winfo_rootx(),
                           '注册视图发码按钮应在验证码框右侧')
        self.assertGreaterEqual(d.account_register_button.winfo_width(),d.account_email_input.winfo_width()*0.85)
        # ④ 切到找回密码视图：验证码框与发码钮同一水平行
        d.account_login_tab.invoke();self.pump()
        d.account_forgot_button.invoke();self.pump()
        self.assertEqual(d.account_login_view['view'],'reset')
        self.assertLessEqual(
            abs(d.account_reset_code_input.winfo_rooty()-d.account_reset_send_button.winfo_rooty()),8,
            '找回密码视图验证码框与发码按钮应在同一水平行')
        self.assertGreater(d.account_reset_send_button.winfo_rootx(),d.account_reset_code_input.winfo_rootx(),
                           '找回密码视图发码按钮应在验证码框右侧')
        self.assertGreaterEqual(d.account_reset_button.winfo_width(),d.account_email_input.winfo_width()*0.85)

    def test_gate_closes_visible_cloud_via_public_pet_api(self):
        class Pet:                                   # 只有公开接口，没有 _cloud
            closed=0
            def cloud_visible(self,sticker_only=False):return True
            def close_chat(self,event=None):Pet.closed+=1
        self.use(_Client())
        with unittest.mock.patch.object(self.desktop,'pet',Pet(),create=True):
            self.desktop.begin_startup_or_login(True,lambda:None)
        self.assertEqual(Pet.closed,1)

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
        d.account_email_input.insert(0,'a@b.cn');d.account_use_code_button.invoke();self.pump()      # 点「用验证码登录」直接发码并切到验证码视图
        d.account_code_input.insert(0,'123456');d.account_login_button.invoke();self.pump()
        self.assertFalse(d.login_gate_active)
        self.assertIsNone(d.login_gate)
        self.assertEqual(started,[1])

    def test_gate_login_redraws_account_page_underneath(self):
        """R2046：闸门下停着登录前画的「会员账户」页；闸门登录后须重画，不能露出旧的「未登录」。"""
        from desktop_page_registry import PAGE_ACCOUNT
        from widget_test_support import widget_texts
        client=_Client(send_code=success({'ok':True}),
                       verify_code=success({'refresh_token':'r1','server_time':NOW,
                                            'lease':sign(payload(state='expired',trial_ends_at=NOW-DAY))}))
        self.use(client)
        d=self.desktop
        d.show(PAGE_ACCOUNT);self.pump()
        self.assertIn('当前状态：未登录',widget_texts(d.content))
        d.begin_startup_or_login(True,lambda:None);self.pump()
        d.account_email_input.insert(0,'a@b.cn');d.account_use_code_button.invoke();self.pump()      # 点「用验证码登录」直接发码并切到验证码视图
        d.account_code_input.insert(0,'123456');d.account_login_button.invoke();self.pump()
        texts=widget_texts(d.content)
        self.assertIsNone(d.login_gate)
        self.assertIn('当前状态：授权已失效',texts)
        self.assertNotIn('当前状态：未登录',texts)
        d.account.logout()

    def test_gate_shows_unreachable_prompts_with_retry(self):
        """R-REL05：网络不通／服务无响应／证书校验失败三种，闸叠加人话提示与重试按钮。"""
        self.assertEqual(len({text for text in account_client.UNREACHABLE_MESSAGES.values()}), 3)
        for code in account_client.UNREACHABLE_MESSAGES:
            with self.subTest(code):
                client = _Client(send_code=SystemError(account_client.UNREACHABLE_MESSAGES[code],
                                                       data={'code': code}))
                self.use(client)
                d = self.desktop
                d.begin_startup_or_login(True, lambda: None)
                self.pump()
                self.assertTrue(d.login_gate_active)
                d.account_email_input.insert(0, 'a@b.cn')
                d.account_use_code_button.invoke()
                self.pump()
                notice = getattr(d, 'gate_notice', None)
                self.assertIsNotNone(notice, '闸没有给出服务不可达的提示')
                self.assertIn(account_client.UNREACHABLE_MESSAGES[code], str(notice.cget('text')))
                button = getattr(d, 'gate_notice_button', None)
                self.assertIsNotNone(button, '闸没有提供重试按钮')
                self.assertTrue(button.winfo_exists())
                sent = sum(1 for name, _args in client.calls if name == 'send_code')
                button.invoke()
                self.pump()
                self.assertEqual(sum(1 for name, _args in client.calls if name == 'send_code'),
                                 sent + 1, '重试按钮没有重新发出登录验证码')

    def test_logout_brings_gate_back(self):
        self.use(_Client(),lease=sign(payload()))
        d=self.desktop
        d.begin_startup_or_login(True,lambda:None)
        self.assertIsNone(d.login_gate)
        d.account.logout()
        d._account_changed();self.pump()
        self.assertTrue(d.login_gate_active)
        self.assertFalse(hasattr(d,'membership_badge'))   # R2027：侧栏到期小字已删

    def test_unlicensed_pages_are_locked_and_unlock_after_renewal(self):
        """R2048：授权失效时只锁收费阶段；授权恢复后解锁并重建当前页。
        R2933：图标轨上锁定改为换 lock.png（PNG 缺失才退回 🔒 文字兜底）。"""
        from desktop_account_page import NAV_LOCK_MARK
        from desktop_page_registry import (NAV_LOCK_ICON, PAGE, PAGE_ACCOUNT,
                                           PAGE_NAV_ICONS, PAGE_SITES)
        from ui_icons import IconLoader
        d=self.desktop
        store=self.use(_Client(),lease=sign(payload(state='expired',trial_ends_at=NOW-DAY)))
        d._require_login=True;d.refresh_nav_locks()
        def locked():
            return any(getattr(w,'cget',None) and _text(w)=='需要登录或授权' for w in _walk(d.content))
        def nav_icon(index,name):
            return IconLoader.nav_icon(d.nav[index],name)
        def image_name(index):
            value=str(d.nav[index].cget('image'))
            found=re.findall(r"'([^']+)'",value)
            return found[0] if found else value
        try:
            index=PAGE['storyboard']
            button=d.nav[index]
            self.assertTrue(button._nav_locked)
            if nav_icon(index,NAV_LOCK_ICON) is not None:
                self.assertEqual(image_name(index),str(nav_icon(index,NAV_LOCK_ICON)))
                self.assertEqual(str(button.cget('compound')),'image')
            else:
                self.assertTrue(button.cget('text').endswith(NAV_LOCK_MARK))
            self.assertFalse(getattr(d.nav[PAGE['script_structure']],'_nav_locked',False))
            self.assertFalse(getattr(d.nav[PAGE_SITES],'_nav_locked',False))
            d.show(PAGE_SITES);self.pump()
            self.assertFalse(locked())
            d.show(PAGE['storyboard']);self.pump()
            self.assertTrue(locked())
            self.assertIn('试用或会员已到期',d.status.get())
            d.show(PAGE_ACCOUNT);self.pump()
            self.assertFalse(locked())
            d.show(PAGE['storyboard']);self.pump()
            account_store.save_session({'email':'a@b.c','refresh_token':'r','lease':sign(payload()),'server_time':NOW},store.path)
            d._account_changed();self.pump()
            self.assertFalse(d.nav[index]._nav_locked)
            if nav_icon(index,PAGE_NAV_ICONS[index]) is not None:
                self.assertEqual(image_name(index),str(nav_icon(index,PAGE_NAV_ICONS[index])))
            self.assertFalse(locked())
        finally:
            d._require_login=False;d.refresh_nav_locks()


    def test_gate_prefills_the_last_login_email_even_after_logout(self):
        """R2052：登录框默认显示上一次登录的邮箱；退出登录后也保留，从没登录过则留空显示占位。"""
        d=self.desktop
        store=self.use(_Client())
        d.begin_startup_or_login(True,lambda:None);self.pump()
        self.assertEqual(d.account_email_input.get(),'','从没登录过：不预填')
        d.login_gate.destroy();d.login_gate=None;d.login_gate_active=False
        account_store.save_session({'email':'me@example.com','refresh_token':'r','lease':sign(payload()),'server_time':NOW},store.path)
        account_store.clear_session(store.path)
        self.assertEqual(account_store.last_email(store.path),'me@example.com')
        self.assertEqual(account_store.load(store.path).get('refresh_token'),None)
        d.begin_startup_or_login(True,lambda:None);self.pump()
        self.assertEqual(d.account_email_input.get(),'me@example.com')


class ModelGuideTests(LoginGateTests):
    """任务书 M7：登录通过且模型池存储为空 → 自动开模型管理并给一行说明。"""

    def _login_through_gate(self, client):
        self.use(client)
        d = self.desktop
        d.begin_startup_or_login(True, lambda: None)
        self.pump()
        d.account_email_input.insert(0, 'a@b.cn')
        d.account_use_code_button.invoke(); self.pump()
        d.account_code_input.insert(0, '123456')

    def test_empty_pool_after_login_opens_model_manager(self):
        """全新账号：模型池存储区空 → 闸通过后打开模型管理并给一行说明。"""
        client = _Client(send_code=success({'ok': True}),
                         verify_code=success({'refresh_token': 'r1',
                                              'lease': sign(payload()), 'server_time': NOW}))
        self._login_through_gate(client)
        d = self.desktop
        opened = []
        import infra.config_snapshot as config_snapshot
        import model_pool
        with unittest.mock.patch.object(model_pool, 'raw', return_value={}),                 unittest.mock.patch.object(config_snapshot, 'has_usable_cli_engine',
                                           return_value=False),                 unittest.mock.patch.object(d.pet, 'open_model_manager',
                                           lambda: opened.append(1)):
            d.account_login_button.invoke(); self.pump()
        self.assertEqual(opened, [1])
        self.assertIn('模型', str(d.status.get()))

    def test_configured_pool_does_not_open_manager(self):
        """模型池已有模型：登录后不出现引导。"""
        client = _Client(send_code=success({'ok': True}),
                         verify_code=success({'refresh_token': 'r1',
                                              'lease': sign(payload()), 'server_time': NOW}))
        self._login_through_gate(client)
        d = self.desktop
        opened = []
        import model_pool
        with unittest.mock.patch.object(model_pool, 'raw',
                                        return_value={'models': {'m1': {'model': 'x'}}}),                 unittest.mock.patch.object(d.pet, 'open_model_manager',
                                           lambda: opened.append(1)):
            d.account_login_button.invoke(); self.pump()
        self.assertEqual(opened, [])

    def test_guide_only_runs_after_gate_passes(self):
        """未走登录闸（持有效授权直入）不触发引导。"""
        self.use(_Client(), lease=sign(payload()))
        d = self.desktop
        opened = []
        with unittest.mock.patch.object(d.pet, 'open_model_manager',
                                        lambda: opened.append(1)):
            d.begin_startup_or_login(True, lambda: None)
            self.pump()
        self.assertEqual(opened, [])


class MissingSetupHintTests(unittest.TestCase):
    """REL-03（REQ-S01-119）：缺模型或引擎时的统一提示——同一句话、指出去处。"""

    def test_hint_lists_both_destinations(self):
        import model_router
        text = model_router.missing_setup_hint()
        self.assertIn('需要配置', text)
        for needle in ('模型管理', '新增模型', 'API Key', '命令行引擎', '调用设置', '.exe'):
            self.assertIn(needle, text)

    def test_hint_accepts_a_specific_destination(self):
        import model_router
        text = model_router.missing_setup_hint('点下方「配置线上视频 API」保存接口与 Key')
        self.assertIn('需要配置', text)
        self.assertIn('配置线上视频 API', text)


class FirstRunMatrixTests(LoginGateTests):
    """REL-03（REQ-S01-119）：干净机器四种缺配置组合的端到端行为——
    启动自检、登录引导、发送边界三处的提示都要指出去处；不调用真实模型。"""

    def _sandbox_engines(self, engines=()):
        """引擎探测环境钉进临时沙盒：PATH 查不到引擎、安装目录指向临时位置；
        ``engines`` 里列出的引擎在其已知安装目录放入假 .exe。"""
        sandbox = Path(tempfile.mkdtemp(dir=self.temp.name))
        local, appdata, home = sandbox / 'LA', sandbox / 'AD', sandbox / 'home'
        plants = {'codex': local / 'OpenAI' / 'Codex' / 'bin' / 'v1' / 'codex.exe',
                  'claude': home / '.local' / 'bin' / 'claude.exe'}
        for name in engines:
            exe = plants[name]
            exe.parent.mkdir(parents=True, exist_ok=True)
            exe.write_text('x')
        real_which = shutil.which
        engine_exes = ('codex.exe', 'claude.exe', 'qwen.exe', 'opencode-cli.exe')
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(unittest.mock.patch('shutil.which',
                lambda name, *a, **k: None if name in engine_exes else real_which(name, *a, **k)))
        stack.enter_context(unittest.mock.patch.dict(os.environ,
                {'LOCALAPPDATA': str(local), 'APPDATA': str(appdata)}))
        stack.enter_context(unittest.mock.patch.object(Path, 'home', classmethod(lambda cls: home)))
        return sandbox

    def _login_through_gate(self, client):
        """同 ModelGuideTests：走闸到输入验证码前一步；登录键留给调用方在补丁上下文里点。"""
        self.use(client)
        d = self.desktop
        d.begin_startup_or_login(True, lambda: None)
        self.pump()
        d.account_email_input.insert(0, 'a@b.cn')
        d.account_use_code_button.invoke(); self.pump()
        d.account_code_input.insert(0, '123456')

    def _gate_guide(self, models):
        """走完整登录闸，``models`` 为 model_pool.raw 的补丁值；返回 (是否开模型管理, 状态栏文本)。"""
        client = _Client(send_code=success({'ok': True}),
                         verify_code=success({'refresh_token': 'r1',
                                              'lease': sign(payload()), 'server_time': NOW}))
        self._login_through_gate(client)
        d = self.desktop
        opened = []
        import model_pool
        with unittest.mock.patch.object(model_pool, 'raw', return_value=models), \
                unittest.mock.patch.object(d.pet, 'open_model_manager', lambda: opened.append(1)):
            d.account_login_button.invoke(); self.pump()
        return opened, str(d.status.get())

    def _selfcheck_program(self, models=None):
        """临时程序目录（含可选模型池配置），跑真实启动自检返回 Diagnostic 列表。"""
        import infra.diagnostic_capture as diagnostic_capture
        from test_startup_selfcheck import _write_models
        program = Path(tempfile.mkdtemp(dir=self.temp.name)) / '程序'
        _write_models(program, models)
        state = Path(self.temp.name) / 'logs' / 'diagnostics' / 'latest.json'
        with unittest.mock.patch.multiple(diagnostic_capture, PROGRAM=program,
                LOGS=state.parent.parent, ERROR_LOG=state.parent.parent / 'e.log',
                STATE_FILE=state):
            return diagnostic_capture.run_startup_selfcheck(program)

    def _send(self, **kwargs):
        """发送边界真实解析：空项目在 storyboard 阶段走 resolve_for_send。"""
        import orchestrator.workflow_settings as workflow_settings
        project = Path(tempfile.mkdtemp(dir=self.temp.name))
        return workflow_settings.resolve_for_send(project, 'storyboard', **kwargs)

    def test_first_run_matrix_empty_pool_no_engine(self):
        """REQ-S01-119 空池无引擎：自检报 model-pool-empty、登录后弹模型管理、
        发送在入队前被拦——三处提示都含两处去处。"""
        self._sandbox_engines()
        hit = [item for item in self._selfcheck_program() if item.code == 'model-pool-empty']
        self.assertEqual(len(hit), 1)
        for needle in ('模型管理', '调用设置'):
            self.assertIn(needle, hit[0].remedy)
        opened, status = self._gate_guide({})
        self.assertEqual(opened, [1])
        for needle in ('模型管理', '调用设置'):
            self.assertIn(needle, status)
        with self.assertRaises(ValueError) as ctx:
            self._send()
        for needle in ('模型管理', '调用设置'):
            self.assertIn(needle, str(ctx.exception))

    def test_first_run_matrix_cli_engine_only(self):
        """REQ-S01-119 只装命令行引擎：自检不报空池、登录后不弹引导、
        发送预检放行（本条是卡面点名的有意契约变更）。"""
        self._sandbox_engines(('codex',))
        self.assertNotIn('model-pool-empty', [item.code for item in self._selfcheck_program()])
        opened, _status = self._gate_guide({})
        self.assertEqual(opened, [])
        config = self._send()
        self.assertEqual(config['engine'], 'codex')

    def test_first_run_matrix_api_only(self):
        """REQ-S01-119 只配直连 API：自检干净、不弹引导；直连发送不查本机引擎。"""
        self._sandbox_engines()
        self.assertNotIn('model-pool-empty',
                         [item.code for item in self._selfcheck_program({'m1': {'model': 'm', 'label': 'M'}})])
        opened, _status = self._gate_guide({'models': {'m1': {'model': 'm'}}})
        self.assertEqual(opened, [])
        config = self._send(direct_api=True, model_snapshot=('m1', {'model': 'm', 'label': 'M'}))
        self.assertEqual(config['engine'], 'qwen')
        self.assertEqual(config['model'], 'm1')

    def test_first_run_matrix_engine_and_api(self):
        """REQ-S01-119 两者齐全：自检干净、无引导、发送预检放行。"""
        self._sandbox_engines(('codex',))
        self.assertNotIn('model-pool-empty',
                         [item.code for item in self._selfcheck_program({'m1': {'model': 'm', 'label': 'M'}})])
        opened, _status = self._gate_guide({'models': {'m1': {'model': 'm'}}})
        self.assertEqual(opened, [])
        config = self._send()
        self.assertEqual(config['engine'], 'codex')


def _walk(widget):
    for child in widget.winfo_children():
        yield child
        yield from _walk(child)


def _text(widget):
    try:return str(widget.cget('text'))
    except Exception:return ''

if __name__=='__main__':
    unittest.main()
