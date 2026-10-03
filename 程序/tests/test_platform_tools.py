# -*- coding: utf-8 -*-
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import platform_tools


class OpenPathTests(unittest.TestCase):
    def test_windows_registry_degrades_cleanly_off_windows(self):
        with patch.object(platform_tools.os, 'name', 'posix'):
            self.assertIsNone(platform_tools.windows_registry())

    def test_hidden_console_flags_degrade_cleanly_off_windows(self):
        with patch.object(platform_tools.os, 'name', 'posix'):
            self.assertEqual(platform_tools.hidden_console_flags(), 0)

    def test_windows_only_action_has_actionable_non_windows_error(self):
        with patch.object(platform_tools.os, 'name', 'posix'):
            with self.assertRaisesRegex(ValueError, '仅支持 Windows'):
                platform_tools.require_windows('ComfyUI 进程检测')

    def test_terminate_registered_process_uses_portable_api_off_windows(self):
        class Process:
            pid = 123
            def __init__(self):
                self.terminated = False
            def terminate(self):
                self.terminated = True
        process = Process()
        with patch.object(platform_tools.os, 'name', 'posix'):
            self.assertTrue(platform_tools.terminate_process_tree(process))
        self.assertTrue(process.terminated)

    def test_terminate_registered_process_uses_taskkill_tree_on_windows(self):
        class Process:
            pid = 456
        with patch.object(platform_tools.os, 'name', 'nt'), \
             patch('platform_tools.subprocess.run') as run:
            run.return_value.returncode = 0
            self.assertTrue(platform_tools.terminate_process_tree(Process()))
        run.assert_called_once()
        args, kwargs = run.call_args
        self.assertEqual(args, (['taskkill', '/PID', '456', '/F', '/T'],))
        self.assertEqual(kwargs['capture_output'], True)
        self.assertEqual(kwargs['timeout'], 3)
        self.assertEqual(kwargs['creationflags'], getattr(platform_tools.subprocess, 'CREATE_NO_WINDOW', 0))

    def test_missing_path_has_actionable_error(self):
        with self.assertRaisesRegex(ValueError, '不存在'):
            platform_tools.open_path(Path(tempfile.gettempdir()) / 'not-a-real-open-target')

    def test_windows_startfile_is_used_when_available(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            with patch.object(os, 'startfile', create=True) as startfile:
                self.assertEqual(platform_tools.open_path(target), str(target))
            startfile.assert_called_once_with(str(target))

    def test_missing_non_windows_launcher_has_actionable_error(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.object(platform_tools.os, 'startfile', create=False, new=None), \
                 patch('platform_tools.shutil.which', return_value=None):
                with self.assertRaisesRegex(ValueError, '默认打开器'):
                    platform_tools.open_path(td)

    def test_http_target_uses_browser_but_other_schemes_are_rejected(self):
        with patch('platform_tools.webbrowser.open', return_value=True) as browser:
            self.assertEqual(platform_tools.open_target('https://example.test/task'), 'https://example.test/task')
        browser.assert_called_once_with('https://example.test/task')
        with self.assertRaisesRegex(ValueError, 'HTTP'):
            platform_tools.open_target('file:///unsafe')

    def test_windows_drive_path_is_not_mistaken_for_url_scheme(self):
        with tempfile.TemporaryDirectory() as td:
            with patch('platform_tools.open_path', return_value='opened') as open_path:
                self.assertEqual(platform_tools.open_target(td), 'opened')
            open_path.assert_called_once_with(td)

    def test_comfy_launcher_uses_platform_adapter(self):
        import comfy_runtime
        target = Path('C:/Apps/ComfyUI.exe')
        with patch.object(comfy_runtime, 'executable', return_value=target), \
             patch.object(comfy_runtime, 'open_path', return_value=str(target)) as open_path:
            self.assertEqual(comfy_runtime.open_comfy({}), target)
        open_path.assert_called_once_with(target)

    def test_comfy_wait_honours_unattended_cancellation_before_network_retry(self):
        import comfy_runtime
        with self.assertRaisesRegex(ValueError, '已取消等待'):
            comfy_runtime.wait_comfy('http://127.0.0.1:8189', cancelled=lambda: True)

    def test_windows_app_launcher_checks_host_and_starts_existing_executable(self):
        with tempfile.TemporaryDirectory() as td:
            executable = Path(td) / 'JianyingPro.exe'
            executable.write_bytes(b'')
            with patch.object(platform_tools.os, 'name', 'posix'):
                with self.assertRaisesRegex(ValueError, '仅支持 Windows'):
                    platform_tools.launch_windows_app(executable, '剪映专业版')
            with patch.object(platform_tools.os, 'name', 'nt'), \
                 patch('platform_tools.subprocess.Popen') as launch:
                process = platform_tools.launch_windows_app(executable, '剪映专业版')
            self.assertIs(process, launch.return_value)
            launch.assert_called_once_with([str(executable)], cwd=str(executable.parent), env=None,
                                           creationflags=0)
