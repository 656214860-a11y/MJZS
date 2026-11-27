"""轮次门禁的阈值来自基线 JSON，不再写死过期数字（对应 G4）。"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

PROGRAM = Path(__file__).resolve().parent.parent
SCRIPT = PROGRAM / '维护记录' / '基准脚本' / 'round_gate.py'
spec = importlib.util.spec_from_file_location('round_gate_for_tests', SCRIPT)
gate = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = gate
spec.loader.exec_module(gate)


class RoundGateFloorTests(unittest.TestCase):
    def test_floors_are_read_from_the_baseline_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'b.json'
            path.write_text(json.dumps({'architecture_gate_files_min': 5, 'skill_registry_count': 7,
                                        'smoke_checks_expected': 8}), encoding='utf-8')
            self.assertEqual(gate.load_floors(path), {'architecture_gate_files_min': 5,
                                                      'skill_registry_count': 7, 'smoke_checks_expected': 8})

    def test_missing_baseline_yields_zero_floors_so_the_gate_stays_red(self):
        self.assertEqual(set(gate.load_floors(Path('nope.json')).values()), {0})

    def test_current_tree_meets_its_own_recorded_floors(self):
        floors = gate.load_floors()
        actual = len(list((PROGRAM / 'tests' / 'architecture').glob('test_*.py')))
        self.assertGreaterEqual(actual, floors['architecture_gate_files_min'])
        self.assertGreater(floors['architecture_gate_files_min'], 14)

    def test_registry_baseline_matches_the_live_registry(self):
        import skill_registry
        self.assertEqual(skill_registry.Registry(PROGRAM / 'skills').count(),
                         gate.load_floors()['skill_registry_count'])

    def test_evidence_directory_is_allowed_in_staging_but_results_are_not(self):
        staged = ['程序/tasks_round/evidence/R1.json', '程序/tasks_round/tasks_round_1_result.md', '程序/a.py']
        self.assertEqual(gate.staging_forbidden(staged), ['程序/tasks_round/tasks_round_1_result.md'])


if __name__ == '__main__':
    unittest.main()
