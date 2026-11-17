# -*- coding: utf-8 -*-
"""T2：SKILL 导入来源扩展——本地文件夹直选与 ZIP 压缩包导入。

服务层 ``skill_archive.import_archive``：zipfile 安全解包（路径穿越／盘符／
体量护栏）→ 与仓库导入同一条「候选扫描→预检→确认→暂存→换入→试冻结→登记」
管线；面板新增「新增·文件夹」「新增·ZIP」两个入口；文件夹按
``Registry._package_source`` 口径认 SKILL.md（README 兜底）整包导入。
"""
import tempfile
import tkinter as tk
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import ui.skill_archive as skill_archive
import skill_import_service
import skill_panel
import skill_registry
from test_skill_repo_import import make_program
from test_skills import PanelTests


def make_zip(path, entries):
    """entries: {arcname: 文本内容或 bytes}；None 值表示目录条目。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            if content is None:
                archive.writestr(name.rstrip('/') + '/', '')
            else:
                archive.writestr(name, content)
    return path


SKILL_MD = ('---\nname: zip-pack\nstage: 剧本准备\n---\n'
            '# 压缩包技能\n见 [规则](references/rules.md)\n')
FOLDER_MD = ('---\nname: folder-pack\nstage: 剧本准备\n---\n'
             '# 文件夹技能\n见 [规则](references/rules.md)\n')


class ArchiveCase(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.program, self.registry = make_program(self.root)

    def import_zip(self, path, **kwargs):
        return skill_archive.import_archive(path, self.program, self.registry, **kwargs)


class ArchiveRejectionTests(ArchiveCase):
    def test_traversal_entry_is_rejected_and_nothing_escapes(self):
        zip_path = make_zip(self.root / 'evil.zip', {
            'pack/SKILL.md': SKILL_MD,
            '../evil.md': '# 逃逸',
        })
        with self.assertRaises(skill_import_service.ImportBlocked) as ctx:
            self.import_zip(zip_path, confirm=lambda m: True)
        self.assertIn('不安全', str(ctx.exception))
        self.assertFalse((self.root / 'evil.md').exists(), '路径穿越条目不得落到解压目录之外')
        user = self.program / 'data' / 'skills'
        self.assertFalse((user / '01剧本准备SKILL' / 'pack').exists())

    def test_absolute_and_drive_entries_are_rejected(self):
        for index, bad in enumerate(('/abs/evil.md', 'C:/Windows/evil.md', 'C:\\temp\\evil.md')):
            zip_path = make_zip(self.root / ('abs-%d.zip' % index), {bad: '# x'})
            with self.assertRaises(skill_import_service.ImportBlocked, msg=bad):
                self.import_zip(zip_path, confirm=lambda m: True)

    def test_entry_count_over_limit_is_rejected(self):
        entries = {'f%03d.txt' % i: 'x' for i in range(5)}
        zip_path = make_zip(self.root / 'many.zip', entries)
        with mock.patch.object(skill_archive, 'ARCHIVE_MAX_ENTRIES', 3):
            with self.assertRaises(skill_import_service.ImportBlocked) as ctx:
                self.import_zip(zip_path, confirm=lambda m: True)
        self.assertIn('条目', str(ctx.exception))

    def test_total_size_over_limit_is_rejected(self):
        zip_path = make_zip(self.root / 'big.zip', {'big.bin': 'x' * 4096})
        with mock.patch.object(skill_import_service, 'PACKAGE_MAX_BYTES', 1024):
            with self.assertRaises(skill_import_service.ImportBlocked) as ctx:
                self.import_zip(zip_path, confirm=lambda m: True)
        self.assertIn('体积', str(ctx.exception))

    def test_non_zip_file_is_rejected(self):
        fake = self.root / 'fake.zip'
        fake.write_text('这不是压缩包', encoding='utf-8')
        with self.assertRaises(skill_import_service.ImportBlocked):
            self.import_zip(fake, confirm=lambda m: True)

    def test_zip_without_skill_markers_is_rejected(self):
        zip_path = make_zip(self.root / 'empty.zip', {'readme.txt': '没有 SKILL', 'a/b.txt': 'x'})
        with self.assertRaises(skill_import_service.ImportBlocked) as ctx:
            self.import_zip(zip_path, confirm=lambda m: True)
        self.assertIn('SKILL', str(ctx.exception))


class ArchiveImportTests(ArchiveCase):
    def test_package_zip_installs_and_freezes(self):
        zip_path = make_zip(self.root / 'my-pack.zip', {
            'my-pack/SKILL.md': SKILL_MD,
            'my-pack/references/rules.md': '规则正文',
        })
        report = self.import_zip(zip_path, confirm=lambda m: True)
        self.assertEqual(len(report['installed']), 1)
        self.assertEqual(report['installed'][0]['name'], 'zip-pack')
        user = self.program / 'data' / 'skills'
        installed = user / '01剧本准备SKILL' / 'my-pack'
        self.assertTrue((installed / 'SKILL.md').is_file())
        self.assertTrue((installed / 'references' / 'rules.md').is_file())
        ledger = skill_import_service._read_items(
            skill_import_service.ledger_path(self.program))
        row = next(iter(ledger.values()))
        self.assertEqual(row['source'], str(zip_path.resolve()))
        self.assertEqual(row.get('source_kind'), 'archive')
        self.assertTrue(row['sha256'])

    def test_root_manifest_zip_installs_single_file(self):
        zip_path = make_zip(self.root / 'manifests.zip', {
            'solo.skill.md': '---\nname: solo\nstage: 剧本准备\n---\n# 单文件\n正文',
        })
        report = self.import_zip(zip_path, confirm=lambda m: True)
        self.assertEqual(len(report['installed']), 1)
        self.assertTrue((self.program / 'data' / 'skills' / '01剧本准备SKILL'
                         / 'solo.skill.md').is_file())

    def test_staging_is_recycled_after_import(self):
        zip_path = make_zip(self.root / 'pack.zip', {
            'pack/SKILL.md': SKILL_MD,
            'pack/references/rules.md': '规则',
        })
        report = self.import_zip(zip_path, confirm=lambda m: True)
        self.assertEqual(len(report['installed']), 1)
        leftovers = [p for p in (self.program / 'data' / 'skills').iterdir()
                     if p.name.startswith(skill_archive.ARCHIVE_STAGING_PREFIX)]
        self.assertEqual(leftovers, [])

    def test_confirm_decline_aborts_update_and_keeps_old_version(self):
        zip_path = make_zip(self.root / 'pack.zip', {
            'pack/SKILL.md': SKILL_MD,
            'pack/references/rules.md': '规则',
        })
        self.import_zip(zip_path, confirm=lambda m: True)
        installed = (self.program / 'data' / 'skills' / '01剧本准备SKILL' / 'pack' / 'SKILL.md')
        self.assertIn('zip-pack', installed.read_text(encoding='utf-8'))
        # 第二次导入命中「目标已存在」软问题：确认被拒绝时旧版必须原样保留。
        with self.assertRaises(skill_import_service.ImportBlocked) as ctx:
            self.import_zip(zip_path, confirm=lambda m: False)
        self.assertIn('已取消', str(ctx.exception))
        self.assertIn('zip-pack', installed.read_text(encoding='utf-8'))


class FolderImportTests(ArchiveCase):
    """文件夹导入：入口按 ``_package_source`` 口径，整包走同一 plan/perform 管线。"""

    def _folder(self, dirname='外部技能包', entry='SKILL.md', entry_text=FOLDER_MD):
        folder = self.root / dirname
        (folder / 'references').mkdir(parents=True)
        (folder / entry).write_text(entry_text, encoding='utf-8')
        (folder / 'references' / 'rules.md').write_text('规则正文', encoding='utf-8')
        return folder

    def test_skill_md_folder_imports_as_package(self):
        folder = self._folder()
        entry = skill_registry.Registry._package_source(folder)
        self.assertEqual(entry.name, 'SKILL.md')
        plan = skill_import_service.plan_import(
            entry, self.registry.user_stage_directory_for('script'), 'script', self.registry)
        self.assertEqual(plan['kind'], 'package')
        skill_import_service.perform_import(plan, self.program)
        installed = self.program / 'data' / 'skills' / '01剧本准备SKILL' / '外部技能包'
        self.assertTrue((installed / 'SKILL.md').is_file())
        self.assertTrue((installed / 'references' / 'rules.md').is_file())
        ledger = skill_import_service._read_items(
            skill_import_service.ledger_path(self.program))
        row = next(iter(ledger.values()))
        self.assertEqual(row.get('source_kind'), 'dir')

    def test_readme_entry_folder_imports_as_package(self):
        folder = self._folder(entry='README_ZH.md',
                              entry_text='# 集合包\n正文\n见 [规则](references/rules.md)')
        entry = skill_registry.Registry._package_source(folder)
        self.assertEqual(entry.name, 'README_ZH.md')
        plan = skill_import_service.plan_import(
            entry, self.registry.user_stage_directory_for('script'), 'script', self.registry)
        self.assertEqual(plan['kind'], 'package')
        self.assertTrue(plan['target'].name == 'README_ZH.md')
        skill_import_service.perform_import(plan, self.program)
        installed = self.program / 'data' / 'skills' / '01剧本准备SKILL' / '外部技能包'
        self.assertTrue((installed / 'README_ZH.md').is_file())

    def test_folder_without_package_entry_has_no_source(self):
        folder = self.root / '普通文件夹'
        folder.mkdir()
        (folder / 'notes.txt').write_text('x', encoding='utf-8')
        self.assertIsNone(skill_registry.Registry._package_source(folder))


class PanelImportSourceTests(unittest.TestCase):
    """面板两个新入口：文件夹走目录选择器，ZIP 走文件选择器，均落到同一管线。"""
    tk = tk
    setUp = PanelTests.setUp

    def _panel(self):
        builtin = self.desktop.app / 'skills'
        (builtin / '01剧本准备SKILL').mkdir(parents=True, exist_ok=True)
        registry = skill_registry.Registry(builtin,
                                           user_root=self.desktop.app / 'data' / 'skills')
        with mock.patch.object(skill_registry, 'default_registry', return_value=registry):
            panel = skill_panel.Panel(self.win, self.desktop, 'script')
        self.addCleanup(panel.destroy)
        return panel, registry

    def test_manage_menu_offers_folder_and_zip_entries(self):
        self.assertIn('新增·文件夹', skill_panel.MANAGE_LABELS)
        self.assertIn('新增·ZIP', skill_panel.MANAGE_LABELS)

    def test_folder_entry_uses_directory_picker_and_imports_package(self):
        panel, _registry = self._panel()
        folder = Path(self.tmp.name) / '外部技能包'
        (folder / 'references').mkdir(parents=True)
        (folder / 'SKILL.md').write_text(FOLDER_MD, encoding='utf-8')
        (folder / 'references' / 'rules.md').write_text('规则', encoding='utf-8')
        with mock.patch('ui_dialogs.filedialog.askdirectory', return_value=str(folder)):
            target = panel.add_skill_from_folder()
        self.assertIsNotNone(target)
        installed = (self.desktop.app / 'data' / 'skills' / '01剧本准备SKILL'
                     / '外部技能包' / 'SKILL.md')
        self.assertTrue(installed.is_file())
        self.assertIn('已新增 SKILL', panel.state.cget('text'))

    def test_folder_entry_rejects_non_package_folder(self):
        panel, _registry = self._panel()
        folder = Path(self.tmp.name) / '普通文件夹'
        folder.mkdir()
        (folder / 'notes.txt').write_text('x', encoding='utf-8')
        with mock.patch('ui_dialogs.filedialog.askdirectory', return_value=str(folder)):
            self.assertIsNone(panel.add_skill_from_folder())
        self.assertIn('不是 SKILL 包', panel.state.cget('text'))

    def test_zip_entry_uses_file_picker_and_imports(self):
        panel, _registry = self._panel()
        zip_path = make_zip(Path(self.tmp.name) / 'pack.zip', {
            'pack/SKILL.md': SKILL_MD,
            'pack/references/rules.md': '规则',
        })
        # 面板按 __file__ 定位程序目录；测试里把它指到临时程序目录，导入落在隔离区。
        fake_module = str(self.desktop.app / 'ui' / 'skill_import_service.py')
        with mock.patch('ui_dialogs.filedialog.askopenfilename', return_value=str(zip_path)), \
                mock.patch.object(skill_import_service, '__file__', fake_module):
            report = panel.add_skill_from_archive()
        self.assertIsNotNone(report)
        self.assertEqual(len(report['installed']), 1)
        installed = (self.desktop.app / 'data' / 'skills' / '01剧本准备SKILL'
                     / 'pack' / 'SKILL.md')
        self.assertTrue(installed.is_file())
        self.assertIn('ZIP 导入完成', panel.state.cget('text'))

    def test_choose_skill_action_dispatches_new_entries(self):
        panel, _registry = self._panel()
        panel.skill_action.set('新增·文件夹')
        with mock.patch.object(panel, 'add_skill_from_folder', return_value='ok') as folder, \
                mock.patch.object(panel, 'add_skill_from_archive', return_value='ok') as archive:
            self.assertEqual(panel.choose_skill_action(), 'ok')
            folder.assert_called_once()
            archive.assert_not_called()
            panel.skill_action.set('新增·ZIP')
            self.assertEqual(panel.choose_skill_action(), 'ok')
            archive.assert_called_once()
        self.assertEqual(panel.skill_action.get(), skill_panel.MANAGE_ALL)


if __name__ == '__main__':
    unittest.main()
