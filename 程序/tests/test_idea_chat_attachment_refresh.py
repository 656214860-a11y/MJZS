"""上传回调更新附件状态并请求受保护回填，不直接改写用户草稿。"""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
import desktop


class AttachmentRefreshTests(unittest.TestCase):
    def test_upload_keeps_inline_draft_and_reports_new_entry(self):
        draft = Mock(return_value='用户已修改的模板')
        view = SimpleNamespace(idea_send=None, draft_text=draft,
                               refresh_idea_brief_from_attachments=Mock(),
                               status=Mock(), update_idea_attachment_status=Mock(),
                               idea_chat_controller=Mock())
        view.idea_chat_controller.poll_attachment_preparation.return_value = {
            'ok': True, 'value': {'names': ['创意.txt']}}
        desktop.Desktop.poll_idea_attachment_preparation(view)
        view.update_idea_attachment_status.assert_called_once()
        view.refresh_idea_brief_from_attachments.assert_called_once()
        draft.assert_not_called()
        self.assertIn('发送框', view.status.set.call_args.args[0])
        self.assertNotIn('表单', view.status.set.call_args.args[0])
        self.assertFalse(hasattr(desktop.Desktop, 'open_brief_creation_form'))
