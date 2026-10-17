"""REQ-S03-02/05/10/11/12/13/14/16/17/18/40/42/44/50：初步分镜阶段的锁、并行、契约文本、路径、SG-A 与 SKILL 归属。"""
import tempfile
import unittest
from pathlib import Path

import script_contract
import stage_flow
import stage_parallel
import storyboard_catalog_service
import storyboard_contract
import storyboard_plan_service
import workflow_settings
from script_manifest_schema import PRODUCERS
from storyboard_paths import media_root

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / 'skills' / '03初步分镜SKILL'
SKILLS = ('pipeline-storyboard-draft', 'storyboard-scene-breakdown', 'storyboard-shot-generation',
          'storyboard-camera-language', 'storyboard-duration-estimate', 'storyboard-pacing-check')


class StoryboardScopeTests(unittest.TestCase):
    def test_req_s03_02_depends_on_structure_and_collects_no_locks(self):
        self.assertEqual(stage_flow.DEPENDS['storyboard'], ('script_structure',))
        self.assertNotIn('storyboard', script_contract.STAGE_LOCK_REQUIREMENTS)

    def test_req_s03_05_parallel_by_scene_serial_inside_and_blocking_retry(self):
        row = stage_parallel.CONFIG['storyboard']
        self.assertEqual((row['unit'], row['min'], row['max'], row['limit']),
                         (stage_parallel.SCENE, 2, 3, 3))
        self.assertTrue(row['serial'])
        self.assertEqual(row['retry']['attempts'], 2)
        self.assertEqual(row['retry']['on_exhaust'], stage_parallel.ON_BLOCK)

    def test_req_s03_10_to_17_contract_text_keeps_json_rules(self):
        text = storyboard_contract.rules()
        for term in ('episode_id', 'source_script', 'prompt_language', 'SH001', '2–15', '1–1500',
                     'frame_prompt', 'video_prompt', 'trim_in', 'ordinary_props', 'action_complexity',
                     'validate_episode', '镜头三元组'):
            with self.subTest(term=term):
                self.assertIn(term, text)

    def test_req_s03_01_04_work_plan_splits_todo_and_revise(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = storyboard_plan_service.build_work_plan(
                [root / 'a.md', root / 'b.md'], [root / 'x.json', root / 'y.json'],
                [root / 'a.md'], [root / 'x.json'])
            self.assertEqual(plan['todo'], [(root / 'b.md').resolve()])
            self.assertEqual(plan['revise'], [(root / 'y.json').resolve()])

    def test_req_s03_40_new_and_legacy_dirs_share_media_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            for name in ('分镜拆分', '分镜文档'):
                self.assertEqual(media_root(root / '03初步分镜' / name / 'EP001.json'), root / '03初步分镜')
        for name in ('frames', '历史版本', '剧本输入', '首帧任务'):
            self.assertIn(name, storyboard_catalog_service.IGNORED)

    def test_req_s03_42_gate_sga_guards_storyboard_to_animatic(self):
        gate = next(row for row in stage_parallel.GATES if row['id'] == 'SG-A')
        self.assertEqual((gate['from'], gate['to'], gate['check']), ('storyboard', 'animatic', 'animatic_input_ready'))
        self.assertTrue(callable(getattr(stage_parallel, gate['check'])))

    def test_req_s03_19_output_contract_forbids_rewriting_structure_script(self):
        contract = workflow_settings.stage_output_contract('storyboard')
        for term in ('结构剧本', '镜头三元组', '不得重新整理角色'):
            with self.subTest(term=term):
                self.assertIn(term, contract)

    def test_req_s03_44_scene_breakdown_belongs_to_storyboard_skill(self):
        self.assertEqual(PRODUCERS['scene_breakdown.json'][0], 'storyboard-scene-breakdown')
        mine = {name for name, (skill, _stage) in PRODUCERS.items() if skill.startswith('storyboard-')}
        self.assertEqual(mine, {'scene_breakdown.json'})

    def test_req_s03_50_six_skills_exist_for_the_stage(self):
        for name in SKILLS:
            with self.subTest(name=name):
                path = SKILL_DIR / (name + '.skill.md')
                self.assertTrue(path.is_file())
                self.assertIn('stage: 初步分镜', path.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
