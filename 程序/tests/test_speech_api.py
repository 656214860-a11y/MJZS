import base64
import json
import queue
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import contract.platform_tools as platform_tools
import speech_api
from agent.core import save


class FakeSocket:
    """假 WebSocket：记下发出的消息；收到 session.finish 后依次回放 ``replies``。"""
    def __init__(self, replies):
        self.sent, self.replies, self.inbox, self.closed = [], list(replies), queue.Queue(), False

    def send_text(self, text):
        message = json.loads(text)
        self.sent.append(message)
        if message['type'] == 'session.finish':
            for reply in self.replies:
                self.inbox.put(reply if isinstance(reply, str) else json.dumps(reply, ensure_ascii=False))
            self.inbox.put(None)

    def recv_text(self):
        return self.inbox.get(timeout=5)

    def close(self):
        self.closed = True


def drain(session):
    events = []
    while not events or events[-1][0] != 'closed':
        events.append(session.events.get(timeout=5))
    return events


class SpeechApiTests(unittest.TestCase):
    """REQ-S01-71：实时语音识别默认阿里云 qwen3-asr-flash-realtime，可由 data/语音识别.json 覆盖，失败给中文原因。"""

    def test_defaults_and_user_override(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / '语音识别.json'
            self.assertEqual(speech_api.read_settings(path)['model'], 'qwen3-asr-flash-realtime')
            path.write_text(json.dumps({'model': 'my-asr', 'base_url': 'wss://asr.example.com/v1', 'unknown': 1}), encoding='utf-8')
            settings = speech_api.read_settings(path)
        self.assertEqual((settings['model'], settings['base_url']), ('my-asr', 'wss://asr.example.com/v1'))
        self.assertEqual(settings['key_env'], 'DASHSCOPE_API_KEY')
        self.assertNotIn('unknown', settings)
        self.assertEqual(speech_api.endpoint(settings), 'wss://asr.example.com/v1?model=my-asr')
        with self.assertRaises(ValueError):
            speech_api.endpoint({**settings, 'base_url': 'ws://asr.example.com/v1'})

    def test_session_streams_audio_and_reports_partial_then_final(self):
        socket = FakeSocket([
            {'type': 'session.created'},
            {'type': 'conversation.item.input_audio_transcription.text', 'item_id': 'a', 'text': '主角', 'stash': '走'},
            'not json',
            {'type': 'conversation.item.input_audio_transcription.completed', 'item_id': 'a', 'transcript': '主角走进雨夜。'},
            {'type': 'session.finished'}])
        opened = {}

        def connect(url, *, timeout, headers):
            opened.update(url=url, headers=headers)
            return socket

        session = speech_api.RealtimeSession(dict(speech_api.DEFAULTS), key='sk-test', connect=connect)
        session.start()
        session.send(b'\x01\x02')
        session.finish()
        events = drain(session)
        self.assertEqual(events, [('partial', 'a', '主角走'), ('final', 'a', '主角走进雨夜。'), ('closed', '', '')])
        self.assertEqual(opened['url'], 'wss://dashscope.aliyuncs.com/api-ws/v1/realtime?model=qwen3-asr-flash-realtime')
        self.assertEqual(opened['headers']['Authorization'], 'Bearer sk-test')
        kinds = [message['type'] for message in socket.sent]
        self.assertEqual(kinds, ['session.update', 'input_audio_buffer.append', 'session.finish'])
        update = socket.sent[0]['session']
        self.assertEqual((update['sample_rate'], update['input_audio_transcription']['language']), (16000, 'zh'))
        self.assertEqual(update['turn_detection']['silence_duration_ms'], 400)
        self.assertEqual(base64.b64decode(socket.sent[1]['audio']), b'\x01\x02')
        self.assertTrue(socket.closed)

    def test_failures_become_readable_reasons_without_key(self):
        settings = dict(speech_api.DEFAULTS)

        def denied(url, **kwargs):
            raise platform_tools.WebSocketRefused(401)

        def offline(url, **kwargs):
            raise ConnectionRefusedError()

        for connect, expected in ((denied, '密钥无效'), (offline, '连不上识别服务')):
            session = speech_api.RealtimeSession(settings, key='sk-secret', connect=connect)
            session.start()
            events = drain(session)
            self.assertEqual(events[0][0], 'error')
            self.assertIn(expected, events[0][2])
            self.assertNotIn('sk-secret', events[0][2])
            self.assertEqual(events[-1][0], 'closed')
        socket = FakeSocket([{'type': 'error', 'error': {'message': 'quota exceeded'}}])
        session = speech_api.RealtimeSession(settings, key='k', connect=lambda url, **kwargs: socket)
        session.start(); session.finish()
        self.assertIn('quota exceeded', drain(session)[0][2])
        with patch.object(speech_api, 'api_key', return_value=''):
            self.assertIn('DASHSCOPE_API_KEY', speech_api.missing_reason(settings))
            session = speech_api.RealtimeSession(settings, connect=denied)
            session.start()
            self.assertIn('DASHSCOPE_API_KEY', drain(session)[0][2])

    def test_save_settings_validates_and_writes_only_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'data' / '语音识别.json'
            merged = speech_api.save_settings({**speech_api.DEFAULTS, 'language': 'en', 'silence_ms': ' 600 '}, publish=save, path=target)
            self.assertEqual(json.loads(target.read_text(encoding='utf-8')), {'language': 'en', 'silence_ms': 600})
            self.assertEqual(merged['silence_ms'], 600)
            self.assertEqual(speech_api.read_settings(target)['language'], 'en', '保存后立即读到新值')
            for bad in ({'silence_ms': '50'}, {'timeout': 'abc'}, {'model': ' '}, {'base_url': 'https://x.test/'}):
                with self.assertRaises(ValueError):
                    speech_api.save_settings({**speech_api.DEFAULTS, **bad}, publish=save, path=target)
            self.assertEqual(json.loads(target.read_text(encoding='utf-8')), {'language': 'en', 'silence_ms': 600}, '校验失败不动文件')
            speech_api.save_settings(dict(speech_api.DEFAULTS), publish=save, path=target)
            self.assertEqual(json.loads(target.read_text(encoding='utf-8')), {})

if __name__ == '__main__':
    unittest.main()
