"""跳过测试的卫生契约：源码、原因常量和台账必须同步。"""

import ast
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "tests"
LEDGER = ROOT / "维护记录" / "skip台账.json"
REASONS = TESTS / "skip_reasons.py"
ALLOWED_KINDS = {"平台限制", "缺外部程序", "需真实凭据", "需实机复验", "待修复缺陷"}


def _reason_constants():
    tree = ast.parse(REASONS.read_text(encoding="utf-8"), filename=str(REASONS))
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                values[node.targets[0].id] = node.value.value
    return values


def _skip_reason_argument(node, decorator=False):
    """返回 skip API 的理由参数；不是 skip 调用则返回 None。"""
    name = node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id if isinstance(node.func, ast.Name) else ""
    if name == "skipTest":
        return node.args[0] if node.args else None
    if name in {"skipIf", "skipUnless"}:
        return node.args[1] if len(node.args) > 1 else None
    if decorator and name == "skip":
        return node.args[0] if node.args else None
    return None


class _SkipCollector(ast.NodeVisitor):
    def __init__(self, relative_path, constants):
        self.relative_path = relative_path
        self.constants = constants
        self.class_name = ""
        self.function_name = ""
        self.ordinal = {}
        self.rows = []

    def visit_ClassDef(self, node):
        previous = self.class_name
        self.class_name = node.name
        self.generic_visit(node)
        self.class_name = previous

    def visit_FunctionDef(self, node):
        previous = self.function_name
        self.function_name = node.name
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call):
                self._record(decorator, decorator=True)
        self.generic_visit(node)
        self.function_name = previous

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node):
        self._record(node)
        self.generic_visit(node)

    def _record(self, node, decorator=False):
        argument = _skip_reason_argument(node, decorator=decorator)
        if argument is None:
            return
        names = [part.id for part in ast.walk(argument) if isinstance(part, ast.Name) and part.id in self.constants]
        if len(names) != 1:
            raise AssertionError(f"{self.relative_path}:{node.lineno} 的 skip 必须引用一个模块级原因常量")
        test = ".".join(part for part in (self.class_name, self.function_name) if part) or "<module>"
        key = (test,)
        self.ordinal[key] = self.ordinal.get(key, 0) + 1
        constant = names[0]
        value = self.constants[constant]
        kind, separator, recovery = value.partition("：")
        if kind not in ALLOWED_KINDS or not separator or "应恢复" not in recovery:
            raise AssertionError(f"{self.relative_path}:{node.lineno} 的原因常量不含有效类别和恢复条件")
        self.rows.append({
            "file": self.relative_path,
            "test": test,
            "ordinal": self.ordinal[key],
            "kind": kind,
            "reason_constant": constant,
        })


def _source_rows():
    constants = _reason_constants()
    rows = []
    for path in sorted(TESTS.rglob("*.py")):
        if path == REASONS:
            continue
        collector = _SkipCollector(path.relative_to(ROOT).as_posix(), constants)
        collector.visit(ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
        rows.extend(collector.rows)
    return rows


class SkipHygieneTests(unittest.TestCase):
    def test_every_skip_has_a_reason_constant_with_a_recovery_condition(self):
        rows = _source_rows()
        self.assertGreater(len(rows), 0, "扫描集合不能为空，否则卫生门禁没有意义")

    def test_ledger_and_source_skip_sets_are_bidirectionally_equal(self):
        source = _source_rows()
        payload = json.loads(LEDGER.read_text(encoding="utf-8"))
        ledger = payload.get("entries", [])
        self.assertEqual(len(ledger), len(source), "台账不能多记或漏记 skip")
        source_by_key = {(row["file"], row["test"], row["ordinal"]): row for row in source}
        ledger_by_key = {(row.get("file"), row.get("test"), row.get("ordinal")): row for row in ledger}
        self.assertEqual(set(ledger_by_key), set(source_by_key), "台账与源码 skip 集合必须双向相等")
        for key, source_row in source_by_key.items():
            ledger_row = ledger_by_key[key]
            self.assertEqual(ledger_row.get("kind"), source_row["kind"], key)
            self.assertEqual(ledger_row.get("reason_constant"), source_row["reason_constant"], key)
            self.assertTrue(ledger_row.get("reason"), f"{key} 缺少可读原因")
            self.assertIn("应恢复", ledger_row["reason"], f"{key} 缺少恢复条件")

    def test_defect_skips_have_a_live_round_or_defect_ledger_reference(self):
        payload = json.loads(LEDGER.read_text(encoding="utf-8"))
        defect_ledger = ROOT / "维护记录" / "缺陷台账_20261001.md"
        defect_text = defect_ledger.read_text(encoding="utf-8") if defect_ledger.exists() else ""
        task_text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in (ROOT / "tasks_round").rglob("tasks_round_*_result.md"))
        for row in payload.get("entries", []):
            if row.get("kind") != "待修复缺陷":
                continue
            reference = row.get("reference", "")
            self.assertRegex(reference, r"(?:R\d+|缺陷台账)", f"{row} 的待修复缺陷缺少引用")
            self.assertTrue(reference in defect_text or reference in task_text, f"{row} 的待修复缺陷引用已失效")


if __name__ == "__main__":
    unittest.main()
