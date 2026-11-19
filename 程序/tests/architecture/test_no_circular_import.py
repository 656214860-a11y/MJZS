from __future__ import annotations
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from tests.architecture import _scan
from tests.architecture._scan import module_imports_with_dynamic_of, module_name, module_scan_files

def _tarjan(graph: dict[str, set[str]]) -> list[list[str]]:
    index, indexes, lowlinks = 0, {}, {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[list[str]] = []
    def visit(node: str) -> None:
        nonlocal index
        indexes[node] = lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        for target in sorted(graph[node]):
            if target not in indexes:
                visit(target)
                lowlinks[node] = min(lowlinks[node], lowlinks[target])
            elif target in on_stack:
                lowlinks[node] = min(lowlinks[node], indexes[target])
        if lowlinks[node] == indexes[node]:
            component: list[str] = []
            while True:
                member = stack.pop()
                on_stack.remove(member)
                component.append(member)
                if member == node:
                    break
            components.append(sorted(component))
    for node in sorted(graph):
        if node not in indexes:
            visit(node)
    return components

# R3246 轮 2（任务书 D2）：agent/ 并入分层包扫描后暴露的存量环，只许减少、不许新增；
# 拆掉一个就删一行。沿用同一个存量环，改用完整模块身份。
KNOWN_STATIC_CYCLES = frozenset({
    ("agent.core", "agent.publication", "infra.file_cache"),
})


class CircularImportTests(unittest.TestCase):
    def test_static_import_cycles_are_a_nonincreasing_baseline(self) -> None:
        files = {module_name(path, qualified=True): path for path in _scan.production_runtime_files()}
        rows = {name: tuple(_scan.resolved_module_import_rows(path, qualified=True))
                for name, path in files.items()}
        graph = {name: {target for _, target in imports if target in files}
                 for name, imports in rows.items()}
        found = {tuple(component) for component in _tarjan(graph) if len(component) > 1}
        found |= {(node,) for node, edges in graph.items() if node in edges}
        known = set(KNOWN_STATIC_CYCLES)
        unexpected = sorted(found - known)
        if unexpected:
            self.fail("生产静态导入出现新的循环依赖，请拆环而不是登记。\n" + "\n".join(
                f"{files[source].relative_to(_scan.ROOT).as_posix()}:{line}: {source} → {target}"
                for component in unexpected
                for source in component
                for line, target in sorted(set(rows[source]))
                if target in component
            ))
        self.assertEqual(sorted(known - found), [],
                         "下列静态环已不存在，请从 KNOWN_STATIC_CYCLES 删除（棘轮只降不升）：")


class ProductionCycleScannerTests(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(self.enterContext(TemporaryDirectory()))
        self.enterContext(patch.object(_scan, "ROOT", root))
        self.enterContext(patch(__name__ + ".KNOWN_STATIC_CYCLES", frozenset()))
        package = root / "sample"
        package.mkdir()
        (package / "__init__.py").touch()
        self.first = package / "first.py"
        self.second = package / "second.py"
        self.first.write_text("from sample import second\n", encoding="utf-8")
        self.second.write_text("from . import first\n", encoding="utf-8")
        paths = (package / "__init__.py", self.first, self.second)
        self.enterContext(patch.object(_scan, "production_runtime_files", return_value=paths))

    def test_rejects_package_and_relative_import_cycle(self) -> None:
        guard = CircularImportTests().test_static_import_cycles_are_a_nonincreasing_baseline
        with self.assertRaisesRegex(AssertionError, r"sample/first\.py:1: .*sample\.second"):
            guard()

    def test_accepts_one_way_package_dependency(self) -> None:
        self.second.write_text("VALUE = 1\n", encoding="utf-8")
        CircularImportTests().test_static_import_cycles_are_a_nonincreasing_baseline()


# R1777 审计：常量字符串的 import_module／__import__ 曾绕开上面的静态环检测。
# 下面是并入动态导入后才暴露的存量，只许减少、不许新增；拆掉一个就删一行。
# R3246 轮 2：agent/ 入图后 (white_model,white_model_ref) 二环被更大的
# keyframe_evidence→shot_assets→white_model_ref→white_model→stage_parallel 环吸收，
# 同时暴露出与静态环同源的 {core,file_cache,publication}；按实测重登。
KNOWN_DYNAMIC_CYCLES = (
    ("local_video", "skill_orchestrator", "skill_tools", "stage_execution_service"),
    ("stage_models", "workflow_settings"),
    ("core", "file_cache", "publication"),
    ("keyframe_evidence", "shot_assets", "stage_parallel", "white_model", "white_model_ref"),
)


class DynamicImportCycleRatchetTests(unittest.TestCase):
    def test_dynamic_imports_do_not_add_import_cycles(self) -> None:
        paths = module_scan_files()
        names = {module_name(path) for path in paths}
        graph = {module_name(path): {target for target in module_imports_with_dynamic_of(path)
                                     if target in names and target != module_name(path)} for path in paths}
        found = {tuple(component) for component in _tarjan(graph) if len(component) > 1}
        known = set(KNOWN_DYNAMIC_CYCLES)
        self.assertEqual(sorted(found - known), [],
                         "并入 import_module／__import__ 后出现新的循环依赖，请拆环而不是登记：")
        self.assertEqual(sorted(known - found), [],
                         "下列环已不存在，请从 KNOWN_DYNAMIC_CYCLES 删除（棘轮只降不升）：")
