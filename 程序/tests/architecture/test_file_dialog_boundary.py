"""首迁附件入口不得退回页面内直接文件选择。"""
from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class FileDialogBoundaryTests(unittest.TestCase):
    def test_idea_attachment_uses_unified_file_dialog(self):
        tree = ast.parse((ROOT / 'desktop.py').read_text(encoding='utf-8'))
        desktop = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Desktop')
        method = next(node for node in desktop.body if isinstance(node, ast.FunctionDef) and node.name == 'choose_idea_attachments')
        calls = [node for node in ast.walk(method) if isinstance(node, ast.Call)]
        attrs = [node.func.attr for node in calls if isinstance(node.func, ast.Attribute)]
        self.assertIn('open_files', attrs)
        self.assertNotIn('askopenfilenames', attrs)

    def test_desktop_has_no_direct_file_chooser_calls(self):
        tree = ast.parse((ROOT / 'desktop.py').read_text(encoding='utf-8'))
        forbidden = []
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == 'filedialog'):
                forbidden.append(node.func.attr)
        self.assertEqual(forbidden, [], 'Desktop 页面必须经 FileDialog 选择文件')

    def test_business_pages_have_no_direct_file_chooser_calls(self):
        forbidden = []
        for path in ROOT.rglob('*.py'):
            if 'tests' in path.parts or path.name == 'ui_dialogs.py':
                continue
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == 'filedialog'):
                    forbidden.append('%s:%s' % (path.name, node.lineno))
        self.assertEqual(forbidden, [], '业务页面不得直调 filedialog')
