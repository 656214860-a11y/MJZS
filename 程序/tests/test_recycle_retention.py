# -*- coding: utf-8 -*-
"""R3117（任务书 P2，Q5）：回收站保留期与「清空过期批次」。

覆盖：超过保留期的整批被物理删除、未到期的保留、清单不可读的批次不猜内容、保留期
非正数时不动作；删除只发生在项目回收站内。
"""
import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import infra.storage_maintenance as storage
from agent.core import save
from infra.storage_maintenance import (RECYCLE_RETENTION_DAYS, purge_expired_batches, recycle_base,
                                 recycle_paths)


def _recycle_one(root, name='a.md'):
    folder = root / '01剧本准备' / 'docs'
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / name
    target.write_text('正文', encoding='utf-8')
    before = set(recycle_base(root).iterdir()) if recycle_base(root).is_dir() else set()
    recycle_paths(root, [target], '测试')
    return next(batch for batch in recycle_base(root).iterdir() if batch.is_dir() and batch not in before)


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
            with self.assertRaises(ValueError):
                purge_expired_batches(root)
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


class RecycleSafetyTests(unittest.TestCase):
    def test_settings_roundtrip_and_explicit_purge_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = _recycle_one(root)
            _age_batch(batch, 40)
            self.assertEqual(storage.recycle_retention_days(root), 30)
            storage.save_recycle_retention_days(root, 0)
            self.assertEqual(storage.recycle_retention_days(root), 0)
            self.assertEqual(purge_expired_batches(root), [])
            self.assertTrue(batch.exists())
            storage.save_recycle_retention_days(root, 7)
            self.assertEqual(storage.recycle_retention_days(root), 7)
            self.assertTrue(batch.exists())
            self.assertEqual(purge_expired_batches(root), [batch.name])

    def test_gateway_rejects_cross_root_and_nested_batches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'project'; root.mkdir()
            library = Path(tmp) / 'library'; library.mkdir()
            batch = _recycle_one(root)
            outside = _recycle_one(library)
            for invalid in (outside, batch / 'nested', root):
                with self.assertRaises(ValueError):
                    storage.purge_recycle_batches(root, [invalid])
            self.assertTrue(batch.exists())
            self.assertTrue(outside.exists())

    def test_gateway_preflights_all_batches_and_reports_corrupt_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            good = _recycle_one(root)
            bad = _recycle_one(root, 'b.md')
            (bad / '恢复位置.json').write_text('broken', encoding='utf-8')
            with self.assertRaises(ValueError):
                storage.purge_recycle_batches(root, [good, bad])
            self.assertTrue(good.exists())
            self.assertTrue(bad.exists())
            _age_batch(good, 40)
            with self.assertRaises(ValueError):
                purge_expired_batches(root)
            self.assertTrue(good.exists())

    def test_gateway_rejects_junction_and_ancestor_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = _recycle_one(root)
            real = Path.is_junction
            for linked in (batch, batch.parent, batch.parent.parent):
                with patch.object(Path, 'is_junction', lambda p: p == linked or real(p)):
                    with self.assertRaises(ValueError):
                        storage.purge_recycle_batches(root, [batch])
                self.assertTrue(batch.exists())

    def test_real_junction_to_external_data_is_never_followed(self):
        if os.name != 'nt':
            return
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'project'; root.mkdir()
            outside = Path(tmp) / 'outside'; outside.mkdir()
            sentinel = outside / 'keep.txt'; sentinel.write_text('保留', encoding='utf-8')
            batch = _recycle_one(root)
            junction = batch / 'external'
            result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(junction), str(outside)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            try:
                with self.assertRaises(ValueError):
                    storage.purge_recycle_batches(root, [batch])
                self.assertEqual(sentinel.read_text(encoding='utf-8'), '保留')
                self.assertTrue(batch.exists())
            finally:
                junction.rmdir()

    def test_invalid_manifest_paths_and_settings_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = _recycle_one(root)
            manifest = batch / '恢复位置.json'
            data = json.loads(manifest.read_text(encoding='utf-8'))
            data['items'][0]['recycle_path'] = '../outside.txt'
            save(manifest, data)
            with self.assertRaises(ValueError):
                storage.purge_recycle_batches(root, [batch])
            for invalid in ('-1', '1.5', '', True):
                with self.assertRaises(ValueError):
                    storage.save_recycle_retention_days(root, invalid)
            self.assertTrue(batch.exists())

    def test_gateway_reports_io_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = _recycle_one(root)
            with patch.object(storage.shutil, 'rmtree', side_effect=OSError('busy')):
                with self.assertRaises(OSError):
                    storage.purge_recycle_batches(root, [batch])
            self.assertTrue(batch.exists())


if __name__ == '__main__':
    unittest.main()
