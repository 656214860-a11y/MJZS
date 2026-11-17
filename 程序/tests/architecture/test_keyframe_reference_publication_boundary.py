# -*- coding: utf-8 -*-
"""首帧媒体发布与分镜关联更新必须经独立边界。"""
import ast
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _function(tree, name):
    return next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)


def _calls(node):
    return {call.func.id for call in ast.walk(node) if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)}


class KeyframeReferencePublicationBoundaryTests(unittest.TestCase):
    def test_register_delegates_reference_write_after_media_publish(self):
        path = os.path.join(ROOT, 'ui', 'keyframe_import.py')
        with open(path, encoding='utf-8') as handle: tree = ast.parse(handle.read(), path)
        register = _function(tree, 'register')
        reference = _function(tree, 'publish_frame_reference')
        self.assertIn('save_bytes_new', _calls(register))
        self.assertIn('publish_frame_reference', _calls(register))
        self.assertNotIn('save', _calls(register))
        self.assertIn('save', _calls(reference))


if __name__ == '__main__': unittest.main()
