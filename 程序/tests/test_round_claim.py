"""共享轮次号分配器的并发与恢复回归。"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path


PROGRAM = Path(__file__).resolve().parent.parent
SCRIPT = PROGRAM / "维护记录" / "基准脚本" / "round_claim.py"
spec = importlib.util.spec_from_file_location("round_claim_for_tests", SCRIPT)
round_claim = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = round_claim
spec.loader.exec_module(round_claim)


class RoundClaimTests(unittest.TestCase):
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
            self.assertEqual(round_claim.claim_next(common_dir=root / ".git", tasks_round=self._tasks(root, 868)), 869)

    def test_claim_uses_atomic_counter_after_result_directory_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            common = root / ".git"
            tasks = self._tasks(root, 2)
            self.assertEqual(round_claim.claim_next(common_dir=common, tasks_round=tasks), 3)
            self.assertEqual(round_claim.claim_next(common_dir=common, tasks_round=tasks), 4)
            self.assertEqual(json.loads((common / "round-counter.json").read_text(encoding="utf-8"))["last_claimed"], 4)

    def test_concurrent_claims_are_unique_and_contiguous(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            common = root / ".git"
            tasks = self._tasks(root, 40)
            values: list[int] = []
            errors: list[BaseException] = []

            def worker():
                try:
                    values.append(round_claim.claim_next(common_dir=common, tasks_round=tasks))
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
