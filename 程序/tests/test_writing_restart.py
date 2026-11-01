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

    def test_confirm_new_outline_invalidates_character_and_script(self):
        """REQ-S01-14：确认重写后该步及下游确认失效，已采用的自然稿撤销采用。"""
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

    def test_native_claude_answers_revise_pending_document_before_confirmation(self):
        stage_config.put(self.project, 'script', model='claude-test')
        record = {'label': 'Claude Test', 'model': 'claude-test', 'provider': 'anthropic',
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

    def test_desktop_stage_menu_routes_explicit_restart_and_cancel(self):
        import ast
        from types import SimpleNamespace
        from unittest.mock import Mock
        source = Path(writing_api.__file__).with_name('desktop_writing_page.py')  # R1499：script_menu 在迁出的 writing 里
        tree = ast.parse(source.read_text(encoding='utf-8-sig'))
        node = next(item for item in ast.walk(tree) if isinstance(item, ast.FunctionDef)
                    and item.name == 'script_menu')
        tree = Mock()  # 阶段动作按所点行的类别决定（R1862 复原四张表后仍按行类别）
        # 表格支持多选后菜单先看选区：这里每次右键的行就是唯一选中行（单选菜单）。
        tree.selection.side_effect = lambda: (tree.identify_row.return_value,)
        rows = {'row-' + name: name for name in ('setting', 'outline', 'character', 'script')}
        restart = Mock()
        menu = Mock()
        ContextMenu = Mock(return_value=menu)  # R1988：菜单经 page.writing_page_services 取，不再是模块全局
        namespace = dict(script_row_category=rows,
                         self=SimpleNamespace(win=object(), safe=lambda call: call(),
                                             writing_page_services=SimpleNamespace(context_menu=ContextMenu)),
                         restart_preparation=restart, open_script_file=Mock(), rename_script=Mock(),
                         adopt_script=Mock(), delete_script=Mock(), keep_one_selection=Mock())
        # R1817：script_menu 成了 _WritingPage 的方法：闭包变量改由实例属性提供，桌面主窗成了 page
        page = SimpleNamespace(page=namespace.pop('self'), **{key: namespace.pop(key) for key in (
            'script_row_category', 'restart_preparation', 'open_script_file', 'rename_script', 'adopt_script', 'delete_script',
            'keep_one_selection')})
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), namespace)
        script_menu = namespace['script_menu']
        namespace['script_menu'] = lambda tree, event: script_menu(page, tree, event)
        for category, stage in zip(('setting', 'outline', 'character'), writing_api.PREPARATION_STAGES):
            menu.reset_mock()
            tree.identify_row.return_value = 'row-' + category
            namespace['script_menu'](tree, SimpleNamespace(y=0))
            actions = {call.args[0]: call.args[1] for call in menu.command.call_args_list}
            actions['重写' + stage]()
            restart.assert_called_with(stage)
            actions['放弃重写，恢复原稿']()
            restart.assert_called_with(None)

    class _TextBox:
        def __init__(self, text=''):
            self.text = text
            self.focused = False

        def winfo_exists(self):
            return True

        def get(self, start, end):
            return self.text

        def delete(self, start, end):
            self.text = ''

        def insert(self, index, value):
            self.text = value

        def focus_set(self):
            self.focused = True

    def _restart_for_desktop(self, text, model):
        from types import SimpleNamespace
        from unittest.mock import Mock
        import desktop_writing_page
        box = self._TextBox(text)
        status = Mock()
        host = SimpleNamespace(root=self.project, idea_input=box, status=status)
        refresh = Mock()
        restart = Mock()
        patches = (patch.object(writing_api, 'selected_model', return_value=(model, {})),
                   patch('stage_execution_service.restart_writing_preparation', restart))
        return desktop_writing_page._restart_preparation, host, refresh, status, box, restart, patches

    def test_req_s01_52_desktop_model_prefills_explicit_restart_command(self):
        "REQ-S01-52：桌面／命令行模型右键重写不报缺 API 模型，而是填入可识别的重写指令。"
        from workflow_tasks import writing_restart_requested
        call, host, refresh, status, box, restart, patches = self._restart_for_desktop(
            '第三幕节奏再快一点', '')
        with patches[0], patches[1]:
            call(host, '剧本大纲', refresh)
            restart.assert_not_called()
            refresh.assert_not_called()
            self.assertEqual(box.text.split('\n')[0], '重新生成剧本大纲')
            self.assertIn('第三幕节奏再快一点', box.text)
            self.assertTrue(writing_restart_requested(box.text))
            self.assertTrue(box.focused)
            self.assertIn('重新生成剧本大纲', status.set.call_args.args[0])
            call(host, '剧本大纲', refresh)
            self.assertEqual(box.text.count('重新生成剧本大纲'), 1)

    def test_req_s01_52_api_model_and_cancel_keep_revision_path(self):
        "REQ-S01-52：API 模型仍写重写记录；放弃重写不要求 API 模型。"
        call, host, refresh, _status, box, restart, patches = self._restart_for_desktop('', 'deepseek-v4-flash')
        with patches[0], patches[1]:
            call(host, '角色卡', refresh)
            restart.assert_called_once_with(self.project, '角色卡')
            refresh.assert_called_once_with()
        call, host, refresh, _status, box, restart, patches = self._restart_for_desktop('', '')
        with patches[0], patches[1]:
            call(host, None, refresh)
            restart.assert_called_once_with(self.project, None)
            self.assertEqual(box.text, '')
