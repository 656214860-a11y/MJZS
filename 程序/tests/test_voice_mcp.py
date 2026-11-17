# -*- coding: utf-8 -*-
"""agent/voice_mcp_server：MCP stdio JSON-RPC 与 voice_transcribe 工具（WAV/PCM→离线识别）。"""
import base64
import io
import json
import os
import queue
import struct
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import agent.voice_mcp_server as mcp


def make_wav(path, pcm, rate=16000, channels=1, bits=16):
    """手写 RIFF/WAVE：产品运行时无 wave 标准库，测试同样自备。"""
    sampwidth = bits // 8
    byte_rate = rate * channels * sampwidth
    block_align = channels * sampwidth
    fmt = struct.pack('<HHIIHH', 1, channels, rate, byte_rate, block_align, bits)
    body = b'fmt ' + struct.pack('<I', len(fmt)) + fmt + b'data' + struct.pack('<I', len(pcm)) + pcm
    Path(path).write_bytes(b'RIFF' + struct.pack('<I', 4 + len(body)) + b'WAVE' + body)


class FakeSession:
    """会话替身：记录喂入，start 后回放预置事件。"""
    def __init__(self, events):
        self.events = queue.Queue()
        self._events = list(events)
        self.sent, self.started, self.finished, self.cancelled = [], False, False, False

    def start(self):
        self.started = True
        for event in self._events:
            self.events.put(event)

    def send(self, pcm):
        self.sent.append(bytes(pcm))

    def finish(self):
        self.finished = True

    def cancel(self):
        self.cancelled = True


class ResampleTests(unittest.TestCase):
    def test_same_rate_passthrough_and_double_rate(self):
        pcm = struct.pack('<4h', 0, 1000, -1000, 500)
        self.assertEqual(mcp._resample_pcm16(pcm, 16000), pcm)
        doubled = mcp._resample_pcm16(pcm, 8000)
        self.assertEqual(len(doubled), len(pcm) * 2)
        self.assertEqual(mcp._resample_pcm16(b'', 8000), b'')


class PcmLoadTests(unittest.TestCase):
    def test_wav_mono_16bit_ok_and_bad_formats_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            good = Path(td) / 'a.wav'
            make_wav(good, struct.pack('<4h', 1, 2, 3, 4), rate=8000)
            pcm, rate = mcp._load_pcm({'audio_path': str(good)})
            self.assertEqual(rate, 16000, '重采样后按目标率计')
            self.assertEqual(len(pcm), 8 * 2, '8k→16k 时长翻倍')
            stereo = Path(td) / 'stereo.wav'
            make_wav(stereo, struct.pack('<8h', *range(8)), channels=2)
            with self.assertRaises(ValueError):
                mcp._load_pcm({'audio_path': str(stereo)})
            wide = Path(td) / 'wide.wav'
            make_wav(wide, b'\x00' * 16, bits=24)
            with self.assertRaises(ValueError):
                mcp._load_pcm({'audio_path': str(wide)})
            with self.assertRaises(ValueError):
                mcp._load_pcm({'audio_path': str(Path(td) / 'missing.wav')})

    def test_pcm_base64_path_and_argument_validation(self):
        blob = base64.b64encode(struct.pack('<4h', 1, 2, 3, 4)).decode('ascii')
        pcm, rate = mcp._load_pcm({'pcm_base64': blob, 'sample_rate': 16000})
        self.assertEqual((pcm, rate), (struct.pack('<4h', 1, 2, 3, 4), 16000))
        for bad in ({}, {'audio_path': 'a.wav', 'pcm_base64': blob},
                    {'pcm_base64': '!!!'}, {'pcm_base64': blob, 'sample_rate': 99999},
                    {'pcm_base64': base64.b64encode(b'').decode('ascii')}):
            with self.assertRaises(ValueError, msg=repr(bad)):
                mcp._load_pcm(bad)


class TranscribeTests(unittest.TestCase):
    def test_feeds_chunks_and_joins_finals_with_forced_offline(self):
        captured = {}

        def factory(settings):
            captured['settings'] = settings
            return FakeSession([('partial', 's1', '半'), ('final', 's1', '你好。'),
                                ('final', 's2', '再见。'), ('closed', '', '')])

        pcm = struct.pack('<%dh' % (mcp.PCM_CHUNK // 2 * 3), *([1000] * (mcp.PCM_CHUNK // 2 * 3)))
        text = mcp.transcribe({'pcm_base64': base64.b64encode(pcm).decode('ascii'),
                               'hotword': '漫剧 子进程'},
                              session_factory=factory, settings={'backend': 'cloud'})
        self.assertEqual(text, '你好。再见。')
        self.assertEqual(captured['settings']['backend'], 'offline', 'MCP 固定走离线')
        self.assertEqual(captured['settings']['offline']['hotword'], '漫剧 子进程')

    def test_error_event_becomes_value_error(self):
        def factory(settings):
            return FakeSession([('error', '', '引擎崩了'), ('closed', '', '')])

        with self.assertRaises(ValueError) as ctx:
            mcp.transcribe({'pcm_base64': base64.b64encode(b'\x01\x00' * 100).decode('ascii')},
                           session_factory=factory, settings={})
        self.assertIn('引擎崩了', str(ctx.exception))

    def test_send_finish_called_and_cancel_on_close(self):
        session_box = {}

        def factory(settings):
            session = FakeSession([('final', 's1', '好'), ('closed', '', '')])
            session_box['session'] = session
            return session

        mcp.transcribe({'pcm_base64': base64.b64encode(b'\x01\x00' * 64).decode('ascii')},
                       session_factory=factory, settings={})
        session = session_box['session']
        self.assertTrue(session.started and session.finished)
        self.assertTrue(session.sent, 'PCM 分块送入')
        self.assertTrue(session.cancelled, '收尾统一 cancel 清理')


class ProtocolTests(unittest.TestCase):
    def test_initialize_tools_list_and_notification(self):
        init = mcp.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
                           'params': {'protocolVersion': '2024-11-05'}})
        self.assertEqual(init['result']['serverInfo']['name'], 'voice-transcribe')
        self.assertEqual(init['result']['protocolVersion'], '2024-11-05')
        self.assertEqual(init['result']['capabilities'], {'tools': {}})
        tools = mcp.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'})
        self.assertEqual([t['name'] for t in tools['result']['tools']], ['voice_transcribe'])
        self.assertIsNone(mcp.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'}))

    def test_tools_call_success_and_errors(self):
        def factory(settings):
            return FakeSession([('final', 's1', '转写结果'), ('closed', '', '')])

        call = {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call',
                'params': {'name': 'voice_transcribe',
                           'arguments': {'pcm_base64': base64.b64encode(b'\x01\x00' * 32).decode('ascii')}}}
        with patch.object(mcp, 'transcribe', wraps=mcp.transcribe) as spy:
            response = mcp.handle(call, session_factory=factory, settings={})
        result = response['result']
        self.assertFalse(result['isError'])
        self.assertEqual(result['content'][0]['text'], '转写结果')
        self.assertEqual(spy.call_args.kwargs['session_factory'], factory)
        bad = mcp.handle({'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call',
                          'params': {'name': 'voice_transcribe', 'arguments': {}}},
                         session_factory=factory, settings={})
        self.assertTrue(bad['result']['isError'])
        unknown = mcp.handle({'jsonrpc': '2.0', 'id': 5, 'method': 'tools/call',
                              'params': {'name': 'nope', 'arguments': {}}})
        self.assertIn('未知工具', unknown['error']['message'])
        self.assertIn('未知方法', mcp.handle({'jsonrpc': '2.0', 'id': 6, 'method': 'x/y'})['error']['message'])

    def test_main_stdio_loop(self):
        lines = [json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'}),
                 json.dumps({'jsonrpc': '2.0', 'method': 'notifications/initialized'}),
                 json.dumps({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'}),
                 'not json',
                 json.dumps([1, 2, 3])]
        out = io.StringIO()
        with patch.object(sys, 'stdin', io.StringIO('\n'.join(lines) + '\n')), \
             redirect_stdout(out):
            mcp.main()
        responses = [json.loads(line) for line in out.getvalue().splitlines() if line.strip()]
        self.assertEqual([r.get('id') for r in responses], [1, 2, None],
                         '通知不回包；坏 JSON 回 id=null 错误')
        self.assertEqual(responses[2]['error']['code'], -32603)


class StdioEncodingTests(unittest.TestCase):
    """MCP stdio 契约：必须输出 UTF-8——中文 Windows 默认 GBK 会把中文打成乱码。"""

    def test_server_stdout_emits_utf8_chinese(self):
        script = Path(mcp.__file__).resolve()
        # PYTHONIOENCODING=gbk 强制子进程复现中文 Windows 默认编码，验证服务自行固定 UTF-8。
        env = dict(os.environ, PYTHONUTF8='0', PYTHONIOENCODING='gbk')
        proc = subprocess.Popen(
            [sys.executable, str(script)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        try:
            out, _err = proc.communicate(input=b'not json\n', timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            self.fail('MCP 服务进程 30 秒未退出')
        text = out.decode('utf-8', errors='replace')
        payload = json.loads(text.strip().splitlines()[-1])
        self.assertIn('请求不是有效 JSON', payload['error']['message'])


if __name__ == '__main__':
    unittest.main()
