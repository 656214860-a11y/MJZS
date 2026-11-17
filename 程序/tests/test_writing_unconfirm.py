# -*- coding: utf-8 -*-
"""「取消已确认」：右键菜单把「重写<阶段>」改为「取消已确认」，阶段回退到该阶段，只改台账不删文件。

REQ-S01-78：取消①②③任一步的确认并回退；REQ-S01-52：取消确认不依赖所选模型。
"""
import hashlib
import json
import tempfile
import unittest
from unittest.mock import Mock, patch

import infra.model_pool as model_pool
from contract import project_stages
import script_contract
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

    def adopt_script(self):
        """写入一份自然稿并登记采用。"""
        folder = self.target.parent / '项目剧本'
        folder.mkdir(parents=True, exist_ok=True)
        script = folder / '旧剧本.md'
        script.write_text('# 自然剧本\n旧稿\n', encoding='utf-8')
        save(script_contract.natural_script_selection_path(self.project), {
            'path': script.relative_to(self.project).as_posix(),
            'sha256': hashlib.sha256(script.read_bytes()).hexdigest()})
        return script

    def selection(self):
        path = script_contract.natural_script_selection_path(self.project)
        return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None

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

    def test_unconfirm_revokes_natural_script_adoption(self):
        """REQ-S01-14 口径扩展：取消已确认使采用基线变化，已采用自然稿同步撤销。"""
        self.adopt_script()
        unconfirm_writing_preparation(self.project, '剧本大纲')
        self.assertIsNone(script_contract.resolve_script_source(self.project))
        self.assertIn('前置阶段已更新', self.selection()['reason'])
        self.assertEqual(self.selection()['path'], '')

    def test_unconfirm_without_adoption_writes_no_selection_record(self):
        """从未采用过自然稿的项目，取消确认只改台账，不产生多余的失效记录。"""
        unconfirm_writing_preparation(self.project, '剧本大纲')
        self.assertIsNone(self.selection())

    def test_unconfirm_then_reconfirm_different_file_keeps_adoption_revoked(self):
        """REQ-S01-14 口径扩展：取消后改文件重确认，采用基线仍不同，采用维持撤销。"""
        from orchestrator import writing_unconfirm
        from stage_execution_service import publish_stage_text
        self.adopt_script()
        unconfirm_writing_preparation(self.project, '角色卡')
        path = self.target.parent / '角色卡' / '新卡.md'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('# 角色卡\n新少年\n', encoding='utf-8')
        writing_unconfirm.confirm_preparation_document(
            self.project, '角色卡', path, publish=publish_stage_text)
        self.assertIsNone(script_contract.resolve_script_source(self.project))
        self.assertIn('前置阶段已更新', self.selection()['reason'])

    def test_partial_adoption_of_confirmed_doc_trims_deconfirms_and_revokes_adoption(self):
        """REQ-S01-88：已确认稿选段采用——截写文件、按取消确认口径回退该阶段、撤销自然稿采用、台账记 partial_adoption。"""
        from stage_execution_service import apply_partial_adoption
        outline = self.target.parent / self.original['documents'][1]['path']
        outline.write_text('## 场一\n甲\n\n## 场二\n乙\n\n## 场三\n丙\n\n## 场四\n丁\n\n## 场五\n戊\n',
                           encoding='utf-8')
        self.adopt_script()
        apply_partial_adoption(self.project, '剧本大纲', outline, keep=(0, 1, 2))
        text = outline.read_text(encoding='utf-8')
        self.assertIn('场三', text)
        self.assertNotIn('场四', text)
        documents = self.state()['documents']
        self.assertEqual([doc['stage'] for doc in documents], ['项目设定', '剧本大纲'])
        self.assertTrue(documents[0]['confirmed'])
        self.assertFalse(documents[1]['confirmed'])
        self.assertEqual(documents[1]['partial_adoption'], {'kept': [0, 1, 2], 'total': 5})
        self.assertIsNone(script_contract.resolve_script_source(self.project))
        self.assertIn('前置阶段已更新', self.selection()['reason'])

    def test_partial_adoption_pending_draft_keeps_prefix_and_marks_ledger(self):
        """REQ-S01-88：待确认草稿选段——文件截写、前缀确认不动、台账记标记。"""
        from stage_execution_service import apply_partial_adoption
        unconfirm_writing_preparation(self.project, '角色卡')
        card = self.target.parent / self.original['documents'][2]['path']
        card.write_text('卡A\n\n卡B\n\n卡C\n', encoding='utf-8')
        apply_partial_adoption(self.project, '角色卡', card, keep=(0, 2))
        self.assertEqual(card.read_text(encoding='utf-8').strip(), '卡A\n\n卡C')
        documents = self.state()['documents']
        self.assertTrue(documents[0]['confirmed'] and documents[1]['confirmed'])
        self.assertFalse(documents[2]['confirmed'])
        self.assertEqual(documents[2]['partial_adoption'], {'kept': [0, 2], 'total': 3})

    def test_partial_adoption_all_sections_is_noop(self):
        """REQ-S01-88：全选等同不操作——文件与台账都不动。"""
        from stage_execution_service import apply_partial_adoption
        outline = self.target.parent / self.original['documents'][1]['path']
        outline.write_text('## 一\n甲\n\n## 二\n乙\n', encoding='utf-8')
        before_state = self.target.read_text(encoding='utf-8')
        before_file = outline.read_text(encoding='utf-8')
        apply_partial_adoption(self.project, '剧本大纲', outline, keep=(0, 1))
        self.assertEqual(outline.read_text(encoding='utf-8'), before_file)
        self.assertEqual(self.target.read_text(encoding='utf-8'), before_state)

    def test_adoption_sections_splits_headings_then_paragraphs(self):
        """REQ-S01-88：markdown 标题分段；无标题按空行分段。"""
        from orchestrator import writing_unconfirm
        sections = writing_unconfirm.adoption_sections('## 一\n甲\n\n## 二\n乙')
        self.assertEqual(len(sections), 2)
        self.assertEqual(sections[0]['title'], '## 一')
        self.assertIn('甲', sections[0]['text'])
        plain = writing_unconfirm.adoption_sections('段甲\n\n段乙\n\n段丙')
        self.assertEqual([s['text'] for s in plain], ['段甲', '段乙', '段丙'])

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
        from desktop_files_panel import ProjectFilesPanel
        from desktop_writing_page import WritingPageServices
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
        page = ProjectFilesPanel.__new__(ProjectFilesPanel)
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
