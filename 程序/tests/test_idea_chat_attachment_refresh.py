"""上传回调只更新附件状态，不改写用户输入或只读示例。"""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
import desktop


class AttachmentRefreshTests(unittest.TestCase):
    def test_upload_keeps_inline_draft_and_reports_new_entry(self):
        draft = Mock(return_value='用户已修改的模板')
        view = SimpleNamespace(idea_send=None, draft_text=draft,
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
