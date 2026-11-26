# -*- coding: utf-8 -*-
"""轮 3B 启动自检接线：run_startup_selfcheck 组装、乙类检查、G12 开关、
崩溃预算账本、DEGRADED 状态栏出口与启动器保护（任务书 D3-g～D3-n）。"""
from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

HERE = Path(__file__).resolve().parent.parent          # 程序/
REPO = HERE.parent                                     # 仓库根（启动漫剧制作助手.pyw 所在）
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import infra.config_snapshot as config_snapshot
import infra.diagnostic_capture as subject
from contract.diagnostics import Diagnostic, Severity, StartupPhase
from contract.error_codes import describe
from contract.selfcheck import SELFCHECK_TO_CODE
from ui.ui_status_bus import StatusBus

LAUNCHER = REPO / '启动漫剧制作助手.pyw'


def _write_models(program, models=None):
    """写一份最小模型池配置；models=None 表示不写 models 键（视为空池）。"""
    folder = Path(program) / '配置' / '宠物'
    folder.mkdir(parents=True, exist_ok=True)
    data = {'level': 'hint'}
    if models is not None:
        data['models'] = models
    (folder / '配置.json').write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')


class StartupSelfcheckTests(unittest.TestCase):
    """run_startup_selfcheck：L0 甲类＋L1 乙类组装；返回 Diagnostic 列表。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.program = Path(self.temp.name) / '程序'
        self.program.mkdir()
        # 自检结果落盘也改指临时文件：不污染真实 logs/diagnostics/latest.json。
        self.state = Path(self.temp.name) / 'logs' / 'diagnostics' / 'latest.json'
        patcher = mock.patch.multiple(subject, PROGRAM=self.program, LOGS=self.state.parent.parent,
                                      ERROR_LOG=self.state.parent.parent / 'e.log', STATE_FILE=self.state)
        patcher.start()
        self.addCleanup(patcher.stop)
        # 让乙类检查尽量干净：可写目录、模型池非空、随包工具在（真实环境自带）、无 .corrupt
        _write_models(self.program, {'m1': {'model': 'm', 'label': 'm'}})

    def _run(self):
        return subject.run_startup_selfcheck(self.program)

    def _codes(self, items, severity=None):
        rows = [item for item in items if severity is None or item.severity is severity]
        return [item.code for item in rows]

    def test_returns_diagnostic_list_and_records_state(self):
        items = self._run()
        self.assertIsInstance(items, list)
        self.assertTrue(all(isinstance(item, Diagnostic) for item in items))
        state = json.loads(self.state.read_text(encoding='utf-8'))
        self.assertIn('selfcheck', state)                     # 结果已写进诊断状态
        self.assertIsInstance(state['selfcheck']['items'], list)
        self.assertTrue(state['selfcheck']['at'])

    def test_healthy_minimal_program_has_no_fatal(self):
        items = self._run()
        self.assertEqual(self._codes(items, Severity.FATAL), [])

    def test_data_dir_as_file_reports_degraded_writable(self):
        (self.program / 'data').write_text('x', encoding='utf-8')   # 文件占了目录位
        items = self._run()
        degraded = [item for item in items if item.code == 'data-logs-writable']
        self.assertEqual(len(degraded), 1)
        self.assertIs(degraded[0].severity, Severity.DEGRADED)
        self.assertIn('data', degraded[0].message)

    def test_low_disk_space_reports_degraded(self):
        with mock.patch('shutil.disk_usage',
                        return_value=SimpleNamespace(free=100 * 1048576, total=1, used=0)):
            items = self._run()
        hit = [item for item in items if item.code == 'disk-space-low']
        self.assertEqual(len(hit), 1)
        self.assertIs(hit[0].severity, Severity.DEGRADED)

    def test_empty_model_pool_reports_degraded(self):
        _write_models(self.program)                      # 不写 models 键 → 空池
        with mock.patch.object(config_snapshot, 'has_usable_cli_engine', return_value=False):
            items = self._run()
        hit = [item for item in items if item.code == 'model-pool-empty']
        self.assertEqual(len(hit), 1)
        self.assertIs(hit[0].severity, Severity.DEGRADED)
        self.assertEqual(hit[0].scope, StartupPhase.CONFIG.value)

    def test_empty_pool_with_cli_engine_skips_warning(self):
        """REL-03（REQ-S01-119）：模型池为空但本机有命令行引擎 → 不报 model-pool-empty。"""
        _write_models(self.program)
        with mock.patch.object(config_snapshot, 'has_usable_cli_engine', return_value=True):
            self.assertNotIn('model-pool-empty', self._codes(self._run(), Severity.DEGRADED))

    def test_configured_model_pool_has_no_empty_warning(self):
        self.assertNotIn('model-pool-empty', self._codes(self._run()))

    def test_missing_model_config_is_an_empty_pool(self):
        (self.program / '配置' / '宠物' / '配置.json').unlink()
        with mock.patch.object(config_snapshot, 'has_usable_cli_engine', return_value=False):
            self.assertIn('model-pool-empty', self._codes(self._run(), Severity.DEGRADED))

    def test_unreadable_model_config_records_nonfatal_check_error(self):
        (self.program / '配置' / '宠物' / '配置.json').write_text('{', encoding='utf-8')
        items = self._run()
        self.assertNotIn('model-pool-empty', self._codes(items))
        self.assertEqual(self._codes(items, Severity.FATAL), [])
        self.assertIn('check-error', self._codes(items, Severity.DEGRADED))
        state = json.loads(self.state.read_text(encoding='utf-8'))
        self.assertIn('check-error', [row['code'] for row in state['selfcheck']['items']])

    def test_missing_bundled_tools_reports_degraded(self):
        with mock.patch('contract.platform_tools.tool_path', return_value=None):
            items = self._run()
        hit = [item for item in items if item.code == 'bundled-tools-missing']
        self.assertEqual(len(hit), 1)
        self.assertIn('ffmpeg', hit[0].message)

    def test_configured_tool_path_counts_as_present(self):
        seen = {}

        def fake_tool_path(name, fallback='', configured=''):
            seen[name] = configured
            return 'stub'
        with mock.patch('contract.platform_tools.tool_path', side_effect=fake_tool_path):
            items = self._run()
        self.assertEqual(self._codes(items, Severity.DEGRADED), [])
        self.assertIn('ffmpeg', seen)

    def test_dependency_lock_mismatch_reports_degraded(self):
        (self.program / 'requirements.txt').write_text('requests==0.0.0\n', encoding='utf-8')
        items = self._run()
        hit = [item for item in items if item.code == 'dependency-lock-mismatch']
        self.assertEqual(len(hit), 1)
        self.assertIn('requests', hit[0].message)

    def test_dependency_lock_missing_file_is_not_a_finding(self):
        items = self._run()
        self.assertNotIn('dependency-lock-mismatch', self._codes(items))
        self.assertNotIn('dependency-lock-invalid', self._codes(items))

    def test_settings_corrupt_sidecar_reports_degraded(self):
        (self.program / 'desktop_settings.json.corrupt').write_text('{}', encoding='utf-8')
        items = self._run()
        hit = [item for item in items if item.code == 'settings-corrupt']
        self.assertEqual(len(hit), 1)
        self.assertIs(hit[0].severity, Severity.DEGRADED)

    def test_stage_contract_fatal_and_flag_downgrades_to_degraded(self):
        with mock.patch('contract.stage_layout.stage_contract_errors',
                        return_value=('阶段目录顺序与 pet_bus.STAGES 不一致',)):
            fatal_items = self._run()
            self.assertIn('stage-contract', self._codes(fatal_items, Severity.FATAL))
            # G12：data/selfcheck_failopen.flag 存在 → 甲类 FATAL 全部降为 DEGRADED
            flag_dir = self.program / 'data'
            flag_dir.mkdir(exist_ok=True)
            (flag_dir / 'selfcheck_failopen.flag').write_text('', encoding='utf-8')
            degraded_items = self._run()
        self.assertEqual(self._codes(degraded_items, Severity.FATAL), [])
        downgraded = [item for item in degraded_items if item.code == 'stage-contract']
        self.assertEqual(len(downgraded), 1)
        self.assertIs(downgraded[0].severity, Severity.DEGRADED)
        self.assertIn('selfcheck_failopen', downgraded[0].escape_hint)

    def test_selfcheck_never_walks_or_globs_recursively(self):
        calls = {'walk': 0, 'rglob': 0}
        real_walk = os.walk
        real_rglob = Path.rglob

        def counting_walk(*args, **kwargs):
            calls['walk'] += 1
            return real_walk(*args, **kwargs)

        def counting_rglob(self, pattern):
            calls['rglob'] += 1
            return real_rglob(self, pattern)

        with mock.patch('os.walk', counting_walk), \
                mock.patch.object(Path, 'rglob', counting_rglob):
            self._run()
        self.assertEqual(calls, {'walk': 0, 'rglob': 0})


class CliEngineProbeTests(unittest.TestCase):
    """REL-03：config_snapshot.has_usable_cli_engine 的自包含探针，
    查找点与 workflow_settings.find_program 的 CLI 分支对齐（PATH → 已知安装目录）。"""

    def _env(self, root):
        local, appdata, home = Path(root) / 'LA', Path(root) / 'AD', Path(root) / 'home'
        return local, appdata, {'LOCALAPPDATA': str(local), 'APPDATA': str(appdata)}, home

    def test_nothing_installed_reports_false(self):
        with tempfile.TemporaryDirectory() as root:
            _local, _appdata, environ, home = self._env(root)
            self.assertFalse(config_snapshot.has_usable_cli_engine(
                which=lambda name: None, environ=environ, home=home))

    def test_engine_on_path_reports_true(self):
        for exe in ('codex.exe', 'claude.exe', 'qwen.exe', 'opencode-cli.exe'):
            with self.subTest(exe):
                self.assertTrue(config_snapshot.has_usable_cli_engine(
                    which=lambda name, _e=exe: 'x' if name == _e else None,
                    environ={}, home=Path('missing')))

    def test_codex_install_dir_reports_true(self):
        with tempfile.TemporaryDirectory() as root:
            local, _a, environ, home = self._env(root)
            exe = local / 'OpenAI' / 'Codex' / 'bin' / 'v1' / 'codex.exe'
            exe.parent.mkdir(parents=True)
            exe.write_text('x', encoding='utf-8')
            self.assertTrue(config_snapshot.has_usable_cli_engine(
                which=lambda name: None, environ=environ, home=home))

    def test_claude_home_bin_reports_true(self):
        with tempfile.TemporaryDirectory() as root:
            _l, _a, environ, home = self._env(root)
            exe = home / '.local' / 'bin' / 'claude.exe'
            exe.parent.mkdir(parents=True)
            exe.write_text('x', encoding='utf-8')
            self.assertTrue(config_snapshot.has_usable_cli_engine(
                which=lambda name: None, environ=environ, home=home))

    def test_qwen_install_pair_required(self):
        with tempfile.TemporaryDirectory() as root:
            local, _a, environ, home = self._env(root)
            qwen = local / 'qwen-code' / 'qwen-code'
            (qwen / 'node').mkdir(parents=True)
            (qwen / 'node' / 'node.exe').write_text('x', encoding='utf-8')
            (qwen / 'lib').mkdir(parents=True)
            probe = dict(which=lambda name: None, environ=environ, home=home)
            self.assertFalse(config_snapshot.has_usable_cli_engine(**probe),
                             '只有 node.exe、缺 cli-entry.js 不算装好')
            (qwen / 'lib' / 'cli-entry.js').write_text('x', encoding='utf-8')
            self.assertTrue(config_snapshot.has_usable_cli_engine(**probe))

    def test_opencode_appdata_cli_reports_true(self):
        with tempfile.TemporaryDirectory() as root:
            _l, appdata, environ, home = self._env(root)
            exe = Path(environ['APPDATA']) / 'ai.opencode.desktop' / 'cli' / 'v1' / 'opencode-cli.exe'
            exe.parent.mkdir(parents=True)
            exe.write_text('x', encoding='utf-8')
            self.assertTrue(config_snapshot.has_usable_cli_engine(
                which=lambda name: None, environ=environ, home=home))


class StartupDiagnosticsRecordTests(unittest.TestCase):
    """record_selfcheck：自检结果写进诊断状态文件（export 随 latest.json 带走）。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.state = root / 'logs' / 'diagnostics' / 'latest.json'
        patcher = mock.patch.multiple(subject, PROGRAM=root, LOGS=root / 'logs',
                                      ERROR_LOG=root / 'logs' / 'e.log', STATE_FILE=self.state)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_selfcheck_items_persisted_with_severity_and_code(self):
        item = Diagnostic(severity=Severity.DEGRADED, scope='resource', code='disk-space-low',
                          message='磁盘不足 token=abc', remedy='清理磁盘')
        subject.record_selfcheck([item])
        state = json.loads(self.state.read_text(encoding='utf-8'))
        row = state['selfcheck']['items'][0]
        self.assertEqual(row['severity'], 'degraded')
        self.assertEqual(row['code'], 'disk-space-low')
        self.assertNotIn('abc', row['message'])          # 写状态前照样脱敏
        self.assertTrue(state['selfcheck']['at'])


class CrashBudgetTests(unittest.TestCase):
    """diagnostic_capture 崩溃预算（G6/Chromium）：宽限窗、上限、READY/关闭结清、排除项。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.state = root / 'logs' / 'diagnostics' / 'latest.json'
        patcher = mock.patch.multiple(subject, PROGRAM=root, LOGS=root / 'logs',
                                      ERROR_LOG=root / 'logs' / 'e.log', STATE_FILE=self.state)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _guard(self):
        return json.loads(self.state.read_text(encoding='utf-8')).get('startup_guard') or {}

    def _seed(self, **fields):
        self.state.parent.mkdir(parents=True, exist_ok=True)
        self.state.write_text(json.dumps({'startup_guard': fields}), encoding='utf-8')

    def test_first_launch_proceeds_and_marks_attempt(self):
        self.assertEqual(subject.startup_guard(), 'proceed')
        guard = self._guard()
        self.assertTrue(guard.get('attempt_at'))
        self.assertEqual(guard.get('crash_count'), 0)

    def test_three_unfinished_attempts_reach_safe_start(self):
        # 每次启动都没走到 READY（attempt 一直挂着）→ 逐次计崩溃
        self.assertEqual(subject.startup_guard(), 'proceed')      # 第 1 次启动
        self.assertEqual(subject.startup_guard(), 'proceed')      # 第 2 次：计 1 次崩溃
        self.assertEqual(self._guard().get('crash_count'), 1)
        self.assertEqual(subject.startup_guard(), 'proceed')      # 第 3 次：计 2 次
        self.assertEqual(subject.startup_guard(), 'safe_start')   # 第 4 次：计 3 次 → 预算耗尽
        self.assertEqual(self._guard().get('crash_count'), subject.CRASH_LIMIT)

    def test_ready_clears_attempt_and_resets_count(self):
        subject.startup_guard()
        subject.startup_guard()                                   # 计 1 次崩溃
        subject.record_startup_ready()                            # 到达 READY：清零
        guard = self._guard()
        self.assertIsNone(guard.get('attempt_at'))
        self.assertEqual(guard.get('crash_count'), 0)
        self.assertEqual(subject.startup_guard(), 'proceed')
        self.assertEqual(self._guard().get('crash_count'), 0)     # 新启动不继承旧账

    def test_clean_close_settles_attempt_without_counting(self):
        subject.startup_guard()
        subject.record_startup_closed()                           # 正常关闭（含系统结束）
        self.assertIsNone(self._guard().get('attempt_at'))
        self.assertEqual(subject.startup_guard(), 'proceed')
        self.assertEqual(self._guard().get('crash_count'), 0)     # 不计崩溃

    def test_five_minute_window_forgives_old_crashes(self):
        from datetime import datetime, timedelta
        old = (datetime.now() - timedelta(minutes=subject.FORGIVE_MINUTES + 1)).isoformat(timespec='seconds')
        self._seed(attempt_at=None, crash_count=2, last_crash_at=old)
        # 上一次崩溃已出宽限窗：计数先被赦免再 +1 → 2-1+1=2，未达上限
        subject.startup_guard()
        # attempt_at=None → 不结算崩溃；直接看写入的进行中标记
        self.assertEqual(self._guard().get('crash_count'), 2)

    def test_window_forgiveness_applies_when_settling_dead_attempt(self):
        from datetime import datetime, timedelta
        old = (datetime.now() - timedelta(minutes=subject.FORGIVE_MINUTES + 1)).isoformat(timespec='seconds')
        pending = datetime.now().isoformat(timespec='seconds')
        # attempt 挂着＝上次崩了；last_crash 距今 >5min → 赦免 1 次
        self._seed(attempt_at=pending, crash_count=2, last_crash_at=old)
        self.assertEqual(subject.startup_guard(), 'proceed')      # 2-1+1=2 < 3
        self.assertEqual(self._guard().get('crash_count'), 2)

    def test_clock_rollback_counts_as_zero_delta(self):
        from datetime import datetime, timedelta
        future = (datetime.now() + timedelta(hours=1)).isoformat(timespec='seconds')
        pending = datetime.now().isoformat(timespec='seconds')
        # 时钟回拨：last_crash 在未来 → 差值为负按 0 处理 → 不赦免，2+1=3 → 预算耗尽
        self._seed(attempt_at=pending, crash_count=2, last_crash_at=future)
        self.assertEqual(subject.startup_guard(), 'safe_start')

    def test_corrupt_state_file_treated_as_no_history(self):
        self.state.parent.mkdir(parents=True, exist_ok=True)
        self.state.write_text('{not json', encoding='utf-8')
        self.assertEqual(subject.startup_guard(), 'proceed')
        self.assertTrue(self._guard().get('attempt_at'))          # 状态被重写成合法结构

    def test_unwritable_state_file_still_proceeds(self):
        with mock.patch.object(subject, '_save_state', side_effect=OSError('disk full')):
            self.assertEqual(subject.startup_guard(), 'proceed')
            subject.record_startup_ready()                        # 也不抛
            subject.record_startup_closed()

    def test_startup_gate_asks_only_when_budget_exceeded(self):
        asks = []
        self.assertFalse(subject.startup_gate(ask=lambda *a: asks.append(a) or 6))
        self.assertEqual(asks, [])                                # 正常启动不弹二选一
        # 造到预算耗尽
        for _ in range(subject.CRASH_LIMIT):
            subject.startup_guard()
        self.assertTrue(subject.startup_gate(ask=lambda *a: asks.append(a) or 6))
        self.assertEqual(len(asks), 1)
        text = asks[0][0]
        self.assertIn('安全模式', text)
        self.assertIn('不恢复上次项目', text)

    def test_confirm_safe_start_maps_button_ids(self):
        self.assertTrue(subject.confirm_safe_start(ask=lambda *a: 6))    # IDYES
        self.assertFalse(subject.confirm_safe_start(ask=lambda *a: 7))   # IDNO
        self.assertFalse(subject.confirm_safe_start(ask=lambda *a: (_ for _ in ()).throw(RuntimeError('x'))))


class StartupReadyLateTests(unittest.TestCase):
    """DES-APP-06：READY 后移到 settle／登录闸／60s 兜底；不建真实 Desktop／Tk。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.state = root / 'logs' / 'diagnostics' / 'latest.json'
        patcher = mock.patch.multiple(subject, PROGRAM=root, LOGS=root / 'logs',
                                      ERROR_LOG=root / 'logs' / 'e.log', STATE_FILE=self.state)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _guard(self):
        return json.loads(self.state.read_text(encoding='utf-8')).get('startup_guard') or {}

    def _host(self, *, login_gate_active=False, shutting_down=False):
        from ui.desktop_automation_tick import AutomationTickMixin
        from orchestrator.desktop_automation_service import DesktopAutomationScheduler

        class Host(AutomationTickMixin):
            pass

        host = Host()
        host.shutting_down = shutting_down
        host._startup_tick_resume_id = None
        host._startup_tick_paused = True
        host._startup_ready_fallback_id = None
        host.login_gate_active = login_gate_active
        host.win = SimpleNamespace(_desktop_startup_settled=False)
        host._sched = {'cb': None, 'ms': None, 'timer': 'fallback-tid', 'cancelled': []}

        def schedule_after(ms, cb):
            host._sched['ms'] = ms
            host._sched['cb'] = cb
            return host._sched['timer']

        def cancel_scheduled(tid):
            host._sched['cancelled'].append(tid)

        host.automation_scheduler = DesktopAutomationScheduler(
            schedule_after=schedule_after,
            cancel_scheduled=cancel_scheduled,
            is_stopping=lambda: bool(getattr(host, 'shutting_down', False)),
        )
        return host

    def test_ready_fallback_ms_is_sixty_seconds(self):
        self.assertEqual(subject.READY_FALLBACK_MS, 60_000)

    def test_resume_tick_clears_attempt_after_settle(self):
        subject.startup_guard()
        self.assertTrue(self._guard().get('attempt_at'))
        host = self._host()
        host._resume_tick_after_first_paint()
        guard = self._guard()
        self.assertTrue(host.win._desktop_startup_settled)
        self.assertIsNone(guard.get('attempt_at'))
        self.assertEqual(guard.get('crash_count'), 0)

    def test_arm_without_login_keeps_attempt_until_settle(self):
        subject.startup_guard()
        host = self._host(login_gate_active=False)
        host._arm_startup_ready_guard()
        self.assertTrue(self._guard().get('attempt_at'))
        self.assertEqual(host._sched['ms'], subject.READY_FALLBACK_MS)
        host._resume_tick_after_first_paint()
        self.assertIsNone(self._guard().get('attempt_at'))

    def test_login_gate_active_marks_ready_immediately(self):
        subject.startup_guard()
        host = self._host(login_gate_active=True)
        host._arm_startup_ready_guard()
        guard = self._guard()
        self.assertIsNone(guard.get('attempt_at'))
        self.assertEqual(guard.get('crash_count'), 0)

    def test_fallback_callback_clears_budget(self):
        subject.startup_guard()
        host = self._host()
        host._arm_startup_ready_guard()
        self.assertTrue(self._guard().get('attempt_at'))
        host._sched['cb']()
        guard = self._guard()
        self.assertIsNone(guard.get('attempt_at'))
        self.assertEqual(guard.get('crash_count'), 0)

    def test_fallback_skipped_when_shutting_down(self):
        subject.startup_guard()
        host = self._host()
        host._arm_startup_ready_guard()
        host.shutting_down = True
        host._sched['cb']()
        self.assertTrue(self._guard().get('attempt_at'))

    def test_settle_cancels_fallback_timer(self):
        subject.startup_guard()
        host = self._host()
        host._arm_startup_ready_guard()
        host._resume_tick_after_first_paint()
        self.assertIn(host._sched['timer'], host._sched['cancelled'])

    def test_destroy_cancel_all_drops_fallback(self):
        subject.startup_guard()
        host = self._host()
        host._arm_startup_ready_guard()
        host.automation_scheduler.cancel_all()
        self.assertIn(host._sched['timer'], host._sched['cancelled'])
        self.assertTrue(self._guard().get('attempt_at'))

    def test_death_before_ready_still_counts_toward_safe_start(self):
        self.assertEqual(subject.startup_guard(), 'proceed')
        self.assertEqual(subject.startup_guard(), 'proceed')
        self.assertEqual(self._guard().get('crash_count'), 1)
        self.assertEqual(subject.startup_guard(), 'proceed')
        self.assertEqual(subject.startup_guard(), 'safe_start')


class FatalDialogTests(unittest.TestCase):
    """notify_startup_fatal / fatal_diagnostics_text：FATAL 的可操作弹窗文本。"""

    def test_text_contains_message_remedy_escape_and_flag_hint(self):
        item = Diagnostic(severity=Severity.FATAL, scope='contract', code='stage-contract',
                          message='阶段契约撕裂', remedy='请升级程序', escape_hint='联系支持')
        text = subject.fatal_diagnostics_text([item])
        self.assertIn('stage-contract', text)
        self.assertIn('阶段契约撕裂', text)
        self.assertIn('请升级程序', text)
        self.assertIn('联系支持', text)
        self.assertIn('selfcheck_failopen.flag', text)             # G12 关闭开关用法

    def test_text_starts_with_registered_selfcheck_code(self):
        """L5-E3：FATAL 弹窗文本第一行是登记的 E-START-SELFCHECK 文案，原有逐项内容不变。"""
        item = Diagnostic(severity=Severity.FATAL, scope='contract', code='stage-contract',
                          message='阶段契约撕裂', remedy='请升级程序', escape_hint='联系支持')
        text = subject.fatal_diagnostics_text([item])
        self.assertEqual(text.splitlines()[0], describe('E-START-SELFCHECK'))
        self.assertIn('【stage-contract】阶段契约撕裂', text)
        self.assertIn('处理建议：请升级程序', text)
        self.assertIn('selfcheck_failopen.flag', text)

    def test_notify_uses_message_box_and_never_raises(self):
        seen = []
        with mock.patch.object(subject, '_win32_message_box',
                               side_effect=lambda text, title, flags: seen.append((text, title, flags)) or 1):
            subject.notify_startup_fatal([Diagnostic(severity=Severity.FATAL, scope='c',
                                                     code='x', message='坏')])
        self.assertEqual(len(seen), 1)
        self.assertIn('坏', seen[0][0])
        with mock.patch.object(subject, '_win32_message_box', side_effect=RuntimeError('no user32')):
            subject.notify_startup_fatal([Diagnostic(severity=Severity.FATAL, scope='c',
                                                     code='x', message='坏')])   # 不抛


class StartupAnnounceTests(unittest.TestCase):
    """D3-m/H2：DEGRADED 在主窗口状态栏发一次带【警告】前缀的消息，同码每次启动至多一条。"""

    def _announce(self, items):
        from ui import ui_status_bus
        bus = StatusBus()
        events = []
        bus.subscribe(lambda event: events.append(event))
        ui_status_bus.publish_startup_warnings(bus, items)
        bus.pump()
        return [message for kind, message, _prev in events if kind == 'current' and message]

    def _diag(self, code, message='问题说明'):
        return Diagnostic(severity=Severity.DEGRADED, scope='resource', code=code, message=message)

    def test_degraded_items_become_one_warning_with_prefix(self):
        messages = self._announce([self._diag('disk-space-low', '磁盘不足'),
                                   self._diag('model-pool-empty', '模型池为空')])
        self.assertEqual(len(messages), 1)
        text = messages[0].text
        self.assertTrue(text.startswith('【警告】'))
        # EC-5B：逐项经 SELFCHECK_TO_CODE→describe() 统一出口，自检 code 不再上屏。
        self.assertIn(describe(SELFCHECK_TO_CODE['disk-space-low']), text)
        self.assertIn(describe(SELFCHECK_TO_CODE['model-pool-empty']), text)
        self.assertEqual(messages[0].level, 'warning')

    def test_items_render_via_error_code_registry(self):
        """EC-5B：输出含 [E- 与 （建议： 的登记表文案；未进表的码兜底 E-UNKNOWN。"""
        messages = self._announce([self._diag('disk-space-low', '磁盘不足'),
                                   self._diag('app-log-unavailable', '日志装不上')])
        self.assertEqual(len(messages), 1)
        text = messages[0].text
        self.assertTrue(text.startswith('【警告】启动自检：'))
        self.assertIn('[E-', text)
        self.assertIn('（建议：', text)
        self.assertIn(describe('E-IO-WRITE'), text)
        self.assertIn(describe('E-UNKNOWN'), text)
        self.assertNotIn('app-log-unavailable', text)

    def test_same_code_is_announced_once_per_launch(self):
        messages = self._announce([self._diag('disk-space-low', '第一次'),
                                   self._diag('disk-space-low', '重复')])
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].text.count(describe('E-IO-WRITE')), 1)

    def test_empty_and_none_items_are_silent(self):
        self.assertEqual(self._announce([]), [])
        self.assertEqual(self._announce(None), [])


class LauncherWiringTests(unittest.TestCase):
    """启动器源码顺序守卫：二次启动退出在崩溃预算之前；自检在建 Tk 之前。"""

    @classmethod
    def setUpClass(cls):
        cls.source = LAUNCHER.read_text(encoding='utf-8')

    def test_second_instance_exit_precedes_crash_budget(self):
        exit_at = self.source.index('sys.exit(0)')
        budget_at = self.source.index('run_preflight(')
        self.assertLess(exit_at, budget_at,
                        '单实例二次启动必须在启动预检（含崩溃预算）之前退出（不计数不清零）')

    def test_selfcheck_runs_before_tk_construction(self):
        check_at = self.source.index('run_preflight(')
        tk_at = self.source.index('tk.Tk()')
        self.assertLess(check_at, tk_at, '启动预检必须在建 Tk 之前运行')

    def test_launcher_uses_shared_run_preflight(self):
        """REF-L5-1：启动器与 ``desktop_launcher.launch()`` 共用一个预检入口。"""
        self.assertIn('desktop_launcher.run_preflight(', self.source)

    def test_mutex_uses_last_error_safe_kernel(self):
        """L5-REF：CreateMutexW 竞态修复——WinDLL(use_last_error=True)＋get_last_error。"""
        self.assertIn('use_last_error=True', self.source)
        self.assertIn('get_last_error()', self.source)
        self.assertNotIn('kernel.GetLastError', self.source)

    def test_program_dir_is_added_to_sys_path_once(self):
        """L5-REF：程序目录只入 sys.path 一次（第 39 行重复 insert 已删）。"""
        self.assertEqual(self.source.count('sys.path.insert'), 1)

    def test_early_imports_are_inside_try_and_except_has_no_contract_import(self):
        # hash_backend／APP_NAME／app_logging.install 必须在 try 保护内
        self.assertLess(self.source.index('try:'), self.source.index('import hash_backend'))
        # except 分支不再无保护地 import contract：VERSION 取值必须有兜底
        # （取 finally 之后的第一个 except——末尾 MessageBoxW 还有一行 except:pass 兜底）
        except_at = self.source.index('except Exception:', self.source.index('finally:'))
        tail = self.source[except_at:]
        self.assertIn("'未知'", tail)
        self.assertNotIn('from contract.app_metadata import VERSION\n', tail)


class BrokenContractSubprocessTests(unittest.TestCase):
    """D3-n①：contract 包损坏时启动器仍给出提示（子进程＋坏 sys.path，不弹真窗口）。"""

    def test_failure_first_line_literal_matches_registered_code(self):
        """L5-E3：启动文件内含 E-START-FAILED 的字面量与 error_codes.describe 逐字一致。"""
        tree = ast.parse(LAUNCHER.read_text(encoding='utf-8'))
        literals = [node.value for node in ast.walk(tree)
                    if isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and 'E-START-FAILED' in node.value]
        self.assertEqual(literals, [describe('E-START-FAILED')])

    def test_startup_failure_dialog_starts_with_error_code(self):
        """L5-E3：contract 损坏时弹窗文案以 [E-START-FAILED] 开头，并给出日志完整路径。"""
        self.assertTrue(LAUNCHER.is_file(), '仓库根缺少 启动漫剧制作助手.pyw')
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            program = root / '程序'
            (program / 'contract').mkdir(parents=True)
            (program / 'hash_backend.py').write_text(
                'def install():\n    pass\n', encoding='utf-8')
            (program / 'contract' / '__init__.py').write_text('', encoding='utf-8')
            (program / 'contract' / 'app_metadata.py').write_text(
                'raise RuntimeError("contract broken for test")\n', encoding='utf-8')
            launcher = root / '启动漫剧制作助手.pyw'
            shutil.copy(LAUNCHER, launcher)
            wrapper = root / 'wrap.py'
            wrapper.write_text(textwrap.dedent('''
                import sys, types, ctypes, runpy
                class _User32:
                    def MessageBoxW(self, *args):
                        print('DIALOG_TEXT=' + str(args[1]))
                        return 1
                ctypes.windll = types.SimpleNamespace(user32=_User32())
                runpy.run_path(sys.argv[1], run_name='__main__')
            '''), encoding='utf-8')
            done = subprocess.run(
                [sys.executable, '-X', 'utf8', '-B', str(wrapper), str(launcher)],
                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
            self.assertEqual(done.returncode, 0, done.stderr[-2000:])
            line = next((row for row in done.stdout.splitlines()
                         if row.startswith('DIALOG_TEXT=')), '')
            self.assertTrue(line, '弹窗文案没有回传：%r' % done.stdout[-800:])
            text = line.split('=', 1)[1]
            self.assertTrue(text.startswith('[E-START-FAILED]'), text[:200])
            self.assertIn('详情已保存到：' + str(root / '启动错误.log'), done.stdout)

    def test_broken_contract_still_reports_failure(self):
        # 启动器是仓库根必备文件：缺失属检出损坏，按失败处理而非跳过（skip 卫生门禁）。
        self.assertTrue(LAUNCHER.is_file(), '仓库根缺少 启动漫剧制作助手.pyw')
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            program = root / '程序'
            (program / 'contract').mkdir(parents=True)
            # hash_backend 用桩替身：本测试只验证「contract 坏掉时启动器仍有提示」，
            # 不复制真实依赖链（infra.hash_backend 等）。
            (program / 'hash_backend.py').write_text(
                'def install():\n    pass\n', encoding='utf-8')
            (program / 'contract' / '__init__.py').write_text('', encoding='utf-8')
            (program / 'contract' / 'app_metadata.py').write_text(
                'raise RuntimeError("contract broken for test")\n', encoding='utf-8')
            launcher = root / '启动漫剧制作助手.pyw'
            shutil.copy(LAUNCHER, launcher)
            wrapper = root / 'wrap.py'
            wrapper.write_text(textwrap.dedent('''
                import sys, types, ctypes, runpy
                class _User32:
                    def MessageBoxW(self, *args):
                        print('DIALOG_TITLE=' + str(args[2]))
                        print('DIALOG_TEXT_HEAD=' + str(args[1])[:120])
                        return 1
                ctypes.windll = types.SimpleNamespace(user32=_User32())
                runpy.run_path(sys.argv[1], run_name='__main__')
            '''), encoding='utf-8')
            done = subprocess.run(
                [sys.executable, '-X', 'utf8', '-B', str(wrapper), str(launcher)],
                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
            self.assertEqual(done.returncode, 0, done.stderr[-2000:])
            self.assertIn('DIALOG_TITLE=漫剧助手', done.stdout)
            log = root / '启动错误.log'
            self.assertTrue(log.is_file(), 'contract 损坏必须留下启动错误.log')
            content = log.read_text(encoding='utf-8', errors='replace')
            self.assertIn('未知', content)                     # 版本兜底
            self.assertIn('contract broken for test', content)  # 真实异常被记录

    def test_unwritable_startup_log_still_shows_dialog(self):
        """AUD-BOOT D2：启动错误.log 写不进（仓库根只读）时弹窗仍要出现。"""
        self.assertTrue(LAUNCHER.is_file(), '仓库根缺少 启动漫剧制作助手.pyw')
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            program = root / '程序'
            (program / 'contract').mkdir(parents=True)
            (program / 'hash_backend.py').write_text(
                'def install():\n    pass\n', encoding='utf-8')
            (program / 'contract' / '__init__.py').write_text('', encoding='utf-8')
            (program / 'contract' / 'app_metadata.py').write_text(
                'raise RuntimeError("contract broken for test")\n', encoding='utf-8')
            launcher = root / '启动漫剧制作助手.pyw'
            shutil.copy(LAUNCHER, launcher)
            log = root / '启动错误.log'
            log.write_text('previous failure\n', encoding='utf-8')
            os.chmod(log, 0o444)                     # 仓库根只读：write_text 必抛 OSError
            wrapper = root / 'wrap.py'
            wrapper.write_text(textwrap.dedent('''
                import sys, types, ctypes, runpy
                class _User32:
                    def MessageBoxW(self, *args):
                        print('DIALOG_TITLE=' + str(args[2]))
                        print('DIALOG_TEXT=' + str(args[1]))
                        return 1
                ctypes.windll = types.SimpleNamespace(user32=_User32())
                runpy.run_path(sys.argv[1], run_name='__main__')
            '''), encoding='utf-8')
            try:
                done = subprocess.run(
                    [sys.executable, '-X', 'utf8', '-B', str(wrapper), str(launcher)],
                    capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
            finally:
                os.chmod(log, 0o666)                 # 恢复可写，临时目录才能清掉
            self.assertEqual(done.returncode, 0, done.stderr[-2000:])
            self.assertIn('DIALOG_TITLE=漫剧助手', done.stdout)
            self.assertIn('[E-START-FAILED]', done.stdout)
            self.assertIn('日志没能保存', done.stdout)
            self.assertIn('contract broken for test', done.stdout)


class AppLogInstallFailureTests(unittest.TestCase):
    """AUD-BOOT D6：``app_logging.install`` 返回 False 时启动器必须记降级诊断并让状态栏可见。

    子进程跑真实 ``.pyw``，tkinter／desktop／诊断模块全部换成桩（不建真窗口、
    不碰真实 logs），只验证「install 返回 False → 降级诊断落账＋状态栏【警告】」接线。
    """

    def _run_launcher(self, install_plan):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / '程序').mkdir()                     # 启动器 os.chdir(program) 需要它存在
            launcher = root / '启动漫剧制作助手.pyw'
            shutil.copy(LAUNCHER, launcher)
            wrapper = root / 'wrap.py'
            wrapper.write_text(textwrap.dedent('''
                import sys, types, ctypes, runpy, json, os, importlib.util

                RESULTS = {'selfcheck_records': [], 'window_degraded': [],
                           'window_messages': [], 'bus': [], 'install_calls': 0}

                def _mod(name):
                    module = types.ModuleType(name)
                    sys.modules[name] = module
                    return module

                def _fn(ret):
                    class F:
                        def __call__(self, *a):
                            return ret
                    return F()

                # ctypes.windll 全替身：不建真互斥体、不弹真 MessageBox。
                kernel32 = types.SimpleNamespace(
                    CreateMutexW=_fn(1), GetLastError=_fn(0), CreateEventW=_fn(1),
                    SetEvent=_fn(1), WaitForSingleObject=_fn(0), CloseHandle=_fn(1))
                ctypes.windll = types.SimpleNamespace(
                    kernel32=kernel32, user32=types.SimpleNamespace(MessageBoxW=_fn(1)))

                program_dir = sys.argv[2]

                hash_backend = _mod('hash_backend')
                hash_backend.install = lambda: None

                app_logging = _mod('app_logging')
                app_logging.CALLS = 0
                plan = os.environ.get('FAKE_INSTALL_PLAN', 'F,F').split(',')
                def _install(root=None, crash_sink=None):
                    app_logging.CALLS += 1
                    RESULTS['install_calls'] += 1
                    ok = plan[min(app_logging.CALLS - 1, len(plan) - 1)] == 'T'
                    app_logging._install_error = None if ok else OSError('denied for test')
                    return ok
                app_logging.install = _install
                app_logging.redact = lambda value: str(value)
                app_logging.swallowed = lambda *a, **k: None

                contract_pkg = _mod('contract')
                contract_pkg.__path__ = []
                app_metadata = _mod('contract.app_metadata')
                app_metadata.APP_NAME = '漫剧助手'
                app_metadata.VERSION = 'unittest'
                contract_pkg.app_metadata = app_metadata

                def _load_real(name, path):
                    spec = importlib.util.spec_from_file_location(name, path)
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[name] = module
                    spec.loader.exec_module(module)
                    return module

                # contract.diagnostics 与 ui_status_bus 用真实源码（纯数据／纯总线，无副作用）。
                diagnostics = _load_real('contract.diagnostics',
                                         program_dir + '/contract/diagnostics.py')
                contract_pkg.diagnostics = diagnostics
                # EC-5B：状态栏逐项查 SELFCHECK_TO_CODE→error_codes.describe()，
                # 两张表同挂真实源码，否则 publish_startup_warnings 内 import 被吞、总线为空。
                contract_pkg.error_codes = _load_real(
                    'contract.error_codes', program_dir + '/contract/error_codes.py')
                contract_pkg.selfcheck = _load_real(
                    'contract.selfcheck', program_dir + '/contract/selfcheck.py')

                infra_pkg = _mod('infra')
                infra_pkg.__path__ = []
                infra_pkg.app_logging = app_logging
                sys.modules['infra.app_logging'] = app_logging
                infra_pkg.hash_backend = hash_backend
                sys.modules['infra.hash_backend'] = hash_backend

                diag_cap = _mod('infra.diagnostic_capture')
                diag_cap.run_startup_selfcheck = lambda program=None: []
                diag_cap.startup_gate = lambda ask=None: False
                diag_cap.startup_guard = lambda: 'proceed'
                diag_cap.record_startup_ready = lambda: None
                diag_cap.record_startup_closed = lambda: None
                diag_cap.record_crash = lambda exc, trace=None: None
                def _record_selfcheck(items):
                    RESULTS['selfcheck_records'].append(
                        [getattr(item, 'code', '') for item in (items or [])])
                diag_cap.record_selfcheck = _record_selfcheck
                diag_cap.notify_startup_fatal = lambda items: None
                infra_pkg.diagnostic_capture = diag_cap
                sys.modules['infra.diagnostic_capture'] = diag_cap

                app_icon = _mod('app_icon')
                app_icon.set_app_id = lambda: None
                app_icon.apply = lambda window: None

                # C 卡组合根在 .pyw 内绑定工具执行器；启动隔离桩不加载真实 UI 依赖树。
                ui_pkg = _mod('ui')
                ui_pkg.__path__ = []
                skill_tools = _mod('ui.skill_tools')
                skill_tools.install_executor = lambda: None
                ui_pkg.skill_tools = skill_tools

                ui_widgets = _mod('ui_widgets')
                ui_widgets.notify = lambda *a, **k: None
                # 对齐 R4427（UX-L5-DIALOGS）desktop_launcher.py 顶层导入所需桩。
                class _DialogStub:
                    pass
                ui_widgets.BaseDialog = _DialogStub
                ui_widgets.DescriptionBlock = _DialogStub
                ui_widgets.PrimaryButton = _DialogStub
                ui_widgets.SecondaryButton = _DialogStub
                ui_widgets.DIALOG_ACTION_GAP = 8
                ui_widgets.SPACING = {'none': 0}

                status_bus_mod = _load_real('ui_status_bus',
                                            program_dir + '/ui/ui_status_bus.py')

                desktop = _mod('desktop')
                class _Desktop:
                    # 复刻 desktop.py 状态栏播报：读 window._selfcheck_degraded 走 publish_startup_warnings。
                    def __init__(self, window, root=None, require_login=False, **kw):
                        degraded = list(getattr(window, '_selfcheck_degraded', None) or [])
                        RESULTS['window_degraded'] = [getattr(i, 'code', '') for i in degraded]
                        RESULTS['window_messages'] = [getattr(i, 'message', '') for i in degraded]
                        bus = status_bus_mod.StatusBus()
                        seen = []
                        bus.subscribe(lambda event: seen.append(event))
                        status_bus_mod.publish_startup_warnings(bus, degraded)
                        bus.pump()
                        RESULTS['bus'] = [message.text for kind, message, _prev in seen
                                          if kind == 'current' and message]
                desktop.Desktop = _Desktop

                tk = _mod('tkinter')
                class _Window:
                    def __init__(self):
                        self._selfcheck_degraded = None
                    def attributes(self, *a):
                        return None
                    def title(self, text):
                        pass
                    def after(self, ms, cb):
                        return 'tid'
                    def after_idle(self, cb):
                        return 'tid'
                    def after_cancel(self, tid):
                        pass
                    def update_idletasks(self):
                        pass
                    def lift(self):
                        pass
                    def focus_force(self):
                        pass
                    def deiconify(self):
                        pass
                    def grab_current(self):
                        return None
                    def wm_frame(self):
                        return ''
                    def winfo_screenwidth(self):
                        return 1920
                    def winfo_screenheight(self):
                        return 1080
                    def winfo_exists(self):
                        return True
                    def bind(self, *a, **k):
                        return ''
                    def unbind(self, *a, **k):
                        pass
                    def mainloop(self):
                        pass
                tk.Tk = _Window
                tk.TclError = Exception

                # REL-14：desktop_launcher 用真实源码；其依赖（infra.hash_backend、
                # tkinter、ui_widgets.notify 等）在上面已桩化，加载无副作用。
                _load_real('desktop_launcher', program_dir + '/desktop_launcher.py')
                runpy.run_path(sys.argv[1], run_name='__main__')
                print('RESULT_JSON=' + json.dumps(RESULTS, ensure_ascii=False))
            '''), encoding='utf-8')
            env = dict(os.environ, FAKE_INSTALL_PLAN=install_plan)
            return subprocess.run(
                [sys.executable, '-X', 'utf8', '-B', str(wrapper), str(launcher), str(HERE)],
                capture_output=True, text=True, encoding='utf-8', errors='replace',
                timeout=60, env=env)

    @staticmethod
    def _payload(done):
        line = next((row for row in done.stdout.splitlines()
                     if row.startswith('RESULT_JSON=')), '')
        assert line, ('桩进程未回传 RESULT_JSON；stdout 尾部：' + done.stdout[-800:]
                      + '；stderr 尾部：' + done.stderr[-800:])
        return json.loads(line.split('=', 1)[1])

    def test_install_false_records_degraded_and_status_warning(self):
        """两次 install 都失败：降级诊断落账、挂上 _selfcheck_degraded、状态栏出【警告】。"""
        done = self._run_launcher('F,F')
        self.assertEqual(done.returncode, 0, done.stderr[-2000:])
        results = self._payload(done)
        self.assertEqual(results['install_calls'], 2)
        recorded = [code for codes in results['selfcheck_records'] for code in codes]
        self.assertIn('app-log-unavailable', recorded)
        self.assertIn('app-log-unavailable', results['window_degraded'])
        self.assertTrue(any(text.startswith('【警告】') and describe('E-UNKNOWN') in text
                            for text in results['bus']),
                        '状态栏应有一条含 [E-UNKNOWN] 的【警告】：%r' % results['bus'])

    def test_install_retry_success_stays_silent(self):
        """第一次失败、建窗后重试成功：最终已生效，不算降级，不误报。"""
        done = self._run_launcher('F,T')
        self.assertEqual(done.returncode, 0, done.stderr[-2000:])
        results = self._payload(done)
        self.assertEqual(results['install_calls'], 2)
        recorded = [code for codes in results['selfcheck_records'] for code in codes]
        self.assertNotIn('app-log-unavailable', recorded)
        self.assertNotIn('app-log-unavailable', results['window_degraded'])
        self.assertFalse(any(text.startswith('【警告】启动自检：')
                             for text in results['bus']))


class FatalManufactureTests(unittest.TestCase):
    """D3-n④：甲类逐条「制造故障 → FATAL → 修复后自检放行」。

    三条甲类（Q6）：① 阶段契约撕裂；② 产物版本登记不自洽；③ 契约模块 import
    失败。③由启动器层兜底——BrokenContractSubprocessTests 已证坏包仍弹可操作
    诊断；「修复后能启动」由本类末尾对真实 程序 的零 FATAL 断言合证
    （完整 Tk 启动由 smoke／桌面测试覆盖，不在子进程内验收）。
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.program = Path(self.temp.name) / '程序'
        self.program.mkdir()
        _write_models(self.program, {'m1': {'model': 'm', 'label': 'm'}})
        self.state = Path(self.temp.name) / 'logs' / 'diagnostics' / 'latest.json'
        patcher = mock.patch.multiple(subject, PROGRAM=self.program,
                                      STATE_FILE=self.state)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _fatal_codes(self, items):
        return [item.code for item in items if item.severity is Severity.FATAL]

    def test_stage_contract_tear_fatal_then_recovers(self):
        from contract import stage_layout
        real = stage_layout.stage_contract_errors
        try:
            with mock.patch.object(stage_layout, 'stage_contract_errors',
                                   return_value=('阶段目录顺序与 pet_bus.STAGES 不一致',)):
                items = subject.run_startup_selfcheck(self.program)
                self.assertIn('stage-contract', self._fatal_codes(items))
            # 修复后：同一入口自检放行（启动器据此继续建 Tk）
            items = subject.run_startup_selfcheck(self.program)
            self.assertNotIn('stage-contract', self._fatal_codes(items))
        finally:
            stage_layout.stage_contract_errors = real

    def test_artifact_registry_inconsistency_fatal_then_recovers(self):
        from contract import artifact_schema
        with mock.patch.dict(artifact_schema.REGISTRY,
                             {'__manufactured__': {'version': 0, 'required': (), 'owner': 'x'}},
                             clear=False):
            items = subject.run_startup_selfcheck(self.program)
            self.assertIn('artifact-registry', self._fatal_codes(items))
        items = subject.run_startup_selfcheck(self.program)
        self.assertNotIn('artifact-registry', self._fatal_codes(items))

    def test_contract_import_failure_repair_shown_by_healthy_tree(self):
        """③的「修复后能启动」：契约完好时真实 程序 自检零 FATAL（启动器会继续建 Tk）。"""
        items = subject.run_startup_selfcheck(HERE)
        self.assertEqual(self._fatal_codes(items), [])


class FamilySwitchTests(unittest.TestCase):
    """§3c-3 族开关（GUI 等价物＝旗标文件）：``data/selfcheck_skip_<族>.flag``
    跳过该族检查并留一条 DEGRADED 诊断；``data/selfcheck_disable_<族>.flag``
    关闭该族告警（检查照跑、产出被抑制、完全静默）。每个开关只管一族。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.program = Path(self.temp.name) / '程序'
        self.program.mkdir()
        self.state = Path(self.temp.name) / 'logs' / 'diagnostics' / 'latest.json'
        patcher = mock.patch.multiple(subject, PROGRAM=self.program, LOGS=self.state.parent.parent,
                                      ERROR_LOG=self.state.parent.parent / 'e.log', STATE_FILE=self.state)
        patcher.start()
        self.addCleanup(patcher.stop)
        engine_probe = mock.patch.object(config_snapshot, 'has_usable_cli_engine', return_value=False)
        engine_probe.start()
        self.addCleanup(engine_probe.stop)
        _write_models(self.program, {'m1': {'model': 'm', 'label': 'm'}})

    def _run(self):
        return subject.run_startup_selfcheck(self.program)

    def _codes(self, items, severity=None):
        rows = [item for item in items if severity is None or item.severity is severity]
        return [item.code for item in rows]

    def _flag(self, name):
        data = self.program / 'data'
        data.mkdir(exist_ok=True)
        (data / name).write_text('', encoding='utf-8')

    @staticmethod
    def _low_disk():
        return SimpleNamespace(free=100 * 1048576, total=1, used=0)

    def _empty_pool_and_low_disk(self):
        _write_models(self.program)                      # 不写 models 键 → 空池
        return mock.patch('shutil.disk_usage', return_value=self._low_disk())

    def test_skip_flag_skips_only_its_family_and_records_diagnostic(self):
        with self._empty_pool_and_low_disk():
            baseline = self._run()
            self.assertIn('model-pool-empty', self._codes(baseline))
            self.assertIn('disk-space-low', self._codes(baseline))
            self._flag('selfcheck_skip_disk_space.flag')
            items = self._run()
        codes = self._codes(items)
        self.assertNotIn('disk-space-low', codes)
        self.assertIn('model-pool-empty', codes)
        skip = [item for item in items if item.code == 'selfcheck-skip-disk-space']
        self.assertEqual(len(skip), 1)
        self.assertIs(skip[0].severity, Severity.DEGRADED)
        self.assertIn('disk_space', skip[0].message)
        self.assertIn('selfcheck_skip_disk_space.flag', skip[0].message)

    def test_disable_flag_silences_only_its_family(self):
        with self._empty_pool_and_low_disk():
            self._flag('selfcheck_disable_model_pool.flag')
            items = self._run()
        codes = self._codes(items)
        self.assertNotIn('model-pool-empty', codes)
        self.assertIn('disk-space-low', codes)
        self.assertFalse([item for item in items if 'selfcheck-skip' in str(item.code)])

    def test_disable_still_runs_check_but_discards_output(self):
        _write_models(self.program)
        with mock.patch.object(subject, '_check_model_pool',
                               wraps=subject._check_model_pool) as spy:
            self._flag('selfcheck_disable_model_pool.flag')
            items = self._run()
            spy.assert_called()
        self.assertNotIn('model-pool-empty', self._codes(items))

    def test_skip_does_not_execute_the_check(self):
        with mock.patch.object(subject, '_check_disk_space') as spy:
            self._flag('selfcheck_skip_disk_space.flag')
            items = self._run()
            spy.assert_not_called()
        self.assertIn('selfcheck-skip-disk-space', self._codes(items))

    def test_disable_swallows_check_error_silently(self):
        with mock.patch.object(subject, '_check_model_pool',
                               side_effect=RuntimeError('boom')):
            self._flag('selfcheck_disable_model_pool.flag')
            items = self._run()
        self.assertFalse([item for item in items
                          if item.code in ('check-error', 'model-pool-empty')])

    def test_no_flags_preserves_current_behavior(self):
        with self._empty_pool_and_low_disk():
            items = self._run()
        codes = self._codes(items)
        self.assertIn('model-pool-empty', codes)
        self.assertIn('disk-space-low', codes)
        self.assertFalse([item for item in items if 'selfcheck-skip' in str(item.code)])

    def test_family_flags_do_not_affect_fatal_or_global_failopen(self):
        with mock.patch('contract.stage_layout.stage_contract_errors',
                        return_value=('阶段目录顺序与 pet_bus.STAGES 不一致',)):
            self._flag('selfcheck_skip_stage_contract.flag')
            self._flag('selfcheck_disable_contract.flag')
            items = self._run()
            self.assertIn('stage-contract', self._codes(items, Severity.FATAL))
            self._flag('selfcheck_failopen.flag')
            items = self._run()
            self.assertNotIn('stage-contract', self._codes(items, Severity.FATAL))
            downgraded = [item for item in items if item.code == 'stage-contract']
            self.assertEqual(len(downgraded), 1)
            self.assertIs(downgraded[0].severity, Severity.DEGRADED)
            self.assertIn('selfcheck_failopen', downgraded[0].escape_hint)

    def test_unknown_family_flag_is_inert(self):
        self._flag('selfcheck_skip_nonexistent.flag')
        self._flag('selfcheck_disable_nonexistent.flag')
        items = self._run()
        self.assertFalse([item for item in items if 'selfcheck-skip' in str(item.code)])
        _write_models(self.program)
        items = self._run()
        self.assertIn('model-pool-empty', self._codes(items))

    def test_flags_honored_on_safe_start_entry(self):
        _write_models(self.program)
        self._flag('selfcheck_disable_model_pool.flag')
        items = subject.run_startup_selfcheck(self.program)
        self.assertNotIn('model-pool-empty', self._codes(items))


if __name__ == '__main__':
    unittest.main()
