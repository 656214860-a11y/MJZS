# -*- coding: utf-8 -*-
"""阶段名称展示必须服从 pet_bus 的单一权威表。"""
import ast
import unittest
from pathlib import Path

import pet_bus


ROOT = Path(__file__).resolve().parents[2]


class StageDisplayBoundaryTests(unittest.TestCase):
    def test_desktop_pages_are_generated_from_canonical_stage_table(self):
        source = (ROOT / 'desktop.py').read_text(encoding='utf-8')
        self.assertIn('for index, stage in enumerate(pet_bus.STAGES, start=1)', source)
        self.assertIn('pet_bus.stage_name(stage)', source)

        tree = ast.parse(source)
        pages_assignment = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == 'PAGES' for target in node.targets)
        )
        literals = [node.value for node in ast.walk(pages_assignment.value)
                    if isinstance(node, ast.Constant) and isinstance(node.value, str)]
        self.assertFalse(set(literals) & set(pet_bus.STAGE_NAMES.values()))
        self.assertIn('13  参考网站', literals)

    def test_stage_name_has_a_stable_unknown_stage_fallback(self):
        self.assertEqual(pet_bus.stage_name('script'), pet_bus.STAGE_NAMES['script'])
        self.assertEqual(pet_bus.stage_name('unknown'), 'unknown')
        self.assertEqual(pet_bus.stage_name('unknown', '当前阶段'), '当前阶段')
