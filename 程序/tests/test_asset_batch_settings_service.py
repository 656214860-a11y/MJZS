import tempfile
import unittest
from pathlib import Path

from agent.core import read, save
from asset_batch_settings_service import remove_model, save_settings


class AssetBatchSettingsServiceTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        save(self.root / 'ui_settings.json', {
            'auto_asset': True,
            'asset_batch': {'url': 'http://127.0.0.1:8189', 'model': 'old.safetensors',
                            'deleted_models': ['old-id'], 'quality': 'low'},
        })

    def test_save_settings_preserves_unrelated_preferences_and_restores_model(self):
        saved = save_settings(self.root, {'model': 'new.safetensors'},
                              {'CHAR': True, 'PROP': False}, 'old-id', publish=save)
        self.assertEqual(saved['model'], 'new.safetensors')
        self.assertEqual(saved['deleted_models'], [])
        self.assertTrue(saved['CHAR'])
        self.assertFalse(saved['PROP'])
        persisted = read(self.root / 'ui_settings.json')
        self.assertTrue(persisted['auto_asset'])
        self.assertEqual(persisted['asset_batch']['quality'], 'low')

    def test_remove_model_keeps_unrelated_settings_and_deduplicates_identity(self):
        saved = remove_model(self.root, 'http://127.0.0.1:8189/', 'old.safetensors', 'old-id', publish=save)
        self.assertEqual(saved['model'], '')
        self.assertEqual(saved['deleted_models'], ['old-id'])
        self.assertEqual(read(self.root / 'ui_settings.json')['asset_batch']['quality'], 'low')
