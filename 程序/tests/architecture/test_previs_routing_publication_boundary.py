"""白模分流的正式 JSON 只能由 L3 发布器注入。"""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class PrevisRoutingPublicationBoundaryTests(unittest.TestCase):
    def test_l2_write_points_require_an_injected_publisher(self):
        source = (ROOT / 'previs_routing.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        methods = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        self.assertNotIn('from agent.core import read,save', source)
        for name in ('set_override', 'dispatch'):
            self.assertIn('publish', [argument.arg for argument in methods[name].args.kwonlyargs])
            calls = [node for node in ast.walk(methods[name]) if isinstance(node, ast.Call)]
            self.assertTrue(any(isinstance(node.func, ast.Name) and node.func.id == 'publish' for node in calls))

    def test_previs_page_delegates_publication_to_l3(self):
        page = (ROOT / 'local_previs.py').read_text(encoding='utf-8')
        self.assertIn('from stage_execution_service import save_stage_previs_override', page)
        self.assertIn('from stage_execution_service import dispatch_stage_previs', page)
        self.assertNotIn('previs_routing.set_override(', page)
        self.assertNotIn('previs_routing.dispatch(', page)
        service = (ROOT / 'stage_execution_service.py').read_text(encoding='utf-8')
        self.assertIn('def save_stage_previs_override(', service)
        self.assertIn('def dispatch_stage_previs(', service)


if __name__ == '__main__':
    unittest.main()
