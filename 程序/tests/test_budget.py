# -*- coding: utf-8 -*-
"""I16 预算治理（L1 任务书／L1-H10）：L1 引擎 infra.budget＋L3 策略 orchestrator.pet_budget。

- I16-1：五类硬上限迁移前后事件序列逐字等价（budget.warning／budget.exceeded 负载不变）。
- I16-2：无界面（三虎不在场）阶段跑批越线 → 暂停语义＋budget.exceeded 事件，不依赖 pet_agent。
- I16-3：budget.summary(project, since) 按 stage/provider 聚合，数值与 request_ledger 一致。
"""
import tempfile
import unittest
from pathlib import Path

import pet_bus
import pet_state
import pet_agent
from agent.core import save
from infra import budget as budget_engine
from infra import request_ledger
from orchestrator import pet_budget, skill_budget, skill_orchestrator


class CheckAmountParityTests(unittest.TestCase):
    """check_amount 与历史 pet_agent.Budget.check 同口径（L1-H10 逐字等价）。"""

    def test_five_kinds_boundary_and_over(self):
        for kind, limit in (('image', 200), ('firstframe', 200), ('video', 100),
                            ('voice', 200), ('tokens', 2000000)):
            with self.subTest(kind=kind):
                edge = budget_engine.check_amount(kind, limit - 1, limit, 1)
                self.assertTrue(edge['ok'])
                self.assertFalse(edge['exceeded'])
                self.assertEqual(edge['remaining'], 0)
                self.assertTrue(edge['warning'])          # 100% ≥ 90% 预警线
                over = budget_engine.check_amount(kind, limit, limit, 1)
                self.assertFalse(over['ok'])
                self.assertTrue(over['exceeded'])
                self.assertEqual(over['remaining'], 0)

    def test_warning_threshold_and_fields(self):
        below = budget_engine.check_amount('image', 179, 200, 1)   # 180/200 = 90%
        self.assertTrue(below['ok'] and below['warning'])
        self.assertFalse(below['exceeded'])
        self.assertEqual(below['remaining'], 20)
        quiet = budget_engine.check_amount('image', 100, 200, 1)   # 101/200 < 90%
        self.assertTrue(quiet['ok'])
        self.assertFalse(quiet['warning'])
        zero = budget_engine.check_amount('image', 200, 200, 0)
        self.assertTrue(zero['ok'])                                # amount=0 不扣不超

    def test_amount_normalization(self):
        verdict = budget_engine.check_amount('video', 0, 100, 'abc')
        self.assertEqual(verdict['amount'], 0)
        self.assertTrue(verdict['ok'])
        verdict = budget_engine.check_amount('video', 0, 100, -5)
        self.assertEqual(verdict['amount'], 0)

    def test_custom_warn_ratio(self):
        verdict = budget_engine.check_amount('image', 50, 100, 10, warn_ratio=0.5)
        self.assertTrue(verdict['warning'])                        # 60% ≥ 50%
        verdict = budget_engine.check_amount('image', 50, 100, 10, warn_ratio=0.7)
        self.assertFalse(verdict['warning'])


class PetBudgetPolicyTests(unittest.TestCase):
    """orchestrator.pet_budget.Budget：五类策略原样保留，判定走 L1 引擎。"""

    def test_spend_sequence_verdicts_identical(self):
        budget = pet_budget.Budget({'image': 3})
        first = budget.spend('image')
        self.assertTrue(first['ok'])
        self.assertFalse(first['warning'])
        second = budget.spend('image')
        self.assertTrue(second['ok'])
        self.assertFalse(second['warning'])                        # (1+1)/3 < 90%
        third = budget.spend('image')
        self.assertTrue(third['ok'] and third['warning'])          # (2+1)/3 = 100%
        fourth = budget.spend('image')
        self.assertFalse(fourth['ok'])
        self.assertTrue(fourth['exceeded'])
        self.assertEqual(budget.used['image'], 3)                  # 越线不扣
        self.assertEqual(budget.snapshot()['limits']['image'], 3)

    def test_aliases_and_invalid_kind(self):
        self.assertEqual(pet_budget.normalize_kind('token'), 'tokens')
        self.assertEqual(pet_budget.normalize_kind('keyframe'), 'firstframe')
        self.assertEqual(pet_budget.normalize_kind('tts'), 'voice')
        self.assertEqual(pet_budget.normalize_kind('IMG'), 'image')
        with self.assertRaises(ValueError) as ctx:
            pet_budget.normalize_kind('spaceship')
        self.assertIn('未登记的配额类型', str(ctx.exception))

    def test_limits_from_config_and_defaults(self):
        budget = pet_budget.Budget({'image': '5', 'video': -1, '未知': 9})
        self.assertEqual(budget.limits['image'], 5)
        self.assertEqual(budget.limits['video'], pet_budget.DEFAULT_BUDGET['video'])
        self.assertEqual(budget.limits['tokens'], pet_budget.DEFAULT_BUDGET['tokens'])

    def test_sync_tokens_and_snapshot(self):
        class FakeLedger:
            def today_tokens(self, at=None):
                return 1234
        budget = pet_budget.Budget()
        self.assertEqual(budget.sync_tokens(FakeLedger()), 1234)
        self.assertEqual(budget.used['tokens'], 1234)
        self.assertEqual(budget.sync_tokens(None), 1234)
        snap = budget.snapshot()
        self.assertEqual(set(snap), {'limits', 'used'})
        self.assertEqual(snap['used']['tokens'], 1234)

    def test_pet_agent_reexports_l3_policy(self):
        """pet_agent 的公开名仍指向 L3 策略模块（L4 只显示，判定不在界面层）。"""
        self.assertIs(pet_agent.Budget, pet_budget.Budget)
        self.assertIs(pet_agent.normalize_kind, pet_budget.normalize_kind)
        self.assertEqual(pet_agent.DEFAULT_BUDGET, pet_budget.DEFAULT_BUDGET)
        self.assertEqual(pet_agent.BUDGET_KINDS, pet_budget.BUDGET_KINDS)


class AgentEventEquivalenceTests(unittest.TestCase):
    """I16-1：迁移后三虎 spend 的事件序列与负载与迁移前逐字一致。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        self.bus = pet_bus.Bus()
        self.machine = pet_state.Machine(self.project, persist=False)

    def _agent(self, limits):
        return pet_agent.Agent(project=self.project, bus=self.bus, machine=self.machine,
                               settings={'budget_limits': limits}, persist=False)

    def _events(self, kind):
        self.bus.pump()
        return [item for item in self.bus.history if item.get('kind') == kind]

    def test_warning_then_exceeded_payloads(self):
        agent = self._agent({'image': 2})
        agent.spend('image')
        agent.spend('image')
        verdict = agent.spend('image', stage='assets')
        self.assertFalse(verdict['ok'])
        self.assertTrue(agent.paused)
        warnings = self._events('budget.warning')
        exceeded = self._events('budget.exceeded')
        self.assertEqual(len(warnings), 1)
        self.assertEqual(len(exceeded), 1)
        # 负载逐字：{budget, used, limit} 三键，无多无少
        # warning 负载带扣前 used（spend#2 触发：used=1+1=2 ≥ 90%×2）
        self.assertEqual({k: warnings[0][k] for k in ('budget', 'used', 'limit')},
                         {'budget': 'image', 'used': 1, 'limit': 2})
        self.assertEqual({k: exceeded[0][k] for k in ('budget', 'used', 'limit')},
                         {'budget': 'image', 'used': 2, 'limit': 2})
        self.assertIn('已暂停自动执行', agent.notifier.pending[-1]['text'])

    def test_alias_kind_normalizes_in_event(self):
        agent = self._agent({'image': 1})
        agent.spend('img')                                   # 别名归一到 image
        verdict = agent.spend('image')
        self.assertFalse(verdict['ok'])
        exceeded = self._events('budget.exceeded')
        self.assertEqual(exceeded[0]['budget'], 'image')
        self.assertEqual(exceeded[0]['used'], 1)

    def test_tokens_sync_from_ledger(self):
        class FakeClient:
            class ledger:
                @staticmethod
                def today_tokens(at=None):
                    return 1999999
        agent = pet_agent.Agent(project=self.project, bus=self.bus, machine=self.machine,
                                client=FakeClient(), persist=False)
        verdict = agent.spend('tokens')
        self.assertTrue(verdict['ok'])
        self.assertTrue(verdict['warning'])                  # (1999999+1)/2000000 ≥ 90%
        warnings = self._events('budget.warning')
        self.assertEqual(warnings[0]['budget'], 'tokens')
        self.assertEqual(warnings[0]['used'], 1999999)


class HeadlessBudgetTests(unittest.TestCase):
    """I16-2：无界面阶段跑批越线 → BUDGET 结果＋budget.exceeded，链路不含 pet_agent。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)

    def test_orchestrator_budget_exceeded_without_pet_agent(self):
        # 预置预算账：images 已用满默认上限 200
        path = skill_budget.budget_path(self.project)
        path.parent.mkdir(parents=True, exist_ok=True)
        used = 10 ** 9                                # 任何合理上限都已用满
        save(path, {'tokens': 0, 'images': used, 'videos': 0, 'reservations': {}})
        bus = pet_bus.Bus()
        delivered = []
        bus.subscribe('*', delivered.append)
        orch = skill_orchestrator.default_orchestrator(bus=bus, project=str(self.project))
        row = orch.execute('firstframe-quality',
                           {'tools': {'firstframe.qualityCheck': {'ok': True}}})
        bus.pump()
        self.assertEqual(row['status'], skill_orchestrator.BUDGET)
        exceeded = [e for e in delivered if e.get('kind') == 'budget.exceeded']
        self.assertTrue(exceeded, 'headless 路径必须发出 budget.exceeded')
        self.assertEqual(exceeded[0]['budget'], 'images')
        self.assertEqual(exceeded[0]['used'], used)
        self.assertEqual(exceeded[0]['limit'], orch.budget.limit('images'))

    def test_budget_path_has_no_pet_agent_dependency(self):
        """编排预算链（orchestrator→skill_budget/pet_budget→infra.budget→request_ledger）
        的 import 图里不得出现 pet_agent——无界面路径不依赖三虎。"""
        import ast
        for rel in ('orchestrator/skill_orchestrator.py', 'orchestrator/skill_budget.py',
                    'orchestrator/pet_budget.py', 'infra/budget.py'):
            tree = ast.parse(Path(rel).read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or '']
                else:
                    continue
                for name in names:
                    self.assertFalse(name == 'pet_agent' or name.startswith('pet_agent.'),
                                     '%s 不得 import pet_agent' % rel)


class EngineLedgerTests(unittest.TestCase):
    """L1 引擎对 request_ledger 的预留/结算/汇总（I16-3）。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)

    def _ledger(self):
        ledger = request_ledger.RequestLedger(self.project)
        ledger.load()
        return ledger

    def test_usage_matches_report_kinds(self):
        ledger = self._ledger()
        budget_engine.reserve(ledger, 'r1', 'images', 2, meta={'stage':'assets','provider':'p1'})
        budget_engine.settle(ledger, 'r1', amount=2)
        budget_engine.reserve(ledger, 'r2', 'videos', 1)
        budget_engine.cancel(ledger, 'r2', reason='test')
        budget_engine.reserve(ledger, 'r3', 'tokens', 100)
        self.assertEqual(budget_engine.usage(ledger), ledger.report()['kinds'])
        only = budget_engine.usage(ledger, 'images')
        self.assertEqual(set(only), {'images'})
        self.assertEqual(only['images']['settled'], 2.0)

    def test_reserve_limit_rejects_without_entry(self):
        ledger = self._ledger()
        budget_engine.reserve(ledger, 'r1', 'images', 2)
        budget_engine.settle(ledger, 'r1', amount=2)
        with self.assertRaises(request_ledger.BudgetRejected):
            budget_engine.reserve(ledger, 'r2', 'images', 1, limits={'images': 2})
        self.assertEqual(len(ledger.entries), 1)               # 越线不落账
        # 未登记上限的 kind 不判额度
        entry = budget_engine.reserve(ledger, 'r3', 'videos', 5)
        self.assertEqual(entry['state'], 'reserved')

    def test_reserve_counts_in_flight_reserved(self):
        ledger = self._ledger()
        budget_engine.reserve(ledger, 'r1', 'images', 2)       # 还占着
        with self.assertRaises(request_ledger.BudgetRejected):
            budget_engine.reserve(ledger, 'r2', 'images', 1, limits={'images': 2})

    def test_reserve_stamps_stage_and_provider(self):
        ledger = self._ledger()
        entry = budget_engine.reserve(ledger, 'r1', 'images', 1,
                                      meta={'stage':'assets','provider':'seedream'})
        budget_engine.settle(ledger, 'r1', amount=1)
        ledger.save()
        self.assertEqual(entry['stage'], 'assets')
        self.assertEqual(entry['provider'], 'seedream')

    def test_summary_aggregates_by_stage_and_provider(self):
        ledger = self._ledger()
        budget_engine.reserve(ledger, 'r1', 'images', 2, meta={'stage':'assets','provider':'p1'})
        budget_engine.settle(ledger, 'r1', amount=2)
        budget_engine.reserve(ledger, 'r2', 'images', 3, meta={'stage':'keyframe','provider':'p2'})
        budget_engine.settle(ledger, 'r2', amount=3)
        budget_engine.reserve(ledger, 'r3', 'tokens', 10, meta={'stage':'assets'})
        budget_engine.settle(ledger, 'r3', amount=10)
        budget_engine.reserve(ledger, 'r4', 'videos', 1)       # 保持 reserved：进 kinds 不进 by_*
        ledger.save()

        fresh = request_ledger.RequestLedger(self.project)
        fresh.load()
        out = budget_engine.summary(self.project)
        self.assertEqual(out['kinds'], fresh.report()['kinds'])   # I16-3：与台账一致
        self.assertEqual(out['by_stage']['assets'], {'images': 2.0, 'tokens': 10.0})
        self.assertEqual(out['by_stage']['keyframe'], {'images': 3.0})
        self.assertEqual(out['by_provider']['p1'], {'images': 2.0})
        self.assertEqual(out['by_provider']['p2'], {'images': 3.0})
        self.assertEqual(out['by_provider']['unknown'], {'tokens': 10.0})
        self.assertEqual(out['requests'], 4)

    def test_summary_since_filters_by_settled_at(self):
        ledger = self._ledger()
        ledger.clock = lambda: 1000.0
        budget_engine.reserve(ledger, 'old', 'images', 1, meta={'stage':'assets'})
        budget_engine.settle(ledger, 'old', amount=1, at=1000.0)
        ledger.clock = lambda: 5000.0
        budget_engine.reserve(ledger, 'new', 'images', 2, meta={'stage':'assets'})
        budget_engine.settle(ledger, 'new', amount=2, at=5000.0)
        ledger.save()
        out = budget_engine.summary(self.project, since=2000.0)
        self.assertEqual(out['by_stage']['assets'], {'images': 2.0})
        self.assertEqual(out['kinds']['images']['settled'], 2.0)
        out_all = budget_engine.summary(self.project)
        self.assertEqual(out_all['kinds']['images']['settled'], 3.0)

    def test_summary_accepts_iso_date(self):
        out = budget_engine.summary(self.project, since='2020-01-01')
        self.assertIn('kinds', out)
        with self.assertRaises(ValueError):
            budget_engine.summary(self.project, since='not-a-date')


class SkillBudgetHeadroomTests(unittest.TestCase):
    """skill_budget.remaining 收敛到 L1 headroom，数值不变。"""

    def test_remaining_matches_legacy_formula(self):
        budget = skill_budget.Budget(config={'images_per_project': 10})
        budget.counters['images'] = 3
        budget.reservations['r1'] = {'kind': 'images', 'amount': 2, 'state': 'reserved'}
        self.assertEqual(budget.remaining('images'), 5)         # 10-3-2
        self.assertEqual(budget.check('images', 6)[0], False)
        self.assertEqual(budget.check('images', 5)[0], True)


if __name__ == '__main__':
    unittest.main()

