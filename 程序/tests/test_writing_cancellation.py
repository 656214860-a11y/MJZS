"""取消请求的迟到结果不得发布；所有文件与模型替身均为隔离数据。"""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import model_pool
import project_stages
import script_contract
import stage_config
import writing_api
from hollmwood_roles import RoleCancelledError
from idea_chat_controller import IdeaChatController
from stage_execution_service import publish_stage_text
from tests.test_workflow import make_project


class WritingCancellationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.project = make_project(temp.name)
        stage_config.put(self.project, 'script', model='gpt-4o',
                         skills=['pipeline-script-preparation'], hollmwood_enabled=False)
        writing = self.project / 'writing'; writing.mkdir(exist_ok=True)
        brief = script_contract.brief_document({
            'story_summary': '雨夜少年发现会说话的底片。', 'main_characters': '少年和老板',
            'genre': '奇幻', 'length': '单集 60 秒'})
        (writing / 'brief_complete.json').write_text(json.dumps(brief), encoding='utf-8')
        # 本组验证自然剧本发布时的取消保护，真实前置确认由 API 阶段测试覆盖。
        from tests.test_writing_api import WritingApiTests
        WritingApiTests.confirmed_preparation(self.project)
        self.text = ('雨夜照相馆，少年推开门。老板说：“底片会告诉你真相。”少年攥紧相机继续追查。\n') * 30
        self.cancelled = threading.Event()
        self.enterContext(patch('writing_api.model_pool.pool', return_value=model_pool.default_pool()))

    def test_cancelled_before_request_does_not_call_model_or_publish_context(self):
        self.cancelled.set()
        with patch('writing_api.PoolAdapter.chat') as chat, \
                patch('workflow_context_controller.publish_writing_context') as context:
            with self.assertRaises(RoleCancelledError):
                writing_api.reply(self.project, '创作', cancelled=self.cancelled.is_set)
        chat.assert_not_called(); context.assert_not_called()

    def test_cancelled_during_request_does_not_replace_existing_script(self):
        target = project_stages.writing(self.project) / 'script_raw.md'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('原有稿件', encoding='utf-8')
        def chat(*args, **kwargs):
            self.cancelled.set()
            return {'ok': True, 'text': self.text}
        with patch('writing_api.PoolAdapter.chat', side_effect=chat):
            with self.assertRaises(RoleCancelledError):
                writing_api.reply(self.project, '创作', cancelled=self.cancelled.is_set,
                                  publish=publish_stage_text)
        self.assertEqual(target.read_text(encoding='utf-8'), '原有稿件')

    def test_cancelled_during_auto_save_validation_is_checked_at_publisher(self):
        original = writing_api._write_script_raw
        def cancel_before_publish(*args, **kwargs):
            self.cancelled.set()
            return original(*args, **kwargs)
        publish = Mock()
        with patch('writing_api.PoolAdapter.chat', return_value={'ok': True, 'text': self.text}), \
                patch('writing_api._write_script_raw', side_effect=cancel_before_publish):
            with self.assertRaises(RoleCancelledError):
                writing_api.reply(self.project, '创作', cancelled=self.cancelled.is_set, publish=publish)
        publish.assert_not_called()

    @staticmethod
    def tool_response():
        return {'ok': True, 'data': {'content': [
            {'type': 'tool_use', 'id': 'one', 'name': 'read_project_writing_file', 'input': {}},
            {'type': 'tool_use', 'id': 'two', 'name': 'write_project_writing_file', 'input': {}}]}}

    def test_cancelled_after_model_prevents_all_tool_execution(self):
        def chat(*args, **kwargs):
            self.cancelled.set(); return self.tool_response()
        adapter = SimpleNamespace(chat=Mock(side_effect=chat))
        with patch('writing_api.writing_tools.execute') as execute:
            with self.assertRaises(RoleCancelledError):
                writing_api._reply_with_project_tools(adapter, 'model', '', '创作', self.project,
                                                      cancelled=self.cancelled.is_set)
        execute.assert_not_called(); self.assertEqual(adapter.chat.call_count, 1)

    def test_cancelled_between_tools_prevents_next_tool_and_next_request(self):
        adapter = SimpleNamespace(chat=Mock(return_value=self.tool_response()))
        def execute(*args, **kwargs):
            self.cancelled.set(); return {'content': '材料'}
        with patch('writing_api.writing_tools.execute', side_effect=execute) as tool:
            with self.assertRaises(RoleCancelledError):
                writing_api._reply_with_project_tools(adapter, 'model', '', '创作', self.project,
                                                      cancelled=self.cancelled.is_set)
        self.assertEqual(tool.call_count, 1); self.assertEqual(adapter.chat.call_count, 1)

    def test_cancelled_inside_tool_is_checked_at_publisher(self):
        adapter = SimpleNamespace(chat=Mock(return_value=self.tool_response()))
        publish = Mock()
        def execute(*args, **kwargs):
            self.cancelled.set()
            kwargs['publish'](self.project / 'late.md', '迟到内容', bool, lambda _: None)
        with patch('writing_api.writing_tools.execute', side_effect=execute):
            with self.assertRaises(RoleCancelledError):
                writing_api._reply_with_project_tools(adapter, 'model', '', '创作', self.project,
                                                      cancelled=self.cancelled.is_set, publish=publish)
        publish.assert_not_called()

    def test_new_request_does_not_reactivate_cancelled_old_request(self):
        controller = IdeaChatController()
        old_token, old_event = controller.begin_request(cancellable=True)
        def chat(*args, **kwargs):
            controller.cancel_request()
            new_token, new_event = controller.begin_request(cancellable=True)
            self.assertIsNot(old_token, new_token); self.assertFalse(new_event.is_set())
            return {'ok': True, 'text': self.text}
        publish = Mock()
        with patch('writing_api.PoolAdapter.chat', side_effect=chat):
            with self.assertRaises(RoleCancelledError):
                writing_api.reply(self.project, '创作', cancelled=old_event.is_set, publish=publish)
        publish.assert_not_called(); self.assertTrue(controller.requesting)

    def test_uncancelled_direct_request_still_publishes(self):
        with patch('writing_api.PoolAdapter.chat', return_value={'ok': True, 'text': self.text}):
            result = writing_api.reply(self.project, '创作', cancelled=self.cancelled.is_set,
                                       publish=publish_stage_text)
        self.assertTrue(result['ok'])
        self.assertEqual(Path(result['script_raw_path']).read_text(encoding='utf-8'), self.text.strip() + '\n')

    def test_uncancelled_tool_request_still_publishes(self):
        response = {'ok': True, 'data': {'content': [
            {'type': 'tool_use', 'id': 'save', 'name': 'write_project_writing_file',
             'input': {'path': 'writing/新稿.md', 'content': '已完成的新稿'}}]}}
        adapter = SimpleNamespace(chat=Mock(side_effect=[response, {'ok': True, 'text': '完成'}]))
        result = writing_api._reply_with_project_tools(adapter, 'model', '', '创作', self.project,
                                                       cancelled=self.cancelled.is_set, publish=publish_stage_text)
        self.assertTrue(result['ok'])
        self.assertEqual((project_stages.writing(self.project) / '新稿.md').read_text(encoding='utf-8'), '已完成的新稿')
