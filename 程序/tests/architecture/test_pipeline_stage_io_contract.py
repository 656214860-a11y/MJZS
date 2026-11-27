"""全流程阶段目录骨架、输入来源和 manifest 归属契约。"""
from pathlib import Path
import unittest

import pet_bus
import script_contract
import skill_registry
import stage_layout

PROGRAM = Path(__file__).resolve().parents[2]
SKILLS = PROGRAM / 'skills'


class PipelineStageIoContractTests(unittest.TestCase):
    def test_animatic_tools_and_gates_follow_the_stage_authority(self):
        import skill_tools
        import stage_parallel
        self.assertEqual(pet_bus.STAGES[2:5], ('storyboard', 'animatic', 'assets'))
        self.assertEqual(stage_parallel.gate_for('animatic')['id'], 'SG-A')
        self.assertEqual(stage_parallel.gate_for('assets')['id'], 'SG-B')
        for tool in ('animatic.generate', 'animatic.validate'):
            self.assertEqual(skill_tools.PAGES[tool][0], pet_bus.STAGES.index('animatic'))

    def setUp(self):
        self.registry = skill_registry.Registry(SKILLS)
        self.registry.scan(force=True)
        self.stage_index = {stage: position for position, stage in enumerate(pet_bus.STAGES)}

    def test_builtin_skills_contain_no_retired_pipeline_or_stage_files(self):
        self.assertEqual(self.registry.getAll(), [], '程序内置 skills/ 不应残留任何已退役的内置 SKILL')
        leftover = sorted(str(p.relative_to(SKILLS)) for p in SKILLS.rglob('*.skill.md'))
        self.assertEqual(leftover, [], f'内置 skills/ 残留 .skill.md：{leftover}')
        for number in range(0, 14):
            prefix = '%02d' % number
            matches = [d for d in SKILLS.iterdir() if d.is_dir() and d.name.startswith(prefix)]
            self.assertEqual(len(matches), 1, f'内置 skills/ 应保留干净的 {prefix} 阶段目录骨架')

    def test_manifest_owners_derive_from_stage_contract_sources(self):
        for filename, (producer, folder) in script_contract.PRODUCERS.items():
            # REQ-S02-25：每份 manifest 落在产出它的阶段目录，而不是统一堆进旧名 00_script。
            row = stage_layout.stage_dir(folder)
            self.assertIn(filename, row[5])
            self.assertNotIn(row[0], stage_layout.LEGACY_STAGE_ALIASES)
            self.assertTrue(script_contract.is_stage_producer(producer),
                            f'{filename} 产出者应显式归属阶段 stage:<key>：{producer}')
            owner_stage = script_contract.producer_stage_key(producer)
            self.assertIn(owner_stage, self.stage_index, producer)
