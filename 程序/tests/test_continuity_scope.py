"""REQ-S06-02/03/11/20/22/23/30：连贯性清单阶段的依赖、锁、产出、完成判据与 SKILL 范围。"""
import tempfile
import unittest
from pathlib import Path

import continuity_ledger
import script_contract
import stage_flow
import stage_layout
import stage_config
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

    def test_req_s06_24_sg02_blocks_a_ledger_that_does_not_match_current_shots(self):
        from unittest.mock import patch
        shots = [{'id': 'S01', 'characters': [], 'location': ''}, {'id': 'S02', 'characters': [], 'location': ''}]
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw)
            continuity_ledger.write(project, continuity_ledger.build(shots, {}))
            with patch.object(stage_parallel, '_adopted', return_value=[(project / 'a.json', shots)]):
                self.assertTrue(stage_parallel.ledger_ready(project)['ok'])
            more = shots + [{'id': 'S03', 'characters': [], 'location': ''}]
            with patch.object(stage_parallel, '_adopted', return_value=[(project / 'a.json', more)]):
                result = stage_parallel.ledger_ready(project)
            self.assertFalse(result['ok'])
            self.assertTrue(result['started'])
            self.assertIn('S03', ' '.join(result['problems']))

    def test_req_s06_24_empty_ledger_does_not_cover_adopted_shots_and_missing_ledger_still_passes(self):
        from unittest.mock import patch
        shots = [{'id': 'S01', 'characters': [], 'location': ''}]
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw)
            with patch.object(stage_parallel, '_adopted', return_value=[(project / 'a.json', shots)]):
                self.assertTrue(stage_parallel.ledger_ready(project)['ok'])
                continuity_ledger.write(project, continuity_ledger.build([], {}))
                self.assertFalse(stage_parallel.ledger_ready(project)['ok'])

    def test_req_s06_32_skill_declares_local_rules_and_maps_repair_list(self):
        text = (SKILL_DIR / 'pipeline-continuity.skill.md').read_text(encoding='utf-8')
        self.assertIn('capabilities: [structured-output]', text)
        self.assertNotIn('qwen-max', text)
        self.assertIn('continuity_issues.json', text)
        self.assertIn('不调用模型', text)

    def test_req_s06_33_auto_chain_has_one_entry_through_the_registry(self):
        source = (ROOT / 'desktop_pet_bridge.py').read_text(encoding='utf-8')  # SPLITD：pet_start/_start_unattended_stage 迁到 PetBridgeMixin
        self.assertIn("if stage=='continuity':return self.pet_continuity_ledger()", source)
        self.assertIn("stage_handler_registry.start(self,stage,trigger='auto',fallback=self._start_unattended_stage)",
                      source)
        pages = (ROOT / 'desktop_media_pages.py').read_text(encoding='utf-8')
        self.assertEqual(pages.count('self.write_continuity_ledger('), 1)
        self.assertGreaterEqual(pages.count('self.generate_continuity_ledger('), 2)

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
        self.assertIn('pipeline-continuity', stage_config.default_entry('continuity')['skills'])

    def test_req_s06_26_g08_is_optional_and_sg02_does_not_depend_on_it(self):
        """REQ-S06-26：G-08 人工裁决可选、建议，不是 SG-02 的放行条件。"""
        import confirm_gates
        gate = confirm_gates.by_id('G-08')
        self.assertEqual(gate['type'], confirm_gates.SUBJECTIVE)
        self.assertEqual(gate['ask'], 'conflicts')
        self.assertIn('可选', gate['condition'])
        self.assertIn('不影响 SG-02', gate['reject'])
        self.assertIn('可选', stage_flow.RECOVERY_HINTS['continuity'])
        sg02 = next(row for row in stage_parallel.GATES if row['id'] == 'SG-02')
        self.assertEqual(sg02['check'], 'ledger_ready')
        self.assertNotIn('G-08', str(sg02))


if __name__ == '__main__':
    unittest.main()
