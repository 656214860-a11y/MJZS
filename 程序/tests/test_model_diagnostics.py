# -*- coding: utf-8 -*-
"""模型诊断只能保留协议元数据，不能复制创作正文或推理文本。"""
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import model_diagnostics


class ModelDiagnosticsTests(unittest.TestCase):
    def test_record_whitelists_metadata_and_excludes_content(self):
        result = {
            'ok': True, 'status': 200, 'model': 'DeepSeek V4 Flash',
            'text': '绝不能写入诊断文件的剧本正文',
            'usage': {'prompt_tokens': 12, 'completion_tokens': 8, 'private': 'no'},
            'response_meta': {
                'response_id': 'req_safe_001', 'finish_reason': 'stop',
                'wire_api': 'chat_completions', 'response_shape': ['choices'],
                'message_fields': ['content', 'reasoning_content'],
                'reasoning_fields': ['reasoning_content'],
                'reasoning_lengths': {'reasoning_content': 321}, 'content_length': 17,
            },
        }
        with tempfile.TemporaryDirectory() as folder:
            path = model_diagnostics.record(folder, result,
                                            {'stage': 'script', 'role': 'director'},
                                            at=datetime(2026, 9, 27, 12, 0, 0))
            raw = path.read_text(encoding='utf-8')
            saved = json.loads(raw)
        self.assertEqual(path.parent.name, 'model_diagnostics')
        self.assertEqual(saved['response_id'], 'req_safe_001')
        self.assertEqual(saved['finish_reason'], 'stop')
        self.assertEqual(saved['reasoning_lengths'], {'reasoning_content': 321})
        self.assertEqual(saved['usage'], {'prompt_tokens': 12, 'completion_tokens': 8})
        self.assertNotIn('绝不能写入诊断文件的剧本正文', raw)
        self.assertNotIn('private', raw)

    def test_failed_result_has_stable_empty_metadata(self):
        saved = model_diagnostics.event({'ok': False, 'error_class': 'network'})
        self.assertFalse(saved['ok'])
        self.assertEqual(saved['error_class'], 'network')
        self.assertEqual(saved['content_length'], 0)
        self.assertEqual(saved['reasoning_lengths'], {})


if __name__ == '__main__':
    unittest.main()
