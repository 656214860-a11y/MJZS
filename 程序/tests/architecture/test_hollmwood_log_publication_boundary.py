"""四角色协作日志必须由 L3 编排器注入发布能力。"""
import ast
import unittest

from tests.architecture._scan import ROOT, parse


class HollmwoodLogPublicationBoundaryTests(unittest.TestCase):
    def test_l2_log_writer_requires_l3_publisher(self):
        roles = parse(ROOT / 'hollmwood_roles.py')
        imports = [name.name for node in roles.body if isinstance(node, ast.ImportFrom)
                   and node.module == 'agent.core' for name in node.names]
        self.assertNotIn('save_text', imports)
        functions = {node.name: node for node in roles.body if isinstance(node, ast.FunctionDef)}
        self.assertIn('publish', [arg.arg for arg in functions['_write_log'].args.kwonlyargs])
        self.assertIn('publish_log', [arg.arg for arg in functions['run'].args.kwonlyargs])
        self.assertIn('_hollmwood_result', [item.id for item in functions['run'].decorator_list
                                             if isinstance(item, ast.Name)])

        writing = parse(ROOT / 'writing_api.py')
        writing_functions = {node.name: node for node in writing.body if isinstance(node, ast.FunctionDef)}
        self.assertIn('hollmwood_gateway', writing_functions)
        reply = writing_functions['_hollmwood_reply']
        calls = [node for node in ast.walk(reply) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute) and node.func.attr == 'run']
        self.assertEqual(1, len(calls))
        self.assertTrue(any(keyword.arg == 'publish_log' for keyword in calls[0].keywords))
