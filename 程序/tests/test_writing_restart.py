"""共享阶段成果的显式重写、确认失效与迟到响应保护。"""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import infra.model_pool as model_pool
from contract import project_stages
import script_contract
import stage_config
import writing_api
from agent.core import save
from stage_execution_service import publish_stage_text, restart_writing_preparation
from test_workflow import make_project
import test_writing_api


class WritingRestartTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = make_project(temporary.name)
        stage_config.put(self.project, 'script', model='gpt-4o', skills=['pipeline-script-preparation'])
        save(project_stages.writing(self.project) / 'brief_complete.json', test_writing_api.WritingApiTests.complete_brief())
        test_writing_api.WritingApiTests.confirmed_preparation(self.project)
        self.target, self.original, _ = writing_api._preparation_state(
            self.project, writing_api._complete_brief(self.project))
        pool = patch('writing_api.model_pool.pool', return_value=model_pool.default_pool())
        pool.start()
        self.addCleanup(pool.stop)

    def reply(self, title, creative='重写'):
        with patch('writing_api.PoolAdapter.chat', return_value={
                'ok': True, 'text': '# ' + title + '\n新版本：雨夜寻找失踪的姐姐。\n待确认'}):
            return writing_api.reply(self.project, creative, publish=publish_stage_text)

    def test_restart_each_stage_preserves_adopted_until_confirmation(self):
        """REQ-S01-14：①②③任一步可显式重写；重写未确认前旧稿仍在、不删除。"""
        for index, stage in enumerate(writing_api.PREPARATION_STAGES):
            with self.subTest(stage=stage):
                save(self.target, self.original)
                restart_writing_preparation(self.project, stage)
                title = '人物设定（角色卡）' if index == 2 else stage
                result = self.reply(title)
                state = json.loads(self.target.read_text(encoding='utf-8'))
                self.assertEqual(state['documents'], self.original['documents'])
                self.assertEqual(len(state['revision']['documents']), index + 1)
                self.assertFalse(state['revision']['documents'][-1]['confirmed'])
                self.assertTrue(Path(result['preparation_path']).is_file())
                for document in self.original['documents']:
                    self.assertTrue((self.target.parent / document['path']).is_file())

    def test_confirm_new_outline_invalidates_character_and_keeps_script_adoption(self):
        """REQ-S01-14：确认重写后该步及下游确认失效；已采用的自然稿不撤销。"""
        script = self.target.parent / '项目剧本' / '旧剧本.md'
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text('# 自然剧本\n旧稿\n', encoding='utf-8')
        selection = script_contract.natural_script_selection_path(self.project)
        save(selection, {'path': script.relative_to(self.project).as_posix(),
                         'sha256': hashlib.sha256(script.read_bytes()).hexdigest()})
        adopted = selection.read_bytes()
        restart_writing_preparation(self.project, '剧本大纲')
        result = self.reply('剧本大纲')
        self.reply('人物设定（角色卡）', '确认')
        state = json.loads(self.target.read_text(encoding='utf-8'))
        self.assertNotIn('revision', state)
        self.assertEqual(state['documents'][0], self.original['documents'][0])
        self.assertTrue(state['documents'][1]['confirmed'])
        self.assertEqual((self.target.parent / state['documents'][1]['path']).resolve(),
                         Path(result['preparation_path']).resolve())
        self.assertFalse(state['documents'][2]['confirmed'])
        self.assertNotEqual(state['documents'][2], self.original['documents'][2])
        self.assertEqual(script_contract.resolve_script_source(self.project), script.resolve())
        self.assertEqual(selection.read_bytes(), adopted)

    def test_cancel_and_failed_generation_preserve_adopted(self):
        restart_writing_preparation(self.project, '项目设定')
        with patch('writing_api.PoolAdapter.chat', return_value={'ok': False, 'error': 'timeout'}):
            result = writing_api.reply(self.project, '重写', publish=publish_stage_text)
        self.assertFalse(result['ok'])
        self.assertEqual(json.loads(self.target.read_text(encoding='utf-8'))['documents'], self.original['documents'])
        restart_writing_preparation(self.project, None)
        self.assertEqual(json.loads(self.target.read_text(encoding='utf-8')), self.original)

    def test_switching_model_alone_preserves_confirmations(self):
        stage_config.put(self.project, 'script', model='deepseek-v4-flash')
        _, state, texts = writing_api._preparation_state(self.project, writing_api._complete_brief(self.project))
        self.assertEqual(state, self.original)
        self.assertEqual(len(texts), 3)

    def test_native_claude_answers_revise_pending_document_before_confirmation(self):
        stage_config.put(self.project, 'script', model='claude-test')
        record = {'context_length': 200000, 'label': 'Claude Test', 'model': 'claude-test', 'provider': 'anthropic',
                  'wire_api': 'messages', 'base_url': 'https://api.anthropic.com',
                  'key_env': 'ANTHROPIC_API_KEY'}
        restart_writing_preparation(self.project, '项目设定')
        draft = '# 项目设定\n1.世界观是否全量呈现？\n2.是否补充空缺集数？\n待确认'
        revised = '# 项目设定\n世界观按需呈现；空缺集数安排决战前夜。\n待确认'
        answer = '1.按需呈现；2.补充'
        responses = [{'ok': True, 'text': value, 'data': {'stop_reason': 'end_turn'}}
                     for value in (draft, revised, '# 剧本大纲\n决战前夜。\n待确认')]
        with patch('writing_api.model_pool.pool', return_value={'claude-test': record}), \
             patch('writing_api.PoolAdapter.chat', side_effect=responses) as chat:
            first = writing_api.reply(self.project, '重新创作', publish=publish_stage_text)
            result = writing_api.reply(self.project, answer, publish=publish_stage_text)
            request = chat.call_args.args[0][0]['content']
            system = chat.call_args.kwargs['system']
            self.assertIn('当前待修改草稿', request)
            self.assertGreater(request.index(answer), request.index(draft))
            self.assertIn('不得把已经回答的问题再次列为待确认事项', system)
            self.assertEqual(result['preparation_stage'], '项目设定')
            self.assertEqual(result['preparation_path'], first['preparation_path'])
            self.assertEqual(Path(result['preparation_path']).read_text(encoding='utf-8').strip(), revised)
            state = json.loads(self.target.read_text(encoding='utf-8'))
            self.assertFalse(state['revision']['documents'][0]['confirmed'])
            self.assertEqual(state['documents'], self.original['documents'])
            next_result = writing_api.reply(self.project, '确认', publish=publish_stage_text)
        self.assertEqual(next_result['preparation_stage'], '剧本大纲')
        self.assertEqual(chat.call_count, 3)

    def test_stale_input_state_and_model_refuse_publication(self):
        for change in ('file', 'state', 'model'):
            with self.subTest(change=change):
                save(self.target, self.original)
                stage_config.put(self.project, 'script', model='gpt-4o')
                restart_writing_preparation(self.project, '角色卡')
                before = set(self.target.parent.rglob('*.md'))
                setting = self.target.parent / self.original['documents'][0]['path']
                old = setting.read_text(encoding='utf-8')
                def response(*args, **kwargs):
                    if change == 'file':
                        setting.write_text(old + '外部修改', encoding='utf-8')
                    elif change == 'state':
                        restart_writing_preparation(self.project, '项目设定')
                    else:
                        stage_config.put(self.project, 'script', model='deepseek-v4-flash')
                    return {'ok': True, 'text': '# 人物设定（角色卡）\n迟到结果。\n待确认'}
                with patch('writing_api.PoolAdapter.chat', side_effect=response):
                    with self.assertRaisesRegex(ValueError, '本次结果未采用'):
                        writing_api.reply(self.project, '重写', publish=publish_stage_text)
                self.assertEqual(set(self.target.parent.rglob('*.md')), before)
                setting.write_text(old, encoding='utf-8')

    def test_restart_rejects_missing_upstream_and_invalid_stage(self):
        state = dict(self.original, documents=[])
        save(self.target, state)
        for stage in ('剧本大纲', '角色卡', '自然剧本'):
            with self.subTest(stage=stage), self.assertRaises(ValueError):
                restart_writing_preparation(self.project, stage)

    def test_confirm_rewritten_character_supplies_new_text_to_script_request(self):
        restart_writing_preparation(self.project, '角色卡')
        self.reply('人物设定（角色卡）')
        with patch('writing_api.PoolAdapter.chat', side_effect=[
                {'ok': True, 'text': '{"next_stage": "自然剧本"}'},
                {'ok': True, 'text': '短回复'}]) as chat:
            writing_api.reply(self.project, '确认', publish=publish_stage_text)
        task = chat.call_args_list[-1].args[0][0]['content']
        confirmed = json.loads(task.split('<brief_complete>', 1)[1].split('</brief_complete>', 1)[0])['已确认阶段文件']
        self.assertIn('新版本', confirmed['角色卡'])
        self.assertIn('已确认的创作依据', confirmed['项目设定'])
        self.assertNotIn('revision', json.loads(self.target.read_text(encoding='utf-8')))

    def test_adoption_failure_restores_selection_and_pending_version(self):
        restart_writing_preparation(self.project, '项目设定')
        self.reply('项目设定')
        before = self.target.read_bytes()
        selection = script_contract.natural_script_selection_path(self.project)
        save(selection, {'path': 'original.md', 'sha256': 'original'})
        selection_before = selection.read_bytes()
        def fail_state(path, *args, **kwargs):
            if Path(path) == self.target:
                raise OSError('state publication failed')
            return publish_stage_text(path, *args, **kwargs)
        with patch('writing_api.PoolAdapter.chat', return_value={
                'ok': True, 'text': '# 剧本大纲\n新的大纲。\n待确认'}), \
             self.assertRaisesRegex(OSError, 'state publication failed'):
            writing_api.reply(self.project, '确认', publish=fail_state)
        self.assertEqual(self.target.read_bytes(), before)
        self.assertEqual(selection.read_bytes(), selection_before)

    def test_labels_distinguish_adopted_and_pending_versions(self):
        restart_writing_preparation(self.project, '剧本大纲')
        result = self.reply('剧本大纲')
        labels = writing_api.preparation_file_labels(self.project)
        old_path = self.target.parent / self.original['documents'][1]['path']
        self.assertEqual(labels[str(old_path.resolve())], '已确认')
        self.assertEqual(labels[str(Path(result['preparation_path']).resolve())], '重写待确认')

    def test_labels_keep_confirmed_revision_documents(self):
        """revision 里已确认的文档也要标「已确认」，不能因为走重写分支就从标签里消失。"""
        state = json.loads(self.target.read_text(encoding='utf-8'))
        confirmed_only = dict(self.original['documents'][1],
                              confirmed=True, path='剧本大纲/重写定稿.md')
        pending = dict(self.original['documents'][2],
                       confirmed=False, path='人物设定（角色卡）/待确认.md')
        state['revision'] = {'documents': [confirmed_only, pending]}
        save(self.target, state)
        confirmed_file = self.target.parent / confirmed_only['path']
        pending_file = self.target.parent / pending['path']
        confirmed_file.parent.mkdir(parents=True, exist_ok=True)
        pending_file.parent.mkdir(parents=True, exist_ok=True)
        confirmed_file.write_text('# 剧本大纲\n重写定稿。\n', encoding='utf-8')
        pending_file.write_text('# 人物设定（角色卡）\n草稿\n', encoding='utf-8')
        labels = writing_api.preparation_file_labels(self.project)
        self.assertEqual(labels[str(confirmed_file.resolve())], '已确认')
        self.assertEqual(labels[str(pending_file.resolve())], '重写待确认')
