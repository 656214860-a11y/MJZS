# -*- coding: utf-8 -*-
import tempfile
import unittest
from pathlib import Path

from storage_maintenance import (recycle_paths, restore_recycle_batch,
                                 restore_latest_recycled_child, restore_latest_recycled_path)
from storyboard_files import latest_recycle_batch, restore_latest_recycled_files


class RecycleRestoreTests(unittest.TestCase):
    def test_restore_recycles_full_batch_to_original_locations(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first = root / '01剧本准备' / '剧本.md'
            second = root / '03初步分镜' / '分镜.json'
            first.parent.mkdir(); second.parent.mkdir()
            first.write_text('剧本', encoding='utf-8'); second.write_text('{}', encoding='utf-8')
            records = recycle_paths(root, [first, second], '测试删除', now=1_700_000_000)
            self.assertEqual(len(records), 2)
            batch = next((root / '工作流任务' / '回收站').iterdir())
            restored = restore_recycle_batch(root, batch)
            self.assertEqual(set(restored), {first, second})
            self.assertEqual(first.read_text(encoding='utf-8'), '剧本')
            self.assertEqual(second.read_text(encoding='utf-8'), '{}')

    def test_restore_refuses_conflicting_destination_without_partial_move(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); target = root / '01剧本准备' / '剧本.md'
            target.parent.mkdir(); target.write_text('旧稿', encoding='utf-8')
            records = recycle_paths(root, [target], '测试删除', now=1_700_000_000)
            target.write_text('新稿', encoding='utf-8')
            batch = next((root / '工作流任务' / '回收站').iterdir())
            with self.assertRaisesRegex(ValueError, '已被占用'):
                restore_recycle_batch(root, batch)
            recycled = root / records[0]['recycle_path']
            self.assertTrue(recycled.is_file())

    def test_restore_latest_path_does_not_restore_other_files_in_the_batch(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first = root / '04资产管理' / 'assets' / 'CHAR_001.png'
            second = root / '04资产管理' / 'assets' / 'LOC_001.png'
            first.parent.mkdir(parents=True)
            first.write_bytes(b'first'); second.write_bytes(b'second')
            recycle_paths(root, [first, second], '删除资产图片', now=1_700_000_000)
            self.assertEqual(restore_latest_recycled_path(root, first), [first])
            self.assertTrue(first.is_file())
            self.assertFalse(second.exists())

    def test_restore_latest_child_matches_asset_without_known_extension(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            image = root / '04资产管理' / 'assets' / 'characters' / 'CHAR_001.webp'
            other = image.with_name('CHAR_002.png')
            image.parent.mkdir(parents=True)
            image.write_bytes(b'image'); other.write_bytes(b'other')
            recycle_paths(root, [image, other], '删除资产图片', now=1_700_000_000)
            restored = restore_latest_recycled_child(root, image.parent, 'CHAR_001', ('.png', '.webp'))
            self.assertEqual(restored, [image])
            self.assertTrue(image.is_file())
            self.assertFalse(other.exists())

    def test_storyboard_restore_uses_latest_manual_batch_only(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            original = root / '01剧本准备' / '自然剧本.md'
            original.parent.mkdir(); original.write_text('原稿', encoding='utf-8')
            # Automatic maintenance batches use ``items`` and must not appear in
            # the storyboard page's "restore most recent delete" action.
            recycle_paths(root, [original], '自动清理', now=1_700_000_000)
            manual = root / '工作流任务' / '回收站' / 'storyboard-manual'
            recycled = manual / '01剧本准备' / '自然剧本.md'
            recycled.parent.mkdir(parents=True)
            automatic_batch = next(
                item for item in (root / '工作流任务' / '回收站').iterdir()
                if item.name.startswith('自动维护_')
            )
            automatic_file = next(automatic_batch.rglob('自然剧本.md'))
            automatic_file.replace(recycled)
            (manual / '恢复位置.json').write_text(
                '{"files": [{"original": "01剧本准备/自然剧本.md", '
                '"recycled": "工作流任务/回收站/storyboard-manual/01剧本准备/自然剧本.md"}]}', encoding='utf-8')
            candidate = latest_recycle_batch(root)
            self.assertIsNotNone(candidate)
            self.assertEqual(candidate[0], manual)
            names, restored = restore_latest_recycled_files(root)
            self.assertEqual(names, ['01剧本准备/自然剧本.md'])
            self.assertEqual(restored, [original])
            self.assertEqual(original.read_text(encoding='utf-8'), '原稿')
