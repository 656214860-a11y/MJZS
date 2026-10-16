"""逐 AI 适配器的失败分类一致性：把《生成服务失败处理契约》的判定表钉在真实适配器上。

`tests/test_model_failure_route.py` 用统一的桩适配器覆盖路由与切换；本文件进一步要求
**每个内置文本适配器**（DeepSeek/GPT/Qwen/Anthropic）对同一批回执给出同一套分类，
防止某个适配器把 5xx 误报成已受理或把 429 误报成不可重试。
"""
from __future__ import annotations

import unittest

import model_router as m


def _transport(payload):
    if isinstance(payload, Exception):
        def failing(*_args, **_kwargs):
            raise payload
        return failing
    return lambda *args, **kwargs: dict(payload)


# (场景, 传输回执, 期望(acceptance, reason_code, retryable))
SCENARIOS = (
    ('429-无受理证据', {'ok': False, 'status': 429}, ('not_accepted', 'rate_limit', True)),
    ('5xx-受理未知', {'ok': False, 'status': 503}, ('unknown', 'server_error', False)),
    ('5xx-明确未受理', {'ok': False, 'status': 503, 'accepted': False}, ('not_accepted', 'server_error', True)),
    ('401-鉴权', {'ok': False, 'status': 401}, ('not_accepted', 'authentication', False)),
    ('400-不支持请求', {'ok': False, 'status': 400}, ('not_accepted', 'unsupported_request', False)),
    ('422-不支持请求', {'ok': False, 'status': 422}, ('not_accepted', 'unsupported_request', False)),
    ('有远端编号-视为已受理', {'ok': False, 'status': 500, 'task_id': 'remote-9'}, ('accepted', 'server_error', False)),
    ('超时-回执未知', TimeoutError('t'), ('unknown', 'receipt_unknown', False)),
)

ADAPTERS = (
    ('deepseek', m.DeepSeekAdapter, 'deepseek-v4-pro'),
    ('gpt', m.GPTAdapter, 'gpt-4o'),
    ('qwen', m.QwenAdapter, 'qwen-max'),
    ('anthropic', m.AnthropicAdapter, 'claude-opus-5'),
)


class AdapterFailureConformanceTests(unittest.TestCase):
    def test_every_adapter_classifies_every_scenario(self):
        for name, factory, model in ADAPTERS:
            for label, payload, expected in SCENARIOS:
                with self.subTest(adapter=name, scenario=label):
                    adapter = factory(key='test', transport=_transport(payload))
                    out = adapter.chat([], model=model)
                    policy = m.failure_policy(out)
                    self.assertEqual(
                        (policy['acceptance'], policy['reason_code'], policy['retryable']),
                        expected,
                        '%s · %s 分类漂移' % (name, label))
                    self.assertEqual(out['text'], '', '%s · %s 失败回执不得带正文' % (name, label))

    def test_success_is_not_classified_as_failure(self):
        body = {'ok': True, 'status': 200, 'data': {'choices': [{'message': {'content': 'ok'}}]}}
        for name, factory, model in ADAPTERS:
            with self.subTest(adapter=name):
                adapter = factory(key='test', transport=_transport(body))
                policy = m.failure_policy(adapter.chat([], model=model))
                self.assertEqual(policy['acceptance'], 'accepted')
                self.assertEqual(policy['reason_code'], 'succeeded')
                self.assertFalse(policy['retryable'])


if __name__ == '__main__':
    unittest.main()