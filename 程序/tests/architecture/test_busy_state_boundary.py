"""主后台任务的忙碌态必须成对经过 BusyState。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import ROOT, parse


class BusyStateBoundaryTests(unittest.TestCase):
    def test_async_lifecycle_uses_busy_state_for_start_and_finish(self):
        tree = parse(ROOT / 'desktop.py')
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute)
                 and isinstance(node.func.value, ast.Attribute)
                 and node.func.value.attr == 'busy_state'
                 and node.func.attr == 'set_busy']
        values = [node.args[0].value for node in calls
                  if node.args and isinstance(node.args[0], ast.Constant)
                  and isinstance(node.args[0].value, bool)]
        self.assertIn(True, values)
        self.assertGreaterEqual(values.count(False), 2,
                                '完成和中断都必须经 BusyState 恢复界面')

    def test_interrupt_does_not_stop_the_progressbar_directly(self):
        tree = parse(ROOT / 'desktop.py')
        method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                      and node.name == 'interrupt_script_agent')
        stops = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute)
                 and node.func.attr == 'stop'
                 and isinstance(node.func.value, ast.Attribute)
                 and node.func.value.attr == 'progress']
        self.assertEqual(stops, [])
