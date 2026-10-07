"""创作表单上传后刷新：只使用无头控件桩与临时项目。"""
import ast
from contextlib import ExitStack
import inspect
from pathlib import Path
import tempfile
import textwrap
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import desktop
from stage_execution_service import project_context
from tests.test_ui_edges import make_minimal_project


class TextStub:
    def __init__(self, *args, **kwargs):
        self.value = ''
        self.modified = False

    def insert(self, index, value):
        self.value += value
        self.modified = True

    def get(self, *args):
        return self.value

    def edit_modified(self, value=None):
        if value is not None:
            self.modified = value
        return self.modified

    def grid(self, **kwargs):
        pass


class AttachmentRefreshTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        directory = self.stack.enter_context(tempfile.TemporaryDirectory())
        root = make_minimal_project(directory)
        self.reference = {'brief_texts': (), 'brief_unreadable': ()}
        self.five = {'故事画风': '水墨风格', '故事分集': '第一集寻找底片',
                     '内容补充': '以照片推动线索', '特殊要求': '不出现旁白', '单集时间': '两分钟'}
        self.fresh = {'brief_texts': ('\n'.join(k + '：' + v for k, v in self.five.items()),),
                      'brief_unreadable': ()}
        self.view = SimpleNamespace(root=root, win=Mock(), idea_attachment_paths=(),
                                    idea_send=None, status=Mock(), idea_chat_controller=Mock(),
                                    update_idea_attachment_status=Mock(),
                                    idea_chat_context=lambda: project_context(root), draft_text=Mock(return_value=''))
        self.resolve = self.stack.enter_context(patch(
            'stage_execution_service.stage_idea_attachment_reference',
            side_effect=lambda *args: self.reference))
        self.stack.enter_context(patch('stage_config.current_workflow', return_value={}))
        self.stack.enter_context(patch.object(desktop, 'FormDialog', side_effect=self.dialog))
        self.stack.enter_context(patch.object(desktop, 'TextArea', TextStub))
        self.stack.enter_context(patch.object(desktop.tk, 'Text', TextStub))
        self.stack.enter_context(patch.object(desktop.tk, 'Canvas'))
        for name in ('Frame', 'Label', 'Scrollbar', 'Separator'):
            self.stack.enter_context(patch.object(desktop.ttk, name))
        self.stack.enter_context(patch.object(desktop, 'protect_readonly_combobox'))

    @staticmethod
    def dialog(*args, **kwargs):
        return SimpleNamespace(content=Mock(), winfo_exists=lambda: True,
                               deiconify=Mock(), lift=Mock(), focus_force=Mock(),
                               add_form_actions=Mock(), after_idle=Mock(), close=Mock())

    def open(self, **kwargs):
        desktop.Desktop.open_brief_creation_form(self.view, **kwargs)
        return self.view._brief_creation_window

    def values(self, form):
        return {k: form.brief_editors[k].get() for k in self.five}

    def test_upload_after_empty_form_fills_five_fields_from_current_selection(self):
        form = self.open(attachment_reference=self.reference)
        self.assertTrue(all(not value for value in self.values(form).values()))
        self.reference = self.fresh
        self.view.idea_attachment_paths = (Path('输入/素材.md'),)
        self.view.draft_text.return_value = '@素材'
        self.view.idea_chat_controller.poll_attachment_preparation.return_value = {
            'ok': True, 'value': {'names': ['素材.md']}}
        desktop.Desktop.poll_idea_attachment_preparation(self.view)
        self.assertEqual(self.values(form), self.five)
        self.resolve.assert_called_once_with(self.view.root, '@素材', self.view.idea_attachment_paths)
        self.assertIn('已自动同步可识别字段到创作信息表单', self.view.status.set.call_args.args[0])

    def test_user_edits_and_explicit_clear_are_never_overwritten(self):
        form = self.open(attachment_reference=self.reference)
        form.brief_editors['故事画风'].insert('1.0', '用户手填')
        cleared = form.brief_editors['内容补充']
        cleared.insert('1.0', '用户曾输入')
        cleared.value = ''
        self.reference = self.fresh
        form.refresh_attachment_fields()
        self.assertEqual(form.brief_editors['故事画风'].get(), '用户手填')
        self.assertEqual(cleared.get(), '')
        self.assertEqual(form.brief_editors['单集时间'].get(), '两分钟')

    def test_reuse_window_accepts_explicit_reference_after_selection_was_cleared(self):
        form = self.open(attachment_reference=self.reference)
        reused = self.open(attachment_reference=self.fresh)
        self.assertIs(reused, form)
        self.assertEqual(self.values(form), self.five)
        self.resolve.assert_not_called()
        form.lift.assert_called_once()

    def test_reuse_window_resolves_current_selection(self):
        form = self.open(attachment_reference=self.reference)
        self.reference = self.fresh
        self.view.idea_attachment_paths = (Path('输入/素材.md'),)
        self.assertIs(self.open(), form)
        self.assertEqual(self.values(form), self.five)
        self.resolve.assert_called_once_with(self.view.root, '', self.view.idea_attachment_paths)

    def test_implicit_and_explicit_reference_refresh_agree(self):
        form = self.open(attachment_reference=self.reference)
        self.reference = self.fresh
        form.refresh_attachment_fields()
        implicit = self.values(form)
        for editor in form.brief_editors.values():
            editor.value = ''
            editor.edit_modified(False)
        self.resolve.reset_mock()
        form.refresh_attachment_fields(self.fresh)
        self.assertEqual(self.values(form), implicit)
        self.assertEqual(implicit, self.five)
        self.resolve.assert_not_called()

    def test_refresh_uses_current_unsent_text_not_opening_text(self):
        form = self.open(attachment_reference=self.reference)
        self.view.draft_text.return_value = '故事画风：当前未发送的画风'
        self.reference = self.fresh
        form.refresh_attachment_fields()
        self.assertEqual(form.brief_editors['故事画风'].get(), '当前未发送的画风')

    def test_closed_form_upload_does_not_claim_synchronization(self):
        self.view.idea_chat_controller.poll_attachment_preparation.return_value = {
            'ok': True, 'value': {'names': ['素材.md']}}
        desktop.Desktop.poll_idea_attachment_preparation(self.view)
        self.assertNotIn('已自动同步', self.view.status.set.call_args.args[0])

    def test_refresh_ast_does_not_capture_opening_attachment_reference(self):
        tree = ast.parse(textwrap.dedent(inspect.getsource(desktop.Desktop.open_brief_creation_form)))
        refresh = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                       and n.name == 'refresh_attachment_fields')
        self.assertNotIn('attachment_reference', {n.id for n in ast.walk(refresh) if isinstance(n, ast.Name)})


if __name__ == '__main__':
    unittest.main()
