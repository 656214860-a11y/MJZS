"""commit_round：等锁逻辑只在锁持有进程存活时阻塞；失效锁被回收，超时不吞暂存区。"""
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM / 'scripts'))
import commit_round  # noqa: E402
import run_selftests  # noqa: E402


class CommitRoundTests(unittest.TestCase):
    def test_explicit_commit_rejects_foreign_index_before_adding_files(self):
        from contextlib import ExitStack
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            repo = Path(tmp)
            program = repo / 'program'
            program.mkdir()
            git = commit_round._git
            def run(*args):
                result = git(*args, cwd=program)
                result.check_returncode()
                return result.stdout
            run('init', '-b', 'codex/test', str(repo))
            run('config', 'user.name', 'test')
            run('config', 'user.email', 'test@example.invalid')
            run('config', 'core.hooksPath', 'unused')
            run('commit', '--allow-empty', '-m', 'base')
            (repo / '其他文件').write_text('foreign', encoding='utf8')
            (program / 'owned').write_text('requested', encoding='utf8')
            run('add', '../其他文件')
            head = run('rev-parse', 'HEAD')
            index = run('write-tree')
            stack.enter_context(patch.object(commit_round, 'PROGRAM', program))
            stack.enter_context(patch.object(commit_round, '_git', side_effect=lambda *a, **kw:
                                             git(*a, cwd=kw.get('cwd', program))))
            for guard in ('attach_codex_worktree', 'check_scope_overlap', 'check_test_move',
                          'check_taskbook_closure', 'attach_evidence', 'common_dir'):
                stack.enter_context(patch.object(commit_round, guard, return_value=0))
            self.assertNotEqual(0, commit_round.main(['-m', 'R1: explicit', 'owned']))
            self.assertEqual(head, run('rev-parse', 'HEAD'))
            self.assertEqual(index, run('write-tree'))
            self.assertEqual(0, commit_round.main(['-m', 'R1: staged']))
            merge_head = repo / '.git' / 'MERGE_HEAD'
            merge_head.write_text(run('rev-parse', 'HEAD'), encoding='ascii')
            self.assertNotEqual(0, commit_round.main(['-m', 'R2: partial merge', 'owned']))
            self.assertEqual('', run('diff', '--cached', '--name-only'))
            merge_head.unlink()
            # Another process stages a file after the last check, before Git takes its lock.
            late = repo / 'late'
            late.write_text('concurrent addition', encoding='utf8')
            original_run = commit_round._run_git
            def stage_during_commit(args, cwd, env=None):
                if args[0] == 'commit':
                    original_run(['add', '--', 'late'], repo).check_returncode()
                return original_run(args, cwd, env)
            with patch.object(commit_round, '_run_git', side_effect=stage_during_commit):
                self.assertEqual(0, commit_round.main(['-m', 'R2: explicit', 'owned']))
            self.assertEqual('late', run('diff', '--cached', '--name-only').strip())
            self.assertEqual('program/owned', run('diff-tree', '--no-commit-id', '--name-only',
                                                 '-r', 'HEAD').strip())

    def test_detached_codex_commit_keeps_index_and_leaves_shared_lock_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            repo = home / "repo"
            repo.mkdir()
            work = home / ".codex" / "worktrees" / "abcd" / "repo"
            git = commit_round._git
            git("init", "-b", "main", cwd=repo).check_returncode()
            git("-c", "user.name=test", "-c", "user.email=test@example.org",
                "commit", "--allow-empty", "-m", "init", cwd=repo).check_returncode()
            git("worktree", "add", "--detach", str(work), cwd=repo).check_returncode()
            lock = self.lock(commit_round.common_dir(repo), os.getpid())
            (work / "change").write_text("staged", encoding="utf-8")
            git("add", "change", cwd=work).check_returncode()
            before = git("rev-parse", "HEAD", cwd=work).stdout
            with patch.object(Path, "home", return_value=home):
                self.assertEqual(commit_round.attach_codex_worktree(work), 0)
                self.assertEqual(commit_round.attach_codex_worktree(work), 0)
            self.assertEqual(git("branch", "--show-current", cwd=work).stdout.strip(), "codex/worktree-abcd")
            self.assertEqual(git("rev-parse", "HEAD", cwd=work).stdout, before)
            self.assertEqual(git("diff", "--cached", "--name-only", cwd=work).stdout.strip(), "change")
            self.assertTrue(lock.exists())

    def lock(self, common, pid):
        path = Path(common) / run_selftests.FULL_SAFE_LOCK_NAME
        path.write_text(json.dumps({'pid': pid, 'round': 1}), encoding='utf-8')
        return path

    def test_no_lock_passes_immediately(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(commit_round.wait_for_lock(Path(tmp), 0, out=lambda _: None))

    def test_dead_holder_lock_is_reclaimed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.lock(tmp, 2 ** 22 + 12345)
            self.assertTrue(commit_round.wait_for_lock(Path(tmp), 5, poll=0.01, out=lambda _: None))
            self.assertFalse(path.exists())

    def test_live_holder_times_out_and_lock_stays(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.lock(tmp, os.getpid())
            self.assertFalse(commit_round.wait_for_lock(Path(tmp), 0.05, poll=0.01, out=lambda _: None))
            self.assertTrue(path.exists())

    def test_fresh_heartbeat_stays_even_when_the_pid_cannot_be_opened(self):
        import time
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / run_selftests.FULL_SAFE_LOCK_NAME
            path.write_text(json.dumps({
                'pid': 2 ** 22 + 9, 'round': 4, 'token': 'held',
                'heartbeat_at': time.time(), 'started_at': time.time(),
            }), encoding='utf-8')
            self.assertFalse(commit_round.wait_for_lock(Path(tmp), 0.05, poll=0.01, out=lambda _: None))
            self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['token'], 'held')

    def test_silent_heartbeat_is_reclaimed_even_if_the_pid_is_alive(self):
        import time
        with tempfile.TemporaryDirectory() as tmp:
            path = self.lock(tmp, os.getpid())
            path.write_text(json.dumps({
                'pid': os.getpid(), 'round': 4, 'token': 'old',
                'heartbeat_at': time.time() - 300, 'started_at': time.time(),
            }), encoding='utf-8')
            self.assertTrue(commit_round.wait_for_lock(Path(tmp), 1, poll=0.01, out=lambda _: None))
            self.assertFalse(path.exists())

    def test_young_unreadable_lock_is_not_deleted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / run_selftests.FULL_SAFE_LOCK_NAME
            path.write_text('{', encoding='utf-8')
            self.assertFalse(commit_round.wait_for_lock(Path(tmp), 0.05, poll=0.01, out=lambda _: None))
            self.assertEqual(path.read_text(encoding='utf-8'), '{')

    def test_index_lock_retries_then_stops(self):
        from subprocess import CompletedProcess
        calls = []

        def fake_run(command, **kwargs):
            calls.append(command)
            if len(calls) < 3:
                return CompletedProcess(command, 128, '', "fatal: Unable to create '.git/index.lock': File exists.")
            return CompletedProcess(command, 0, '', '')

        with patch('commit_round.subprocess.run', side_effect=fake_run), \
             patch('commit_round.time.sleep') as slept:
            done = commit_round._git('add', '--', 'a')
        self.assertEqual(done.returncode, 0)
        self.assertEqual([item.args[0] for item in slept.call_args_list], [0.2, 0.4])

    def test_unrelated_git_failure_is_not_retried(self):
        from subprocess import CompletedProcess

        def fake_run(command, **kwargs):
            return CompletedProcess(command, 1, '', 'fatal: pathspec did not match')

        with patch('commit_round.subprocess.run', side_effect=fake_run) as run, \
             patch('commit_round.time.sleep') as slept:
            done = commit_round._git('add', '--', 'missing')
        self.assertEqual(done.returncode, 1)
        self.assertEqual(run.call_count, 1)
        slept.assert_not_called()

    def test_old_round_numbers_skip_evidence_and_new_ones_require_it(self):
        import round_evidence
        self.assertEqual(commit_round.attach_evidence('R1931: 旧轮', [], Path('.')), 0)
        self.assertEqual(commit_round.attach_evidence('WIP: 半成品', [], Path('.')), 0)
        self.assertGreater(round_evidence.EVIDENCE_REQUIRED_FROM, 1931)


    def test_agent_trailer_is_appended_once_and_only_when_named(self):
        self.assertEqual(commit_round.with_agent_trailer('R1: x', ''), 'R1: x')
        once = commit_round.with_agent_trailer('R1: x', 'swe-2')
        self.assertEqual(once, 'R1: x\n\nAgent: swe-2')
        self.assertEqual(commit_round.with_agent_trailer(once, 'swe-2'), once)

    def test_test_move_check_only_runs_for_move_round_messages(self):
        from unittest import mock
        with mock.patch.object(commit_round.test_move_audit, 'audit_staged', return_value=['x：改了断言']) as audit:
            self.assertEqual(commit_round.check_test_move('R1: 普通改动', Path('.')), 0)
            self.assertEqual(commit_round.check_test_move('R1: 补测试搬家守卫', Path('.')), 0)
            audit.assert_not_called()
            self.assertEqual(commit_round.check_test_move('R1: 测试搬家：迁入 tests/', Path('.')), 5)
            audit.assert_called_once()
        with mock.patch.object(commit_round.test_move_audit, 'audit_staged', return_value=[]):
            self.assertEqual(commit_round.check_test_move('R1: 测试搬家', Path('.')), 0)

if __name__ == '__main__':
    unittest.main()
