# -*- coding: utf-8 -*-
"""「设置 → SKILL 管理」页自检（生命周期任务书 T7／R3089）。

覆盖：树形列表（三层来源、真实包子技能、阶段入口与旧包）、筛选与详情、说明弹窗、
体检详情、删除确认（内置层拒绝、用户层进回收站）、导入对话框五入口与单文件安装管线。
运行：python run_selftests.py -k pet_skills_manage
"""
from skip_reasons import PLATFORM_TKINTER
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, PROGRAM)
os.chdir(PROGRAM)

import pet_skills_manage
import ui.pet_ui as pet_ui
import skill_registry
from test_skills import write_skill

import selftest_sandbox
selftest_sandbox.isolate(pet_ui)

STAGE_DIR = '01 剧本准备SKILL'


class FakeDesktop:
    def __init__(self, tk, ttk, win):
        self.win = win
        self.root = None
        self.shutting_down = False
        self.title_row = ttk.Frame(win)
        self.title_row.pack(fill='x')
        self.body = ttk.Frame(win)
        self.body.pack(fill='both', expand=True)
        self.header_status = ttk.Label(self.title_row, text='就绪')
        self.header_status.pack(side='right')
        self.sidebar_head = ttk.Frame(win)
        self.sidebar_head.pack(fill='x')
        self.status = tk.StringVar(master=win, value='就绪')

    def kick_unattended(self, source):
        pass

    def asset_base(self):
        return self.root / 'episode'

    def close(self):
        return True


class SkillsManageCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            from tkinter import ttk
            cls.tk, cls.ttk = tk, ttk
        except Exception:
            cls.tk = None

    def setUp(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        self.win = self.tk.Tk()
        self.win.withdraw()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.program = Path(self.tmp.name) / 'program'
        (self.program / 'skills').mkdir(parents=True)
        (self.program / 'data' / 'skills').mkdir(parents=True)
        self.project = Path(self.tmp.name) / 'project'
        (self.project / 'skills').mkdir(parents=True)
        (self.project / 'episode').mkdir(parents=True)
        (self.project / 'episode' / 'assets.json').write_text('{}', encoding='utf-8')
        patcher = mock.patch.object(pet_ui, 'PROGRAM', self.program)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.fake = FakeDesktop(self.tk, self.ttk, self.win)
        self.fake.root = self.project
        self.pet = pet_ui.attach(self.fake, autostart=False)
        self.pet.asker = lambda title, text: True
        self.pet.program = self.program
        self.pet.project = self.project
        self.addCleanup(self.win.destroy)

    def pump(self, seconds=0.05, rounds=200):
        for _ in range(rounds):
            self.win.update()
            time.sleep(seconds)

    def hub(self, tab='skills'):
        win = self.pet.open_settings(tab)
        self.addCleanup(win.destroy)
        return win

    def tree(self, win):
        return win._pet_seams['skills']['tree']

    def wait_rows(self, win, minimum=1):
        for _ in range(400):
            self.win.update()
            if len(self.tree(win).get_children()) >= minimum:
                return True
            time.sleep(0.02)
        return False

    def wait_tree(self, win, predicate):
        """等后台刷新真正回填：旧行在 fill 前不会被换掉，按内容谓词等待。"""
        for _ in range(400):
            self.win.update()
            if predicate(self.tree(win)):
                return True
            time.sleep(0.02)
        return False

    def add_skills(self):
        self.builtin = write_skill(self.program / 'skills' / STAGE_DIR,
                                   'pipeline-script-preparation')
        self.user = write_skill(self.program / 'data' / 'skills' / STAGE_DIR,
                                'user-layer-skill')
        self.project_skill = write_skill(self.project / 'skills' / STAGE_DIR,
                                         'project-layer-skill')

    def write_package(self, package, name='pack-main'):
        package = Path(package)
        (package / 'nested').mkdir(parents=True)
        (package / 'SKILL.md').write_text(
            '---\nname: %s\ndisplayName: 测试技能包\ndescription: 包说明\n---\n\n# 测试技能包\n\n包正文。\n' % name,
            encoding='utf-8')
        (package / 'nested' / 'pack-child.skill.md').write_text(
            '---\nname: pack-child\ndisplayName: 包内子技能\ndescription: 子说明\n---\n\n子正文。\n',
            encoding='utf-8')
        return package

    def select(self, win, name):
        tree = self.tree(win)
        tree.selection_set(name)
        return tree


class SkillsManagePageTests(SkillsManageCase):
    def test_lists_all_layers_with_health_status(self):
        self.add_skills()
        win = self.hub()
        self.assertTrue(self.wait_rows(win, 3), '后台加载后列表应有 3 行')
        tree = self.tree(win)
        rows = {iid: tree.item(iid, 'values') for iid in tree.get_children()}
        self.assertIn('pipeline-script-preparation', rows)
        self.assertIn('user-layer-skill', rows)
        self.assertIn('project-layer-skill', rows)
        # 层列：项目版／用户版／内置版
        layers = {values[3] for values in rows.values()}
        self.assertEqual({'项目版', '用户版', '内置版'}, layers)
        # 体检状态列非空
        self.assertTrue(all(str(values[4]).strip('— ') for values in rows.values()))
        seams = win._pet_seams['skills']
        self.assertIn('hint', seams)
        self.assertIn('filter', seams)
        self.assertIn('detail', seams)

    def test_real_package_expands_children_and_child_actions_stay_scoped(self):
        self.add_skills()
        package = self.program / 'data' / 'skills' / STAGE_DIR / 'pack-dir'
        self.write_package(package)
        win = self.hub()
        self.assertTrue(self.wait_rows(win, 4), '包应作为一个父行进入列表')
        tree = self.tree(win)
        self.assertEqual('pack-main', tree.get_children()[0], '真实技能包应排在独立 SKILL 前')
        values = tree.item('pack-main', 'values')
        self.assertEqual('技能包', values[5])
        self.assertEqual('用户版', values[3])
        children = tree.get_children('pack-main')
        self.assertEqual(1, len(children))
        child = children[0]
        self.assertTrue(child.startswith('child|pack-main|'))
        child_values = tree.item(child, 'values')
        self.assertEqual('包内子技能', child_values[5])
        self.assertEqual('随父包', child_values[4])
        self.assertIn('不单独执行', child_values[6])

        self.win.deiconify()
        win.deiconify()
        win.update()
        tree.focus_force()
        tree.focus('pack-main')
        tree.event_generate('<space>')
        win.update()
        self.assertTrue(tree.item('pack-main', 'open'), '空格应能展开真实技能包')
        tree.selection_set(child)
        tree.event_generate('<<TreeviewSelect>>')
        win.update()
        seams = win._pet_seams['skills']
        detail = seams['detail'].get('1.0', 'end-1c')
        self.assertIn('包内子技能', detail)
        self.assertIn('所属包：pack-main', detail)
        self.assertIn('nested/pack-child.skill.md', detail)
        with mock.patch('pet_skills_manage.ask_confirmation') as confirm:
            self.assertIsNone(pet_skills_manage.toggle_disabled(
                self.pet, tree, seams['state'], seams['refresh'], seams['hint']))
            self.assertIsNone(pet_skills_manage.remove_skill(
                self.pet, tree, seams['state'], seams['refresh'], seams['hint']))
        confirm.assert_not_called()
        self.assertIn('父包', seams['hint'].get())
        self.assertTrue((package / 'nested' / 'pack-child.skill.md').is_file())

    def test_package_disable_and_enable_apply_to_whole_package(self):
        self.add_skills()
        package = self.program / 'data' / 'skills' / STAGE_DIR / 'pack-dir'
        self.write_package(package)
        win = self.hub()
        self.assertTrue(self.wait_rows(win, 4))
        tree = self.tree(win)
        seams = win._pet_seams['skills']
        tree.selection_set('pack-main')
        with mock.patch('pet_skills_manage.ask_confirmation', return_value=True):
            self.assertTrue(pet_skills_manage.toggle_disabled(
                self.pet, tree, seams['state'], seams['refresh'], seams['hint']))
        self.assertTrue(self.wait_tree(
            win, lambda t: 'disabled|pack-main' in t.get_children()))
        row = 'disabled|pack-main'
        values = tree.item(row, 'values')
        self.assertEqual('技能包', values[5])
        self.assertEqual('已禁用', values[4])
        self.assertEqual(1, len(tree.get_children(row)),
                         '禁用后的包仍应能看出子技能随包管理')
        tree.selection_set(row)
        with mock.patch('pet_skills_manage.ask_confirmation', return_value=True):
            self.assertTrue(pet_skills_manage.toggle_disabled(
                self.pet, tree, seams['state'], seams['refresh'], seams['hint']))
        self.assertTrue(self.wait_tree(
            win, lambda t: 'pack-main' in t.get_children()
            and 'disabled|pack-main' not in t.get_children()))

    def test_stage_root_entry_is_not_mislabeled_as_package(self):
        self.add_skills()
        stage_root = self.program / 'data' / 'skills' / STAGE_DIR
        entry = stage_root / 'SKILL.md'
        entry.write_text(
            '---\nname: stage-root-entry\ndisplayName: 阶段总入口\ndescription: 阶段说明\n---\n\n阶段正文。\n',
            encoding='utf-8')
        win = self.hub()
        self.assertTrue(self.wait_rows(win, 4))
        tree = self.tree(win)
        self.assertIn('stage-root-entry', tree.get_children())
        values = tree.item('stage-root-entry', 'values')
        self.assertEqual('阶段入口', values[5])
        self.assertEqual('用户版', values[3])
        self.assertNotEqual('技能包', values[5])
        self.assertEqual((), tree.get_children('stage-root-entry'),
                         '阶段目录根部总入口不能伪造子技能树')

        tree.selection_set('stage-root-entry')
        tree.event_generate('<<TreeviewSelect>>')
        win.update()
        seams = win._pet_seams['skills']
        self.assertIn('disabled', seams['delete'].state())
        self.assertIn('阶段总入口', seams['delete_tip'].text)
        with mock.patch('pet_skills_manage.ask_confirmation') as confirm, \
                mock.patch('pet_skills_manage.ask_string') as ask:
            self.assertIsNone(pet_skills_manage.remove_skill(
                self.pet, tree, seams['state'], seams['refresh'], seams['hint']))
            self.assertIsNone(pet_skills_manage.rename_skill(
                self.pet, tree, seams['state'], seams['refresh'], seams['hint']))
        confirm.assert_not_called()
        ask.assert_not_called()
        self.assertTrue(entry.is_file())
        with mock.patch('pet_skills_manage.platform_tools.open_path') as opener:
            result = pet_skills_manage.edit_skill(
                self.pet, tree, seams['state'], seams['hint'])
        self.assertEqual(entry, result)
        opener.assert_called_once_with(entry)

    def test_legacy_package_source_filters_and_actions_are_explicit(self):
        self.add_skills()
        package = self.program / 'skills' / 'LegacyPack'
        self.write_package(package, name='legacy-entry')
        win = self.hub()
        self.assertTrue(self.wait_rows(win, 4))
        tree = self.tree(win)
        iid = 'legacy|LegacyPack'
        self.assertIn(iid, tree.get_children())
        values = tree.item(iid, 'values')
        self.assertEqual('旧包（未挂载）', values[3])
        self.assertEqual('未挂载', values[4])
        self.assertEqual('旧包', values[5])
        children = tree.get_children(iid)
        self.assertEqual(1, len(children), '旧包可查看内容，但内容仍不注册执行')
        self.assertEqual('包内子技能', tree.item(children[0], 'values')[5])

        seams = win._pet_seams['skills']
        seams['state']['source_filter'].set('旧包')
        win.update()
        self.assertEqual((iid,), tree.get_children())
        seams['state']['source_filter'].set('项目')
        win.update()
        self.assertEqual(('project-layer-skill',), tree.get_children())
        seams['state']['source_filter'].set('全部来源')
        seams['state']['filter_text'].set('pack-child')
        win.update()
        self.assertEqual((iid,), tree.get_children(), '子技能命中时父包只作定位外壳')
        self.assertEqual(1, len(tree.get_children(iid)))

        tree.selection_set(children[0])
        with mock.patch('pet_skills_manage.ask_confirmation') as confirm:
            self.assertIsNone(pet_skills_manage.toggle_disabled(
                self.pet, tree, seams['state'], seams['refresh'], seams['hint']))
        confirm.assert_not_called()
        tree.selection_set(iid)
        with mock.patch('pet_skills_manage.ask_confirmation', return_value=False) as confirm:
            self.assertIsNone(pet_skills_manage.remove_skill(
                self.pet, tree, seams['state'], seams['refresh'], seams['hint']))
        confirm.assert_called_once()
        self.assertTrue(package.exists())
        with mock.patch('pet_skills_manage.ask_confirmation') as confirm:
            self.assertIsNone(pet_skills_manage.toggle_disabled(
                self.pet, tree, seams['state'], seams['refresh'], seams['hint']))
            self.assertIsNone(pet_skills_manage.rename_skill(
                self.pet, tree, seams['state'], seams['refresh'], seams['hint']))
        confirm.assert_not_called()

    def test_text_source_and_stage_filters_keep_rows_traceable(self):
        self.add_skills()
        package = self.program / 'data' / 'skills' / STAGE_DIR / 'pack-dir'
        self.write_package(package)
        win = self.hub()
        self.assertTrue(self.wait_rows(win, 4))
        tree = self.tree(win)
        seams = win._pet_seams['skills']
        state = seams['state']
        state['filter_text'].set('user-layer')
        win.update()
        self.assertEqual(('user-layer-skill',), tree.get_children())
        state['filter_text'].set('')
        state['source_filter'].set('用户')
        win.update()
        self.assertEqual({'pack-main', 'user-layer-skill'}, set(tree.get_children()))
        script_label = next(label for label, sid in state['stage_ids'].items() if sid == 'script')
        state['stage_filter'].set(script_label)
        win.update()
        self.assertEqual({'pack-main', 'user-layer-skill'}, set(tree.get_children()))
        state['source_filter'].set('项目')
        win.update()
        self.assertEqual(('project-layer-skill',), tree.get_children())
        state['stage_filter'].set('全部阶段')
        state['source_filter'].set('全部来源')
        state['filter_text'].set('pack-child')
        win.update()
        self.assertEqual(('pack-main',), tree.get_children())
        self.assertEqual(1, len(tree.get_children('pack-main')))
        values = tree.item(tree.get_children('pack-main')[0], 'values')
        self.assertEqual('包内子技能', values[5])

    def test_project_isolated_registry(self):
        # 另一个项目的 skills/ 不进本项目列表（T5 隔离口径延续到管理页）。
        self.add_skills()
        other = Path(self.tmp.name) / 'other'
        (other / 'skills' / STAGE_DIR).mkdir(parents=True)
        write_skill(other / 'skills' / STAGE_DIR, 'other-project-skill')
        win = self.hub()
        self.assertTrue(self.wait_rows(win, 3))
        names = [self.tree(win).item(iid, 'values')[0] for iid in self.tree(win).get_children()]
        self.assertNotIn('other-project-skill', names)

    def test_residue_entry_lists_package_and_requires_both_confirmations(self):
        package = self.program / 'skills' / 'AIGC创作全流程'
        package.mkdir(parents=True)
        (package / 'README.md').write_text('总包说明', encoding='utf-8')
        other = self.program / 'skills' / 'imagegen'
        other.mkdir()
        (other / 'SKILL.md').write_text('另一个包', encoding='utf-8')
        hub = self.hub()
        self.assertIn('残留包管理…', self._dialog_buttons(hub))
        win = pet_skills_manage.residue_dialog(self.pet, mock.Mock())
        self.addCleanup(win.destroy)
        seam = win._pet_seams['residue']
        rows = seam['tree'].get_children()
        self.assertEqual(rows, ('AIGC创作全流程', 'imagegen'))
        self.assertEqual(str(seam['tree']['selectmode']), 'extended')
        self.assertEqual(seam['tree']['columns'], ('name', 'path', 'count', 'size', 'description'))
        seam['tree'].selection_set(rows)
        with mock.patch.object(pet_skills_manage, 'ask_confirmation', return_value=False) as confirm:
            self.assertIsNone(seam['dispose']())
            self.assertEqual(confirm.call_count, 1)
        with mock.patch.object(pet_skills_manage, 'ask_confirmation', side_effect=[True, False]) as confirm:
            self.assertIsNone(seam['dispose']())
            self.assertEqual(confirm.call_count, 2)
        self.assertTrue(package.exists())
        self.win.update()
        for child in self.walk(win, self.ttk.Button):
            if isinstance(child, self.ttk.Button):
                self.assertGreater(child.winfo_width(), 0)
                self.assertLessEqual(child.winfo_rootx() + child.winfo_width(), win.winfo_rootx() + win.winfo_width())
        with mock.patch.object(pet_skills_manage, 'ask_confirmation', return_value=True) as confirm:
            result = seam['dispose']()
            self.assertTrue(result.ok, result.reason)
            self.assertEqual(confirm.call_count, 2)
        self.assertFalse(package.exists())
        self.assertFalse(other.exists())
        self.assertEqual(len(result.data['records']), 2)
        self.assertEqual(seam['tree'].get_children(), ())

    def test_note_dialog_shows_body(self):
        self.add_skills()
        win = self.hub()
        self.assertTrue(self.wait_rows(win, 3))
        self.select(win, 'user-layer-skill')
        note = pet_skills_manage.show_note(self.pet, self.tree(win),
                                           win._pet_seams['skills']['state'])
        self.assertIsNotNone(note)
        self.addCleanup(note.destroy)

    def test_health_dialog_opens_report(self):
        self.add_skills()
        win = self.hub()
        self.assertTrue(self.wait_rows(win, 3))
        report = pet_skills_manage.health_dialog(self.pet, win._pet_seams['skills']['state'])
        self.assertIsNotNone(report)
        self.addCleanup(report.destroy)

    def test_builtin_delete_is_refused(self):
        self.add_skills()
        win = self.hub()
        self.assertTrue(self.wait_rows(win, 3))
        self.select(win, 'pipeline-script-preparation')
        seams = win._pet_seams['skills']
        result = pet_skills_manage.remove_skill(self.pet, self.tree(win), seams['state'],
                                                 seams['refresh'], seams['hint'])
        self.assertIsNone(result)
        self.assertIn('只读', seams['hint'].get())
        self.assertTrue(self.builtin.is_file())

    def test_user_delete_moves_to_recycle(self):
        self.add_skills()
        win = self.hub()
        self.assertTrue(self.wait_rows(win, 3))
        self.select(win, 'user-layer-skill')
        seams = win._pet_seams['skills']
        with mock.patch('pet_skills_manage.ask_confirmation', return_value=True) as confirm:
            result = pet_skills_manage.remove_skill(self.pet, self.tree(win), seams['state'],
                                                     seams['refresh'], seams['hint'])
        self.assertTrue(result)
        confirm.assert_called_once()
        self.assertFalse(self.user.exists())
        self.assertIn('回收站', seams['hint'].get())

    def _dialog_buttons(self, dialog):
        from ui_widgets import SecondaryButton
        return {str(child.cget('text')): child for child in self.walk(dialog, SecondaryButton)}

    def walk(self, widget, kind):
        found = []
        if isinstance(widget, kind):
            found.append(widget)
        for child in widget.winfo_children():
            found.extend(self.walk(child, kind))
        return found

    def lock_selected_skill(self, name):
        from agent.core import save
        from stage_layout import skill_config_path
        save(skill_config_path(self.project), {
            'production_locks': {'aspect_ratio': '9:16'},
            'script': {'skills': [name]}})

    def test_occupied_selection_disables_delete_and_explains_reason(self):
        self.add_skills()
        self.lock_selected_skill('user-layer-skill')
        win = self.hub()
        self.assertTrue(self.wait_rows(win, 3))
        seams = win._pet_seams['skills']
        tree = self.select(win, 'user-layer-skill')
        tree.event_generate('<<TreeviewSelect>>')
        win.update()
        self.assertIn('disabled', seams['delete'].state())
        self.assertIn('制作锁', seams['delete_tip'].text)
        with mock.patch('pet_skills_manage.ask_confirmation') as confirm:
            self.assertIsNone(pet_skills_manage.remove_skill(
                self.pet, tree, seams['state'], seams['refresh'], seams['hint']))
        confirm.assert_not_called()
        self.assertTrue(self.user.is_file())
        tree.selection_set('project-layer-skill')
        tree.event_generate('<<TreeviewSelect>>')
        win.update()
        self.assertNotIn('disabled', seams['delete'].state())

    def test_occupancy_created_during_confirmation_blocks_delete(self):
        self.add_skills()
        win = self.hub()
        self.assertTrue(self.wait_rows(win, 3))
        tree = self.select(win, 'user-layer-skill')
        seams = win._pet_seams['skills']

        def confirm_and_lock(*args, **kwargs):
            self.lock_selected_skill('user-layer-skill')
            return True

        with mock.patch('pet_skills_manage.ask_confirmation', side_effect=confirm_and_lock):
            self.assertIsNone(pet_skills_manage.remove_skill(
                self.pet, tree, seams['state'], seams['refresh'], seams['hint']))
        self.assertTrue(self.user.is_file())
        self.assertIn('制作锁', seams['hint'].get())
        self.assertIn('disabled', seams['delete'].state())
        self.assertIn('制作锁', seams['delete_tip'].text)

    def test_import_dialog_offers_five_sources(self):
        win = self.hub()
        state = win._pet_seams['skills']['state']
        dialog = pet_skills_manage.import_dialog(self.pet, state, lambda: None)
        self.assertIsNotNone(dialog)
        self.addCleanup(dialog.destroy)
        buttons = self._dialog_buttons(dialog)
        for label in ('文件', '文件夹', 'ZIP', '仓库', '链接', '关闭'):
            self.assertIn(label, buttons)

    def test_file_import_lands_in_user_stage_dir(self):
        self.add_skills()
        source = Path(self.tmp.name) / 'incoming.skill.md'
        source.write_text('---\nname: manage-imported\ndisplayName: 管理页导入\n'
                          'description: 测试\nstage: 剧本准备\n---\n正文\n',
                          encoding='utf-8')
        win = self.hub()
        state = win._pet_seams['skills']['state']
        refreshed = []
        dialog = pet_skills_manage.import_dialog(self.pet, state, lambda: refreshed.append(1))
        self.addCleanup(dialog.destroy)
        buttons = self._dialog_buttons(dialog)
        # 「导入到」默认「项目」；切成「全局」走用户层。
        layer_box = next(child for child in self.walk(dialog, self.ttk.Combobox)
                         if str(child.get()) == '项目')
        layer_box.current(1)
        self.assertEqual(str(layer_box.get()), '全局')
        from ui_dialogs import FileDialog
        with mock.patch.object(FileDialog, 'open_file', return_value=str(source)), \
                mock.patch('pet_skills_manage.ask_confirmation', return_value=True), \
                mock.patch('pet_skills_manage.notify') as notify:
            buttons['文件'].invoke()
        # 默认阶段留「自动」、SKILL 自带 stage: 剧本准备 → 用户层对应阶段目录。
        target_dir = state['registry'].stage_directory_for('script', 'user')
        self.assertTrue((target_dir / source.name).is_file())
        self.assertTrue(refreshed)
        messages = [str(call.args[1]) for call in notify.call_args_list if len(call.args) > 1]
        self.assertTrue(any('manage-imported' in text for text in messages))

    def test_disable_shows_greyed_row_and_enable_restores(self):
        # T8：禁用后行灰显「已禁用」，文件保留；再点「禁用/启用」恢复。
        self.add_skills()
        win = self.hub()
        self.assertTrue(self.wait_rows(win, 3))
        self.select(win, 'user-layer-skill')
        seams = win._pet_seams['skills']
        with mock.patch('pet_skills_manage.ask_confirmation', return_value=True):
            self.assertTrue(pet_skills_manage.toggle_disabled(
                self.pet, self.tree(win), seams['state'], seams['refresh'], seams['hint']))
        tree = self.tree(win)
        self.assertTrue(self.wait_tree(
            win, lambda t: 'disabled|user-layer-skill' in t.get_children()))
        values = tree.item('disabled|user-layer-skill', 'values')
        self.assertEqual('已禁用', values[4])
        # 文件仍在盘上。
        self.assertTrue((self.program / 'data' / 'skills' / STAGE_DIR
                         / 'user-layer-skill.skill.md').is_file())
        # 重新选中禁用行再启用。
        tree.selection_set('disabled|user-layer-skill')
        with mock.patch('pet_skills_manage.ask_confirmation', return_value=True):
            self.assertTrue(pet_skills_manage.toggle_disabled(
                self.pet, tree, seams['state'], seams['refresh'], seams['hint']))
        self.assertTrue(self.wait_tree(
            win, lambda t: 'user-layer-skill' in t.get_children()
            and 'disabled|user-layer-skill' not in t.get_children()))

    def test_builtin_disable_and_enable_are_available(self):
        self.add_skills()
        win = self.hub()
        self.assertTrue(self.wait_rows(win, 3))
        name = 'pipeline-script-preparation'
        self.select(win, name)
        seams = win._pet_seams['skills']
        with mock.patch('pet_skills_manage.ask_confirmation', return_value=True) as confirm:
            result = pet_skills_manage.toggle_disabled(
                self.pet, self.tree(win), seams['state'], seams['refresh'], seams['hint'])
        self.assertTrue(result)
        confirm.assert_called_once()
        self.assertIn('已禁用', seams['hint'].get())
        self.assertTrue(self.wait_tree(win, lambda t: 'disabled|' + name in t.get_children()))
        self.select(win, 'disabled|' + name)
        with mock.patch('pet_skills_manage.ask_confirmation', return_value=True):
            self.assertTrue(pet_skills_manage.toggle_disabled(
                self.pet, self.tree(win), seams['state'], seams['refresh'], seams['hint']))
        self.assertTrue(self.wait_tree(win, lambda t: name in t.get_children()
                                     and 'disabled|' + name not in t.get_children()))

    def test_rename_flows_through_plan_and_apply(self):
        self.add_skills()
        win = self.hub()
        self.assertTrue(self.wait_rows(win, 3))
        self.select(win, 'user-layer-skill')
        seams = win._pet_seams['skills']
        old_file = self.program / 'data' / 'skills' / STAGE_DIR / 'user-layer-skill.skill.md'
        with mock.patch('pet_skills_manage.ask_string', return_value='user-layer-v2'), \
                mock.patch('pet_skills_manage.ask_confirmation', return_value=True), \
                mock.patch('pet_skills_manage._sync_agents_background') as sync_bg, \
                mock.patch('pet_skills_manage.notify') as notify:
            result = pet_skills_manage.rename_skill(
                self.pet, self.tree(win), seams['state'], seams['refresh'], seams['hint'])
        sync_bg.assert_called_once()
        messages = [str(call.args[1]) for call in notify.call_args_list if len(call.args) > 1]
        self.assertTrue(any('user-layer-v2' in text for text in messages))
        self.assertIsNotNone(result)
        self.assertFalse(old_file.exists())
        self.assertTrue((self.program / 'data' / 'skills' / STAGE_DIR
                         / 'user-layer-v2.skill.md').is_file())
        tree = self.tree(win)
        self.assertTrue(self.wait_tree(
            win, lambda t: 'user-layer-v2' in t.get_children()))
        names = [tree.item(iid, 'values')[0] for iid in tree.get_children()]
        self.assertIn('user-layer-v2', names)
        self.assertNotIn('user-layer-skill', names)

    def test_edit_opens_system_handler(self):
        self.add_skills()
        win = self.hub()
        self.assertTrue(self.wait_rows(win, 3))
        self.select(win, 'user-layer-skill')
        seams = win._pet_seams['skills']
        with mock.patch('pet_skills_manage.platform_tools.open_path') as opener:
            result = pet_skills_manage.edit_skill(
                self.pet, self.tree(win), seams['state'], seams['hint'])
        self.assertIsNotNone(result)
        opener.assert_called_once()
        self.assertTrue(str(opener.call_args.args[0]).endswith('user-layer-skill.skill.md'))

    def test_disabled_skill_deletes_via_entry_point(self):
        self.add_skills()
        win = self.hub()
        self.assertTrue(self.wait_rows(win, 3))
        self.select(win, 'user-layer-skill')
        seams = win._pet_seams['skills']
        with mock.patch('pet_skills_manage.ask_confirmation', return_value=True):
            pet_skills_manage.toggle_disabled(
                self.pet, self.tree(win), seams['state'], seams['refresh'], seams['hint'])
        tree = self.tree(win)
        self.assertTrue(self.wait_tree(
            win, lambda t: 'disabled|user-layer-skill' in t.get_children()))
        tree.selection_set('disabled|user-layer-skill')
        with mock.patch('pet_skills_manage.ask_confirmation', return_value=True):
            result = pet_skills_manage.remove_skill(
                self.pet, self.tree(win), seams['state'], seams['refresh'], seams['hint'])
        self.assertTrue(result)
        self.assertFalse((self.program / 'data' / 'skills' / STAGE_DIR
                          / 'user-layer-skill.skill.md').exists())


if __name__ == '__main__':
    unittest.main()
