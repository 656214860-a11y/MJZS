import ast
from types import SimpleNamespace
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import project_stages
from script_workspace_service import ensure_script_workspace, rename_script_document
from service_contract import SystemError, UserError, success
from tests.architecture._scan import entity_file


class ScriptWorkspaceResultTests(unittest.TestCase):
    def test_mkdir_failure_is_system_error(self):
        with patch.object(Path, 'mkdir', side_effect=OSError('private detail')):
            with self.assertLogs('script_workspace_service', level='ERROR'):
                result = ensure_script_workspace('project')
        self.assertIsInstance(result, SystemError)
        self.assertNotIn('private detail', result.reason)

    def test_rename_invalid_failure_and_noop_preserve_source(self):
        with tempfile.TemporaryDirectory() as temp:
            source = project_stages.writing(temp) / '原名.md'
            source.parent.mkdir(parents=True)
            source.write_text('original', encoding='utf-8')
            # R3110 起改名走 agent.core.replace（原子替换＋缓存失效），不再直调 Path.rename；
            # 用例的替身点随之同步，断言原意不变（非法名与同名改都不落盘、失败不泄露系统细节）。
            with patch('agent.core.replace') as rename:
                self.assertIsInstance(rename_script_document(temp, source, '../bad'), UserError)
                unchanged = rename_script_document(temp, source, source.name)
                self.assertTrue(unchanged.ok)
                self.assertEqual(source.resolve(), unchanged.data)
                rename.assert_not_called()
            with patch('agent.core.replace', side_effect=OSError('private detail')):
                with self.assertLogs('script_workspace_service', level='ERROR'):
                    result = rename_script_document(temp, source, 'new.md')
            self.assertIsInstance(result, SystemError)
            self.assertNotIn('private detail', result.reason)
            self.assertEqual('original', source.read_text(encoding='utf-8'))
            self.assertFalse(source.with_name('new.md').exists())

    def test_wrapped_filesystem_failure_is_not_user_error(self):
        error = ValueError('wrapped')
        error.__cause__ = OSError('private detail')
        with patch('script_workspace_service.selected_script_paths', side_effect=error):
            with self.assertLogs('script_workspace_service', level='ERROR'):
                result = rename_script_document('project', 'source', 'target')
        self.assertIsInstance(result, SystemError)

    def test_programming_error_propagates(self):
        with patch.object(Path, 'mkdir', side_effect=TypeError('bug')):
            with self.assertRaisesRegex(TypeError, 'bug'):
                ensure_script_workspace('project')

    def test_desktop_rename_success_failure_and_cancel(self):
        source = entity_file('desktop_files_panel')  # R2962：文件列表迁到 ProjectFilesPanel
        tree = ast.parse(source.read_text(encoding='utf-8'))
        methods = [node for node in ast.walk(tree)
                   if isinstance(node, ast.FunctionDef) and node.name == 'rename_script']
        self.assertEqual(1, len(methods))
        for result in (SystemError('保存失败'), success(Path('new.md'))):
            app, dialog, refresh = Mock(), Mock(), Mock()
            dialog.ask_string.return_value = 'new.md'
            # R2962：rename_script 成了 ProjectFilesPanel 的方法，原来的闭包变量成了实例属性、桌面主窗成了 page
            env = dict(ask_string=dialog.ask_string)
            exec(compile(ast.Module(body=methods, type_ignores=[]), str(source), 'exec'), env)
            page = SimpleNamespace(page=app, fill_script_list=refresh, selected_script=Mock(return_value=Path('old.md')))
            rename = env['rename_script']
            env['rename_script'] = lambda: rename(page)
            with patch('script_workspace_service.rename_script_document', return_value=result) as service:
                if result.ok:
                    env['rename_script']()
                    refresh.assert_called_once()
                    app.status.set.assert_called_once_with('已重命名：new.md')
                else:
                    with self.assertRaisesRegex(ValueError, '保存失败'):
                        env['rename_script']()
                    refresh.assert_not_called()
                    app.status.set.assert_not_called()
                dialog.ask_string.return_value = ''
                service.reset_mock()
                env['rename_script']()
                service.assert_not_called()

    def test_desktop_initialization_failure_stops_before_page_construction(self):
        source = entity_file('desktop_writing_page')  # R1499：writing 已原样迁到 WritingPageMixin
        tree = ast.parse(source.read_text(encoding='utf-8'))
        desktop = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'WritingPageMixin')
        method = next(node for node in desktop.body if isinstance(node, ast.FunctionDef) and node.name == 'writing')
        page_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == '_WritingPage')  # R1817：页面主体改写成了类
        env = {}  # R2962：_WritingPage 不再继承 mixin，抽取执行无需基类名
        exec(compile(ast.Module(body=[method, page_class], type_ignores=[]), str(source), 'exec'), env)
        with patch('script_workspace_service.ensure_script_workspace', return_value=SystemError('初始化失败')):
            with self.assertRaisesRegex(ValueError, '初始化失败'):
                env['writing'](Mock())
