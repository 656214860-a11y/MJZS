import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent.core import read, save
from desktop_settings_service import publish_desktop_settings


class DesktopSettingsServiceTests(unittest.TestCase):
    def test_publishes_merged_preferences_without_mutating_input(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'desktop_settings.json'
            current = {'comfy_url': 'http://127.0.0.1:8188', 'jianying': ''}

            saved = publish_desktop_settings(path, current, {'jianying': 'C:/Jianying.exe'}, publish=save)

            self.assertEqual('', current['jianying'])
            self.assertEqual('http://127.0.0.1:8188', saved['comfy_url'])
            self.assertEqual(saved, read(path))

    def test_failed_write_keeps_caller_state_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'desktop_settings.json'
            current = {'comfy_exe': 'old.exe'}

            with patch('agent.core.save', side_effect=OSError('disk full')):
                with self.assertRaisesRegex(OSError, 'disk full'):
                    publish_desktop_settings(path, current, {'comfy_exe': 'new.exe'},
                                             publish=__import__('agent.core', fromlist=['save']).save)

            self.assertEqual({'comfy_exe': 'old.exe'}, current)
            self.assertFalse(path.exists())

    def test_rejects_other_files_and_empty_updates(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, 'desktop_settings'):
                publish_desktop_settings(Path(temp) / 'other.json', {}, {'jianying': 'x'})
            with self.assertRaisesRegex(ValueError, '非空'):
                publish_desktop_settings(Path(temp) / 'desktop_settings.json', {}, {})
