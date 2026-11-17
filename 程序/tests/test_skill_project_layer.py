# -*- coding: utf-8 -*-
"""T5 项目级 SKILL 层：project > user > builtin 仲裁、缓存键隔离、引用回退、导入目标与台账口径。"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import skill_registry
import skill_import_service

STAGE_DIR = '01 剧本准备SKILL'


def _skill_md(name, stage='script', extra=''):
    return ('---\nname: %s\ndisplayName: %s\ndescription: 测试技能\nstage: %s\n'
            'capabilities: []\npreferredModels: []\nfallbackModels: []\ntools: []\n'
            'dependsOn: []\nconflictsWith: []\nparallelizable: false\npaid: false\n'
            'input: []\noutput: []\nconstraints: []\nfeedback: []\nexamples: []\n%s---\n\n正文 %s\n'
            % (name, name, stage, extra, name))


def _write(path, name, stage='script', extra=''):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_skill_md(name, stage, extra), encoding='utf-8')
    return path


class ProjectLayerCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.program = root / '程序'
        self.builtin = self.program / 'skills'
        self.user = self.program / 'data' / 'skills'
        self.project_a = root / '项目A'
        self.project_b = root / '项目B'
        for project in (self.project_a, self.project_b):
            (project / 'skills' / STAGE_DIR).mkdir(parents=True)
            (project / 'skill_config.json').write_text('{}', encoding='utf-8')
        (self.builtin / STAGE_DIR).mkdir(parents=True)
        (self.user / STAGE_DIR).mkdir(parents=True)

    def registry(self, project=None):
        return skill_registry.Registry(
            self.builtin, user_root=self.user,
            project_root=project).scan(force=True)

    # ── 可见性与隔离 ────────────────────────────────────────────────
    def test_project_skill_visible_only_in_its_project(self):
        _write(self.project_a / 'skills' / STAGE_DIR / 'aaa-project.skill.md', 'aaa-project')
        _write(self.project_b / 'skills' / STAGE_DIR / 'bbb-project.skill.md', 'bbb-project')
        a = self.registry(self.project_a)
        b = self.registry(self.project_b)
        glob = self.registry()
        self.assertIsNotNone(a.getById('aaa-project'))
        self.assertIsNone(b.getById('aaa-project'), '项目 A 的 SKILL 不得出现在项目 B')
        self.assertIsNone(glob.getById('aaa-project'), '项目层不得漏进全局两层视图')
        self.assertIsNotNone(b.getById('bbb-project'))
        self.assertEqual(a.getById('aaa-project').layer, 'project')
        self.assertEqual(b.getById('bbb-project').layer, 'project')

    def test_same_name_three_layer_arbitration(self):
        _write(self.builtin / STAGE_DIR / 'same-name.skill.md', 'same-name')
        _write(self.user / STAGE_DIR / 'same-name.skill.md', 'same-name')
        _write(self.project_a / 'skills' / STAGE_DIR / 'same-name.skill.md', 'same-name')
        reg = self.registry(self.project_a)
        item = reg.getById('same-name')
        self.assertEqual(item.layer, 'project', '项目版优先于用户版与内置版')
        self.assertTrue(item.path.is_relative_to(self.project_a / 'skills'))
        text = '\n'.join(reg.warnings())
        self.assertIn('项目版', text)
        self.assertIn('覆盖', text)
        # 没有项目层的注册表：用户版仍盖内置版（T1 前语义不变）
        glob = self.registry()
        self.assertEqual(glob.getById('same-name').layer, 'user')
        # 项目 B 看不到项目 A 的同名遮蔽
        b = self.registry(self.project_b)
        self.assertEqual(b.getById('same-name').layer, 'user')

    def test_project_shadows_user_warns(self):
        _write(self.user / STAGE_DIR / 'only-user.skill.md', 'only-user')
        _write(self.project_a / 'skills' / STAGE_DIR / 'only-user.skill.md', 'only-user')
        reg = self.registry(self.project_a)
        self.assertEqual(reg.getById('only-user').layer, 'project')
        self.assertTrue(any('项目版' in w and '用户版' in w for w in reg.warnings()))

    def test_same_layer_duplicate_still_hard_problem(self):
        _write(self.project_a / 'skills' / STAGE_DIR / 'dup-a.skill.md', 'dup-name')
        _write(self.project_a / 'skills' / STAGE_DIR / 'dup-b.skill.md', 'dup-name')
        reg = self.registry(self.project_a)
        self.assertTrue(any('重名' in p for p in reg.problems()))

    # ── default_registry 缓存键 ─────────────────────────────────────
    def test_default_registry_cache_key_includes_project(self):
        _write(self.project_a / 'skills' / STAGE_DIR / 'aaa-project.skill.md', 'aaa-project')
        with mock.patch.object(skill_registry, 'default_root', lambda p=None: self.builtin), \
             mock.patch.object(skill_registry, 'default_user_root', lambda p=None: self.user):
            skill_registry._DEFAULTS.clear()
            try:
                ga = skill_registry.default_registry(project=self.project_a)
                gb = skill_registry.default_registry(project=self.project_b)
                gg = skill_registry.default_registry()
                self.assertIsNot(ga, gb)
                self.assertIsNot(ga, gg)
                self.assertIs(ga, skill_registry.default_registry(project=self.project_a))
                self.assertIsNotNone(ga.getById('aaa-project'))
                self.assertIsNone(gb.getById('aaa-project'))
                self.assertIsNone(gg.getById('aaa-project'))
            finally:
                skill_registry._DEFAULTS.clear()

    # ── 目录推导与写入目标 ─────────────────────────────────────────
    def test_project_skill_root_for_path_derivation(self):
        inside = self.project_a / 'skills' / STAGE_DIR / 'x.skill.md'
        outside = self.builtin / STAGE_DIR / 'y.skill.md'
        no_config = Path(self.tmp.name) / '裸skills' / 'z.skill.md'
        (no_config.parent).mkdir(parents=True)
        self.assertEqual(skill_registry.project_skill_root_for(inside),
                         (self.project_a / 'skills').resolve())
        self.assertIsNone(skill_registry.project_skill_root_for(outside))
        self.assertIsNone(skill_registry.project_skill_root_for(no_config))

    def test_stage_directory_for_scopes(self):
        reg = self.registry(self.project_a)
        self.assertEqual(reg.project_stage_directory_for('script'),
                         self.project_a / 'skills' / STAGE_DIR)
        self.assertEqual(reg.stage_directory_for('script', 'project'),
                         self.project_a / 'skills' / STAGE_DIR)
        self.assertEqual(reg.stage_directory_for('script', 'user'),
                         self.user / STAGE_DIR)
        self.assertIsNone(self.registry().project_stage_directory_for('script'))
        with self.assertRaises(ValueError):
            reg.stage_directory_for('script', 'bogus')

    def test_project_stage_dir_falls_back_to_builtin_name(self):
        # 项目层没有该阶段目录时按内置目录名给出（与 user 层同口径）
        (self.builtin / '12后期剪辑SKILL').mkdir(parents=True, exist_ok=True)
        project = Path(self.tmp.name) / '项目C'
        (project / 'skills').mkdir(parents=True)
        (project / 'skill_config.json').write_text('{}', encoding='utf-8')
        reg = self.registry(project)
        target = reg.project_stage_directory_for('edit')
        self.assertIsNotNone(target)
        self.assertTrue(str(target).endswith('12后期剪辑SKILL'))

    # ── 引用解析回退 ───────────────────────────────────────────────
    def test_resolve_reference_project_falls_back_user_then_builtin(self):
        shared_user = self.user / '00全流程SKILL' / 'shared.md'
        shared_builtin = self.builtin / '00全流程SKILL' / 'shared.md'
        shared_user.parent.mkdir(parents=True, exist_ok=True)
        shared_builtin.parent.mkdir(parents=True, exist_ok=True)
        source = self.project_a / 'skills' / STAGE_DIR / 'aaa.skill.md'
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(_skill_md('aaa', extra='see [x](../00全流程SKILL/shared.md)\n'),
                          encoding='utf-8')
        # 只内置层有 → 落到内置层
        shared_builtin.write_text('builtin', encoding='utf-8')
        hit = skill_registry.resolve_reference(source, Path('../00全流程SKILL/shared.md'),
                                               program=self.program)
        self.assertEqual(hit, shared_builtin.resolve())
        # 用户层也有 → 项目引用优先用户层共享资料
        shared_user.write_text('user', encoding='utf-8')
        hit = skill_registry.resolve_reference(source, Path('../00全流程SKILL/shared.md'),
                                               program=self.program)
        self.assertEqual(hit, shared_user.resolve())

    def test_skill_roots_includes_project_when_given(self):
        roots = skill_registry.skill_roots(program=self.program, project=self.project_a)
        self.assertIn((self.project_a / 'skills').resolve(), roots)
        self.assertEqual(len(skill_registry.skill_roots(program=self.program)), 2)

    # ── 根目录遗留 manifest 迁移到项目层 ────────────────────────────
    def test_root_manifest_migrates_into_project_layer(self):
        stray = self.project_a / 'skills' / 'loose.skill.md'
        _write(stray, 'loose-skill')
        reg = self.registry(self.project_a)
        self.assertTrue(reg.getById('loose-skill') is not None)
        self.assertFalse(stray.exists(), '根目录遗留文件应迁入阶段目录')
        migrated = self.project_a / 'skills' / STAGE_DIR / 'loose.skill.md'
        self.assertTrue(migrated.is_file())

    # ── 导入目标与台账 scope ────────────────────────────────────────
    def test_plan_import_project_target_and_ledger_scope(self):
        source = Path(self.tmp.name) / 'src' / 'new-skill.skill.md'
        _write(source, 'new-skill')
        reg = self.registry(self.project_a)
        plan = skill_import_service.plan_import(
            source, reg.project_stage_directory_for('script'), 'script', reg)
        self.assertTrue(str(plan['target']).startswith(str(self.project_a / 'skills')))
        report = skill_import_service.perform_import(plan, self.program)
        self.assertTrue(Path(report['target']).is_file())
        items = skill_import_service.ledger_items(self.program)
        row = next(iter(items.values()))
        self.assertEqual(row.get('scope'), 'project')
        self.assertEqual(Path(row.get('project', '')).resolve(), self.project_a.resolve())
        # 全局视图注册表看不到项目层安装结果
        self.assertIsNone(self.registry().getById('new-skill'))
        self.assertIsNotNone(self.registry(self.project_a).getById('new-skill'))

    def test_project_import_shadowing_user_warns_not_blocks(self):
        _write(self.user / STAGE_DIR / 'shadowed.skill.md', 'shadowed')
        source = Path(self.tmp.name) / 'src' / 'shadowed.skill.md'
        _write(source, 'shadowed')
        reg = self.registry(self.project_a)
        plan = skill_import_service.plan_import(
            source, reg.project_stage_directory_for('script'), 'script', reg)
        self.assertTrue(any('覆盖' in p for p in plan['problems']))
        self.assertFalse(any('重名' in p and 'ImportBlocked' not in p for p in plan['problems']))

    # ── 面板「导入到」选择 ─────────────────────────────────────────
    def test_panel_import_layer_choice(self):
        import skill_panel_import
        reg = self.registry(self.project_a)

        class _Var:
            def __init__(self, value):
                self._value = value

            def get(self):
                return self._value

        class _Panel:
            pass

        panel = _Panel()
        panel.registry = reg
        panel.stage = 'script'
        panel.desktop = type('D', (), {'root': str(self.project_a)})()
        for scope, expected in (('项目', 'project'), ('全局', 'user')):
            panel.import_scope_var = _Var(scope)
            self.assertEqual(
                skill_panel_import._import_layer(panel), expected)
        # 无项目时只能全局
        panel.desktop = type('D', (), {'root': None})()
        panel.import_scope_var = _Var('项目')
        self.assertEqual(skill_panel_import._import_layer(panel), 'user')
        # 目标目录跟随选择
        panel.desktop = type('D', (), {'root': str(self.project_a)})()
        panel.import_scope_var = _Var('项目')
        self.assertEqual(
            skill_panel_import._import_target_dir(panel, 'script'),
            self.project_a / 'skills' / STAGE_DIR)
        panel.import_scope_var = _Var('全局')
        self.assertEqual(
            skill_panel_import._import_target_dir(panel, 'script'),
            self.user / STAGE_DIR)

    # ── check_updates 项目过滤 ──────────────────────────────────────
    def test_check_updates_scoped_by_project(self):
        # 项目 A 装一份，项目 B 检查时不得看到 A 的行
        source = Path(self.tmp.name) / 'src' / 'scoped.skill.md'
        _write(source, 'scoped')
        reg_a = self.registry(self.project_a)
        plan = skill_import_service.plan_import(
            source, reg_a.project_stage_directory_for('script'), 'script', reg_a)
        skill_import_service.perform_import(plan, self.program)
        all_status = skill_import_service.check_updates(self.program)
        self.assertTrue(all_status, '全量检查应含项目行')
        only_b = skill_import_service.check_updates(self.program, project=self.project_b)
        self.assertFalse(any('scoped' in key for key in only_b),
                         '项目 B 的检查不得包含项目 A 的台账行')
        only_a = skill_import_service.check_updates(self.program, project=self.project_a)
        self.assertTrue(any('scoped' in key for key in only_a))

    def test_forget_ledger_targets_removes_project_row(self):
        source = Path(self.tmp.name) / 'src' / 'forget-me.skill.md'
        _write(source, 'forget-me')
        reg = self.registry(self.project_a)
        plan = skill_import_service.plan_import(
            source, reg.project_stage_directory_for('script'), 'script', reg)
        skill_import_service.perform_import(plan, self.program)
        target = plan['target']
        removed = skill_import_service.forget_ledger_targets(self.program, [target])
        self.assertEqual(removed, 1)
        self.assertFalse(skill_import_service.ledger_items(self.program))


if __name__ == '__main__':
    unittest.main()
