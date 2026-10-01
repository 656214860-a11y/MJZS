import json
import tempfile
import unittest
from pathlib import Path

from recycle_recovery_controller import RecycleRecoveryController
from recycle_recovery_service import list_batches, restore_batch, restore_item
from storage_maintenance import recycle_paths, restore_recycle_batch


class RecycleRecoveryServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / '项目'
        self.root.mkdir(parents=True)
        self.first = self.root / '01_script' / 'a.txt'
        self.second = self.root / '01_script' / 'b.txt'
        self.first.parent.mkdir()
        self.first.write_text('a', encoding='utf-8')
        self.second.write_text('b', encoding='utf-8')
        recycle_paths(self.root, (self.first, self.second), '测试恢复入口', now=1_700_000_000)
        self.batch = next((self.root / '工作流任务' / '回收站').iterdir())

    def tearDown(self):
        self.temp.cleanup()

    def test_lists_batch_metadata_and_items(self):
        records = list_batches(self.root)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['reason'], '测试恢复入口')
        self.assertEqual({row['source'] for row in records[0]['items']}, {'01_script/a.txt', '01_script/b.txt'})

    def test_restores_whole_batch(self):
        restored = restore_batch(list_batches(self.root)[0])
        self.assertEqual(set(restored), {self.first, self.second})
        self.assertTrue(self.first.is_file())
        self.assertTrue(self.second.is_file())

    def test_restores_one_item_without_moving_sibling(self):
        restored = restore_item(list_batches(self.root)[0], '01_script/a.txt')
        self.assertEqual(restored, [self.first])
        self.assertTrue(self.first.is_file())
        self.assertFalse(self.second.exists())
        self.assertTrue((self.batch / '01_script' / 'b.txt').is_file())
        self.assertEqual([item['source'] for item in list_batches(self.root)[0]['items']], ['01_script/b.txt'])

    def test_existing_target_keeps_entire_batch_in_place(self):
        self.first.write_text('new', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, '已被占用'):
            restore_batch(list_batches(self.root)[0])
        self.assertTrue((self.batch / '01_script' / 'a.txt').is_file())
        self.assertTrue((self.batch / '01_script' / 'b.txt').is_file())
        self.assertFalse(self.second.exists())

    def test_outside_batch_is_rejected(self):
        outside = Path(self.temp.name) / 'outside'
        outside.mkdir()
        with self.assertRaisesRegex(ValueError, '不在当前项目回收站'):
            restore_recycle_batch(self.root, outside)

    def test_legacy_files_manifest_is_listed_and_restored(self):
        legacy = self.root / '工作流任务' / '回收站' / '自动维护_旧版'
        legacy.mkdir(parents=True)
        source = legacy / '01_script' / 'legacy.txt'
        source.parent.mkdir()
        source.write_text('legacy', encoding='utf-8')
        (legacy / '恢复位置.json').write_text(json.dumps({'reason': '旧格式', 'files': [
            {'original': '01_script/legacy.txt', 'recycled': '工作流任务/回收站/自动维护_旧版/01_script/legacy.txt'}
        ]}, ensure_ascii=False), encoding='utf-8')
        record = next(row for row in list_batches(self.root) if row['batch'] == legacy)
        self.assertEqual(record['items'][0]['source'], '01_script/legacy.txt')
        self.assertEqual(restore_item(record, '01_script/legacy.txt'), [self.root / '01_script' / 'legacy.txt'])

    def test_controller_includes_project_and_library_recycle_roots(self):
        library = Path(self.temp.name) / '项目库'
        library.mkdir()
        library_file = library / 'lost.txt'
        library_file.write_text('lost', encoding='utf-8')
        recycle_paths(library, (library_file,), '删除项目', now=1_700_000_001)
        records = RecycleRecoveryController(self.root, library).list_batches()
        self.assertEqual({row['scope'] for row in records}, {'项目内回收站', '项目库回收站'})
