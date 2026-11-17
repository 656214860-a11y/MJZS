# -*- coding: utf-8 -*-
"""\u56de\u9000\u5230\u5df2\u786e\u8ba4\u9636\u6bb5\u7684\u610f\u56fe\u8bc6\u522b\u4e0e\u4e8c\u6b21\u786e\u8ba4\u95e8\u69db\u3002"""
import json
import tempfile
import unittest
from unittest.mock import patch

import infra.model_pool as model_pool
from contract import project_stages
import stage_config
import writing_api
from agent.core import save
from stage_execution_service import publish_stage_text
from test_workflow import make_project
import test_writing_api


class WritingRestartIntentTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = make_project(temporary.name)
        stage_config.put(self.project, 'script', model='gpt-4o', skills=['pipeline-script-preparation'])
        save(project_stages.writing(self.project) / 'brief_complete.json',
             test_writing_api.WritingApiTests.complete_brief())
        test_writing_api.WritingApiTests.confirmed_preparation(self.project)
        self.target, self.original, _ = writing_api._preparation_state(
            self.project, writing_api._complete_brief(self.project))
        pool = patch('writing_api.model_pool.pool', return_value=model_pool.default_pool())
        pool.start()
        self.addCleanup(pool.stop)

    def state(self):
        return json.loads(self.target.read_text(encoding='utf-8'))

    def test_restart_intent_recognizes_rollback_and_keeps_revision_separate(self):
        for text, expected in (('\u56de\u5230\u8bbe\u5b9a\u9636\u6bb5', '\u9879\u76ee\u8bbe\u5b9a'),
                               ('\u56de\u5230\u8bbe\u5b9a\u9636\u6bb5\u91cd\u65b0\u5199', '\u9879\u76ee\u8bbe\u5b9a'),
                               ('\u5927\u7eb2\u8981\u91cd\u5199', '\u5267\u672c\u5927\u7eb2'),
                               ('\u89d2\u8272\u5361\u63a8\u7ffb\u91cd\u6765', '\u89d2\u8272\u5361'),
                               ('\u91cd\u65b0\u521b\u4f5c\u9879\u76ee\u8bbe\u5b9a', '\u9879\u76ee\u8bbe\u5b9a'),
                               ('\u8bf7\u91cd\u65b0\u751f\u6210\u89d2\u8272\u5361\u3002', '\u89d2\u8272\u5361')):
            with self.subTest(text=text):
                self.assertEqual(writing_api.preparation_restart_intent(text), expected)
        for text in ('\u4fee\u6539\u4e3b\u89d2', '\u786e\u8ba4', '\u5f00\u59cb\u521b\u4f5c', '\u4e0d\u8981\u786e\u8ba4\uff0c\u5148\u6539\u8bbe\u5b9a',
                     '\u7ee7\u7eed\u8f93\u51fa\u9879\u76ee\u5927\u7eb2', '\u89d2\u8272\u8bf4\uff1a\u91cd\u65b0\u521b\u4f5c', '\u628a\u8bbe\u5b9a\u6539\u4e00\u4e0b',
                     '\u91cd\u65b0\u521b\u4f5c'):
            with self.subTest(text=text):
                self.assertIsNone(writing_api.preparation_restart_intent(text))

    def test_rollback_asks_first_then_runs_after_confirmation(self):
        with patch('writing_api.PoolAdapter.chat',
                   side_effect=AssertionError('\u786e\u8ba4\u524d\u4e0d\u5f97\u8c03\u7528\u6a21\u578b')):
            asked = writing_api.reply(self.project, '\u56de\u5230\u8bbe\u5b9a\u9636\u6bb5\u91cd\u65b0\u5199',
                                      publish=publish_stage_text)
        self.assertTrue(asked['ok'])
        for stage in writing_api.PREPARATION_STAGES:
            self.assertIn(stage, asked['text'])
        state = self.state()
        self.assertEqual(state['pending_restart']['stage'], '\u9879\u76ee\u8bbe\u5b9a')
        self.assertEqual(state['documents'], self.original['documents'])
        self.assertNotIn('revision', state)

        with patch('writing_api.PoolAdapter.chat', return_value={
                'ok': True, 'text': '# \u9879\u76ee\u8bbe\u5b9a\n\u65b0\u7248\u672c\uff1a\u96e8\u591c\u5bfb\u627e\u5931\u8e2a\u7684\u59d0\u59d0\u3002\n\u5f85\u786e\u8ba4'}) as chat:
            result = writing_api.reply(self.project, '\u786e\u8ba4', publish=publish_stage_text)
        self.assertTrue(chat.called)
        self.assertTrue(result['ok'])
        self.assertEqual(result['preparation_stage'], '\u9879\u76ee\u8bbe\u5b9a')
        state = self.state()
        self.assertNotIn('pending_restart', state)
        self.assertEqual(state['documents'], self.original['documents'])
        self.assertEqual([doc['stage'] for doc in state['revision']['documents']], ['\u9879\u76ee\u8bbe\u5b9a'])
        self.assertFalse(state['revision']['documents'][-1]['confirmed'])

    def test_casual_reply_keeps_status_quo_and_clears_pending_restart(self):
        """REQ-S01-12：二次确认只认明确词；「好的」「继续」「ok」属保持现状。"""
        from copy import deepcopy
        for word in ('好的', '继续', 'ok'):
            with self.subTest(word=word):
                save(self.target, deepcopy(self.original))
                asked = writing_api.reply(self.project, '回到设定阶段重新写',
                                          publish=publish_stage_text)
                self.assertEqual(self.state()['pending_restart']['stage'], '项目设定')
                with patch('writing_api.PoolAdapter.chat', return_value={
                        'ok': True, 'text': '# 项目设定\n新版本：雨夜寻找失踪的姐姐。\n待确认'}):
                    result = writing_api.reply(self.project, word, publish=publish_stage_text)
                self.assertTrue(result['ok'])
                state = self.state()
                self.assertNotIn('pending_restart', state)
                self.assertNotIn('revision', state)
                self.assertEqual(state['documents'], self.original['documents'])

        save(self.target, deepcopy(self.original))
        asked = writing_api.reply(self.project, '回到设定阶段重新写',
                                  publish=publish_stage_text)
        self.assertEqual(self.state()['pending_restart']['stage'], '项目设定')
        with patch('writing_api.PoolAdapter.chat', return_value={
                'ok': True, 'text': '# 项目设定\n新版本：雨夜寻找失踪的姐姐。\n待确认'}) as chat:
            result = writing_api.reply(self.project, '确认', publish=publish_stage_text)
        self.assertTrue(chat.called)
        self.assertTrue(result['ok'])
        state = self.state()
        self.assertNotIn('pending_restart', state)
        self.assertIn('revision', state)

    def test_rollback_not_run_without_confirmation(self):
        state = self.state()
        state['documents'] = state['documents'][:2]
        save(self.target, state)
        asked = writing_api.reply(self.project, '\u56de\u5230\u8bbe\u5b9a\u9636\u6bb5\u91cd\u65b0\u5199',
                                  publish=publish_stage_text)
        self.assertIn('\u9879\u76ee\u8bbe\u5b9a', asked['text'])
        with patch('writing_api.PoolAdapter.chat', return_value={
                'ok': True, 'text': '# \u4eba\u7269\u8bbe\u5b9a\uff08\u89d2\u8272\u5361\uff09\n\u65b0\u89d2\u8272\u5361\u3002\n\u5f85\u786e\u8ba4'}) as chat:
            result = writing_api.reply(self.project, '\u5148\u7b97\u4e86\u5427', publish=publish_stage_text)
        self.assertTrue(chat.called)
        self.assertTrue(result['ok'])
        self.assertEqual(result['preparation_stage'], '\u89d2\u8272\u5361')
        state = self.state()
        self.assertNotIn('revision', state)
        self.assertNotIn('pending_restart', state)
        self.assertEqual(len(state['documents']), 3)
        self.assertFalse(state['documents'][2]['confirmed'])

    def test_rollback_without_confirmed_downstream_falls_through(self):
        state = self.state()
        state['documents'] = state['documents'][:1]
        save(self.target, state)
        with patch('writing_api.PoolAdapter.chat', return_value={
                'ok': True, 'text': '# \u5267\u672c\u5927\u7eb2\n\u65b0\u5927\u7eb2\u3002\n\u5f85\u786e\u8ba4'}) as chat:
            result = writing_api.reply(self.project, '\u56de\u5230\u5267\u672c\u5927\u7eb2\u9636\u6bb5\u91cd\u65b0\u5199',
                                       publish=publish_stage_text)
        self.assertTrue(chat.called)
        self.assertEqual(result['preparation_stage'], '\u5267\u672c\u5927\u7eb2')
        state = self.state()
        self.assertNotIn('pending_restart', state)
        self.assertNotIn('revision', state)


if __name__ == '__main__':
    unittest.main()
