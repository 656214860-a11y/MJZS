# -*- coding: utf-8 -*-
"""L1 任务书轮 6（R3331）：对接 L0——自检检查项注入、model_router 判类收敛、降级记录错误码。"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import diagnostic_capture as subject
import infra.request_ledger as request_ledger
import infra.temporary_sweep as temporary_sweep
from contract.diagnostics import Severity
from contract import error_codes


class ErrorClassConvergenceTests(unittest.TestCase):
    """R6-b：model_router.error_class 收敛到 error_codes.classify，HTTP 状态优先。"""

    def test_status_drives_classification_before_text(self):
        from infra.model_router import error_class
        # 状态码参与判定：503 → E-NET-SERVER → transport；文本为空也成立
        self.assertEqual(error_class('', status=503), 'transport')
        self.assertEqual(error_class('whatever', status=401), 'authentication')
        self.assertEqual(error_class('', status=429), 'transport')

    def test_text_fallback_without_status(self):
        from infra.model_router import error_class
        self.assertEqual(error_class('连接超时'), 'timeout')
        self.assertEqual(error_class('ValueError：DeepSeek 缺少 API Key'), 'authentication')
        self.assertEqual(error_class('HTTP 400 bad request'), 'protocol')
        self.assertEqual(error_class('余额不足请充值'), 'configuration')
        self.assertEqual(error_class('完全无法理解的错误'), 'transport')

    def test_local_substring_table_is_gone(self):
        """旧子串表特征不再生效：'协议'/'payload'/'404' 等旧关键词不再单独决定类别。"""
        from infra.model_router import error_class
        # 旧表把 '/chat/completions'/'404' 判 protocol；classify 对 404 无命中 → E-UNKNOWN → transport
        self.assertEqual(error_class('HTTP 404 /chat/completions'), 'transport')

    def test_chat_result_passes_http_status(self):
        """chat() 失败结果把 result.status 传给 error_class：401 空文本也能判出鉴权类。"""
        from infra.model_router import ModelAdapter

        class _Adapter(ModelAdapter):
            provider = 'Test'
            key_env = 'TEST_KEY'
            base_url = 'https://example.invalid/v1'
            models = {'test-model': {}}

            def headers(self):
                return {}

        def transport(*_args):
            return {'ok': False, 'status': 401, 'error': '', 'data': None}
        result = _Adapter(transport=transport, key='sk-test').chat([], model='test-model')
        self.assertFalse(result['ok'])
        self.assertEqual(result['error_class'], 'authentication')


class DegradationErrorCodeTests(unittest.TestCase):
    """R6-c：降级记录带 L0 错误码。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.logs = root / "logs"
        self.state = self.logs / "diagnostics" / "latest.json"
        self.patch = patch.multiple(subject, PROGRAM=root, LOGS=self.logs,
                                    ERROR_LOG=self.logs / "启动错误.log", STATE_FILE=self.state)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.addCleanup(self.temp.cleanup)

    def test_record_degradation_stores_code(self):
        subject.record_degradation(OSError('disk full'), stage='request-ledger', error_code='E-IO-WRITE')
        state = json.loads(self.state.read_text(encoding='utf-8'))
        row = state['degradations'][-1]
        self.assertEqual(row['code'], 'E-IO-WRITE')

    def test_record_degradation_code_defaults_empty(self):
        subject.record_degradation(RuntimeError('x'), page='p')
        state = json.loads(self.state.read_text(encoding='utf-8'))
        self.assertEqual(state['degradations'][-1]['code'], '')


class StartupCheckProviderTests(unittest.TestCase):
    """R6-a：四项 L1 检查函数返回 Diagnostic(DEGRADED) 或 None，且不扫描目录。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.program = self.root / '程序'
        self.program.mkdir()
        self.project = self.root / '项目A'
        self.project.mkdir()
        (self.program / 'projects.json').write_text(
            json.dumps({'active': str(self.project), 'projects': [{'path': str(self.project)}]},
                       ensure_ascii=False), encoding='utf-8')
        self.logs = self.root / 'logs'
        self.state = self.logs / 'diagnostics' / 'latest.json'
        self.patch = patch.multiple(subject, PROGRAM=self.program, LOGS=self.logs,
                                    ERROR_LOG=self.logs / '启动错误.log', STATE_FILE=self.state)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.addCleanup(self.temp.cleanup)

    def _ledger(self, entries):
        path = request_ledger.request_ledger_path(self.project)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'entries': entries}, ensure_ascii=False), encoding='utf-8')
        return path

    def test_ledger_corrupt_reports_degraded(self):
        path = self._ledger([])
        path.write_text('{broken json', encoding='utf-8')
        item = subject._check_request_ledger(self.program)
        self.assertIsNotNone(item)
        self.assertEqual(item.severity, Severity.DEGRADED)
        self.assertEqual(item.code, 'request-ledger-corrupt')

    def test_ledger_healthy_returns_none(self):
        self._ledger([{'id': 'r1', 'state': 'settled'}])
        self.assertIsNone(subject._check_request_ledger(self.program))

    def test_unknown_stale_over_threshold_reports(self):
        entries = [{'id': 'r%d' % i, 'state': 'unknown', 'unknown_via': 'stale-reserved'}
                   for i in range(subject._LEDGER_UNKNOWN_STALE_LIMIT + 1)]
        entries.append({'id': 'normal', 'state': 'unknown'})   # 无标记不计
        self._ledger(entries)
        item = subject._check_ledger_unknown_stale(self.program)
        self.assertIsNotNone(item)
        self.assertEqual(item.severity, Severity.DEGRADED)
        self.assertEqual(item.code, 'request-ledger-unknown-stale')

    def test_unknown_stale_under_threshold_returns_none(self):
        self._ledger([{'id': 'r1', 'state': 'unknown', 'unknown_via': 'stale-reserved'}])
        self.assertIsNone(subject._check_ledger_unknown_stale(self.program))

    def test_ui_settings_corrupt_sidecar_reports(self):
        (self.project / 'ui_settings.json.corrupt').write_text('{}', encoding='utf-8')
        item = subject._check_ui_settings_corrupt(self.program)
        self.assertIsNotNone(item)
        self.assertEqual(item.severity, Severity.DEGRADED)
        self.assertEqual(item.code, 'ui-settings-corrupt')
        (self.project / 'ui_settings.json.corrupt').unlink()
        self.assertIsNone(subject._check_ui_settings_corrupt(self.program))

    def test_temporary_leftovers_from_recorded_sweep(self):
        subject.record_temporary_sweep(removed=3, remaining=subject._TEMP_LEFTOVER_LIMIT + 1)
        item = subject._check_temporary_leftovers(self.program)
        self.assertIsNotNone(item)
        self.assertEqual(item.severity, Severity.DEGRADED)
        self.assertEqual(item.code, 'temporary-files-leftover')

    def test_temporary_leftovers_under_threshold_and_missing_record(self):
        subject.record_temporary_sweep(removed=3, remaining=1)
        self.assertIsNone(subject._check_temporary_leftovers(self.program))
        # 换一个没有记录的 STATE_FILE：无从确认 → None
        empty_state = self.root / 'other-state.json'
        with patch.object(subject, 'STATE_FILE', empty_state):
            self.assertIsNone(subject._check_temporary_leftovers(self.program))

    def test_checks_do_not_scan_directories(self):
        with patch.object(Path, 'rglob', side_effect=AssertionError('不得递归扫描')), \
             patch.object(Path, 'iterdir', side_effect=AssertionError('不得枚举目录')):
            for check in (subject._check_request_ledger, subject._check_ledger_unknown_stale,
                          subject._check_ui_settings_corrupt, subject._check_temporary_leftovers):
                check(self.program)

    def test_startup_checks_includes_l1_items(self):
        checks = subject.startup_checks(self.program)
        self.assertEqual(len(checks), 10)   # 乙类六项＋L1 四项


class SweepStatsTests(unittest.TestCase):
    """轮 2 清扫：stats 回填 remaining，供自检读取。"""

    def test_remaining_counts_undeleted_stale_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stale = root / ('a.' + '0' * 32 + '.tmp')
            stale.write_text('x', encoding='utf-8')
            old = stale.stat().st_mtime - temporary_sweep.TEMP_SWEEP_MAX_AGE_SECONDS - 10
            import os
            os.utime(stale, (old, old))
            stats = {}
            removed = temporary_sweep.sweep_stale_temporary_files(root, stats=stats)
            self.assertEqual(removed, 1)
            self.assertEqual(stats['remaining'], 0)

    def test_remaining_counts_files_that_survive_removal(self):
        """remove_temporary_file 删不掉（如被占用）时计入 remaining，不误报已删。"""
        import os
        import infra.file_cache as file_cache
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stuck = root / ('b.' + '1' * 32 + '.tmp')
            stuck.write_text('x', encoding='utf-8')
            old = stuck.stat().st_mtime - temporary_sweep.TEMP_SWEEP_MAX_AGE_SECONDS - 10
            os.utime(stuck, (old, old))
            original = file_cache.remove_temporary_file

            def flaky(path):
                if Path(path).name.startswith('b.'):
                    return False
                return original(path)

            stats = {}
            with patch.object(file_cache, 'remove_temporary_file', side_effect=flaky):
                removed = temporary_sweep.sweep_stale_temporary_files(root, stats=stats)
            self.assertEqual(removed, 0)
            self.assertEqual(stats['remaining'], 1)
            self.assertTrue(stuck.exists())

    def test_schedule_worker_swallows_record_failure(self):
        """写回诊断状态失败不影响清扫线程本身（降级绝不反噬主流程）。"""
        import threading
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            done = threading.Event()

            def boom(*_args, **_kwargs):
                done.set()
                raise RuntimeError('state 写失败')

            with patch.object(subject, 'record_temporary_sweep', side_effect=boom):
                temporary_sweep.schedule_stale_temporary_sweep(root)
                self.assertTrue(done.wait(10), '清扫 worker 未在期限内尝试写回')
            # worker 是守护线程：记录失败被吞掉，不向调用方传播

    def test_schedule_worker_real_sweep_writes_record(self):
        """真清扫（非 mock）跑完后，诊断状态里留下 temporary_sweep 记录供自检读取。"""
        import os
        import threading
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            doomed = root / ('c.' + '2' * 32 + '.tmp')
            doomed.write_text('x', encoding='utf-8')
            old = doomed.stat().st_mtime - temporary_sweep.TEMP_SWEEP_MAX_AGE_SECONDS - 10
            os.utime(doomed, (old, old))
            state = root / 'diag-state.json'
            done = threading.Event()
            original = subject.record_temporary_sweep

            def spy(removed, remaining):
                result = original(removed, remaining)
                done.set()
                return result

            with patch.object(subject, 'STATE_FILE', state), \
                 patch.object(subject, 'record_temporary_sweep', side_effect=spy):
                temporary_sweep.schedule_stale_temporary_sweep(root)
                self.assertTrue(done.wait(10), '清扫 worker 未在期限内写回结果')
            data = json.loads(state.read_text(encoding='utf-8'))
            self.assertEqual(data['temporary_sweep']['removed'], 1)
            self.assertEqual(data['temporary_sweep']['remaining'], 0)

    def test_schedule_worker_records_sweep_result(self):
        """schedule 的 worker 跑完 sweep 会把 (removed, remaining) 写进诊断状态。"""
        import threading
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            done = threading.Event()
            seen = []
            def fake_sweep(target, *, now=None, max_age_seconds=None, stats=None):
                if stats is not None:
                    stats['remaining'] = 7
                return 2
            def spy(removed, remaining):
                seen.append((removed, remaining))
                done.set()
            state = root / 'state.json'
            with patch.object(temporary_sweep, 'sweep_stale_temporary_files', side_effect=fake_sweep), \
                 patch.object(subject, 'STATE_FILE', state), \
                 patch.object(subject, 'record_temporary_sweep', side_effect=spy):
                temporary_sweep.schedule_stale_temporary_sweep(root)
                self.assertTrue(done.wait(10), '清扫 worker 未在期限内写回结果')
            self.assertEqual(seen, [(2, 7)])


class LedgerUnknownViaTests(unittest.TestCase):
    """request_ledger 两处 reserved→unknown 转换打 unknown_via 标记。"""

    def test_stale_reserved_sweep_marks_via(self):
        ledger = request_ledger.RequestLedger(project=None, clock=lambda: 100000.0)
        entry = ledger.reserve('r1', 'requests', 1, at=0)
        # 直接走模块函数：state reserved 且超时 → unknown + unknown_via
        request_ledger._sweep_stale_reserved(ledger.entries, lambda: 100000.0 + request_ledger.REQUEST_RESERVED_STALE_SECONDS + 1)
        self.assertEqual(entry['state'], 'unknown')
        self.assertEqual(entry.get('unknown_via'), 'stale-reserved')

    def test_settle_lock_timeout_marks_via(self):
        ledger = request_ledger.RequestLedger(project=None, clock=lambda: 1.0)
        ledger.reserve('r2', 'requests', 1)
        entry = ledger._find('r2')
        exc = request_ledger.LedgerLockTimeout('busy')
        request_ledger._settle_lock_timeout(ledger, 'r2', exc)
        self.assertEqual(entry['state'], 'unknown')
        self.assertEqual(entry.get('unknown_via'), 'settle-lock-timeout')


if __name__ == '__main__':
    unittest.main()
