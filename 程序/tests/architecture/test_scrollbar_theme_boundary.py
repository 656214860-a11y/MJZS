"""全局滚动条样式必须经 token 入口统一。"""
import ast
import unittest
from pathlib import Path


PROGRAM = Path(__file__).resolve().parents[2]


class ScrollbarThemeBoundaryTests(unittest.TestCase):
    def test_both_standard_scrollbar_orientations_use_shared_tokens_and_active_state(self):
        tree = ast.parse((PROGRAM / 'ui_theme.py').read_text(encoding='utf-8'))
        source = ast.unparse(tree)
        for token in ('SCROLLBAR_THUMB', 'SCROLLBAR_THUMB_ACTIVE', 'SCROLLBAR_TROUGH',
                      'SCROLLBAR_ARROW', 'SCROLLBAR_BORDER_WIDTH'):
            self.assertIn(token, source)
        self.assertIn("'Vertical.TScrollbar'", source)
        self.assertIn("'Horizontal.TScrollbar'", source)
        self.assertIn("('active', SCROLLBAR_THUMB_ACTIVE)", source)

    def test_production_scrollbars_do_not_override_global_style(self):
        violations = []
        for path in PROGRAM.rglob('*.py'):
            relative = path.relative_to(PROGRAM)
            if (path.name in {'ui_theme.py', 'ui_widgets.py'} or path.name.startswith('test')
                    or 'tests' in relative.parts or 'tasks_round' in relative.parts
                    or '维护记录' in relative.parts):
                continue
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == 'ttk' and node.func.attr == 'Scrollbar'):
                    continue
                if any(keyword.arg == 'style' for keyword in node.keywords):
                    violations.append(f'{relative}:{node.lineno}')
        self.assertEqual(violations, [],
                         '业务滚动条必须使用全局 TScrollbar 样式：' + '; '.join(violations))
