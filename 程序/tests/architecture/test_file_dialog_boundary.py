"""首迁附件入口不得退回页面内直接文件选择。"""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

from tests.architecture._scan import entity_file, parse_desktop

ROOT = Path(__file__).resolve().parents[2]


class FileDialogBoundaryTests(unittest.TestCase):
    def test_idea_attachment_uses_unified_file_dialog(self):
        tree = parse_desktop()  # R1490：该方法已迁到 IdeaChatMixin，按全部 Desktop 源码查找
        method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == 'choose_idea_attachments')
        calls = [node for node in ast.walk(method) if isinstance(node, ast.Call)]
        attrs = [node.func.attr for node in calls if isinstance(node.func, ast.Attribute)]
        self.assertIn('open_files', attrs)
        self.assertNotIn('askopenfilenames', attrs)

    def test_desktop_file_chooser_calls_do_not_increase(self):
        tree = parse_desktop()
        self.assertLessEqual(len(_direct_file_dialog_calls(tree)), LEGACY_FILE_DIALOG_MAX['desktop.py'],
                             'Desktop 历史直调 filedialog 数量只能下降')

    def test_business_pages_have_no_direct_file_chooser_calls(self):
        actual = {}
        for filename, maximum in LEGACY_FILE_DIALOG_MAX.items():
            count = len(_direct_file_dialog_calls(ast.parse(entity_file(Path(filename).stem).read_text(encoding='utf-8'))))
            if count > maximum:
                actual[filename] = f'{count}>{maximum}'
        self.assertEqual(actual, {}, '业务页历史直调 filedialog 数量只能下降：' + str(actual))

    def test_business_modules_use_file_dialog_boundary(self):
        """路线图收口：除统一入口本身外，业务模块不再直调 tkinter.filedialog。"""
        actual = {}
        for path in ROOT.glob('*.py'):
            if path.name == 'ui_dialogs.py':
                continue
            calls = _direct_file_dialog_calls(ast.parse(path.read_text(encoding='utf-8')))
            if calls:
                actual[path.name] = [call.lineno for call in calls]
        self.assertEqual(actual, {}, '业务模块必须经 FileDialog 选择文件：' + str(actual))

    def test_all_production_modules_use_file_dialog_boundary(self):
        actual = {}
        for path in ROOT.rglob('*.py'):
            relative = path.relative_to(ROOT)
            if (path.name == 'ui_dialogs.py' or path.name.startswith('test')
                    or 'tests' in relative.parts or 'tasks_round' in relative.parts
                    or '维护记录' in relative.parts or 'voice_asr_venv' in relative.parts):
                continue
            calls = _direct_file_dialog_calls(ast.parse(path.read_text(encoding='utf-8')))
            if calls:
                actual[str(relative)] = [call.lineno for call in calls]
        self.assertEqual(actual, {}, '生产模块必须经 FileDialog 选择文件：' + str(actual))

 # 现有业务页的冻结上限；首迁入口仍由下方的零容忍断言保护。
LEGACY_FILE_DIALOG_MAX = {
    'app.py': 2, 'asset_detail.py': 2, 'asset_reference_import.py': 1,
    'desktop.py': 7, 'reference_wall.py': 2, 'storyboard_files.py': 1,
    'white_model.py': 1, 'workflow_settings_dialog.py': 1,
}

def _direct_file_dialog_calls(tree):
    return [node for node in ast.walk(tree) if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == 'filedialog']
