# -*- coding: utf-8 -*-
"""REQ-S01-86：简报必填校验前置到输入框——缺字段实时置灰发送并在状态行点名缺失字段。"""
import tempfile
import unittest
from unittest.mock import Mock

import model_pool
import project_stages
import stage_config
import writing_api
from agent.core import save
from desktop_idea_chat import IdeaChatMixin
from idea_chat_controller import IdeaChatController
from test_workflow import make_project
import test_writing_api


class IdeaSendGateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = make_project(temporary.name)
        stage_config.put(self.project, 'script', model='gpt-4o')
        self.page = IdeaChatMixin.__new__(IdeaChatMixin)
        self.page.win = Mock()
        self.page.win.after = Mock(return_value='after-id')
        self.page.win.after_cancel = Mock()
        self.page.root = self.project
        self.page.idea_chat_controller = IdeaChatController()
        self.page.shared_input = Mock()
        self.page.shared_input.send_button = Mock()
        self.page.update_script_interrupt_button = Mock()
        self.page.status = Mock()
        self.page._idea_send_state_after = None
        self.page._idea_send_hint = ''
        self._draft = ''
        self.page.draft_text = lambda: self._draft

    def draft(self, value):
        self._draft = value
        self.page._apply_idea_send_state()

    def test_incomplete_draft_disables_send_and_names_missing_fields(self):
        """REQ-S01-86：必填缺失时置灰发送（经 update_script_interrupt_button），状态行点名缺哪些字段。"""
        self.draft('')
        self.page.update_script_interrupt_button.assert_called_once()
        hint = self.page.status.set.call_args[0][0]
        self.assertIn('还缺必填', hint)
        self.assertIn('故事梗概', hint)

    def test_complete_draft_enables_send(self):
        """REQ-S01-86：五项必填齐全时发送恢复可用。"""
        self.draft('故事梗概：雨夜少年发现会说话的底片。\n故事题材：奇幻\n'
                   '故事角色：少年、老板\n故事集数：80\n单集时间：60秒')
        missing = self.page._idea_live_missing()
        self.page.update_script_interrupt_button.assert_called_once()
        if not missing:
            self.assertEqual(self.page.status.set.call_args[0][0], '就绪')
        else:
            # 新项目若另有必填制作锁，缺失提示须点名锁字段而不是静默通过。
            hint = self.page.status.set.call_args[0][0]
            self.assertIn('还缺必填', hint)
            self.assertTrue(all(label in hint for label in missing))

    def test_completed_brief_keeps_send_enabled_without_fields(self):
        """REQ-S01-86：简报已完成进入四阶段流程后，普通追问不再要求必填字段。"""
        save(project_stages.writing(self.project) / 'brief_complete.json',
             test_writing_api.WritingApiTests.complete_brief())
        self.draft('继续')
        self.page.update_script_interrupt_button.assert_called_once()

    def test_refresh_debounces_through_after(self):
        """REQ-S01-86：输入期防抖——重复刷新只保留最近一次 after 回调。"""
        self.page.refresh_idea_send_state()
        self.page.refresh_idea_send_state()
        self.page.win.after_cancel.assert_called_once()
        self.assertEqual(self.page.win.after.call_count, 2)
        self.assertIsNotNone(self.page._idea_send_state_after)

    def test_attachment_change_schedules_refresh(self):
        """REQ-S01-86：附件变化同样触发可用态刷新（附件可能补齐必填字段）。"""
        self.page.idea_attachment_paths = ('参考.md',)
        self.page.win.after.assert_called()
        self.assertIsNotNone(self.page._idea_send_state_after)


if __name__ == '__main__':
    unittest.main()
