import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent.core import read, save
from desktop_settings_service import publish_desktop_settings
from service_contract import SystemError, UserError


class DesktopSettingsServiceTests(unittest.TestCase):
    def test_publishes_merged_preferences_without_mutating_input(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'desktop_settings.json'
            current = {'comfy_url': 'http://127.0.0.1:8188', 'jianying': ''}

            saved = publish_desktop_settings(path, current, {'jianying': 'C:/Jianying.exe'}, publish=save)

            self.assertEqual('', current['jianying'])
            self.assertTrue(saved.ok)
            self.assertEqual('http://127.0.0.1:8188', saved.data['comfy_url'])
            self.assertEqual(saved.data, read(path))

    def test_failed_write_keeps_caller_state_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'desktop_settings.json'
            current = {'comfy_exe': 'old.exe'}

            with patch('agent.core.save', side_effect=OSError('disk full')):
                with self.assertLogs('desktop_settings_service', level='ERROR'):
                    result = publish_desktop_settings(path, current, {'comfy_exe': 'new.exe'},
                                                     publish=__import__('agent.core', fromlist=['save']).save)
                self.assertIsInstance(result, SystemError)
                self.assertNotIn('disk full', result.reason)

            self.assertEqual({'comfy_exe': 'old.exe'}, current)
            self.assertFalse(path.exists())

    def test_rejects_other_files_and_empty_updates(self):
        with tempfile.TemporaryDirectory() as temp:
            result = publish_desktop_settings(Path(temp) / 'other.json', {}, {'jianying': 'x'})
            self.assertIsInstance(result, UserError)
            self.assertIn('desktop_settings', result.reason)
            result = publish_desktop_settings(Path(temp) / 'desktop_settings.json', {}, {})
            self.assertIsInstance(result, UserError)
            self.assertIn('非空', result.reason)

    def test_programming_errors_are_not_converted(self):
        for error in (TypeError('bug'), ValueError('bug')):
            with self.subTest(error=type(error)):
                def publish(*args):
                    raise error
                with self.assertRaisesRegex(type(error), 'bug'):
                    publish_desktop_settings('desktop_settings.json', {}, {'x': 1}, publish=publish)

    def test_invalid_inputs_do_not_publish(self):
        from unittest.mock import Mock
        for current, updates in ((None, {'x': 1}), ({}, {}), ({}, {'': 1})):
            publish = Mock()
            result = publish_desktop_settings('desktop_settings.json', current, updates, publish=publish)
            self.assertIsInstance(result, UserError)
            publish.assert_not_called()

    def test_l3_preserves_result_identity(self):
        from stage_execution_service import publish_desktop_preferences
        expected = SystemError('保存失败')
        with patch('desktop_settings_service.publish_desktop_settings', return_value=expected) as service:
            self.assertIs(expected, publish_desktop_preferences('desktop_settings.json', {}, {'x': 1}))
        self.assertTrue(callable(service.call_args.kwargs['publish']))
