"""REQ-S02-02/15/23/30/31：剧本结构阶段的锁、范围、SKILL 与 manifest 归属。"""
import unittest
from pathlib import Path

import script_contract
import workflow_settings
from script_manifest_schema import MERGED, PRODUCERS

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / 'skills' / '02 剧本整理SKILL'
SKILLS = ('pipeline-script-structure', 'script-structured-generation', 'script-character-extraction',
          'script-dialogue-polish', 'script-worldbuilding')


class ScriptStructureScopeTests(unittest.TestCase):
    def test_req_s02_02_structure_stage_collects_no_locks(self):
        self.assertNotIn('script_structure', script_contract.STAGE_LOCK_REQUIREMENTS)

    def test_req_s02_15_output_contract_forbids_storyboard_work(self):
        contract = workflow_settings.stage_output_contract('script_structure')
        for term in ('镜头三元组', '分镜 JSON', '首帧', '不得重写或替换自然语言原稿'):
            with self.subTest(term=term):
                self.assertIn(term, contract)

    def test_req_s02_23_three_manifests_belong_to_character_extraction(self):
        for name in ('character_manifest.json', 'scene_manifest.json', 'prop_manifest.json'):
            with self.subTest(name=name):
                self.assertEqual(PRODUCERS[name][0], 'script-character-extraction')
        skill = (SKILL_DIR / 'script-character-extraction.skill.md').read_text(encoding='utf-8')
        for name in ('character_manifest.json', 'scene_manifest.json', 'prop_manifest.json'):
            self.assertIn(name, skill)

    def test_req_s02_23_structure_stage_does_not_own_other_manifests(self):
        mine = {name for name, (skill, _stage) in PRODUCERS.items() if skill.startswith('script-')}
        self.assertEqual(mine, {'character_manifest.json', 'scene_manifest.json', 'prop_manifest.json'})

    def test_req_s02_30_five_skills_exist_for_the_stage(self):
        for name in SKILLS:
            with self.subTest(name=name):
                self.assertTrue((SKILL_DIR / (name + '.skill.md')).is_file())

    def test_req_s02_31_dialogue_and_worldbuilding_are_merged_not_standalone(self):
        landing = {skill: place for skill, _part, place in MERGED}
        self.assertEqual(set(landing), {'script-dialogue-polish', 'script-worldbuilding'})
        self.assertIn('不单独出文件', landing['script-dialogue-polish'])
        self.assertEqual(landing['script-worldbuilding'], 'docs/world_bible.md')


if __name__ == '__main__':
    unittest.main()
