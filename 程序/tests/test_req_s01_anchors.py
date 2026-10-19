# -*- coding: utf-8 -*-
"""REQ-S01 测试锚定：剧本准备里没有现成行为用例可挂的两条需求。

其余十二条需求（S01 段的 01、02、03、04、10、11、12、13、14、20、21、30）由 ``tests/``
下既有的行为用例锚定，见各测试 docstring；本文件只补下面两条没有现成锚点的需求。

- REQ-S01-22：阶段完成＝能解析到被采用的剧本源；模型文字／界面提示不算证据。
- REQ-S01-31：SKILL 内容超预算或缺失时阻止发送，不截断、不静默省略。

断言只调用真实函数（``stage_completion_service``／``script_contract``／
``workflow_context_budget``／``workflow_settings``／``stage_path_service``），不 mock
被测事实、不检查源码字符串；需要落盘时一律在 ``tempfile.TemporaryDirectory()`` 隔离目录内。
"""
import tempfile
import unittest
from pathlib import Path

import script_contract
import stage_completion_service
import stage_config
import workflow_context_budget
import workflow_settings
from agent.core import save
from stage_path_service import write_dir

RAW = (
    '第 1 集\n'
    '场景 1：夜，旧书店内\n'
    '林小满：把旧怀表交给我。\n'
    '陆时：先离开这里。\n'
    '道具：旧怀表\n'
)


class S01AnchorTests(unittest.TestCase):
    def test_req_s01_22_completion_evidence_is_the_adopted_script_source(self):
        """REQ-S01-22：阶段完成＝能解析到被采用的剧本源；模型文字不算证据。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            # 没有可解析的剧本源时不算完成；模型自称“写完了”也不发完成事件。
            self.assertFalse(stage_completion_service.completion_evidence(root, 'script')[0])
            events = []

            def emit(*args, **kwargs):
                events.append((args, kwargs))
                return {'ok': True}

            ok, _detail, payload = stage_completion_service.emit_verified_completion(
                root, 'script', '模型说写完了', emit)
            self.assertFalse(ok)
            self.assertIsNone(payload)
            self.assertEqual(events, [])
            # 出现被采用的剧本源后才有证据，事件才发出。
            folder = write_dir(root, 'script')
            folder.mkdir(parents=True, exist_ok=True)
            source = folder / '我的剧本_自然剧本_20260101.md'
            source.write_text(RAW, encoding='utf-8')
            self.assertEqual(script_contract.resolve_script_source(root), source)
            self.assertTrue(stage_completion_service.completion_evidence(root, 'script')[0])
            ok, _detail, payload = stage_completion_service.emit_verified_completion(
                root, 'script', '完成', emit)
            self.assertTrue(ok)
            self.assertEqual([args[0] for args, _kwargs in events], ['stage.completed'])
            self.assertEqual(events[0][1]['stage'], 'script')

    def test_req_s01_31_oversized_or_missing_skill_blocks_send_without_truncation(self):
        """REQ-S01-31：SKILL 缺失或超预算时阻止发送，且不截断、不静默省略。"""
        # 缺失：已勾选但未加载的 SKILL 直接阻止发送。
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            save(stage_config.path(project),
                 {'script': {'model': 'gpt-4o', 'skills': ['deleted-skill']}})
            with self.assertRaisesRegex(ValueError, '已勾选的 SKILL 未加载'):
                workflow_settings.validate_selected_skills(project, 'writing')
        # 超预算：冻结 SKILL 正文时走同一硬保护，抛错而不是截断或省略。
        oversized = '技' * (workflow_context_budget.REQUEST_CONTEXT_MAX_CHARS + 1)
        with self.assertRaises(ValueError) as caught:
            workflow_context_budget.ensure_request_context(oversized, 'SKILL')
        self.assertIn('超过', str(caught.exception))
        # 预算内的 SKILL 原样返回，不截断、不静默省略。
        text, _budget = workflow_context_budget.prepare_request_context('技能正文', 'SKILL', report=True)
        self.assertEqual(text, '技能正文')


if __name__ == '__main__':
    unittest.main()
