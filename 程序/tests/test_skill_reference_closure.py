# -*- coding: utf-8 -*-
"""O35：SKILL 引用闭包与依赖类型必须明确——不递归、不静默忽略，必需引用缺失阻止发送。"""
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import skill_registry
import workflow_settings


def skill_text(name, stage, depends_on=(), tools=(), body=''):
    return ('---\n'
            'name: %s\n'
            'displayName: %s\n'
            'description: 测试技能\n'
            'stage: %s\n'
            'capabilities: [creative-writing]\n'
            'preferredModels: []\n'
            'fallbackModels: []\n'
            'tools: [%s]\n'
            'dependsOn: [%s]\n'
            'conflictsWith: []\n'
            'parallelizable: false\n'
            'paid: false\n'
            'input: []\n'
            'output: []\n'
            'constraints: []\n'
            'feedback: []\n'
            'examples: []\n'
            '---\n%s' % (name, name, stage, ', '.join(tools), ', '.join(depends_on), body))


def write_skill(root, folder, name, *, body='', stage='script', depends_on=(), tools=()):
    target = Path(root) / folder / (name + '.skill.md')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(skill_text(name, stage, depends_on, tools, body), encoding='utf-8')
    return target


def sample_body():
    return ('正文\n'
            '[一](one.md#sec)\n'
            '[重复](one.md)\n'
            '[图片](img.png)\n'
            '[站外](https://example.com/x.md)\n'
            '[锚](#top)\n'
            '[越界](../outside.md)\n')


def sample_root(td, reference_body='直接正文一\n[嵌套](nested.md)\n[回指](SKILL.md)\n', skill_body=None):
    root = Path(td) / 'skills'
    root.mkdir(parents=True, exist_ok=True)
    skill = root / 'SKILL.md'
    skill.write_text('---\nname: sample\n---\n'
                     + (sample_body() if skill_body is None else skill_body), encoding='utf-8')
    (root / 'one.md').write_text(reference_body, encoding='utf-8')
    (root / 'nested.md').write_text('不该被加载的嵌套正文', encoding='utf-8')
    (root / 'img.png').write_bytes(b'png')
    (Path(td) / 'outside.md').write_text('越界正文', encoding='utf-8')
    return root, skill


class ReferenceTargetTests(unittest.TestCase):
    def test_links_are_classified_and_normalised(self):
        rows = skill_registry.reference_targets(
            '[一](one.md#sec) [二](two.txt "标题") [图](img.png) '
            '[站外](https://example.com/a.md) [锚](#top) [目录](docs/)')
        self.assertEqual([row['kind'] for row in rows],
                         ['markdown', 'markdown', 'other', 'remote', 'anchor', 'other'])
        self.assertEqual(rows[0]['path'], Path('one.md'))
        self.assertEqual(rows[0]['fragment'], 'sec')
        self.assertEqual(rows[1]['path'], Path('two.txt'))
        self.assertIsNone(rows[3]['path'])
        self.assertIsNone(rows[4]['path'])
        self.assertEqual(skill_registry.reference_targets(''), [])

    def test_tools_and_scripts_are_not_document_references(self):
        rows = skill_registry.reference_targets('[脚本](run.py) [说明](readme.md)')
        self.assertEqual([row['kind'] for row in rows], ['other', 'markdown'])


class DependencyKindTests(unittest.TestCase):
    def test_registered_dependencies_are_separated_from_external_steps(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'skills'
            write_skill(root, '01 剧本', 'upstream')
            write_skill(root, '01 剧本', 'downstream',
                        depends_on=['upstream', 'asset-search'], tools=['script.validate'])
            registry = skill_registry.Registry(root)
            registry.scan(force=True)
            skills = {skill.name: skill for skill in registry.getAll()}
            known = set(skills)
            report = skill_registry.dependency_report(skills['downstream'], known)
            self.assertEqual(report['skill'], ['upstream'])
            self.assertEqual(report['external'], ['asset-search'])
            self.assertEqual(report['tools'], ['script.validate'])
            self.assertEqual(skill_registry.external_references(skills['downstream'], known),
                             ['asset-search'])
            self.assertEqual(skill_registry.classify_dependencies(skills['upstream'], known),
                             {'skill': [], 'external': []})
            self.assertIn('依赖 asset-search', ' '.join(registry.warnings()))


class ClosureTests(unittest.TestCase):
    def test_every_direct_reference_has_an_explicit_status(self):
        with tempfile.TemporaryDirectory() as td:
            root, skill = sample_root(td)
            with patch('skill_registry.default_root', return_value=root):
                text, closure = workflow_settings._inline_skill_report(skill)
            direct = {row['target']: row['status'] for row in closure if row['depth'] == 1}
            self.assertEqual(direct['one.md#sec'], 'inlined')
            self.assertEqual(direct['one.md'], 'duplicate')
            self.assertEqual(direct['img.png'], 'resource')
            self.assertEqual(direct['https://example.com/x.md'], 'remote')
            self.assertEqual(direct['#top'], 'anchor')
            self.assertEqual(direct['../outside.md'], 'outside')
            nested = {row['target']: row['status'] for row in closure if row['depth'] == 2}
            self.assertEqual(nested['nested.md'], 'nested')
            self.assertEqual(nested['SKILL.md'], 'cycle')
            self.assertIn('直接正文一', text)
            self.assertNotIn('不该被加载的嵌套正文', text)

    def test_missing_direct_reference_blocks_sending(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'skills'
            root.mkdir(parents=True, exist_ok=True)
            skill = root / 'SKILL.md'
            skill.write_text('---\nname: sample\n---\n正文 [缺](gone.md)\n', encoding='utf-8')
            with patch('skill_registry.default_root', return_value=root):
                with self.assertRaisesRegex(ValueError, '引用缺失，已阻止发送'):
                    workflow_settings._inline_skill_report(skill, strict=True)

    def test_outside_reference_blocks_only_in_strict_mode(self):
        with tempfile.TemporaryDirectory() as td:
            root, skill = sample_root(td)
            with patch('skill_registry.default_root', return_value=root):
                with self.assertRaisesRegex(ValueError, '超出允许目录，已阻止发送'):
                    workflow_settings._inline_skill_report(skill, strict=True)
                _text, closure = workflow_settings._inline_skill_report(skill)
            self.assertIn('outside', [row['status'] for row in closure])

    def test_nested_findings_are_reported_but_never_block(self):
        with tempfile.TemporaryDirectory() as td:
            root, skill = sample_root(td, '直接正文一\n[缺](nested-missing.md)\n',
                                      skill_body='正文\n[一](one.md)\n')
            with patch('skill_registry.default_root', return_value=root):
                text, closure = workflow_settings._inline_skill_report(skill, strict=True)
            self.assertIn('直接正文一', text)
            self.assertEqual([row['status'] for row in closure if row['depth'] == 2], ['missing'])


class ManifestTests(unittest.TestCase):
    def freeze(self, root, skill):
        config = {'engine': 'qwen', 'model': 'first', 'stage': 'writing',
                  'skills': [str(skill)], 'stage_skills': [str(skill)]}
        with patch('skill_registry.default_root', return_value=root):
            return workflow_settings.freeze_skills(config)

    def test_freeze_records_the_closure_with_skill_attribution(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'skills'
            root.mkdir(parents=True, exist_ok=True)
            skill = root / 'SKILL.md'
            skill.write_text('---\nname: sample\n---\n正文 [一](one.md)\n', encoding='utf-8')
            (root / 'one.md').write_text('直接正文一', encoding='utf-8')
            manifest = self.freeze(root, skill)['skill_injection']
            self.assertEqual(len(manifest['loaded']), 1)
            self.assertEqual(len(manifest['selected']), 1)
            closures = manifest['references']
            self.assertEqual([row['status'] for row in closures], ['inlined'])
            self.assertEqual(closures[0]['skill'], str(skill.resolve()))
            self.assertEqual(closures[0]['target'], 'one.md')
            self.assertEqual(closures[0]['depth'], 1)

    def test_freeze_blocks_when_a_direct_reference_is_missing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'skills'
            root.mkdir(parents=True, exist_ok=True)
            skill = root / 'SKILL.md'
            skill.write_text('---\nname: sample\n---\n正文 [缺](gone.md)\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, '已阻止发送'):
                self.freeze(root, skill)


class RemovablePackageTests(unittest.TestCase):
    def test_removing_a_non_dependency_package_leaves_script_skills_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'skills'
            write_skill(root, '01 剧本', 'upstream')
            package = root / '01 剧本' / 'jingju-skills'
            package.mkdir(parents=True)
            (package / 'SKILL.md').write_text('---\nname: jingju-skills\ndescription: 鲸剧\n---\n# 鲸剧\n',
                                              encoding='utf-8')
            registry = skill_registry.Registry(root)
            registry.scan(force=True)
            before = {skill.name: skill for skill in registry.getAll()}
            self.assertIn('jingju-skills', before)
            self.assertEqual(before['jingju-skills'].dependsOn, [])
            report_before = skill_registry.dependency_report(before['upstream'], set(before))
            self.assertEqual([item for item in registry.problems() if 'upstream' in item], [])
            shutil.rmtree(package)
            registry.scan(force=True)
            after = {skill.name: skill for skill in registry.getAll()}
            self.assertNotIn('jingju-skills', after)
            self.assertEqual(skill_registry.dependency_report(after['upstream'], set(after)),
                             report_before)
            self.assertEqual([item for item in registry.problems() if 'upstream' in item], [])

    def test_real_script_skills_do_not_depend_on_the_removable_jingju_package(self):
        registry = skill_registry.default_registry()
        registry.scan(force=True)
        skills = {skill.name: skill for skill in registry.getAll()}
        # 鲸剧包放在非阶段目录 00全流程SKILL 下，不是注册依赖源；删掉它不改剧本技能的依赖面。
        package = skill_registry.default_root() / '00全流程SKILL' / 'jingju-skills'
        self.assertTrue((package / 'SKILL.md').is_file())
        self.assertNotIn('jingju-skills', skills)
        known = set(skills)
        for skill in skills.values():
            self.assertNotIn('jingju-skills', skill.dependsOn)
            if skill.stage in ('script', 'script_structure'):
                self.assertEqual(skill_registry.classify_dependencies(skill, known)['external'], [])
        self.assertEqual(list(registry.warnings()), [])


if __name__ == '__main__':
    unittest.main()
