# -*- coding: utf-8 -*-
"""「取消已确认」：右键菜单把「重写<阶段>」改为「取消已确认」，阶段回退到该阶段，只改台账不删文件。

REQ-S01-78：取消①②③任一步的确认并回退；REQ-S01-52：取消确认不依赖所选模型。
"""
import json
import tempfile
import unittest
from unittest.mock import Mock, patch

import model_pool
import project_stages
import stage_config
import writing_api
from agent.core import save
from stage_execution_service import restart_writing_preparation, unconfirm_writing_preparation
from test_workflow import make_project
import test_writing_api


class WritingUnconfirmTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = make_project(temporary.name)
        stage_config.put(self.project, 'script', model='gpt-4o',
                         skills=['pipeline-script-preparation'])
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

    def file_texts(self):
        return {self.target.parent / doc['path']: (self.target.parent / doc['path']).read_text(encoding='utf-8')
                for doc in self.original['documents']}

    def test_unconfirm_middle_stage_keeps_setting_and_cancels_outline_and_character(self):
        """REQ-S01-78：取消中间阶段（剧本大纲）→ 项目设定仍确认，大纲与角色卡一并取消。"""
        invalidated = unconfirm_writing_preparation(self.project, '剧本大纲')
        self.assertEqual(invalidated, ('角色卡',))
        documents = self.state()['documents']
        self.assertEqual([doc['stage'] for doc in documents], ['项目设定', '剧本大纲'])
        self.assertTrue(documents[0]['confirmed'])
        self.assertFalse(documents[1]['confirmed'])

    def test_unconfirm_first_stage_cancels_all_three(self):
        """REQ-S01-78：取消首阶段（项目设定）→ 三阶段全取消，阶段指针回到项目设定。"""
        invalidated = unconfirm_writing_preparation(self.project, '项目设定')
        self.assertEqual(invalidated, ('剧本大纲', '角色卡'))
        documents = self.state()['documents']
        self.assertEqual([doc['stage'] for doc in documents], ['项目设定'])
        self.assertFalse(documents[0]['confirmed'])

    def test_unconfirm_last_stage_cancels_only_itself(self):
        """REQ-S01-78：取消末阶段（角色卡）→ 无下游连带，角色卡变为待确认。"""
        invalidated = unconfirm_writing_preparation(self.project, '角色卡')
        self.assertEqual(invalidated, ())
        documents = self.state()['documents']
        self.assertEqual([doc['stage'] for doc in documents], ['项目设定', '剧本大纲', '角色卡'])
        self.assertTrue(documents[0]['confirmed'])
        self.assertTrue(documents[1]['confirmed'])
        self.assertFalse(documents[2]['confirmed'])

    def test_unconfirm_unconfirmed_or_missing_stage_is_noop(self):
        """REQ-S01-78：未确认或已截断的阶段取消无效、不报错、不改台账。"""
        unconfirm_writing_preparation(self.project, '剧本大纲')
        before = self.target.read_text(encoding='utf-8')
        self.assertEqual(unconfirm_writing_preparation(self.project, '剧本大纲'), ())
        self.assertEqual(self.target.read_text(encoding='utf-8'), before)
        self.assertEqual(unconfirm_writing_preparation(self.project, '角色卡'), ())
        self.assertEqual(self.target.read_text(encoding='utf-8'), before)

    def test_unconfirm_keeps_files_on_disk(self):
        """REQ-S01-78：取消确认不删除、不覆盖任何文件，原稿保留。"""
        before = self.file_texts()
        unconfirm_writing_preparation(self.project, '项目设定')
        for path, text in before.items():
            self.assertTrue(path.is_file())
            self.assertEqual(path.read_text(encoding='utf-8'), text)

    def test_unconfirm_clears_pending_rewrite(self):
        """REQ-S01-78：取消确认同时清掉进行中的重写台账（revision），采用版本回到该阶段待确认。"""
        restart_writing_preparation(self.project, '项目设定')
        self.assertIn('revision', self.state())
        unconfirm_writing_preparation(self.project, '项目设定')
        state = self.state()
        self.assertNotIn('revision', state)
        self.assertEqual([doc['stage'] for doc in state['documents']], ['项目设定'])
        self.assertFalse(state['documents'][0]['confirmed'])

    def test_req_s01_52_unconfirm_does_not_require_api_model(self):
        """REQ-S01-52：取消已确认只改台账，不依赖所选模型，桌面／命令行模型也不报「请选择 API 模型」。"""
        stage_config.put(self.project, 'script', model='')  # 桌面／命令行：selected_model 返回空
        invalidated = unconfirm_writing_preparation(self.project, '项目设定')
        self.assertEqual(invalidated, ('剧本大纲', '角色卡'))
        self.assertFalse(self.state()['documents'][0]['confirmed'])

    def test_chat_restart_path_unchanged(self):
        """REQ-S01-78：聊天口令回退路径（重写／放弃重写）仍走 restart_preparation，行为不变。"""
        self.assertEqual(writing_api.preparation_restart_intent('重写剧本大纲'), '剧本大纲')
        self.assertEqual(writing_api.preparation_restart_intent('回到项目设定阶段重新创作'), '项目设定')
        self.assertIsNone(writing_api.preparation_restart_intent('随便说点什么'))
        restart_writing_preparation(self.project, '剧本大纲')
        self.assertIn('revision', self.state())
        restart_writing_preparation(self.project, None)
        self.assertNotIn('revision', self.state())
        self.assertEqual(self.state()['documents'], self.original['documents'])

    def test_menu_offers_cancel_confirmation_only_when_stage_confirmed(self):
        """REQ-S01-78：右键菜单文案「取消已确认」，且只在阶段已确认时出现，旧「重写／放弃重写」已移除。"""
        import tkinter as tk
        from types import SimpleNamespace
        from desktop_writing_page import _WritingPage, WritingPageServices
        from ui_widgets import ContextMenu
        from skip_reasons import PLATFORM_TKINTER, PLATFORM_TK_DISPLAY
        try:
            win = tk.Tk()
        except tk.TclError:
            self.skipTest(PLATFORM_TKINTER)
        win.withdraw()
        self.addCleanup(lambda: win.winfo_exists() and win.destroy())

        created = []

        def context_menu(owner):
            menu = ContextMenu(owner)  # 真实 ContextMenu + 真实 tk.Menu 条目
            menu.menu.tk_popup = lambda *a, **k: None  # 只不真弹，避免阻塞
            created.append(menu)
            return menu

        def labels_of(menu):
            return [menu.menu.entrycget(i, 'label') for i in range(menu.menu.index('end') + 1)]

        services = WritingPageServices(open_path=Mock(), context_menu=context_menu,
                                       confirm=Mock(return_value=True), confirm_project_removal=Mock())
        page = _WritingPage.__new__(_WritingPage)
        page.page = SimpleNamespace(win=win, root=self.project, writing_page_services=services,
                                    safe=lambda call: call())
        page.script_row_category = {'row-setting': 'setting', 'row-outline': 'outline'}
        page.keep_one_selection = Mock()
        tree = Mock()
        tree.selection.return_value = ('row-setting',)

        # 三阶段均已确认：设定与大纲的菜单都应出现「取消已确认」，且没有旧「重写」「放弃重写」。
        tree.identify_row.return_value = 'row-setting'
        page.script_menu(tree, SimpleNamespace(y=0, x_root=0, y_root=0))
        setting_labels = labels_of(created[-1])
        self.assertIn('取消已确认', setting_labels)
        self.assertIn('设为项目设定定稿', setting_labels)
        self.assertNotIn('重写项目设定', setting_labels)
        self.assertNotIn('放弃重写，恢复原稿', setting_labels)

        tree.identify_row.return_value = 'row-outline'
        page.script_menu(tree, SimpleNamespace(y=0, x_root=0, y_root=0))
        self.assertIn('取消已确认', labels_of(created[-1]))
        self.assertIn('设为剧本大纲定稿', labels_of(created[-1]))

        # 取消全部确认后：菜单不再出现「取消已确认」，仍保留「设为定稿」。
        unconfirm_writing_preparation(self.project, '项目设定')
        tree.identify_row.return_value = 'row-setting'
        page.script_menu(tree, SimpleNamespace(y=0, x_root=0, y_root=0))
        unconfirmed_labels = labels_of(created[-1])
        self.assertNotIn('取消已确认', unconfirmed_labels)
        self.assertIn('设为项目设定定稿', unconfirmed_labels)


if __name__ == '__main__':
    unittest.main()
