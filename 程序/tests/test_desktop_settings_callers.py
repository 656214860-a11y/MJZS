"""Exercise real desktop methods without creating Tk or launching applications."""
from tests.architecture._scan import parse_desktop  # R1505：Desktop 方法分布在 desktop.py 与迁出的 Mixin 模块
import ast
import os
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

from service_contract import SystemError, success


class DesktopSettingsCallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(__file__).resolve().parents[1] / 'desktop.py'
        tree = parse_desktop()
        names = {'remember_daily_project_choice', '_sync_desktop_project_paths',
                 'launch_comfy', 'find_editor'}
        methods = [node for node in ast.walk(tree)
                   if isinstance(node, ast.FunctionDef) and node.name in names]
        assert len(methods) == 4
        cls.namespace = dict(Path=Path, date=date, os=os)
        exec(compile(ast.Module(body=methods, type_ignores=[]), str(source), 'exec'), cls.namespace)

    def test_each_caller_checks_result_before_mutation_or_continuation(self):
        for name in ('remember_daily_project_choice', '_sync_desktop_project_paths',
                     'launch_comfy', 'find_editor'):
            for ok in (False, True):
                with self.subTest(method=name, ok=ok):
                    before = {'project_choice_path': str(Path('old')), 'jianying': ''}
                    after = {**before, 'saved': True}
                    app = Mock(settings=before, settings_file=Path('desktop_settings.json'))
                    app.comfy_listening.return_value = False
                    dialog = Mock()
                    dialog.return_value.open_file.return_value = 'ComfyUI.exe'
                    app.media_page_services.file_dialog = dialog          # R1995 起走注入的页面服务，不再读模块级名
                    app.media_page_services.comfy_executable = Mock(return_value=None)
                    result = success(after) if ok else SystemError('保存失败')
                    args = {'remember_daily_project_choice': ('new',),
                            '_sync_desktop_project_paths': ('old', 'new'),
                            'launch_comfy': (), 'find_editor': ()}[name]
                    with patch('stage_execution_service.publish_desktop_preferences', return_value=result) as save, \
                         patch('native_apps.open_comfy') as launch, \
                         patch.object(Path, 'glob', return_value=[]), \
                         patch.object(Path, 'is_file', return_value=True):
                        if ok:
                            returned = self.namespace[name](app, *args)
                            self.assertIs(app.settings, after)
                            if name == 'launch_comfy':
                                self.assertTrue(returned)
                                launch.assert_called_once()
                            elif name == 'find_editor':
                                self.assertIsInstance(returned, Path)
                        else:
                            with self.assertRaisesRegex(ValueError, '保存失败'):
                                self.namespace[name](app, *args)
                            self.assertIs(app.settings, before)
                            app.status.set.assert_not_called()
                            launch.assert_not_called()
                        save.assert_called_once()
                    self.assertEqual(before, {'project_choice_path': str(Path('old')), 'jianying': ''})

    def test_no_path_change_does_not_save(self):
        app = Mock(settings={}, settings_file=Path('desktop_settings.json'))
        with patch('stage_execution_service.publish_desktop_preferences') as save:
            self.namespace['_sync_desktop_project_paths'](app, 'old', 'new')
        save.assert_not_called()

    def test_cancelled_comfy_selection_does_not_save_or_launch(self):
        app = Mock(settings={})
        app.comfy_listening.return_value = False
        app.media_page_services.comfy_executable = Mock(return_value=None)
        dialog = Mock()
        dialog.return_value.open_file.return_value = ''
        app.media_page_services.file_dialog = dialog
        with patch('stage_execution_service.publish_desktop_preferences') as save, \
             patch('native_apps.open_comfy') as launch:
            self.namespace['launch_comfy'](app)
        save.assert_not_called()
        launch.assert_not_called()
