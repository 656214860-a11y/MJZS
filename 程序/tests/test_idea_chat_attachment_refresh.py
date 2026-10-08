"""上传回调只更新附件状态，不改写用户输入或只读示例。"""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
import desktop


class AttachmentRefreshTests(unittest.TestCase):
    def test_upload_keeps_inline_draft_and_reports_new_entry(self):
        draft = Mock(return_value='用户已修改的模板')
        view = SimpleNamespace(idea_send=None, draft_text=draft,
                               poll_idea_semantic_brief=Mock(),
                               status=Mock(), update_idea_attachment_status=Mock(),
                               idea_chat_controller=Mock())
        view.idea_chat_controller.poll_attachment_preparation.return_value = {
            'ok': True, 'value': {'names': ['创意.txt']}}
        desktop.Desktop.poll_idea_attachment_preparation(view)
        view.update_idea_attachment_status.assert_called_once()
        self.assertFalse(hasattr(desktop.Desktop, 'refresh_idea_brief_from_attachments'))
        draft.assert_not_called()
        self.assertIn('发送框', view.status.set.call_args.args[0])
        self.assertNotIn('表单', view.status.set.call_args.args[0])
        self.assertFalse(hasattr(desktop.Desktop, 'open_brief_creation_form'))

    def test_successful_upload_never_fills_empty_or_manual_input(self):
        for current in ('', '用户输入保持原样'):
            with self.subTest(current=current):
                view = SimpleNamespace(
                    root='unused', idea_attachment_paths=('材料.md',), idea_send=None,
                    draft_text=Mock(return_value=current), fill_idea_brief=Mock(),
                    poll_idea_semantic_brief=Mock(), status=Mock(),
                    update_idea_attachment_status=Mock(), idea_chat_controller=Mock())
                view.idea_chat_controller.poll_attachment_preparation.return_value = {
                    'ok': True, 'value': {'paths': ('材料.md',), 'names': ['材料.md']}}
                with patch('stage_execution_service.stage_idea_attachment_reference'), \
                        patch('stage_execution_service.stage_idea_brief_defaults',
                              return_value={'values': {'故事梗概': '附档正文'}}):
                    desktop.Desktop.poll_idea_attachment_preparation(view)
                view.fill_idea_brief.assert_not_called()
                view.update_idea_attachment_status.assert_called_once()
