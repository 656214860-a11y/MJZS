"""物理删除只能留在回收服务、缓存或明确的 tempfile 清理中。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._layers import LAYERS
from tests.architecture._scan import module_name, parse, production_files


_REMOVE_CALLS = frozenset({'os.remove', 'os.unlink', 'shutil.rmtree'})
_AUTHORITIES = frozenset({'storage_maintenance', 'file_cache', 'log_maintenance'})


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)
        return f'{parent}.{node.attr}' if parent else None
    return None


def _is_tempfile_cleanup(path, node: ast.Call) -> bool:
    """仅放行直接以 tempfile 前缀构造的临时文件清理。"""
    line = path.read_text(encoding='utf-8').splitlines()[node.lineno - 1]
    return 'tempfile.' in line


class RecycleServiceTests(unittest.TestCase):
    def test_physical_removal_is_recycle_or_tempfile_owned(self) -> None:
        """非授权生产模块的删除调用必须提供文件和行号。"""
        violations = []
        for path in production_files():
            if module_name(path) in _AUTHORITIES:
                continue
            layer = LAYERS.get(module_name(path), '未登记')
            for node in ast.walk(parse(path)):
                if not isinstance(node, ast.Call):
                    continue
                called = _dotted_name(node.func)
                is_path_unlink = (
                    isinstance(node.func, ast.Attribute) and node.func.attr == 'unlink'
                )
                if (called not in _REMOVE_CALLS and not is_path_unlink) or _is_tempfile_cleanup(path, node):
                    continue
                violations.append(f'{path.name}:{node.lineno} {called} (L{layer})')
        self.assertEqual(
            violations, [],
            '物理删除仅允许 storage_maintenance、file_cache 或 tempfile 清理:\n'
            + '\n'.join(violations),
        )
