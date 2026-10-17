"""REQ-S07-01/02/03/04/13/14/33/41/42/50/51：分镜定稿阶段的范围、批次规则、门禁与 SKILL 归属。"""
import json
import re
import unittest
from pathlib import Path
from unittest import mock

import pet_bus
import shot_batches
import stage_flow
import stage_layout
import stage_parallel
import stage_path_service
import workflow_settings
from storyboard_paths import is_final_dir

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / 'skills' / '07分镜定稿SKILL'
SKILLS = ('pipeline-storyboard-final', 'storyboard-asset-sync', 'storyboard-consistency-lock',
          'storyboard-final-validate', 'storyboard-prompt-render', 'storyboard-version-snapshot')


def _shot(index, batch='', scene='LOC_001', seconds=3):
    return {'id': 'S%02d' % index, 'scene_id': scene, 'character_ids': ['CHAR_001'], 'costume_id': 'CST-01',
            'batch_id': batch, 'estimated_duration': seconds}


def _walk(value):
    yield value
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


class StoryboardFinalScopeTests(unittest.TestCase):
    def test_req_s07_40_stage_identity_and_directory(self):
        self.assertEqual(pet_bus.STAGE_NAMES['final'], '分镜定稿')
        row = next(item for item in stage_layout.STAGES if item[1] == 'final')
        self.assertEqual(row[0], '07分镜定稿')

    def test_req_s07_33_new_writes_use_07_and_legacy_06_is_read_only(self):
        project = Path('X:/project')
        self.assertEqual(stage_path_service.write_dir(project, 'final').name, '07分镜定稿')
        self.assertEqual(stage_path_service.LEGACY_NUMBERED['final'], '06分镜定稿')
        names = [folder.name for folder in stage_path_service.read_dirs(project, 'final')]
        self.assertEqual(names[0], '07分镜定稿')
        self.assertIn('06分镜定稿', names[1:])

    def test_req_s07_33_final_directory_names_are_recognised(self):
        self.assertTrue(is_final_dir('EP001_分镜定稿_20261017'))
        self.assertTrue(is_final_dir('定稿_旧命名'))
        self.assertFalse(is_final_dir('EP001_分镜初稿'))

    def test_req_s07_03_dependency_table_only_names_storyboard(self):
        self.assertEqual(stage_flow.DEPENDS['final'], ('storyboard',))
        self.assertEqual(stage_flow.MANUAL_LABELS['final'], '手动同步资产')

    def test_req_s07_04_final_runs_as_a_single_global_task(self):
        config = stage_parallel.CONFIG['final']
        self.assertEqual((config['min'], config['max'], config['limit']), (1, 1, 1))
        self.assertEqual(config['retry']['attempts'], 2)
        self.assertEqual(config['retry']['on_exhaust'], stage_parallel.ON_BLOCK)

    def test_req_s07_02_and_42_gates_around_the_stage(self):
        entry = stage_parallel.gate_for('final')
        self.assertEqual((entry['id'], entry['from'], entry['check']), ('SG-02', 'continuity', 'ledger_ready'))
        exit_gate = stage_parallel.gate_for('keyframe')
        self.assertEqual((exit_gate['id'], exit_gate['from'], exit_gate['check']),
                         ('SG-03', 'final', 'batches_ready'))

    def test_req_s07_13_batch_limits_and_nine_fields(self):
        self.assertEqual(shot_batches.BATCH_MAX_SHOTS, 4)
        self.assertEqual(shot_batches.BATCH_SECONDS, 18)
        self.assertEqual(shot_batches.BATCH_SECONDS_LONG, 25)
        self.assertEqual(shot_batches.TRIPLET, ('scene_id', 'character_ids', 'costume_id'))
        self.assertEqual([item[0] for item in shot_batches.SHOT_FIELDS],
                         ['shot_id', 'scene_id', 'character_ids', 'costume_id', 'batch_id',
                          'character_refs', 'reference_roles', 'continuity_flags', 'estimated_duration'])

    def test_req_s07_13_assign_numbers_batches_and_keeps_old_keys(self):
        shots = [{'id': 'S01', 'location': 'LOC_001', 'characters': ['CHAR_001'], 'duration': 3}]
        out = shot_batches.assign(shots)
        self.assertEqual(out[0]['batch_id'], 'B01')
        self.assertEqual(out[0]['id'], 'S01')
        self.assertEqual(out[0]['location'], 'LOC_001')
        self.assertEqual(out[0]['duration'], 3)

    def test_req_s07_14_design_range_is_advice_but_four_is_the_hard_limit(self):
        self.assertEqual(shot_batches.BATCH_SHOTS, (3, 5))
        two = [_shot(1, 'B01'), _shot(2, 'B01')]
        self.assertEqual(shot_batches.check_batches(two), [])
        self.assertTrue(any('设计区间' in note for note in shot_batches.advise(two)))
        five = [_shot(index, 'B01', seconds=2) for index in range(1, 6)]
        self.assertTrue(shot_batches.check_batches(five))

    def test_req_s07_42_gate_lets_through_a_project_without_adopted_storyboard(self):
        with mock.patch.object(stage_parallel, '_adopted', return_value=[]):
            result = stage_parallel.batches_ready(Path('X:/project'))
        self.assertTrue(result['ok'])
        self.assertFalse(result['started'])

    def test_req_s07_42_gate_blocks_started_but_incomplete_batches(self):
        shots = [_shot(index, 'B01', seconds=2) for index in range(1, 6)]
        with mock.patch.object(stage_parallel, '_adopted', return_value=[(Path('x.json'), shots)]), \
                mock.patch.object(stage_parallel, 'has_run', return_value=False):
            result = stage_parallel.batches_ready(Path('X:/project'))
        self.assertFalse(result['ok'])
        self.assertTrue(result['started'])

    def test_req_s07_42_gate_blocks_shots_without_batch_id_once_batching_started(self):
        shots = [_shot(1, 'B01'), _shot(2, '')]
        with mock.patch.object(stage_parallel, '_adopted', return_value=[(Path('x.json'), shots)]), \
                mock.patch.object(stage_parallel, 'has_run', return_value=False):
            result = stage_parallel.batches_ready(Path('X:/project'))
        self.assertFalse(result['ok'])

    def test_req_s07_41_completed_batches_count_as_stage_evidence(self):
        shots = [_shot(1, 'B01'), _shot(2, 'B01')]
        with mock.patch.object(stage_parallel, '_adopted', return_value=[(Path('x.json'), shots)]), \
                mock.patch.object(stage_parallel, 'has_run', return_value=False):
            result = stage_parallel.batches_ready(Path('X:/project'))
        self.assertTrue(result['ok'] and result['started'])

    def test_req_s07_41_completion_service_maps_final_to_batches_ready(self):
        text = (ROOT / 'stage_completion_service.py').read_text(encoding='utf-8')
        self.assertIn("'final': 'batches_ready'", text)

    def test_req_s07_50_six_skills_belong_to_the_stage(self):
        for name in SKILLS:
            with self.subTest(name=name):
                path = SKILL_DIR / (name + '.skill.md')
                self.assertTrue(path.is_file())
                self.assertRegex(path.read_text(encoding='utf-8'), r'(?m)^stage: 分镜定稿$')
        self.assertEqual(sorted(path.name for path in SKILL_DIR.glob('*.skill.md')),
                         sorted(name + '.skill.md' for name in SKILLS))

    def test_req_s07_50_default_skill_is_the_pipeline_entry(self):
        manifest = json.loads(workflow_settings.MASTER_MANIFEST.read_text(encoding='utf-8'))
        self.assertIn(['pipeline-storyboard-final'], [
            value['final'] for value in _walk(manifest) if isinstance(value, dict) and 'final' in value])
        builtin = workflow_settings.BUILTIN_WORKFLOW_PRESETS['AIGC全流程']['stage_skills']
        self.assertEqual(builtin['final'], ['pipeline-storyboard-final'])

    def test_req_s07_51_pipeline_skill_reads_locks_and_freezes_seams(self):
        text = (SKILL_DIR / 'pipeline-storyboard-final.skill.md').read_text(encoding='utf-8')
        for term in ('splice_mode', 'in_state', 'out_state', 'cut_type', 'audio_bridge', 'owner',
                     '不得加载 00 包全文', '不再向用户弹问'):
            with self.subTest(term=term):
                self.assertIn(term, text)
        self.assertIsNotNone(re.search(r'(?m)^dependsOn: \[pipeline-continuity\]$', text))


if __name__ == '__main__':
    unittest.main()
