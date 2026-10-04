import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from agent.core import read, save
from asset_batch_settings_service import remove_model, save_settings
from service_contract import ServiceResult, SystemError, UserError, success


class AssetBatchSettingsServiceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        save(self.root / 'ui_settings.json', {
            'auto_asset': True,
            'asset_batch': {'url': 'http://127.0.0.1:8189', 'model': 'old.safetensors',
                            'deleted_models': ['old-id'], 'quality': 'low'},
        })

    def test_save_settings_preserves_unrelated_preferences_and_restores_model(self):
        saved = save_settings(self.root, {'model': 'new.safetensors'},
                              {'CHAR': True, 'PROP': False}, 'old-id', publish=save)
        self.assertIsInstance(saved, ServiceResult)
        self.assertTrue(saved.ok)
        saved = saved.data
        self.assertEqual(saved['model'], 'new.safetensors')
        self.assertEqual(saved['deleted_models'], [])
        self.assertTrue(saved['CHAR'])
        self.assertFalse(saved['PROP'])
        persisted = read(self.root / 'ui_settings.json')
        self.assertTrue(persisted['auto_asset'])
        self.assertEqual(persisted['asset_batch']['quality'], 'low')

    def test_remove_model_keeps_unrelated_settings_and_deduplicates_identity(self):
        saved = remove_model(self.root, 'http://127.0.0.1:8189/', 'old.safetensors', 'old-id', publish=save)
        self.assertIsInstance(saved, ServiceResult)
        self.assertTrue(saved.ok)
        saved = saved.data
        self.assertEqual(saved['model'], '')
        self.assertEqual(saved['deleted_models'], ['old-id'])
        self.assertEqual(read(self.root / 'ui_settings.json')['asset_batch']['quality'], 'low')

    def operations(self, publish):
        return [lambda: save_settings(self.root, {}, publish=publish),
                lambda: remove_model(self.root, 'url', 'model', 'id', publish=publish)]

    def test_invalid_options_do_not_publish(self):
        publisher = Mock()
        for options, categories in [(None, None), ({}, [])]:
            with self.subTest(options=options, categories=categories):
                result = save_settings(self.root, options, categories, publish=publisher)
                self.assertIsInstance(result, UserError)
                self.assertFalse(result.ok)
        publisher.assert_not_called()

    def test_read_failure_preserves_original_and_does_not_publish(self):
        original = (self.root / 'ui_settings.json').read_bytes()
        publisher = Mock()
        for operation in self.operations(publisher):
            with patch('asset_batch_settings_service.read_prefs', side_effect=ValueError('private detail')):
                with self.assertLogs('asset_batch_settings_service', level='ERROR'):
                    result = operation()
            self.assertIsInstance(result, SystemError)
            self.assertNotIn('private detail', result.reason)
        publisher.assert_not_called()
        self.assertEqual((self.root / 'ui_settings.json').read_bytes(), original)

    def test_publish_failure_returns_system_error(self):
        for operation in self.operations(Mock(side_effect=OSError('private detail'))):
            with self.assertLogs('asset_batch_settings_service', level='ERROR'):
                result = operation()
            self.assertIsInstance(result, SystemError)
            self.assertFalse(result.ok)
            self.assertTrue(result.recoverable)
            self.assertIsNone(result.data)
            self.assertNotIn('private detail', result.reason)

    def test_corrupt_settings_are_not_overwritten(self):
        path = self.root / 'ui_settings.json'
        original = b'{"unfinished":'
        path.write_bytes(original)
        publisher = Mock(wraps=save)
        for operation in self.operations(publisher):
            with self.assertLogs('asset_batch_settings_service', level='ERROR'):
                result = operation()
            self.assertIsInstance(result, SystemError)
            self.assertEqual(path.read_bytes(), original)
        publisher.assert_not_called()

    def test_l3_injects_publisher_and_returns_exact_service_result(self):
        from stage_execution_service import save_asset_batch_settings, remove_asset_batch_model
        publisher = Mock()
        for result in [success({'model': 'new'}), UserError('输入错误'), SystemError('保存失败')]:
            with self.subTest(result=type(result).__name__):
                with patch('stage_execution_service.asset_batch_settings_gateway',
                           return_value={'publish_json': publisher}):
                    with patch('asset_batch_settings_service.save_settings', return_value=result) as service:
                        self.assertIs(save_asset_batch_settings(self.root, {}, {'CHAR': True}, 'id'), result)
                        service.assert_called_once_with(self.root, {}, {'CHAR': True}, 'id', publish=publisher)
                    with patch('asset_batch_settings_service.remove_model', return_value=result) as service:
                        self.assertIs(remove_asset_batch_model(self.root, 'url', 'model', 'id'), result)
                        service.assert_called_once_with(self.root, 'url', 'model', 'id', publish=publisher)

    def test_programming_errors_are_not_disguised_as_service_failures(self):
        for publisher in [None, Mock(side_effect=TypeError('bug'))]:
            for operation in self.operations(publisher):
                with self.assertRaises(TypeError):
                    operation()
        for operation in self.operations(Mock(side_effect=ValueError('bug'))):
            with self.assertRaises(ValueError):
                operation()
