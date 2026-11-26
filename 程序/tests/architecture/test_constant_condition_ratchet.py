"""恒真／恒假条件棘轮（C03）：本仓自有 .py 里不许新增布尔常量参与的条件。

命中形态：
- 布尔运算里出现 ``True``/``False`` 字面量：``x or True``、``x and False``、``True and y`` 等；
- ``if``／``while``／条件表达式的判定本身是常量：``if True:``、``if 0:``、``while False:``、``a if 1 else b``。

排除：``while True:`` 是常见的「无限循环＋内部 break/return」写法，意图明确、不是笔误，不计。
扫描范围沿用 ``_scan.production_files_recursive()``（同一份 EXCLUDED_PARTS），不另造排除集合。
存量命中登记在 ``ALLOWED``（键 = 相对路径与源码片段，值 = 理由），只减不增：
登记项消失也会报错，提示把它从白名单删掉。
"""
from __future__ import annotations

import ast
import unittest
from collections import Counter

from tests.architecture._scan import ROOT, production_files_recursive

# (相对路径, 表达式源码) -> 理由
ALLOWED: dict[tuple[str, str], str] = {
    ("scripts/concurrency_report.py", "value or True"):
        "git worktree --porcelain 的无值字段（bare/detached/locked/prunable）是旗标，"
        "空值记 True 表示该旗标存在；`or True` 只作用于空串，非恒真笔误。",
}


def _is_const(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and not isinstance(node.value, (str, bytes))


def _hits_in(tree: ast.AST) -> list[str]:
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.BoolOp):
            if any(isinstance(v, ast.Constant) and isinstance(v.value, bool) for v in node.values):
                hits.append(ast.unparse(node))
        elif isinstance(node, (ast.If, ast.While, ast.IfExp)) and _is_const(node.test):
            if isinstance(node, ast.While) and node.test.value is True:
                continue  # while True: 合法无限循环，见模块说明
            kind = {ast.If: "if", ast.While: "while", ast.IfExp: "ifexp"}[type(node)]
            hits.append(f"{kind} {ast.unparse(node.test)}")
    return hits


def scan() -> Counter:
    found: Counter = Counter()
    for path in production_files_recursive():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        rel = path.relative_to(ROOT).as_posix()
        for snippet in _hits_in(tree):
            found[(rel, snippet)] += 1
    return found


class ConstantConditionRatchetTests(unittest.TestCase):
    def test_detector_catches_known_forms(self) -> None:
        src = ("a = x or True\nb = y and False\nif True:\n    pass\n"
               "while False:\n    pass\nc = 1 if 0 else 2\nwhile True:\n    break\n")
        self.assertEqual(sorted(_hits_in(ast.parse(src))),
                         sorted(["x or True", "y and False", "if True", "while False", "ifexp 0"]))

    def test_no_new_constant_conditions(self) -> None:
        found = scan()
        new = sorted(key for key in found if key not in ALLOWED)
        self.assertEqual(new, [], "新增恒真/恒假条件：修掉该表达式，确属有意才登记 ALLOWED 并写理由")

    def test_allowlist_only_shrinks(self) -> None:
        found = scan()
        stale = sorted(key for key in ALLOWED if key not in found)
        self.assertEqual(stale, [], "白名单条目已不存在：从 ALLOWED 删除（只减不增）")
        for key, reason in ALLOWED.items():
            self.assertTrue(reason.strip(), f"白名单条目缺理由：{key}")


if __name__ == "__main__":
    unittest.main()
