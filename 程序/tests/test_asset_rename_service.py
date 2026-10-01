import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import asset_batch_service
from agent.core import read, save


class AssetRenameServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.plan = self.base / 'assets/资产清单/assets.json'
        self.plan.parent.mkdir(parents=True)
        self.registry = self.base / 'assets.json'
        save(self.plan, {'CHAR_001': {'name': '旧名', 'aliases': ['更早名称']}})
        save(self.registry, {'CHAR_001': {'name': '旧名', 'image': 'assets/characters/a.png'}})

    def test_rename_updates_plan_alias_and_registered_index(self):
        row = asset_batch_service.rename_asset(self.base, 'CHAR_001', '旧名', '新名')
        self.assertEqual(row['name'], '新名')
        self.assertEqual(row['aliases'], ['更早名称', '旧名'])
        self.assertEqual(read(self.plan)['CHAR_001']['name'], '新名')
        self.assertEqual(read(self.registry)['CHAR_001']['name'], '新名')

    def test_second_write_failure_restores_both_documents(self):
        before_plan = self.plan.read_bytes()
        before_registry = self.registry.read_bytes()
        real_save = asset_batch_service.save
        calls = 0

        def fail_second(path, value):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError('磁盘不可用')
            real_save(path, value)

        with patch.object(asset_batch_service, 'save', side_effect=fail_second):
            with self.assertRaisesRegex(OSError, '磁盘不可用'):
                asset_batch_service.rename_asset(self.base, 'CHAR_001', '旧名', '新名')
        self.assertEqual(self.plan.read_bytes(), before_plan)
        self.assertEqual(self.registry.read_bytes(), before_registry)
