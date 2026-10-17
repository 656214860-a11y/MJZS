"""REQ-S04-01/03/04/21/22/50/51：分镜预演阶段的位置、依赖、锁、门禁、并行与 SKILL。"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import pet_bus
import script_contract
import stage_flow
import stage_handler_registry
import stage_layout
import stage_parallel

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills' / '04 分镜预演SKILL' / 'pipeline-animatic.skill.md'


class AnimaticScopeTests(unittest.TestCase):
    def test_req_s04_01_stage_is_fourth_between_storyboard_and_assets(self):
        self.assertEqual(pet_bus.STAGES.index('animatic'), 3)
        row = next(item for item in stage_layout.STAGES if item[1] == 'animatic')
        self.assertEqual(row[0], '04分镜预演')
        self.assertEqual(stage_flow.DEPENDS['animatic'], ('storyboard',))
        self.assertEqual(stage_flow.DEPENDS['assets'], ('animatic',))

    def test_req_s04_03_start_only_opens_the_page_and_never_generates(self):
        with tempfile.TemporaryDirectory() as folder:
            manual = Mock(root=Path(folder), pet=None)
            self.assertEqual(stage_handler_registry.start(manual, 'animatic', 'manual'), '')
            auto = Mock(root=Path(folder))
            reply = stage_handler_registry.start(auto, 'animatic', 'auto')
        manual.show.assert_called_once_with(pet_bus.STAGES.index('animatic'))
        auto.show.assert_called_once_with(pet_bus.STAGES.index('animatic'))
        self.assertIn('确认节奏、时长和对白同步', reply)
        auto.pet._emit.assert_called_once()

    def test_req_s04_04_no_lock_is_required(self):
        self.assertNotIn('animatic', script_contract.STAGE_LOCK_REQUIREMENTS)

    def test_req_s04_05_and_42_gates_sg_a_and_sg_b_are_registered(self):
        gates = {row['id']: row for row in stage_parallel.GATES}
        self.assertEqual((gates['SG-A']['from'], gates['SG-A']['to'], gates['SG-A']['check']),
                         ('storyboard', 'animatic', 'animatic_input_ready'))
        self.assertEqual((gates['SG-B']['from'], gates['SG-B']['to'], gates['SG-B']['check']),
                         ('animatic', 'assets', 'animatic_ready'))

    def test_req_s04_05_empty_project_blocks_sg_a(self):
        with tempfile.TemporaryDirectory() as folder:
            result = stage_parallel.animatic_input_ready(folder)
        self.assertFalse(result['ok'])

    def test_req_s04_21_22_parallel_config(self):
        config = stage_parallel.CONFIG['animatic']
        self.assertEqual((config['unit'], config['limit'], config['serial']), (stage_parallel.BATCH, 3, True))
        self.assertEqual(config['retry']['attempts'], 2)
        self.assertEqual(config['retry']['on_exhaust'], stage_parallel.ON_MANUAL)

    def test_req_s04_41_unconfirmed_empty_project_is_not_complete(self):
        import animatic_service
        with tempfile.TemporaryDirectory() as folder:
            ok, _reason = animatic_service.evidence(folder)
        self.assertFalse(ok)

    def test_req_s04_50_51_single_free_skill_with_local_only_constraints(self):
        text = SKILL.read_text(encoding='utf-8')
        self.assertIn('paid: false', text)
        self.assertIn('dependsOn: [pipeline-storyboard-draft]', text)
        self.assertIn('tools: [animatic.generate, animatic.validate]', text)
        self.assertIn('不替代正式资产或首帧或正式视频', text)
        self.assertEqual(len(list(SKILL.parent.glob('*.skill.md'))), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
