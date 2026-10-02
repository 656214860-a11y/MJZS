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

    def test_desktop_file_chooser_calls_do_not_increase(self):
        tree = ast.parse((ROOT / 'desktop.py').read_text(encoding='utf-8'))
        self.assertLessEqual(len(_direct_file_dialog_calls(tree)), LEGACY_FILE_DIALOG_MAX['desktop.py'],
                             'Desktop 历史直调 filedialog 数量只能下降')

    def test_business_pages_have_no_direct_file_chooser_calls(self):
        actual = {}
        for filename, maximum in LEGACY_FILE_DIALOG_MAX.items():
            count = len(_direct_file_dialog_calls(ast.parse((ROOT / filename).read_text(encoding='utf-8'))))
            if count > maximum:
                actual[filename] = f'{count}>{maximum}'
        self.assertEqual(actual, {}, '业务页历史直调 filedialog 数量只能下降：' + str(actual))
 # 现有业务页的冻结上限；首迁入口仍由下方的零容忍断言保护。
LEGACY_FILE_DIALOG_MAX = {
    'app.py': 2, 'asset_detail.py': 2, 'asset_reference_import.py': 1,
    'desktop.py': 7, 'reference_wall.py': 2, 'storyboard_files.py': 1,
    'white_model.py': 1, 'workflow_settings.py': 1,
}

def _direct_file_dialog_calls(tree):
    return [node for node in ast.walk(tree) if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == 'filedialog']
