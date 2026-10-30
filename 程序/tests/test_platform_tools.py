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

    def test_codex_targets_are_passed_unchanged_to_startfile(self):
        for target in ('codex://threads/abc',
                       'codex://new?path=D%3A%2Fproject&prompt=hello%20world'):
            with self.subTest(target=target), \
                 patch.object(os, 'startfile', create=True) as startfile, \
                 patch('platform_tools.webbrowser.open') as browser:
                self.assertEqual(platform_tools.open_target(target), target)
                startfile.assert_called_once_with(target)
                browser.assert_not_called()

    def test_unknown_scheme_is_still_rejected(self):
        with patch.object(os, 'startfile', create=True) as startfile:
            with self.assertRaisesRegex(ValueError, 'HTTP'):
                platform_tools.open_target('evil://x')
            startfile.assert_not_called()

    def test_codex_startfile_failure_has_actionable_error(self):
        message = '无法打开 codex:// 链接:请确认已安装并注册 ChatGPT/Codex 桌面协议。'
        with patch.object(os, 'startfile', create=True, side_effect=OSError('unregistered')):
            with self.assertRaises(ValueError) as caught:
                platform_tools.open_target('codex://threads/abc')
        self.assertEqual(str(caught.exception), message)

    def test_codex_without_startfile_has_actionable_error(self):
        with patch.object(os, 'startfile', create=True, new=None):
            with self.assertRaises(ValueError) as caught:
                platform_tools.open_target('codex://threads/abc')
        self.assertEqual(str(caught.exception),
                         '无法打开 codex:// 链接:请确认已安装并注册 ChatGPT/Codex 桌面协议。')

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

    def test_open_directory_creates_then_delegates_to_open_path(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / 'stage'
            with patch('platform_tools.open_path', return_value='opened') as open_path:
                self.assertEqual(platform_tools.open_directory(target), 'opened')
            self.assertTrue(target.is_dir())
            open_path.assert_called_once_with(target)

    def test_start_menu_scan_prefers_installed_shortcut_over_uninstaller(self):
        with tempfile.TemporaryDirectory() as td, \
             patch.dict(os.environ, {'APPDATA': td, 'PROGRAMDATA': str(Path(td) / 'programdata')}):
            folder = Path(td) / 'Microsoft/Windows/Start Menu/Programs/剪映'
            folder.mkdir(parents=True)
            (folder / '剪映专业版卸载.lnk').write_text('', encoding='utf-8')
            expected = folder / '剪映专业版.lnk'
            expected.write_text('', encoding='utf-8')
            self.assertEqual(platform_tools.find_editor_shortcut(), expected)

    def test_start_menu_scan_returns_none_when_nothing_matches(self):
        with tempfile.TemporaryDirectory() as td, \
             patch.dict(os.environ, {'APPDATA': td, 'PROGRAMDATA': str(Path(td) / 'programdata')}):
            self.assertIsNone(platform_tools.find_editor_shortcut())


class FakeWinmm:
    """假 winmm：每次 AddBuffer 都把一块 0.1 秒、峰值固定的样本填进缓冲并标记 DONE。"""
    def __init__(self, devices=1, open_code=0, sample=1200):
        import array
        self.devices, self.open_code, self.calls = devices, open_code, []
        self.chunk = array.array('h', [sample, -sample] * (platform_tools._RECORD_CHUNK_BYTES // 4)).tobytes()
    def waveInGetNumDevs(self):
        return self.devices
    def waveInOpen(self, handle, device, fmt, callback, instance, flags):
        self.calls.append('open')
        return self.open_code
    def waveInPrepareHeader(self, handle, header, size):
        return 0
    def waveInAddBuffer(self, handle, header, size):
        import ctypes
        item = header._obj
        ctypes.memmove(item.lpData, self.chunk, len(self.chunk))
        item.dwBytesRecorded, item.dwFlags = len(self.chunk), item.dwFlags | platform_tools._WHDR_DONE
        return 0
    def waveInStart(self, handle):
        return 0
    def waveInReset(self, handle):
        self.calls.append('reset')
    def waveInUnprepareHeader(self, handle, header, size):
        return 0
    def waveInClose(self, handle):
        self.calls.append('close')


class MicrophoneRecorderTests(unittest.TestCase):
    """REQ-S01-71：录音会话收集 16 kHz 单声道 PCM，录满上限自动结束，stop() 交回 WAV 与峰值。"""
    def test_records_until_limit_and_returns_wav(self):
        import struct
        import time
        winmm = FakeWinmm(sample=1200)
        recorder = platform_tools.MicrophoneRecorder(max_seconds=0.5, winmm=winmm)
        self.assertEqual(recorder.start(), '')
        for _ in range(200):
            if recorder.finished:break
            time.sleep(0.01)
        self.assertTrue(recorder.finished, '录满上限应自动结束')
        wav, peak = recorder.stop()
        self.assertEqual(peak, 1200)
        self.assertGreaterEqual(recorder.seconds, 0.5)
        self.assertEqual(wav[:4] + wav[8:16], b'RIFFWAVEfmt ')
        channels, rate = struct.unpack('<HI', wav[22:28])
        self.assertEqual((channels, rate), (1, platform_tools.RECORD_RATE))
        self.assertEqual(struct.unpack('<I', wav[40:44])[0], len(wav) - 44)
        self.assertEqual(winmm.calls[-2:], ['reset', 'close'])

    def test_stop_ends_recording_early(self):
        winmm = FakeWinmm()
        recorder = platform_tools.MicrophoneRecorder(max_seconds=60, winmm=winmm)
        self.assertEqual(recorder.start(), '')
        recorder.stop()
        self.assertTrue(recorder.finished)
        self.assertLess(recorder.seconds, 60)
        self.assertIn('close', winmm.calls)

    def test_missing_or_busy_device_reports_reason(self):
        self.assertIn('没有找到麦克风', platform_tools.MicrophoneRecorder(winmm=FakeWinmm(devices=0)).start())
        busy = platform_tools.MicrophoneRecorder(winmm=FakeWinmm(open_code=4))
        self.assertIn('错误码 4', busy.start())
        self.assertFalse(busy.finished)
        with patch.object(platform_tools.os, 'name', 'posix'):
            self.assertTrue(platform_tools.MicrophoneRecorder().start())


