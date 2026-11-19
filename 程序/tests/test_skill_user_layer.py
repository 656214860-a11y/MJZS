"""R2077：用户导入的 SKILL 独立放在 data/skills/<阶段>/，同名用户优先，旧导入迁移。"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import codex_skill_sync
import skill_import_service
import skill_panel
import skill_panel_import
import skill_registry
import workflow_settings
from agent.core import save
from test_skills import write_skill

STAGE_DIR = '01剧本准备SKILL'


class UserLayerTestCase(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.program = self.base / 'program'
        self.builtin = self.program / 'skills'
        self.user = self.program / 'data' / 'skills'
        (self.builtin / STAGE_DIR).mkdir(parents=True)

    def registry(self):
        return skill_registry.Registry(self.builtin, user_root=self.user).scan(force=True)


class RegistryLayerTests(UserLayerTestCase):
    def test_engine_candidates_reuse_registered_packages_and_project_override(self):
        from domain import skill_command
        from desktop_shared_send import _resolve_skill
        from types import SimpleNamespace
        project_root = self.base / 'project' / 'skills'
        user = self.user / STAGE_DIR / 'user-package' / 'SKILL.md'
        project = project_root / STAGE_DIR / 'project-package' / 'SKILL.md'
        for path, description in ((user, '用户说明'), (project, '项目说明')):
            path.parent.mkdir(parents=True)
            path.write_text('---\nname: installed-engine\ndescription: ' + description
                            + '\n---\n合法入口', encoding='utf-8')
        flat = write_skill(self.user / STAGE_DIR, 'flat-user')
        bad = self.user / STAGE_DIR / 'invalid-package'
        bad.mkdir()
        (bad / 'run.py').write_text('raise AssertionError("must not execute")', encoding='utf-8')
        registry = skill_registry.Registry(self.builtin, user_root=self.user,
                                           project_root=project_root.parent).scan(force=True)
        items = registry.getAll()
        self.assertEqual(skill_command.sub_engine_names(items), ('installed-engine',))
        parsed = skill_command.parse_command('/installed-engine 继续', skills=items)
        self.assertEqual(parsed['kind'], 'engine')
        self.assertEqual(registry.get('installed-engine').path, project)
        host = SimpleNamespace(root=project_root.parent, shared_input=SimpleNamespace(skill_items=lambda: items))
        with mock.patch('desktop_shared_send._skill_items', return_value=items):
            stage, path = _resolve_skill(host, parsed)
        self.assertEqual(path, project)
        self.assertEqual(stage, 'script')
        self.assertEqual(skill_command.parse_command('/flat-user', skills=items)['kind'], 'skill')
        self.assertTrue(flat.is_file())

    def test_user_version_overrides_builtin_and_builtin_returns_after_delete(self):
        write_skill(self.builtin / STAGE_DIR, 'lead', display='内置版')
        user_file = write_skill(self.user / STAGE_DIR, 'lead', display='用户版')
        registry = self.registry()
        skill = registry.get('lead')
        self.assertEqual((skill.displayName, skill.layer), ('用户版', 'user'))
        self.assertEqual(registry.problems(), [], '同名用户版不是错误')
        self.assertTrue(any('覆盖内置版' in item for item in registry.warnings()))
        user_file.unlink()
        skill = registry.scan(force=True).get('lead')
        self.assertEqual((skill.displayName, skill.layer), ('内置版', 'builtin'))

    def test_new_import_directory_is_user_layer_stage_directory(self):
        registry = self.registry()
        self.assertEqual(registry.user_stage_directory_for('script'), self.user / STAGE_DIR)
        self.assertEqual(skill_registry.default_registry(self.program).user_root, self.user)

    def test_user_reference_falls_back_to_builtin_shared_package(self):
        shared = self.builtin / 'shared-reference' / 'rule.md'
        shared.parent.mkdir()
        shared.write_text('共享规则', encoding='utf-8')
        source = write_skill(self.user / STAGE_DIR, 'lead')
        source.write_text(source.read_text(encoding='utf-8') + '\n见 [规则](../shared-reference/rule.md)\n',
                          encoding='utf-8')
        relative = Path('../shared-reference/rule.md')
        self.assertEqual(skill_registry.resolve_reference(source, relative, program=self.program),
                         shared.resolve())
        roots = (self.builtin.resolve(), self.user.resolve())
        with mock.patch.object(skill_registry, 'skill_roots', lambda program=None: roots):
            report = workflow_settings._inline_skill_report(source, strict=True)
        self.assertIn('共享规则', str(report))


class UserImportTests(UserLayerTestCase):
    def panel(self, registry):
        panel = mock.Mock()
        panel.stage = 'script'
        panel.registry = registry
        panel.skill_content.winfo_children.return_value = []
        return panel

    def test_import_lands_in_user_layer_with_ledger_and_soft_override_warning(self):
        builtin = write_skill(self.builtin / STAGE_DIR, 'lead', display='内置版')
        before = builtin.read_bytes()
        source = write_skill(self.base / 'download', 'lead', display='用户版')
        panel = self.panel(self.registry())
        with mock.patch.object(skill_panel_import, 'FileDialog') as dialog, \
                mock.patch.object(skill_panel_import, 'confirm', return_value=True) as confirm:
            dialog.return_value.open_file.return_value = str(source)
            result = skill_panel.Panel.add_skill_from_file(panel)
        self.assertEqual(result, self.user / STAGE_DIR / 'lead.skill.md')
        self.assertIn('将覆盖内置 SKILL', confirm.call_args.args[2])
        self.assertEqual(builtin.read_bytes(), before, '内置版不得被改动')
        ledger = skill_import_service.read_json(skill_import_service.ledger_path(self.program))
        self.assertIn(STAGE_DIR + '/lead.skill.md', ledger['items'])
        self.assertFalse((self.builtin / skill_import_service.LEDGER_NAME).exists())
        self.assertEqual(panel.registry.get('lead').layer, 'user')

    def test_same_name_within_user_layer_is_still_blocked(self):
        write_skill(self.user / '02剧本结构SKILL', 'lead')
        source = write_skill(self.base / 'download', 'lead')
        panel = self.panel(self.registry())
        with mock.patch.object(skill_panel_import, 'FileDialog') as dialog, \
                mock.patch.object(skill_panel_import, 'confirm', return_value=True) as confirm:
            dialog.return_value.open_file.return_value = str(source)
            result = skill_panel.Panel.add_skill_from_file(panel)
        self.assertIsNone(result)
        confirm.assert_not_called()
        self.assertFalse((self.user / STAGE_DIR / 'lead.skill.md').exists())


class LegacyMigrationTests(UserLayerTestCase):
    def legacy(self, items):
        save(self.builtin / skill_import_service.LEDGER_NAME, {'version': 1, 'items': items})

    def package(self, name, reference='references/rules.md'):
        folder = self.builtin / STAGE_DIR / name
        (folder / 'references').mkdir(parents=True)
        (folder / 'references' / 'rules.md').write_text('规则', encoding='utf-8')
        (folder / 'SKILL.md').write_text('---\nname: %s\n---\n# 包\n见 [规则](%s)\n' % (name, reference),
                                         encoding='utf-8')
        return folder

    def test_ledger_items_move_and_unregistered_files_stay(self):
        self.package('ext-pack')
        write_skill(self.builtin / STAGE_DIR, 'lead')
        manual = write_skill(self.builtin / STAGE_DIR, 'manual')
        row = {'source': 'x', 'kind': 'manifest', 'name': 'lead', 'sha256': '0' * 64}
        self.legacy({STAGE_DIR + '/lead.skill.md': row,
                     STAGE_DIR + '/ext-pack': dict(row, kind='package', name='ext-pack'),
                     '../outside.skill.md': row})
        report = skill_import_service.migrate_legacy_imports(self.program)
        self.assertEqual(sorted(report['moved']), [STAGE_DIR + '/ext-pack', STAGE_DIR + '/lead.skill.md'])
        self.assertEqual(report['kept'], ['../outside.skill.md'])
        self.assertTrue((self.user / STAGE_DIR / 'ext-pack' / 'references' / 'rules.md').is_file())
        self.assertTrue((self.user / STAGE_DIR / 'lead.skill.md').is_file())
        self.assertFalse((self.builtin / STAGE_DIR / 'lead.skill.md').exists())
        self.assertTrue(manual.is_file(), '台账外的文件分不清来源，不迁')
        ledger = skill_import_service.read_json(skill_import_service.ledger_path(self.program))
        self.assertEqual(ledger['items'][STAGE_DIR + '/lead.skill.md'], row)
        old = skill_import_service.read_json(self.builtin / skill_import_service.LEDGER_NAME)
        self.assertEqual(list(old['items']), ['../outside.skill.md'])
        self.assertEqual(self.registry().get('lead').layer, 'user')

    def test_fully_migrated_legacy_ledger_is_recycled_and_rerun_is_noop(self):
        write_skill(self.builtin / STAGE_DIR, 'lead')
        self.legacy({STAGE_DIR + '/lead.skill.md': {'kind': 'manifest', 'name': 'lead'}})
        self.assertEqual(skill_import_service.migrate_legacy_imports(self.program)['moved'],
                         [STAGE_DIR + '/lead.skill.md'])
        self.assertFalse((self.builtin / skill_import_service.LEDGER_NAME).exists())
        self.assertEqual(len(list((self.program / '工作流任务' / '回收站').rglob(skill_import_service.LEDGER_NAME))), 1)
        self.assertEqual(skill_import_service.migrate_legacy_imports(self.program), {'moved': [], 'kept': []})

    def test_failed_verification_moves_back_and_existing_user_copy_is_not_overwritten(self):
        self.package('broken', reference='references/missing.md')
        write_skill(self.builtin / STAGE_DIR, 'lead', display='旧导入')
        existing = write_skill(self.user / STAGE_DIR, 'lead', display='用户新版')
        before = existing.read_bytes()
        self.legacy({STAGE_DIR + '/broken': {'kind': 'package'}, STAGE_DIR + '/lead.skill.md': {}})
        report = skill_import_service.migrate_legacy_imports(self.program)
        self.assertEqual(report['moved'], [])
        self.assertEqual(sorted(report['kept']), [STAGE_DIR + '/broken', STAGE_DIR + '/lead.skill.md'])
        self.assertTrue((self.builtin / STAGE_DIR / 'broken' / 'SKILL.md').is_file())
        self.assertFalse((self.user / STAGE_DIR / 'broken').exists())
        self.assertEqual(existing.read_bytes(), before)


class CodexUserLayerTests(UserLayerTestCase):
    def test_user_layer_skill_is_synced_with_builtin_shared_path(self):
        write_skill(self.builtin / STAGE_DIR, 'pipeline-script-preparation')
        source = write_skill(self.user / STAGE_DIR, 'user-extra')
        with source.open('a', encoding='utf-8') as stream:
            stream.write('\n[规则](../shared-reference/reference.md)\n')
        reference = self.builtin / 'shared-reference' / 'reference.md'
        reference.parent.mkdir(parents=True, exist_ok=True)
        reference.write_text('共享规则', encoding='utf-8')
        home = self.base / 'codex' / 'skills'
        result = codex_skill_sync.sync_codex_skills(self.program, home)
        self.assertIn('user-extra', result['written'])
        body = (home / 'user-extra' / 'SKILL.md').read_text(encoding='utf-8')
        self.assertIn((self.builtin / 'shared-reference').resolve().as_posix(), body)

    def test_injected_migration_runs_before_sync_on_the_same_thread(self):
        calls = []
        with mock.patch.object(codex_skill_sync.executors, 'submit') as submit, \
                mock.patch.object(codex_skill_sync, 'sync_codex_skills', side_effect=lambda **kw: calls.append('sync')):
            codex_skill_sync.start_codex_skill_sync(self.program, before=lambda: calls.append('migrate'))
            submit.call_args.args[1]()
        self.assertEqual(calls, ['migrate', 'sync'])


if __name__ == '__main__':
    unittest.main()
