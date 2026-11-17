"""确认门禁的正式 JSON 读取走缓存、写入只由 L3 注入。"""
import ast
import os
import unittest
from pathlib import Path
from tests.architecture._scan import entity_file, stage_execution_source

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class ConfirmGatesJsonBoundaryTests(unittest.TestCase):
    def test_confirmations_use_cache_and_recording_accepts_l3_publisher(self):
        path = os.path.join(ROOT, 'domain/confirm_gates.py')
        with open(path, encoding='utf-8') as handle:
            source = handle.read()
        self.assertIn('from file_cache import read_json', source)
        self.assertIn('data = read_json(path)', source)
        self.assertNotIn('from agent.core import save', source)
        tree = ast.parse(source)
        methods = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        for name in ('record', 'forget'):
            self.assertIn('publish', [argument.arg for argument in methods[name].args.kwonlyargs])
            calls = [node for node in ast.walk(methods[name]) if isinstance(node, ast.Call)]
            self.assertTrue(any(isinstance(node.func, ast.Name) and node.func.id == 'publish' for node in calls))
        self.assertNotIn('json.loads(path.read_text(', source)

    def test_l4_confirmation_writes_delegate_to_l3(self):
        # R1622：门禁方法迁到 desktop_automation_tick（AutomationTickMixin），委托关系随之迁址。
        l4 = '\n'.join(entity_file(Path(name).stem).read_text(encoding='utf-8')
                       for name in ('desktop.py', 'desktop_automation_tick.py'))
        self.assertIn('from stage_execution_service import record_stage_confirmation', l4)
        self.assertNotIn('from confirm_gates import record', l4)
        service = stage_execution_source()
        self.assertIn('def record_stage_confirmation(', service)
        self.assertIn("publish=confirm_gates_gateway()['publish_json']", service)


if __name__ == '__main__':
    unittest.main()
