"""分镜定稿 JSON 必须经受控的双文件发布服务。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import ROOT, parse


class FinalBundleBoundaryTests(unittest.TestCase):
    def test_finalizer_delegates_json_publication_to_storage_service(self) -> None:
        tree = parse(ROOT / 'storyboard_final.py')
        imported = {
            alias.name for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module == 'storyboard_storage'
            for alias in node.names
        }
        self.assertNotIn('publish_final_bundle', imported)
        stage = parse(ROOT / 'stage_execution_service.py')
        self.assertTrue(any(isinstance(node, ast.FunctionDef)
                            and node.name == 'publish_final_storyboard_bundle'
                            for node in ast.walk(stage)))
        storage = (ROOT / 'storyboard_storage.py').read_text(encoding='utf-8')
        self.assertIn('def _require_gateway', storage)
        self.assertNotIn('from agent.core import read, save, save_bytes', storage)
        direct_writers = [
            node.lineno for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in {'save', 'save_bytes', 'save_text', 'write_text', 'write_bytes'}
        ]
        self.assertEqual(
            direct_writers, [],
            '分镜定稿 JSON 只能由 storyboard_storage.publish_final_bundle() 发布：'
            + str(direct_writers),
        )
