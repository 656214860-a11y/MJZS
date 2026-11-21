"""B3 车道注册/租约心跳/合并队列/源码口径 测试。"""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "维护记录" / "基准脚本"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import lane_registry  # noqa: E402
import merge_queue  # noqa: E402
import round_claim  # noqa: E402


class LaneRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.common = Path(self.tmp.name)

    def _register(self, lane="wt-a", branch="codex/a", top="D:/wt-a", **kw):
        with mock.patch.object(lane_registry, "_worktree_info", return_value=(lane, branch, top)):
            return lane_registry.register(Path("."), self.common, **kw)

    def test_register_and_heartbeat_refresh_last_seen(self):
        e1 = self._register(now=1000.0)
        self.assertEqual(e1["branch"], "codex/a")
        self.assertEqual(e1["last_seen"], 1000.0)
        rows = lane_registry.list_lanes(self.common, now=1000.0 + 3600)
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["idle_hours"], 1.0)
        self.assertFalse(rows[0]["stale"])
        self._register(now=1000.0 + 7200)
        rows = lane_registry.list_lanes(self.common, now=1000.0 + 7200 + 8 * 3600)
        self.assertFalse(rows[0]["stale"])  # 8h < 7天阈值
        rows = lane_registry.list_lanes(self.common, now=1000.0 + 7200 + 8 * 24 * 3600)
        self.assertTrue(rows[0]["stale"])

    def test_corrupt_lanes_json_degrades_to_empty(self):
        (self.common / "lanes.json").write_text("{bad", encoding="utf-8")
        self.assertEqual(lane_registry.list_lanes(self.common), [])

    def test_non_dict_lane_entries_degrade_to_empty(self):
        """JSON 合法但条目不是对象（手改/损坏写入）同样按空表降级，不让提交门禁崩。"""
        (self.common / "lanes.json").write_text(
            json.dumps({"lanes": {"bad": "oops", "worse": 7}}), encoding="utf-8")
        self.assertEqual(lane_registry.list_lanes(self.common), [])
        entry = self._register(now=1000.0)
        self.assertEqual(entry["branch"], "codex/a")
        self.assertNotIn("bad", lane_registry._read(lane_registry.lanes_path(self.common))["lanes"])

    def test_role_validation_falls_back_to_existing(self):
        self._register(role="gui")
        e = self._register(role="bogus")
        self.assertEqual(e["role"], "gui")

    def test_unspecified_role_preserves_existing_and_defaults_dev(self):
        self._register(role="merge")
        e = self._register()
        self.assertEqual(e["role"], "merge")
        e2 = self._register(lane="wt-b", top="D:/wt-b")
        self.assertEqual(e2["role"], "dev")


class WorktreeInfoEncodingTests(unittest.TestCase):
    """R2-G3 T1：默认本地编码（cp936）下 _worktree_info 仍能读出 git 的 UTF-8 输出。"""

    def test_worktree_info_with_chinese_path_under_default_encoding(self):
        scripts = Path(__file__).resolve().parents[1] / "维护记录" / "基准脚本"
        with tempfile.TemporaryDirectory(prefix="车道-") as lane_dir:
            root = Path(lane_dir)
            subprocess.run(["git", "init", "-q"], cwd=str(root), check=True, capture_output=True)
            env = {key: value for key, value in os.environ.items()
                   if key.upper() not in ("PYTHONUTF8", "PYTHONIOENCODING")}
            child = ("import json, sys;"
                     "sys.path.insert(0, sys.argv[1]);"
                     "from pathlib import Path;"
                     "import lane_registry;"
                     "print(json.dumps(lane_registry._worktree_info(Path(sys.argv[2]))))")
            done = subprocess.run([sys.executable, "-B", "-c", child, str(scripts), str(root)],
                                  capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", env=env, timeout=30)
            self.assertNotIn("UnicodeDecodeError", done.stderr)
            self.assertEqual(done.returncode, 0, done.stderr)
            lane, _branch, _top = json.loads(done.stdout)
            self.assertEqual(lane, root.name)


class MergeQueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.common = Path(self.tmp.name)

    def test_enqueue_list_dedup_and_order(self):
        a = merge_queue.enqueue(self.common, "codex/a", "A 轮", owner="lane-a")
        b = merge_queue.enqueue(self.common, "codex/b", "B 轮", owner="lane-b")
        self.assertEqual(a["id"], "mq-1")
        self.assertEqual(b["id"], "mq-2")
        with self.assertRaises(RuntimeError):
            merge_queue.enqueue(self.common, "codex/a", "dup")
        items = merge_queue.list_items(self.common)
        self.assertEqual([i["branch"] for i in items], ["codex/a", "codex/b"])

    def test_pop_next_marks_serving_and_stale_requeues(self):
        merge_queue.enqueue(self.common, "codex/a", "A")
        item = merge_queue._pop_next(self.common, time.time())
        self.assertEqual(item["branch"], "codex/a")
        self.assertIsNone(merge_queue._pop_next(self.common, time.time()))  # serving 中不重复出队
        # serving 超龄 → 回 pending
        path = merge_queue.queue_path(self.common)
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["items"][0]["serving_since"] = "2000-01-01T00:00:00+08:00"
        path.write_text(json.dumps(doc), encoding="utf-8")
        item2 = merge_queue._pop_next(self.common, time.time())
        self.assertEqual(item2["branch"], "codex/a")

    def test_finish_marks_done_with_round(self):
        item = merge_queue.enqueue(self.common, "codex/a", "A")
        merge_queue._finish(self.common, item["id"], "done", round_no=3120)
        done = merge_queue.list_items(self.common)[0]
        self.assertEqual(done["status"], "done")
        self.assertEqual(done["round"], 3120)

    def test_serve_records_rebase_return_without_a_round(self):
        merge_queue.enqueue(self.common, "codex/a", "A", owner="lane")
        done = subprocess.CompletedProcess([], 5)
        with mock.patch.object(merge_queue.subprocess, "run", return_value=done):
            rc = merge_queue.serve(self.common, once=True)
        self.assertEqual(rc, 5)
        item = merge_queue.list_items(self.common)[0]
        self.assertEqual(item["status"], "failed")
        self.assertIsNone(item["round"])
        self.assertIn("变基", item["note"])
        self.assertIn("未领号", item["note"])


class RenewTaskTests(unittest.TestCase):
    """队列租约心跳：owner 续约成功；他人/未认领拒绝。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.common = Path(self.tmp.name)
        self.queue = self.common / "maintenance-queue.json"
        now = datetime.now().astimezone()
        self.queue.write_text(json.dumps({
            "lease_minutes": 60,
            "items": [{"id": "T1", "status": "claimed", "owner": "alice",
                       "lease_minutes": 60,
                       "lease_until": (now + timedelta(minutes=10)).isoformat(timespec="seconds")}],
        }), encoding="utf-8")

    def test_owner_renew_extends_lease(self):
        before = json.loads(self.queue.read_text(encoding="utf-8"))["items"][0]["lease_until"]
        item = round_claim.renew_task(common_dir=self.common, queue_path=self.queue,
                                      task_id="T1", owner="alice", lease_minutes=120)
        after = item["lease_until"]
        self.assertGreater(datetime.fromisoformat(after), datetime.fromisoformat(before))
        self.assertEqual(item["lease_minutes"], 120)

    def test_foreign_owner_and_unclaimed_rejected(self):
        with self.assertRaises(RuntimeError):
            round_claim.renew_task(common_dir=self.common, queue_path=self.queue,
                                   task_id="T1", owner="bob")
        doc = json.loads(self.queue.read_text(encoding="utf-8"))
        doc["items"][0]["status"] = "pending"
        doc["items"][0]["owner"] = ""
        doc["items"][0]["lease_until"] = ""
        self.queue.write_text(json.dumps(doc), encoding="utf-8")
        with self.assertRaises(RuntimeError):
            round_claim.renew_task(common_dir=self.common, queue_path=self.queue,
                                   task_id="T1", owner="alice")


class AheadSourceOnlyTests(unittest.TestCase):
    """源码口径：rev-list 只数 *.py/*.pyw 提交（函数级，用假 subprocess 不易——直接验 pathspec 构造）。"""

    def test_source_pathspecs_cover_py_and_pyw(self):
        # 口径定义固化：glob **/*.py 与 **/*.pyw，文档/结果/台账不计
        src = Path(round_claim.__file__).read_text(encoding="utf-8")
        self.assertIn(":(top,glob)**/*.py", src)
        self.assertIn(":(top,glob)**/*.pyw", src)


if __name__ == "__main__":
    unittest.main()

