"""物理删除只能留在回收服务、缓存或明确的 tempfile 清理中。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._layers import LAYERS
from tests.architecture._scan import module_name, parse, module_scan_files


_REMOVE_CALLS = frozenset({'os.remove', 'os.unlink', 'shutil.rmtree'})
_AUTHORITIES = frozenset({
    'storage_maintenance', 'file_cache', 'log_maintenance', 'workspace_maintenance',
    # R3623/I14：metrics 的 raw-*.jsonl 是程序自有缓存，任务书规定 14 天保留期，
    # 清理只删本模块写入的命名文件（与 log_maintenance 同类受控清理）。
    'metrics',
    # R3246 轮 2：agent/ 入分层包扫描后登记。agent.core／agent.publication 是
    # 原子写与发布事务权威（登记名 core／publication），其 unlink 只清理自身
    # temporary_path 暂存与 journal 残件，与 file_cache 同级可信。
    'core', 'publication',
})


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
        for path in module_scan_files():
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
