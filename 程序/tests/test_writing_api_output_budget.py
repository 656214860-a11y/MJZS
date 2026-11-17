"""普通阶段对话的推理与可见正文共享输出预算回归。"""
import tempfile
import unittest
from unittest.mock import Mock, patch

import writing_api
from infra.model_router import PoolAdapter
from test_writing_api import make_project


class WritingOutputBudgetTests(unittest.TestCase):
    def test_money_budget_rejects_direct_writing_before_adapter_send(self):
        import json
        from pathlib import Path
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / 'cost_profile.json').write_text(json.dumps({'budget_amount': '0', 'price_table': {
                'currency': 'CNY', 'version': 'fixture', 'model_rates': {
                    'm': {'prompt_tokens': '0.01', 'completion_tokens': '0.01'}}}}), encoding='utf-8')
            raw = Mock()
            adapter = writing_api.WritingRequestAdapter(raw, {'context_length': 128000}, 'm', project=td)
            result = adapter.chat([{'role': 'user', 'content': 'hello'}], options={'max_tokens': 20})
            self.assertFalse(result['ok'])
            self.assertEqual(result['reason'], 'money_budget_exceeded')
            raw.chat.assert_not_called()

    def test_transport_crash_releases_money_reservation_and_reraises(self):
        raw = Mock()
        raw.chat.side_effect = RuntimeError('断线')
        with tempfile.TemporaryDirectory() as td:
            # J10：计量序列在真实 RequestLedger.metered 里，只把授权／结算两端换成 Mock。
            from infra.pet_llm import RequestLedger
            ledger = RequestLedger(td)
            ledger.authorize_model, ledger.settle_model = Mock(), Mock()
        with tempfile.TemporaryDirectory() as td, patch('pet_llm.RequestLedger', return_value=ledger):
            adapter = writing_api.WritingRequestAdapter(raw, {'context_length': 128000}, 'm', project=td)
            with self.assertRaises(RuntimeError):
                adapter.chat([{'role': 'user', 'content': 'hello'}], options={'max_tokens': 20})
        ledger.authorize_model.assert_called_once()
        request_id = ledger.authorize_model.call_args[0][0]
        ledger.settle_model.assert_called_once_with(request_id, {})

    def test_context_budget_reserves_output_and_rejects_before_transport(self):
        raw = Mock()
        adapter = writing_api.WritingRequestAdapter(raw, {'context_length': 8000}, 'small')
        result = adapter.chat([{'role': 'user', 'content': '中' * 2200}],
                              options={'max_tokens': 4096}, system='规则')
        self.assertFalse(result['ok'])
        self.assertEqual(result['reason'], 'context_budget_exceeded')
        raw.chat.assert_not_called()
        self.assertEqual(result['context_budget']['output_reserved'], 4096)

    def test_usage_accumulates_calls_and_absent_values_remain_unknown(self):
        raw = Mock()
        raw.chat.return_value = {'ok': True, 'text': '正文', 'usage': {
            'prompt_tokens': 100, 'completion_tokens': 20, 'cached_tokens': 0},
            'data': {'usage': {'prompt_tokens': 100, 'completion_tokens': 20}}}
        adapter = writing_api.WritingRequestAdapter(raw, {'context_length': 128000}, 'large')
        adapter.chat([{'role': 'user', 'content': '测试'}], options={'max_tokens': 4096})
        result = adapter.chat([{'role': 'user', 'content': '继续'}], options={'max_tokens': 4096})
        self.assertEqual(result['request_usage']['prompt_tokens'], 200)
        self.assertEqual(result['request_usage']['completion_tokens'], 40)
        self.assertIsNone(result['request_usage']['cached_tokens'])
        raw.chat.return_value = {'ok': True, 'text': '正文', 'usage': {
            'prompt_tokens': 0, 'completion_tokens': 0}, 'data': {}}
        result = adapter.chat([])
        self.assertIsNone(result['request_usage']['prompt_tokens'])
        self.assertEqual(result['request_usage']['calls'], 3)

    def call_reply(self, model, creative='确认', text='# 剧本大纲\n雨夜追查底片。\n待确认'):
        payloads = []

        def transport(url, payload, headers, timeout):
            payloads.append(payload)
            return {'ok': True, 'status': 200, 'data': {
                'choices': [{'message': {'content': text, 'reasoning_content': '不应显示的思考'},
                             'finish_reason': 'stop' if text else 'length'}]}}

        record = {'model': model, 'provider': 'test', 'wire_api': 'chat.completions',
                  'context_length': 200000,  # 合成窗口隔离本组输出额度断言；不绕过完整请求终检。
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
