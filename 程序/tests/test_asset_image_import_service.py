import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import asset_batch_service
from agent.core import read, save
from stage_execution_service import asset_batch_gateway


class AssetImageImportServiceTests(unittest.TestCase):
    def gateway(self):
        return asset_batch_gateway()
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.base = root / 'asset-base'
        self.base.mkdir()
        self.project = root / 'project'
        self.project.mkdir()
        self.source = root / 'incoming.png'
        self.source.write_bytes(b'new image')
        save(self.base / 'assets.json', {'CHAR_001': {'name': '旧角色'}})

    def test_imports_image_publishes_registry_and_renames_source(self):
        kind, result = asset_batch_service.import_asset_image(
            self.base, self.project, 'CHAR_001', self.source,
            {'CHAR_001': {'name': '角色', 'description': '主角'}}, gateway=self.gateway())
        dest = self.base / 'assets/characters/CHAR_001.png'
        self.assertEqual(kind, 'characters')
        self.assertIn('已登记 CHAR_001', result)
        self.assertEqual(dest.read_bytes(), b'new image')
        self.assertEqual(read(self.base / 'assets.json')['CHAR_001'], {
            'name': '角色', 'image': 'assets/characters/CHAR_001.png', 'description': '主角'})
        self.assertFalse(self.source.exists())
        self.assertTrue((self.source.parent / 'CHAR_001.png').is_file())

    def test_formal_import_rejects_missing_l3_gateway(self):
        with self.assertRaisesRegex(TypeError, 'L3'):
            asset_batch_service.import_asset_image(
                self.base, self.project, 'CHAR_001', self.source, {})

    def test_failed_registry_publish_restores_replaced_image_and_keeps_source(self):
        dest = self.base / 'assets/characters/CHAR_001.png'
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b'old image')
        old_registry = (self.base / 'assets.json').read_bytes()
        gateway = self.gateway()
        gateway['publish_json'] = Mock(side_effect=OSError('磁盘不可用'))
        with self.assertRaisesRegex(OSError, '磁盘不可用'):
            asset_batch_service.import_asset_image(
                self.base, self.project, 'CHAR_001', self.source, {}, gateway=gateway)
        self.assertEqual(dest.read_bytes(), b'old image')
        self.assertEqual((self.base / 'assets.json').read_bytes(), old_registry)
        self.assertTrue(self.source.is_file())
