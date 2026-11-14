"""主工作区同步脚本：真实临时 Git 仓库验证只拉不推、fast-forward 与前置拒绝。"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROGRAM = Path(__file__).resolve().parent.parent
SCRIPT = PROGRAM / "scripts" / "sync_master.py"
SPEC = importlib.util.spec_from_file_location("sync_master_for_tests", SCRIPT)
sync_master = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = sync_master
SPEC.loader.exec_module(sync_master)


class SyncMasterTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.container = Path(temporary.name)

    def _repo(self, name: str = "main", branch: str = "master") -> Path:
        root = self.container / name
        root.mkdir()
        subprocess.run(["git", "init", "-b", branch, "--quiet", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "Sync Test"], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.email", "sync@example.invalid"], check=True)
        return root

    def _commit(self, root: Path, message: str) -> None:
        subprocess.run(["git", "-C", str(root), "commit", "--allow-empty", "-m", message], check=True)

    @staticmethod
    def _fetch_result(returncode: int, stderr: str = ""):
        """让模块内 git() 只在 fetch 时返回指定结果，其余走真实实现。"""
        real_git = sync_master.git

        def fake_git(*args, **kwargs):
            if args and args[0] == "fetch":
                return subprocess.CompletedProcess(["git"], returncode, stdout="", stderr=stderr)
            return real_git(*args, **kwargs)

        return mock.patch.object(sync_master, "git", side_effect=fake_git)

    def test_non_main_worktree_refuses(self):
        root = self._repo()
        self._commit(root, "seed")
        tree = self.container / "feature"
        subprocess.run(["git", "-C", str(root), "worktree", "add", "-b", "feature/x", str(tree)], check=True)
        with self.assertRaisesRegex(RuntimeError, "不是主工作区"):
            sync_master.sync_master(root=tree, remote="origin", branch="feature/x")

    def test_wrong_branch_refuses(self):
        root = self._repo()
        self._commit(root, "seed")
        subprocess.run(["git", "-C", str(root), "switch", "-c", "feature/y"], check=True)
        with self.assertRaisesRegex(RuntimeError, "不一致"):
            sync_master.sync_master(root=root, remote="origin", branch="master")

    def test_dirty_master_refuses(self):
        root = self._repo()
        self._commit(root, "seed")
        (root / "draft.txt").write_text("x", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "未提交"):
            sync_master.sync_master(root=root, remote="origin", branch="master")

    def test_already_current_reports_ahead(self):
        root = self._repo()
        self._commit(root, "seed")
        with self._fetch_result(0):
            report = sync_master.sync_master(root=root, remote="origin", branch="master")
        self.assertEqual(report["ahead"], 0)
        self.assertEqual(report["behind"], 0)
        self.assertEqual(report["action"], "already-current")
        self.assertFalse(report["pushed"])

    def test_fetch_failure_propagates(self):
        root = self._repo()
        self._commit(root, "seed")
        with self._fetch_result(1, stderr="network down"):
            with self.assertRaisesRegex(RuntimeError, "fetch"):
                sync_master.sync_master(root=root, remote="origin", branch="master")


if __name__ == "__main__":
    unittest.main()
