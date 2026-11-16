# -*- coding: utf-8 -*-
"""离线 ASR 子进程客户端（domain/offline_asr_client）与后端路由测试。

全部使用假宿主/假进程/假降级会话，不启动真实引擎、不下载模型，
可在随附零依赖解释器下运行。
"""

import json
import os
import queue
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

PROGRAM = Path(__file__).resolve().parents[1]
if str(PROGRAM) not in sys.path:
    sys.path.insert(0, str(PROGRAM))

import domain.offline_asr_client as client  # noqa: E402
import domain.speech_api as speech_api  # noqa: E402


def wait_for(predicate, timeout=5.0, interval=0.01):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def drain(session):
    events = []
    while True:
        try:
            events.append(session.events.get(timeout=0.2))
        except queue.Empty:
            return events


class FakeHost:
    """假引擎宿主：记录命令与音频，测试手动驱动 ``_engine_message``。"""

    def __init__(self, *, attach_error=None):
        self.attached = None
        self.commands = []
        self.feeds = []
        self.killed = []
        self.attach_error = attach_error

    def attach(self, session):
        if self.attach_error is not None:
            raise self.attach_error
        if self.attached is not None:
            raise client.EngineBusy('busy')
        self.attached = session

    def detach(self, session):
        if self.attached is session:
            self.attached = None

    def command(self, message):
        self.commands.append(message)

    def feed(self, pcm):
        self.feeds.append(pcm)

    def kill(self, reason):
        self.killed.append(reason)
        if self.attached is not None:
            self.attached._engine_dead(reason)

    def emit(self, message):
        if self.attached is not None:
            self.attached._engine_message(message)


class FakeDelegate:
    """假云端降级会话：与 RealtimeSession 同接口。"""

    def __init__(self):
        self.events = queue.Queue()
        self.sent = []
        self.started = False
        self.finished = False
        self.cancelled = False

    def start(self):
        self.started = True

    def send(self, pcm):
        self.sent.append(pcm)

    def finish(self):
        self.finished = True
        self.events.put(('closed', '', ''))

    def cancel(self):
        self.cancelled = True
        self.events.put(('closed', '', ''))


def settings(**overrides):
    base = {'backend': 'offline', 'timeout': 5,
            'offline': {'python': '', 'cache_dir': '', 'threads': '',
                        'vad_trailing_ms': 500}}
    base.update(overrides)
    return base


class EnvironmentTests(unittest.TestCase):
    def test_missing_python_reports_reason(self):
        with tempfile.TemporaryDirectory() as td:
            fake = {'backend': 'offline',
                    'offline': {'python': str(Path(td) / 'nope.exe')}}
            reason = client.environment_problem(fake)
        self.assertIn('离线识别环境未安装', reason)
        self.assertIn('nope.exe', reason)

    def test_existing_python_and_script_pass(self):
        fake = settings(offline={'python': sys.executable})
        self.assertEqual(client.environment_problem(fake), '')
        self.assertEqual(client.missing_reason(fake), '')

    def test_resolve_python_prefers_setting(self):
        self.assertEqual(client.resolve_python(settings(offline={'python': 'X:\\py.exe'})),
                         'X:\\py.exe')
        self.assertTrue(client.resolve_python(settings()).endswith('python.exe')
                        if os.name == 'nt' else client.resolve_python(settings()).endswith('python'))


class SessionFlowTests(unittest.TestCase):
    def _session(self, host, **kw):
        return client.OfflineAsrSession(settings(**kw), host=host)

    def test_sentence_becomes_final_and_done_closes(self):
        host = FakeHost()
        session = self._session(host)
        session.start()
        session.send(b'\x01\x02')
        session.finish()
        self.assertTrue(wait_for(lambda: any(c['cmd'] == 'stop' for c in host.commands)))
        host.emit({'type': 'sentence', 'text': '你好世界', 'start_ms': 0, 'end_ms': 900})
        host.emit({'type': 'sentence', 'text': '第二句', 'start_ms': 900, 'end_ms': 1800})
        host.emit({'type': 'done'})
        events = drain(session)
        kinds = [e[0] for e in events]
        self.assertEqual(kinds[-1], 'closed')
        finals = [e for e in events if e[0] == 'final']
        self.assertEqual([e[2] for e in finals], ['你好世界', '第二句'])
        self.assertEqual([e[1] for e in finals], ['s1', 's2'])
        self.assertFalse(any(e[0] == 'partial' for e in events))
        start_cmd = host.commands[0]
        self.assertEqual(start_cmd['cmd'], 'start')
        self.assertEqual(start_cmd['sample_rate'], 16000)
        self.assertIn('vad', start_cmd)
        self.assertEqual(start_cmd['vad']['trailing_ms'], 500)
        self.assertTrue(host.feeds)
        self.assertIsNone(host.attached)

    def test_engine_error_and_death_surface_events(self):
        host = FakeHost()
        session = self._session(host)
        session.start()
        wait_for(lambda: host.attached is session)
        host.emit({'type': 'error', 'message': '引擎内部错误'})
        session.cancel()
        events = drain(session)
        self.assertIn(('error', '', '引擎内部错误'), events)
        self.assertEqual(events[-1][0], 'closed')

    def test_process_death_mid_stream_fails_closed(self):
        host = FakeHost()
        session = self._session(host)
        session.start()
        wait_for(lambda: host.attached is session)
        host.attached = None
        session._engine_dead('离线识别进程意外退出')
        events = drain(session)
        self.assertIn(('error', '', '离线识别进程意外退出'), events)
        self.assertEqual(events[-1][0], 'closed')

    def test_cancel_sends_cancel_command(self):
        host = FakeHost()
        session = self._session(host)
        session.start()
        wait_for(lambda: host.attached is session)
        session.send(b'\x00')
        session.cancel()
        self.assertTrue(wait_for(lambda: any(c['cmd'] == 'cancel' for c in host.commands)))
        self.assertFalse(any(c['cmd'] == 'stop' for c in host.commands))
        events = drain(session)
        self.assertEqual(events[-1][0], 'closed')

    def test_stop_timeout_kills_engine(self):
        host = FakeHost()
        session = self._session(host, timeout=0.2)
        session.start()
        session.finish()
        self.assertTrue(wait_for(lambda: bool(host.killed), timeout=8))
        self.assertIn('超时', host.killed[0])
        events = drain(session)
        errors = [e for e in events if e[0] == 'error']
        self.assertTrue(errors and '超时' in errors[0][2])
        self.assertEqual(events[-1][0], 'closed')

    def test_unavailable_falls_back_to_cloud_with_notice(self):
        host = FakeHost(attach_error=client.EngineUnavailable('环境未安装'))
        delegate = FakeDelegate()
        session = client.OfflineAsrSession(settings(), host=host,
                                           fallback=lambda s: delegate)
        session.start()
        session.send(b'\x01')
        session.finish()
        self.assertTrue(wait_for(lambda: delegate.finished))
        events = drain(session)
        self.assertEqual(events[0][0], 'log')
        self.assertIn('云端识别', events[0][2])
        self.assertEqual(events[-1][0], 'closed')
        self.assertEqual(delegate.sent, [b'\x01'])

    def test_unavailable_without_fallback_reports_error(self):
        host = FakeHost(attach_error=client.EngineUnavailable('环境未安装'))
        session = client.OfflineAsrSession(settings(), host=host)
        session.start()
        events = drain(session)
        self.assertEqual(events[0][0], 'error')
        self.assertIn('环境未安装', events[0][2])
        self.assertEqual(events[-1][0], 'closed')

    def test_busy_engine_falls_back(self):
        host = FakeHost()
        host.attached = object()  # 占用中
        delegate = FakeDelegate()
        session = client.OfflineAsrSession(settings(), host=host,
                                           fallback=lambda s: delegate)
        session.start()
        session.finish()
        self.assertTrue(wait_for(lambda: delegate.finished))
        events = drain(session)
        self.assertIn('云端识别', events[0][2])

    def test_hotword_and_vad_params_in_start(self):
        host = FakeHost()
        session = client.OfflineAsrSession(
            settings(offline={'python': '', 'cache_dir': '', 'threads': '',
                              'vad_trailing_ms': 800, 'hotword': '林小满'}),
            host=host)
        session.start()
        session.finish()
        self.assertTrue(wait_for(lambda: any(c['cmd'] == 'stop' for c in host.commands)))
        command = host.commands[0]
        self.assertEqual(command['hotword'], '林小满')
        self.assertEqual(command['vad'], {'trailing_ms': 800})


class FakePopen:
    """假子process：stdout 先给 ready 行然后永久阻塞（模拟常驻引擎）。"""

    def __init__(self, ready=True):
        self.pid = 99999999
        self.stdin = _FakeStdin()
        self.stderr = iter(())
        self.stdout = _Stdout(ready)
        self.returncode = None
        self.killed = False

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.returncode = 0
        return 0

    def kill(self):
        self.killed = True
        self.returncode = -9


class _FakeStdin:
    def __init__(self):
        self.lines = []

    def write(self, text):
        self.lines.append(text)

    def flush(self):
        pass


class _Stdout:
    def __init__(self, ready):
        self.ready = ready
        self.sent = False

    def __iter__(self):
        if self.ready:
            yield json.dumps({'type': 'ready'}) + '\n'
        # 常驻：一直阻塞直到进程被杀（测试里用 daemon 线程，不会泄漏到退出）
        blocker = threading.Event()
        blocker.wait()


class AcquireTests(unittest.TestCase):
    def setUp(self):
        client._HOST = None

    def tearDown(self):
        client._HOST = None

    def test_acquire_spawns_and_waits_ready(self):
        fake = FakePopen(ready=True)
        with mock.patch.object(client.platform_tools, 'launch_text_process',
                               return_value=fake) as launch, \
             mock.patch.object(client.platform_tools, 'terminate_process_tree',
                               return_value=True):
            host = client.acquire(settings(offline={'python': sys.executable}),
                                  log_sink=lambda _m: None)
            self.assertEqual(host.state, 'ready')
            command = launch.call_args[0][0]
            self.assertEqual(command[0], sys.executable)
            self.assertTrue(str(command[1]).endswith('offline_asr_server.py'))
            host.shutdown()

    def test_acquire_missing_env_raises_without_spawn(self):
        with tempfile.TemporaryDirectory() as td:
            bad = settings(offline={'python': str(Path(td) / 'none.exe')})
            with self.assertRaises(client.EngineUnavailable) as ctx:
                client.acquire(bad)
        self.assertIn('离线识别环境未安装', str(ctx.exception))

    def test_acquire_dead_process_reports_reason(self):
        fake = FakePopen(ready=False)
        fake.stdout = iter([])   # 立即 EOF → _on_exit
        with mock.patch.object(client.platform_tools, 'launch_text_process',
                               return_value=fake):
            host = client._host()
            host.spawn(settings(offline={'python': sys.executable}))
            deadline = time.monotonic() + 5
            while host.state != 'dead' and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertEqual(host.state, 'dead')
            with self.assertRaises(client.EngineUnavailable) as ctx:
                client.acquire(settings(offline={'python': sys.executable}))
            self.assertTrue(str(ctx.exception))


class SpeechApiRoutingTests(unittest.TestCase):
    def test_create_session_routes_by_backend(self):
        cloud = speech_api.create_session({**speech_api.DEFAULTS, 'backend': 'cloud'})
        self.assertIsInstance(cloud, speech_api.RealtimeSession)
        offline = speech_api.create_session({**speech_api.DEFAULTS, 'backend': 'offline'})
        self.assertIsInstance(offline, client.OfflineAsrSession)

    def test_offline_session_gets_fallback_only_with_key(self):
        merged = {**speech_api.DEFAULTS, 'backend': 'offline'}
        with mock.patch.object(speech_api, 'api_key', return_value=''):
            self.assertIsNone(speech_api.create_session(merged).fallback)
        with mock.patch.object(speech_api, 'api_key', return_value='sk-x'):
            self.assertIsNotNone(speech_api.create_session(merged).fallback)

    def test_missing_reason_backend_aware(self):
        merged = {**speech_api.DEFAULTS, 'backend': 'offline',
                  'offline': {**speech_api.DEFAULTS['offline'],
                              'python': 'Z:\\definitely\\missing.exe'}}
        with mock.patch.object(speech_api, 'api_key', return_value=''):
            self.assertIn('离线识别环境未安装', speech_api.missing_reason(merged))
        with mock.patch.object(speech_api, 'api_key', return_value='sk-x'):
            self.assertEqual(speech_api.missing_reason(merged), '')
        cloud = {**merged, 'backend': 'cloud'}
        with mock.patch.object(speech_api, 'api_key', return_value=''):
            self.assertIn('DASHSCOPE_API_KEY', speech_api.missing_reason(cloud))

    def test_save_settings_backend_and_offline_section(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / '语音识别.json'
            values = {**speech_api.DEFAULTS,
                      'backend': 'cloud',
                      'offline': {'python': 'D:\\asr\\python.exe',
                                  'vad_trailing_ms': '800'}}
            merged = speech_api.save_settings(values, publish=lambda p, o: target.write_text(
                json.dumps(o, ensure_ascii=False), encoding='utf-8'), path=target)
            self.assertEqual(merged['backend'], 'cloud')
            self.assertEqual(merged['offline']['python'], 'D:\\asr\\python.exe')
            self.assertEqual(merged['offline']['vad_trailing_ms'], 800)
            saved = json.loads(target.read_text(encoding='utf-8'))
            self.assertEqual(saved['backend'], 'cloud')
            self.assertEqual(saved['offline']['vad_trailing_ms'], 800)
            back = speech_api.read_settings(target)
            self.assertEqual(back['backend'], 'cloud')
            self.assertEqual(back['offline']['vad_trailing_ms'], 800)
            for bad in ({'backend': 'local'}, {'offline': {'vad_trailing_ms': '10'}},
                        {'offline': 'not-a-dict'}):
                with self.assertRaises(ValueError):
                    speech_api.save_settings({**speech_api.DEFAULTS, **bad},
                                             publish=lambda p, o: None, path=target)


if __name__ == '__main__':
    unittest.main()
