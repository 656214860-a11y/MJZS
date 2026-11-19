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
