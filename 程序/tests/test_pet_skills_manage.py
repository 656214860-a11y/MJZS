# -*- coding: utf-8 -*-
"""「设置 → SKILL 管理」页自检（生命周期任务书 T7／R3089）。

覆盖：列表渲染（三层来源与体检状态列）、说明弹窗、体检详情、删除确认
（内置层拒绝、用户层进回收站）、导入对话框五入口与单文件安装管线。
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
import pet_ui
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

    def add_skills(self):
        self.builtin = write_skill(self.program / 'skills' / STAGE_DIR,
                                   'pipeline-script-preparation')
        self.user = write_skill(self.program / 'data' / 'skills' / STAGE_DIR,
                                'user-layer-skill')
        self.project_skill = write_skill(self.project / 'skills' / STAGE_DIR,
                                         'project-layer-skill')

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


if __name__ == '__main__':
    unittest.main()
