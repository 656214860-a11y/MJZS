# -*- coding: utf-8 -*-
"""轮 3B 启动自检接线：run_startup_selfcheck 组装、乙类检查、G12 开关、
崩溃预算账本、DEGRADED 状态栏出口与启动器保护（任务书 D3-g～D3-n）。"""
from __future__ import annotations

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

import infra.diagnostic_capture as subject
from contract.diagnostics import Diagnostic, Severity, StartupPhase
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
        items = self._run()
        hit = [item for item in items if item.code == 'model-pool-empty']
        self.assertEqual(len(hit), 1)
        self.assertIs(hit[0].severity, Severity.DEGRADED)
        self.assertEqual(hit[0].scope, StartupPhase.CONFIG.value)

    def test_configured_model_pool_has_no_empty_warning(self):
        self.assertNotIn('model-pool-empty', self._codes(self._run()))

    def test_missing_model_config_is_an_empty_pool(self):
        (self.program / '配置' / '宠物' / '配置.json').unlink()
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
        self.assertIn('disk-space-low', text)
        self.assertIn('model-pool-empty', text)
        self.assertEqual(messages[0].level, 'warning')

    def test_same_code_is_announced_once_per_launch(self):
        messages = self._announce([self._diag('disk-space-low', '第一次'),
                                   self._diag('disk-space-low', '重复')])
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].text.count('disk-space-low'), 1)

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
        budget_at = self.source.index('startup_gate(')
        self.assertLess(exit_at, budget_at,
                        '单实例二次启动必须在崩溃预算之前退出（不计数不清零）')

    def test_selfcheck_runs_before_tk_construction(self):
        check_at = self.source.index('run_startup_selfcheck(')
        tk_at = self.source.index('tk.Tk()')
        self.assertLess(check_at, tk_at, '自检必须在建 Tk 之前运行')

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
            self.assertIn('日志没能保存', done.stdout)
            self.assertIn('contract broken for test', done.stdout)


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
