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
