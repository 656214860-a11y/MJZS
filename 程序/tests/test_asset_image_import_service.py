import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import asset_batch_service
from agent.core import read, save
from stage_execution_service import asset_batch_gateway
from tests.image_fixtures import png

SOURCE_PNG = png()


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
        self.source.write_bytes(SOURCE_PNG)
        save(self.base / 'assets.json', {'CHAR_001': {'name': '旧角色'}})

    def test_imports_image_publishes_registry_and_renames_source(self):
        kind, result = asset_batch_service.import_asset_image(
            self.base, self.project, 'CHAR_001', self.source,
            {'CHAR_001': {'name': '角色', 'description': '主角'}}, gateway=self.gateway())
        dest = self.base / 'assets/characters/CHAR_001.png'
        self.assertEqual(kind, 'characters')
        self.assertIn('已登记 CHAR_001', result)
        self.assertEqual(dest.read_bytes(), SOURCE_PNG)
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

    def test_import_rejects_non_image_content_with_image_suffix(self):
        registry_before = (self.base / 'assets.json').read_bytes()
        cases = [('fake.png', '这不是图片，只是文本'.encode('utf-8')),
                 ('fake.jpg', '这不是图片，只是文本'.encode('utf-8')),
                 ('fake.jpeg', '这不是图片，只是文本'.encode('utf-8')),
                 ('fake.webp', '这不是图片，只是文本'.encode('utf-8')),
                 ('broken.png', b'\x89PNG\r\n\x1a\n' + b'\x00' * 32),
                 ('broken.jpg', b'\xff\xd8\xff\xe0' + b'\x00' * 32)]
        for name, blob in cases:
            with self.subTest(name=name):
                fake = self.source.with_name(name)
                fake.write_bytes(blob)
                with self.assertRaisesRegex(ValueError, '图片内容无效'):
                    asset_batch_service.import_asset_image(
                        self.base, self.project, 'CHAR_001', fake, {},
                        gateway=self.gateway())
                self.assertTrue(fake.is_file())
        self.assertEqual((self.base / 'assets.json').read_bytes(), registry_before)
        self.assertFalse((self.base / 'assets').exists())

    def test_import_accepts_real_jpeg_and_webp(self):
        import io
        from PIL import Image
        cases = [('LOC_001', '.jpg', 'JPEG'), ('PROP_001', '.webp', 'WEBP')]
        folders = {'LOC_001': 'scenes', 'PROP_001': 'props'}
        for aid, suffix, fmt in cases:
            with self.subTest(suffix=suffix):
                buffer = io.BytesIO()
                Image.new('RGB', (2, 2), (200, 40, 40)).save(buffer, fmt)
                blob = buffer.getvalue()
                source = self.source.with_name('real' + suffix)
                source.write_bytes(blob)
                kind, _result = asset_batch_service.import_asset_image(
                    self.base, self.project, aid, source, {}, gateway=self.gateway())
                dest = self.base / 'assets' / folders[aid] / (aid + suffix)
                self.assertEqual(kind, folders[aid])
                self.assertEqual(dest.read_bytes(), blob)
                self.assertEqual(read(self.base / 'assets.json')[aid]['image'],
                                 dest.relative_to(self.base).as_posix())
