from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import ROOT

from tests.architecture._scan import module_name, parse, production_files_recursive


_REMOVE_CALLS = frozenset({'os.remove', 'os.unlink', 'os.rmdir', 'os.removedirs', 'shutil.rmtree'})
_AUTHORITIES = frozenset({'storage_maintenance', 'asset_batch_lifecycle', 'storyboard_lifecycle', 'file_cache'})
# 开发／维护脚本（程序/scripts/）不是用户可见删除路径；产品删除仍须经生命周期网关。
_DEV_SCRIPT_PARTS = frozenset({'scripts'})


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)
        return f'{parent}.{node.attr}' if parent else None
    return None


class DeletionGatewayTests(unittest.TestCase):
    def test_production_deletion_calls_are_lifecycle_owned(self) -> None:
        """用户文件删除只能经生命周期网关；UI 与业务模块不得绕过。"""
        violations = []
        for path in production_files_recursive():
            if _DEV_SCRIPT_PARTS & set(path.relative_to(ROOT).parts):
                continue
            if module_name(path) in _AUTHORITIES:
                continue
            for node in ast.walk(parse(path)):
                if isinstance(node, ast.Call) and _dotted_name(node.func) in _REMOVE_CALLS:
                    violations.append(f'{path.name}:{node.lineno} {_dotted_name(node.func)}')
        self.assertEqual(violations, [], '\n'.join(violations))
