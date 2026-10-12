# -*- coding: utf-8 -*-
"""O38：回收批次「写前计划 → 逐项状态 → 最终提交」，失败／中断可回滚或恢复。"""
import errno
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import storage_maintenance
from storage_maintenance import (BATCH_COMMITTED, BATCH_PLANNED, BATCH_ROLLED_BACK,
                                 ITEM_FAILED, ITEM_MOVED, ITEM_PLANNED, ITEM_UNDONE,
                                 read_recycle_batch, recycle_paths,
                                 restore_latest_recycled_path, restore_recycle_batch,
                                 rollback_recycle_batch)


def manifest_of(batch):
    return json.loads((batch / "恢复位置.json").read_text(encoding="utf-8"))


class RecycleWriteAheadTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.base = self.root / "工作流任务" / "回收站"
        self.first = self.root / "01剧本准备" / "剧本.md"
        self.second = self.root / "03初步分镜" / "分镜.json"
        self.first.parent.mkdir(parents=True)
        self.second.parent.mkdir(parents=True)
        self.first.write_text("剧本", encoding="utf-8")
        self.second.write_text("{}", encoding="utf-8")

    def _interrupt_after_last_move(self):
        """模拟“两项都搬进回收站、还没写 committed 就中断”。"""
        real = storage_maintenance._write_batch_manifest
        writes = []
        def dying(batch, state, records, reason, created_at):
            writes.append(state)
            if len(writes) == 3:
                raise KeyboardInterrupt("模拟进程中断")
            return real(batch, state, records, reason, created_at)
        with patch.object(storage_maintenance, "_write_batch_manifest", dying):
            with self.assertRaises(KeyboardInterrupt):
                recycle_paths(self.root, [self.first, self.second], "中断", now=1_700_000_000)

    def test_plan_is_on_disk_before_any_move_and_tracks_each_item(self):
        snapshots = []
        real = storage_maintenance.move_planned
        def spy(record, root, batch):
            data = manifest_of(batch)
            snapshots.append((data["state"], [row["status"] for row in data["items"]]))
            return real(record, root, batch)
        with patch.object(storage_maintenance, "move_planned", spy):
            records = recycle_paths(self.root, [self.first, self.second], "写前计划",
                                   now=1_700_000_000)
        self.assertEqual(snapshots[0], (BATCH_PLANNED, [ITEM_PLANNED, ITEM_PLANNED]))
        self.assertEqual(snapshots[1], (BATCH_PLANNED, [ITEM_MOVED, ITEM_PLANNED]))
        batch = next(self.base.iterdir())
        final = manifest_of(batch)
        self.assertEqual(final["state"], BATCH_COMMITTED)
        self.assertEqual([row["status"] for row in final["items"]], [ITEM_MOVED, ITEM_MOVED])
        self.assertEqual(len(records), 2)
        self.assertFalse(self.first.exists())

    def test_failed_item_rolls_whole_batch_back_and_reraises_original(self):
        real = storage_maintenance.shutil.move
        calls = []
        def flaky(src, dst):
            calls.append(Path(src))
            if len(calls) == 2:
                raise PermissionError(13, "occupied")
            return real(src, dst)
        with patch.object(storage_maintenance.shutil, "move", flaky):
            with self.assertRaises(PermissionError) as caught:
                recycle_paths(self.root, [self.first, self.second], "占用文件",
                              now=1_700_000_000)
        self.assertEqual(caught.exception.errno, 13)
        self.assertTrue(self.first.is_file() and self.second.is_file())
        batch = next(self.base.iterdir())
        data = manifest_of(batch)
        self.assertEqual(data["state"], BATCH_ROLLED_BACK)
        self.assertEqual([row["status"] for row in data["items"]], [ITEM_UNDONE, ITEM_FAILED])
        self.assertIn("PermissionError", data["items"][1]["error"])
        leftovers = [item.name for item in batch.rglob("*") if item.is_file()]
        self.assertEqual(leftovers, ["恢复位置.json"])
        self.assertEqual(read_recycle_batch(self.root, batch)["state"], BATCH_ROLLED_BACK)
        with self.assertRaisesRegex(ValueError, "没有可恢复的删除记录"):
            restore_latest_recycled_path(self.root, self.first)

    def test_disk_full_error_also_rolls_back(self):
        def full(src, dst):
            raise OSError(errno.ENOSPC, "no space")
        with patch.object(storage_maintenance.shutil, "move", full):
            with self.assertRaises(OSError):
                recycle_paths(self.root, [self.first, self.second], "磁盘满",
                              now=1_700_000_000)
        self.assertTrue(self.first.is_file() and self.second.is_file())
        self.assertEqual(manifest_of(next(self.base.iterdir()))["state"], BATCH_ROLLED_BACK)

    def test_interrupted_batch_can_be_rolled_back(self):
        self._interrupt_after_last_move()
        self.assertFalse(self.first.exists())
        self.assertFalse(self.second.exists())
        batch = next(self.base.iterdir())
        self.assertEqual(manifest_of(batch)["state"], BATCH_PLANNED)
        restored = rollback_recycle_batch(self.root, batch)
        self.assertEqual(set(restored), {self.first, self.second})
        self.assertTrue(self.first.is_file() and self.second.is_file())
        self.assertEqual(manifest_of(batch)["state"], BATCH_ROLLED_BACK)

    def test_interrupted_batch_restores_what_is_really_in_the_bin(self):
        self._interrupt_after_last_move()
        batch = next(self.base.iterdir())
        # 清单停在 planned 但文件已在回收站：恢复按“文件真的在回收站”判定，两项都要回来。
        self.assertEqual(len(restore_recycle_batch(self.root, batch)), 2)
        self.assertTrue(self.first.is_file() and self.second.is_file())

    def test_rollback_refuses_committed_batch(self):
        recycle_paths(self.root, [self.first], "已提交", now=1_700_000_000)
        batch = next(self.base.iterdir())
        with self.assertRaisesRegex(ValueError, "已提交"):
            rollback_recycle_batch(self.root, batch)
        self.assertTrue((batch / "01剧本准备" / "剧本.md").is_file())

    def test_same_second_batches_stay_independent(self):
        recycle_paths(self.root, [self.first], "第一批", now=1_700_000_000)
        recycle_paths(self.root, [self.second], "第二批", now=1_700_000_000)
        self.assertEqual(len(list(self.base.iterdir())), 2)
        self.assertEqual({read_recycle_batch(self.root, b)["reason"] for b in self.base.iterdir()},
                         {"第一批", "第二批"})
        for batch in list(self.base.iterdir()):
            restore_recycle_batch(self.root, batch)
        self.assertTrue(self.first.is_file() and self.second.is_file())

    def test_committed_batch_reports_state_and_restores(self):
        recycle_paths(self.root, [self.first, self.second], "可恢复", now=1_700_000_000)
        batch = next(self.base.iterdir())
        self.assertEqual(read_recycle_batch(self.root, batch)["state"], BATCH_COMMITTED)
        self.assertEqual(set(restore_recycle_batch(self.root, batch)), {self.first, self.second})
        self.assertTrue(self.first.is_file() and self.second.is_file())

    def test_clean_project_uses_write_ahead_plan(self):
        cleaned = self.root / "库"
        cleaned.mkdir()
        (cleaned / "config.json").write_text("{}", encoding="utf-8")
        history = cleaned / "故事" / "历史版本"
        history.mkdir(parents=True)
        (history / "旧稿.md").write_text("旧", encoding="utf-8")
        with patch.object(storage_maintenance, "downloads_root", lambda: self.root):
            storage_maintenance.clean_project(cleaned, now=1_700_000_000)
        batch = next((cleaned / "工作流任务" / "回收站").iterdir())
        data = manifest_of(batch)
        self.assertEqual(data["state"], BATCH_COMMITTED)
        self.assertEqual([row["status"] for row in data["items"]], [ITEM_MOVED])
        self.assertFalse(history.exists())
        self.assertTrue((batch / "故事" / "历史版本" / "旧稿.md").is_file())


if __name__ == "__main__":
    unittest.main()
