# -*- coding: utf-8 -*-
"""剪辑成片须在临时编码、核验后才发布并登记成果索引。"""
import ast
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _method(tree, cls, name):
    node = next(item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == cls)
    return next(item for item in node.body if isinstance(item, ast.FunctionDef) and item.name == name)


def _calls(node):
    return {call.func.id if isinstance(call.func, ast.Name) else call.func.attr
            for call in ast.walk(node) if isinstance(call, ast.Call)
            and isinstance(call.func, (ast.Name, ast.Attribute))}


class EditPublicationBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, 'engine.py'), encoding='utf-8') as handle:
            cls.tree = ast.parse(handle.read())

    def test_encode_uses_temporary_master_and_delegates_bundle_publication(self):
        calls = _calls(_method(self.tree, 'Studio', '_encode'))
        self.assertTrue({'temporary_path', 'replace', 'publish_edit_bundle'} <= calls)

    def test_bundle_publication_requires_master_and_writes_both_indexes(self):
        calls = _calls(_method(self.tree, 'Studio', 'publish_edit_bundle'))
        self.assertIn('is_file', calls)
        self.assertIn('is_relative_to', calls)
        self.assertIn('save', calls)

    def test_desktop_delegates_checklist_publication_to_l3(self):
        with open(os.path.join(ROOT, 'desktop.py'), encoding='utf-8') as handle:
            desktop = ast.parse(handle.read())
        calls = [node for node in ast.walk(desktop) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == 'save_stage_editing_checklist']
        self.assertEqual(len(calls), 1)
        with open(os.path.join(ROOT, 'edit_service.py'), encoding='utf-8') as handle:
            service = ast.parse(handle.read())
        function = next(node for node in service.body
                        if isinstance(node, ast.FunctionDef) and node.name == 'save_editing_checklist')
        self.assertIn('publish', _calls(function))
        self.assertNotIn('save_text', _calls(function))
        with open(os.path.join(ROOT, 'stage_execution_service.py'), encoding='utf-8') as handle:
            source = handle.read()
        self.assertIn('def save_stage_editing_checklist(', source)
        self.assertIn('allow_empty=True', source)

    def test_desktop_delegates_automatic_assemble_marker_to_l3_publisher(self):
        # R1480：自动粗剪轮询已原样迁到 desktop_auto_flows（断言未动，只改被检文件）。
        with open(os.path.join(ROOT, 'desktop_auto_flows.py'), encoding='utf-8') as handle:
            desktop = ast.parse(handle.read())
        calls = [node for node in ast.walk(desktop) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == 'save_automatic_assemble_marker']
        self.assertEqual(len(calls), 1)
        with open(os.path.join(ROOT, 'edit_service.py'), encoding='utf-8') as handle:
            service = ast.parse(handle.read())
        function = next(node for node in service.body
                        if isinstance(node, ast.FunctionDef) and node.name == 'save_automatic_assemble_marker')
        self.assertIn('publish', _calls(function))
        self.assertNotIn('save', _calls(function))
        with open(os.path.join(ROOT, 'stage_execution_service.py'), encoding='utf-8') as handle:
            source = handle.read()
        self.assertIn("write_dir(Path(project), 'edit')", source)
        self.assertIn('publish_stage_text(', source)


if __name__ == '__main__': unittest.main()
