# -*- coding: utf-8 -*-
"""T9：SKILL 安全加固——不可信来源提示、安装完整性校验、外部字段映射。

确认框必须带来源行与「外部内容注入模型请求」警示；包内 ``scripts/`` 与
``.exe/.dll/.ps1/.bat`` 触发警告行；手改用户层安装后体检出现
``local-modified``；外部包 ``license``/``compatibility`` 进 meta 并在说明区
可见，``allowed-tools`` 只映射本应用已知工具名、其余进 constraints 提示。
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pet_skills_manage
import skill_import_service
import skill_panel_support
import skill_registry
import workflow_settings
from test_skill_archive_import import make_zip
from test_skill_repo_import import make_program


PKG_MD = ('---\nname: sec-pack\nstage: 剧本准备\n---\n# 安全测试包\n正文\n')
PKG_MD_LICENSE = ('---\nname: sec-pack\nstage: 剧本准备\nlicense: MIT\n'
                  'compatibility: Requires Python 3.10\n'
                  'allowed-tools: [script.generate, Read, Write]\n---\n'
                  '# 外部包\n正文\n')


class SecurityCase(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.program, self.registry = make_program(self.root)

    def package_dir(self, name='sec-pack', extra=None, md=PKG_MD):
        folder = self.root / 'src' / name
        folder.mkdir(parents=True)
        (folder / 'SKILL.md').write_text(md, encoding='utf-8')
        for rel, content in (extra or {}).items():
            path = folder / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
        return folder


class PackageAlertTests(SecurityCase):
    def test_scripts_dir_and_executables_are_flagged(self):
        folder = self.package_dir(extra={
            'scripts/deploy.sh': '#!/bin/sh\n',
            'evil.ps1': 'Get-Process',
            'lib/thing.EXE': 'MZ',
            'notes.txt': 'ok',
        })
        alerts = skill_import_service.package_alerts(folder)
        self.assertIn('scripts/', alerts)
        self.assertIn('evil.ps1', alerts)
        self.assertIn('lib/thing.EXE', alerts)
        self.assertNotIn('notes.txt', alerts)

    def test_clean_package_has_no_alerts(self):
        folder = self.package_dir(extra={'references/rules.md': '规则'})
        self.assertEqual([], skill_import_service.package_alerts(folder))

    def test_untrusted_notice_has_source_injection_and_alert_lines(self):
        folder = self.package_dir(extra={'evil.bat': '@echo off'})
        plan = {'name': 'sec-pack', 'kind': 'package',
                'source': folder / 'SKILL.md'}
        notice = skill_import_service.untrusted_source_notice(str(folder), plans=[plan])
        self.assertIn('来源：', notice)
        self.assertIn(str(folder), notice)
        self.assertIn('指令注入模型请求', notice)
        self.assertIn('evil.bat', notice)
        self.assertIn('不会运行', notice)


class ConfirmWarningTests(SecurityCase):
    def test_zip_with_evil_ps1_triggers_confirm_warning(self):
        zip_path = make_zip(self.root / 'evil.zip', {
            'pack/SKILL.md': PKG_MD,
            'pack/evil.ps1': 'Get-Process',
        })
        seen = []
        import skill_archive
        report = skill_archive.import_archive(
            zip_path, self.program, self.registry,
            confirm=lambda m: seen.append(m) or True)
        self.assertTrue(seen, '含可执行文件的包必须弹出确认框')
        message = seen[0]
        self.assertIn('evil.ps1', message)
        self.assertIn('指令注入模型请求', message)
        self.assertEqual(1, len(report['installed']))

    def test_repo_dir_with_scripts_folder_triggers_confirm_warning(self):
        folder = self.package_dir(extra={'scripts/run.sh': 'echo hi'})
        seen = []
        report = skill_import_service.import_from_repo(
            str(folder.parent), self.program, self.registry,
            confirm=lambda m: seen.append(m) or True)
        self.assertTrue(seen)
        self.assertIn('scripts/', seen[0])
        self.assertIn('指令注入模型请求', seen[0])
        self.assertEqual(1, len(report['installed']))

    def test_confirm_decline_still_blocks_alerted_import(self):
        zip_path = make_zip(self.root / 'evil.zip', {
            'pack/SKILL.md': PKG_MD,
            'pack/evil.dll': 'MZ',
        })
        import skill_archive
        with self.assertRaises(skill_import_service.ImportBlocked):
            skill_archive.import_archive(
                zip_path, self.program, self.registry, confirm=lambda m: False)

    def test_single_plan_install_shows_notice_on_alerts(self):
        folder = self.package_dir(extra={'evil.bat': '@echo off'})
        entry = skill_registry.Registry._package_source(folder)
        stage_dir = self.registry.user_stage_directory_for('script')
        plan = skill_import_service.plan_import(entry, stage_dir, 'script', self.registry)
        self.assertFalse(plan['problems'], '干净包不应有字段问题：%s' % plan['problems'])
        seen = []
        flow = pet_skills_manage._ImportFlow(
            pet=mock.Mock(), refresh=mock.Mock(), win=mock.Mock(),
            hint=mock.Mock(), stage_box=mock.Mock(), layer_var=mock.Mock(),
            state={'project': None, 'registry': self.registry})
        flow.confirm = lambda m: seen.append(m) or True
        result = flow.install_plan(plan, '文件夹导入完成')
        self.assertEqual('sec-pack', result)
        self.assertTrue(seen, '含可执行文件的单包导入必须弹确认框')
        self.assertIn('evil.bat', seen[0])
        self.assertIn('指令注入模型请求', seen[0])


class IntegrityTests(SecurityCase):
    def _install_package(self):
        import skill_archive
        folder = self.package_dir(extra={'references/rules.md': '规则'})
        zip_path = make_zip(self.root / 'pkg.zip', {
            'pack/SKILL.md': PKG_MD,
            'pack/references/rules.md': '规则',
        })
        report = skill_archive.import_archive(
            zip_path, self.program, self.registry, confirm=lambda m: True)
        self.assertEqual(1, len(report['installed']))
        return folder

    def test_hand_edit_is_flagged_local_modified_everywhere(self):
        self._install_package()
        installed = (self.program / 'data' / 'skills' / '01剧本准备SKILL'
                     / 'pack' / 'SKILL.md')
        self.assertTrue(installed.is_file(), str(installed))
        installed.write_text(installed.read_text(encoding='utf-8') + '\n手改\n',
                             encoding='utf-8')
        modified = skill_import_service.local_modifications(self.program)
        self.assertIn('sec-pack', modified)
        statuses = skill_import_service.check_updates(self.program, probe=lambda k, r: None)
        self.assertIn('local-modified', statuses.values())

    def test_untouched_install_reports_no_modification(self):
        self._install_package()
        self.assertEqual({}, skill_import_service.local_modifications(self.program))

    def test_health_report_surfaces_local_modified_warning(self):
        self._install_package()
        installed = (self.program / 'data' / 'skills' / '01剧本准备SKILL'
                     / 'pack' / 'SKILL.md')
        installed.write_text(installed.read_text(encoding='utf-8') + '\n手改\n',
                             encoding='utf-8')
        registry = skill_registry.Registry(
            skill_registry.default_root(self.program),
            user_root=skill_registry.default_user_root(self.program))
        report = workflow_settings.skill_health_report(
            registry, local_modified=skill_import_service.local_modifications(self.program))
        row = next(r for r in report['skills'] if r['name'] == 'sec-pack')
        self.assertTrue(any('local-modified' in w or '本地已修改' in w
                            for w in row['warnings']), row['warnings'])
        self.assertEqual('warning', row['status'])


class ExternalFieldTests(SecurityCase):
    def test_imported_package_meta_preserves_license_and_maps_known_tools(self):
        meta = skill_registry.imported_package_meta(
            {'name': 'x', 'license': 'MIT', 'compatibility': 'Requires Python 3.10',
             'allowed-tools': ['script.generate', 'Read', 'Write']},
            '# 外部包\n', Path('pkg'), Path('pkg/SKILL.md'),
            known_tools={'script.generate'})
        self.assertEqual('MIT', meta['license'])
        self.assertEqual('Requires Python 3.10', meta['compatibility'])
        self.assertEqual(['script.generate'], meta['tools'])
        self.assertTrue(any('Read' in c and 'Write' in c for c in meta['constraints']),
                        meta['constraints'])

    def test_unmapped_allowed_tools_all_go_to_constraints(self):
        meta = skill_registry.imported_package_meta(
            {'allowed-tools': ['Bash', 'WebFetch']}, '# x\n',
            Path('pkg'), Path('pkg/SKILL.md'))
        self.assertEqual([], meta['tools'])
        self.assertTrue(any('Bash' in c for c in meta['constraints']))

    def test_scan_maps_allowed_tools_against_builtin_vocabulary(self):
        builtin_dir = self.program / 'skills' / '01剧本准备SKILL'
        (builtin_dir / 'builtin-tool.skill.md').write_text(
            '---\nname: builtin-tool\ndisplayName: 内置\ndescription: d\n'
            'stage: script\ncapabilities: [creative-writing]\npreferredModels: []\n'
            'fallbackModels: []\ntools: [script.generate]\ndependsOn: []\n'
            'conflictsWith: []\nparallelizable: false\npaid: false\ninput: []\n'
            'output: []\nconstraints: []\nfeedback: []\nexamples: []\n---\n# 内置\n',
            encoding='utf-8')
        folder = self.package_dir(md=PKG_MD_LICENSE)
        entry = skill_registry.Registry._package_source(folder)
        user_dir = self.registry.user_stage_directory_for('script')
        plan = skill_import_service.plan_import(entry, user_dir, 'script', self.registry)
        skill_import_service.perform_import(plan, self.program)
        registry = skill_registry.Registry(
            skill_registry.default_root(self.program),
            user_root=skill_registry.default_user_root(self.program))
        skill = registry.getById('sec-pack')
        self.assertIsNotNone(skill)
        self.assertEqual('MIT', skill.meta.get('license'))
        self.assertEqual(['script.generate'], skill.tools)
        self.assertTrue(any('Read' in c for c in skill.constraints))

    def test_note_text_shows_license_and_compatibility(self):
        skill = skill_registry.Skill(
            {'name': 'x', 'displayName': '外部技能', 'description': '简介',
             'license': 'MIT', 'compatibility': 'Requires Python 3.10'},
            path=None)
        text = skill_panel_support.note_text(skill)
        self.assertIn('MIT', text)
        self.assertIn('Requires Python 3.10', text)


if __name__ == '__main__':
    unittest.main()
