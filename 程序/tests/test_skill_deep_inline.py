# -*- coding: utf-8 -*-
"""剧本准备页 skill 完整内联（递归引用、脚本、frontmatter 剥离、回环、超限、CLI 目录白名单）。"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import workflow_settings
from workflow_settings import _inline_skill, _inline_skill_report, skill_roots_for_config


def _write(root, rel, text):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return path


class DeepInlineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'skills'
        (self.root / '01 剧本准备SKILL').mkdir(parents=True)

    def _patch_roots(self):
        return patch('skill_registry.skill_roots', return_value=(self.root.resolve(), self.root.resolve()))

    def test_depth_minus_one_recurses_nested_markdown(self):
        stage = self.root / '01 剧本准备SKILL'
        a = _write(stage, 'a.skill.md',
                   '---\nname: a\ndescription: x\nstage: 剧本准备\n---\nA 正文\n[引用B](./b.md)\n')
        _write(stage, 'b.md', 'B 正文\n[引用C](./c.md)\n')
        _write(stage, 'c.md', 'C 正文\n')
        with self._patch_roots():
            out = _inline_skill(a, depth=-1)
        self.assertIn('A 正文', out)
        self.assertIn('## 引用: b.md', out)
        self.assertIn('B 正文', out)
        self.assertIn('## 引用: c.md', out)
        self.assertIn('C 正文', out)

    def test_depth_zero_keeps_historical_single_level(self):
        stage = self.root / '01 剧本准备SKILL'
        a = _write(stage, 'a.skill.md',
                   '---\nname: a\ndescription: x\nstage: 剧本准备\n---\nA 正文\n[引用B](./b.md)\n')
        _write(stage, 'b.md', 'B 正文\n[引用C](./c.md)\n')
        _write(stage, 'c.md', 'C 正文\n')
        with self._patch_roots():
            out = _inline_skill(a, depth=0)
        self.assertIn('B 正文', out)
        self.assertNotIn('C 正文', out)

    def test_script_inlined_as_code_block_and_binary_gets_hint(self):
        stage = self.root / '01 剧本准备SKILL'
        a = _write(stage, 'a.skill.md',
                   '---\nname: a\ndescription: x\nstage: 剧本准备\n---\n'
                   'A 正文\n[脚本](./run.py)\n[图片](./pic.png)\n')
        _write(stage, 'run.py', 'print("hi")\n')
        _write(stage, 'pic.png', 'not really binary')
        with self._patch_roots():
            out = _inline_skill(a, depth=-1)
        self.assertIn('## 脚本: run.py', out)
        self.assertIn('print("hi")', out)
        self.assertIn('本请求不发送该资源', out)
        self.assertIn('pic.png', out)

    def test_frontmatter_stripped_but_name_tag_kept(self):
        stage = self.root / '01 剧本准备SKILL'
        a = _write(stage, 'a.skill.md',
                   '---\nname: a\ndescription: 这是描述\nstage: 剧本准备\n'
                   'capabilities: [creative-writing]\n---\n正文内容\n')
        with self._patch_roots():
            out = _inline_skill(a, depth=-1)
        self.assertIn('<skill name="a">', out)
        self.assertIn('正文内容', out)
        self.assertNotIn('description:', out)
        self.assertNotIn('capabilities:', out)

    def test_cycle_does_not_recurse_forever(self):
        stage = self.root / '01 剧本准备SKILL'
        a = _write(stage, 'a.skill.md',
                   '---\nname: a\ndescription: x\nstage: 剧本准备\n---\nA 正文\n[引用B](./b.md)\n')
        _write(stage, 'b.md', 'B 正文\n[回A](./a.skill.md)\n')
        with self._patch_roots():
            _, closure = _inline_skill_report(a, depth=-1)
        # 回环应被记为 cycle，而不是无限展开。
        self.assertTrue(any(row.get('status') == 'cycle' for row in closure))

    def test_size_limit_error_names_the_skill(self):
        stage = self.root / '01 剧本准备SKILL'
        a = _write(stage, 'big.skill.md',
                   '---\nname: big\ndescription: x\nstage: 剧本准备\n---\n' + '长' * 100)
        with self._patch_roots():
            with self.assertRaises(ValueError) as ctx:
                _inline_skill_report(a, cap=10, depth=-1)
        self.assertIn('big', str(ctx.exception))
        self.assertIn('字符', str(ctx.exception))

    def test_cli_directory_whitelist_collects_skill_dirs(self):
        stage = self.root / '01 剧本准备SKILL'
        a = _write(stage, 'a.skill.md',
                   '---\nname: a\ndescription: x\nstage: 剧本准备\n---\n正文\n')
        config = {'stage_skills': [str(a)]}
        with self._patch_roots():
            dirs = skill_roots_for_config(config)
        resolved = [os.path.normcase(str(Path(d).resolve())) for d in dirs]
        self.assertIn(os.path.normcase(str(stage.resolve())), resolved)
        self.assertIn(os.path.normcase(str(self.root.resolve())), resolved)

    def test_cli_directory_whitelist_empty_without_skills(self):
        with self._patch_roots():
            self.assertEqual(skill_roots_for_config({'stage_skills': []}), [])

    def test_inline_depth_scoped_to_writing(self):
        stage = self.root / '01 剧本准备SKILL'
        a = _write(stage, 'a.skill.md',
                   '---\nname: a\ndescription: x\nstage: 剧本准备\n---\nA正文\n[引用B](./b.md)\n')
        _write(stage, 'b.md', 'B正文\n[引用C](./c.md)\n')
        _write(stage, 'c.md', 'C正文\n')
        with self._patch_roots():
            writing = workflow_settings.skill_prompt({'stage': 'writing', 'stage_skills': [str(a)]}, inline=True)
            other = workflow_settings.skill_prompt({'stage': 'storyboard', 'stage_skills': [str(a)]}, inline=True)
        self.assertIn('C正文', writing)
        self.assertNotIn('C正文', other)

    def test_budget_skips_oversize_references_with_skipped_status(self):
        """预算耗尽时递归引用不再内联：记 skipped 并留本地路径提示，SKILL 正文照常。"""
        stage = self.root / '01 剧本准备SKILL'
        a = _write(stage, 'a.skill.md',
                   '---\nname: a\ndescription: x\nstage: 剧本准备\n---\nA 正文\n[引用B](./b.md)\n[引用C](./c.md)\n')
        b = _write(stage, 'b.md', 'B 正文\n')
        c = _write(stage, 'c.md', '长正文' * 500)
        budget = {'remaining': 200}      # 只装得下小引用
        with self._patch_roots():
            body, closure = _inline_skill_report(a, depth=-1, budget=budget)
        self.assertIn('A 正文', body)
        self.assertIn('B 正文', body)                      # 小引用仍在预算内
        self.assertNotIn('长正文' * 500, body)              # 大引用被预算挡下
        self.assertIn('本地路径', body)                     # 留提示供目录白名单引擎按需读取
        statuses = {row['target']: row['status'] for row in closure if row.get('status')}
        self.assertEqual(statuses['./c.md'], 'skipped')

    def test_skill_inline_token_budget_scales_with_window(self):
        from contract.workflow_context_budget import skill_inline_token_budget
        self.assertIsNone(skill_inline_token_budget(0))                       # 查不到窗口不设限
        small = skill_inline_token_budget(128_000)
        large = skill_inline_token_budget(1_000_000)
        self.assertLess(small, 128_000)
        self.assertGreater(large, small)


if __name__ == '__main__':
    unittest.main()
