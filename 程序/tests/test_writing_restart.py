"""共享阶段成果的显式重写、确认失效与迟到响应保护。"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import model_pool
import project_stages
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
        stage_config.put(self.project, 'script', model='gpt-4o')
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

    def test_confirm_new_outline_invalidates_character_and_script(self):
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
        self.assertIsNone(script_contract.resolve_script_source(self.project))
        selection = json.loads(script_contract.natural_script_selection_path(self.project).read_text(encoding='utf-8'))
        self.assertIn('前置阶段已更新', selection['reason'])

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

    def test_confirm_rewritten_character_supplies_new_text_to_four_roles(self):
        restart_writing_preparation(self.project, '角色卡')
        self.reply('人物设定（角色卡）')
        with patch('writing_api._hollmwood_reply', return_value={'ok': True}) as roles:
            writing_api.reply(self.project, '确认', publish=publish_stage_text)
        confirmed = roles.call_args.args[4]['已确认阶段文件']
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
        with self.assertRaisesRegex(OSError, 'state publication failed'):
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

    def test_desktop_stage_menu_routes_explicit_restart_and_cancel(self):
        import ast
        from types import SimpleNamespace
        from unittest.mock import Mock
        source = Path(writing_api.__file__).with_name('desktop.py')
        tree = ast.parse(source.read_text(encoding='utf-8-sig'))
        node = next(item for item in ast.walk(tree) if isinstance(item, ast.FunctionDef)
                    and item.name == 'script_menu')
        trees = {name: Mock() for name in ('setting', 'outline', 'character', 'script')}
        restart = Mock()
        menu = Mock()
        namespace = dict(script_trees=trees, ContextMenu=Mock(return_value=menu),
                         self=SimpleNamespace(win=object(), safe=lambda call: call()),
                         restart_preparation=restart, open_script_file=Mock(), rename_script=Mock(),
                         adopt_script=Mock(), delete_script=Mock())
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), namespace)
        for category, stage in zip(('setting', 'outline', 'character'), writing_api.PREPARATION_STAGES):
            menu.reset_mock()
            namespace['script_menu'](trees[category], SimpleNamespace(y=0))
            actions = {call.args[0]: call.args[1] for call in menu.command.call_args_list}
            actions['从本阶段重新创作']()
            restart.assert_called_with(stage)
            actions['放弃未确认重写']()
            restart.assert_called_with(None)
