# -*- coding: utf-8 -*-
"""剧本页 API 直连回归。运行：python test_writing_api.py"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import stage_config
import writing_api
import writing_tools
import model_pool
import script_contract
import project_stages
from stage_execution_service import publish_stage_text
from model_router import PoolAdapter
import token_saver
from test_workflow import make_project


class WritingApiTests(unittest.TestCase):
    @staticmethod
    def confirmed_preparation(project):
        """四角色专项的前置 fixture：三份真实文件及各自确认版本。"""
        import hashlib
        from agent.core import save
        target, state, _ = writing_api._preparation_state(project, writing_api._complete_brief(project))
        target.parent.mkdir(parents=True, exist_ok=True)
        documents = []
        for stage in writing_api.PREPARATION_STAGES:
            path = project_stages.writing(project) / (stage + '.md')
            text = '# ' + stage + '\n已确认的创作依据：雨夜照相馆。\n'
            path.write_text(text, encoding='utf-8')
            documents.append({'stage': stage, 'path': path.name, 'confirmed': True,
                              'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest()})
        state['documents'] = documents
        save(target, state)

    def test_brief_alone_generates_setting_before_four_roles(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            stage_config.put(project, 'script', model='gpt-4o')
            from agent.core import save
            save(project_stages.writing(project) / 'brief_complete.json', self.complete_brief())
            self.assertTrue(writing_api.preparation_continuation(project, '重试'))
            with patch('writing_api.model_pool.pool', return_value=model_pool.default_pool()), \
                 patch('writing_api._hollmwood_reply') as roles, \
                 patch('writing_api.PoolAdapter.chat', return_value={
                     'ok': True, 'text': '# 项目设定\n都市雨夜，少年追查底片。\n待确认'}) as chat:
                result = writing_api.reply(project, '开始创作', publish=publish_stage_text)
            roles.assert_not_called()
            self.assertTrue(result['ok'])
            self.assertEqual(result['preparation_stage'], '项目设定')
            self.assertEqual(chat.call_count, 1)
            self.assertTrue(writing_api.preparation_continuation(project, '确认'))
            self.assertTrue(writing_api.preparation_continuation(project, '请修改设定中的地名'))
            self.assertFalse(writing_api.preparation_continuation(project, '故事梗概：新故事'))
            self.assertTrue(Path(result['preparation_path']).is_file())
            self.assertFalse((project_stages.writing(project) / 'script_raw.md').exists())

    def test_preparation_requires_each_confirmation_and_hands_all_documents_to_roles(self):
        import json
        from agent.core import save
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            stage_config.put(project, 'script', model='gpt-4o')
            save(project_stages.writing(project) / 'brief_complete.json', self.complete_brief())
            answers = [{'ok': True, 'text': text} for text in (
                '# 项目设定\n旧设定。\n待确认', '# 项目设定\n修订设定。\n待确认',
                '# 剧本大纲\n追查底片的三幕故事。\n待确认', '# 人物设定（角色卡）\n阿远的目标与弱点。\n待确认')]
            with patch('writing_api.model_pool.pool', return_value=model_pool.default_pool()), \
                 patch('writing_api.PoolAdapter.chat', side_effect=answers) as chat, \
                 patch('writing_api._hollmwood_reply', return_value={'ok': True, 'text': '自然剧本'}) as roles:
                first = writing_api.reply(project, '开始', publish=publish_stage_text)
                revised = writing_api.reply(project, '不要确认，先改设定', publish=publish_stage_text)
                self.assertEqual(first['preparation_path'], revised['preparation_path'])
                self.assertEqual(revised['preparation_stage'], '项目设定')
                outline = writing_api.reply(project, '确认', publish=publish_stage_text)
                self.assertEqual(outline['preparation_stage'], '剧本大纲')
                self.assertIn('修订设定', chat.call_args.args[0][0]['content'])
                cards = writing_api.reply(project, '确认', publish=publish_stage_text)
                self.assertEqual(cards['preparation_stage'], '角色卡')
                roles.assert_not_called()
                result = writing_api.reply(project, '确认', publish=publish_stage_text)
            self.assertEqual(result['text'], '自然剧本')
            roles.assert_called_once()
            documents = roles.call_args.args[4]['已确认阶段文件']
            self.assertEqual(list(documents), list(writing_api.PREPARATION_STAGES))
            self.assertIn('修订设定', documents['项目设定'])
            self.assertIn('阿远', documents['角色卡'])
            state = json.loads((project_stages.writing(project) / 'preparation_state.json').read_text(encoding='utf-8'))
            self.assertTrue(all(item['confirmed'] for item in state['documents']))
            self.assertEqual(len({item['path'] for item in state['documents']}), 3)
            self.assertEqual(chat.call_count, 4)

    def test_failed_next_stage_resumes_after_persisted_confirmation(self):
        from agent.core import save
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            stage_config.put(project, 'script', model='gpt-4o', hollmwood_enabled=False)
            save(project_stages.writing(project) / 'brief_complete.json', self.complete_brief())
            with patch('writing_api.model_pool.pool', return_value=model_pool.default_pool()), \
                 patch('writing_api._hollmwood_reply') as roles, \
                 patch('writing_api.PoolAdapter.chat', side_effect=[
                     {'ok': True, 'text': '# 项目设定\n雨夜。\n待确认'},
                     {'ok': False, 'error': 'network'},
                     {'ok': True, 'text': '# 剧本大纲\n追查底片。\n待确认'}]):
                writing_api.reply(project, '开始', publish=publish_stage_text)
                failed = writing_api.reply(project, '确认', publish=publish_stage_text)
                self.assertFalse(failed['ok'])
                retry = writing_api.reply(project, '重试', publish=publish_stage_text)
            self.assertEqual(retry['preparation_stage'], '剧本大纲')
            roles.assert_not_called()

    def test_incomplete_preparation_output_never_publishes_or_advances(self):
        from agent.core import save
        for response in ({'ok': True, 'text': '# 项目设定\n雨夜。\n待确认', 'response_meta': {'finish_reason': 'length'}},
                         {'ok': True, 'text': '# 自然剧本\n不允许跳阶段。\n待确认'},
                         {'ok': True, 'text': '# 项目设定\n待确认'}):
            with self.subTest(response=response), tempfile.TemporaryDirectory() as td:
                project = make_project(td)
                stage_config.put(project, 'script', model='gpt-4o')
                save(project_stages.writing(project) / 'brief_complete.json', self.complete_brief())
                with patch('writing_api.model_pool.pool', return_value=model_pool.default_pool()), \
                     patch('writing_api.PoolAdapter.chat', return_value=response), \
                     patch('writing_api._hollmwood_reply') as roles:
                    result = writing_api.reply(project, '开始', publish=publish_stage_text)
                self.assertFalse(result['ok'])
                self.assertFalse((project_stages.writing(project) / 'preparation_state.json').exists())
                self.assertEqual(list(project_stages.writing(project).rglob('*.md')), [])
                roles.assert_not_called()

    def test_deleted_or_modified_confirmed_document_blocks_roles(self):
        from agent.core import save
        for deleted in (True, False):
            with self.subTest(deleted=deleted), tempfile.TemporaryDirectory() as td:
                project = make_project(td)
                stage_config.put(project, 'script', model='gpt-4o')
                save(project_stages.writing(project) / 'brief_complete.json', self.complete_brief())
                self.confirmed_preparation(project)
                path = project_stages.writing(project) / '项目设定.md'
                if deleted:
                    path.unlink()
                else:
                    path.write_text('未经确认的改动', encoding='utf-8')
                with patch('writing_api.model_pool.pool', return_value=model_pool.default_pool()), \
                     patch('writing_api.PoolAdapter.chat') as chat, patch('writing_api._hollmwood_reply') as roles:
                    with self.assertRaisesRegex(ValueError, '原确认失效'):
                        writing_api.reply(project, '开始', publish=publish_stage_text)
                chat.assert_not_called()
                roles.assert_not_called()

    def test_changed_brief_restarts_preparation(self):
        from agent.core import save
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            stage_config.put(project, 'script', model='gpt-4o')
            brief = self.complete_brief()
            save(project_stages.writing(project) / 'brief_complete.json', brief)
            self.confirmed_preparation(project)
            brief['brief']['story_summary'] = '全新的故事'
            save(project_stages.writing(project) / 'brief_complete.json', brief)
            with patch('writing_api.model_pool.pool', return_value=model_pool.default_pool()), \
                 patch('writing_api.PoolAdapter.chat', return_value={'ok': True, 'text': '# 项目设定\n新世界。\n待确认'}), \
                 patch('writing_api._hollmwood_reply') as roles:
                result = writing_api.reply(project, '确认', publish=publish_stage_text)
            self.assertEqual(result['preparation_stage'], '项目设定')
            roles.assert_not_called()

    def test_cancelled_preparation_response_does_not_publish(self):
        from agent.core import save
        from hollmwood_roles import RoleCancelledError
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            stage_config.put(project, 'script', model='gpt-4o')
            save(project_stages.writing(project) / 'brief_complete.json', self.complete_brief())
            stopped = False
            def respond(*_args, **_kwargs):
                nonlocal stopped
                stopped = True
                return {'ok': True, 'text': '# 项目设定\n雨夜。\n待确认'}
            with patch('writing_api.model_pool.pool', return_value=model_pool.default_pool()), \
                 patch('writing_api.PoolAdapter.chat', side_effect=respond):
                with self.assertRaises(RoleCancelledError):
                    writing_api.reply(project, '开始', publish=publish_stage_text, cancelled=lambda: stopped)
            self.assertFalse((project_stages.writing(project) / 'preparation_state.json').exists())
            self.assertEqual(list(project_stages.writing(project).rglob('*.md')), [])

    def test_truncated_actor_stream_fails_without_publishing_script(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            stage_config.put(project, 'script', model='gpt-4o')
            writing = project / 'writing'
            writing.mkdir(exist_ok=True)
            (writing / 'brief_complete.json').write_text(
                __import__('json').dumps(self.complete_brief(), ensure_ascii=False), encoding='utf-8')
            answers = ('计划', '编剧稿', 'APPROVED', '编辑稿', 'APPROVED')
            self.confirmed_preparation(project)
            with patch('writing_api.model_pool.pool', return_value=model_pool.default_pool()), \
                 patch('writing_api.PoolAdapter.chat',
                       side_effect=[{'ok': True, 'text': text} for text in answers]) as chat, \
                 patch('writing_api.PoolAdapter.stream', return_value={
                     'ok': True, 'text': '未完成的演员稿',
                     'response_meta': {'finish_reason': 'length'}}) as stream, \
                 patch('writing_api._write_script_raw') as publish:
                result = writing_api.reply(project, '开始创作', stream=lambda _: None,
                                           publish=publish_stage_text)
            self.assertFalse(result['ok'])
            self.assertIn('actor 角色执行失败', result['error'])
            self.assertIn('finish_reason=length', result['error'])
            self.assertEqual(chat.call_count, 5)
            self.assertEqual(stream.call_count, 1)
            publish.assert_not_called()

    @staticmethod
    def complete_brief():
        return script_contract.brief_document({
            'story_summary': '少年在雨夜照相馆发现会说话的底片。',
            'main_characters': '少年阿远、照相馆老板。',
            'genre': '都市奇幻', 'length': '单集 60 秒',
        })

    @staticmethod
    def natural_script(length):
        return ('雨夜的照相馆里，阿远推开门，老板抬头看见那张会发光的旧底片。'
                '阿远压低声音说：“它显出了明天的雨。”老板握紧相机，决定陪他追查真相。\n') * length

    def test_confirmed_preparation_runs_four_roles_and_writes_human_readable_script_raw(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            stage_config.put(project, 'script', model='gpt-4o')
            writing = project / 'writing'
            writing.mkdir(exist_ok=True)
            brief = script_contract.brief_document({
                'story_summary': '少年在雨夜照相馆发现会说话的底片。',
                'main_characters': '少年阿远、照相馆老板。',
                'genre': '都市奇幻',
                'length': '单集 60 秒',
            })
            (writing / 'brief_complete.json').write_text(
                __import__('json').dumps(brief, ensure_ascii=False), encoding='utf-8')
            answers = ('节奏计划', '编剧稿', 'APPROVED 编剧通过', '编辑稿',
                       'APPROVED 编辑通过', '演员稿', 'APPROVED 演员通过')
            self.confirmed_preparation(project)
            skill = Path(td) / 'SKILL.md'
            skill.write_text('---\nname: api-role-test\n---\n四角色共用内联技能正文', encoding='utf-8')
            with patch('writing_api.model_pool.pool', return_value=model_pool.default_pool()), \
                 patch('workflow_settings.skills_of', return_value=[str(skill)]), \
                 patch('writing_api.PoolAdapter.chat',
                       side_effect=[{'ok': True, 'text': text} for text in answers]) as chat:
                result = writing_api.reply(project, '开始创作', publish=publish_stage_text)
            self.assertTrue(result['ok'])
            self.assertEqual(result['text'], '演员稿')
            self.assertEqual(chat.call_count, 7)
            writer_system = chat.call_args_list[1].kwargs['system']
            self.assertIn('<skill name="api-role-test">', writer_system)
            self.assertIn('四角色共用内联技能正文', writer_system)
            self.assertIn(f'<!-- 来源: {skill.resolve()} -->', writer_system)
            for index, call in enumerate(chat.call_args_list):
                self.assertEqual(call.kwargs['system'].count('四角色共用内联技能正文'), 1)
                self.assertEqual(call.kwargs['system'].count('<skill name="api-role-test">'), 1)
                self.assertNotIn('请先完整读取并遵循本地技能文件', call.kwargs['system'])
                self.assertNotIn('全局节奏模板', call.kwargs['system'])
                prompt = call.args[0][0]['content']
                self.assertEqual(prompt.count('<brief_complete>'), 1)
                self.assertIn('单集 60 秒', prompt)
                self.assertIn('已确认阶段文件', prompt)
                self.assertIn('已确认的创作依据', prompt)
                if index:
                    self.assertEqual(prompt.count('<director_instruction>\n节奏计划'), 1)
            self.assertEqual((project_stages.writing(project) / 'script_raw.md').read_text(encoding='utf-8'), '演员稿\n')
            self.assertEqual(len(list((project / 'logs').glob('hollmwood_step_*.log'))), 7)
            self.assertEqual(len(list((project / 'logs' / 'model_diagnostics').glob('*.json'))), 7)

    def test_disabled_hollmwood_uses_direct_api_with_complete_brief_and_auto_saves(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            stage_config.put(project, 'script', model='gpt-4o', hollmwood_enabled=False)
            writing = project / 'writing'; writing.mkdir(exist_ok=True)
            (writing / 'brief_complete.json').write_text(__import__('json').dumps(self.complete_brief(), ensure_ascii=False), encoding='utf-8')
            text = self.natural_script(20)
            self.confirmed_preparation(project)
            with patch('writing_api.model_pool.pool', return_value=model_pool.default_pool()), \
                 patch('writing_api._hollmwood_reply') as four_roles, \
                 patch('writing_api.PoolAdapter.chat', return_value={'ok': True, 'text': text}) as chat:
                result = writing_api.reply(project, '开始创作', publish=publish_stage_text)
            four_roles.assert_not_called()
            self.assertIn('<brief_complete>', chat.call_args.args[0][0]['content'])
            self.assertTrue(result['script_raw_path'])
            self.assertFalse(result['hollmwood_enabled'])
            self.assertEqual((project_stages.writing(project) / 'script_raw.md').read_text(encoding='utf-8'), text.strip() + '\n')

    def test_complete_brief_reads_formal_json_through_cache_and_observes_atomic_republish(self):
        """确认简报是正式项目数据：缓存读必须随原子发布看到新值。"""
        from agent.core import save
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            target = project_stages.writing(project) / 'brief_complete.json'
            first = self.complete_brief()
            save(target, first)
            self.assertEqual(writing_api._complete_brief(project)['brief']['story_summary'], first['brief']['story_summary'])
            second = script_contract.brief_document({
                'story_summary': '雨后的少年发现底片会预告未来。',
                'main_characters': '少年阿远、照相馆老板。',
                'genre': '都市奇幻', 'length': '单集 60 秒',
            })
            save(target, second)
            self.assertEqual(writing_api._complete_brief(project)['brief']['story_summary'], second['brief']['story_summary'])

    def test_disabled_auto_save_rejects_structured_or_short_text_and_deduplicates_same_text(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            short = {'ok': True, 'text': '短回复'}
            structured = {'ok': True, 'text': '{"source_script": "结构化"}' * 100}
            self.assertNotIn('script_raw_path', writing_api._auto_save_script_raw(project, short))
            self.assertNotIn('script_raw_path', writing_api._auto_save_script_raw(project, structured))
            text = self.natural_script(20).strip()
            first = writing_api._auto_save_script_raw(project, {'ok': True, 'text': text}, publish=publish_stage_text)
            with patch('writing_api._write_script_raw') as write:
                duplicate = writing_api._auto_save_script_raw(project, {'ok': True, 'text': text}, publish=publish_stage_text)
            write.assert_not_called()
            self.assertEqual(duplicate['script_raw_path'], first['script_raw_path'])

    def test_script_raw_save_notice_tracks_the_reply_mode(self):
        from desktop import script_raw_saved_notice
        self.assertEqual(script_raw_saved_notice(True), '四角色剧本已保存：script_raw.md')
        self.assertEqual(script_raw_saved_notice(False), '剧本已自动保存：script_raw.md')

    def test_cancelled_hollmwood_does_not_write_script_raw(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            stage_config.put(project, 'script', model='gpt-4o')
            writing = project / 'writing'; writing.mkdir(exist_ok=True)
            brief = script_contract.brief_document({
                'story_summary': '少年在雨夜照相馆发现会说话的底片。',
                'main_characters': '少年阿远、照相馆老板。',
                'genre': '都市奇幻', 'length': '单集 60 秒',
            })
            (writing / 'brief_complete.json').write_text(
                __import__('json').dumps(brief, ensure_ascii=False), encoding='utf-8')
            with patch('writing_api.model_pool.pool', return_value=model_pool.default_pool()), \
                 patch('writing_api.PoolAdapter.chat') as chat:
                with self.assertRaises(__import__('hollmwood_roles').RoleCancelledError):
                    writing_api.reply(project, '开始创作', cancelled=lambda: True)
            chat.assert_not_called()
            self.assertFalse((project_stages.writing(project) / 'script_raw.md').exists())

    def test_hollmwood_role_network_failure_returns_recoverable_result(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            stage_config.put(project, 'script', model='gpt-4o')
            writing = project / 'writing'; writing.mkdir(exist_ok=True)
            brief = script_contract.brief_document({'story_summary': '雨夜照相馆。', 'main_characters': '阿远。',
                                                    'genre': '都市奇幻', 'length': '60 秒'})
            (writing / 'brief_complete.json').write_text(__import__('json').dumps(brief, ensure_ascii=False), encoding='utf-8')
            self.confirmed_preparation(project)
            with patch('writing_api.model_pool.pool', return_value=model_pool.default_pool()), \
                 patch('writing_api.PoolAdapter.chat', return_value={'ok': False, 'error': 'URLError：TLS EOF'}):
                result = writing_api.reply(project, '开始创作', publish=publish_stage_text)
            self.assertFalse(result['ok'])
            self.assertIn('director 角色执行失败', result['error'])
            self.assertFalse((project_stages.writing(project) / 'script_raw.md').exists())

    def test_claude_timeout_window_allows_thinking_and_visible_output(self):
        self.assertEqual(writing_api.WRITING_REQUEST_TIMEOUT, 180)

    def test_explicit_api_model_uses_pool_adapter_with_workflow_skill(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            stage_config.put(project, 'script', model='gpt-4o')
            skill = Path(td) / 'SKILL.md'
            skill.write_text('---\nname: api-direct-test\n---\n直连共用内联技能正文', encoding='utf-8')
            with patch('writing_api.model_pool.pool', return_value=model_pool.default_pool()), \
                 patch('workflow_settings.skills_of', return_value=[str(skill)]), \
                 patch('model_router.PoolAdapter.chat', return_value={'ok': True, 'text': '收到'}) as chat:
                self.assertEqual(writing_api.selected_model(project)[0], 'gpt-4o')
                result = writing_api.reply(project, '照相馆里有一张会说话的底片')
            self.assertTrue(result['ok'])
            self.assertIn('本次创意输入', chat.call_args.args[0][0]['content'])
            self.assertIn('本次创意输入', chat.call_args.kwargs['system'] + chat.call_args.args[0][0]['content'])
            self.assertIn('<skill name="api-direct-test">', chat.call_args.kwargs['system'])
            self.assertIn('直连共用内联技能正文', chat.call_args.kwargs['system'])
            self.assertIn(f'<!-- 来源: {skill.resolve()} -->', chat.call_args.kwargs['system'])
            self.assertNotIn('请先完整读取并遵循本地技能文件', chat.call_args.kwargs['system'])

    def test_desktop_agent_is_not_treated_as_an_api_model(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            stage_config.put(project, 'script', model='claude-desktop')
            self.assertEqual(writing_api.selected_model(project), ('', {}))

    def test_thinking_block_is_never_rendered_as_chat_text(self):
        data={'content':[{'type':'thinking','thinking':'internal','signature':'secret'},
                         {'type':'text','text':'可展示正文'}]}
        self.assertEqual(token_saver.anthropic_text(data),'可展示正文')
        self.assertEqual(token_saver.anthropic_text({'content':[data['content'][0]]}),'')

    def test_claude_messages_can_read_and_save_with_project_tools(self):
        with tempfile.TemporaryDirectory() as td:
            project=make_project(td)
            stage_config.put(project, 'script', model='claude-test')
            record={'label':'Claude Test','model':'claude-test','provider':'anthropic','wire_api':'messages',
                    'base_url':'https://api.anthropic.com','key_env':'ANTHROPIC_API_KEY'}
            responses = [
                {'ok':True, 'data':{'content':[{'type':'tool_use','id':'read-1',
                    'name':'read_project_writing_file','input':{'path':'writing/项目接续.JSON'}}]}},
                {'ok':True, 'data':{'content':[{'type':'tool_use','id':'write-1',
                    'name':'write_project_writing_file','input':{'path':'writing/剧本初稿.md','content':'# 第一集'}}]}},
                {'ok':True, 'text':'已保存', 'data':{'content':[{'type':'text','text':'已保存'}]}},
            ]
            (project/'writing').mkdir(exist_ok=True)
            (project/'writing'/'项目接续.JSON').write_text('{}',encoding='utf-8')
            with patch('writing_api.model_pool.pool', return_value={'claude-test':record}), \
                 patch('writing_api.PoolAdapter.chat', side_effect=responses) as chat:
                result=writing_api.reply(project,'测试创意', publish=publish_stage_text)
            self.assertTrue(result['ok'])
            self.assertEqual(chat.call_count,3)
            self.assertEqual(chat.call_args_list[0].kwargs['options']['tools'],writing_tools.definitions())
            self.assertIn('资产清单属于后续资产阶段',chat.call_args_list[0].kwargs['system'])
            self.assertEqual((project_stages.writing(project)/'剧本初稿.md').read_text(encoding='utf-8'),'# 第一集')

    def test_script_tools_exclude_assets_and_keep_progress_read_only(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);writing=root/'writing';writing.mkdir()
            (writing/'设定.md').write_text('剧本设定',encoding='utf-8')
            progress=root/'data'/'项目接续.json';progress.parent.mkdir()
            progress.write_text('{"current_stage":"00_script"}',encoding='utf-8')
            asset=root/'episode'/'assets.json';asset.parent.mkdir()
            asset.write_text('{}',encoding='utf-8')

            listed=writing_tools.list_files(root)

            self.assertIn('data/项目接续.json',listed)
            self.assertNotIn('episode/assets.json',listed)
            self.assertEqual(writing_tools.read_file(root,'data/项目接续.json')['content'],'{"current_stage":"00_script"}')
            with self.assertRaises(ValueError):writing_tools.read_file(root,'episode/assets.json')
            with self.assertRaises(ValueError):writing_tools.write_file(root,'episode/assets.json','{}')
            self.assertNotIn('资产',str(writing_tools.definitions()))

    def test_legacy_writing_path_is_read_only_and_new_write_uses_current_stage(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);legacy=root/'writing';legacy.mkdir()
            (legacy/'历史剧本.md').write_text('旧稿',encoding='utf-8')
            self.assertEqual(writing_tools.read_file(root,'writing/历史剧本.md')['content'],'旧稿')
            result=writing_tools.write_file(root,'writing/新剧本.md','新稿', publish=publish_stage_text)
            self.assertTrue(result.ok)
            saved=result.data
            current=project_stages.writing(root)/'新剧本.md'
            self.assertTrue(current.is_file())
            self.assertEqual(current.read_text(encoding='utf-8'),'新稿')
            self.assertFalse((legacy/'新剧本.md').exists())
            self.assertTrue(saved['path'].startswith('01剧本准备/'))

    def test_writing_tool_rejects_blank_model_output(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            with self.assertRaisesRegex(ValueError, '正文不能为空'):
                writing_tools.write_file(root, 'writing/空剧本.md', ' \n\t ')
            self.assertFalse((project_stages.writing(root)/'空剧本.md').exists())

    def test_writing_tool_maps_disk_failure_but_keeps_programmer_error_visible(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            disk=lambda *_args: (_ for _ in ()).throw(OSError('disk'))
            result=writing_tools.write_file(root, 'writing/失败.md', '正文', publish=disk)
            self.assertFalse(result.ok)
            self.assertIn('未能保存', result.reason)
            broken=lambda *_args: (_ for _ in ()).throw(TypeError('bug'))
            with self.assertRaises(TypeError):
                writing_tools.write_file(root, 'writing/程序错误.md', '正文', publish=broken)

    def test_hollmwood_publication_rejects_blank_script(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with self.assertRaisesRegex(ValueError, '空正文'):
                writing_api._write_script_raw(root, ' \n')
            self.assertFalse((project_stages.writing(root) / 'script_raw.md').exists())

    def test_only_repeated_identical_write_request_is_paused(self):
        class Adapter:
            def __init__(self): self.calls = 0
            def chat(self, messages, options=None, model='', system=''):
                self.calls += 1
                return {'ok':True, 'data':{'content':[{'type':'tool_use','id':'same-%d' % self.calls,
                    'name':'write_project_writing_file','input':{'path':'writing/剧本.md','content':'同一内容'}}]}}
        with tempfile.TemporaryDirectory() as td:
            project=make_project(td); adapter=Adapter()
            result=writing_api._reply_with_project_tools(adapter,'claude-test','system','任务',project)
        self.assertFalse(result['ok'])
        self.assertEqual(result['reason'],'repeated_tool_request')
        self.assertEqual(adapter.calls,3)

    def test_repeated_read_gets_a_notice_and_can_continue_to_visible_text(self):
        class Adapter:
            def __init__(self): self.calls = []
            def chat(self, messages, options=None, model='', system=''):
                self.calls.append(messages)
                if len(self.calls) <= 4:
                    return {'ok':True, 'data':{'content':[{'type':'tool_use','id':'read-%d' % len(self.calls),
                        'name':'list_project_writing_files','input':{}}]}}
                return {'ok':True, 'text':'已整理并继续处理。',
                        'data':{'content':[{'type':'text','text':'已整理并继续处理。'}]}}
        with tempfile.TemporaryDirectory() as td:
            project=make_project(td); adapter=Adapter()
            result=writing_api._reply_with_project_tools(adapter,'claude-test','system','任务',project)
        self.assertTrue(result['ok'])
        self.assertEqual(result['text'],'已整理并继续处理。')
        self.assertEqual(len(adapter.calls),5)
        second_repeat = adapter.calls[2][-1]['content'][0]['content']
        self.assertIn('repeat_notice', second_repeat)

    def test_thinking_only_response_continues_once_without_tools(self):
        class Adapter:
            def __init__(self): self.calls = []
            def chat(self, messages, options=None, model='', system=''):
                self.calls.append((messages, options))
                if len(self.calls) == 1:
                    return {'ok': True, 'text': '', 'data': {'content': [
                        {'type': 'thinking', 'thinking': 'hidden', 'signature': 'signed'}]}}
                return {'ok': True, 'text': '可见正文', 'data': {'content': [
                    {'type': 'text', 'text': '可见正文'}]}}
        with tempfile.TemporaryDirectory() as td:
            adapter = Adapter()
            result = writing_api._reply_with_project_tools(adapter, 'claude-test', 'system', '任务', td)
        self.assertTrue(result['ok'])
        self.assertEqual(result['text'], '可见正文')
        self.assertEqual(len(adapter.calls), 2)
        self.assertNotIn('tools', adapter.calls[1][1])
        self.assertEqual(adapter.calls[1][0][-2]['role'], 'assistant')
        self.assertEqual(adapter.calls[0][1]['max_tokens'], writing_api.CLAUDE_VISIBLE_OUTPUT_TOKENS)

    def test_empty_claude_response_retries_once_then_records_failure(self):
        class Adapter:
            def __init__(self): self.calls = 0
            def chat(self, messages, options=None, model='', system=''):
                self.calls += 1
                return {'ok': True, 'status': 200, 'text': '', 'data': {'content': []}, 'usage': {}}
        with tempfile.TemporaryDirectory() as td, patch.object(writing_api, 'EMPTY_RESPONSE_LOG', Path(td) / 'meta.log'):
            adapter = Adapter()
            result = writing_api._reply_with_project_tools(adapter, 'claude-test', 'system', '任务', td)
            self.assertTrue((Path(td) / 'meta.log').is_file())
        self.assertEqual(adapter.calls, 2)
        self.assertEqual(result['text'], '')

    def test_empty_claude_response_retries_once_for_visible_text(self):
        class Adapter:
            def __init__(self): self.calls = []
            def chat(self, messages, options=None, model='', system=''):
                self.calls.append((messages, options))
                if len(self.calls) == 1:
                    return {'ok': True, 'status': 200, 'text': '', 'data': {'content': []}, 'usage': {}}
                return {'ok': True, 'status': 200, 'text': '补发的正文',
                        'data': {'content': [{'type': 'text', 'text': '补发的正文'}]}}
        with tempfile.TemporaryDirectory() as td:
            adapter = Adapter()
            result = writing_api._reply_with_project_tools(adapter, 'claude-test', 'system', '任务', td)
        self.assertTrue(result['ok'])
        self.assertEqual(result['text'], '补发的正文')
        self.assertEqual(len(adapter.calls), 2)
        self.assertNotIn('tools', adapter.calls[1][1])
        self.assertEqual(adapter.calls[0][0][-1]['role'], 'user')
        self.assertEqual(adapter.calls[1][0][-1]['role'], 'user')

    def test_claude_history_is_bounded_without_deleting_local_messages(self):
        rows = [
            {'role': 'user', 'text': '早期设定' * 4000},
            {'role': 'assistant', 'text': '最近确认内容'},
        ]
        history = writing_api._recent_chat_history(rows)
        self.assertIn('最近确认内容', history)
        self.assertLessEqual(len(history), writing_api.CHAT_HISTORY_CHAR_LIMIT + 30)

    def test_long_history_keeps_an_earlier_excerpt_and_recent_turns(self):
        rows = ([{'role': 'user', 'text': '世界观设定：雨城每晚停电一次'}]
                + [{'role': 'assistant', 'text': '中段讨论' * 300} for _ in range(8)]
                + [{'role': 'user', 'text': '最近确认：主角最终选择离开'}])
        history = writing_api._recent_chat_history(rows)
        self.assertIn('较早对话摘录', history)
        self.assertIn('世界观设定：雨城每晚停电一次', history)
        self.assertIn('最近确认：主角最终选择离开', history)
        self.assertLessEqual(len(history), writing_api.CHAT_HISTORY_CHAR_LIMIT)

    def test_direct_chat_rejects_oversize_context_before_model_request(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            stage_config.put(project, 'script', model='gpt-4o')
            huge_context = 'x' * (writing_api.DIRECT_REQUEST_CONTEXT_MAX_CHARS + 1)
            with patch('writing_api.model_pool.pool', return_value=model_pool.default_pool()), \
                 patch('workflow_context.instruction', return_value=__import__('service_contract').success(huge_context)), \
                 patch('writing_api.PoolAdapter.chat') as chat:
                result = writing_api.reply(project, '一个简短创意')
        self.assertFalse(result['ok'])
        self.assertEqual(result['reason'], 'context_budget_exceeded')
        self.assertIn('上下文过长', result['error'])
        chat.assert_not_called()

    def test_tool_chat_rejects_oversize_followup_before_adapter_request(self):
        class Adapter:
            def chat(self, *args, **kwargs):
                raise AssertionError('超长上下文不应调用模型')
        with tempfile.TemporaryDirectory() as td:
            result = writing_api._reply_with_project_tools(
                Adapter(), 'claude-test', '系统规则',
                'x' * (writing_api.DIRECT_REQUEST_CONTEXT_MAX_CHARS + 1), td)
        self.assertFalse(result['ok'])
        self.assertEqual(result['reason'], 'context_budget_exceeded')


if __name__ == '__main__':
    unittest.main(verbosity=2)
