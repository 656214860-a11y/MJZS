"""结构剧本只能由发布契约服务写入并在成功后记录血缘。"""
from __future__ import annotations

from tests.architecture._scan import parse_desktop  # R1505：Desktop 方法分布在 desktop.py 与迁出的 Mixin 模块
import ast
import unittest

from tests.architecture._scan import ROOT, parse
from tests.architecture._layers import LAYERS


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError('缺少函数：' + name)


class StructuredScriptWriteBoundaryTests(unittest.TestCase):
    def test_desktop_delegates_natural_script_edits_to_contract(self) -> None:
        desktop = parse_desktop()
        calls = [node for node in ast.walk(desktop) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == 'save_natural_script']
        self.assertEqual(len(calls), 1, '结构页手改自然剧本必须委托 script_contract')
        function = _function(parse(ROOT / 'contract' / 'script_contract.py'), 'save_natural_script')
        saves = [node.lineno for node in ast.walk(function) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == 'save_text']
        self.assertEqual(len(saves), 1, '自然剧本服务必须使用原子 save_text')

    def test_executor_delegates_to_contract_and_contract_records_after_save(self) -> None:
        """L3 不直接发布结构稿，L0 服务须在成功保存后才建立血缘。"""
        self.assertEqual(LAYERS['script_contract'], 0)
        self.assertEqual(LAYERS['stage_exec'], 3)
        executor = parse(ROOT / 'stage_exec.py')
        executor_calls = [
            node for node in ast.walk(executor)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == 'script_contract'
            and node.func.attr == 'write_structured_script'
        ]
        self.assertTrue(executor_calls, 'stage_exec 必须委托 script_contract.write_structured_script()')
        direct_writers = [
            node.lineno for node in ast.walk(executor)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in {'save', 'save_bytes', 'save_text', 'save_json', 'write_text', 'write_bytes'}
        ]
        self.assertEqual(direct_writers, [], 'stage_exec 不得直接发布结构剧本：' + str(direct_writers))

        publish = _function(parse(ROOT / 'contract' / 'script_contract.py'), 'write_structured_script')
        saves = [node.lineno for node in ast.walk(publish) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == 'save_text']
        records = [node.lineno for node in ast.walk(publish) if isinstance(node, ast.Call)
                   and isinstance(node.func, ast.Name) and node.func.id == 'record']
        self.assertEqual(len(saves), 1, '结构剧本必须由受控 save_text 发布')
        self.assertEqual(len(records), 1, '结构剧本发布后必须记录 artifact_lineage')
        self.assertLess(saves[0], records[0], '血缘记录必须晚于成功保存')
