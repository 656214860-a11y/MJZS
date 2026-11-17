# -*- coding: utf-8 -*-
"""REQ-S01-89：三阶段草稿并行起草与修订；确认仍按序检查依赖。"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import model_pool
from contract import project_stages
import stage_config
import writing_api
from agent.core import save
from stage_execution_service import publish_stage_text
from test_workflow import make_project
import test_writing_api


class PreparationParallelTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = make_project(temporary.name)
        stage_config.put(self.project, 'script', model='gpt-4o',
                         skills=['pipeline-script-preparation'])
        save(project_stages.writing(self.project) / 'brief_complete.json',
             test_writing_api.WritingApiTests.complete_brief())
        pool = patch('writing_api.model_pool.pool', return_value=model_pool.default_pool())
        pool.start()
        self.addCleanup(pool.stop)
        from contract.stage_path_service import write_dir
        self.target = write_dir(self.project, 'script') / 'preparation_state.json'

    def state(self):
        return json.loads(self.target.read_text(encoding='utf-8'))

    def reply(self, creative, model_text):
        with patch('writing_api.PoolAdapter.chat', return_value={
                'ok': True, 'text': model_text}):
            result = writing_api.reply(self.project, creative, publish=publish_stage_text)
        self.assertTrue(result['ok'], result.get('error'))
        return result

    def draft_all_three(self):
        self.reply('开始', '# 项目设定\n雨夜照相馆。\n待确认')
        self.reply('先写剧本大纲', '# 剧本大纲\n三幕。\n待确认')
        self.reply('再写角色卡', '# 人物设定（角色卡）\n阿远。\n待确认')

    def test_named_next_stage_appends_parallel_draft_keeping_pending(self):
        """REQ-S01-89：设定草稿未确认时点名起草大纲——两份草稿并存，都不确认。"""
        self.reply('开始', '# 项目设定\n雨夜照相馆。\n待确认')
        self.reply('先写剧本大纲', '# 剧本大纲\n三幕。\n待确认')
        documents = self.state()['documents']
        self.assertEqual([doc['stage'] for doc in documents], ['项目设定', '剧本大纲'])
        self.assertFalse(documents[0]['confirmed'])
        self.assertFalse(documents[1]['confirmed'])

    def test_generic_reply_works_on_earliest_unconfirmed_draft(self):
        """REQ-S01-89：未点名阶段时处理首个未确认稿——推进确认设定并把新大纲稿落位。"""
        self.reply('开始', '# 项目设定\n雨夜照相馆。\n待确认')
        self.reply('先写剧本大纲', '# 剧本大纲\n三幕。\n待确认')
        self.reply('确认，继续', '# 剧本大纲\n修订的三幕。\n待确认')
        documents = self.state()['documents']
        self.assertTrue(documents[0]['confirmed'])
        self.assertFalse(documents[1]['confirmed'])
        self.assertIn('修订的三幕', (self.target.parent / documents[1]['path']).read_text(encoding='utf-8'))

    def test_named_revision_of_later_draft_keeps_it_unconfirmed(self):
        """REQ-S01-89：点名修订后置草稿——只更新该稿，不越序确认任何阶段。"""
        self.draft_all_three()
        self.reply('把角色卡再改一改', '# 人物设定（角色卡）\n修订后的阿远。\n待确认')
        documents = self.state()['documents']
        self.assertFalse(any(doc['confirmed'] for doc in documents))
        self.assertIn('修订后的阿远',
                      (self.target.parent / documents[2]['path']).read_text(encoding='utf-8'))

    def test_later_stage_output_while_prefix_unconfirmed_stores_draft_not_confirm(self):
        """REQ-S01-89：前置未确认时模型产出更后阶段——落为并行草稿，不越序确认。"""
        self.reply('开始', '# 项目设定\n雨夜照相馆。\n待确认')
        self.reply('先写剧本大纲', '# 剧本大纲\n三幕。\n待确认')
        self.reply('把剧本大纲再改改', '# 人物设定（角色卡）\n阿远。\n待确认')
        documents = self.state()['documents']
        self.assertEqual([doc['stage'] for doc in documents],
                         ['项目设定', '剧本大纲', '角色卡'])
        self.assertFalse(any(doc['confirmed'] for doc in documents))

    def test_named_far_stage_without_intermediate_draft_errors(self):
        """REQ-S01-89：点名跳过未起草的中间阶段——报错并提示先起草。"""
        self.reply('开始', '# 项目设定\n雨夜照相馆。\n待确认')
        with patch('writing_api.PoolAdapter.chat', return_value={'ok': True, 'text': '# 人物设定（角色卡）\n阿远。\n待确认'}), \
                self.assertRaises(ValueError) as ctx:
            writing_api.reply(self.project, '先写角色卡', publish=publish_stage_text)
        self.assertIn('剧本大纲', str(ctx.exception))
        self.assertEqual(len(self.state()['documents']), 1)

    def test_rewrite_command_on_unconfirmed_draft_regenerates_not_prefix_error(self):
        """REQ-S01-89：重写口令指向未确认草稿——按重起草处理，不报「请先确认所选阶段之前的文件」。"""
        self.reply('开始', '# 项目设定\n雨夜照相馆。\n待确认')
        self.reply('先写剧本大纲', '# 剧本大纲\n三幕。\n待确认')
        self.assertTrue(writing_api.preparation_continuation(self.project, '重写剧本大纲'))
        self.reply('重写剧本大纲', '# 剧本大纲\n重写的三幕。\n待确认')
        documents = self.state()['documents']
        self.assertFalse(documents[0]['confirmed'])
        self.assertIn('重写的三幕',
                      (self.target.parent / documents[1]['path']).read_text(encoding='utf-8'))

    def test_confirm_later_stage_requires_confirmed_prefix_and_keeps_later_drafts(self):
        """REQ-S01-89：「设为定稿」依赖检查照旧；确认前阶段保留下游未确认草稿。"""
        from orchestrator import writing_unconfirm
        self.draft_all_three()
        card = self.target.parent / self.state()['documents'][2]['path']
        with self.assertRaises(ValueError) as ctx:
            writing_unconfirm.confirm_preparation_document(
                self.project, '角色卡', card, publish=publish_stage_text)
        self.assertIn('未确认', str(ctx.exception))
        setting = self.target.parent / self.state()['documents'][0]['path']
        writing_unconfirm.confirm_preparation_document(
            self.project, '项目设定', setting, publish=publish_stage_text)
        documents = self.state()['documents']
        self.assertTrue(documents[0]['confirmed'])
        self.assertEqual([doc['stage'] for doc in documents],
                         ['项目设定', '剧本大纲', '角色卡'])
        self.assertFalse(documents[1]['confirmed'])
        self.assertFalse(documents[2]['confirmed'])


if __name__ == '__main__':
    unittest.main()
