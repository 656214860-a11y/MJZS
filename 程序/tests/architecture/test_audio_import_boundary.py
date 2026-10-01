"""The desktop audio page delegates user audio publication to its service."""
import ast
import unittest

from tests.architecture._scan import ROOT


class AudioImportBoundaryTests(unittest.TestCase):
    def test_desktop_delegates_audio_copy_to_service(self):
        tree = ast.parse((ROOT / 'desktop.py').read_text(encoding='utf-8'))
        desktop = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Desktop')
        method = next(node for node in desktop.body if isinstance(node, ast.FunctionDef) and node.name == 'import_audio')
        delegated = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Name) and node.func.id == 'import_stage_audio']
        self.assertEqual(len(delegated), 1)
        orchestration = (ROOT / 'stage_execution_service.py').read_text(encoding='utf-8')
        self.assertIn('return import_audio(project, source, publish=publish_stage_bytes)', orchestration,
                      '生产音频导入必须由 L3 注入统一二进制发布器')
        prohibited = {'copy2', 'save', 'save_bytes', 'write_text', 'write_bytes', 'remove_temporary_file'}
        direct = [node.lineno for node in ast.walk(method) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Name) and node.func.id in prohibited]
        self.assertEqual(direct, [], '音频导入不得由桌面页直接发布: ' + str(direct))
