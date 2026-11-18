# -*- coding: utf-8 -*-
"""后台自动全量：钩子里的欠账判断和起的子进程都不受 git 导出的 GIT_* 变量影响，未到触发点或已有任务时不起进程。"""
import importlib.util
import json
import os
import subprocess
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

    def test_hook_environment_does_not_shrink_the_repository_to_the_program_folder(self):
        # .git 是 gitfile 时，git 给钩子导出绝对 GIT_DIR 而不带 GIT_WORK_TREE；欠账若在这个环境里于「程序」
        # 目录调 git，仓库顶层会被当成「程序」本身：前缀算空、源码轮次算 0，提交后永远不派生后台全量。
        with tempfile.TemporaryDirectory() as folder:
            top, meta = Path(folder) / 'top', Path(folder) / 'meta.git'
            clean = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
            subprocess.run(['git', 'init', '-q', '--separate-git-dir', str(meta), str(top)],
                           check=True, env=clean, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            (top / '程序').mkdir()
            seen = []
            with mock.patch.dict(os.environ, {'GIT_DIR': str(meta), 'GIT_INDEX_FILE': str(meta / 'index')}), \
                 mock.patch.object(auto, 'status', side_effect=lambda: seen.append(dict(os.environ)) or {'auto_due': True}), \
                 mock.patch.object(auto, '_already_running', return_value=False), \
                 mock.patch.object(auto, '_waiter_running', return_value=False), \
                 mock.patch.object(auto.subprocess, 'Popen') as popen:
                self.assertEqual(auto.main(['--spawn']), 0)
                self.assertEqual(os.environ.get('GIT_DIR'), str(meta), '进程内调用返回后环境原样还原')
            popen.assert_called_once()
            toplevel = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], cwd=top / '程序',
                                               env=seen[0], text=True).strip()
            self.assertTrue(os.path.samefile(toplevel, top), '欠账判断看到的仓库顶层是 %s' % toplevel)

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


class RedCooldownTests(unittest.TestCase):
    NOW = 1_800_000_000.0

    def result(self, head='aaa', code=1, age=60.0):
        import time
        finished = time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(self.NOW - age))
        return {'head': head, 'returncode': code, 'finished_at': finished}

    def test_same_head_that_already_went_red_is_not_rerun(self):
        long_ago = auto.RED_COOLDOWN_SECONDS * 5
        self.assertEqual(auto.red_cooldown(self.result('aaa', age=long_ago), 'aaa', self.NOW), 'head')

    def test_a_new_head_waits_out_the_cooldown_then_is_allowed(self):
        inside = auto.RED_COOLDOWN_SECONDS - 60
        self.assertEqual(auto.red_cooldown(self.result('aaa', age=inside), 'bbb', self.NOW), 'time')
        outside = auto.RED_COOLDOWN_SECONDS + 60
        self.assertEqual(auto.red_cooldown(self.result('aaa', age=outside), 'bbb', self.NOW), '')

    def test_green_blocked_or_missing_results_never_cool_down(self):
        for result in ({}, self.result(code=0), self.result(code=auto.BLOCKED_CODE)):
            with self.subTest(result=result):
                self.assertEqual(auto.red_cooldown(result, 'aaa', self.NOW), '')

    def test_unreadable_timestamp_does_not_block_a_rerun(self):
        self.assertEqual(auto.red_cooldown({'head': 'a', 'returncode': 1, 'finished_at': '??'}, 'b', self.NOW), '')

    def status_with(self, last, required):
        with mock.patch.object(auto.run_selftests, 'load_layer_document', return_value={'last_full_safe_all_round': 1}),              mock.patch.object(auto.run_selftests, 'latest_completed_round', return_value=20),              mock.patch.object(auto.run_selftests, 'source_rounds_since', return_value=9),              mock.patch.object(auto.run_selftests, 'is_master_checkout', return_value=True),              mock.patch.object(auto.run_selftests, 'risk_overdue_since', return_value=False),              mock.patch.object(auto.run_selftests, 'full_safe_required', return_value=required),              mock.patch.object(auto.run_selftests, 'full_safe_auto_due', return_value=True),              mock.patch.object(auto, '_git', return_value='bbb'),              mock.patch.object(auto, 'last_result', return_value=last),              mock.patch.object(auto.time, 'time', return_value=self.NOW):
            return auto.status()

    def test_status_suppresses_auto_due_while_cooling(self):
        info = self.status_with(self.result('aaa', age=60), required=False)
        self.assertEqual(info['cooling'], 'time')
        self.assertFalse(info['auto_due'])

    def test_required_gate_overrides_the_time_cooldown_but_not_the_same_head(self):
        info = self.status_with(self.result('aaa', age=60), required=True)
        self.assertEqual(info['cooling'], '')
        self.assertTrue(info['auto_due'])
        same = self.status_with(self.result('bbb', age=60), required=True)
        self.assertEqual(same['cooling'], 'head')
        self.assertFalse(same['auto_due'])

    def test_current_cooling_uses_the_live_head(self):
        with mock.patch.object(auto, '_git', return_value='aaa'), \
             mock.patch.object(auto, 'last_result', return_value=self.result('aaa', age=60)), \
             mock.patch.object(auto.time, 'time', return_value=self.NOW):
            self.assertEqual(auto.current_cooling(), 'head')
        with mock.patch.object(auto, '_git', return_value='bbb'), \
             mock.patch.object(auto, 'last_result', return_value=self.result('aaa', age=60)), \
             mock.patch.object(auto.time, 'time', return_value=self.NOW):
            self.assertEqual(auto.current_cooling(), 'time')

    def test_current_cooling_degrades_to_the_time_check_without_git(self):
        # 读不到 HEAD 时退化为 'time' 判定：仍非空，门禁保持保守（不放行），不会误判成「无冷却」。
        with mock.patch.object(auto, '_git', side_effect=OSError('no git')), \
             mock.patch.object(auto, 'last_result', return_value=self.result('aaa', age=60)), \
             mock.patch.object(auto.time, 'time', return_value=self.NOW):
            self.assertEqual(auto.current_cooling(), 'time')


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

    def test_notice_failure_leaves_swallowed_trace(self):
        """--notice 的附加提示故障必须经 app_logging.swallowed 留痕，不能无声吞掉。"""
        import infra.app_logging as app_logging
        app_logging._recent_swallowed.clear()
        before = len(app_logging._recent_swallowed)
        with mock.patch.object(auto, 'failure_notice', side_effect=RuntimeError('x')):
            self.assertEqual(auto.main(['--notice']), 0)
        self.assertGreater(len(app_logging._recent_swallowed), before)


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
            history = Path(folder) / 'history.jsonl'
            with mock.patch.object(auto, 'LOG', log), \
                 mock.patch.object(auto, '_result_path', return_value=result), \
                 mock.patch.object(auto, '_history_path', return_value=history):
                auto.write_result('abcdef1234', 1, 78.0)
                text = auto.failure_notice()
            self.assertTrue(history.exists(), '历史追加必须落在测试临时目录，不能污染真实 full-safe-history.jsonl')
        self.assertIn('不是测试失败', text)

    def test_a_real_red_still_names_the_modules(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / 'auto.log'
            log.write_text('### test_alpha（1 条红）\n', encoding='utf-8')
            result = Path(folder) / 'result.json'
            history = Path(folder) / 'history.jsonl'
            with mock.patch.object(auto, 'LOG', log), \
                 mock.patch.object(auto, '_result_path', return_value=result), \
                 mock.patch.object(auto, '_history_path', return_value=history):
                auto.write_result('abcdef1234', 1, 700.0)
                text = auto.failure_notice()
            self.assertTrue(history.exists(), '历史追加必须落在测试临时目录，不能污染真实 full-safe-history.jsonl')
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


class IgnoredInputTests(unittest.TestCase):
    """R1693 实测：`test_agents_md` 要读 `维护记录/基准历史.json`，而它被 .gitignore 排除，
    干净检出里天然没有——不补这一份，后台全量每次都会红在同一条上。"""

    def test_the_local_benchmark_history_is_supplied_to_the_checkout(self):
        with tempfile.TemporaryDirectory() as folder:
            main, target = Path(folder) / 'main', Path(folder) / 'ci'
            records = main / '程序' / '维护记录'
            records.mkdir(parents=True)
            (records / '基准历史.json').write_text('[]', encoding='utf-8')
            (records / 'auto_full_safe.log').write_text('不该被拷走', encoding='utf-8')
            auto._fill_ignored_inputs(main, target)
            copied = target / '程序' / '维护记录' / '基准历史.json'
            self.assertEqual(copied.read_text(encoding='utf-8'), '[]')
            self.assertFalse((target / '程序' / '维护记录' / 'auto_full_safe.log').exists(),
                             '只补显式清单，日志与台账不能进检出')
            self.assertIn('维护记录/基准历史.json', auto.IGNORED_INPUTS)

    def test_a_missing_input_is_tolerated(self):
        with tempfile.TemporaryDirectory() as folder:
            auto._fill_ignored_inputs(Path(folder) / 'main', Path(folder) / 'ci')
            # 源文件缺失：不抛，也不在目标检出里凭空建目录或空文件。
            self.assertFalse((Path(folder) / 'ci').exists())

    def test_an_existing_copy_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            main, target = Path(folder) / 'main', Path(folder) / 'ci'
            (main / '程序' / '维护记录').mkdir(parents=True)
            (main / '程序' / '维护记录' / '基准历史.json').write_text('新', encoding='utf-8')
            (target / '程序' / '维护记录').mkdir(parents=True)
            (target / '程序' / '维护记录' / '基准历史.json').write_text('旧', encoding='utf-8')
            auto._fill_ignored_inputs(main, target)
            self.assertEqual((target / '程序' / '维护记录' / '基准历史.json').read_text(encoding='utf-8'), '旧')


class BundledToolTests(unittest.TestCase):
    """运行环境/ 被 .gitignore 排除：干净检出里 tool_path 找不到 ffmpeg/ffprobe，
    关键帧取证等测试必红（R33xx 全量实测 ~10 个文件）。补齐只圈 ffmpeg 一棵子树。"""

    def test_bundled_ffmpeg_is_supplied_to_the_checkout(self):
        with tempfile.TemporaryDirectory() as folder:
            main, target = Path(folder) / 'main', Path(folder) / 'ci'
            bindir = main / '运行环境' / 'ffmpeg' / 'bin'
            bindir.mkdir(parents=True)
            (bindir / 'ffmpeg.exe').write_bytes(b'FFMPEG')
            (bindir / 'ffprobe.exe').write_bytes(b'FFPROBE')
            python_dir = main / '运行环境' / 'Python'
            python_dir.mkdir(parents=True)
            (python_dir / 'python.exe').write_bytes(b'PY')
            auto._fill_bundled_tools(main, target)
            self.assertEqual((target / '运行环境' / 'ffmpeg' / 'bin' / 'ffmpeg.exe').read_bytes(), b'FFMPEG')
            self.assertEqual((target / '运行环境' / 'ffmpeg' / 'bin' / 'ffprobe.exe').read_bytes(), b'FFPROBE')
            self.assertFalse((target / '运行环境' / 'Python').exists(),
                             '只补 ffmpeg 一棵子树，Python 运行时不进检出')
            self.assertIn('ffmpeg', auto.BUNDLED_TOOL_DIRS)

    def test_a_missing_tool_dir_is_tolerated(self):
        with tempfile.TemporaryDirectory() as folder:
            auto._fill_bundled_tools(Path(folder) / 'main', Path(folder) / 'ci')
            self.assertFalse((Path(folder) / 'ci').exists())

    def test_an_existing_tool_dir_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            main, target = Path(folder) / 'main', Path(folder) / 'ci'
            (main / '运行环境' / 'ffmpeg' / 'bin').mkdir(parents=True)
            (main / '运行环境' / 'ffmpeg' / 'bin' / 'ffmpeg.exe').write_bytes(b'NEW')
            old = target / '运行环境' / 'ffmpeg' / 'bin' / 'ffmpeg.exe'
            old.parent.mkdir(parents=True)
            old.write_bytes(b'OLD')
            auto._fill_bundled_tools(main, target)
            self.assertEqual(old.read_bytes(), b'OLD')


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


    def test_history_records_green_and_red_runs_but_not_blocked_ones(self):
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.object(auto, '_history_path', return_value=Path(folder) / 'h.jsonl'):
                auto.append_history('abc', 1, 12.4, ['test_a'])
                auto.append_history('def', 0, 30, [])
                auto.append_history('ghi', 1, 1, [], blocked='sandbox')
            rows = [json.loads(line) for line in (Path(folder) / 'h.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual([(row['head'], row['ok'], row['failed_files']) for row in rows],
                         [('abc', False, ['test_a']), ('def', True, [])])

    def test_history_write_failure_never_breaks_the_run(self):
        with mock.patch.object(auto, '_history_path', return_value=Path('/nonexistent-dir/h.jsonl')):
            auto.append_history('abc', 0, 1, [])

if __name__ == '__main__':
    unittest.main()
