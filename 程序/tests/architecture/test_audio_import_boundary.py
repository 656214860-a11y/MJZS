"""The desktop audio page delegates user audio publication to its service."""
from tests.architecture._scan import parse_desktop  # R1505：Desktop 方法分布在 desktop.py 与迁出的 Mixin 模块
import ast
import unittest

from tests.architecture._scan import ROOT
from tests.architecture._scan import stage_execution_source


class AudioImportBoundaryTests(unittest.TestCase):
    def test_desktop_delegates_audio_copy_to_service(self):
        tree = parse_desktop()
        desktop = ast.Module(body=[member for cls in tree.body if isinstance(cls, ast.ClassDef) for member in cls.body], type_ignores=[])  # Desktop 方法分布在 desktop.py 与迁出的 Mixin 类里
        method = next(node for node in desktop.body if isinstance(node, ast.FunctionDef) and node.name == 'import_audio')
        # FIX-S11-E6：页面经 ui.tts_settings 胶水询问用途后走 L3，不再直调 L3 入口。
        delegated = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Name) and node.func.id == 'import_audio_with_kind']
        self.assertEqual(len(delegated), 1)
        direct = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Name) and node.func.id == 'import_stage_audio']
        self.assertEqual(direct, [], '音频导入的唯一编排入口是 ui.tts_settings 胶水：' + str(direct))
        glue = (ROOT / 'ui' / 'tts_settings.py').read_text(encoding='utf-8')
        self.assertIn('import_stage_audio(project, source, kind=kind)', glue,
                      '音频导入胶水须把用户所选用途原样传给 L3 编排')
        orchestration = stage_execution_source()
        self.assertIn("return import_audio(project, source, publish=media_import_publisher(project, 'audio'), kind=kind)", orchestration,
                      '生产音频导入必须由 L3 注入统一媒体校验及流式发布器')
        self.assertIn('return publish_imported_media(target, source, lambda temporary: validate_import(temporary, config, kind), kind)', orchestration)
        domain = (ROOT / 'domain/audio_import_service.py').read_text(encoding='utf-8')
        self.assertNotIn('read_bytes(', domain, '媒体导入不能整文件读入内存')
        prohibited = {'copy2', 'save', 'save_bytes', 'write_text', 'write_bytes', 'remove_temporary_file'}
        direct = [node.lineno for node in ast.walk(method) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Name) and node.func.id in prohibited]
        self.assertEqual(direct, [], '音频导入不得由桌面页直接发布: ' + str(direct))
