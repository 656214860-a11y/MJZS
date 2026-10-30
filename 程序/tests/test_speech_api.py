import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

import speech_api


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class SpeechApiTests(unittest.TestCase):
    """REQ-S01-71：语音识别默认阿里云 qwen3-asr-flash，可由 data/语音识别.json 覆盖，失败给中文原因。"""

    def test_defaults_and_user_override(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / '语音识别.json'
            self.assertEqual(speech_api.read_settings(path)['model'], 'qwen3-asr-flash')
            path.write_text(json.dumps({'model': 'my-asr', 'base_url': 'https://asr.example.com/v1', 'unknown': 1}), encoding='utf-8')
            settings = speech_api.read_settings(path)
        self.assertEqual((settings['model'], settings['base_url']), ('my-asr', 'https://asr.example.com/v1'))
        self.assertEqual(settings['key_env'], 'DASHSCOPE_API_KEY')
        self.assertNotIn('unknown', settings)

    def test_transcribe_posts_inline_wav_and_reads_text(self):
        sent = {}

        def opener(url, *, timeout, data, headers):
            sent.update(url=url, body=json.loads(data), headers=headers)
            reply = {'choices': [{'message': {'content': '主角走进雨夜。'}}]}
            return FakeResponse(json.dumps(reply, ensure_ascii=False).encode('utf-8'))

        text = speech_api.transcribe(b'RIFFdata', settings=dict(speech_api.DEFAULTS), key='sk-test', opener=opener)
        self.assertEqual(text, '主角走进雨夜。')
        self.assertEqual(sent['url'], 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions')
        self.assertEqual(sent['headers']['Authorization'], 'Bearer sk-test')
        audio = sent['body']['messages'][0]['content'][0]
        self.assertEqual(audio['type'], 'input_audio')
        self.assertTrue(audio['input_audio']['data'].startswith('data:audio/wav;base64,'))
        self.assertEqual(sent['body']['asr_options']['language'], 'zh')

    def test_failures_become_readable_reasons_without_key(self):
        settings = dict(speech_api.DEFAULTS)

        def denied(url, **kwargs):
            raise urllib.error.HTTPError(url, 401, 'unauthorized', {}, None)

        with self.assertRaises(ValueError) as caught:
            speech_api.transcribe(b'x', settings=settings, key='sk-secret', opener=denied)
        self.assertIn('密钥无效', str(caught.exception))
        self.assertNotIn('sk-secret', str(caught.exception))
        with patch.object(speech_api, 'api_key', return_value=''):
            self.assertIn('DASHSCOPE_API_KEY', speech_api.missing_reason(settings))
            with self.assertRaises(ValueError):
                speech_api.transcribe(b'x', settings=settings)
        with self.assertRaises(ValueError):
            speech_api.transcribe(b'x', settings={**settings, 'base_url': 'http://asr.example.com'}, key='k', opener=denied)


if __name__ == '__main__':
    unittest.main()
