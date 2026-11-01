"""手动制作弹窗的摘要：没打开项目也出得来，门禁评估只跑必要的那几遍。

stage_models.plan_window 不带项目调 summary_lines。从前 summary_lines 转去 step_summary，
step_summary 拼 lines 时又以同一个项目转回 summary_lines：没打开项目时两边互相调用直到
RecursionError（有门禁的阶段则先在门禁检查里因 None 抛 TypeError）；打开了项目也要把
stage_parallel.evaluate 跑三遍，每遍都按门禁去读资产索引、台账与批次。
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import stage_flow
import stage_parallel
from pet_bus import STAGES


def _desktop(root):
    subject = type('Stub', (), {})()
    subject.root = root
    subject.app = None
    return subject


def _project(td, state=None):
    proj = Path(td) / 'p'
    (proj / '工作流任务' / '宠物').mkdir(parents=True)
    if state:
        (proj / '工作流任务' / '宠物' / '阶段状态.json').write_text(
            json.dumps(state, ensure_ascii=False), encoding='utf-8')
    return proj


class SummaryWithoutProjectTests(unittest.TestCase):
    def test_every_stage_gets_its_lines_without_a_project(self):
        for stage in STAGES:
            with self.subTest(stage=stage):
                lines = stage_flow.summary_lines(_desktop(None), stage)
                self.assertTrue(2 <= len(lines) <= 4, lines)
                self.assertTrue(lines[0].startswith('模型：'))
                self.assertTrue(lines[1].startswith('SKILL：'))
                self.assertNotIn('依赖：', '\n'.join(lines))
                self.assertEqual(stage_flow.step_summary(_desktop(None), stage)['lines'], lines)

    def test_nothing_blocks_without_a_project(self):
        for stage in STAGES:
            with self.subTest(stage=stage):
                self.assertEqual(stage_flow.blockers(None, stage), [])


class SummaryGateCountTests(unittest.TestCase):
    def count_evaluate(self, call):
        with mock.patch.object(stage_parallel, 'evaluate', wraps=stage_parallel.evaluate) as evaluate:
            result = call()
        return result, evaluate.call_count

    def test_summary_lines_evaluates_the_gate_once(self):
        with tempfile.TemporaryDirectory() as td:
            proj = _project(td)
            lines, count = self.count_evaluate(lambda: stage_flow.summary_lines(_desktop(proj), 'keyframe'))
        self.assertEqual(count, 1)                       # 只有 blockers 那一遍
        self.assertLessEqual(len(lines), 4)

    def test_step_summary_evaluates_the_gate_twice(self):
        with tempfile.TemporaryDirectory() as td:
            proj = _project(td)
            data, count = self.count_evaluate(lambda: stage_flow.step_summary(_desktop(proj), 'keyframe', proj))
        self.assertEqual(count, 2)                       # blockers 一遍，gate 那句文案一遍
        self.assertLessEqual(len(data['lines']), 4)

    def test_both_entries_give_the_same_lines(self):
        with tempfile.TemporaryDirectory() as td:
            proj = _project(td, {'stages': {'final': {'state': 'failed'}}})
            lines = stage_flow.summary_lines(_desktop(proj), 'keyframe')
            data = stage_flow.step_summary(_desktop(proj), 'keyframe', proj)
        self.assertEqual(data['lines'], lines)
        self.assertEqual(data['blocked'], ['final'])
        self.assertIn('依赖：分镜定稿未完成', lines[-1])


if __name__ == '__main__':
    unittest.main()
