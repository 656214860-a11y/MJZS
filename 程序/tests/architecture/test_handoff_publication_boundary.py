# -*- coding: utf-8 -*-
"""剪映交接包的可见成果发布只能由服务层负责。"""
import ast
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _method(tree, cls, name):
    node = next(item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == cls)
    return next(item for item in node.body if isinstance(item, ast.FunctionDef) and item.name == name)


class HandoffPublicationBoundaryTests(unittest.TestCase):
    def test_desktop_delegates_handoff_bundle_publication(self):
        with open(os.path.join(ROOT, 'desktop.py'), encoding='utf-8') as handle:
            text = handle.read()
        source = ast.get_source_segment(text, _method(ast.parse(text), 'Desktop', 'handoff'))
        self.assertIn('publish_bundle(', source)
        self.assertNotIn("镜头顺序.json", source)

    def test_service_owns_manifest_and_instruction_writes(self):
        with open(os.path.join(ROOT, 'handoff_service.py'), encoding='utf-8') as handle:
            source = handle.read()
        self.assertIn('def publish_bundle(', source)
        self.assertIn("镜头顺序.json", source)
        self.assertIn("导入剪映说明.txt", source)
        self.assertNotIn('save_text', source)
        self.assertNotIn('save_bytes', source)
        self.assertNotIn('shutil.copy2', source)

    def test_l3_injects_handoff_bundle_publisher(self):
        with open(os.path.join(ROOT, 'desktop.py'), encoding='utf-8') as handle:
            text = handle.read()
        source = ast.get_source_segment(text, _method(ast.parse(text), 'Desktop', 'handoff'))
        self.assertIn('publish=publish_handoff_bundle', source)
        with open(os.path.join(ROOT, 'stage_execution_service.py'), encoding='utf-8') as handle:
            service = handle.read()
        self.assertIn('def publish_handoff_bundle(', service)
        self.assertIn('publish_stage_bundle(payload', service)

    def test_desktop_delegates_automatic_handoff_marker_to_l3_publisher(self):
        with open(os.path.join(ROOT, 'desktop.py'), encoding='utf-8') as handle:
            method = _method(ast.parse(handle.read()), 'Desktop', 'poll_auto_handoff')
        calls = [node for node in ast.walk(method) if isinstance(node, ast.Call) and getattr(node.func, 'id', '') == 'save_automatic_handoff_marker']
        self.assertEqual(len(calls), 1)
        with open(os.path.join(ROOT, 'handoff_service.py'), encoding='utf-8') as handle:
            service = ast.parse(handle.read())
        marker = next(node for node in service.body if isinstance(node, ast.FunctionDef) and node.name == 'save_automatic_handoff_marker')
        calls = {getattr(node.func, 'id', '') for node in ast.walk(marker) if isinstance(node, ast.Call)}
        self.assertIn('publish', calls)
        self.assertNotIn('save', calls)
        with open(os.path.join(ROOT, 'stage_execution_service.py'), encoding='utf-8') as handle:
            source = handle.read()
        self.assertIn("write_dir(Path(project), 'edit')", source)
        self.assertIn('publish_stage_text(', source)


if __name__ == '__main__': unittest.main()
