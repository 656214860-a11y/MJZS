"""离线编剧任务书的新写入必须由剧本准备阶段服务决定。"""
import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class WritingPreparationPathBoundaryTests(unittest.TestCase):
    def test_prepare_delegates_numbered_script_stage_to_l3(self):
        tree = ast.parse((ROOT / 'writing.py').read_text(encoding='utf-8'))
        prepare = next(node for node in tree.body
                       if isinstance(node, ast.FunctionDef) and node.name == 'prepare')
        names = {node.id for node in ast.walk(prepare) if isinstance(node, ast.Name)}
        self.assertIn('publish', names)
        self.assertNotIn('script_stage', names)
        service = (ROOT / 'stage_execution_service.py').read_text(encoding='utf-8')
        self.assertIn("script_dir = write_dir(root, 'script')", service)
