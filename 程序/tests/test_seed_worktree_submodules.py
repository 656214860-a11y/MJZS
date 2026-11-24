# -*- coding: utf-8 -*-
"""WORKTREE-SUBMODULES：scripts/seed_worktree_submodules.py 的行为自检。

``git worktree add`` 新建的车道里三个子模块目录是空的（本机无网络，不能
``git submodule update --init``），导致 ``test_script_contract`` 的剧本 SKILL
审计在车道误红。本脚本把主工作树 ``.gitmodules`` 里各子模块的纯文件内容逐文件
复制到车道对应路径：不复制 ``.git``、不执行 submodule update、不改变 Git 状态。

本文件用 tempfile 造假主树／车道树，覆盖：正常复制、``.git`` 不复制、幂等、
源缺失／为空警告，以及参数错误退出码；另有一条真 ``git worktree add`` 的
端到端用例覆盖 worktree list 解析。
"""
import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
for folder in (str(HERE.parent / "scripts"), str(HERE.parent)):
    if folder not in sys.path:
        sys.path.insert(0, folder)

import seed_worktree_submodules as sws

GITMODULES = (
    '[submodule "prog/sub-a"]\n'
    '\tpath = prog/sub-a\n'
    '\turl = https://example.invalid/a.git\n'
    '[submodule "prog/nested/sub-b"]\n'
    '\tpath = prog/nested/sub-b\n'
    '\turl = https://example.invalid/b.git\n'
)


def make_main(root):
    """造一个带 .gitmodules 和两个子模块内容的假主工作树，返回根 Path。"""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    (root / ".gitmodules").write_text(GITMODULES, encoding="utf-8")
    sub_a = root / "prog" / "sub-a"
    (sub_a / "inner").mkdir(parents=True)
    (sub_a / "a.txt").write_text("alpha\n", encoding="utf-8")
    (sub_a / "inner" / "b.txt").write_text("beta\n", encoding="utf-8")
    (sub_a / ".git").write_text("gitdir: ../.git/modules/prog/sub-a\n", encoding="utf-8")
    (sub_a / "inner" / ".git").mkdir()
    (sub_a / "inner" / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    sub_b = root / "prog" / "nested" / "sub-b"
    sub_b.mkdir(parents=True)
    (sub_b / "c.txt").write_text("gamma\n", encoding="utf-8")
    return root


def _git(root, *args):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    done = subprocess.run(["git", *args], cwd=str(root), env=env,
                          capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


class SeedWorktreeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.main = make_main(self.base / "main")
        self.lane = self.base / "lane"
        self.lane.mkdir()

    def test_copies_plain_files_skips_dot_git_and_creates_parents(self):
        results = sws.seed_worktree(self.lane, self.main)
        by_path = {row["path"]: row for row in results}
        self.assertEqual(set(by_path), {"prog/sub-a", "prog/nested/sub-b"})
        self.assertEqual(by_path["prog/sub-a"]["copied"], 2)
        self.assertEqual(by_path["prog/nested/sub-b"]["copied"], 1)
        lane_a = self.lane / "prog" / "sub-a"
        self.assertEqual((lane_a / "a.txt").read_text(encoding="utf-8"), "alpha\n")
        self.assertEqual((lane_a / "inner" / "b.txt").read_text(encoding="utf-8"), "beta\n")
        self.assertEqual((self.lane / "prog" / "nested" / "sub-b" / "c.txt")
                         .read_text(encoding="utf-8"), "gamma\n")
        self.assertFalse((lane_a / ".git").exists(), ".git 文件不许复制")
        self.assertFalse((lane_a / "inner" / ".git").exists(), "嵌套 .git 目录不许复制")

    def test_second_run_is_noop_and_sha256_fallback_skips_same_content(self):
        sws.seed_worktree(self.lane, self.main)
        touched = self.lane / "prog" / "sub-a" / "a.txt"
        os.utime(touched, (0, 0))  # 大小相同、mtime 不同：走 sha256 兜底判一致
        results = sws.seed_worktree(self.lane, self.main)
        for row in results:
            self.assertEqual(row["status"], "uptodate", row)
            self.assertEqual(row["copied"], 0)
        self.assertEqual(touched.read_text(encoding="utf-8"), "alpha\n")

    def test_changed_content_is_recopied(self):
        sws.seed_worktree(self.lane, self.main)
        target = self.lane / "prog" / "sub-a" / "a.txt"
        target.write_text("tampered\n", encoding="utf-8")
        results = sws.seed_worktree(self.lane, self.main)
        by_path = {row["path"]: row for row in results}
        self.assertEqual(by_path["prog/sub-a"]["copied"], 1)
        self.assertEqual(target.read_text(encoding="utf-8"), "alpha\n")

    def test_missing_source_warns_but_run_returns_zero(self):
        (self.main / ".gitmodules").write_text(
            '[submodule "ghost"]\n\tpath = ghost\n', encoding="utf-8")
        results = sws.seed_worktree(self.lane, self.main)
        self.assertEqual(results[0]["status"], "missing")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = sws.run(self.lane, self.main)
        self.assertEqual(code, 0)
        self.assertIn("源缺失", buf.getvalue())
        self.assertIn("ghost", buf.getvalue())
        self.assertFalse((self.lane / "ghost").exists())

    def test_empty_source_warns(self):
        (self.main / ".gitmodules").write_text(
            '[submodule "empty"]\n\tpath = empty\n', encoding="utf-8")
        empty = self.main / "empty"
        empty.mkdir()
        (empty / ".git").write_text("gitdir: x\n", encoding="utf-8")
        results = sws.seed_worktree(self.lane, self.main)
        self.assertEqual(results[0]["status"], "empty")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = sws.run(self.lane, self.main)
        self.assertEqual(code, 0)
        self.assertIn("为空", buf.getvalue())

    def test_main_worktree_target_is_idempotent_noop(self):
        results = sws.seed_worktree(self.main, self.main)
        self.assertTrue(results)
        for row in results:
            self.assertIn(row["status"], {"same", "uptodate"})
            self.assertEqual(row["copied"], 0)

    def test_argument_errors_exit_two(self):
        with self.assertRaises(SystemExit) as missing:
            sws.main([])
        self.assertEqual(missing.exception.code, 2)
        with self.assertRaises(SystemExit) as extra:
            sws.main(["a", "b"])
        self.assertEqual(extra.exception.code, 2)
        self.assertEqual(sws.main([str(self.base / "no-such-dir")]), 2)

    def test_main_end_to_end_on_a_real_worktree(self):
        """真 git 仓 + worktree add：验证 worktree list 解析与端到端复制、幂等。"""
        repo = self.base / "repo"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "main")
        make_main(repo)
        _git(repo, "add", ".gitmodules")
        _git(repo, "commit", "-qm", "init")
        lane = self.base / "real-lane"
        _git(repo, "worktree", "add", "-q", "-b", "lane", str(lane))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = sws.main([str(lane)])
        self.assertEqual(code, 0)
        self.assertIn("复制", buf.getvalue())
        self.assertEqual((lane / "prog" / "sub-a" / "a.txt")
                         .read_text(encoding="utf-8"), "alpha\n")
        self.assertFalse((lane / "prog" / "sub-a" / ".git").exists())
        buf2 = io.StringIO()
        with contextlib.redirect_stdout(buf2):
            code2 = sws.main([str(lane)])
        self.assertEqual(code2, 0)
        self.assertIn("已是最新", buf2.getvalue())
        self.assertNotIn("复制", buf2.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
