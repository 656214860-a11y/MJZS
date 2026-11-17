# -*- coding: utf-8 -*-
"""T8 SKILL 生命周期补全：启停用、重命名、version 优先比对、编辑定位。

- 禁用：``data/skills/disabled_skills.json`` 登记，文件保留、``getAll()`` 滤除、
  ``disabled_names``/``disabled_entries`` 供管理页灰显；内置层拒绝；项目层条目
  按项目隔离；发送边界 ``validate_selected_skills`` 报「已禁用」而非「未加载」。
- 重命名：``rename_plan`` 只读干跑统计受影响项目；``apply_rename`` 同步
  frontmatter ``name``（清单）或目录名（包）、全部项目 ``skill_config.json``
  引用、台账键与 ``sha256``、禁用登记；agent 同步标记由 ``getAll()`` 驱动自动重算。
- 版本：``check_updates`` 在来源比较时优先比 frontmatter ``version``，缺版本回退摘要。
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import skill_import_service
import skill_lifecycle_service
import skill_project_layer
import skill_registry
import workflow_settings
from orchestrator import agent_skill_sync
from test_skill_project_layer import _write
from test_skill_repo_import import make_program, write_manifest, write_package
from test_skill_update_check import import_file, ledger_rows

# 与 ``make_program`` 的内置层目录同名（无空格）；阶段判定按前两位数字，
# 项目层目录名宽松但这里保持一致口径。
STAGE_DIR = '01剧本准备SKILL'


def _project(root, program, name='proj', skills=None):
    """登记一个带 ``skill_config.json`` 的项目，并写进 ``program/projects.json``。"""
    project = Path(root) / name
    (project / 'skills' / STAGE_DIR).mkdir(parents=True, exist_ok=True)
    (project / 'skill_config.json').write_text(
        json.dumps({'script': {'model': '自动', 'skills': list(skills or [])}},
                   ensure_ascii=False), encoding='utf-8')
    cfg_path = Path(program) / 'projects.json'
    info = json.loads(cfg_path.read_text(encoding='utf-8')) if cfg_path.is_file() else {}
    info = info if isinstance(info, dict) else {}
    items = info.setdefault('projects', [])
    if not any(isinstance(record, dict) and record.get('path') == str(project)
               for record in items):
        items.append({'path': str(project)})
    info['active'] = str(project)
    cfg_path.write_text(json.dumps(info, ensure_ascii=False), encoding='utf-8')
    return project


class DisabledStoreTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.program, self.registry = make_program(self.root)

    def test_disable_filters_getall_and_enable_restores(self):
        source = _write(self.root / 'src' / 'alpha.skill.md', 'alpha')
        import_file(self.program, self.registry, source)
        self.registry.scan(force=True)
        self.assertIsNotNone(self.registry.getById('alpha'))
        skill_lifecycle_service.set_skill_disabled(self.program, self.registry, 'alpha', True)
        self.registry.scan(force=True)
        self.assertIsNone(self.registry.getById('alpha'))
        self.assertIn('alpha', self.registry.disabled_names())
        entries = self.registry.disabled_entries()
        self.assertEqual(1, len(entries))
        self.assertEqual('user', entries[0].get('layer'))
        # 文件保留在盘上，删登记即恢复。
        target = self.program / 'data' / 'skills' / STAGE_DIR / 'alpha.skill.md'
        self.assertTrue(target.is_file())
        skill_lifecycle_service.set_skill_disabled(self.program, self.registry, 'alpha', False)
        self.registry.scan(force=True)
        self.assertIsNotNone(self.registry.getById('alpha'))
        self.assertNotIn('alpha', self.registry.disabled_names())

    def test_builtin_layer_cannot_be_disabled(self):
        write_manifest(self.program / 'skills' / STAGE_DIR / 'builtin-one.skill.md',
                       name='builtin-one', stage='script')
        self.registry.scan(force=True)
        with self.assertRaises(skill_import_service.ImportBlocked):
            skill_lifecycle_service.set_skill_disabled(
                self.program, self.registry, 'builtin-one', True)

    def test_corrupt_disabled_file_reads_as_empty(self):
        path = skill_project_layer.disabled_skills_path(self.registry.user_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{broken', encoding='utf-8')
        self.assertEqual({}, skill_project_layer.load_disabled(self.registry.user_root))
        self.registry.scan(force=True)   # 不阻塞扫描

    def test_project_layer_disable_isolated_per_project(self):
        project_a = _project(self.root, self.program, 'projA')
        project_b = _project(self.root, self.program, 'projB')
        for project in (project_a, project_b):
            _write(project / 'skills' / STAGE_DIR / 'dup.skill.md', 'dup')
        reg_a = skill_registry.Registry(
            self.registry.root, user_root=self.registry.user_root,
            project_root=project_a).scan(force=True)
        reg_b = skill_registry.Registry(
            self.registry.root, user_root=self.registry.user_root,
            project_root=project_b).scan(force=True)
        self.assertIsNotNone(reg_a.getById('dup'))
        self.assertIsNotNone(reg_b.getById('dup'))
        skill_lifecycle_service.set_skill_disabled(self.program, reg_a, 'dup', True)
        reg_a.scan(force=True)
        reg_b.scan(force=True)
        self.assertIsNone(reg_a.getById('dup'))
        self.assertIn('dup', reg_a.disabled_names())
        self.assertIsNotNone(reg_b.getById('dup'))
        self.assertNotIn('dup', reg_b.disabled_names())
        # 无项目视图（用户层登记表）也不受项目层禁用影响。
        plain = skill_registry.Registry(
            self.registry.root, user_root=self.registry.user_root).scan(force=True)
        self.assertNotIn('dup', plain.disabled_names())

    def test_validate_selected_skills_reports_disabled(self):
        source = _write(self.root / 'src' / 'alpha.skill.md', 'alpha')
        import_file(self.program, self.registry, source)
        project = _project(self.root, self.program, 'projV', skills=['alpha'])
        skill_lifecycle_service.set_skill_disabled(self.program, self.registry, 'alpha', True)
        # validate_selected_skills 内部走 default_registry(project=...)；注入本测试
        # 注册表，验证「已禁用」与「未加载」两条分支的文案区分（行为断言不变）。
        with mock.patch.object(skill_registry, 'default_registry',
                               return_value=self.registry), \
                self.assertRaises(ValueError) as ctx:
            workflow_settings.validate_selected_skills(project, 'script')
        self.assertIn('已禁用', str(ctx.exception))
        self.assertIn('alpha', str(ctx.exception))
        self.assertIn('SKILL 管理', str(ctx.exception))


class FindEntryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.program, self.registry = make_program(self.root)

    def test_enabled_entry_shape(self):
        source = _write(self.root / 'src' / 'alpha.skill.md', 'alpha')
        import_file(self.program, self.registry, source)
        entry = skill_lifecycle_service.find_skill_entry(self.program, self.registry, 'alpha')
        self.assertEqual('manifest', entry['kind'])
        self.assertEqual('user', entry['layer'])
        self.assertFalse(entry['disabled'])
        self.assertTrue(entry['path'].is_file())

    def test_disabled_entry_located_via_registry_path(self):
        source = _write(self.root / 'src' / 'alpha.skill.md', 'alpha')
        import_file(self.program, self.registry, source)
        skill_lifecycle_service.set_skill_disabled(self.program, self.registry, 'alpha', True)
        self.registry.scan(force=True)
        entry = skill_lifecycle_service.find_skill_entry(self.program, self.registry, 'alpha')
        self.assertIsNotNone(entry)
        self.assertTrue(entry['disabled'])
        self.assertEqual('user', entry['layer'])
        self.assertTrue(entry['path'].is_file())

    def test_unknown_name_returns_none(self):
        self.assertIsNone(
            skill_lifecycle_service.find_skill_entry(self.program, self.registry, 'ghost'))


class RenameTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.program, self.registry = make_program(self.root)

    def test_manifest_rename_migrates_refs_ledger_and_registry(self):
        source = _write(self.root / 'src' / 'alpha.skill.md', 'alpha')
        import_file(self.program, self.registry, source)
        project = _project(self.root, self.program, 'proj', skills=['alpha'])
        self.registry.scan(force=True)
        # agent 同步标记按注册表重算：改名前先同步一次，造出旧名 agent 目录供
        # 孤儿回收断言。targets 限定 codex——其余目标缺省会写真实用户目录，测试禁写。
        agent_home = Path(self.root) / 'agent-skills'
        agent_skill_sync.sync_all_agent_skills(
            program=self.program, homes={'codex': agent_home}, targets=('codex',))
        self.assertTrue((agent_home / 'alpha').is_dir())
        plan = skill_lifecycle_service.rename_plan(
            self.program, self.registry, 'alpha', 'alpha-two', project=project)
        self.assertEqual(1, plan['affected_count'])
        self.assertIn(str(project), plan['affected_projects'])
        result = skill_lifecycle_service.apply_rename(self.program, plan)
        self.assertEqual('alpha-two', result['new'])
        # 文件：新清单在、旧文件进回收站、frontmatter name 同步。
        new_file = self.program / 'data' / 'skills' / STAGE_DIR / 'alpha-two.skill.md'
        old_file = self.program / 'data' / 'skills' / STAGE_DIR / 'alpha.skill.md'
        self.assertTrue(new_file.is_file())
        self.assertFalse(old_file.exists())
        self.assertIn('name: alpha-two', new_file.read_text(encoding='utf-8'))
        # 注册表：新名可见、旧名消失。
        self.registry.scan(force=True)
        self.assertIsNotNone(self.registry.getById('alpha-two'))
        self.assertIsNone(self.registry.getById('alpha'))
        # 项目引用迁移。
        config = json.loads((project / 'skill_config.json').read_text(encoding='utf-8'))
        self.assertEqual(['alpha-two'], config['script']['skills'])
        # 台账：键与 name/sha256 同步到新目标。
        rows = ledger_rows(self.program)
        self.assertEqual(1, len(rows))
        row = next(iter(rows.values()))
        self.assertEqual('alpha-two', row['name'])
        self.assertIn('alpha-two.skill.md', next(iter(rows)))
        self.assertEqual(skill_import_service._tree_digest(new_file), row['sha256'])
        # agent 同步标记按注册表重算：二次同步写新名、旧名孤儿目录进回收站。
        report = agent_skill_sync.sync_all_agent_skills(
            program=self.program, homes={'codex': agent_home}, targets=('codex',))
        self.assertTrue((agent_home / 'alpha-two').is_dir())
        self.assertFalse((agent_home / 'alpha').exists())
        self.assertIn('alpha', report['codex']['recycled'])

    def test_package_rename_moves_dir_and_rewrites_name(self):
        folder = write_package(self.root / 'pkg-src', dirname='外部包', stage='script')
        entry = folder / 'SKILL.md'
        plan_import = skill_import_service.plan_import(
            entry, self.registry.user_stage_directory_for('script'), 'script', self.registry)
        skill_import_service.perform_import(plan_import, self.program)
        self.registry.scan(force=True)
        self.assertIsNotNone(self.registry.getById('repo-pack'))
        plan = skill_lifecycle_service.rename_plan(
            self.program, self.registry, 'repo-pack', 'repo-pack-two')
        self.assertEqual('package', plan['kind'])
        skill_lifecycle_service.apply_rename(self.program, plan)
        stage_dir = self.program / 'data' / 'skills' / STAGE_DIR
        self.assertTrue((stage_dir / 'repo-pack-two' / 'SKILL.md').is_file())
        self.assertFalse((stage_dir / '外部包').exists())
        text = (stage_dir / 'repo-pack-two' / 'SKILL.md').read_text(encoding='utf-8')
        self.assertIn('name: repo-pack-two', text)
        self.registry.scan(force=True)
        self.assertIsNotNone(self.registry.getById('repo-pack-two'))
        self.assertIsNone(self.registry.getById('repo-pack'))

    def test_rename_disabled_skill_updates_disabled_entry(self):
        source = _write(self.root / 'src' / 'alpha.skill.md', 'alpha')
        import_file(self.program, self.registry, source)
        skill_lifecycle_service.set_skill_disabled(self.program, self.registry, 'alpha', True)
        self.registry.scan(force=True)
        plan = skill_lifecycle_service.rename_plan(self.program, self.registry, 'alpha', 'alpha-two')
        self.assertTrue(plan['disabled'])
        skill_lifecycle_service.apply_rename(self.program, plan)
        self.registry.scan(force=True)
        self.assertIn('alpha-two', self.registry.disabled_names())
        self.assertNotIn('alpha', self.registry.disabled_names())
        entry = skill_lifecycle_service.find_skill_entry(
            self.program, self.registry, 'alpha-two')
        self.assertTrue(entry['disabled'])
        self.assertTrue(str(entry['path']).endswith('alpha-two.skill.md'))

    def test_rename_plan_rejects_bad_input(self):
        source = _write(self.root / 'src' / 'alpha.skill.md', 'alpha')
        import_file(self.program, self.registry, source)
        self.registry.scan(force=True)
        with self.assertRaises(skill_import_service.ImportBlocked):
            skill_lifecycle_service.rename_plan(self.program, self.registry, 'alpha', 'bad name!')
        with self.assertRaises(skill_import_service.ImportBlocked):
            skill_lifecycle_service.rename_plan(self.program, self.registry, 'alpha', 'alpha')
        with self.assertRaises(skill_import_service.ImportBlocked):
            skill_lifecycle_service.rename_plan(self.program, self.registry, 'ghost', 'g-two')
        # beta 只写了源文件、未导入——不在注册表。
        write_manifest(self.root / 'src' / 'b.skill.md', name='beta', stage='script')
        with self.assertRaises(skill_import_service.ImportBlocked):
            skill_lifecycle_service.rename_plan(self.program, self.registry, 'beta', 'beta-two')


class VersionCompareTests(unittest.TestCase):
    def test_version_key_orders_numeric_segments(self):
        self.assertGreater(skill_import_service._version_key('1.10'),
                           skill_import_service._version_key('1.9'))
        self.assertEqual(0, skill_import_service._version_compare('1.0', '1.0'))
        self.assertIsNone(skill_import_service._version_compare('', '1.0'))
        self.assertEqual(-1, skill_import_service._version_compare('0.9', '1.0'))
        self.assertEqual(1, skill_import_service._version_compare('2.0', '1.9'))

    def test_check_updates_prefers_version_over_digest(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        program, registry = make_program(root)
        source = root / 'src' / 'v.skill.md'
        source.parent.mkdir(parents=True)
        source.write_text('---\nname: ver-skill\ndisplayName: V\ndescription: d\n'
                          'stage: script\nversion: 1.0\n---\n正文一\n', encoding='utf-8')
        import_file(program, registry, source)
        key = next(iter(ledger_rows(program)))
        statuses = skill_import_service.check_updates(program)
        self.assertEqual('unchanged', statuses[key])
        # 版本不变、正文改动 → 摘要兜底判 source-newer。
        source.write_text(source.read_text(encoding='utf-8').replace('正文一', '正文二'),
                          encoding='utf-8')
        self.assertEqual('source-newer',
                         skill_import_service.check_updates(program)[key])
        # 版本降回 0.9 且正文再改 → 版本权威判 unchanged（不提示降级）。
        source.write_text(source.read_text(encoding='utf-8')
                          .replace('version: 1.0', 'version: 0.9')
                          .replace('正文二', '正文三'), encoding='utf-8')
        self.assertEqual('unchanged',
                         skill_import_service.check_updates(program)[key])
        # 版本升到 2.0 → source-newer。
        source.write_text(source.read_text(encoding='utf-8')
                          .replace('version: 0.9', 'version: 2.0'), encoding='utf-8')
        self.assertEqual('source-newer',
                         skill_import_service.check_updates(program)[key])


class UninstallDisabledTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.program, self.registry = make_program(self.root)

    def test_disabled_skill_deletes_via_entry_point(self):
        source = _write(self.root / 'src' / 'alpha.skill.md', 'alpha')
        import_file(self.program, self.registry, source)
        skill_lifecycle_service.set_skill_disabled(self.program, self.registry, 'alpha', True)
        self.registry.scan(force=True)
        result = skill_lifecycle_service.uninstall_skill_entry(
            self.program, self.registry, 'alpha')
        self.assertTrue(result.get('disabled'))
        target = self.program / 'data' / 'skills' / STAGE_DIR / 'alpha.skill.md'
        self.assertFalse(target.exists())
        self.assertEqual({}, ledger_rows(self.program))
        self.registry.scan(force=True)
        self.assertEqual([], self.registry.disabled_entries())


class DeleteOccupancyTests(unittest.TestCase):
    """R3170：制作锁项目里被引用的技能不能经生命周期入口删除。"""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.program, self.registry = make_program(self.root)

    def configure_project(self, locks=None, selected=None):
        from stage_layout import skill_config_path
        from agent.core import save
        project = self.root / 'project'
        project.mkdir(exist_ok=True)
        save(skill_config_path(project), {
            'production_locks': locks or {},
            'script': {'skills': selected or []}})
        return project

    def test_locked_reference_returns_reason_without_mutating_config(self):
        from stage_layout import skill_config_path
        project = self.configure_project({'aspect_ratio': '9:16'}, ['alpha'])
        before = skill_config_path(project).read_bytes()
        reason = skill_lifecycle_service.skill_delete_block_reason(project, 'alpha')
        self.assertIn('制作锁', reason)
        self.assertIn('引用', reason)
        self.assertEqual(before, skill_config_path(project).read_bytes())
        self.assertEqual('', skill_lifecycle_service.skill_delete_block_reason(project, 'alp'))

    def test_unlocked_or_unreferenced_skill_is_not_blocked(self):
        project = self.configure_project(selected=['alpha'])
        self.assertEqual('', skill_lifecycle_service.skill_delete_block_reason(project, 'alpha'))
        project = self.configure_project({'aspect_ratio': '9:16'}, ['other'])
        self.assertEqual('', skill_lifecycle_service.skill_delete_block_reason(project, 'alpha'))
        self.assertEqual('', skill_lifecycle_service.skill_delete_block_reason(None, 'alpha'))

    def test_locked_stage_skill_reference_is_also_blocked(self):
        from agent.core import save
        from stage_layout import skill_config_path
        project = self.configure_project({'aspect_ratio': '9:16'})
        save(skill_config_path(project), {
            'production_locks': {'aspect_ratio': '9:16'},
            'script': {'stage_skills': ['alpha']}})
        self.assertIn('制作锁', skill_lifecycle_service.skill_delete_block_reason(project, 'alpha'))

    def test_locked_enabled_and_disabled_entries_are_preserved(self):
        source = _write(self.root / 'src' / 'alpha.skill.md', 'alpha')
        import_file(self.program, self.registry, source)
        project = self.configure_project({'aspect_ratio': '9:16'}, ['alpha'])
        target = self.program / 'data' / 'skills' / STAGE_DIR / 'alpha.skill.md'
        ledger_before = ledger_rows(self.program)
        for disabled in (False, True):
            with self.subTest(disabled=disabled):
                if disabled:
                    skill_lifecycle_service.set_skill_disabled(
                        self.program, self.registry, 'alpha', True)
                    self.registry.scan(force=True)
                with self.assertRaisesRegex(skill_import_service.ImportBlocked, '制作锁'):
                    skill_lifecycle_service.uninstall_skill_entry(
                        self.program, self.registry, 'alpha', project=project)
                self.assertTrue(target.is_file())
                self.assertEqual(ledger_before, ledger_rows(self.program))

    def test_registry_project_is_used_when_project_argument_is_omitted(self):
        project = self.configure_project({'aspect_ratio': '9:16'}, ['alpha'])
        self.registry.project_root = project
        with mock.patch.object(skill_import_service, 'uninstall_skill') as remove:
            with self.assertRaisesRegex(skill_import_service.ImportBlocked, '制作锁'):
                skill_lifecycle_service.uninstall_skill_entry(self.program, self.registry, 'alpha')
        remove.assert_not_called()


if __name__ == '__main__':
    unittest.main()
