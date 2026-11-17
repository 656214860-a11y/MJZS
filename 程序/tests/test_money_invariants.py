"""金额算术不变量：分项求和＝总额、非负、币种不混算、未知不补零。

既有 `test_request_ledger`／`test_usage_overview` 覆盖场景行为；本文件把**算术恒等式**
独立钉住，用确定性伪随机输入交叉验证，防止后续改动在边界上悄悄破坏金额守恒。
"""
from __future__ import annotations

import unittest
from decimal import Decimal

import infra.pet_llm as pet_llm
import usage_overview as usage


def _rng(seed):
    state = seed

    def next_int(mod):
        nonlocal state
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        return state % mod
    return next_int


TABLE = {
    'version': 'v1', 'currency': 'CNY',
    'rates': {'tokens': '0.000002', 'images': '0.15', 'videos': '1.2', 'seconds': '0.02', 'requests': '0.01'},
    'model_rates': {'m1': {'prompt_tokens': '0.000002', 'completion_tokens': '0.000008'}},
}


class DecimalGuardTests(unittest.TestCase):
    def test_rejects_negative_nonfinite_and_bool(self):
        for bad in (-1, -0.5, 'x', float('nan'), float('inf'), True, False, None):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                pet_llm.RequestLedger.decimal(bad)

    def test_accepts_finite_non_negative(self):
        for good, expected in ((0, '0'), (3, '3'), ('2.5', '2.5'), (0.1, '0.1'), (Decimal('4.25'), '4.25')):
            with self.subTest(value=good):
                self.assertEqual(pet_llm.RequestLedger.decimal(good), Decimal(expected))


class PriceTableInvariantTests(unittest.TestCase):
    def test_amount_is_settled_plus_reserved(self):
        nxt = _rng(7)
        for _ in range(200):
            kinds = {}
            for kind in pet_llm.REQUEST_KINDS:
                kinds[kind] = {'settled': nxt(1000), 'reserved': nxt(500), 'unknown': nxt(5)}
            out = pet_llm.RequestLedger.price(kinds, TABLE)
            self.assertAlmostEqual(out['amount'], out['settled_amount'] + out['reserved_amount'], places=4)
            self.assertGreaterEqual(out['amount'], 0.0)
            self.assertGreaterEqual(out['settled_amount'], 0.0)
            self.assertGreaterEqual(out['reserved_amount'], 0.0)

    def test_amounts_never_exceed_four_decimals(self):
        kinds = {kind: {'settled': 3, 'reserved': 7, 'unknown': 0} for kind in pet_llm.REQUEST_KINDS}
        out = pet_llm.RequestLedger.price(kinds, TABLE)
        for key in ('amount', 'settled_amount', 'reserved_amount'):
            self.assertEqual(Decimal(str(out[key])), Decimal(str(out[key])).quantize(Decimal('0.0001')))

    def test_currency_comes_from_table_and_is_not_converted(self):
        kinds = {kind: {'settled': 1, 'reserved': 0, 'unknown': 0} for kind in pet_llm.REQUEST_KINDS}
        cny = pet_llm.RequestLedger.price(kinds, TABLE, currency='USD')
        self.assertEqual(cny['currency'], 'CNY')  # 价格表自带币种优先，不做汇率换算
        usd = pet_llm.RequestLedger.price(kinds, dict(TABLE, currency='USD'))
        self.assertEqual(usd['currency'], 'USD')
        self.assertAlmostEqual(cny['amount'], usd['amount'], places=4)  # 同一批用量、同一费率

    def test_missing_rate_listed_only_when_used(self):
        used = pet_llm.RequestLedger.price({'images': {'settled': 2, 'reserved': 0, 'unknown': 0}},
                                           {'version': 'v1', 'currency': 'CNY', 'rates': {}})
        self.assertEqual(used['missing_rates'], ['images'])
        self.assertFalse(used['complete'])
        unused = pet_llm.RequestLedger.price({'images': {'settled': 0, 'reserved': 0, 'unknown': 1}},
                                             {'version': 'v1', 'currency': 'CNY', 'rates': {}})
        self.assertEqual(unused['missing_rates'], [])  # 没用量就不算缺费率
        self.assertFalse(unused['complete'])           # 但有 unknown 请求，仍不完整

    def test_model_price_sums_parts_and_refuses_unknown(self):
        rates, cost = pet_llm.RequestLedger._model_price(
            TABLE, 'm1', {'prompt_tokens': 1000, 'completion_tokens': 2000})
        self.assertEqual(Decimal(str(cost)), Decimal('0.000002') * 1000 + Decimal('0.000008') * 2000)
        self.assertEqual(set(rates), {'prompt_tokens', 'completion_tokens'})
        for broken in ({}, {'version': 'v1', 'model_rates': {'m1': {'prompt_tokens': '1'}}},
                       {'version': '', 'currency': 'CNY', 'model_rates': {'m1': {'prompt_tokens': '1'}}}):
            with self.subTest(table=broken):
                _r, c = pet_llm.RequestLedger._model_price(broken, 'm1', {'prompt_tokens': 1000})
                self.assertIsNone(c)  # 宁缺勿造零


class ScenarioEstimateInvariantTests(unittest.TestCase):
    def test_total_equals_sum_of_stage_amounts(self):
        scenario = {'shots': 10, 'candidates': 2, 'attempts': 1, 'stages': [
            {'name': '首帧', 'model': 'm1', 'kind': 'tokens',
             'quantities': {'prompt_tokens': 1000, 'completion_tokens': 500}},
            {'name': '资产', 'model': 'm1', 'kind': 'tokens',
             'quantities': {'prompt_tokens': 300, 'completion_tokens': 100}},
        ]}
        out = usage.estimate_scenario(scenario, TABLE)
        self.assertTrue(out['complete'])
        parts = sum(Decimal(str(s['amount'])) for s in out['stages'])
        self.assertEqual(Decimal(str(out['amount'])), parts)
        self.assertGreaterEqual(out['amount'], 0.0)

    def test_incomplete_scenario_yields_no_total(self):
        scenario = {'stages': [{'name': 'x', 'model': 'unknown-model', 'kind': 'images',
                                'quantities': {'images': 3}}]}
        out = usage.estimate_scenario(scenario, TABLE)
        self.assertFalse(out['complete'])
        self.assertIsNone(out['amount'])
        self.assertIsNone(out['stages'][0]['amount'])
        self.assertEqual(out['currency'], 'CNY')

    def test_unknown_unit_is_rejected(self):
        with self.assertRaises(ValueError):
            usage.estimate_scenario({'stages': [{'name': 'x', 'model': 'm1', 'kind': 'bananas',
                                                 'quantities': {'bananas': 1}}]}, TABLE)


if __name__ == '__main__':
    unittest.main()