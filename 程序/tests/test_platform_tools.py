# -*- coding: utf-8 -*-
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import contract.platform_tools as platform_tools


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
             patch('contract.platform_tools.subprocess.run') as run:
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
                 patch('contract.platform_tools.shutil.which', return_value=None):
                with self.assertRaisesRegex(ValueError, '默认打开器'):
                    platform_tools.open_path(td)

    def test_http_target_uses_browser_but_other_schemes_are_rejected(self):
        with patch('contract.platform_tools.webbrowser.open', return_value=True) as browser:
            self.assertEqual(platform_tools.open_target('https://example.test/task'), 'https://example.test/task')
        browser.assert_called_once_with('https://example.test/task')
        with self.assertRaisesRegex(ValueError, 'HTTP'):
            platform_tools.open_target('file:///unsafe')

    def test_codex_targets_are_passed_unchanged_to_startfile(self):
        for target in ('codex://threads/abc',
                       'codex://new?path=D%3A%2Fproject&prompt=hello%20world'):
            with self.subTest(target=target), \
                 patch.object(os, 'startfile', create=True) as startfile, \
                 patch('contract.platform_tools.webbrowser.open') as browser:
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
            with patch('contract.platform_tools.open_path', return_value='opened') as open_path:
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
                 patch('contract.platform_tools.subprocess.Popen') as launch:
                process = platform_tools.launch_windows_app(executable, '剪映专业版')
            self.assertIs(process, launch.return_value)
            launch.assert_called_once_with([str(executable)], cwd=str(executable.parent), env=None,
                                           creationflags=0)

    def test_open_directory_creates_then_delegates_to_open_path(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / 'stage'
            with patch('contract.platform_tools.open_path', return_value='opened') as open_path:
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

    def test_on_chunk_streams_blocks_instead_of_buffering(self):
        import time
        chunks = []
        recorder = platform_tools.MicrophoneRecorder(max_seconds=0.3, winmm=FakeWinmm(), on_chunk=chunks.append)
        self.assertEqual(recorder.start(), '')
        for _ in range(200):
            if recorder.finished:break
            time.sleep(0.01)
        wav, peak = recorder.stop()
        self.assertGreaterEqual(len(chunks), 3)
        self.assertTrue(all(len(chunk) == platform_tools._RECORD_CHUNK_BYTES for chunk in chunks))
        self.assertGreaterEqual(recorder.seconds, 0.3)
        self.assertEqual(len(recorder.pcm), 0, '流式模式不攒整段')
        self.assertEqual(peak, 1200)


class RequestsJsonTlsTests(unittest.TestCase):
    def capture_transport(self, environment=None, proxy=None):
        import requests
        from types import SimpleNamespace
        from urllib.request import Request
        seen = {}

        def send(adapter, prepared, **settings):
            pool = adapter.get_connection_with_tls_context(
                prepared, settings['verify'], proxies=settings['proxies'], cert=settings['cert'])
            seen.update(adapter=adapter, settings=settings, pool=pool)
            if proxy:
                seen['proxy_manager'] = adapter.proxy_manager_for(proxy)
            return SimpleNamespace(status_code=200, headers={}, close=lambda: None)

        with patch.dict(os.environ, environment or {}, clear=True), patch.object(requests.adapters.HTTPAdapter, 'send', send):
            response = platform_tools.RequestsJsonOpener().open(Request('https://example.test/api'), timeout=3)
            self.addCleanup(response.close)
        return seen

    def assert_verified_context(self, context):
        import ssl
        self.assertIsInstance(context, ssl.SSLContext)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)

    def test_default_context_retains_system_and_certifi_trust_in_actual_pool(self):
        import certifi
        import ssl
        system = ssl.create_default_context()
        public = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        public.load_verify_locations(certifi.where())
        seen = self.capture_transport()
        context = seen['pool'].conn_kw.get('ssl_context')
        self.assert_verified_context(context)
        trusted = set(context.get_ca_certs(binary_form=True))
        self.assertTrue(set(system.get_ca_certs(binary_form=True)) <= trusted, 'system trust must remain included')
        self.assertTrue(set(public.get_ca_certs(binary_form=True)) <= trusted, 'certifi trust must remain included')
        self.assertIs(seen['adapter'].poolmanager.connection_pool_kw.get('ssl_context'), context)
        retry = seen['adapter'].max_retries
        self.assertEqual(retry.total, 0)
        self.assertIs(seen['settings']['verify'], True)

    def test_default_context_loads_certifi_after_system_defaults(self):
        import certifi
        import ssl
        from unittest.mock import Mock
        context = Mock()
        with patch.object(ssl, 'create_default_context', return_value=context) as create:
            seen = self.capture_transport()
        create.assert_called_once_with()
        context.load_verify_locations.assert_called_once_with(certifi.where())
        self.assertIs(seen['pool'].conn_kw.get('ssl_context'), context)

    def test_http_and_https_environment_proxies_preserve_verified_contexts(self):
        for proxy in ('http://proxy.test:8080', 'https://proxy.test:8443'):
            with self.subTest(scheme=proxy.split(':')[0]):
                seen = self.capture_transport({'HTTPS_PROXY': proxy}, proxy)
                manager = seen['proxy_manager']
                context = manager.connection_pool_kw.get('ssl_context')
                self.assert_verified_context(context)
                self.assertIs(seen['pool'].conn_kw.get('ssl_context'), context)
                self.assertIs(manager.proxy_ssl_context, context)
                self.assertEqual(seen['settings']['proxies']['https'], proxy)

    def test_explicit_ca_environment_selects_only_that_bundle_and_requests_wins(self):
        import certifi
        import ssl
        public = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        public.load_verify_locations(certifi.where())
        public_ca = public.get_ca_certs(binary_form=True)[0]
        with tempfile.TemporaryDirectory() as folder:
            bundle = Path(folder) / 'public-test-ca.pem'
            bundle.write_text(ssl.DER_cert_to_PEM_cert(public_ca), encoding='ascii')
            for variable in ('REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE'):
                environment = {variable: str(bundle)}
                if variable == 'REQUESTS_CA_BUNDLE':
                    environment['CURL_CA_BUNDLE'] = str(Path(folder) / 'must-not-load.pem')
                with self.subTest(variable=variable), patch.object(ssl, 'create_default_context', wraps=ssl.create_default_context) as create:
                    seen = self.capture_transport(environment)
                    create.assert_not_called()
                    context = seen['pool'].conn_kw.get('ssl_context')
                    self.assert_verified_context(context)
                    self.assertTrue(set(context.get_ca_certs(binary_form=True)) == {public_ca}, 'explicit bundle must not gain system trust')
                    self.assertEqual(seen['settings']['verify'], str(bundle))

    def test_empty_ca_environment_uses_default_trust(self):
        seen = self.capture_transport({'REQUESTS_CA_BUNDLE': '', 'CURL_CA_BUNDLE': ''})
        self.assert_verified_context(seen['pool'].conn_kw.get('ssl_context'))
        self.assertIs(seen['settings']['verify'], True)


class WebSocketTests(unittest.TestCase):
    """REQ-S01-71：标准库 WebSocket 客户端：握手校验、带掩码文本帧、分片、ping/pong、关闭与拒绝。"""
    def serve(self, handler):
        import socket
        import threading
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0)); listener.listen(1)
        self.addCleanup(listener.close)
        seen = {}

        def run():
            conn, _ = listener.accept()
            with conn:
                request = b''
                while b'\r\n\r\n' not in request:
                    request += conn.recv(4096)
                seen['request'] = request.decode('latin-1')
                handler(conn, seen['request'])
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        return 'ws://127.0.0.1:%d/realtime?model=m' % listener.getsockname()[1], seen

    @staticmethod
    def accept(request):
        import base64
        import hashlib
        key = [line.split(':', 1)[1].strip() for line in request.split('\r\n') if line.lower().startswith('sec-websocket-key')][0]
        token = base64.b64encode(hashlib.sha1((key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
        return ('HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
                'Sec-WebSocket-Accept: %s\r\n\r\n' % token).encode()

    @staticmethod
    def read_frame(conn):
        def exact(count):
            data = b''
            while len(data) < count:
                data += conn.recv(count - len(data))
            return data
        head = exact(2)
        mask = exact(4) if head[1] & 0x80 else b''
        payload = exact(head[1] & 0x7F)
        if mask:
            payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        return head[0] & 0x0F, payload, bool(mask)

    def test_handshake_text_fragments_ping_and_close(self):
        frames = {}

        def handler(conn, request):
            conn.sendall(self.accept(request) + b'\x01\x03\xe4\xb8\xbb')        # 首片紧跟在握手响应后
            conn.sendall(b'\x89\x02hi' + b'\x80\x03\xe8\xa7\x92')              # 中间插一个 ping，再给末片
            frames['pong'] = self.read_frame(conn)
            frames['text'] = self.read_frame(conn)
            conn.sendall(b'\x88\x00')
            frames['close'] = self.read_frame(conn)

        url, seen = self.serve(handler)
        ws = platform_tools.open_websocket(url, headers={'Authorization': 'Bearer t'}, timeout=5)
        self.assertEqual(ws.recv_text(), '主角')
        ws.send_text('你好')
        self.assertIsNone(ws.recv_text())
        self.assertIn('GET /realtime?model=m HTTP/1.1', seen['request'])
        self.assertIn('Authorization: Bearer t', seen['request'])
        self.assertEqual(frames['pong'], (0xA, b'hi', True))
        self.assertEqual(frames['text'], (0x1, '你好'.encode('utf-8'), True), '客户端帧必须带掩码')
        self.assertEqual(frames['close'][0], 0x8)

    def test_refused_handshake_reports_status(self):
        url, _ = self.serve(lambda conn, request: conn.sendall(b'HTTP/1.1 401 Unauthorized\r\nContent-Length: 0\r\n\r\n'))
        with self.assertRaises(platform_tools.WebSocketRefused) as caught:
            platform_tools.open_websocket(url, timeout=5)
        self.assertEqual(caught.exception.status, 401)
        with self.assertRaises(ValueError):
            platform_tools.open_websocket('https://example.test/')


class RunProcessEncodingTests(unittest.TestCase):
    """R3315：text=True 缺省必须钉 UTF-8——cp936 本地化下 GBK 解码会让
    reader 线程崩溃、stdout 变 None；显式编码/错误策略的调用方不被覆盖。"""

    def test_text_mode_defaults_to_utf8(self):
        import subprocess as sp
        import sys
        code = "import sys;sys.stdout.write('漫剧助手')"
        done = platform_tools.run_process([sys.executable, '-X', 'utf8', '-c', code],
                                          capture_output=True, text=True)
        self.assertEqual(done.stdout, '漫剧助手')

    def test_explicit_encoding_is_respected(self):
        import subprocess as sp
        seen = {}
        def fake_run(command, **kwargs):
            seen.update(kwargs)
            return sp.CompletedProcess(command, 0, '', '')
        platform_tools.run_process(['x'], run=fake_run, text=True, encoding='gbk')
        self.assertEqual(seen.get('encoding'), 'gbk')
        self.assertNotIn('errors', seen)

    def test_binary_mode_gets_no_encoding(self):
        import subprocess as sp
        seen = {}
        def fake_run(command, **kwargs):
            seen.update(kwargs)
            return sp.CompletedProcess(command, 0, b'', b'')
        platform_tools.run_process(['x'], run=fake_run, capture_output=True)
        self.assertNotIn('encoding', seen)
