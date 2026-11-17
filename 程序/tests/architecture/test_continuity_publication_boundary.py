"""连贯性清单的四份关联成果只能经同一发布包更新。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import entity_file, parse


class ContinuityPublicationBoundaryTests(unittest.TestCase):
    def test_write_delegates_to_bundle_publisher_without_direct_save(self) -> None:
        tree = parse(entity_file('continuity_ledger'))
        write = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'write')
        calls = [node for node in ast.walk(write) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
        self.assertEqual([node.func.id for node in calls], ['publish_bundle'])
