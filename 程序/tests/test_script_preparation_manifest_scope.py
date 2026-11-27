"""REQ-S01-23：剧本准备只产出 emotion_curve.json，其余四类 manifest 归后续 SKILL。"""
import unittest
from pathlib import Path

from contract.script_manifest_schema import PRODUCERS, normalize_producer

ROOT = Path(__file__).resolve().parents[1]


class ScriptPreparationManifestScopeTests(unittest.TestCase):
    def test_only_emotion_curve_from_preparation_skill(self):
        mine = sorted(name for name, (producer, stage) in PRODUCERS.items()
                      if producer == 'stage:script' and stage == '01剧本准备')
        self.assertEqual(mine, ['emotion_curve.json'])
        self.assertNotIn('pipeline-script-preparation',
                         {producer for producer, _stage in PRODUCERS.values()})
        self.assertEqual(normalize_producer('pipeline-script-preparation'), 'stage:script')

    def test_other_manifests_owned_by_later_skills(self):
        for name in ('character_manifest.json', 'scene_manifest.json', 'prop_manifest.json'):
            with self.subTest(name=name):
                self.assertEqual(PRODUCERS[name][0], 'stage:script_structure')
        self.assertEqual(PRODUCERS['scene_breakdown.json'][0], 'stage:storyboard')
        self.assertEqual(normalize_producer('script-character-extraction'), 'stage:script_structure')
        self.assertEqual(normalize_producer('storyboard-scene-breakdown'), 'stage:storyboard')

    def test_skill_declares_emotion_curve_as_auxiliary(self):
        import workflow_settings
        self.assertEqual(PRODUCERS['emotion_curve.json'], ('stage:script', '01剧本准备'))
        contract = workflow_settings.stage_output_contract('writing')
        self.assertIn('节拍表', contract)
        self.assertIn('唯一正式交付物是完整自然语言剧本正文', contract)

    def test_writing_api_does_not_write_manifests(self):
        text = (ROOT / 'writing_api.py').read_text(encoding='utf-8')
        for name in PRODUCERS:
            with self.subTest(name=name):
                self.assertNotIn(name, text)


if __name__ == '__main__':
    unittest.main()
