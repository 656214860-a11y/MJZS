# -*- coding: utf-8 -*-
"""R2178 J10：授权 → 发送 → 结算的唯一序列，无 Tk、无网络。"""
import unittest

from model_metering import metered


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


if __name__ == '__main__':
    unittest.main()
