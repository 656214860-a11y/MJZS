"""用户修改已确认准备文件后，显式重写使用当前正文并保留原采用状态。"""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import model_pool
from contract import project_stages
import stage_config
import writing_api
from orchestrator import writing_unconfirm
from agent.core import save
from stage_execution_service import publish_stage_text, restart_writing_preparation
from test_workflow import make_project
import test_writing_api


class WritingEditedRestartTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = make_project(temporary.name)
        stage_config.put(self.project, 'script', model='gpt-4o',
                         skills=['pipeline-script-preparation'])
        self.brief_path = project_stages.writing(self.project) / 'brief_complete.json'
        self.brief = test_writing_api.WritingApiTests.complete_brief()
        save(self.brief_path, self.brief)
        test_writing_api.WritingApiTests.confirmed_preparation(self.project)
        self.target, self.original, _ = writing_api._preparation_state(
            self.project, writing_api._complete_brief(self.project))
        self.paths = [self.target.parent / doc['path'] for doc in self.original['documents']]
        self.edited = ['# ' + stage + '\n用户修改后的独有正文：' + str(index) + '。\n'
                       for index, stage in enumerate(writing_api.PREPARATION_STAGES)]
        pool = patch('writing_api.model_pool.pool', return_value=model_pool.default_pool())
        pool.start()
        self.addCleanup(pool.stop)

    def edit_sources(self, changed_brief=False):
        save(self.target, self.original)
        brief = copy.deepcopy(self.brief)
        if changed_brief:
            brief['brief']['story_summary'] = '用户修改后的创意：港口追查失踪的姐姐。'
        save(self.brief_path, brief)
        for path, text in zip(self.paths, self.edited):
            path.write_text(text, encoding='utf-8')

    def state(self):
        return json.loads(self.target.read_text(encoding='utf-8'))

    def generate(self, index, creative='请按我的修改重写'):
        title = ('项目设定', '剧本大纲', '人物设定（角色卡）')[index]
        with patch('writing_api.PoolAdapter.chat', return_value={
                'ok': True, 'text': '# ' + title + '\n新版本：港口追查失踪的姐姐。\n待确认'}) as chat:
            result = writing_api.reply(self.project, creative, publish=publish_stage_text)
        self.assertTrue(result['ok'], result.get('error'))
        self.assertEqual(result.get('preparation_stage'), writing_api.PREPARATION_STAGES[index],
                         result.get('preparation_restart_pending'))
        return result, chat.call_args.args[0][0]['content']

    def assert_adopted_unchanged(self):
        state = self.state()
        self.assertEqual(state['documents'], self.original['documents'])
        self.assertEqual(state['brief_hash'], self.original['brief_hash'])
        for path, text in zip(self.paths, self.edited):
            self.assertEqual(path.read_text(encoding='utf-8'), text)

    def test_restart_each_edited_stage_uses_current_source_and_keeps_adopted(self):
        for changed_brief in (False, True):
            for index, stage in enumerate(writing_api.PREPARATION_STAGES):
                with self.subTest(changed_brief=changed_brief, stage=stage):
                    self.edit_sources(changed_brief)
                    restart_writing_preparation(self.project, stage)
                    self.assertTrue(writing_api.preparation_continuation(self.project, '请重写'))
                    result, prompt = self.generate(index)
                    self.assert_adopted_unchanged()
                    self.assertTrue(Path(result['preparation_path']).is_file())
                    for text in self.edited[:index + 1]:
                        self.assertIn(text, prompt)
                    if changed_brief:
                        self.assertIn('用户修改后的创意', prompt)
                    self.assertFalse(self.state()['revision']['documents'][-1]['confirmed'])

    def test_cancel_edited_restart_restores_original_record_before_or_after_generation(self):
        for changed_brief in (False, True):
            for generate in (False, True):
                with self.subTest(changed_brief=changed_brief, generate=generate):
                    self.edit_sources(changed_brief)
                    restart_writing_preparation(self.project, '剧本大纲')
                    if generate:
                        self.generate(1)
                    restart_writing_preparation(self.project, None)
                    self.assertEqual(self.state(), self.original)
                    self.assert_adopted_unchanged()

    def test_confirm_rewritten_outline_adopts_edited_prefix_and_current_brief(self):
        self.edit_sources(changed_brief=True)
        restart_writing_preparation(self.project, '剧本大纲')
        result, _ = self.generate(1)
        self.assert_adopted_unchanged()
        self.generate(2, '确认')
        state = self.state()
        self.assertNotIn('revision', state)
        fingerprint = hashlib.sha256(json.dumps(
            writing_api._complete_brief(self.project)['brief'], ensure_ascii=False,
            sort_keys=True).encode('utf-8')).hexdigest()
        self.assertEqual(state['brief_hash'], fingerprint)
        self.assertNotEqual(state['brief_hash'], self.original['brief_hash'])
        self.assertEqual(state['documents'][0]['sha256'],
                         hashlib.sha256(self.edited[0].encode('utf-8')).hexdigest())
        self.assertTrue(state['documents'][0]['confirmed'])
        self.assertTrue(state['documents'][1]['confirmed'])
        self.assertEqual((self.target.parent / state['documents'][1]['path']).resolve(),
                         Path(result['preparation_path']).resolve())
        self.assertFalse(state['documents'][2]['confirmed'])
        for path, text in zip(self.paths, self.edited):
            self.assertEqual(path.read_text(encoding='utf-8'), text)

    def test_chat_restart_and_second_confirmation_accept_edited_sources(self):
        for changed_brief in (False, True):
            with self.subTest(changed_brief=changed_brief):
                self.edit_sources(changed_brief)
                request = '重写剧本大纲'
                self.assertTrue(writing_api.preparation_continuation(self.project, request))
                with patch('writing_api.PoolAdapter.chat') as chat:
                    pending = writing_api.reply(self.project, request, publish=publish_stage_text)
                chat.assert_not_called()
                self.assertEqual(pending['preparation_restart_pending'], '剧本大纲')
                self.assert_adopted_unchanged()
                self.assertTrue(writing_api.preparation_continuation(self.project, '确认'))
                _, prompt = self.generate(1, '确认')
                for text in self.edited[:2]:
                    self.assertIn(text, prompt)
                self.assert_adopted_unchanged()

    def test_rewrite_still_rejects_unconfirmed_missing_empty_or_external_prefix(self):
        for issue in ('unconfirmed', 'missing', 'empty', 'outside'):
            with self.subTest(issue=issue):
                self.edit_sources(changed_brief=True)
                state = copy.deepcopy(self.original)
                if issue == 'unconfirmed':
                    state['documents'][0]['confirmed'] = False
                    save(self.target, state)
                elif issue == 'missing':
                    self.paths[0].unlink()
                elif issue == 'empty':
                    self.paths[0].write_text('  \n', encoding='utf-8')
                else:
                    outside = self.target.parent.parent / '外部设定.md'
                    outside.write_text(self.edited[0], encoding='utf-8')
                    state['documents'][0]['path'] = '../外部设定.md'
                    save(self.target, state)
                before = self.target.read_text(encoding='utf-8')
                with self.assertRaises(ValueError):
                    restart_writing_preparation(self.project, '剧本大纲')
                self.assertEqual(self.target.read_text(encoding='utf-8'), before)

    def test_missing_target_and_downstream_do_not_block_earlier_rewrite(self):
        for changed_brief in (False, True):
            for index in (0, 1):
                with self.subTest(changed_brief=changed_brief, index=index):
                    self.edit_sources(changed_brief)
                    for path in self.paths[index:]:
                        path.unlink()
                    restart_writing_preparation(self.project, writing_api.PREPARATION_STAGES[index])
                    self.generate(index)
                    self.assertEqual(self.state()['documents'], self.original['documents'])
                    for path in self.paths[index:]:
                        self.assertFalse(path.exists())

    def test_inputs_changed_during_edited_rewrite_still_refuse_publication(self):
        for change in ('prefix', 'target', 'brief'):
            with self.subTest(change=change):
                self.edit_sources(changed_brief=True)
                restart_writing_preparation(self.project, '剧本大纲')
                state_before = self.target.read_text(encoding='utf-8')
                markdown_before = set(self.target.parent.rglob('*.md'))

                def response(*_args, **_kwargs):
                    if change == 'brief':
                        brief = json.loads(self.brief_path.read_text(encoding='utf-8'))
                        brief['brief']['story_summary'] += '生成中又有修改。'
                        save(self.brief_path, brief)
                    else:
                        index = 0 if change == 'prefix' else 1
                        self.paths[index].write_text(self.edited[index] + '生成中又有修改。',
                                                     encoding='utf-8')
                    return {'ok': True, 'text': '# 剧本大纲\n迟到的新版本。\n待确认'}

                with patch('writing_api.PoolAdapter.chat', side_effect=response):
                    with self.assertRaisesRegex(ValueError, '本次结果未采用'):
                        writing_api.reply(self.project, '按当前内容开始生成', publish=publish_stage_text)
                self.assertEqual(self.target.read_text(encoding='utf-8'), state_before)
                self.assertEqual(set(self.target.parent.rglob('*.md')), markdown_before)

    def test_right_click_confirmation_keeps_current_revision_when_brief_changed(self):
        self.edit_sources(changed_brief=True)
        restart_writing_preparation(self.project, '剧本大纲')
        result, _ = self.generate(1)
        writing_unconfirm.confirm_preparation_document(
            self.project, '剧本大纲', result['preparation_path'], publish=publish_stage_text)
        self.assert_adopted_unchanged()
        state = self.state()
        self.assertEqual(len(state['revision']['documents']), 2)
        self.assertTrue(state['revision']['documents'][-1]['confirmed'])
        self.assertTrue(writing_api.preparation_continuation(self.project, '继续'))
        self.generate(2, '继续')

    def test_chat_restart_uses_edited_prefix_when_target_has_no_confirmed_version(self):
        for changed_brief in (False, True):
            for pending_target in (False, True):
                with self.subTest(changed_brief=changed_brief, pending_target=pending_target):
                    self.edit_sources(changed_brief)
                    state = copy.deepcopy(self.original)
                    state['documents'] = state['documents'][:2 if pending_target else 1]
                    if pending_target:
                        state['documents'][-1]['confirmed'] = False
                    else:
                        self.paths[1].unlink()
                    self.paths[2].unlink()
                    save(self.target, state)
                    request = '重写剧本大纲'
                    self.assertTrue(writing_api.preparation_continuation(self.project, request))
                    result, prompt = self.generate(1, request)
                    self.assertNotIn('preparation_restart_pending', result)
                    self.assertIn(self.edited[0], prompt)
                    if changed_brief:
                        self.assertIn('用户修改后的创意', prompt)
                    self.assertEqual(self.state()['documents'], state['documents'])
                    self.assertEqual(self.state()['brief_hash'], self.original['brief_hash'])
                    self.assertFalse(self.state()['revision']['documents'][-1]['confirmed'])

    def test_failed_state_publication_does_not_mutate_cached_confirmation_record(self):
        for action in ('cancel_revision', 'register_chat_restart'):
            with self.subTest(action=action):
                self.edit_sources(changed_brief=True)
                if action == 'cancel_revision':
                    restart_writing_preparation(self.project, '剧本大纲')
                cached = writing_api.read_json(self.target)
                before = copy.deepcopy(cached)
                disk_before = self.target.read_bytes()

                def fail_publish(*_args, **_kwargs):
                    raise OSError('模拟状态发布失败')

                with self.assertRaisesRegex(OSError, '模拟状态发布失败'):
                    if action == 'cancel_revision':
                        writing_api.restart_preparation(self.project, None, publish=fail_publish)
                    else:
                        writing_api.reply(self.project, '重写剧本大纲', publish=fail_publish)
                self.assertEqual(self.target.read_bytes(), disk_before)
                self.assertEqual(cached, before)
                self.assertEqual(writing_api.read_json(self.target), before)

    def test_chat_rewrite_of_edited_pending_revision_uses_its_current_draft(self):
        for changed_prefix in (False, True):
            with self.subTest(changed_prefix=changed_prefix):
                self.edit_sources(changed_brief=True)
                restart_writing_preparation(self.project, '剧本大纲')
                first, _ = self.generate(1)
                draft = '# 剧本大纲\n用户手改的重写新稿：姐姐已成为港口守望者。\n'
                Path(first['preparation_path']).write_text(draft, encoding='utf-8')
                setting = self.edited[0]
                if changed_prefix:
                    setting += '用户又补充：港口藏在雾中。\n'
                    self.paths[0].write_text(setting, encoding='utf-8')
                request = '重写大纲'
                self.assertTrue(writing_api.preparation_continuation(self.project, request))
                result, prompt = self.generate(1, request)
                self.assertNotIn('preparation_restart_pending', result)
                self.assertNotIn('pending_restart', self.state())
                self.assertIn(setting, prompt)
                self.assertIn(draft, prompt)
                self.assertNotIn(self.edited[1], prompt)
                self.assertEqual(self.state()['documents'], self.original['documents'])
                self.assertEqual(self.state()['brief_hash'], self.original['brief_hash'])
                self.assertFalse(self.state()['revision']['documents'][-1]['confirmed'])


if __name__ == '__main__':
    unittest.main()
