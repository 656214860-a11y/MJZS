"""branch_scope：活跃车道新增文件撞名检测与范围重叠扫描（R2542/R2538 重复实现教训）。"""
import contextlib
import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
SCRIPT = PROGRAM / "维护记录/基准脚本/branch_scope.py"
SPEC = importlib.util.spec_from_file_location("branch_scope_tests", SCRIPT)
scope = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scope)

sys.path.insert(0, str(PROGRAM / "scripts"))
import commit_round  # noqa: E402


def git(repo, *args):
    done = subprocess.run(["git", "-c", "core.quotepath=false", "-C", str(repo), *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    if done.returncode:
        raise RuntimeError("%s failed: %s" % (args[0], done.stderr.strip()))
    return done.stdout.strip()


def write(repo, rel, text="x\n"):
    path = Path(repo) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class BranchScopeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.container = Path(temporary.name)
        self.repo = self.container / "main"
        self.repo.mkdir()
        git(self.repo, "init", "-b", "master")
        git(self.repo, "config", "user.name", "Scope Test")
        git(self.repo, "config", "user.email", "scope@example.invalid")
        write(self.repo, "base.txt", "base\n")
        git(self.repo, "add", "base.txt")
        git(self.repo, "commit", "-m", "seed")
        # 车道 A：从 master 拉出，新增 prog/dup.py 并提交，挂到工作树 wt-a
        git(self.repo, "switch", "-c", "codex/lane-a")
        write(self.repo, "prog/dup.py", "lane-a\n")
        git(self.repo, "add", "prog/dup.py")
        git(self.repo, "commit", "-m", "lane-a add")
        git(self.repo, "switch", "-c", "codex/current", "master")
        git(self.repo, "worktree", "add", str(self.container / "wt-a"), "codex/lane-a")
        # 游离工作树不应被算作车道
        git(self.repo, "worktree", "add", "--detach", str(self.container / "wt-detached"), "master")

    def stage(self, rel):
        write(self.repo, rel)
        git(self.repo, "add", rel)

    def test_added_file_collision_is_flagged(self):
        self.stage("prog/dup.py")
        report = scope.commit_gate_report(self.repo, exclude_branch="codex/current")
        self.assertEqual(len(report["conflicts"]), 1)
        self.assertIn("prog/dup.py", report["conflicts"][0])
        self.assertIn("codex/lane-a", report["conflicts"][0])
        self.assertEqual(report["skipped"], [])

    def test_no_staged_additions_means_no_conflict(self):
        # 修改的文件不在其他车道的未合入改动里，门禁不触发
        write(self.repo, "base.txt", "changed\n")
        git(self.repo, "add", "base.txt")
        report = scope.commit_gate_report(self.repo, exclude_branch="codex/current")
        self.assertEqual(report["conflicts"], [])

    def test_overlapping_modification_is_rejected(self):
        git(self.repo, "switch", "-c", "codex/lane-b", "master")
        write(self.repo, "base.txt", "lane-b\n")
        git(self.repo, "add", "base.txt")
        git(self.repo, "commit", "-m", "lane-b modify")
        git(self.repo, "switch", "codex/current")
        git(self.repo, "worktree", "add", str(self.container / "wt-b"), "codex/lane-b")
        write(self.repo, "base.txt", "current\n")
        git(self.repo, "add", "base.txt")
        report = scope.commit_gate_report(self.repo, exclude_branch="codex/current")
        self.assertEqual(len(report["conflicts"]), 1)
        self.assertIn("base.txt", report["conflicts"][0])
        self.assertIn("codex/lane-b", report["conflicts"][0])
        self.assertNotIn("add/add", report["conflicts"][0])
        self.assertEqual(commit_round.check_scope_overlap(self.repo), 5)

    def test_unrelated_new_file_passes(self):
        self.stage("prog/other.py")
        report = scope.commit_gate_report(self.repo, exclude_branch="codex/current")
        self.assertEqual(report["conflicts"], [])

    def test_merged_lane_does_not_block(self):
        # lane-a 合入 master 后其改动已在主干：master...lane-a 为空，不再算「其他分支新增」。
        # 当前分支不回并 master，prog/dup.py 对它仍是新增文件——正是要验证的场景。
        git(self.repo, "switch", "master")
        git(self.repo, "merge", "--no-edit", "codex/lane-a")
        git(self.repo, "switch", "codex/current")
        self.stage("prog/dup.py")
        report = scope.commit_gate_report(self.repo, exclude_branch="codex/current")
        self.assertEqual(report["conflicts"], [])

    def test_scope_report_prefix_matching(self):
        report = scope.scope_report(self.repo, ["prog"], exclude={"codex/current"})
        self.assertIn("codex/lane-a", report["branches"])
        self.assertEqual(report["branches"]["codex/lane-a"]["matches"], ["prog/dup.py"])
        report = scope.scope_report(self.repo, ["prog/dup.py"], exclude={"codex/current"})
        self.assertIn("codex/lane-a", report["branches"])
        report = scope.scope_report(self.repo, ["prog/du"], exclude={"codex/current"})
        self.assertNotIn("codex/lane-a", report["branches"])

    def test_scope_report_added_only_ignores_modifications(self):
        # lane-b 修改已存在文件：全部改动口径命中，新增口径不命中
        git(self.repo, "switch", "-c", "codex/lane-b", "master")
        write(self.repo, "base.txt", "lane-b\n")
        git(self.repo, "add", "base.txt")
        git(self.repo, "commit", "-m", "lane-b modify")
        git(self.repo, "switch", "codex/current")
        git(self.repo, "worktree", "add", str(self.container / "wt-b"), "codex/lane-b")
        all_report = scope.scope_report(self.repo, ["base.txt"], exclude={"codex/current"})
        self.assertIn("codex/lane-b", all_report["branches"])
        added_report = scope.scope_report(self.repo, ["base.txt"], added_only=True,
                                          exclude={"codex/current"})
        self.assertNotIn("codex/lane-b", added_report["branches"])

    def test_detached_worktree_is_not_a_lane(self):
        lanes = {lane["branch"] for lane in scope.lane_branches(self.repo, exclude={"codex/current"})}
        self.assertEqual(lanes, {"codex/lane-a"})

    def test_hit_requires_path_boundary(self):
        self.assertTrue(scope._hit("prog/dup.py", "prog"))
        self.assertTrue(scope._hit("prog/dup.py", "prog/dup.py"))
        self.assertFalse(scope._hit("prog/dup.py", "prog/du"))
        self.assertFalse(scope._hit("prog/dup.py", ""))

    def test_commit_round_gate_returns_5_on_collision(self):
        self.stage("prog/dup.py")
        self.assertEqual(commit_round.check_scope_overlap(self.repo), 5)

    def test_commit_round_gate_skips_on_master(self):
        git(self.repo, "switch", "master")
        self.stage("prog/dup.py")
        self.assertEqual(commit_round.check_scope_overlap(self.repo), 0)

    def test_cli_json_output(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = scope.main(["--root", str(self.repo), "--json", "prog"])
        self.assertEqual(code, 0)
        self.assertIn("codex/lane-a", out.getvalue())


if __name__ == "__main__":
    unittest.main()
