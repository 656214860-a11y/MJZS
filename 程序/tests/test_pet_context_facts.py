# -*- coding: utf-8 -*-
"""三虎项目事实快照自检：只汇总宿主已有的计数、缺口与门禁人话，不新增盘扫。"""
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, PROGRAM)
sys.path.insert(0, HERE)
os.chdir(PROGRAM)


class FakeVoice:
    """facts_snapshot 只认这几个既有出口；盘上读数由用例直接给。"""

    def __init__(self, project=None, counts=None, gaps=None, blocked='', stage='keyframe'):
        self.agent = SimpleNamespace(project=project)
        self._counts = counts or {}
        self._gaps = gaps or []
        self._blocked = blocked
        self._stage = stage
        self.counts_calls = 0
        self.gaps_calls = 0
        self.gate_stage = None

    def counts(self):
        self.counts_calls += 1
        return dict(self._counts)

    def gaps(self, at=None, force=False):
        self.gaps_calls += 1
        return list(self._gaps)

    def snapshot(self):
        return {'stage': self._stage}

    def gate_reason(self, stage):
        self.gate_stage = stage
        return self._blocked


class FactsSnapshotTests(unittest.TestCase):
    def test_snapshot_has_fixed_shape_and_real_numbers(self):
        from ui import pet_context_facts
        counts = {'scripts': 1, 'storyboards': 3, 'adopted': 1, 'shots': 40,
                  'frames': 25, 'assets': 2, 'ready_assets': 2}
        gaps = ['2 份分镜 JSON 还没采用（分镜 → 手动采用分镜）',
                '首帧还差 15 个镜头（首帧 → 手动制作首帧）']
        voice = FakeVoice(project=Path('项目'), counts=counts, gaps=gaps, blocked='缺资产')
        data = pet_context_facts.facts_snapshot(voice)
        self.assertEqual(set(data), {'counts', 'gaps', 'blocked'})
        self.assertEqual(data['counts'], counts)
        self.assertTrue(all(isinstance(value, int) for value in data['counts'].values()))
        self.assertEqual(data['gaps'], gaps)
        self.assertEqual(data['blocked'], '缺资产')
        self.assertEqual(voice.gate_stage, 'keyframe')

    def test_no_project_returns_empty_without_reading(self):
        from ui import pet_context_facts
        voice = FakeVoice(project=None, counts={'shots': 1}, gaps=['缺口'])
        self.assertEqual(pet_context_facts.facts_snapshot(voice), {})
        self.assertEqual(voice.counts_calls, 0)
        self.assertEqual(voice.gaps_calls, 0)

    def test_gaps_are_capped_at_four(self):
        from ui import pet_context_facts
        voice = FakeVoice(project=Path('项目'), counts={'shots': 9, 'frames': 0},
                          gaps=['第%d条' % index for index in range(1, 7)])
        self.assertEqual(pet_context_facts.facts_snapshot(voice)['gaps'],
                         ['第1条', '第2条', '第3条', '第4条'])

    def test_blocked_is_empty_without_a_current_stage(self):
        from ui import pet_context_facts
        voice = FakeVoice(project=Path('项目'), stage=None, blocked='不该出现')
        data = pet_context_facts.facts_snapshot(voice)
        self.assertEqual(data['blocked'], '')
        self.assertIsNone(voice.gate_stage)


if __name__ == '__main__':
    unittest.main(verbosity=1)
