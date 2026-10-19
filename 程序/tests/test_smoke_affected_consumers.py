"""REQ-AFFECT-01：--affected 必须包含直接导入改动模块的测试文件。"""
import ast
import unittest
from pathlib import Path

import smoke_test


class AffectedConsumerTests(unittest.TestCase):
    def test_stage_layout_consumer_without_module_name_is_selected(self):
        """REQ-AFFECT-01：test_animatic_scope 导入 stage_layout，但文件名不含该模块名。"""
        selected = smoke_test.affected_test_modules(('stage_layout',))
        expected = set()
        tests_dir = Path(__file__).parent
        for path in tests_dir.glob('**/test_*.py'):
            tree = ast.parse(path.read_text(encoding='utf-8'))
            imported = {
                alias.name.split('.', 1)[0]
                for node in ast.walk(tree) if isinstance(node, ast.Import)
                for alias in node.names
            }
            imported.update(
                node.module.split('.', 1)[0]
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and not node.level and node.module
            )
            if 'stage_layout' in imported:
                expected.add('.'.join(path.relative_to(tests_dir).with_suffix('').parts))

        self.assertTrue(expected <= set(selected))
        self.assertIn('test_animatic_scope', selected)
        self.assertNotIn('stage_layout', 'test_animatic_scope')

    def test_existing_aliases_remain_in_filters(self):
        """REQ-AFFECT-02：既有手工别名仍是兼容兜底。"""
        self.assertIn('skills', smoke_test.affected_test_filters(('skill_registry',)))


if __name__ == '__main__':
    unittest.main()
