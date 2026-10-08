"""SKILL frontmatter 块标量简介回归。"""
import unittest
from pathlib import Path

import skill_registry


class BlockScalarTests(unittest.TestCase):
    def test_block_scalar_description_reaches_imported_package(self):
        for marker in ('>', '>-', '>+', '|', '|-', '|+'):
            with self.subTest(marker=marker):
                meta, body = skill_registry.parse(
                    '---\ndescription: ' + marker + '\n  第一行\n  第二行\n'
                    'tools:\n  - script.generate\nname: sample\n---\n正文')
                expected = '第一行\n第二行' if marker.startswith('|') else '第一行 第二行'
                self.assertEqual(meta['description'], expected)
                self.assertEqual(meta['tools'], ['script.generate'])
                self.assertEqual(meta['name'], 'sample')
                self.assertEqual(body, '正文')
                package = Path('skills/01剧本准备SKILL/sample')
                imported = skill_registry.imported_package_meta(meta, body, package, package / 'SKILL.md')
                self.assertEqual(imported['description'], expected)

    def test_plain_multiline_scalar_resets_separator_after_literal_block(self):
        meta, _ = skill_registry.parse(
            '---\ndescription: |\n  第一行\n  第二行\n'
            'notes:\n  普通行一\n  普通行二\n---\n')
        self.assertEqual(meta['description'], '第一行\n第二行')
        self.assertEqual(meta['notes'], '普通行一 普通行二')
