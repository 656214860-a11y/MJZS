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
import writing_stream
import writing_tools
import model_pool
import script_contract
import project_stages
from stage_execution_service import publish_stage_text
from model_router import PoolAdapter
import token_saver
from test_workflow import make_project as _make_project


def make_project(td):
    """API 行为用例显式选择阶段技能，不隐式全选本机安装的写作包。"""
    project = _make_project(td)
    stage_config.put(project, 'script', skills=['pipeline-script-preparation'])
    return project


def script_documents(chat):
    '''自然剧本请求里随 <brief_complete> 交给模型的已确认阶段文件。'''
    import json
    task = chat.call_args.args[0][0]['content']
    return json.loads(task.split('<brief_complete>', 1)[1].split('</brief_complete>', 1)[0])['已确认阶段文件']


def script_stage_probe():
    '''观察是否真正进入阶段④自然剧本请求（放行后仍执行原函数）。'''
    import workflow_tasks
    return patch('workflow_tasks.script_prompt', wraps=workflow_tasks.script_prompt)


class WritingApiTests(unittest.TestCase):
    def test_custom_desktop_model_uses_its_program_without_api(self):
        """REQ-S01-30：桌面模型走桌面调用方式，不落 API 配置，直接投给该程序。"""
        record = {'label': 'gemini', 'model': 'Google Gemini 4 Argon', 'provider': 'desktop',
                  'call_mode': 'Desktop', 'program': 'C:/Apps/Gemini.exe', 'base_url': ''}
        with tempfile.TemporaryDirectory() as td, patch('model_pool.pool', return_value={'gemini': record}):
            project = make_project(td)
            stage_config.put(project, 'script', model='gemini')
            self.assertEqual(writing_api.selected_model(project), ('', {}))
            skill = Path(td) / 'SKILL.md'
            skill.write_text('---\nname: desktop-route-test\n---\n编写剧本', encoding='utf-8')
            with patch('workflow_settings.skills_of', return_value=[str(skill)]):
                request = writing_api.capture_request(project)
            self.assertEqual(request['id'], '')
            self.assertEqual(request['settings']['engine'], 'desktop-app')
            self.assertEqual(request['settings']['program'], record['program'])
            self.assertEqual(request['settings']['display_model'], 'gemini')
            self.assertNotIn('api', request['settings'])
            import workflow_settings
            self.assertEqual(workflow_settings.stage_model(project, 'writing'), ('', ''))
            self.assertEqual(workflow_settings.effective_model(project, 'writing'), 'gemini')

    def test_desktop_routing_honors_explicit_mode_and_legacy_provider(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            stage_config.put(project, 'script', model='gemini')
            for record, direct in (({'provider': 'desktop'}, False),
                                   ({'provider': 'google', 'call_mode': 'Desktop'}, False),
                                   ({'provider': 'google', 'call_mode': 'API'}, True)):
                with self.subTest(record=record), patch('model_pool.pool', return_value={'gemini': record}):
                    self.assertEqual(bool(writing_api.selected_model(project)[0]), direct)

    def test_real_request_sends_the_frozen_skill_once_in_the_system_prompt(self):
        import workflow_settings
        from agent.core import save
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            stage_config.put(project, 'script', model='gpt-4o', skills=[])
            skill = Path(td) / 'SKILL.md'
            skill.write_text('本次共享规则标记', encoding='utf-8')
            config = workflow_settings.defaults('writing')
            workflow_settings.set_skills(config['profiles']['qwen'], [str(skill)])
            save(workflow_settings.settings_path(project), {'flows': {'writing': config}})
            save(project_stages.writing(project) / 'brief_complete.json', self.complete_brief())
            self.confirmed_preparation(project)
            with patch('model_pool.pool', return_value=model_pool.default_pool()):
                request = writing_api.capture_request(project)
                skill.write_text('后来修改的规则', encoding='utf-8')
                stage_config.put(project, 'script', model='deepseek-v4-flash')
                with patch('writing_api.PoolAdapter.chat', return_value={
                        'ok': True, 'text': self.natural_script(20)}) as chat:
                    result = writing_api.reply(project, '开始', request_model=request, publish=publish_stage_text)
            self.assertTrue(result['ok'])
            self.assertEqual(chat.call_count, 1)
            call = chat.call_args
            self.assertEqual(call.kwargs['model'], 'gpt-4o')
            self.assertEqual(call.kwargs['system'].count('本次共享规则标记'), 1)
            self.assertNotIn('后来修改的规则', call.kwargs['system'])

    def test_real_configuration_switches_and_freezes_selected_skills(self):
        import workflow_settings
        import workflow_engines
        from agent.core import save
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            stage_config.put(project, 'script', skills=[])
            profiles = workflow_settings.defaults('writing')
            for engine, profile in profiles['profiles'].items():
                path = Path(td) / engine / 'SKILL.md'
                path.parent.mkdir()
                path.write_text('本次规则_' + engine, encoding='utf-8')
                workflow_settings.set_skills(profile, [str(path)])
            save(workflow_settings.settings_path(project), {'flows': {'writing': profiles}})
            snapshots = []
            with patch('model_pool.pool', return_value=model_pool.default_pool()):
                for model in ('gpt-4o', 'deepseek-v4-flash', 'chatgpt-desktop', 'claude-desktop'):
                    stage_config.put(project, 'script', model=model)
                    request = writing_api.capture_request(project)
                    snapshots.append(request)
                    engine = model_pool.desktop_engine(model) or 'qwen'
                    self.assertEqual(request['settings']['engine'], engine)
                    self.assertEqual(request['settings']['skill_injection']['mode'],
                                     model_pool.desktop_engine(model) or 'api')
                    self.assertIn('本次规则_' + engine, workflow_engines.prompt_with_settings('请求', request['settings']))
                Path(profiles['profiles']['qwen']['skills'][0]).write_text('修改后的内容', encoding='utf-8')
                self.assertIn('本次规则_qwen', workflow_settings.skill_prompt(snapshots[0]['settings'], inline=True))
                self.assertEqual(snapshots[0]['id'], 'gpt-4o')
                self.assertEqual(snapshots[1]['id'], 'deepseek-v4-flash')

    def test_missing_selection_survives_refresh_and_blocks_transport(self):
        """REQ-S01-31：已勾选 SKILL 缺失时阻止发送，不静默按未勾选处理。"""
        from agent.core import save
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            save(stage_config.path(project), {'script': {'model': 'gpt-4o', 'skills': ['deleted-skill']}})
            stage_config.get(project, 'script')
            with patch('writing_api.PoolAdapter.chat') as chat:
                with self.assertRaisesRegex(ValueError, '已勾选的 SKILL 未加载'):
                    writing_api.reply(project, '发送')
            chat.assert_not_called()

    def test_request_keeps_model_and_publication_identity_after_selection_changes(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            stage_config.put(project, 'script', model='gpt-4o')
            from agent.core import save
            save(project_stages.writing(project) / 'brief_complete.json', self.complete_brief())
            records = model_pool.default_pool()
            with patch('writing_api.model_pool.pool', return_value=records):
                request = writing_api.capture_request_model(project)
                original_label = request['label']
                stage_config.put(project, 'script', model='deepseek-v4-flash')
                records['gpt-4o']['label'] = '请求发出后改名'
                with patch('writing_api.PoolAdapter.chat', return_value={
                        'ok': True, 'text': '# 项目设定\n都市雨夜，少年追查底片。\n待确认'}) as chat:
                    result = writing_api.reply(project, '开始', publish=publish_stage_text, request_model=request)
            self.assertEqual(chat.call_args.kwargs['model'], 'gpt-4o')
            self.assertIn(original_label, Path(result['preparation_path']).parts)
            self.assertNotIn('请求发出后改名', Path(result['preparation_path']).parts)

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

    def test_brief_alone_generates_setting_before_script_stage(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            stage_config.put(project, 'script', model='gpt-4o')
            from agent.core import save
            save(project_stages.writing(project) / 'brief_complete.json', self.complete_brief())
            self.assertTrue(writing_api.preparation_continuation(project, '重试'))
            with patch('writing_api.model_pool.pool', return_value=model_pool.default_pool()), \
                 patch('workflow_tasks.script_prompt') as roles, \
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

    def test_preparation_requires_each_confirmation_and_hands_all_documents_to_script_request(self):
        """REQ-S01-10/13：四步固定（①项目设定→②剧本大纲→③角色卡→④自然剧本），④只在①②③全确认后启动。"""
        import json
        from agent.core import save
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            stage_config.put(project, 'script', model='gpt-4o')
            save(project_stages.writing(project) / 'brief_complete.json', self.complete_brief())
            answers = [{'ok': True, 'text': text} for text in (
                '# 项目设定\n旧设定。\n待确认', '# 项目设定\n修订设定。\n待确认',
                '# 剧本大纲\n追查底片的三幕故事。\n待确认', '# 人物设定（角色卡）\n阿远的目标与弱点。\n待确认', '{"next_stage":"自然剧本"}',
                '自然剧本')]
            with patch('writing_api.model_pool.pool', return_value=model_pool.default_pool()), \
                 patch('writing_api.PoolAdapter.chat', side_effect=answers) as chat, \
                 script_stage_probe() as roles:
                first = writing_api.reply(project, '开始', publish=publish_stage_text)
                revised = writing_api.reply(project, '不要确认，先改设定', publish=publish_stage_text)
                self.assertEqual(first['preparation_path'], revised['preparation_path'])
                self.assertIn('修订设定', Path(first['preparation_path']).read_text(encoding='utf-8'))
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
            documents = script_documents(chat)
            self.assertEqual(list(documents), list(writing_api.PREPARATION_STAGES))
            self.assertIn('修订设定', documents['项目设定'])
            self.assertIn('阿远', documents['角色卡'])
            state = json.loads((project_stages.writing(project) / 'preparation_state.json').read_text(encoding='utf-8'))
            self.assertTrue(all(item['confirmed'] for item in state['documents']))
            self.assertEqual(len({item['path'] for item in state['documents']}), 3)
            self.assertEqual(chat.call_count, 6)

    def test_colloquial_confirmation_advances_preparation(self):
        from agent.core import save
        for confirmation in ('可以', '好的', '没问题', 'OK', 'ok'):
            with self.subTest(confirmation=confirmation), tempfile.TemporaryDirectory() as td:
                project = make_project(td)
                stage_config.put(project, 'script', model='gpt-4o')
                brief = self.complete_brief()
                save(project_stages.writing(project) / 'brief_complete.json', brief)
                with patch('writing_api.model_pool.pool', return_value=model_pool.default_pool()), \
                     patch('writing_api.PoolAdapter.chat', side_effect=[
                         {'ok': True, 'text': '# 项目设定\n初始设定。\n待确认'},
                         {'ok': True, 'text': '# 剧本大纲\n大纲正文。\n待确认'}]):
                    writing_api.reply(project, '开始', publish=publish_stage_text)
                    result = writing_api.reply(project, confirmation, publish=publish_stage_text)
                self.assertTrue(result['ok'])
                self.assertEqual(result['preparation_stage'], '剧本大纲')
                _, state, _ = writing_api._preparation_state(project, brief)
                self.assertIs(state['documents'][0]['confirmed'], True)
                self.assertIs(state['documents'][1]['confirmed'], False)

    def test_qualified_confirmation_keeps_current_preparation_stage(self):
        from agent.core import save
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            stage_config.put(project, 'script', model='gpt-4o')
            brief = self.complete_brief()
            save(project_stages.writing(project) / 'brief_complete.json', brief)
            with patch('writing_api.model_pool.pool', return_value=model_pool.default_pool()), \
                 patch('writing_api.PoolAdapter.chat', side_effect=[
                     {'ok': True, 'text': '# 项目设定\n初始设定。\n待确认'},
                     {'ok': True, 'text': '# 项目设定\n主角改成女的。\n待确认'}]):
                writing_api.reply(project, '开始', publish=publish_stage_text)
                result = writing_api.reply(project, '可以，但是把主角改成女的', publish=publish_stage_text)
            self.assertTrue(result['ok'])
            self.assertEqual(result['preparation_stage'], '项目设定')
            _, state, _ = writing_api._preparation_state(project, brief)
            self.assertEqual(len(state['documents']), 1)
            self.assertIs(state['documents'][0]['confirmed'], False)

    def test_recent_history_keeps_twelve_messages_without_excerpt(self):
        rows = [{'role': 'user', 'text': '完整消息' + str(index)} for index in range(12)]
        history = writing_api._recent_chat_history(rows)
        self.assertNotIn('较早对话摘录', history)
        for row in rows:
            self.assertIn(row['text'], history)
        self.assertLessEqual(len(history), writing_api.CHAT_HISTORY_CHAR_LIMIT)

    def test_confirmation_uses_user_message_not_attachment_context(self):
        """REQ-S01-12：肯定回复只认输入框原文首行，附档正文里的“确认”不顶替。"""
        from agent.core import save
        from stage_execution_service import reply_to_writing
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            stage_config.put(project, 'script', model='gpt-4o')
            save(project_stages.writing(project) / 'brief_complete.json', self.complete_brief())
            with patch('writing_api.model_pool.pool', return_value=model_pool.default_pool()), \
                 patch('writing_api.PoolAdapter.chat', side_effect=[
                     {'ok': True, 'text': '# 项目设定\n初始设定。\n待确认'},
                     {'ok': True, 'text': '# 项目设定\n修改设定。\n待确认'},
                     {'ok': True, 'text': '# 剧本大纲\n大纲正文。\n待确认'}]) as chat:
                first = reply_to_writing(project, '开始')
                revised = reply_to_writing(project, '修改\n附件正文：确认', user_message='修改')
                self.assertEqual(revised['preparation_stage'], '项目设定')
                result = reply_to_writing(project, '确认\n附件正文：故事梗概：雨夜', user_message='确认')
            self.assertEqual(result['preparation_stage'], '剧本大纲')
            self.assertIn('附件正文：故事梗概：雨夜', chat.call_args.args[0][0]['content'])
            self.assertEqual(first['preparation_path'], revised['preparation_path'])
            self.assertIn('修改设定', Path(first['preparation_path']).read_text(encoding='utf-8'))

    def test_missing_stage_relinks_identical_download_before_confirmation(self):
        import json
        import hashlib
        from agent.core import save
        for ending in ('', '\n'):
            with self.subTest(ending=ending), tempfile.TemporaryDirectory() as td:
                project = make_project(td)
                stage_config.put(project, 'script', model='gpt-4o')
                folder = project_stages.writing(project)
                save(folder / 'brief_complete.json', self.complete_brief())
                with patch('writing_api.model_pool.pool', return_value=model_pool.default_pool()), \
                     patch('workflow_tasks.script_prompt') as roles, \
                     patch('writing_api.PoolAdapter.chat', side_effect=[
                         {'ok': True, 'text': '# 项目设定\n雨夜照相馆。\n待确认'},
                         {'ok': True, 'text': '# 剧本大纲\n追查底片。\n待确认'}]) as chat:
                    first = writing_api.reply(project, '开始', publish=publish_stage_text)
                    old = Path(first['preparation_path'])
                    copy = old.with_name('下载副本.md')
                    copy.write_text(old.read_text(encoding='utf-8').rstrip('\n') + ending, encoding='utf-8')
                    old.unlink()
                    ledger = folder / 'preparation_state.json'
                    before = ledger.read_bytes()
                    copy_before = copy.read_bytes()
                    self.assertTrue(writing_api.preparation_continuation(project, '确认'))
                    self.assertEqual(ledger.read_bytes(), before)
                    result = writing_api.reply(project, '确认', publish=publish_stage_text)
                self.assertEqual(result['preparation_stage'], '剧本大纲')
                self.assertEqual(chat.call_count, 2)
                roles.assert_not_called()
                state = json.loads(ledger.read_text(encoding='utf-8'))
                self.assertEqual(state['documents'][0]['path'], copy.relative_to(folder).as_posix())
                self.assertTrue(state['documents'][0]['confirmed'])
                self.assertEqual(state['documents'][0]['sha256'],
                                 hashlib.sha256(copy.read_text(encoding='utf-8').encode()).hexdigest())
                self.assertEqual(copy.read_bytes(), copy_before)
                self.assertFalse(old.exists())

    def test_relocated_character_card_relinks_only_identical_current_category(self):
        import json
        from agent.core import save
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            stage_config.put(project, 'script', model='gpt-4o')
            folder = project_stages.writing(project)
            save(folder / 'brief_complete.json', self.complete_brief())
            self.confirmed_preparation(project)
            ledger = folder / 'preparation_state.json'
            state = json.loads(ledger.read_text(encoding='utf-8'))
            card = state['documents'][-1]
            source = folder / card['path']
            text = source.read_text(encoding='utf-8')
            source.unlink()
            batch = folder / 'GPT' / 'GPT-4o' / '创意_20261011'
            card.update(path=(batch / '项目设定' / '旧角色卡.md').relative_to(folder).as_posix(),
                        confirmed=False)
            save(ledger, state)
            moved = batch / '角色卡' / '角色卡.md'
            moved.parent.mkdir(parents=True)
            moved.write_text(text, encoding='utf-8')
            before = ledger.read_bytes()
            self.assertTrue(writing_api.preparation_continuation(project, '确认'))
            self.assertEqual(ledger.read_bytes(), before)
            moved.write_text('已修改的角色卡', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, '原确认失效'):
                writing_api.preparation_continuation(project, '确认')
            moved.unlink()
            with self.assertRaisesRegex(ValueError, '原确认失效'):
                writing_api.preparation_continuation(project, '确认')
            moved.write_text(text, encoding='utf-8')
            with patch('writing_api.model_pool.pool', return_value=model_pool.default_pool()), \
                 patch('writing_api.PoolAdapter.chat', side_effect=[
                     {'ok': True, 'text': '{"next_stage":"自然剧本"}'}, {'ok': True, 'text': '自然剧本'}]), \
                 script_stage_probe() as roles:
                writing_api.reply(project, '确认', publish=publish_stage_text)
            roles.assert_called_once()
            current = json.loads(ledger.read_text(encoding='utf-8'))['documents'][-1]
            self.assertEqual(current['path'], moved.relative_to(folder).as_posix())
            self.assertEqual(current['sha256'], card['sha256'])
            self.assertTrue(current['confirmed'])
            self.assertEqual(moved.read_text(encoding='utf-8'), text)

    def test_relink_requires_matching_content_and_persists_before_script_request(self):
        import json
        from agent.core import save
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            stage_config.put(project, 'script', model='gpt-4o')
            folder = project_stages.writing(project)
            save(folder / 'brief_complete.json', self.complete_brief())
            self.confirmed_preparation(project)
            original = folder / '项目设定.md'
            text = original.read_text(encoding='utf-8')
            copy = folder / '改名后的设定.md'
            copy.write_text(text, encoding='utf-8')
            original.write_text('已修改正文', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, '原确认失效'):
                writing_api.preparation_continuation(project, '确认')
            original.unlink()
            copy.write_text('不同版本', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, '原确认失效'):
                writing_api.preparation_continuation(project, '确认')
            copy.write_text(text, encoding='utf-8')
            ledger = folder / 'preparation_state.json'
            before = ledger.read_bytes()
            with patch('writing_api.model_pool.pool', return_value=model_pool.default_pool()), \
                 patch('writing_api.PoolAdapter.chat', return_value={'ok': True, 'text': '自然剧本'}) as chat, \
                 script_stage_probe() as roles:
                with self.assertRaisesRegex(OSError, '台账写入失败'):
                    writing_api.reply(project, '继续', publish=lambda *args: (_ for _ in ()).throw(OSError('台账写入失败')))
                self.assertEqual(ledger.read_bytes(), before)
                roles.assert_not_called()
                result = writing_api.reply(project, '继续', publish=publish_stage_text)
            self.assertTrue(result['ok'])
            chat.assert_called_once()
            roles.assert_called_once()
            self.assertEqual(script_documents(chat)['项目设定'], text)
            state = json.loads(ledger.read_text(encoding='utf-8'))
            self.assertEqual(state['documents'][0]['path'], copy.name)
            self.assertTrue(all(item['confirmed'] for item in state['documents']))

    def test_failed_next_stage_resumes_after_persisted_confirmation(self):
        from agent.core import save
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            stage_config.put(project, 'script', model='gpt-4o')
            save(project_stages.writing(project) / 'brief_complete.json', self.complete_brief())
            with patch('writing_api.model_pool.pool', return_value=model_pool.default_pool()), \
                 patch('workflow_tasks.script_prompt') as roles, \
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
        """REQ-S01-11：一次请求只产一步；不合格输出不发布、不推进到下一步。"""
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
                     patch('workflow_tasks.script_prompt') as roles:
                    result = writing_api.reply(project, '开始', publish=publish_stage_text)
                self.assertFalse(result['ok'])
                self.assertFalse((project_stages.writing(project) / 'preparation_state.json').exists())
                self.assertEqual(list(project_stages.writing(project).rglob('*.md')), [])
                roles.assert_not_called()

    def test_user_edited_pending_draft_is_revised_not_invalidated(self):
        """待确认草稿从未被确认；用户手改后重发应以改后正文修订，已确认前置文件仍严格比对。"""
        import json
        from agent.core import save
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            stage_config.put(project, 'script', model='gpt-4o')
            folder = project_stages.writing(project)
            save(folder / 'brief_complete.json', self.complete_brief())
            with patch('writing_api.model_pool.pool', return_value=model_pool.default_pool()), \
                 patch('writing_api.PoolAdapter.chat', side_effect=[
                     {'ok': True, 'text': '# 项目设定\n雨夜。\n待确认'},
                     {'ok': True, 'text': '# 剧本大纲\n追查底片。\n待确认'}]):
                writing_api.reply(project, '开始', publish=publish_stage_text)
                writing_api.reply(project, '确认', publish=publish_stage_text)
            ledger = folder / 'preparation_state.json'
            outline = folder / json.loads(ledger.read_text(encoding='utf-8'))['documents'][-1]['path']
            outline.write_text('# 剧本大纲\n用户改成：追查失踪的胶卷。\n待确认', encoding='utf-8')
            with patch('writing_api.model_pool.pool', return_value=model_pool.default_pool()), \
                 patch('writing_api.PoolAdapter.chat',
                       return_value={'ok': True, 'text': '# 剧本大纲\n追查失踪的胶卷，雨夜收网。\n待确认'}) as chat:
                result = writing_api.reply(project, '按我改的大纲重新输出', publish=publish_stage_text)
            self.assertTrue(result['ok'])
            prompt = json.dumps(chat.call_args, ensure_ascii=False, default=str)
            self.assertIn('追查失踪的胶卷', prompt)
            self.assertIn('用户已直接修改这份草稿', prompt)
            documents = json.loads(ledger.read_text(encoding='utf-8'))['documents']
            self.assertTrue(documents[0]['confirmed'])
            self.assertFalse(documents[-1]['confirmed'])
            setting = folder / documents[0]['path']
            setting.write_text('# 项目设定\n未经确认的改动。\n待确认', encoding='utf-8')
            with patch('writing_api.model_pool.pool', return_value=model_pool.default_pool()), \
                 patch('writing_api.PoolAdapter.chat') as chat:
                with self.assertRaisesRegex(ValueError, '原确认失效'):
                    writing_api.reply(project, '继续', publish=publish_stage_text)
            chat.assert_not_called()

    def test_deleted_or_modified_confirmed_document_blocks_script_request(self):
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
                     patch('writing_api.PoolAdapter.chat') as chat, patch('workflow_tasks.script_prompt') as roles:
                    with self.assertRaisesRegex(ValueError, '原确认失效'):
                        writing_api.reply(project, '开始', publish=publish_stage_text)
                chat.assert_not_called()
                roles.assert_not_called()

    def test_confirmed_document_tolerates_trailing_newline_difference(self):
        """自动保存追加末尾换行、旧下载不写换行；仅换行差异不得误报原确认失效。"""
        from agent.core import save
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            stage_config.put(project, 'script', model='gpt-4o')
            save(project_stages.writing(project) / 'brief_complete.json', self.complete_brief())
            self.confirmed_preparation(project)
            path = project_stages.writing(project) / '角色卡.md'
            path.write_text(path.read_text(encoding='utf-8').rstrip('\n'), encoding='utf-8')
            with patch('writing_api.model_pool.pool', return_value=model_pool.default_pool()), \
                 patch('writing_api.PoolAdapter.chat') as chat, patch('workflow_tasks.script_prompt') as roles:
                self.assertTrue(writing_api.preparation_continuation(project, '确认'))
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
                 patch('workflow_tasks.script_prompt') as roles:
                result = writing_api.reply(project, '确认', publish=publish_stage_text)
            self.assertEqual(result['preparation_stage'], '项目设定')
            roles.assert_not_called()

    def test_cancelled_preparation_response_does_not_publish(self):
        from agent.core import save
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
                with self.assertRaises(writing_api.WritingCancelledError):
                    writing_api.reply(project, '开始', publish=publish_stage_text, cancelled=lambda: stopped)
            self.assertFalse((project_stages.writing(project) / 'preparation_state.json').exists())
            self.assertEqual(list(project_stages.writing(project).rglob('*.md')), [])

    def test_preparation_publication_failure_preserves_cached_state_and_document(self):
        from agent.core import save
        for message in ('确认', '修改设定'):
            with self.subTest(message=message), tempfile.TemporaryDirectory() as td:
                project = make_project(td)
                stage_config.put(project, 'script', model='gpt-4o')
                save(project_stages.writing(project) / 'brief_complete.json', self.complete_brief())
                with patch('writing_api.model_pool.pool', return_value=model_pool.default_pool()), \
                     patch('writing_api.PoolAdapter.chat', return_value={'ok': True, 'text': '# 项目设定\n原设定。\n待确认'}):
                    first = writing_api.reply(project, '开始', publish=publish_stage_text)
                    state_path = project_stages.writing(project) / 'preparation_state.json'
                    original_state = state_path.read_bytes()
                    document = Path(first['preparation_path'])
                    original_document = document.read_bytes()
                    def fail_state(target, *args, **kwargs):
                        if target == state_path:
                            raise OSError('模拟阶段记录发布失败')
                        return publish_stage_text(target, *args, **kwargs)
                    with patch('writing_api.PoolAdapter.chat', return_value={'ok': True, 'text': '# 项目设定\n新设定。\n待确认'}), \
                         patch('workflow_tasks.script_prompt') as roles:
                        with self.assertRaisesRegex(OSError, '阶段记录发布失败'):
                            writing_api.reply(project, message, publish=fail_state)
                    roles.assert_not_called()
                    self.assertEqual(state_path.read_bytes(), original_state)
                    self.assertEqual(document.read_bytes(), original_document)
                    _, state, texts = writing_api._preparation_state(project, writing_api._complete_brief(project))
                    self.assertFalse(state['documents'][0]['confirmed'])
                    self.assertEqual(texts, [original_document.decode('utf-8').replace('\r\n', '\n')])

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

    def test_confirmed_preparation_runs_one_request_and_writes_human_readable_script_raw(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            stage_config.put(project, 'script', model='gpt-4o')
            writing = project / 'writing'
            writing.mkdir(exist_ok=True)
            (writing / 'brief_complete.json').write_text(
                __import__('json').dumps(self.complete_brief(), ensure_ascii=False), encoding='utf-8')
            text = self.natural_script(20)
            self.confirmed_preparation(project)
            skill = Path(td) / 'SKILL.md'
            skill.write_text('---\nname: api-skill-test\n---\n内联技能正文', encoding='utf-8')
            import workflow_settings
            from agent.core import save
            config = workflow_settings.defaults('writing')
            workflow_settings.set_skills(config['profiles']['qwen'], [str(skill)])
            save(workflow_settings.settings_path(project), {'flows': {'writing': config}})
            with patch('writing_api.model_pool.pool', return_value=model_pool.default_pool()), \
                 patch('writing_api.PoolAdapter.chat', return_value={'ok': True, 'text': text}) as chat:
                result = writing_api.reply(project, '开始创作', publish=publish_stage_text)
            self.assertTrue(result['ok'])
            self.assertEqual(chat.call_count, 1)
            system = chat.call_args.kwargs['system']
            self.assertIn('<skill name="api-skill-test">', system)
            self.assertEqual(system.count('内联技能正文'), 1)
            self.assertIn(f'<!-- 来源: {skill.resolve()} -->', system)
            self.assertNotIn('请先完整读取并遵循本地技能文件', system)
            # R2450 起 writing 阶段递归内联 SKILL 引用；'APPROVED_R01' 是引用文档的正文，
            # 不能再当「旧内容泄漏」哨兵——哨兵只保留仍属废弃词的两条。
            for obsolete in ('全局节奏模板', 'HOLLMWOOD'):
                self.assertNotIn(obsolete, system)
            prompt = chat.call_args.args[0][0]['content']
            self.assertEqual(prompt.count('<brief_complete>'), 1)
            self.assertIn('单集 60 秒', prompt)
            self.assertIn('已确认阶段文件', prompt)
            self.assertIn('已确认的创作依据', prompt)
            self.assertEqual((project_stages.writing(project) / 'script_raw.md').read_text(encoding='utf-8'), text.strip() + '\n')
            formal = Path(result['natural_script_path'])
            self.assertEqual(formal.parent.name, '项目剧本')
            self.assertEqual(formal.read_text(encoding='utf-8').strip(), text.strip())
            self.assertNotEqual(formal.name, 'script_raw.md')
            self.assertFalse(list((project / 'logs').glob('hollmwood_step_*.log')))
            self.assertEqual(len(list((project / 'logs' / 'model_diagnostics').glob('*.json'))), 1)

    def test_direct_api_uses_complete_brief_and_auto_saves(self):
        """REQ-S01-30：API 方式由程序自动归档正文（script_raw 与正式自然剧本）。"""
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            stage_config.put(project, 'script', model='gpt-4o')
            writing = project / 'writing'; writing.mkdir(exist_ok=True)
            (writing / 'brief_complete.json').write_text(__import__('json').dumps(self.complete_brief(), ensure_ascii=False), encoding='utf-8')
            text = self.natural_script(20)
            self.confirmed_preparation(project)
            with patch('writing_api.model_pool.pool', return_value=model_pool.default_pool()), \
                 patch('writing_api.PoolAdapter.chat', return_value={'ok': True, 'text': text}) as chat:
                result = writing_api.reply(project, '开始创作', publish=publish_stage_text)
            self.assertIn('<brief_complete>', chat.call_args.args[0][0]['content'])
            self.assertTrue(result['script_raw_path'])
            self.assertEqual((project_stages.writing(project) / 'script_raw.md').read_text(encoding='utf-8'), text.strip() + '\n')
            self.assertEqual(Path(result['natural_script_path']).read_text(encoding='utf-8').strip(), text.strip())

    def test_api_formal_script_reuses_download_path_and_versions_changed_text(self):
        """REQ-S01-20：同一阶段多份稿件并存且可区分，正文有变才另存新稿，不覆盖旧稿。"""
        import idea_chat
        from project_context_factory import project_context
        from stage_execution_service import publish_idea_creative
        with tempfile.TemporaryDirectory() as td, patch('model_pool.pool', return_value=model_pool.default_pool()):
            project = make_project(td)
            text = '# 自然剧本\n场景：雨夜照相馆\n' + self.natural_script(20).strip()
            result = {'ok': True, 'text': text, 'model': 'DeepSeek V4 Flash'}
            first = writing_api._auto_save_script_raw(project, result, publish=publish_stage_text)
            formal = Path(first['natural_script_path'])
            self.assertIn('DeepSeek', formal.name)
            provider, model = idea_chat.storage_identity(result['model'])
            downloaded = idea_chat.save_reply(project_context(project), text, provider=provider, model=model,
                                             publish=publish_idea_creative)
            self.assertEqual(downloaded, formal)
            again = writing_api._auto_save_script_raw(project, result, publish=publish_stage_text)
            self.assertEqual(again['natural_script_path'], str(formal))
            changed = writing_api._auto_save_script_raw(project, dict(result, text=text + '\n阿远关上门。'),
                                                       publish=publish_stage_text)
            revised = Path(changed['natural_script_path'])
            self.assertIn('DeepSeek(1)', revised.name)
            self.assertEqual(formal.read_text(encoding='utf-8').strip(), text)
            self.assertEqual(len(list(formal.parent.glob('*.md'))), 2)

    def test_episode_incremental_hint_and_ledger_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            original = ('# 第1集：起风\n第一集正文。\n'
                        '\n# 第2集：雨后\n第二集正文。\n')
            saved = writing_api._save_formal_script(
                project, {'ok': True, 'text': original, 'model': 'DeepSeek V4 Flash'},
                publish=publish_stage_text, previous_script='')
            self.assertTrue(script_contract.episode_ledger_path(project).is_file())
            formal = Path(saved['natural_script_path'])
            unchanged = writing_api._episode_reference_hint(project)
            self.assertNotIn('第一集正文。', unchanged)
            self.assertNotIn('第二集正文。', unchanged)
            formal.write_text(original.replace('第二集正文。', '第二集改过的正文。'), encoding='utf-8')
            changed = writing_api._episode_reference_hint(project)
            self.assertIn('第二集改过的正文。', changed)
            self.assertNotIn('第一集正文。', changed)
            self.assertIn('第2集已修改', changed)

    def test_formal_publish_failure_surfaces_and_retry_archives_existing_raw(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            result = {'ok': True, 'text': self.natural_script(20), 'model': 'DeepSeek V4 Flash'}
            def fail_formal(path, *args):
                if path.name != 'script_raw.md':
                    raise OSError('formal publication failed')
                return publish_stage_text(path, *args)
            with self.assertRaisesRegex(OSError, 'formal publication failed'):
                writing_api._auto_save_script_raw(project, result, publish=fail_formal)
            with patch('writing_api._write_script_raw') as raw:
                saved = writing_api._auto_save_script_raw(project, result, publish=publish_stage_text)
            raw.assert_not_called()
            self.assertTrue(Path(saved['natural_script_path']).is_file())

    def test_cancel_at_formal_publish_does_not_create_formal_script(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            cancelled = False
            def publish(path, *args):
                nonlocal cancelled
                output = publish_stage_text(path, *args)
                cancelled = True
                return output
            result = {'ok': True, 'text': self.natural_script(20), 'model': 'DeepSeek V4 Flash'}
            with self.assertRaises(writing_api.WritingCancelledError):
                writing_api._auto_save_script_raw(project, result,
                    publish=writing_api._cancellable_publisher(publish, lambda: cancelled))
            self.assertEqual(list(project_stages.writing(project).rglob('*自然剧本*.md')), [])

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

    def test_script_raw_save_notice_names_the_formal_script(self):
        from desktop import script_raw_saved_notice
        self.assertEqual(script_raw_saved_notice(), '剧本已自动保存：script_raw.md')
        self.assertEqual(script_raw_saved_notice('目录/摄影侠_自然剧本_DeepSeek.md'),
                         '剧本已自动保存：摄影侠_自然剧本_DeepSeek.md')

    def test_cancelled_request_does_not_write_script_raw(self):
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
                with self.assertRaises(writing_api.WritingCancelledError):
                    writing_api.reply(project, '开始创作', cancelled=lambda: True)
            chat.assert_not_called()
            self.assertFalse((project_stages.writing(project) / 'script_raw.md').exists())

    def test_network_failure_returns_recoverable_result(self):
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
            self.assertIn('TLS EOF', result['error'])
            self.assertFalse((project_stages.writing(project) / 'script_raw.md').exists())

    def test_claude_desktop_model_is_not_a_direct_api_model(self):
        with tempfile.TemporaryDirectory() as td, patch('model_pool.pool', return_value=model_pool.default_pool()):
            project = make_project(td)
            stage_config.put(project, 'script', model='claude-desktop')
            self.assertEqual(writing_api.selected_model(project), ('', {}))
            self.assertEqual(writing_api.capture_request(project)['id'], '')

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

    def test_script_raw_publication_rejects_blank_script(self):
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
                + [{'role': 'assistant', 'text': '中段讨论' * 300} for _ in range(16)]
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


class StreamingChatTests(unittest.TestCase):
    class Adapter:
        wire_api = 'chat'

        def __init__(self, stream_result, chunks=()):
            self.stream_result, self.chunks, self.chat_calls = stream_result, chunks, 0

        def stream(self, messages, options=None, model=None, system=None, on_chunk=None, cancelled=None):
            for chunk in self.chunks:
                on_chunk(chunk)
            return self.stream_result

        def chat(self, *args, **kwargs):
            self.chat_calls += 1
            return {'ok': True, 'text': '整段'}

    def run_chat(self, adapter, sink):
        with writing_stream.stream_to(sink):
            return writing_stream.chat_streaming(adapter, [], {}, 'm', 's')

    def test_chunks_reach_the_sink_without_a_second_request(self):
        got = []
        adapter = self.Adapter({'ok': True, 'text': 'ab'}, ('a', 'b'))
        result = self.run_chat(adapter, got.append)
        self.assertEqual((got, result['text'], adapter.chat_calls), (['a', 'b'], 'ab', 0))

    def test_failure_before_any_text_falls_back_to_plain_chat(self):
        adapter = self.Adapter({'ok': False, 'error_class': 'network'})
        self.assertEqual(self.run_chat(adapter, lambda c: None)['text'], '整段')
        self.assertEqual(adapter.chat_calls, 1)

    def test_failure_after_text_is_not_resent(self):
        adapter = self.Adapter({'ok': False, 'error_class': 'network'}, ('a',))
        self.assertFalse(self.run_chat(adapter, lambda c: None)['ok'])
        self.assertEqual(adapter.chat_calls, 0)

    def test_without_a_sink_uses_plain_chat(self):
        adapter = self.Adapter({'ok': True, 'text': 'x'}, ('x',))
        self.assertEqual(writing_stream.chat_streaming(adapter, [], {}, 'm', 's')['text'], '整段')


if __name__ == '__main__':
    unittest.main(verbosity=2)
