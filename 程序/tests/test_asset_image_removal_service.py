import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import asset_batch_service
from agent.core import read, save


class AssetImageRemovalServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.image = self.base / 'assets/characters/CHAR_001.png'
        self.image.parent.mkdir(parents=True)
        self.image.write_bytes(b'png')
        self.index = self.base / 'assets.json'
        save(self.index, {'CHAR_001': {'name': '角色', 'image': 'assets/characters/CHAR_001.png'}})

    def test_recycles_image_then_clears_registered_pointer(self):
        result = asset_batch_service.remove_asset_image(self.base, 'CHAR_001')
        self.assertEqual(result, self.image.resolve())
        self.assertFalse(self.image.exists())
        self.assertNotIn('image', read(self.index)['CHAR_001'])

    def test_failed_index_save_restores_recycled_image_and_old_pointer(self):
        with patch.object(asset_batch_service, 'save', side_effect=OSError('磁盘不可用')):
            with self.assertRaisesRegex(OSError, '磁盘不可用'):
                asset_batch_service.remove_asset_image(self.base, 'CHAR_001')
        self.assertTrue(self.image.is_file())
        self.assertEqual(read(self.index)['CHAR_001']['image'], 'assets/characters/CHAR_001.png')
