"""首迁失败反馈必须经过统一通知分发器。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import ROOT, parse


class NotificationBoundaryTests(unittest.TestCase):
    def test_desktop_safe_uses_the_notification_dispatcher(self):
        tree = parse(ROOT / "desktop.py")
        method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                      and node.name == "safe")
        messagebox_errors = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                             and isinstance(node.func, ast.Attribute)
                             and isinstance(node.func.value, ast.Name)
                             and node.func.value.id == "messagebox"
                             and node.func.attr == "showerror"]
        notifier_errors = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                           and isinstance(node.func, ast.Attribute)
                           and isinstance(node.func.value, ast.Attribute)
                           and node.func.value.attr == "notifier"
                           and node.func.attr == "error"]
        self.assertEqual(messagebox_errors, [], "首迁错误链不得退回裸 messagebox")
        self.assertEqual(len(notifier_errors), 1, "Desktop.safe 必须经统一通知入口")

    def test_desktop_display_notifications_use_dispatcher(self):
        tree = parse(ROOT / "desktop.py")
        direct = [node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute)
                  and isinstance(node.func.value, ast.Name)
                  and node.func.value.id == 'messagebox'
                  and node.func.attr in {'showerror', 'showwarning', 'showinfo'}]
        self.assertEqual(direct, [], 'Desktop 的展示型通知必须经 NotificationDispatcher')

    def test_business_pages_have_no_direct_display_messagebox_calls(self):
        forbidden = []
        for path in ROOT.rglob('*.py'):
            if 'tests' in path.parts or path.name == 'ui_widgets.py':
                continue
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == 'messagebox'
                        and node.func.attr in {'showerror', 'showwarning', 'showinfo'}):
                    forbidden.append('%s:%s' % (path.name, node.lineno))
        self.assertEqual(forbidden, [], '业务页面展示型通知必须经 NotificationDispatcher')
