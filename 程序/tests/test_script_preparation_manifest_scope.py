"""REQ-S01-23：剧本准备只产出 emotion_curve.json，其余四类 manifest 归后续 SKILL。"""
import unittest
from pathlib import Path

from contract.script_manifest_schema import PRODUCERS

ROOT = Path(__file__).resolve().parents[1]


class ScriptPreparationManifestScopeTests(unittest.TestCase):
    def test_only_emotion_curve_from_preparation_skill(self):
        mine = sorted(name for name, (skill, _stage) in PRODUCERS.items()
                      if skill == 'pipeline-script-preparation')
        self.assertEqual(mine, ['emotion_curve.json'])

    def test_other_manifests_owned_by_later_skills(self):
        for name in ('character_manifest.json', 'scene_manifest.json', 'prop_manifest.json'):
            with self.subTest(name=name):
                self.assertEqual(PRODUCERS[name][0], 'script-character-extraction')
        self.assertEqual(PRODUCERS['scene_breakdown.json'][0], 'storyboard-scene-breakdown')

    def test_skill_declares_emotion_curve_as_auxiliary(self):
        text = (ROOT / 'skills' / '01 剧本准备SKILL' / 'pipeline-script-preparation.skill.md').read_text(encoding='utf-8')
        self.assertIn('emotion_curve.json', text)
        self.assertIn('辅助质检数据', text)

    def test_writing_api_does_not_write_manifests(self):
        text = (ROOT / 'writing_api.py').read_text(encoding='utf-8')
        for name in PRODUCERS:
            with self.subTest(name=name):
                self.assertNotIn(name, text)


if __name__ == '__main__':
    unittest.main()
