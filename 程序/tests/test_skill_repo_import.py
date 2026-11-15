# -*- coding: utf-8 -*-
"""R2881：SKILL 仓库导入——地址解析、仓库扫描、克隆管线复用、回收站与台账。"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import skill_import_service
import skill_registry


def make_program(root):
    """临时程序目录：内置层只建阶段目录（用户层由导入方按需新建）。"""
    program = Path(root) / 'program'
    builtin = program / 'skills'
    user = program / 'data' / 'skills'
    for name in ('01剧本准备SKILL', '03初步分镜SKILL', '08首帧管理SKILL'):
        (builtin / name).mkdir(parents=True)
    registry = skill_registry.Registry(builtin, user_root=user)
    return program, registry


def write_manifest(path, name='repo-skill', stage='script', body='# 仓库清单\n正文'):
    path.parent.mkdir(parents=True, exist_ok=True)
    stage_line = 'stage: %s\n' % stage if stage else ''
    path.write_text('---\nname: %s\n%s---\n%s\n' % (name, stage_line, body), encoding='utf-8')
    return path


def write_package(path, dirname='外部包', stage='script', body='# 外部包\n见 [规则](references/rules.md)'):
    folder = Path(path) / dirname
    (folder / 'references').mkdir(parents=True)
    (folder / 'references' / 'rules.md').write_text('规则正文', encoding='utf-8')
    stage_line = 'stage: %s\n' % stage if stage else ''
    (folder / 'SKILL.md').write_text('---\nname: repo-pack\n%s---\n%s\n' % (stage_line, body),
                                     encoding='utf-8')
    return folder


class ParseRepoRefTests(unittest.TestCase):
    def test_shorthand_expands_to_github(self):
        spec = skill_import_service.parse_repo_ref('owner/repo')
        self.assertEqual(spec['kind'], 'url')
        self.assertEqual(spec['url'], 'https://github.com/owner/repo')
        self.assertEqual(spec['ref'], '')
        self.assertEqual(spec['label'], 'github.com/owner/repo')

    def test_shorthand_with_branch(self):
        spec = skill_import_service.parse_repo_ref('owner/repo@main')
        self.assertEqual(spec['url'], 'https://github.com/owner/repo')
        self.assertEqual(spec['ref'], 'main')
        self.assertEqual(spec['label'], 'github.com/owner/repo@main')

    def test_full_url_and_ref_with_slash(self):
        spec = skill_import_service.parse_repo_ref('https://github.com/a/b@feature/x')
        self.assertEqual(spec['url'], 'https://github.com/a/b')
        self.assertEqual(spec['ref'], 'feature/x')

    def test_scp_like_and_userinfo(self):
        spec = skill_import_service.parse_repo_ref('git@github.com:a/b.git')
        self.assertEqual(spec['kind'], 'url')
        self.assertEqual(spec['url'], 'git@github.com:a/b.git')
        spec = skill_import_service.parse_repo_ref('https://user:pass@github.com/a/b')
        self.assertEqual(spec['ref'], '', 'userinfo 里的 @ 不能被当成 @ref')
        self.assertNotIn('pass', spec['label'], '台账标签不得回显凭据')

    def test_local_dir_and_bad_input(self):
        with tempfile.TemporaryDirectory() as td:
            spec = skill_import_service.parse_repo_ref(td)
            self.assertEqual(spec['kind'], 'local')
            self.assertEqual(spec['path'], Path(td))
        with self.assertRaises(skill_import_service.ImportBlocked):
            skill_import_service.parse_repo_ref('')
        with self.assertRaises(skill_import_service.ImportBlocked):
            skill_import_service.parse_repo_ref('不是地址')


class RepoScanTests(unittest.TestCase):
    def test_candidates_find_packages_and_manifests(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_package(root / 'pkgs' / 'one')
            write_manifest(root / 'skills' / 'two' / 'two.skill.md', stage='')
            (root / '.hidden' / 'SKILL.md').parent.mkdir(parents=True)
            (root / '.hidden' / 'SKILL.md').write_text('# x', encoding='utf-8')
            candidates = skill_import_service._repo_candidates(root)
            kinds = sorted(c['kind'] for c in candidates)
            self.assertEqual(kinds, ['manifest', 'package'])
            self.assertFalse(any('.hidden' in str(c['source']) for c in candidates))

    def test_package_dir_is_not_scanned_inside(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            folder = write_package(root)
            write_manifest(folder / 'inner' / 'inner.skill.md')
            candidates = skill_import_service._repo_candidates(root)
            self.assertEqual(len(candidates), 1, '包内清单不单独成候选')
            self.assertEqual(candidates[0]['kind'], 'package')


class RepoImportTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.program, self.registry = make_program(self.root)
        self.repo = self.root / 'repo'
        self.repo.mkdir()

    def test_local_repo_imports_package_and_manifest_to_declared_stages(self):
        write_package(self.repo, dirname='pack')
        write_manifest(self.repo / '03分镜' / 'shot.skill.md', name='shot-skill', stage='storyboard')
        report = skill_import_service.import_from_repo(str(self.repo), self.program,
                                                      self.registry, confirm=lambda m: True)
        self.assertEqual(len(report['installed']), 2)
        user = self.program / 'data' / 'skills'
        self.assertTrue((user / '01剧本准备SKILL' / 'pack' / 'SKILL.md').is_file())
        self.assertTrue((user / '03初步分镜SKILL' / 'shot.skill.md').is_file())

    def test_stage_falls_back_to_hint_and_path_directory(self):
        # NN 目录优先于面板提示；都没有时用 stage_hint。
        write_manifest(self.repo / '03分镜' / 'bydir.skill.md', name='bydir', stage='')
        write_manifest(self.repo / 'm1.skill.md', name='hint-skill', stage='')
        report = skill_import_service.import_from_repo(str(self.repo), self.program,
                                                      self.registry, stage_hint='script',
                                                      confirm=lambda m: True)
        self.assertEqual(len(report['installed']), 2)
        user = self.program / 'data' / 'skills'
        self.assertTrue((user / '03初步分镜SKILL' / 'bydir.skill.md').is_file())
        self.assertTrue((user / '01剧本准备SKILL' / 'm1.skill.md').is_file())
        self.registry.scan(force=True)
        self.assertEqual(self.registry.getById('bydir').stage, 'storyboard')
        self.assertEqual(self.registry.getById('hint-skill').stage, 'script')

    def test_confirm_false_imports_nothing(self):
        write_manifest(self.repo / 'x.skill.md', name='x1', stage='script')
        with self.assertRaises(skill_import_service.ImportBlocked):
            skill_import_service.import_from_repo(str(self.repo), self.program,
                                                  self.registry, confirm=lambda m: False)
        self.assertFalse((self.program / 'data' / 'skills').exists()
                         and any((self.program / 'data' / 'skills').rglob('*.skill.md')))

    def test_empty_repo_and_missing_dir_are_blocked(self):
        with self.assertRaises(skill_import_service.ImportBlocked):
            skill_import_service.import_from_repo(str(self.repo), self.program,
                                                  self.registry, confirm=lambda m: True)
        with self.assertRaises(skill_import_service.ImportBlocked):
            skill_import_service.import_from_repo(str(self.root / 'nope'), self.program,
                                                  self.registry, confirm=lambda m: True)

    def test_clone_path_uses_staging_and_records_repo_label(self):
        def fake_clone(url, ref, dest):
            self.assertEqual(url, 'https://github.com/o/r')
            self.assertEqual(ref, 'main')
            Path(dest).mkdir(parents=True)
            write_package(Path(dest), dirname='cloned')
        with mock.patch.object(skill_import_service, '_git_clone', side_effect=fake_clone):
            report = skill_import_service.import_from_repo('o/r@main', self.program,
                                                          self.registry, stage_hint='script',
                                                          confirm=lambda m: True)
        self.assertEqual(len(report['installed']), 1)
        self.assertEqual(report['label'], 'github.com/o/r@main')
        ledger = skill_import_service.read_json(skill_import_service.ledger_path(self.program))
        row = next(iter(ledger['items'].values()))
        self.assertEqual(row['source'], 'github.com/o/r@main', '台账记仓库来源而非临时克隆路径')
        leftovers = [p for p in (self.program / 'data' / 'skills').iterdir()
                     if p.name.startswith(skill_import_service.REPO_CLONE_PREFIX)]
        self.assertEqual(leftovers, [], '克隆暂存目录必须收走')

    def test_clone_failure_cleans_staging(self):
        with mock.patch.object(skill_import_service, '_git_clone',
                               side_effect=skill_import_service.ImportBlocked('clone boom')):
            with self.assertRaises(skill_import_service.ImportBlocked):
                skill_import_service.import_from_repo('o/r', self.program,
                                                      self.registry, confirm=lambda m: True)
        leftovers = [p for p in (self.program / 'data' / 'skills').iterdir()
                     if p.name.startswith(skill_import_service.REPO_CLONE_PREFIX)]
        self.assertEqual(leftovers, [])

    def test_update_overwrites_via_recycle_and_uninstall_removes(self):
        write_manifest(self.repo / 'v.skill.md', name='ver', stage='script', body='# V1\n')
        skill_import_service.import_from_repo(str(self.repo), self.program,
                                              self.registry, confirm=lambda m: True)
        target = self.program / 'data' / 'skills' / '01剧本准备SKILL' / 'v.skill.md'
        self.assertIn('# V1', target.read_text(encoding='utf-8'))
        write_manifest(self.repo / 'v.skill.md', name='ver', stage='script', body='# V2\n')
        report = skill_import_service.update_from_repo(str(self.repo), self.program,
                                                      self.registry, confirm=lambda m: True)
        self.assertEqual(len(report['installed']), 1)
        self.assertIn('# V2', target.read_text(encoding='utf-8'))
        self.registry.scan(force=True)
        result = skill_import_service.uninstall_skill(self.program, self.registry, 'ver')
        self.assertFalse(target.exists())
        self.assertIn('ver', result['name'])
        with self.assertRaises(skill_import_service.ImportBlocked):
            skill_import_service.uninstall_skill(self.program, self.registry, '不存在的')

    def test_validate_skill_uses_freeze_gate(self):
        good = write_manifest(self.root / 'good.skill.md', name='gv', stage='script')
        ok, _message = skill_import_service.validate_skill(good)
        self.assertTrue(ok)
        bad = self.root / 'bad.skill.md'
        bad.write_text('---\nname: bad\n---\n# 空正文引用缺失\n见 [x](missing.md)\n', encoding='utf-8')
        ok, message = skill_import_service.validate_skill(bad)
        self.assertFalse(ok)
        self.assertTrue(message)


if __name__ == '__main__':
    unittest.main()
