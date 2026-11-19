# -*- coding: utf-8 -*-
"""R2178 J10：授权 → 发送 → 结算的唯一序列，无 Tk、无网络。"""
import unittest

import infra.model_router as model_router
import infra.pet_llm as pet_llm
from model_metering import metered, replayable_retry, submission_retryable


def _ledger():
    calls = []

    class Ledger:
        def authorize_model(self, *args):
            calls.append(('authorize', args))

        def settle_model(self, request_id, usage):
            calls.append(('settle', request_id, usage))
    return Ledger(), calls


class MeteredSequenceTests(unittest.TestCase):
    def test_runs_authorize_send_on_result_settle_in_order(self):
        ledger, calls = _ledger()
        result, usage, rejected = metered(
            ledger, ('r1', 'm', 'script', 10, 20), lambda: calls.append('send') or {'ok': True},
            lambda r: {'prompt_tokens': 1}, on_result=lambda r, u: calls.append(('on_result', u)))
        self.assertEqual([c if isinstance(c, str) else c[0] for c in calls],
                         ['authorize', 'send', 'on_result', 'settle'])
        self.assertEqual(calls[0][1], ('r1', 'm', 'script', 10, 20))
        self.assertEqual((result, usage, rejected), ({'ok': True}, {'prompt_tokens': 1}, None))

    def test_rejected_authorization_never_sends(self):
        ledger, calls = _ledger()
        ledger.authorize_model = lambda *a: (_ for _ in ()).throw(ValueError('over budget'))
        result, usage, rejected = metered(ledger, ('r2', 'm', 's', 1, 1), lambda: calls.append('send'), dict)
        self.assertEqual((result, usage, calls), (None, {}, []))
        self.assertEqual(str(rejected), 'over budget')

    def test_send_error_settles_unknown_usage_then_reraises(self):
        ledger, calls = _ledger()

        def boom():
            raise RuntimeError('network')
        with self.assertRaises(RuntimeError):
            metered(ledger, ('r3', 'm', 's', 1, 1), boom, dict)
        self.assertEqual(calls[-1], ('settle', 'r3', {}))

    def test_send_value_error_is_not_mistaken_for_a_budget_rejection(self):
        ledger, calls = _ledger()
        with self.assertRaises(ValueError):
            metered(ledger, ('r4', 'm', 's', 1, 1), lambda: (_ for _ in ()).throw(ValueError('bad')), dict)
        self.assertEqual(calls[-1], ('settle', 'r4', {}))


class RetryPolicyNamingTests(unittest.TestCase):
    """R2178 J12：「对话可重放」与「提交可能已受理」两种口径显式命名，且旧入口委托到它们。"""

    def test_http_500_is_replayable_for_chat_but_not_for_submission(self):
        self.assertTrue(replayable_retry(500))
        self.assertFalse(model_router.failure_policy({'status': 500})['retryable'])
        self.assertFalse(submission_retryable('unknown', 'server_error'))

    def test_submission_retries_only_confirmed_not_accepted_throttling_and_server_errors(self):
        self.assertTrue(submission_retryable('not_accepted', 'rate_limit'))
        self.assertTrue(submission_retryable('not_accepted', 'server_error'))
        self.assertFalse(submission_retryable('accepted', 'rate_limit'))
        self.assertFalse(submission_retryable('not_accepted', 'authentication'))

    def test_old_entries_delegate_to_the_named_policies(self):
        for status in (0, 400, 401, 408, 429, 500, 503, None):
            self.assertEqual(pet_llm.is_retryable(status), replayable_retry(status))
        self.assertTrue(model_router.failure_policy({'status': 429})['retryable'])


if __name__ == '__main__':
    unittest.main()

class AttemptPersistenceTests(unittest.TestCase):
    """R3709 A 维验收发现：metered 的尝试元数据必须在结算事务重读后仍落盘。"""

    def test_attempt_metadata_survives_settle(self):
        import json
        import tempfile
        from pathlib import Path
        from infra.pet_llm import RequestLedger, request_ledger_path
        with tempfile.TemporaryDirectory() as td:
            ledger = RequestLedger(Path(td))
            result, usage, rejected = metered(
                ledger, ('r-att', 'm', 'script', 100, 50),
                lambda: {'ok': True, 'status': 200,
                         'data': {'usage': {'prompt_tokens': 3, 'completion_tokens': 4}}},
                lambda r: {'prompt_tokens': 3, 'completion_tokens': 4})
            self.assertIsNone(rejected)
            self.assertTrue(result.get('ok'))
            data = json.loads(request_ledger_path(Path(td)).read_text(encoding='utf-8'))
            entry = data['entries'][0]
            self.assertEqual(entry['state'], 'settled')
            attempts = entry.get('attempts') or []
            self.assertTrue(attempts, '结算后尝试元数据必须仍在台账里')
            self.assertEqual(attempts[0].get('status'), 200)
            self.assertEqual(attempts[0].get('wire_api'), '')
