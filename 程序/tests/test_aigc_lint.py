# -*- coding: utf-8 -*-
"""总控包 scripts 机检桥（aigc_lint）与 skill_tools 接线的定向回归。

覆盖两类事实：
1. 桥的契约 —— 子模块未挂载返回友好 dict（不裸抛）、subprocess 桥的退出码映射、
   import 桥的画风锁纯函数返回形状；
2. 接线 —— ``feed.*`` / ``style.*`` 五个工具登记进 READY，``call`` 能跑通并能把
   未挂载 / 缺输入转成既有的 ToolError / ToolNeedsInput，不泄露 Traceback。

子模块挂载时的真实机检由上游脚本自己的 ``--self-test`` 覆盖（本机已实测 PASSED），
本文件只钉桥这一层，不重复跑 400KB 脚本的全量判据。
"""
from __future__ import annotations

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, PROGRAM)
sys.path.insert(1, HERE)

from infra import aigc_lint
import skill_tools
from skip_reasons import REQUIRES_BUNDLED_SKILL


def _mounted():
    """子模块 scripts 是否在磁盘上（工作树可能未初始化子模块）。"""
    return aigc_lint._scripts_root() is not None


class BridgeContractTests(unittest.TestCase):
    def test_unmounted_scripts_return_friendly_dict_not_raise(self):
        if _mounted():
            self.skipTest(REQUIRES_BUNDLED_SKILL)
        for name in ('validate_prompt', 'gate_check', 'audit_contract',
                     'style_ladder', 'style_recommend'):
            func = getattr(aigc_lint, name)
            with self.subTest(func=name):
                result = func('任意正文') if name not in ('style_ladder',) else func('玄幻')
                self.assertIsInstance(result, dict)
                self.assertFalse(result.get('ok'))
                self.assertIn('未挂载', result.get('error', ''))

    def test_validate_prompt_returns_structured_dict_when_mounted(self):
        if not _mounted():
            self.skipTest(REQUIRES_BUNDLED_SKILL)
        # 非投喂稿：exit 3，桥仍应返回结构化 dict 而非抛异常。
        result = aigc_lint.validate_prompt('这不是投喂稿，没有七段式栏位。')
        self.assertIsInstance(result, dict)
        self.assertIn('exit', result)
        self.assertIn(result['exit'], (0, 1, 2, 3))

    def test_gate_check_returns_structured_dict_when_mounted(self):
        if not _mounted():
            self.skipTest(REQUIRES_BUNDLED_SKILL)
        result = aigc_lint.gate_check('无投喂单元正文')
        self.assertIsInstance(result, dict)
        self.assertIn('exit', result)

    def test_style_recommend_returns_pool_shape_when_mounted(self):
        if not _mounted():
            self.skipTest(REQUIRES_BUNDLED_SKILL)
        result = aigc_lint.style_recommend('玄幻仙侠打斗，有法术特效')
        self.assertIsInstance(result, dict)
        if result.get('ok'):
            self.assertIn('pool', result)
            self.assertIn('excluded', result)
            self.assertIsInstance(result['pool'], list)

    def test_style_ladder_returns_text_when_mounted(self):
        if not _mounted():
            self.skipTest(REQUIRES_BUNDLED_SKILL)
        result = aigc_lint.style_ladder('都市情感夜戏，无打斗')
        self.assertIsInstance(result, dict)
        if result.get('ok'):
            self.assertIn('text', result)
            self.assertIsInstance(result['text'], str)


class SkillToolsWiringTests(unittest.TestCase):
    def test_feed_and_style_tools_are_registered_ready(self):
        for tool in ('feed.validate', 'feed.gateCheck', 'feed.auditContract',
                     'style.lockRecommend', 'style.lockLadder'):
            with self.subTest(tool=tool):
                self.assertIn(tool, skill_tools.READY)
                self.assertEqual(skill_tools.status_of(tool), 'ready')

    def test_feed_validate_requires_feed_input(self):
        with self.assertRaises(skill_tools.ToolNeedsInput):
            skill_tools.call('feed.validate', {})

    def test_style_recommend_requires_genre_input(self):
        with self.assertRaises(skill_tools.ToolNeedsInput):
            skill_tools.call('style.lockRecommend', {})

    def test_unmounted_feed_validate_raises_toolerror_not_traceback(self):
        if _mounted():
            self.skipTest(REQUIRES_BUNDLED_SKILL)
        with self.assertRaises(skill_tools.ToolError):
            skill_tools.call('feed.validate', {'feed': '任意正文'})


if __name__ == '__main__':
    unittest.main()
