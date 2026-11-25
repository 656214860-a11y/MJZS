"""C 卡边界守卫：L3 SKILL 编排器不得反向依赖 L4 UI 工具表。"""
import ast
import unittest

from tests.architecture._scan import ROOT, dynamic_import_rows, parse


class SkillOrchestratorBoundaryTests(unittest.TestCase):
    def test_skill_orchestrator_never_imports_ui_or_skill_tools(self):
        tree = parse(ROOT / 'orchestrator' / 'skill_orchestrator.py')
        offenders = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == 'ui' or alias.name.startswith('ui.') or alias.name == 'skill_tools':
                        offenders.append((node.lineno, alias.name))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                if module == 'ui' or module.startswith('ui.') or module == 'skill_tools':
                    offenders.append((node.lineno, module))
        self.assertEqual(offenders, [],
                         'L3 编排器只能消费注入的 ToolResult 执行器，不得导入 UI/工具表：%s' % offenders)

    def test_skill_orchestrator_never_dynamically_imports_ui_or_skill_tools(self):
        path = ROOT / 'orchestrator' / 'skill_orchestrator.py'
        offenders = [(line, name) for line, name in dynamic_import_rows(path)
                     if name in ('ui', 'skill_tools')]
        self.assertEqual(offenders, [],
                         'L3 编排器不得用字面量动态导入绕过 UI/工具表边界：%s' % offenders)


if __name__ == '__main__':
    unittest.main()
