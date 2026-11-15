from __future__ import annotations
import ast
import unittest
from tests.architecture._scan import module_name, parse, module_scan_files

# This guard owns *workflow-stage directory* layout.  Generic data filenames
# are intentionally excluded: ``assets.json`` and ``config.json`` are domain
# records, and their schemas belong to their respective contracts rather than
# to stage-path authority.
_PATH_MARKERS = ("writing/", "writing\\", "episode/", "episode\\", "storyboard/", "storyboard\\")
_WHITELIST = frozenset({"stage_layout", "storyboard_paths", "script_contract", "asset_contract", "model_pool"})


def _is_path_literal(node: ast.Constant, parents: dict[ast.AST, ast.AST]) -> bool:
    """Return true only when a matched string is used as a filesystem segment.

    Prompts and user-facing help legitimately mention names such as
    ``assets.json``.  The former broad scan treated those explanations as path
    writes, which made the architecture gate noisy and hid the actual
    violations.  This intentionally recognises only common ``pathlib``
    construction operations.
    """
    parent = parents.get(node)
    if isinstance(parent, ast.BinOp) and isinstance(parent.op, ast.Div):
        return True
    if not isinstance(parent, ast.Call):
        return False
    func = parent.func
    if isinstance(func, ast.Name) and func.id == "Path":
        return True
    return isinstance(func, ast.Attribute) and func.attr in {
        "glob", "rglob", "joinpath", "with_name", "with_suffix",
    }

class PathAuthorityTests(unittest.TestCase):
    def test_path_rules_are_owned_by_authority_modules(self) -> None:
        violations: list[str] = []
        for path in module_scan_files():
            if module_name(path) in _WHITELIST:
                continue
            tree = parse(path)
            parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
            for node in ast.walk(tree):
                if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                    continue
                if not _is_path_literal(node, parents):
                    continue
                normalized = node.value.replace("\\\\", "/")
                if any(marker in normalized for marker in _PATH_MARKERS):
                    violations.append(f"{path.name}:{node.lineno} {node.value!r}")
        if violations:
            self.fail("发现非路径权威模块中的工作流路径字面量：\n" + "\n".join(violations[:80])
                      + (f"\n... 另有 {len(violations) - 80} 处" if len(violations) > 80 else ""))
