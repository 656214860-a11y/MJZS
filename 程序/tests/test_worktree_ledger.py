"""工作树台账：真实临时 Git 仓库及只读回收计划。"""
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "维护记录/基准脚本/worktree_ledger.py"
SPEC = importlib.util.spec_from_file_location("worktree_ledger_tests", SCRIPT)
ledger = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ledger)

RELOCATE_SCRIPT = Path(__file__).resolve().parents[1] / "scripts/relocate_lanes.py"
RELOCATE_SPEC = importlib.util.spec_from_file_location("relocate_lanes_tests", RELOCATE_SCRIPT)
relocate = importlib.util.module_from_spec(RELOCATE_SPEC)
sys.modules[RELOCATE_SPEC.name] = relocate
RELOCATE_SPEC.loader.exec_module(relocate)


class WorktreeLedgerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.container = Path(temporary.name)
        self.repo = self.container / "main"
        self.repo.mkdir()
        ledger.git(self.repo, "init", "-b", "master")
        ledger.git(self.repo, "config", "user.name", "Ledger Test")
        ledger.git(self.repo, "config", "user.email", "ledger@example.invalid")
        ledger.git(self.repo, "commit", "--allow-empty", "-m", "seed")
        self.empty, self.detached = [self.container / name for name in ("empty", "detached")]
        ledger.git(self.repo, "worktree", "add", "-b", "codex/empty", str(self.empty))
        ledger.git(self.repo, "worktree", "add", "--detach", str(self.detached))

    def rows(self):
        return {Path(row["path"]).name: row for row in ledger.collect(self.repo)["worktrees"]}

    def test_real_trees_detached_block_and_zero_ahead_recycle(self):
        before = ledger.git(self.repo, "status", "--porcelain")
        rows = self.rows()
        self.assertEqual(rows["main"]["action"], "KEEP")
        self.assertEqual(rows["empty"]["action"], "RECYCLE")
        self.assertEqual((rows["empty"]["ahead"], rows["empty"]["behind"]), (0, 0))
        self.assertEqual(rows["detached"]["action"], "BLOCK")
        self.assertTrue(rows["detached"]["detached"])
        self.assertFalse(rows["detached"]["orphan"])
        data = ledger.collect(self.repo)
        commands = ledger.plan(data, self.repo)
        self.assertTrue(any("worktree remove" in command for command in commands))
        self.assertTrue(self.empty.is_dir())
        self.assertEqual(ledger.git(self.repo, "status", "--porcelain"), before)

    def test_unique_detached_commit_is_orphan_and_branch_ahead_is_kept(self):
        ledger.git(self.detached, "commit", "--allow-empty", "-m", "orphan")
        ledger.git(self.empty, "commit", "--allow-empty", "-m", "branch work")
        rows = self.rows()
        self.assertTrue(rows["detached"]["orphan"])
        self.assertEqual(rows["detached"]["action"], "BLOCK")
        self.assertEqual(rows["empty"]["ahead"], 1)
        self.assertEqual(rows["empty"]["action"], "KEEP")

    def test_age_threshold_dirty_and_lease_precedence(self):
        row = {"ahead": 1, "behind": 21, "idle_hours": 48}
        self.assertEqual(ledger.classify(row)[0], "RECYCLE")
        self.assertEqual(ledger.classify(dict(row, idle_hours=47.99))[0], "KEEP")
        self.assertEqual(ledger.classify(dict(row, behind=20))[0], "KEEP")
        self.assertEqual(ledger.classify(dict(row, dirty=True))[0], "KEEP")
        self.assertEqual(ledger.classify(dict(row, leases=["active"]))[0], "KEEP")
        self.assertEqual(ledger.classify(dict(row, leases=["active"], detached=True))[0], "BLOCK")

    def test_queue_lease_maps_to_tree_and_expired_does_not_protect(self):
        queue = self.repo / ".git/maintenance-queue.json"
        queue.write_text(json.dumps({"items": [
            {"id": "active", "status": "claimed", "worktree": str(self.empty),
             "lease_until": "2099-01-01T00:00:00+00:00", "owner": "test"},
            {"id": "old", "status": "claimed", "lease_until": "2000-01-01T00:00:00+00:00"}
        ]}), encoding="utf-8")
        rows = self.rows()
        self.assertEqual(rows["empty"]["action"], "KEEP")
        self.assertEqual([item["id"] for item in rows["empty"]["leases"]], ["active"])
        self.assertFalse(rows["main"]["leases"])

    def test_missing_management_and_external_residuals_are_only_planned(self):
        entry = self.repo / ".git/worktrees/stale"
        entry.mkdir()
        (entry / "gitdir").write_text(str(self.container / "gone/.git"), encoding="utf-8")
        residual = self.container / "residual"
        residual.mkdir()
        data = ledger.collect(self.repo, scan_roots=[self.container])
        rows = {Path(row["path"]).name: row for row in data["residuals"]}
        self.assertEqual(rows["stale"]["action"], "RECYCLE")
        self.assertEqual(rows["residual"]["action"], "RECYCLE")
        self.assertTrue(any("prune --dry-run" in line for line in ledger.plan(data, self.repo)))
        self.assertTrue(entry.exists())
        self.assertTrue(residual.exists())

    def test_reparse_point_is_not_traversed(self):
        candidate = self.container / "link"
        candidate.mkdir()
        with mock.patch.object(ledger, "is_link", side_effect=lambda path: path == candidate):
            rows = ledger.scan_residuals(self.container, {self.repo, self.empty, self.detached})
        self.assertEqual(rows[0]["action"], "KEEP")
        self.assertNotIn("entries", rows[0])

    def test_cli_json_and_plan_are_read_only(self):
        result = subprocess.run([__import__("sys").executable, str(SCRIPT), "--root", str(self.repo),
                                 "--format", "json", "--plan"], capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(len(data["worktrees"]), 3)
        self.assertIn("plan", data)
        self.assertTrue(self.empty.exists())


def git(*args, cwd=None):
    return subprocess.run(["git", "-c", "core.quotepath=false", *args],
                          cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def snapshot(root):
    root = Path(root)
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*") if p.is_file() and not p.is_symlink()}


def porcelain(lane):
    done = git("-C", str(lane), "status", "--porcelain")
    done.check_returncode()
    return done.stdout


def porcelain_map(source):
    result = {}
    for lane in sorted(Path(source).iterdir()):
        if (lane / ".git").exists():
            result[lane.name] = porcelain(lane)
    return result


def worktree_count(repo):
    done = git("-C", str(repo), "worktree", "list", "--porcelain")
    done.check_returncode()
    return sum(1 for line in done.stdout.splitlines() if line.startswith("worktree "))


def idle_dispatch(*_args, **_kwargs):
    return ("idle", "队列空闲")


def empty_cwds(*_args, **_kwargs):
    return []


def free_probes(**extra):
    probes = {"dispatch": idle_dispatch, "cwds": empty_cwds}
    probes.update(extra)
    return probes


class RelocateLanesTests(unittest.TestCase):
    """车道迁固态盘脚本（junction 方案）：全部用例只在临时目录建假仓库与假车道。"""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.container = Path(temporary.name)
        self.repo = self.container / "repo"
        self.repo.mkdir()
        git("init", "-b", "master", "--quiet", str(self.repo)).check_returncode()
        git("-C", str(self.repo), "config", "user.name", "Relocate Test").check_returncode()
        git("-C", str(self.repo), "config", "user.email", "relocate@example.invalid").check_returncode()
        (self.repo / "base.txt").write_bytes(b"base")
        git("-C", str(self.repo), "add", "base.txt").check_returncode()
        git("-C", str(self.repo), "commit", "-m", "seed", "--quiet").check_returncode()
        self.source = self.container / "hub" / ".agents" / "worktrees"
        self.source.mkdir(parents=True)
        self.lanes = []
        for name in ("lane_a", "lane_b", "lane_c"):
            lane = self.source / name
            done = git("-C", str(self.repo), "worktree", "add", "-b",
                       "codex/" + name, str(lane))
            self.assertEqual(done.returncode, 0, done.stderr)
            (lane / "payload.bin").write_bytes(name.encode() * 64)
            self.lanes.append(lane)
        dirty = self.source / "lane_b"
        (dirty / "base.txt").write_bytes(b"modified")
        (dirty / "scratch.txt").write_bytes(b"untracked")
        self.target = self.container / "ssd" / "dev-lanes"
        self.status_before = porcelain_map(self.source)
        self.count_before = worktree_count(self.repo)

    def test_relocate_plan_is_read_only_and_reports_facts(self):
        before = snapshot(self.source)
        out = io.StringIO()
        with redirect_stdout(out):
            code = relocate.main(["--plan", "--source", str(self.source),
                                  "--target", str(self.target)],
                                 probes=free_probes())
        text = out.getvalue()
        self.assertEqual(code, 0, text)
        self.assertEqual(snapshot(self.source), before)
        self.assertFalse(self.target.exists())
        self.assertIn("lane_a", text)
        self.assertIn("lane_b", text)
        self.assertIn("lane_c", text)
        for token in ("字节", "余量", "worktree", "占用"):
            self.assertIn(token, text)

    def test_relocate_plan_reports_junction_state_when_already_relocated(self):
        code = relocate.apply(self.source, self.target, probes=free_probes())
        self.assertEqual(code, 0)
        out = io.StringIO()
        with redirect_stdout(out):
            code = relocate.main(["--plan", "--source", str(self.source),
                                  "--target", str(self.target)],
                                 probes=free_probes())
        self.assertEqual(code, 0)
        self.assertIn("junction", out.getvalue().lower())

    def test_relocate_apply_moves_through_junction_and_keeps_git_state(self):
        before = snapshot(self.source)
        code = relocate.apply(self.source, self.target, probes=free_probes())
        self.assertEqual(code, 0)
        self.assertTrue(self.source.is_junction())
        self.assertTrue((self.target / "lane_a" / "payload.bin").is_file())
        self.assertEqual(snapshot(self.source), before)
        self.assertEqual(porcelain_map(self.source), self.status_before)
        self.assertEqual(worktree_count(self.repo), self.count_before)
        toplevel = git("-C", str(self.source / "lane_a"),
                       "rev-parse", "--show-toplevel")
        self.assertEqual(toplevel.returncode, 0)

    def test_relocate_apply_ignores_same_drive_cwd_outside_source(self):
        before = snapshot(self.source)
        outside = self.container / "elsewhere"
        outside.mkdir()
        cwds = mock.Mock(return_value=[{"pid": 7, "name": "python.exe",
                                        "cwd": str(outside)}])
        code = relocate.apply(self.source, self.target,
                              probes=free_probes(cwds=cwds))
        self.assertEqual(code, 0)
        self.assertTrue(self.source.is_junction())
        self.assertEqual(snapshot(self.source), before)

    def test_relocate_apply_is_refused_when_target_drive_too_small(self):
        before = snapshot(self.source)
        tiny = mock.Mock(return_value=64)
        code = relocate.apply(self.source, self.target,
                              probes=free_probes(disk_free=tiny))
        self.assertNotEqual(code, 0)
        self.assertFalse(self.source.is_junction())
        self.assertFalse(self.target.exists())
        self.assertEqual(snapshot(self.source), before)

    def test_relocate_apply_is_refused_while_dispatch_in_flight(self):
        before = snapshot(self.source)
        busy = mock.Mock(return_value=("busy", "队列里有在派项"))
        code = relocate.apply(self.source, self.target,
                              probes=free_probes(dispatch=busy))
        self.assertNotEqual(code, 0)
        self.assertFalse(self.source.is_junction())
        self.assertEqual(snapshot(self.source), before)

    def test_relocate_apply_is_refused_when_dispatch_state_unknown_without_flag(self):
        before = snapshot(self.source)
        unknown = mock.Mock(return_value=("unknown", "读不到 cpa auto status"))
        code = relocate.apply(self.source, self.target,
                              probes=free_probes(dispatch=unknown))
        self.assertNotEqual(code, 0)
        code = relocate.apply(self.source, self.target, i_know_lanes_idle=True,
                              probes=free_probes(dispatch=unknown))
        self.assertEqual(code, 0)
        self.assertTrue(self.source.is_junction())
        self.assertEqual(snapshot(self.source), before)

    def test_relocate_apply_is_refused_while_lane_dir_occupied(self):
        before = snapshot(self.source)
        lane = str(self.source / "lane_a")
        cwds = mock.Mock(return_value=[{"pid": 4242, "name": "python.exe", "cwd": lane}])
        code = relocate.apply(self.source, self.target,
                              probes=free_probes(cwds=cwds))
        self.assertNotEqual(code, 0)
        self.assertFalse(self.source.is_junction())
        self.assertEqual(snapshot(self.source), before)

    def test_relocate_apply_is_refused_when_target_nonempty(self):
        before = snapshot(self.source)
        self.target.mkdir(parents=True)
        (self.target / "leftover.txt").write_bytes(b"x")
        code = relocate.apply(self.source, self.target, probes=free_probes())
        self.assertNotEqual(code, 0)
        self.assertFalse(self.source.is_junction())
        self.assertEqual(snapshot(self.source), before)
        self.assertEqual((self.target / "leftover.txt").read_bytes(), b"x")

    def test_relocate_rollback_restores_plain_directory(self):
        before = snapshot(self.source)
        self.assertEqual(relocate.apply(self.source, self.target,
                                        probes=free_probes()), 0)
        self.assertTrue(self.source.is_junction())
        code = relocate.rollback(self.source, self.target, probes=free_probes())
        self.assertEqual(code, 0)
        self.assertFalse(self.source.is_junction())
        self.assertTrue(self.source.is_dir())
        self.assertFalse(self.target.exists())
        self.assertEqual(snapshot(self.source), before)
        self.assertEqual(porcelain_map(self.source), self.status_before)
        self.assertEqual(worktree_count(self.repo), self.count_before)

    def test_relocate_rollback_without_junction_is_noop_refusal(self):
        code = relocate.rollback(self.source, self.target, probes=free_probes())
        self.assertNotEqual(code, 0)
        self.assertTrue(self.source.is_dir())
        self.assertFalse(self.target.exists())

    def test_relocate_queue_claimed_presence_check(self):
        queue = self.container / "maintenance-queue.json"
        self.assertIsNone(relocate._queue_claimed(queue))
        queue.write_text(json.dumps({"items": [
            {"id": "OPS-A", "status": "claimed", "lease_until": "2026-11-24T00:00:00+08:00"},
            {"id": "OPS-B", "status": "completed"}]}), encoding="utf-8")
        state, detail = relocate._queue_claimed(queue)
        self.assertEqual(state, "busy")
        self.assertIn("OPS-A", detail)
        queue.write_text(json.dumps({"items": [
            {"id": "OPS-B", "status": "completed"},
            {"id": "OPS-C", "status": "pending"}]}), encoding="utf-8")
        self.assertEqual(relocate._queue_claimed(queue)[0], "idle")

    def test_relocate_cli_apply_and_rollback_round_trip(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = relocate.main(["--apply", "--source", str(self.source),
                                  "--target", str(self.target)],
                                 probes=free_probes())
        self.assertEqual(code, 0, out.getvalue())
        self.assertTrue(self.source.is_junction())
        with redirect_stdout(io.StringIO()):
            code = relocate.main(["--rollback", "--source", str(self.source),
                                  "--target", str(self.target)],
                                 probes=free_probes())
        self.assertEqual(code, 0)
        self.assertFalse(self.source.is_junction())

