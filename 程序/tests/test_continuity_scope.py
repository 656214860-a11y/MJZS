"""REQ-S06-02/03/11/20/22/23/30：连贯性清单阶段的依赖、锁、产出、完成判据与 SKILL 范围。"""
import tempfile
import unittest
from pathlib import Path

import continuity_ledger
import script_contract
import stage_flow
import stage_layout
import stage_parallel
import workflow_settings

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / 'skills' / '06连贯性SKILL'
SKILLS = ('pipeline-continuity', 'continuity-anchor-freeze', 'continuity-conflict-adjudicate',
          'continuity-cross-batch-guard', 'continuity-drift-audit', 'continuity-triplet-check')


class ContinuityScopeTests(unittest.TestCase):
    def test_req_s06_02_depends_on_assets_and_is_serial(self):
        self.assertEqual(stage_flow.DEPENDS['continuity'], ('assets',))
        config = stage_parallel.CONFIG['continuity']
        self.assertEqual((config['min'], config['max'], config['serial']), (1, 1, False))
        self.assertEqual(config['retry']['attempts'], 2)
        self.assertEqual(config['retry']['on_exhaust'], stage_parallel.ON_BLOCK)

    def test_req_s06_02_gates_sit_on_both_sides_of_the_stage(self):
        gates = {row['id']: row for row in stage_parallel.GATES}
        self.assertEqual((gates['SG-01']['from'], gates['SG-01']['to'], gates['SG-01']['check']),
                         ('assets', 'continuity', 'assets_locked'))
        self.assertEqual((gates['SG-02']['from'], gates['SG-02']['to'], gates['SG-02']['check']),
                         ('continuity', 'final', 'ledger_ready'))

    def test_req_s06_03_stage_collects_no_locks(self):
        self.assertNotIn('continuity', script_contract.STAGE_LOCK_REQUIREMENTS)

    def test_req_s06_11_empty_build_has_all_sections(self):
        ledger = continuity_ledger.build([], {})
        for key in ('batches', 'conflicts', 'cross_batch', 'triplets', 'drift', 'summary'):
            with self.subTest(key=key):
                self.assertIn(key, ledger)
        self.assertEqual(ledger['version'], 1)
        self.assertEqual(ledger['summary'], {'batches': 0, 'shots': 0, 'ok': True, 'problems': []})

    def test_req_s06_20_bundle_lands_in_four_agreed_places_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw)
            ledger = continuity_ledger.build([], {})
            file = continuity_ledger.write(project, ledger)
            expected = (project / '06连贯性清单' / 'output' / 'continuity_ledger.json',
                        project / '06连贯性清单' / 'docs' / 'continuity_ledger.md',
                        project / '_shared' / 'anchors' / 'anchors.json',
                        project / '_shared' / 'triplets' / 'triplets.json')
            self.assertEqual(file, expected[0])
            before = [path.read_bytes() for path in expected]
            continuity_ledger.write(project, ledger)
            self.assertEqual([path.read_bytes() for path in expected], before)
            self.assertEqual(continuity_ledger.issues_path(project),
                             stage_layout.paths(project, '03_continuity')['output'] / 'continuity_issues.json')

    def test_req_s06_22_severity_by_kind(self):
        self.assertEqual(continuity_ledger.SEVERITIES,
                         {'conflict': '高', 'triplet': '高', 'drift': '中', 'cross_batch': '中'})

    def test_req_s06_23_sg02_passes_through_without_ledger_and_marks_started_with_one(self):
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw)
            before = stage_parallel.ledger_ready(project)
            self.assertTrue(before['ok'])
            self.assertFalse(before['started'])
            continuity_ledger.write(project, continuity_ledger.build([], {}))
            after = stage_parallel.ledger_ready(project)
            self.assertTrue(after['ok'])
            self.assertTrue(after['started'])

    def test_req_s06_23_sg02_blocks_a_ledger_with_unresolved_problems(self):
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw)
            ledger = continuity_ledger.build([], {})
            ledger['summary'] = {'batches': 1, 'shots': 1, 'ok': False, 'problems': ['B01：同一批次里出现 2 种三元组，必须重切批次']}
            continuity_ledger.write(project, ledger)
            result = stage_parallel.ledger_ready(project)
            self.assertFalse(result['ok'])
            self.assertTrue(result['started'])

    def test_req_s06_23_completion_uses_sg02_with_started(self):
        source = (ROOT / 'stage_completion_service.py').read_text(encoding='utf-8')
        self.assertIn("'continuity': 'ledger_ready'", source)
        self.assertIn("result.get('ok') and result.get('started')", source)

    def test_req_s06_30_six_skills_belong_to_the_stage(self):
        for name in SKILLS:
            with self.subTest(name=name):
                text = (SKILL_DIR / (name + '.skill.md')).read_text(encoding='utf-8')
                self.assertIn('name: ' + name, text)
                self.assertIn('stage: 连贯性清单', text)
        preset = workflow_settings.BUILTIN_WORKFLOW_PRESETS['AIGC全流程']['stage_skills']
        self.assertEqual(preset['continuity'], ['pipeline-continuity'])


if __name__ == '__main__':
    unittest.main()
