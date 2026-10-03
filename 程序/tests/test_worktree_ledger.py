"""工作树台账：真实临时 Git 仓库及只读回收计划。"""
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "维护记录/基准脚本/worktree_ledger.py"
SPEC = importlib.util.spec_from_file_location("worktree_ledger_tests", SCRIPT)
ledger = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ledger)


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

