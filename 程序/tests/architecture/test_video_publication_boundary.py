# -*- coding: utf-8 -*-
"""视频成果索引只能在集中发布入口中写入。"""
import ast
import os
import unittest

from tests.architecture._scan import entity_file

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _method(tree, cls, name):
    node = next(item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == cls)
    return next(item for item in node.body if isinstance(item, ast.FunctionDef) and item.name == name)


def _calls(node):
    return {call.func.attr for call in ast.walk(node) if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)}


class VideoPublicationBoundaryTests(unittest.TestCase):
    def test_cloud_and_local_poll_delegate_downloaded_state_publication(self):
        with open(str(entity_file('engine')), encoding='utf-8') as handle: cloud = ast.parse(handle.read())
        with open(os.path.join(ROOT, 'local_video.py'), encoding='utf-8') as handle: local = ast.parse(handle.read())
        self.assertIn('publish_downloaded_video', _calls(_method(cloud, 'Studio', 'poll')))
        self.assertIn('publish_downloaded_video', _calls(_method(local, 'LocalStudio', 'poll')))


if __name__ == '__main__': unittest.main()
