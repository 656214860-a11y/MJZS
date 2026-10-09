"""普通阶段对话的推理与可见正文共享输出预算回归。"""
import tempfile
import unittest
from unittest.mock import patch

import writing_api
from model_router import PoolAdapter
from test_workflow import make_project


class WritingOutputBudgetTests(unittest.TestCase):
    def call_reply(self, model, creative='确认', text='# 剧本大纲\n雨夜追查底片。\n待确认'):
        payloads = []

        def transport(url, payload, headers, timeout):
            payloads.append(payload)
            return {'ok': True, 'status': 200, 'data': {
                'choices': [{'message': {'content': text, 'reasoning_content': '不应显示的思考'},
                             'finish_reason': 'stop' if text else 'length'}]}}

        record = {'model': model, 'provider': 'test', 'wire_api': 'chat.completions',
                  'base_url': 'https://example.invalid', 'path': '/v1/chat/completions'}
        adapter = PoolAdapter(record, model, transport=transport, key='test-only')
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            with patch('writing_api.selected_model', return_value=(model, record)), \
                 patch('writing_api.PoolAdapter', return_value=adapter):
                result = writing_api.reply(project, creative)
        self.assertTrue(result['ok'])
        self.assertEqual(result['text'], text)
        self.assertEqual(len(payloads), 1, '不得增加隐式重试调用')
        return payloads[0]

    def test_deepseek_v4_confirmation_has_room_for_reasoning_and_body(self):
        for model in ('deepseek-v4-flash', 'deepseek-v4-pro'):
            with self.subTest(model=model):
                self.assertEqual(self.call_reply(model)['max_tokens'], 32768)

    def test_first_setting_request_uses_same_budget(self):
        self.assertEqual(self.call_reply('deepseek-v4-flash', '请输出项目设定')['max_tokens'], 32768)

    def test_other_models_keep_existing_budget(self):
        self.assertEqual(self.call_reply('gpt-4o')['max_tokens'], 4096)

    def test_empty_body_is_not_replaced_by_reasoning_or_silently_retried(self):
        self.assertEqual(self.call_reply('deepseek-v4-flash', text='')['max_tokens'], 32768)


if __name__ == '__main__':
    unittest.main()
