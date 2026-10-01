"""手动创意成果必须由无界面创意服务发布。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import ROOT, parse


class ManualCreativePublicationBoundaryTests(unittest.TestCase):
    def test_desktop_delegates_manual_creative_publication(self) -> None:
        desktop = parse(ROOT / 'desktop.py')
        calls = [node for node in ast.walk(desktop) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute)
                 and isinstance(node.func.value, ast.Name)
                 and node.func.value.id == 'idea_chat'
                 and node.func.attr == 'save_manual_creative']
        self.assertEqual(len(calls), 1, '桌面层不得直接发布手动创意')
        reply_calls = [node for node in ast.walk(desktop) if isinstance(node, ast.Call)
                       and isinstance(node.func, ast.Attribute)
                       and isinstance(node.func.value, ast.Name)
                       and node.func.value.id == 'idea_chat'
                       and node.func.attr == 'save_reply']
        self.assertEqual(len(reply_calls), 1, '桌面层不得绕过模型创意的统一发布入口')
        for call in calls + reply_calls:
            self.assertTrue(any(item.arg == 'publish' for item in call.keywords),
                            '桌面必须向创意服务注入 L3 发布器')

        service = parse(ROOT / 'idea_chat.py')
        target = next(node for node in service.body
                      if isinstance(node, ast.FunctionDef) and node.name == 'save_manual_creative')
        names = {node.id for node in ast.walk(target) if isinstance(node, ast.Name)}
        self.assertIn('publish', names, 'L2 必须接收 L3 发布器')
        self.assertFalse({'save_text', 'save', 'mkdir'} & names,
                         'L2 不得直接创建目录或发布手动创意')
        execution = parse(ROOT / 'stage_execution_service.py')
        self.assertTrue(any(isinstance(node, ast.FunctionDef) and node.name == 'publish_idea_creative'
                            for node in execution.body), 'L3 必须承接创意成果发布')
