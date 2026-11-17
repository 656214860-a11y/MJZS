# -*- coding: utf-8 -*-
"""HITL 请求/决策信封（R3119）：风险分级、自动放行、超时、EDIT 回填、confirm_gates 适配。

运行：python tests/test_hitl.py
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from domain import hitl


class HitlTests(unittest.TestCase):
    def test_choice_request_is_low_risk_and_serializable(self):
        request = hitl.make_request(hitl.RequestKind.CHOICE,
                                    {'title': '选结局', 'candidates': ['A', 'B']})
        self.assertEqual(request['kind'], 'choice')
        self.assertEqual(request['risk'], 'low')
        self.assertEqual(request['timeout'], hitl.DEFAULT_TIMEOUT_SECONDS)
        self.assertEqual(request['payload']['candidates'], ['A', 'B'])
        self.assertEqual(json.loads(json.dumps(request))['kind'], 'choice')

    def test_approval_risk_by_action(self):
        self.assertEqual(hitl.risk_of('approve', {'action': 'delete'}), 'high')
        self.assertEqual(hitl.risk_of('approve', {'action': 'save'}), 'low')

    def test_low_risk_auto_approves_high_risk_waits(self):
        self.assertIsNone(hitl.auto_decision(hitl.make_request('approve', {'action': 'delete'})))
        self.assertEqual(hitl.auto_decision(hitl.make_request('approve', {'action': 'save'})),
                         {'decision': 'approve', 'payload': {}})

    def test_expired_uses_injected_clock(self):
        request = hitl.make_request('approve', {'action': 'delete'}, timeout=60)
        self.assertFalse(hitl.expired(request, now=request['created_at'] + 59))
        self.assertTrue(hitl.expired(request, now=request['created_at'] + 60))
        self.assertEqual(hitl.timeout_decision()['decision'], 'timeout')

    def test_edit_decision_merges_payload(self):
        request = hitl.make_request('choice', {'title': '选', 'candidates': ['A', 'B']})
        applied = hitl.apply_decision(request, hitl.decide('edit', {'selected': 'B'}))
        self.assertEqual(applied['decision'], 'edit')
        self.assertEqual(applied['payload']['selected'], 'B')
        self.assertEqual(applied['payload']['candidates'], ['A', 'B'])

    def test_unknown_decision_raises(self):
        with self.assertRaises(ValueError):
            hitl.decide('nope')
        with self.assertRaises(ValueError):
            hitl.apply_decision(hitl.make_request('approve'), {'decision': 'nope'})

    def test_from_confirm_result_builds_choice_card(self):
        self.assertIsNone(hitl.from_confirm_result({'ask': ()}))
        request = hitl.from_confirm_result({'gate_id': 'G-06', 'title': '锚点定稿',
                                            'ask': ({'label': '候选1'}, {'label': '候选2'})})
        self.assertEqual(request['kind'], 'choice')
        self.assertEqual(request['payload']['gate_id'], 'G-06')
        self.assertEqual(len(request['payload']['candidates']), 2)


if __name__ == '__main__':
    unittest.main()
