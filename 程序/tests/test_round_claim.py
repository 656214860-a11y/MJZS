"""共享轮次号分配器的并发与恢复回归。"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import subprocess
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock


PROGRAM = Path(__file__).resolve().parent.parent
SCRIPT = PROGRAM / "维护记录" / "基准脚本" / "round_claim.py"
spec = importlib.util.spec_from_file_location("round_claim_for_tests", SCRIPT)
round_claim = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = round_claim
spec.loader.exec_module(round_claim)


class RoundClaimTests(unittest.TestCase):
    def _init_repo(self, root: Path) -> None:
        subprocess.run(["git", "init", "--quiet", str(root)], check=True)

    def _tasks(self, root: Path, *rounds: int) -> Path:
        tasks = root / "tasks_round"
        tasks.mkdir()
        for number in rounds:
            (tasks / ("tasks_round_%s_result.md" % number)).write_text("# result\n", encoding="utf-8")
        return tasks

    def _queue(self, root: Path, *, status="pending", owner="", lease_until="", note="") -> Path:
        path = root / "任务队列.json"
        path.write_text(json.dumps({"items": [{"id": "T1", "status": status, "owner": owner,
                                                "lease_until": lease_until, "note": note}]}), encoding="utf-8")
        return path

    def test_claim_starts_after_existing_result_round(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._init_repo(root)
            self.assertEqual(round_claim.claim_next(common_dir=root / ".git", tasks_round=self._tasks(root, 868), root=root), 869)

    def test_claim_uses_atomic_counter_after_result_directory_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._init_repo(root)
            common = root / ".git"
            tasks = self._tasks(root, 2)
            self.assertEqual(round_claim.claim_next(common_dir=common, tasks_round=tasks, root=root), 3)
            self.assertEqual(round_claim.claim_next(common_dir=common, tasks_round=tasks, root=root), 4)
            self.assertEqual(json.loads((common / "round-counter.json").read_text(encoding="utf-8"))["last_claimed"], 4)

    def test_claim_catches_counter_up_to_all_refs_before_allocating(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "--quiet", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "-c", "user.name=Round Test", "-c",
                            "user.email=round@example.invalid", "commit", "--allow-empty", "-m", "R1016: historic"],
                           check=True)
            common = round_claim.git_common_dir(root)
            (common / round_claim.COUNTER_NAME).write_text('{"last_claimed": 997}\n', encoding="utf-8")
            with mock.patch('builtins.print') as printed:
                self.assertEqual(round_claim.claim_next(common_dir=common, tasks_round=self._tasks(root, 3), root=root), 1017)
            printed.assert_called_once_with("计数器已从 997 追平到 1016")

    def test_claim_records_owner_worktree_branch_and_time(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._init_repo(root)
            top = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"],
                                 capture_output=True, text=True, check=True).stdout.strip()
            branch = subprocess.run(["git", "-C", str(root), "symbolic-ref", "--quiet", "--short", "HEAD"],
                                    capture_output=True, text=True).stdout.strip()
            self.assertEqual(round_claim.claim_next(common_dir=root / ".git",
                                                    tasks_round=self._tasks(root), root=root), 1)
            claims = json.loads((root / ".git" / round_claim.CLAIMS_NAME).read_text(encoding="utf-8"))
            entry = claims["claims"]["1"]
            self.assertEqual(os.path.normcase(os.path.normpath(entry["worktree"])),
                             os.path.normcase(os.path.normpath(top)))
            self.assertEqual(entry["branch"], branch)
            self.assertTrue(entry["at"])

    def test_record_claim_backfills_owner_and_rejects_foreign_or_unallocated(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._init_repo(root)
            common = root / ".git"
            tasks = self._tasks(root)
            self.assertEqual(round_claim.claim_next(common_dir=common, tasks_round=tasks, root=root), 1)
            other = Path(temporary) / "other-lane"
            other.mkdir()
            counter = common / "round-counter.json"
            doc = json.loads(counter.read_text(encoding="utf-8"))
            doc["last_claimed"] = 3
            counter.write_text(json.dumps(doc), encoding="utf-8")
            claims_file = common / round_claim.CLAIMS_NAME
            claims_file.write_text(json.dumps({"claims": {
                "2": {"worktree": str(other), "branch": "codex/other", "at": "x"},
                "3": {"worktree": str(Path(temporary) / "gone-lane"),
                      "branch": "codex/gone", "at": "x"}}}), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "其他工作树"):
                round_claim.record_claim(common_dir=common, number=2, claimant_dir=root)
            with self.assertRaisesRegex(RuntimeError, "尚未分配"):
                round_claim.record_claim(common_dir=common, number=4, claimant_dir=root)
            entry = round_claim.record_claim(common_dir=common, number=1, claimant_dir=root)
            saved = json.loads(claims_file.read_text(encoding="utf-8"))["claims"]
            self.assertEqual(os.path.normcase(os.path.normpath(saved["2"]["worktree"])),
                             os.path.normcase(os.path.normpath(str(other))))
            self.assertEqual(os.path.normcase(os.path.normpath(saved["1"]["worktree"])),
                             os.path.normcase(os.path.normpath(entry["worktree"])))
            # 登记路径已不存在的失效记录允许补登到新位置。
            moved = round_claim.record_claim(common_dir=common, number=3, claimant_dir=root)
            saved = json.loads(claims_file.read_text(encoding="utf-8"))["claims"]
            self.assertEqual(os.path.normcase(os.path.normpath(saved["3"]["worktree"])),
                             os.path.normcase(os.path.normpath(moved["worktree"])))

    def test_concurrent_claims_are_unique_and_contiguous(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._init_repo(root)
            common = root / ".git"
            tasks = self._tasks(root, 40)
            values: list[int] = []
            errors: list[BaseException] = []

            def worker():
                try:
                    values.append(round_claim.claim_next(common_dir=common, tasks_round=tasks, root=root))
                except BaseException as exc:  # pragma: no cover - asserted below
                    errors.append(exc)

            threads = [threading.Thread(target=worker) for _ in range(8)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(errors, [])
            self.assertEqual(sorted(values), list(range(41, 49)))

    def test_claim_rejects_another_active_lease_and_release_restores_pending(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            now = datetime(2026, 10, 3, 14, tzinfo=timezone.utc)
            queue = self._queue(root)
            claimed = round_claim.claim_task(common_dir=root / ".git", queue_path=queue, task_id="T1",
                                             owner="alice", now=now)
            self.assertEqual(claimed["status"], "claimed")
            with self.assertRaises(RuntimeError):
                round_claim.claim_task(common_dir=root / ".git", queue_path=queue, task_id="T1",
                                       owner="bob", now=now)
            released = round_claim.release_task(common_dir=root / ".git", queue_path=queue, task_id="T1", owner="alice")
            self.assertEqual((released["status"], released["owner"], released["lease_until"]), ("pending", "", ""))

    def test_expired_lease_can_be_taken_over_with_note(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            queue = self._queue(root, status="claimed", owner="alice", lease_until="2026-10-03T12:00:00+00:00")
            claimed = round_claim.claim_task(common_dir=root / ".git", queue_path=queue, task_id="T1", owner="bob",
                                             now=datetime(2026, 10, 3, 13, tzinfo=timezone.utc))
            self.assertEqual(claimed["owner"], "bob")
            self.assertIn("alice 过期后由 bob 抢占", claimed["note"])

    def test_completed_task_cannot_be_claimed_again(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            queue = self._queue(root, status="completed", owner="alice")
            with self.assertRaisesRegex(RuntimeError, "已完成"):
                round_claim.claim_task(common_dir=root / ".git", queue_path=queue, task_id="T1", owner="bob")


class SharedWorktreeQueueTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / "main"
        self.repo.mkdir()
        self.git("init", str(self.repo))
        self.git("-C", str(self.repo), "-c", "user.name=Queue Test", "-c",
                 "user.email=queue@example.invalid", "commit", "--allow-empty", "-m", "seed")
        script = self.repo / "程序/维护记录/基准脚本/round_claim.py"
        script.parent.mkdir(parents=True)
        script.write_bytes(SCRIPT.read_bytes())
        lanes = script.with_name("lane_registry.py")
        lanes.write_bytes(SCRIPT.with_name("lane_registry.py").read_bytes())
        lease = script.with_name("lock_lease.py")
        lease.write_bytes(SCRIPT.with_name("lock_lease.py").read_bytes())
        entry = self.repo / "程序/scripts/dev.py"
        entry.parent.mkdir(parents=True)
        entry.write_bytes((PROGRAM / "scripts/dev.py").read_bytes())
        self.git("-C", str(self.repo), "add", "--", "程序/维护记录/基准脚本/round_claim.py",
                 "程序/维护记录/基准脚本/lane_registry.py",
                 "程序/维护记录/基准脚本/lock_lease.py", "程序/scripts/dev.py")
        self.git("-C", str(self.repo), "-c", "user.name=Queue Test", "-c",
                 "user.email=queue@example.invalid", "commit", "-m", "script fixture")
        self.trees = [self.root / name for name in ("A", "B")]
        for tree in self.trees:
            self.git("-C", str(self.repo), "worktree", "add", "--detach", str(tree))
        self.common = round_claim.git_common_dir(self.repo)

    def git(self, *args):
        result = subprocess.run(["git", *args], capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace")[-1500:])
        return result.stdout

    def snapshot(self, tree, items):
        path = tree / round_claim.SNAPSHOT
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"lease_minutes": 60, "items": items}), encoding="utf-8")
        return path

    def test_detached_next_cli_refuses_without_allocating_and_gives_switch_command(self):
        tree = self.trees[0]
        script = tree / "程序/维护记录/基准脚本/round_claim.py"
        result = subprocess.run([sys.executable, str(script), "next"], cwd=script.parent,
                                capture_output=True, timeout=20)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"detached HEAD", result.stderr)
        self.assertIn(b"git switch -c codex/r1-main", result.stderr)
        self.assertFalse((self.common / round_claim.COUNTER_NAME).exists())
        self.git("-C", str(tree), "switch", "-c", "codex/test-lane")
        result = subprocess.run([sys.executable, str(script), "next"], cwd=script.parent,
                                capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), b"1")

    def test_dirty_next_cli_refuses_on_master_without_allocating(self):
        script = self.repo / "程序/维护记录/基准脚本/round_claim.py"
        branch = self.git("-C", str(self.repo), "branch", "--show-current").strip().decode()
        self.git("-C", str(self.repo), "branch", "-m", "master") if branch != "master" else None
        (self.repo / "draft.txt").write_text("unfinished", encoding="utf-8")
        result = subprocess.run([sys.executable, str(script), "next"], cwd=script.parent,
                                capture_output=True, timeout=20)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("master".encode(), result.stderr)
        self.assertFalse((self.common / round_claim.COUNTER_NAME).exists())
        self.assertEqual(self.git("-C", str(self.repo), "branch", "--show-current").strip(), b"master")

    def test_dirty_next_cli_claims_then_parks_changes_on_lowercase_wip_branch(self):
        # 非 codex 的旧工作分支仍自动停泊，新建名称使用小写 kebab。
        tree = self.trees[0]
        script = tree / "程序/维护记录/基准脚本/round_claim.py"
        self.git("-C", str(tree), "switch", "-c", "old-task")
        (tree / "draft.txt").write_text("unfinished", encoding="utf-8")
        result = subprocess.run([sys.executable, str(script), "next"], cwd=script.parent,
                                capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), b"1")
        self.assertEqual(self.git("-C", str(tree), "branch", "--show-current").strip(), b"codex/wip-r1")
        self.assertEqual((tree / "draft.txt").read_text(encoding="utf-8"), "unfinished")
        claims = json.loads((self.common / round_claim.CLAIMS_NAME).read_text(encoding="utf-8"))
        self.assertEqual(claims["claims"]["1"]["branch"], "codex/wip-r1")
        lanes = json.loads((self.common / "lanes.json").read_text(encoding="utf-8"))["lanes"]
        self.assertEqual(lanes[tree.name]["branch"], "codex/wip-r1")

    def test_claim_new_branch_rejects_bad_names_before_any_state_write(self):
        tree = self.trees[0]
        self.git("-C", str(tree), "switch", "-c", "codex/existing-task")
        entry = tree / "程序/scripts/dev.py"
        for name in ("", "codex/", "codex/Whitelist-framework", "codex/white_list",
                     "codex/task/nested", "codex/-task", "codex/task-", "codex/task--name",
                     "task-name", "codex/task name"):
            with self.subTest(branch=name):
                before = sorted(path.name for path in self.common.iterdir())
                result = subprocess.run([sys.executable, "-B", str(entry), "claim", "--branch", name],
                                        cwd=entry.parent, capture_output=True, timeout=20)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn(b"codex/<lowercase-kebab-task>", result.stderr)
                self.assertEqual(sorted(path.name for path in self.common.iterdir()), before)
                self.assertFalse((self.common / round_claim.COUNTER_NAME).exists())
                self.assertEqual(self.git("-C", str(tree), "branch", "--show-current").strip(),
                                 b"codex/existing-task")

    def test_dev_claim_forwards_valid_new_branch_and_preserves_claim_registration(self):
        tree = self.trees[0]
        self.git("-C", str(tree), "switch", "-c", "codex/existing-task")
        entry = tree / "程序/scripts/dev.py"
        result = subprocess.run([sys.executable, "-B", str(entry), "claim", "--branch",
                                 "codex/whitelist-framework"], cwd=entry.parent,
                                capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), b"1")
        self.assertEqual(self.git("-C", str(tree), "branch", "--show-current").strip(),
                         b"codex/whitelist-framework")
        claims = json.loads((self.common / round_claim.CLAIMS_NAME).read_text(encoding="utf-8"))
        self.assertEqual(claims["claims"]["1"]["branch"], "codex/whitelist-framework")
        self.assertEqual(Path(claims["claims"]["1"]["worktree"]), tree)
        lanes = json.loads((self.common / "lanes.json").read_text(encoding="utf-8"))["lanes"]
        self.assertEqual(lanes[tree.name]["branch"], "codex/whitelist-framework")
        self.assertEqual(Path(lanes[tree.name]["worktree"]), tree)

    def test_existing_dirty_codex_branches_are_not_renamed(self):
        for tree, branch in zip(self.trees, ("codex/whitelist-framework", "codex/wip-R987")):
            with self.subTest(branch=branch):
                self.git("-C", str(tree), "switch", "-c", branch)
                draft = tree / "draft.txt"
                draft.write_text("unfinished", encoding="utf-8")
                script = tree / "程序/维护记录/基准脚本/round_claim.py"
                result = subprocess.run([sys.executable, "-B", str(script), "next"], cwd=script.parent,
                                        capture_output=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.git("-C", str(tree), "branch", "--show-current").strip().decode(), branch)
                self.assertEqual(draft.read_text(encoding="utf-8"), "unfinished")

    def test_ahead_over_limit_refuses_next_without_allocating(self):
        tree = self.trees[0]
        script = tree / "程序/维护记录/基准脚本/round_claim.py"
        self.git("-C", str(tree), "switch", "-c", "codex/far-ahead")
        for index in range(11):
            (tree / ("commit-%d.py" % index)).write_text("x = %d" % index, encoding="utf-8")
            self.git("-C", str(tree), "add", ".")
            self.git("-C", str(tree), "-c", "user.name=Queue Test", "-c",
                     "user.email=queue@example.invalid", "commit", "-m", "far %d" % index)
        result = subprocess.run([sys.executable, str(script), "next"], cwd=script.parent,
                                capture_output=True, timeout=30,
                                env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("领先 master".encode(), result.stderr)
        self.assertFalse((self.common / round_claim.COUNTER_NAME).exists())

    def test_ahead_within_limit_allows_next(self):
        tree = self.trees[0]
        script = tree / "程序/维护记录/基准脚本/round_claim.py"
        self.git("-C", str(tree), "switch", "-c", "codex/near-ahead")
        (tree / "one.py").write_text("x = 1", encoding="utf-8")
        self.git("-C", str(tree), "add", ".")
        self.git("-C", str(tree), "-c", "user.name=Queue Test", "-c",
                 "user.email=queue@example.invalid", "commit", "-m", "near 1")
        result = subprocess.run([sys.executable, str(script), "next"], cwd=script.parent,
                                capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), b"1")

    def test_two_worktrees_cannot_claim_same_id_and_export_is_identical(self):
        self.snapshot(self.trees[0], [{"id": "T1", "status": "pending"}])
        queue = self.common / round_claim.QUEUE_NAME
        round_claim.claim_task(common_dir=self.common, queue_path=queue, root=self.trees[0],
                               task_id="T1", owner="alice")
        with self.assertRaisesRegex(RuntimeError, "alice"):
            round_claim.claim_task(common_dir=round_claim.git_common_dir(self.trees[1]),
                                   queue_path=queue, root=self.trees[1], task_id="T1", owner="bob")
        self.assertEqual(queue.read_bytes(), (self.trees[0] / round_claim.SNAPSHOT).read_bytes())
        round_claim.release_task(common_dir=self.common, queue_path=queue, root=self.trees[0],
                                 task_id="T1", owner="alice")
        round_claim.claim_task(common_dir=self.common, queue_path=queue, root=self.trees[1],
                               task_id="T1", owner="bob")
        self.assertEqual(queue.read_bytes(), (self.trees[1] / round_claim.SNAPSHOT).read_bytes())

    def test_seed_union_12_and_20_preserves_completed_notes_and_latest_lease(self):
        first = [{"id": str(i), "status": "pending", "note": "A"} for i in range(12)]
        second = [{"id": str(i), "status": "claimed", "owner": "B", "note": "B",
                   "lease_until": "2026-10-04T01:00:00+00:00"} for i in range(6, 26)]
        first[6]["status"] = "completed"
        first[7].update(status="claimed", owner="A", lease_until="2026-10-04T02:00:00+00:00")
        self.snapshot(self.trees[0], first)
        self.snapshot(self.trees[1], second)
        queue = round_claim.seed_queue(self.common, self.repo)
        items = {item["id"]: item for item in round_claim._read_queue(queue)["items"]}
        self.assertEqual(set(items), set(map(str, range(26))))
        self.assertEqual(items["6"]["status"], "completed")
        self.assertEqual(items["7"]["owner"], "A")
        self.assertIn("A", items["6"]["note"])
        self.assertIn("B", items["6"]["note"])
        original = queue.read_bytes()
        self.snapshot(self.trees[0], [{"id": "should-not-reseed", "status": "pending"}])
        round_claim.seed_queue(self.common, self.repo)
        self.assertEqual(original, queue.read_bytes())

    def test_show_and_validate_do_not_lock_or_rewrite_initialized_queue(self):
        self.snapshot(self.repo, [{"id": "T1", "status": "pending"}])
        queue = round_claim.seed_queue(self.common, self.repo)
        before = queue.stat().st_mtime_ns
        with mock.patch.object(round_claim, 'git_common_dir', return_value=self.common), \
             mock.patch.object(round_claim, 'shared_lock', side_effect=AssertionError("write lock")), \
             mock.patch('builtins.print'):
            self.assertEqual(round_claim.main(["show", "--queue", str(queue)]), 0)
            self.assertEqual(round_claim.main(["validate", "--queue", str(queue)]), 0)
        self.assertEqual(before, queue.stat().st_mtime_ns)

    def test_validate_duplicate_empty_owner_and_inconsistent_lease(self):
        now = datetime(2026, 10, 4, tzinfo=timezone.utc)
        payload = {"items": [{"id": "T", "status": "claimed", "owner": "",
                              "lease_until": "2026-10-04T10:00:00+00:00"},
                             {"id": "T", "status": "pending"}]}
        errors, warnings = round_claim.validate_queue(payload, now)
        self.assertEqual(len(errors), 2)
        self.assertEqual(len(warnings), 1)
        for empty_owner in (None, " ", 0):
            with self.subTest(owner=empty_owner):
                payload["items"][0]["owner"] = empty_owner
                self.assertEqual(len(round_claim.validate_queue(payload, now)[0]), 2)
        payload["items"] = [{"id": "T", "status": "claimed", "owner": "A", "lease_minutes": 60,
                              "lease_until": "2026-10-04T01:00:00+00:00"}]
        self.assertEqual(round_claim.validate_queue(payload, now), ([], []))

    def test_stale_claim_lock_is_reclaimed_and_fresh_heartbeat_blocks(self):
        import time
        with tempfile.TemporaryDirectory() as tmp:
            common = Path(tmp)
            stale = common / round_claim.LOCK_NAME
            stale.write_text(json.dumps({
                "pid": 2 ** 22 + 3, "token": "old",
                "heartbeat_at": time.time() - 300, "created_at": time.time() - 300,
            }), encoding="utf-8")
            lock = round_claim._acquire_lock(common, timeout=1)
            try:
                body = json.loads(lock.read_text(encoding="utf-8"))
                self.assertNotEqual(body["token"], "old")
                self.assertGreater(body["heartbeat_at"], time.time() - 5)
            finally:
                round_claim.lock_lease.release(lock)
                lock.unlink(missing_ok=True)
            fresh = common / round_claim.LOCK_NAME
            fresh.write_text(json.dumps({
                "pid": 2 ** 22 + 3, "token": "live",
                "heartbeat_at": time.time(), "created_at": time.time(),
            }), encoding="utf-8")
            with self.assertRaises(TimeoutError):
                round_claim._acquire_lock(common, timeout=0.2)
            self.assertEqual(json.loads(fresh.read_text(encoding="utf-8"))["token"], "live")
            fresh.unlink()
            with round_claim.shared_lock(common):
                self.assertTrue((common / round_claim.LOCK_NAME).exists())
            self.assertFalse((common / round_claim.LOCK_NAME).exists())
