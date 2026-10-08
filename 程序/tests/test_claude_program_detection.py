"""Claude Code npm 安装识别；不启动真实会话。"""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import workflow_settings as settings


class ClaudeProgramDetectionTests(unittest.TestCase):
    def test_npm_native_binary_is_used_without_executing_shim(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            prefix = root / 'custom npm prefix'
            executable = prefix / 'node_modules/@anthropic-ai/claude-code/bin/claude.exe'
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b'test-only')
            shim = prefix / 'claude.cmd'
            shim.write_text('must not execute', encoding='utf-8')
            with patch.object(settings.shutil, 'which', side_effect=lambda name: str(shim) if name == 'claude.cmd' else None), \
                    patch.object(settings.Path, 'home', return_value=root):
                self.assertEqual(settings.find_program({'engine': 'claude', 'program': ''}), str(executable))

    def test_default_npm_prefix_without_path_entry(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            executable = root / 'npm/node_modules/@anthropic-ai/claude-code/bin/claude.exe'
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b'test-only')
            with patch.object(settings.shutil, 'which', return_value=None), \
                    patch.object(settings.Path, 'home', return_value=root), \
                    patch.dict(os.environ, {'APPDATA': str(root)}):
                settings.clear_desktop_installation_cache()
                self.addCleanup(settings.clear_desktop_installation_cache)
                self.assertEqual(settings.find_program({'engine': 'claude', 'program': ''}), str(executable))
                self.assertNotIn('未安装', settings.desktop_model_label('claude-desktop', 'Claude Desktop · Claude Code'))
                executable.unlink()
                with self.assertRaisesRegex(ValueError, '未找到'):
                    settings.find_program({'engine': 'claude', 'program': ''})

    def test_existing_detection_priority_is_preserved(self):
        with patch.object(settings.shutil, 'which', return_value='path/claude.exe'):
            self.assertEqual(settings.find_program({'engine': 'claude', 'program': 'chosen.exe'}), 'chosen.exe')
            self.assertEqual(settings.find_program({'engine': 'claude', 'program': ''}), 'path/claude.exe')


if __name__ == '__main__':
    unittest.main()
