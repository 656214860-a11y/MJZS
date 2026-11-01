"""REQ-S02-02/15/23/30/31：剧本结构阶段的锁、范围、SKILL 与 manifest 归属。"""
import json
import tempfile
import unittest
from pathlib import Path

import script_contract
import skill_orchestrator
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


STRUCTURED = script_contract.structure_script(
    '第1场 咖啡馆 内景\n林夏：你好，我是黑发的人。\n陈默：道具：旧怀表\n林夏：走吧。')


class StructureManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def structured_file(self):
        path = script_contract.canonical_structured_script_path(self.root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(STRUCTURED, encoding='utf-8')
        return path

    def test_req_s02_23_manifests_are_derived_from_the_structured_script(self):
        folder = script_contract.write_structure_manifests(self.root, STRUCTURED)
        self.assertEqual(folder.parent.name, '02剧本结构')
        data = {name: json.loads((folder / name).read_text(encoding='utf-8'))
                for name in script_contract.STRUCTURE_MANIFESTS}
        self.assertEqual([i['name'] for i in data['character_manifest.json']['items']], ['林夏', '陈默'])
        self.assertEqual(data['character_manifest.json']['items'][0]['character_id'], 'CHAR_001')
        self.assertEqual(len(data['scene_manifest.json']['items']), 1)
        self.assertEqual(data['scene_manifest.json']['items'][0]['scene_id'], 'LOC_001')

    def test_req_s02_23_stage_is_not_verified_until_manifests_exist(self):
        path = self.structured_file()
        self.assertTrue(script_contract.is_structured_script(path))
        self.assertFalse(skill_orchestrator.verified_stage_output(self.root, 'script_structure'))
        script_contract.write_structure_manifests(self.root, STRUCTURED)
        self.assertEqual(script_contract.structure_manifest_problems(self.root, path), [])
        self.assertTrue(skill_orchestrator.verified_stage_output(self.root, 'script_structure'))

    def test_completion_service_and_orchestrator_share_one_script_structure_criterion(self):
        """R2178 J16：两处判据一致——结构剧本在、manifest 缺失时都不算完成；补齐后都算。"""
        import stage_completion_service
        path = self.structured_file()
        self.assertTrue(script_contract.is_structured_script(path))
        done, reason = stage_completion_service.completion_evidence(self.root, 'script_structure')
        self.assertFalse(done, '缺 manifest 时完成服务不应放行')
        self.assertFalse(skill_orchestrator.verified_stage_output(self.root, 'script_structure'))
        script_contract.write_structure_manifests(self.root, STRUCTURED)
        self.assertTrue(stage_completion_service.completion_evidence(self.root, 'script_structure')[0])
        self.assertTrue(skill_orchestrator.verified_stage_output(self.root, 'script_structure'))

    def test_req_s02_23_stale_or_broken_manifest_blocks_verification(self):
        path = self.structured_file()
        folder = script_contract.write_structure_manifests(self.root, STRUCTURED)
        target = folder / 'scene_manifest.json'
        stale = json.loads(target.read_text(encoding='utf-8'))
        stale['items'][0]['name'] = '别的场景'
        target.write_text(json.dumps(stale, ensure_ascii=False), encoding='utf-8')
        self.assertTrue(any('不一致' in text for text in script_contract.structure_manifest_problems(self.root, path)))
        target.write_text('{不是 JSON', encoding='utf-8')
        self.assertTrue(any('读不出来' in text for text in script_contract.structure_manifest_problems(self.root, path)))

    def test_req_s02_23_write_structured_script_publishes_manifests_with_it(self):
        raw = self.root / '01剧本准备' / 'output' / 'script_raw.md'
        raw.parent.mkdir(parents=True)
        raw.write_text('第1场 咖啡馆 内景\n林夏：你好。', encoding='utf-8')
        script_contract.write_structured_script(self.root, source=raw)
        self.assertEqual(script_contract.structure_manifest_problems(
            self.root, script_contract.structured_script_path(self.root)), [])

    def test_req_s02_25_manifests_land_in_their_producer_stage_not_legacy_dir(self):
        import stage_layout
        for name, (_skill, folder) in PRODUCERS.items():
            with self.subTest(name=name):
                self.assertIn(name, stage_layout.stage_dir(folder)[5])
                self.assertNotIn(folder, stage_layout.LEGACY_STAGE_ALIASES)
        self.assertEqual(PRODUCERS['character_manifest.json'][1], '02剧本结构')
        self.assertEqual(PRODUCERS['scene_breakdown.json'][1], '03初步分镜')
        self.assertEqual(PRODUCERS['emotion_curve.json'][1], '01剧本准备')


if __name__ == '__main__':
    unittest.main()
