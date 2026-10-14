"""Claude Code npm 安装识别；不启动真实会话。"""
import os
from pathlib import Path
import tempfile
import unittest
import unittest.mock
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


class StoreProgramUpdateTests(unittest.TestCase):
    def test_stale_store_version_path_follows_installed_package(self):
        with tempfile.TemporaryDirectory() as folder:
            apps = Path(folder) / 'WindowsApps'
            current = apps / 'Claude_2.31226.1.0_x64__pzs8sxrjxfjjc/app/claude.exe'
            current.parent.mkdir(parents=True)
            current.write_bytes(b'test-only')
            stale = str(apps / 'Claude_2.31226.0.0_x64__pzs8sxrjxfjjc/app/claude.exe')
            names = ['Other_1.0.0.0_x64__pzs8sxrjxfjjc', 'Claude_2.31226.1.0_x64__pzs8sxrjxfjjc']
            fake = unittest.mock.MagicMock()
            fake.EnumKey.side_effect = lambda key, index: names[index] if index < len(names) else (_ for _ in ()).throw(OSError())
            with patch.dict('sys.modules', {'winreg': fake}):
                self.assertEqual(settings.find_program({'engine': 'claude', 'program': stale}), str(current))
                current.unlink()
                self.assertEqual(settings.current_store_program(stale), stale)

    def test_non_store_and_existing_paths_unchanged(self):
        self.assertEqual(settings.current_store_program('chosen.exe'), 'chosen.exe')


class StoreDesktopDetectionTests(unittest.TestCase):
    """R1424：自动搜寻识别商店版 Claude Desktop（WindowsApps），新版本优先。"""

    def fake_registry(self, roots):
        names = list(roots)
        fake = unittest.mock.MagicMock()
        fake.EnumKey.side_effect = lambda key, index: names[index] if index < len(names) else (_ for _ in ()).throw(OSError())
        opened = {}
        def open_key(parent, name):
            handle = unittest.mock.MagicMock()
            handle.__enter__.return_value = name
            opened[name] = handle
            return handle
        fake.OpenKey.side_effect = open_key
        def query(name, value):
            if roots.get(name) is None:
                raise OSError('missing')
            return (roots[name], 1)
        fake.QueryValueEx.side_effect = query
        return fake

    def test_store_install_found_when_squirrel_paths_missing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            apps = root / 'WindowsApps'
            old = apps / 'Claude_2.31226.0.0_x64__pzs8sxrjxfjjc'
            new = apps / 'Claude_2.31226.1.0_x64__pzs8sxrjxfjjc'
            for base in (old, new):
                (base / 'app').mkdir(parents=True)
                (base / 'app' / 'Claude.exe').write_bytes(b'test-only')
            roots = {'Other_9.0.0.0_x64__x': str(apps / 'Other'), old.name: str(old), new.name: str(new)}
            fake = self.fake_registry(roots)
            with patch('platform_tools.windows_registry', return_value=fake), \
                    patch.dict(os.environ, {'LOCALAPPDATA': str(root / 'empty')}):
                self.assertEqual(settings.find_program({'engine': 'claude-desktop-app', 'program': ''}),
                                 str(new / 'app' / 'Claude.exe'))
                (new / 'app' / 'Claude.exe').unlink()
                self.assertEqual(settings.find_program({'engine': 'claude-desktop-app', 'program': ''}),
                                 str(old / 'app' / 'Claude.exe'))

    def test_missing_root_value_falls_back_to_program_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            name = 'Claude_2.31226.1.0_x64__pzs8sxrjxfjjc'
            exe = root / 'WindowsApps' / name / 'app' / 'Claude.exe'
            exe.parent.mkdir(parents=True)
            exe.write_bytes(b'test-only')
            fake = self.fake_registry({name: None})
            with patch('platform_tools.windows_registry', return_value=fake), \
                    patch.dict(os.environ, {'LOCALAPPDATA': str(root / 'empty'), 'ProgramFiles': str(root)}):
                self.assertEqual(settings.store_package_program('Claude', Path('app') / 'Claude.exe'), str(exe))

    def test_no_registry_keeps_not_found_error(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch('platform_tools.windows_registry', return_value=None), \
                    patch.dict(os.environ, {'LOCALAPPDATA': folder}):
                with self.assertRaisesRegex(ValueError, '未找到 Claude Desktop'):
                    settings.find_program({'engine': 'claude-desktop-app', 'program': ''})


class GuiCliGuardTests(unittest.TestCase):
    """R1425：Claude Desktop 图形程序不能当命令行 claude.exe 调用。"""

    def test_gui_paths_are_recognised_and_cli_paths_are_not(self):
        gui = [r'C:\Program Files\WindowsApps\Claude_2.1.0.0_x64__x\app\Claude.exe',
               r'C:\Users\a\AppData\Local\AnthropicClaude\app-1.0\claude.exe',
               r'C:\Users\a\AppData\Local\Programs\Claude\Claude.exe']
        cli = [r'C:\Users\a\.local\bin\claude.exe',
               r'C:\Users\a\AppData\Roaming\npm\node_modules\@anthropic-ai\claude-code\bin\claude.exe',
               r'C:\Program Files\WindowsApps\Other_1_x64__x\app\other.exe', '']
        self.assertTrue(all(settings.gui_claude_program(path) for path in gui))
        self.assertFalse(any(settings.gui_claude_program(path) for path in cli))
