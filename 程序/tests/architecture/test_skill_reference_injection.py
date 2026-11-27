"""内置 SKILL 净化与总包/阶段引用解析门禁：退役内建总控与残留包后不留断链或幽灵包。"""
from pathlib import Path
import tempfile
import unittest

import skill_registry
from orchestrator.skill_registry import reference_targets, resolve_reference

PROGRAM = Path(__file__).resolve().parents[2]
SKILLS = PROGRAM / 'skills'
RETIRED_ROOT_PACKAGES = ('imagegen', 'short-drama-storyboard',
                         'storyboard-image-prompts', 'video-storyboard-gen')


class SkillReferenceInjectionTests(unittest.TestCase):
    def test_builtin_root_has_no_retired_packages_or_skill_files(self):
        for name in RETIRED_ROOT_PACKAGES:
            self.assertFalse((SKILLS / name).exists(), f'内置根部遗留包未清理：{name}')
        self.assertFalse((SKILLS / 'skills-lock.json').exists(), '遗留 skills-lock.json 未清理')
        self.assertEqual(list(SKILLS.rglob('*.skill.md')), [])
        self.assertEqual(list(SKILLS.rglob('SKILL.md')), [])
        self.assertTrue((SKILLS / '00 总包SKILL').is_dir(), '缺少 00 总包SKILL 目录骨架')
        self.assertTrue((SKILLS / 'templates').is_dir(), '应保留模板目录 templates/')

    def test_composite_suite_and_stage_skill_references_resolve_cleanly(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'skills'
            suite = root / '00 总包SKILL' / 'demo-suite'
            director = suite / 'short-drama-director'
            sub = suite / 'sd-script-engine'
            (director / 'references').mkdir(parents=True)
            sub.mkdir(parents=True)
            (director / 'references' / 'rules.md').write_text('# 规则\n', encoding='utf-8')
            entry = director / 'SKILL.md'
            entry.write_text(
                '---\nname: short-drama-director\ndescription: 总控入口\n---\n\n'
                '先读 [规则](references/rules.md)，再调度 [剧本](../sd-script-engine/SKILL.md)。\n',
                encoding='utf-8')
            (sub / 'SKILL.md').write_text(
                '---\nname: sd-script-engine\ndescription: 剧本引擎\n---\n\n正文。\n',
                encoding='utf-8')
            registry = skill_registry.Registry(root)
            registry.scan(force=True)
            found = registry.get('demo-suite')
            self.assertIsNotNone(found)
            self.assertEqual(found.stage, skill_registry.SUITE_STAGE)
            self.assertEqual(found.path.resolve(), entry.resolve())
            self.assertIn(found, registry.getForStage('script'))
            text = entry.read_text(encoding='utf-8')
            targets = [item for item in reference_targets(text) if item.get('path')]
            self.assertGreaterEqual(len(targets), 1)
            for item in targets:
                self.assertTrue(resolve_reference(entry, item['path']).is_file(), item['raw'])
