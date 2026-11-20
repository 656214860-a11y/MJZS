"""branch_scope 精确重叠门禁（《Git并发锁机制优化任务书》G2）。

只有与活跃车道存在真实文本冲突或双方新增同名文件时才拒绝提交。临时仓库里搭车道，覆盖：
不同段落放行、同一段落拒绝、对方超过 48 小时无活动只提示、心跳让旧分支重新算活跃、同名新增即使
内容相同也拒绝、R3919 的 ``architecture.md`` 场景放行、对方与主干此前已有的冲突不算本次新增、
已冲突文件里新增一段冲突或改到已有冲突段仍拒绝、对方改过名的文件冲突落在新路径上也拒绝、与主干新提交的冲突
不算在车道头上、试合并不往仓库写对象也不动索引、结果缓存命中后不重算。
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

PROGRAM = Path(__file__).resolve().parents[1]
SCRIPT = PROGRAM / "维护记录/基准脚本/branch_scope.py"
SPEC = importlib.util.spec_from_file_location("branch_scope_precise_tests", SCRIPT)
scope = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scope)

sys.path.insert(0, str(PROGRAM / "scripts"))
import commit_round  # noqa: E402

HOUR = 3600
CURRENT = "codex/current"


def git(repo, *args, env=None):
    done = subprocess.run(["git", "-c", "core.quotepath=false", "-C", str(repo), *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env=dict(os.environ, **env) if env else None)
    if done.returncode:
        raise RuntimeError("%s failed: %s" % (args[0], done.stderr.strip()))
    return done.stdout.strip()


def write(repo, rel, text):
    path = Path(repo) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def body(**changes):
    """30 行正文；``body(line3="甲")`` 把第 3 行换掉。行间隔开三行以上的改动可以自动合并。"""
    lines = ["第 %02d 行" % number for number in range(1, 31)]
    for key, text in changes.items():
        lines[int(key.removeprefix("line")) - 1] = text
    return "\n".join(lines) + "\n"


class PreciseGateCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.container = Path(temporary.name)
        self.repo = self.container / "main"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "master")
        git(self.repo, "config", "user.name", "Scope Test")
        git(self.repo, "config", "user.email", "scope@example.invalid")
        git(self.repo, "config", "core.autocrlf", "false")
        write(self.repo, "doc.md", body())
        git(self.repo, "add", "doc.md")
        git(self.repo, "commit", "-q", "-m", "seed")
        git(self.repo, "switch", "-q", "-c", CURRENT)

    def lane(self, name, files, *, days_ago=0):
        """从 master 拉出车道分支、挂到独立工作树并提交 files；days_ago 让提交时间落在过去。"""
        path = self.container / ("wt-" + name)
        if not path.exists():
            git(self.repo, "worktree", "add", "-q", "-b", "codex/" + name, str(path), "master")
        for rel, text in files.items():
            write(path, rel, text)
        git(path, "add", "--", *files)
        env = None
        if days_ago:
            stamp = "%d +0000" % (time.time() - days_ago * 24 * HOUR)
            env = {"GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp}
        git(path, "commit", "-q", "-m", name, env=env)
        return "codex/" + name

    def master_moves(self, files):
        """主干前进一个提交，当前分支跟到新的主干上。"""
        git(self.repo, "switch", "-q", "master")
        for rel, text in files.items():
            write(self.repo, rel, text)
        git(self.repo, "add", "--", *files)
        git(self.repo, "commit", "-q", "-m", "master moves")
        git(self.repo, "switch", "-q", "-C", CURRENT, "master")

    def stage(self, files):
        for rel, text in files.items():
            write(self.repo, rel, text)
        git(self.repo, "add", "--", *files)

    def report(self, **options):
        return scope.commit_gate_report(self.repo, exclude_branch=CURRENT, **options)

    def assert_passes(self, report):
        self.assertEqual(report["conflicts"], [])
        self.assertEqual(commit_round.check_scope_overlap(self.repo), 0)


class RealConflictTests(PreciseGateCase):
    def test_different_paragraphs_of_one_file_pass(self):
        self.lane("lane-a", {"doc.md": body(line3="车道甲")})
        self.lane("lane-b", {"doc.md": body(line27="车道乙")})
        self.stage({"doc.md": body(line15="当前")})
        report = self.report()
        self.assert_passes(report)
        notes = "\n".join(report["notes"])
        for expected in ("doc.md", "codex/lane-a", "codex/lane-b"):
            self.assertIn(expected, notes)
        self.assertEqual(report["skipped"], [])

    def test_same_paragraph_is_rejected(self):
        self.lane("lane-a", {"doc.md": body(line3="车道甲")})
        self.lane("lane-b", {"doc.md": body(line27="车道乙")})
        self.stage({"doc.md": body(line3="当前")})
        report = self.report()
        self.assertEqual(len(report["conflicts"]), 1)
        self.assertIn("doc.md", report["conflicts"][0])
        self.assertIn("codex/lane-a", report["conflicts"][0])
        self.assertIn("未合入改动重叠", report["conflicts"][0])
        self.assertNotIn("codex/lane-b", report["conflicts"][0])
        self.assertIn("codex/lane-b", "\n".join(report["notes"]))
        self.assertEqual(commit_round.check_scope_overlap(self.repo), 5)

    def test_deleting_a_file_the_lane_edits_is_rejected(self):
        self.lane("lane-a", {"doc.md": body(line3="车道甲")})
        git(self.repo, "rm", "-q", "doc.md")
        report = self.report()
        self.assertEqual(len(report["conflicts"]), 1)
        self.assertIn("codex/lane-a", report["conflicts"][0])

    def test_r3919_shared_document_touched_by_many_lanes_passes(self):
        self.master_moves({"architecture.md": body()})
        for index, line in enumerate((2, 6, 10, 14, 18, 22), start=1):
            path = self.container / ("wt-doc-%d" % index)
            git(self.repo, "worktree", "add", "-q", "-b", "codex/doc-%d" % index, str(path), "master")
            write(path, "architecture.md", body(**{"line%d" % line: "车道 %d 的段落" % index}))
            git(path, "commit", "-q", "-am", "doc-%d" % index)
        self.stage({"architecture.md": body(line28="本轮的段落")})
        report = self.report()
        self.assert_passes(report)
        self.assertIn("architecture.md", "\n".join(report["notes"]))

    def test_unrelated_paths_need_no_note(self):
        self.lane("lane-a", {"doc.md": body(line3="车道甲")})
        self.stage({"other.md": "新文件\n"})
        self.assertEqual(self.report(), {"conflicts": [], "skipped": [], "notes": []})


class RenamedFileTests(PreciseGateCase):
    """一方把文件改了名：改动清单按「删旧名加新名」算，冲突落在新路径上也要拦。"""

    def renaming_lane(self, name, **changes):
        path = self.container / ("wt-" + name)
        git(self.repo, "worktree", "add", "-q", "-b", "codex/" + name, str(path), "master")
        git(path, "mv", "doc.md", "moved.md")
        write(path, "moved.md", body(**changes))
        git(path, "commit", "-q", "-am", name)
        return "codex/" + name

    def test_edit_colliding_with_a_lane_that_renamed_the_file_is_rejected(self):
        self.renaming_lane("lane-a", line3="车道甲")
        self.stage({"doc.md": body(line3="当前")})
        report = self.report()
        self.assertEqual(len(report["conflicts"]), 1)
        self.assertIn("codex/lane-a", report["conflicts"][0])
        self.assertIn("moved.md", report["conflicts"][0])
        self.assertNotIn("可以自动合并", "\n".join(report["notes"]))
        self.assertEqual(commit_round.check_scope_overlap(self.repo), 5)

    def test_edit_elsewhere_in_a_file_the_lane_renamed_passes(self):
        self.renaming_lane("lane-a", line3="车道甲")
        self.stage({"doc.md": body(line20="当前")})
        report = self.report()
        self.assert_passes(report)
        self.assertIn("codex/lane-a", "\n".join(report["notes"]))

    def test_renaming_a_file_the_lane_edits_passes_when_mergeable(self):
        self.lane("lane-a", {"doc.md": body(line3="车道甲")})
        git(self.repo, "mv", "doc.md", "moved.md")
        report = self.report()
        self.assert_passes(report)
        self.assertIn("codex/lane-a", "\n".join(report["notes"]))

    def test_renaming_and_rewording_the_paragraph_the_lane_edits_is_rejected(self):
        self.lane("lane-a", {"doc.md": body(line3="车道甲")})
        git(self.repo, "mv", "doc.md", "moved.md")
        self.stage({"moved.md": body(line3="当前")})
        report = self.report()
        self.assertEqual(len(report["conflicts"]), 1)
        self.assertIn("codex/lane-a", report["conflicts"][0])
        self.assertIn("moved.md", report["conflicts"][0])


class BehindTrunkTests(PreciseGateCase):
    """对方分支比本分支多带了主干提交：与那段主干的冲突该先变基，不算在车道头上。"""

    def lane_on_newer_trunk(self, trunk_change, lane_change):
        git(self.repo, "switch", "-q", "master")
        write(self.repo, "doc.md", body(**trunk_change))
        git(self.repo, "commit", "-q", "-am", "master moves")
        self.lane("lane-new", {"doc.md": body(**trunk_change, **lane_change)})
        git(self.repo, "switch", "-q", CURRENT)

    def test_conflict_with_a_newer_trunk_commit_is_not_blamed_on_the_lane(self):
        self.lane_on_newer_trunk({"line3": "主干"}, {"line27": "车道乙"})
        self.stage({"doc.md": body(line3="当前")})
        report = self.report()
        self.assert_passes(report)
        notes = "\n".join(report["notes"])
        self.assertIn("变基", notes)
        self.assertIn("codex/lane-new", notes)

    def test_conflict_with_the_lane_itself_is_still_rejected_when_behind_trunk(self):
        self.lane_on_newer_trunk({"line15": "主干"}, {"line3": "车道乙"})
        self.stage({"doc.md": body(line3="当前")})
        report = self.report()
        self.assertEqual(len(report["conflicts"]), 1)
        self.assertIn("codex/lane-new", report["conflicts"][0])

    def test_conflicts_with_both_trunk_and_lane_are_rejected(self):
        self.lane_on_newer_trunk({"line15": "主干"}, {"line3": "车道乙"})
        self.stage({"doc.md": body(line3="当前", line15="当前")})
        report = self.report()
        self.assertEqual(len(report["conflicts"]), 1)
        self.assertIn("codex/lane-new", report["conflicts"][0])


class ActiveLaneTests(PreciseGateCase):
    def test_lane_idle_over_48_hours_only_warns(self):
        self.lane("lane-old", {"doc.md": body(line3="旧车道")}, days_ago=3)
        self.stage({"doc.md": body(line3="当前")})
        report = self.report()
        self.assert_passes(report)
        notes = "\n".join(report["notes"])
        self.assertIn("codex/lane-old", notes)
        self.assertIn("doc.md", notes)

    def test_recent_heartbeat_makes_an_old_branch_active_again(self):
        self.lane("lane-old", {"doc.md": body(line3="旧车道")}, days_ago=3)
        self.stage({"doc.md": body(line3="当前")})
        lanes = {"lanes": {"wt-lane-old": {"branch": "codex/lane-old", "worktree": str(self.container / "wt-lane-old"),
                                           "last_seen": time.time() - HOUR}}}
        (self.repo / ".git" / "lanes.json").write_text(json.dumps(lanes), encoding="utf-8")
        report = self.report()
        self.assertEqual(len(report["conflicts"]), 1)
        self.assertIn("codex/lane-old", report["conflicts"][0])

    def test_activity_window_is_24_hours(self):
        self.lane("lane-a", {"doc.md": body(line3="车道甲")})
        self.stage({"doc.md": body(line3="当前")})
        self.assertEqual(len(self.report(now=time.time() + 23 * HOUR)["conflicts"]), 1)
        later = self.report(now=time.time() + 25 * HOUR)
        self.assertEqual(later["conflicts"], [])
        self.assertIn("codex/lane-a", "\n".join(later["notes"]))

    def test_broken_lane_registry_falls_back_to_commit_time(self):
        self.lane("lane-a", {"doc.md": body(line3="车道甲")})
        self.stage({"doc.md": body(line3="当前")})
        (self.repo / ".git" / "lanes.json").write_text("{bad", encoding="utf-8")
        self.assertEqual(len(self.report()["conflicts"]), 1)


class SameNameAdditionTests(PreciseGateCase):
    def test_same_named_new_file_is_rejected_even_when_identical(self):
        self.lane("lane-a", {"prog/new.py": "same\n"})
        self.stage({"prog/new.py": "same\n"})
        report = self.report()
        self.assertEqual(len(report["conflicts"]), 1)
        self.assertIn("撞名", report["conflicts"][0])
        self.assertIn("prog/new.py", report["conflicts"][0])
        self.assertIn("codex/lane-a", report["conflicts"][0])

    def test_same_named_new_file_in_idle_lane_only_warns(self):
        self.lane("lane-old", {"prog/new.py": "old\n"}, days_ago=3)
        self.stage({"prog/new.py": "mine\n"})
        report = self.report()
        self.assert_passes(report)
        self.assertIn("codex/lane-old", "\n".join(report["notes"]))


class ExistingConflictTests(PreciseGateCase):
    def test_conflict_that_already_existed_is_not_blamed_on_this_commit(self):
        self.lane("lane-a", {"doc.md": body(line3="车道甲")})
        self.master_moves({"doc.md": body(line3="主干")})
        self.stage({"doc.md": body(line3="主干", line20="当前")})
        report = self.report()
        self.assert_passes(report)
        notes = "\n".join(report["notes"])
        self.assertIn("codex/lane-a", notes)
        self.assertIn("此前已", notes)

    def test_new_hunk_in_an_already_conflicting_file_is_rejected(self):
        self.lane("lane-a", {"doc.md": body(line3="车道甲", line20="车道甲二")})
        self.master_moves({"doc.md": body(line3="主干")})
        self.stage({"doc.md": body(line3="主干", line20="当前")})
        report = self.report()
        self.assertEqual(len(report["conflicts"]), 1)
        self.assertIn("codex/lane-a", report["conflicts"][0])

    def test_edit_inside_an_existing_conflict_region_is_rejected(self):
        # 冲突段数没变，但这一段的内容被本次提交改了：合入的人要多对一个版本，按新冲突算。
        self.lane("lane-a", {"doc.md": body(line3="车道甲")})
        self.master_moves({"doc.md": body(line3="主干")})
        self.stage({"doc.md": body(line3="当前")})
        report = self.report()
        self.assertEqual(len(report["conflicts"]), 1)
        self.assertIn("codex/lane-a", report["conflicts"][0])

    def test_adopting_the_lane_wording_removes_the_conflict(self):
        # R3950 实录：主干与对方已经冲突，本轮把这一行改成与对方逐字相同，冲突消失，应当放行。
        self.lane("lane-a", {"doc.md": body(line3="车道甲")})
        self.master_moves({"doc.md": body(line3="主干")})
        self.stage({"doc.md": body(line3="车道甲")})
        self.assert_passes(self.report())


class TrialMergeHygieneTests(PreciseGateCase):
    def snapshot(self):
        """对象库计数、索引字节、``.git`` 顶层文件名（不含缓存文件）。不调 ``git status``：它自己会刷新索引。"""
        index = hashlib.sha256((self.repo / ".git" / "index").read_bytes()).hexdigest()
        names = sorted(entry.name for entry in (self.repo / ".git").iterdir() if entry.name != scope.CACHE_NAME)
        return git(self.repo, "count-objects", "-v"), index, names

    def conflicting_setup(self):
        self.lane("lane-a", {"doc.md": body(line3="车道甲")})
        self.lane("lane-b", {"doc.md": body(line27="车道乙")})
        self.stage({"doc.md": body(line3="当前")})

    def test_trial_merge_leaves_objects_and_index_untouched(self):
        self.conflicting_setup()
        before = self.snapshot()
        self.assertEqual(len(self.report()["conflicts"]), 1)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(git(self.repo, "status", "--porcelain"), "M  doc.md")

    def test_repeated_check_reuses_cached_trial_merge(self):
        self.conflicting_setup()
        first = self.report()
        self.assertTrue((self.repo / ".git" / scope.CACHE_NAME).is_file())
        with mock.patch.object(scope, "_run_merge_tree", side_effect=AssertionError("缓存命中后不应重算")):
            self.assertEqual(self.report(), first)

    def test_cache_is_not_used_after_the_lane_tip_moves(self):
        self.lane("lane-a", {"doc.md": body(line27="车道甲")})
        self.stage({"doc.md": body(line3="当前")})
        self.assertEqual(self.report()["conflicts"], [])
        self.lane("lane-a", {"doc.md": body(line3="车道甲改了同一行", line27="车道甲")})
        self.assertEqual(len(self.report()["conflicts"]), 1)

    def test_damaged_cache_file_is_ignored(self):
        self.conflicting_setup()
        (self.repo / ".git" / scope.CACHE_NAME).write_text("{bad", encoding="utf-8")
        self.assertEqual(len(self.report()["conflicts"]), 1)

    def test_cache_from_another_format_version_is_ignored(self):
        # 缓存内容的含义变过而版本号没动时，旧缓存会被当成「那时没有这些冲突」（R3956 开发中途出过）。
        self.conflicting_setup()
        first = self.report()
        cache = self.repo / ".git" / scope.CACHE_NAME
        data = json.loads(cache.read_text(encoding="utf-8"))
        self.assertEqual(data["version"], scope.CACHE_VERSION)
        data["version"] = scope.CACHE_VERSION - 1
        data["entries"] = {key: {"at": 0, "conflicts": {}} for key in data["entries"]}
        cache.write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual(self.report(), first)

    def test_failed_trial_merge_only_warns(self):
        self.conflicting_setup()
        with mock.patch.object(scope, "_run_merge_tree", side_effect=RuntimeError("boom")):
            report = self.report()
        self.assertEqual(report["conflicts"], [])
        skipped = "\n".join(report["skipped"])
        self.assertIn("boom", skipped)
        self.assertIn("codex/lane-a", skipped)
        self.assertIn("doc.md", skipped)


class CommandLineTests(PreciseGateCase):
    def test_commit_tool_prints_notes_for_mergeable_overlap(self):
        self.lane("lane-a", {"doc.md": body(line3="车道甲")})
        self.stage({"doc.md": body(line15="当前")})
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = commit_round.check_scope_overlap(self.repo)
        self.assertEqual(code, 0)
        self.assertIn("提示：", err.getvalue())
        self.assertIn("codex/lane-a", err.getvalue())

    def test_staged_flag_reports_the_gate_verdict(self):
        self.lane("lane-a", {"doc.md": body(line3="车道甲")})
        self.stage({"doc.md": body(line15="当前")})
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = scope.main(["--root", str(self.repo), "--staged"])
        self.assertEqual(code, 0)
        self.assertIn("codex/lane-a", out.getvalue())
        self.stage({"doc.md": body(line3="当前")})
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = scope.main(["--root", str(self.repo), "--staged", "--json"])
        self.assertEqual(code, 5)
        self.assertEqual(len(json.loads(out.getvalue())["conflicts"]), 1)


if __name__ == "__main__":
    unittest.main()
