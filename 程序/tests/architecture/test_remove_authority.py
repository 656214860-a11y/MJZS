from __future__ import annotations
import ast
import unittest
from tests.architecture._scan import module_name, parse, production_files

_REMOVE_CALLS = frozenset({"os.remove", "os.unlink", "os.rmdir", "os.removedirs", "shutil.rmtree"})
_WHITELIST = frozenset({"storage_maintenance", "asset_batch_lifecycle", "storyboard_lifecycle", "file_cache"})

def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)
        return f"{parent}.{node.attr}" if parent else None
    return None

class RemoveAuthorityTests(unittest.TestCase):
    def test_file_removal_is_owned_by_lifecycle_modules(self) -> None:
        violations: list[str] = []
        for path in production_files():
            if module_name(path) in _WHITELIST:
                continue
            for node in ast.walk(parse(path)):
                if isinstance(node, ast.Call) and _dotted_name(node.func) in _REMOVE_CALLS:
                    violations.append(f"{path.name}:{node.lineno} {_dotted_name(node.func)}")
        if violations:
            self.fail("发现非删除权威模块直接删除文件：\n" + "\n".join(violations[:80])
                      + (f"\n... 另有 {len(violations) - 80} 处" if len(violations) > 80 else ""))
