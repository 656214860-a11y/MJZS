# -*- coding: utf-8 -*-
"""创意附档归档只能经 L3 发布器写入项目阶段。"""
import ast
import os
import unittest
import io
from tests.architecture._scan import stage_execution_source

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class IdeaAttachmentPublicationBoundaryTests(unittest.TestCase):
    def test_l2_store_requires_injected_publisher_without_direct_write(self):
        path = os.path.join(ROOT, 'domain/idea_attachments.py')
        with open(path, encoding='utf-8') as handle:
            tree = ast.parse(handle.read())
        store = next(node for node in tree.body
                     if isinstance(node, ast.FunctionDef) and node.name == 'store')
        calls = {getattr(node.func, 'id', '') for node in ast.walk(store)
                 if isinstance(node, ast.Call)}
        self.assertIn('publish', calls)
        self.assertNotIn('save_text', calls)

    def test_l3_injects_stage_text_publisher_and_controller_uses_l3(self):
        with io.StringIO(stage_execution_source()) as handle:
            source = handle.read()
        self.assertIn('def archive_idea_attachments(', source)
        self.assertIn('def stage_idea_attachment_reference(', source)
        self.assertIn('publish_stage_text(', source)
        with open(os.path.join(ROOT, 'idea_chat_controller.py'), encoding='utf-8') as handle:
            controller = handle.read()
        self.assertIn('archive_idea_attachments(root, selected)', controller)
        self.assertNotIn('idea_attachments.store(root, selected)', controller)
        self.assertIn('stage_idea_attachment_reference(project, value, self.attachment_paths)', controller)


if __name__ == '__main__':
    unittest.main()
