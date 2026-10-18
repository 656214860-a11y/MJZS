# -*- coding: utf-8 -*-
"""后台自动全量：钩子里起的子进程不得继承 git 导出的 GIT_* 变量，未到触发点或已有任务时不起进程。"""
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM))
spec = importlib.util.spec_from_file_location('auto_full_safe_for_tests', PROGRAM / 'scripts' / 'auto_full_safe.py')
auto = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auto)


class AutoFullSafeTests(unittest.TestCase):
    def test_spawn_strips_git_environment(self):
        with mock.patch.object(auto, 'status', return_value={'auto_due': True}), \
             mock.patch.object(auto, '_already_running', return_value=False), \
             mock.patch.object(auto, '_waiter_running', return_value=False), \
             mock.patch.dict(os.environ, {'GIT_INDEX_FILE': 'x', 'GIT_DIR': 'y', 'KEEP_ME': '1'}), \
             mock.patch.object(auto.subprocess, 'Popen') as popen:
            self.assertEqual(auto.spawn(), 0)
        env = popen.call_args.kwargs['env']
        self.assertFalse([key for key in env if key.startswith('GIT_')])
        self.assertEqual(env.get('KEEP_ME'), '1')

    def test_spawn_does_nothing_when_not_due_or_already_running(self):
        for due, running in ((False, False), (True, True)):
            with self.subTest(due=due, running=running), \
                 mock.patch.object(auto, 'status', return_value={'auto_due': due}), \
                 mock.patch.object(auto, '_already_running', return_value=running), \
                 mock.patch.object(auto, '_waiter_running', return_value=False), \
                 mock.patch.object(auto.subprocess, 'Popen') as popen:
                self.assertEqual(auto.spawn(), 0)
                popen.assert_not_called()

    def test_hook_entry_swallows_errors(self):
        with mock.patch.object(auto, 'spawn', side_effect=RuntimeError('boom')):
            self.assertEqual(auto.main(['--spawn']), 0)


class DebounceTests(unittest.TestCase):
    def test_decision_waits_for_quiet_unless_the_gate_would_already_be_red(self):
        quiet, longest = auto.QUIET_SECONDS, auto.MAX_WAIT_SECONDS
        due = {'auto_due': True, 'required': False}
        self.assertEqual(auto.decide({'auto_due': False}, 0, 0), 'stop')
        self.assertEqual(auto.decide(due, quiet - 1, 0), 'wait', '刚有提交：继续等')
        self.assertEqual(auto.decide(due, quiet, 0), 'run', '安静够久：跑')
        self.assertEqual(auto.decide(due, 0, longest), 'run', '等太久：跑')
        self.assertEqual(auto.decide({'auto_due': True, 'required': True}, 0, 0), 'run', '门禁已红：不等')

    def test_wait_run_polls_until_quiet_then_runs_once_and_clears_its_lock(self):
        ages = iter([10, 20, auto.QUIET_SECONDS + 1])
        sleeps = []
        with tempfile.TemporaryDirectory() as folder:
            lock = Path(folder) / auto.WAITER_LOCK_NAME
            with mock.patch.object(auto, '_waiter_lock_path', return_value=lock),                  mock.patch.object(auto, '_waiter_running', return_value=False),                  mock.patch.object(auto, 'status', return_value={'auto_due': True, 'required': False}),                  mock.patch.object(auto, '_last_commit_age', side_effect=lambda: next(ages)),                  mock.patch.object(auto, 'run', return_value=0) as run:
                self.assertEqual(auto.wait_run(sleep=sleeps.append, clock=lambda: 0), 0)
            run.assert_called_once()
            self.assertEqual(len(sleeps), 2)
            self.assertFalse(lock.exists())

    def test_a_second_waiter_is_not_started(self):
        with mock.patch.object(auto, 'status', return_value={'auto_due': True}),              mock.patch.object(auto, '_already_running', return_value=False),              mock.patch.object(auto, '_waiter_running', return_value=True),              mock.patch.object(auto.subprocess, 'Popen') as popen:
            self.assertEqual(auto.spawn(), 0)
        popen.assert_not_called()


class EmbeddedRepoAlignTests(unittest.TestCase):
    def test_a_stale_embedded_copy_is_realigned_to_the_registered_commit(self):
        calls = []
        def fake_git(*args, cwd=None):
            calls.append(args)
            return 'old-sha' if args[:2] == ('rev-parse', 'HEAD') else ''
        with mock.patch.object(auto, '_git', side_effect=fake_git):
            auto._align_embedded_repo(Path('dest'), Path('src'), 'new-sha')
        self.assertIn(('checkout', '-f', '--detach', 'new-sha'), calls)
        self.assertTrue(any(call[:2] == ('fetch', '--quiet') for call in calls))

    def test_an_up_to_date_embedded_copy_is_left_alone(self):
        calls = []
        def fake_git(*args, cwd=None):
            calls.append(args)
            return 'same-sha'
        with mock.patch.object(auto, '_git', side_effect=fake_git):
            auto._align_embedded_repo(Path('dest'), Path('src'), 'same-sha')
        self.assertEqual(calls, [('rev-parse', 'HEAD')])


class FailureNoticeTests(unittest.TestCase):
    def test_red_modules_are_read_from_the_log_in_order_without_duplicates(self):
        log = '### test_core（1 条红）\n\nx\n### test_asset_gating（2 条红）\n### test_core（3 条红）\n'
        self.assertEqual(auto.red_modules(log), ['test_core', 'test_asset_gating'])

    def test_notice_only_for_a_failed_last_run(self):
        failed = {'head': 'abcdef1234', 'returncode': 1, 'finished_at': 't', 'red': ['test_core'], 'log': 'L'}
        with mock.patch.object(auto, 'last_result', return_value=failed), \
             mock.patch.object(auto, 'LOG', Path('不存在的日志')):
            text = auto.failure_notice()
        self.assertIn('abcdef1', text)
        self.assertIn('test_core', text)
        for result in ({}, {'returncode': 0}):
            with mock.patch.object(auto, 'last_result', return_value=result):
                self.assertEqual(auto.failure_notice(), '')

    def test_notice_flag_prints_and_never_fails(self):
        with mock.patch.object(auto, 'failure_notice', return_value='boom-text'), \
             mock.patch('builtins.print') as shown:
            self.assertEqual(auto.main(['--notice']), 0)
        shown.assert_called_once_with('boom-text')
        with mock.patch.object(auto, 'failure_notice', side_effect=RuntimeError('x')):
            self.assertEqual(auto.main(['--notice']), 0)


BROKEN = ('concurrent.futures.process.BrokenProcessPool: A child process terminated abruptly, '
          'the process pool is not usable anymore\n')


class EnvironmentBlockedTests(unittest.TestCase):
    """R1693：沙箱会话里提交时钩子继承同一限制，全量必崩在进程池上。

    这类失败不是测试红：不能记「未通过」，也不能白跑 78 秒再假装一次全量。
    """

    def test_probe_reports_a_working_pool_as_clean(self):
        self.assertEqual(auto.spawn_problem(), '')

    def test_probe_failure_becomes_a_reason_instead_of_an_exception(self):
        def boom():
            raise RuntimeError('无法派生工作进程')
        reason = auto.spawn_problem(run=boom)
        self.assertIn('RuntimeError', reason)
        self.assertIn('无法派生工作进程', reason)

    def test_blocked_signatures_are_recognised(self):
        self.assertEqual(auto.blocked_reason(BROKEN), 'BrokenProcessPool')
        self.assertEqual(auto.blocked_reason('all green'), '')

    def test_blocked_run_is_not_announced_as_a_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / 'auto.log'
            log.write_text('[自动全量] 环境不允许派生工作进程，本轮未测\n' + BROKEN, encoding='utf-8')
            result = Path(folder) / 'result.json'
            with mock.patch.object(auto, 'LOG', log), \
                 mock.patch.object(auto, '_result_path', return_value=result):
                auto.write_result('abcdef1234', auto.BLOCKED_CODE, 0.0, blocked='BrokenProcessPool')
                text = auto.failure_notice()
        self.assertIn('环境不允许派生工作进程', text)
        self.assertIn('不是测试失败', text)
        self.assertNotIn('未通过', text)

    def test_an_old_fake_red_is_reclassified_from_its_log(self):
        """历史结果没有 blocked 字段，只能靠日志特征把它从「未通过」里摘出来。"""
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / 'auto.log'
            log.write_text(BROKEN, encoding='utf-8')
            result = Path(folder) / 'result.json'
            with mock.patch.object(auto, 'LOG', log), \
                 mock.patch.object(auto, '_result_path', return_value=result):
                auto.write_result('abcdef1234', 1, 78.0)
                text = auto.failure_notice()
        self.assertIn('不是测试失败', text)

    def test_a_real_red_still_names_the_modules(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / 'auto.log'
            log.write_text('### test_alpha（1 条红）\n', encoding='utf-8')
            result = Path(folder) / 'result.json'
            with mock.patch.object(auto, 'LOG', log), \
                 mock.patch.object(auto, '_result_path', return_value=result):
                auto.write_result('abcdef1234', 1, 700.0)
                text = auto.failure_notice()
        self.assertIn('未通过', text)
        self.assertIn('test_alpha', text)


class CleanWorktreeTests(unittest.TestCase):
    """R1693：半成品检出（缺 程序/run_selftests.py）不能直接拿去跑。"""

    def make_root(self, folder, complete):
        root = Path(folder)
        target = root / '.wt' / 'ci'
        (target / '程序').mkdir(parents=True)
        (target / '.git').write_text('gitdir: x\n', encoding='utf-8')
        if complete:
            (target / '程序' / 'run_selftests.py').write_text('# x\n', encoding='utf-8')
        return root, target

    def test_a_complete_checkout_is_realigned_in_place(self):
        calls = []
        with tempfile.TemporaryDirectory() as folder:
            root, target = self.make_root(folder, complete=True)
            with mock.patch.object(auto, '_git', side_effect=lambda *a, cwd=None: calls.append(a) or ''), \
                 mock.patch.object(auto, '_fill_embedded_repos'), \
                 mock.patch.object(auto, '_lock_worktree') as lock:
                program = auto._sync_clean_worktree(root, 'head-sha')
            self.assertEqual(program, target / '程序')
            lock.assert_called_once()
        self.assertIn(('checkout', '-f', '--detach', 'head-sha'), calls)
        self.assertNotIn('worktree', [call[0] for call in calls if len(call) > 1 and call[0] == 'add'], )

    def test_an_incomplete_checkout_is_rebuilt_once_then_verified(self):
        calls = []
        with tempfile.TemporaryDirectory() as folder:
            root, target = self.make_root(folder, complete=False)
            with mock.patch.object(auto, '_git', side_effect=lambda *a, cwd=None: calls.append(a) or ''), \
                 mock.patch.object(auto, '_fill_embedded_repos'), \
                 mock.patch.object(auto, '_lock_worktree'):
                with self.assertRaises(RuntimeError):
                    auto._sync_clean_worktree(root, 'head-sha')
        flattened = [' '.join(call) for call in calls]
        self.assertTrue(any('worktree remove' in item for item in flattened), flattened)
        self.assertTrue(any(item.startswith('worktree add') for item in flattened), flattened)

    def test_the_worktree_is_locked_so_repo_hygiene_cannot_recycle_it(self):
        calls = []
        with mock.patch.object(auto, '_git', side_effect=lambda *a, cwd=None: calls.append(a) or ''):
            auto._lock_worktree(Path('.wt/ci'))
        self.assertIn('lock', calls[0])


class ScanIsolationTests(unittest.TestCase):
    """R1693：`.wt/ci` 常驻后，扫描口径必须把它当检出副本，不能算第二批生产模块。"""

    def test_the_ci_worktree_is_excluded_from_production_scans(self):
        from tests.architecture import _scan
        self.assertIn('.wt', _scan.EXCLUDED_PARTS)
        self.assertIn('.selftmp', _scan.EXCLUDED_PARTS, '自检临时区里的探针不是产品模块')
        tool_spec = importlib.util.spec_from_file_location(
            'coverage_report_for_tests', PROGRAM / 'scripts' / 'coverage_report.py')
        tool = importlib.util.module_from_spec(tool_spec)
        tool_spec.loader.exec_module(tool)
        self.assertIn('.wt', tool.EXCLUDED_PARTS)
        self.assertIn('.selftmp', tool.EXCLUDED_PARTS)

    def test_a_worktree_copy_is_not_reported_as_a_second_module(self):
        from tests.architecture import _scan
        names = [path.relative_to(_scan.ROOT).as_posix() for path in _scan.production_runtime_files()]
        self.assertFalse([name for name in names if name.startswith(('.wt/', '.selftmp/'))], names[:5])


if __name__ == '__main__':
    unittest.main()
