"""REQ-S08-01/02/03/04/10/50/51：首帧管理阶段的位置、依赖、锁、门禁、格式与 SKILL。"""
import unittest
from pathlib import Path

import keyframe_evidence
import pet_bus
import script_contract
import stage_flow
import stage_layout
import stage_parallel

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / 'skills' / '08首帧管理SKILL'
PAID = {'firstframe-batch': True, 'firstframe-auto-fill': True, 'firstframe-retry': True,
        'firstframe-quality': False, 'firstframe-thumbnail': False}


class KeyframeScopeTests(unittest.TestCase):
    def test_req_s08_01_stage_is_eighth_and_reads_final_storyboard(self):
        self.assertEqual(pet_bus.STAGES.index('keyframe'), 7)
        row = next(item for item in stage_layout.STAGES if item[1] == 'keyframe')
        self.assertEqual(row[0], '08首帧管理')
        self.assertIn('storyboard_final.json', row[4])

    def test_req_s08_02_depends_on_final_and_gate_sg03_guards_entry(self):
        self.assertEqual(stage_flow.DEPENDS['keyframe'], ('final',))
        gates = {row['id']: row for row in stage_parallel.GATES}
        self.assertEqual((gates['SG-03']['from'], gates['SG-03']['to']), ('final', 'keyframe'))
        self.assertEqual(gates['SG-03']['check'], 'batches_ready')

    def test_req_s08_03_three_locks_required(self):
        self.assertEqual(script_contract.STAGE_LOCK_REQUIREMENTS['keyframe'],
                         ('aspect_ratio', 'video_model_version', 'delivery_format'))

    def test_req_s08_04_gate_sg04_guards_previs_and_passes_empty_project(self):
        gates = {row['id']: row for row in stage_parallel.GATES}
        self.assertEqual((gates['SG-04']['from'], gates['SG-04']['to']), ('keyframe', 'previs'))
        self.assertEqual(gates['SG-04']['check'], 'frames_ready')
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            result = stage_parallel.frames_ready(folder)
        self.assertTrue(result['ok'])
        self.assertFalse(result['started'])

    def test_req_s08_10_only_nonempty_png_is_accepted(self):
        for data in (b'', b'GIF89a-not-a-png', b'\x89PNG\r\n\x1a\n'):
            with self.subTest(data=data[:8]):
                with self.assertRaises(ValueError):
                    keyframe_evidence.image_facts(data)

    def test_req_s08_50_six_skills_with_expected_cost_flags(self):
        self.assertTrue((SKILL_DIR / 'pipeline-keyframe.skill.md').is_file())
        for name, paid in PAID.items():
            with self.subTest(skill=name):
                text = (SKILL_DIR / (name + '.skill.md')).read_text(encoding='utf-8')
                self.assertIn('paid: ' + str(paid).lower(), text)

    def test_req_s08_51_pipeline_skill_depends_on_final_storyboard(self):
        text = (SKILL_DIR / 'pipeline-keyframe.skill.md').read_text(encoding='utf-8')
        self.assertIn('dependsOn: [pipeline-storyboard-final]', text)
        self.assertIn('每个首帧文件非空', text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
