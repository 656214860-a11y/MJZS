from __future__ import annotations
import unittest
from tests.architecture._scan import imports_of, module_name, production_files

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

class CircularImportTests(unittest.TestCase):
    def test_root_production_modules_have_no_import_cycle(self) -> None:
        paths = production_files()
        names = {module_name(path) for path in paths}
        graph = {module_name(path): {target for target in imports_of(path) if target in names} for path in paths}
        cycles = [component for component in _tarjan(graph) if len(component) > 1]
        cycles.extend([[node] for node, edges in graph.items() if node in edges])
        if cycles:
            self.fail("发现根目录模块循环依赖：\n" + "\n".join(
                " -> ".join(cycle + [cycle[0]]) for cycle in cycles))


# R1777 审计：常量字符串的 import_module／__import__ 曾绕开上面的静态环检测。
# 下面 4 个环是并入动态导入后才暴露的存量，只许减少、不许新增；拆掉一个就删一行。
KNOWN_DYNAMIC_CYCLES = (
    ("local_video", "skill_orchestrator", "skill_tools", "stage_execution_service"),
    ("script_contract", "script_skill_report"),
    ("stage_models", "workflow_settings"),
    ("white_model", "white_model_ref"),
)


class DynamicImportCycleRatchetTests(unittest.TestCase):
    def test_dynamic_imports_do_not_add_import_cycles(self) -> None:
        from tests.architecture._scan import imports_with_dynamic_of
        paths = production_files()
        names = {module_name(path) for path in paths}
        graph = {module_name(path): {target for target in imports_with_dynamic_of(path)
                                     if target in names and target != module_name(path)} for path in paths}
        found = {tuple(component) for component in _tarjan(graph) if len(component) > 1}
        known = set(KNOWN_DYNAMIC_CYCLES)
        self.assertEqual(sorted(found - known), [],
                         "并入 import_module／__import__ 后出现新的循环依赖，请拆环而不是登记：")
        self.assertEqual(sorted(known - found), [],
                         "下列环已不存在，请从 KNOWN_DYNAMIC_CYCLES 删除（棘轮只降不升）：")
