# -*- coding: utf-8 -*-
"""R3117（任务书 P2，Q5）：回收站保留期与「清空过期批次」。

覆盖：超过保留期的整批被物理删除、未到期的保留、清单不可读的批次不猜内容、保留期
非正数时不动作；删除只发生在项目回收站内。
"""
import json
import tempfile
import time
import unittest
from pathlib import Path

from agent.core import save
from infra.storage_maintenance import (RECYCLE_RETENTION_DAYS, purge_expired_batches, recycle_base,
                                 recycle_paths)


def _recycle_one(root, name='a.md'):
    folder = root / '01剧本准备' / 'docs'
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / name
    target.write_text('正文', encoding='utf-8')
    recycle_paths(root, [target], '测试')
    return next(batch for batch in recycle_base(root).iterdir() if batch.is_dir())


def _age_batch(batch, days):
    manifest = batch / '恢复位置.json'
    data = json.loads(manifest.read_text(encoding='utf-8'))
    data['created_at'] = time.strftime('%Y-%m-%d %H:%M:%S',
                                       time.localtime(time.time() - days * 86400))
    save(manifest, data)


class PurgeExpiredTests(unittest.TestCase):
    def test_old_batch_is_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / '项目'
            root.mkdir()
            batch = _recycle_one(root)
            _age_batch(batch, RECYCLE_RETENTION_DAYS + 1)
            removed = purge_expired_batches(root)
            self.assertEqual(removed, [batch.name])
            self.assertFalse(batch.exists())

    def test_fresh_batch_is_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / '项目'
            root.mkdir()
            batch = _recycle_one(root)
            self.assertEqual(purge_expired_batches(root), [])
            self.assertTrue(batch.is_dir())

    def test_batch_with_unreadable_manifest_is_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / '项目'
            root.mkdir()
            batch = _recycle_one(root)
            (batch / '恢复位置.json').write_text('{坏掉的 JSON', encoding='utf-8')
            self.assertEqual(purge_expired_batches(root), [])
            self.assertTrue(batch.is_dir())

    def test_non_positive_retention_is_a_no_op(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / '项目'
            root.mkdir()
            batch = _recycle_one(root)
            _age_batch(batch, RECYCLE_RETENTION_DAYS + 5)
            self.assertEqual(purge_expired_batches(root, days=0), [])
            self.assertTrue(batch.is_dir())

    def test_only_the_recycle_base_is_touched(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / '项目'
            root.mkdir()
            batch = _recycle_one(root)
            _age_batch(batch, RECYCLE_RETENTION_DAYS + 1)
            keep = root / '工作流任务' / '覆盖前备份' / '旧东西'
            keep.mkdir(parents=True)
            (keep / 'x.md').write_text('保留', encoding='utf-8')
            purge_expired_batches(root)
            self.assertFalse(batch.exists())
            self.assertTrue((keep / 'x.md').is_file())

    def test_missing_project_is_harmless(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(purge_expired_batches(Path(tmp) / '不存在'), [])

    def test_retention_constant_matches_the_task_book(self):
        self.assertEqual(RECYCLE_RETENTION_DAYS, 30)


if __name__ == '__main__':
    unittest.main()
