"""故障注入链路：传输层注入超时／429／5xx／半截响应，沿「计量 → 适配器分类 → 阶段完成核验」走一遍（对应 G8）。

断言的是付费调用失败时的不变量：失败回执不带正文；预留额度不被占住；未知用量不算已花费；
一次请求只记一条、不重复计费；模型嘴上说完成也不能让阶段完成（规则 20）。传输层是桩，不联网、不用 Tk。
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import model_metering
import model_router
import request_ledger
import stage_completion_service

GOOD = {'ok': True, 'status': 200, 'data': {'choices': [{'message': {'content': '写好了'}}],
                                            'usage': {'prompt_tokens': 3, 'completion_tokens': 2}}}
FAULTS = (
    ('超时', TimeoutError('slow')),
    ('429', {'ok': False, 'status': 429}),
    ('503', {'ok': False, 'status': 503}),
    ('503-明确未受理', {'ok': False, 'status': 503, 'accepted': False}),
    ('401', {'ok': False, 'status': 401}),
    ('半截响应-无 data', {'ok': True, 'status': 200, 'data': {}}),
)


def transport(payload, calls):
    def send(*_args, **_kwargs):
        calls.append(1)
        if isinstance(payload, Exception):
            raise payload
        return dict(payload)
    return send


class FaultChain(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def call(self, payload):
        calls = []
        ledger = request_ledger.RequestLedger(tempfile.mkdtemp(dir=self.root))
        adapter = model_router.GPTAdapter(key='k', transport=transport(payload, calls))
        result = model_metering.chat_metered(adapter, ledger, 'video', [{'role': 'user', 'content': '生成'}],
                                             {'max_tokens': 100}, 'gpt-4o', '你是导演')
        return result, ledger.report(), len(calls)

    def test_every_fault_returns_no_text_and_never_settles_spend(self):
        for label, payload in FAULTS:
            with self.subTest(fault=label):
                result, report, calls = self.call(payload)
                tokens = report['kinds']['tokens']
                self.assertEqual(result['text'], '')
                self.assertEqual(tokens['settled'], 0.0, '未知用量不得算作已花费')
                self.assertEqual(tokens['reserved'], 0.0, '预留额度不得被失败请求占住')
                self.assertEqual((tokens['count'], report['requests'], calls), (1, 1, 1), '一次请求只记一条、只发一次')
                self.assertEqual(report['duplicate_ids'], [])

    def test_faults_with_unknown_usage_are_visible_in_the_ledger(self):
        for label, payload in FAULTS:
            with self.subTest(fault=label):
                _result, report, _calls = self.call(payload)
                self.assertEqual(report['kinds']['tokens']['unknown'], 1)
                self.assertEqual(len(report['unknown_ids']), 1)

    def test_retry_classification_matches_the_billing_risk(self):
        expected = {'超时': ('unknown', False), '429': ('not_accepted', True), '503': ('unknown', False),
                    '503-明确未受理': ('not_accepted', True), '401': ('not_accepted', False)}
        for label, payload in FAULTS:
            if label in expected:
                with self.subTest(fault=label):
                    result, _report, _calls = self.call(payload)
                    policy = model_router.failure_policy(result)
                    self.assertEqual((policy['acceptance'], policy['retryable']), expected[label])

    def test_success_settles_reported_usage_exactly_once(self):
        result, report, calls = self.call(GOOD)
        self.assertEqual(result['text'], '写好了')
        self.assertEqual((report['kinds']['tokens']['settled'], report['kinds']['tokens']['unknown']), (5.0, 0))
        self.assertEqual((report['requests'], calls), (1, 1))

    def test_a_failed_paid_call_plus_a_confident_model_text_still_does_not_complete_the_stage(self):
        emitted = []
        for label, payload in FAULTS:
            with self.subTest(fault=label):
                self.call(payload)
                ok, detail, _ = stage_completion_service.emit_verified_completion(
                    self.root, 'video', '视频已全部生成完成', lambda *args, **kwargs: emitted.append((args, kwargs)))
                self.assertFalse(ok)
                self.assertTrue(detail)
        self.assertEqual(emitted, [], '没有产物时不得发出 stage.completed')

    def test_a_successful_call_without_artifacts_does_not_complete_the_stage_either(self):
        emitted = []
        self.call(GOOD)
        ok, _detail, _ = stage_completion_service.emit_verified_completion(
            self.root, 'video', '视频已全部生成完成', lambda *args, **kwargs: emitted.append(args))
        self.assertFalse(ok)
        self.assertEqual(emitted, [])

    def test_stage_completes_only_when_a_real_output_file_exists(self):
        from project_stages import stage as stage_dir
        emitted = []
        folder = Path(stage_dir(self.root, 'video'))
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'shot.mp4').write_bytes(b'0' * 16)
        ok, _detail, _ = stage_completion_service.emit_verified_completion(
            self.root, 'video', '完成', lambda *args, **kwargs: emitted.append(args),
            video_ready=lambda: ('digest', []))
        self.assertTrue(ok)
        self.assertEqual(len(emitted), 1)


if __name__ == '__main__':
    unittest.main()
