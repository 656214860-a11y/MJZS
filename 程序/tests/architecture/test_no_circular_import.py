from __future__ import annotations
import unittest
from tests.architecture._scan import module_imports_of, module_imports_with_dynamic_of, module_name, module_scan_files

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
# 拆掉一个就删一行。{core,file_cache,publication} 是 agent.core／agent.publication 与
# file_cache 的存储层互导（多为函数级懒加载，静态口径仍成环），收口属专项轮次。
KNOWN_STATIC_CYCLES = frozenset({
    ("core", "file_cache", "publication"),
})


class CircularImportTests(unittest.TestCase):
    def test_static_import_cycles_are_a_nonincreasing_baseline(self) -> None:
        paths = module_scan_files()
        names = {module_name(path) for path in paths}
        graph = {module_name(path): {target for target in module_imports_of(path) if target in names} for path in paths}
        found = {tuple(component) for component in _tarjan(graph) if len(component) > 1}
        found |= {(node,) for node, edges in graph.items() if node in edges}
        known = set(KNOWN_STATIC_CYCLES)
        self.assertEqual(sorted(found - known), [],
                         "静态导入出现新的循环依赖，请拆环而不是登记：")
        self.assertEqual(sorted(known - found), [],
                         "下列静态环已不存在，请从 KNOWN_STATIC_CYCLES 删除（棘轮只降不升）：")


# R1777 审计：常量字符串的 import_module／__import__ 曾绕开上面的静态环检测。
# 下面是并入动态导入后才暴露的存量，只许减少、不许新增；拆掉一个就删一行。
# R3246 轮 2：agent/ 入图后 (white_model,white_model_ref) 二环被更大的
# keyframe_evidence→shot_assets→white_model_ref→white_model→stage_parallel 环吸收，
# 同时暴露出与静态环同源的 {core,file_cache,publication}；按实测重登。
KNOWN_DYNAMIC_CYCLES = (
    ("local_video", "skill_orchestrator", "skill_tools", "stage_execution_service"),
    ("script_contract", "script_skill_report"),
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
