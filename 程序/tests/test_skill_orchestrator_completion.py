# -*- coding: utf-8 -*-
"""REQ-S13-54：L3/SKILL 完成事件出口——页面未打开也能完成，空项目不推进自动链。

任务书轮 7B（D10-a/D10-c）：非剧本阶段的 SKILL ``DONE`` 现在经
``stage_completion_service.emit_verified_completion`` 按磁盘证据发
``stage.completed``；``completion_evidence(None)`` 判未完成；自动链只在真实
完成事件上推进。
"""
import tempfile
import unittest
from pathlib import Path

import pet_bus
import stage_flow
import stage_completion_service
from agent.core import save
from contract.stage_path_service import write_dir
from orchestrator import skill_orchestrator


def adopted_storyboard(root):
    """一份已采用且含镜头的分镜 JSON：storyboard 阶段证据成立的最小项目。"""
    folder = write_dir(root, 'storyboard')
    folder.mkdir(parents=True, exist_ok=True)
    source = folder / 'episode_v2.json'
    save(source, {'episode_id': 'EP001', 'title': '第1集',
                  'shots': [{'id': 'SH001', 'location': 'LOC_001', 'title': '开场'}]})
    save(root / 'ui_settings.json',
         {'frame_json': str(source), 'adopted_storyboards': [str(source)]})
    return source


def pacing_context(project):
    """storyboard-pacing-check 的两个工具都换成「跑完了」的替身，不碰真实页面。"""
    return {'project': str(project) if project else '',
            'tools': {'storyboard.pacingCheck': {'ok': True},
                      'storyboard.continuityCheck': {'ok': True}}}


class SkillCompletionExitTests(unittest.TestCase):
    """L3 无界面路径：核验通过才发 stage.completed，且整轮恰好一条。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def _run(self, project, context=None):
        bus = pet_bus.Bus()
        delivered = []
        bus.subscribe('*', delivered.append)
        orch = skill_orchestrator.default_orchestrator(project=str(project or ''), bus=bus)
        row = orch.execute('storyboard-pacing-check', context or pacing_context(project))
        bus.pump()
        return row, delivered

    def test_req_s13_54_headless_storyboard_emits_exactly_one_completed(self):
        """REQ-S13-54：页面未打开时，非剧本 SKILL DONE＋磁盘证据→恰好一条 stage.completed。"""
        adopted_storyboard(self.root)
        row, delivered = self._run(self.root)
        self.assertEqual(row['status'], skill_orchestrator.DONE)
        completed = [item for item in delivered
                     if item['kind'] == 'stage.completed' and item.get('stage') == 'storyboard']
        self.assertEqual(len(completed), 1,
                         'L3 无界面完成必须恰好投递一条 stage.completed：%r' % delivered)
        self.assertEqual(completed[0].get('run'), 1)   # 终态事件带本轮 run（R4A/R3286）
        self.assertIn('stage.started', [item['kind'] for item in delivered])
        self.assertFalse([item for item in delivered if item['kind'] == 'stage.paused'])

    def test_req_s13_54_empty_project_does_not_advance_auto_chain(self):
        """REQ-S13-54：空项目 SKILL DONE 只发 stage.paused，自动链不推进。"""
        auto = stage_flow.Auto(order=list(pet_bus.STAGES))
        auto.script_done('auto')
        self.assertTrue(auto.armed)
        bus = pet_bus.Bus()
        bus.subscribe('stage.completed',
                      lambda item: auto.done(str(item.get('stage') or ''), True))
        delivered = []
        bus.subscribe('*', delivered.append)
        orch = skill_orchestrator.default_orchestrator(project=str(self.root), bus=bus)
        row = orch.execute('storyboard-pacing-check', pacing_context(self.root))
        bus.pump()
        self.assertEqual(row['status'], skill_orchestrator.DONE)
        self.assertFalse([item for item in delivered if item['kind'] == 'stage.completed'],
                         '空项目不得发出 stage.completed')
        paused = [item for item in delivered if item['kind'] == 'stage.paused'
                  and item.get('stage') == 'storyboard']
        self.assertEqual(len(paused), 1)
        self.assertIn('还没有已采用', str(paused[0].get('reason') or ''))
        self.assertEqual(auto.index, 0)
        self.assertEqual(auto.pending(), list(pet_bus.STAGES))

    def test_req_s13_54_no_project_context_never_completes(self):
        """REQ-S13-54：project 为空串／None 时证据判未完成，只发 stage.paused。"""
        for project in ('', None):
            with self.subTest(project=project):
                row, delivered = self._run(project, pacing_context(project))
                self.assertEqual(row['status'], skill_orchestrator.DONE)
                self.assertFalse([item for item in delivered
                                  if item['kind'] == 'stage.completed'])
                paused = [item for item in delivered if item['kind'] == 'stage.paused'
                          and item.get('stage') == 'storyboard']
                self.assertEqual(len(paused), 1)
                self.assertIn('未打开项目', str(paused[0].get('reason') or ''))

    def test_req_s13_54_verified_stage_output_covers_all_stages(self):
        """REQ-S13-54：verified_stage_output 不再限剧本两段——有证据的阶段为真。"""
        self.assertTrue(skill_orchestrator.verified_stage_output(self.root, 'storyboard') is False)
        adopted_storyboard(self.root)
        self.assertTrue(skill_orchestrator.verified_stage_output(self.root, 'storyboard'))
        for stage in pet_bus.STAGES:
            if stage != 'storyboard':
                self.assertFalse(skill_orchestrator.verified_stage_output(self.root, stage),
                                 '%s 在只有分镜证据的项目里不应算完成' % stage)
        self.assertFalse(skill_orchestrator.verified_stage_output(None, 'storyboard'))
        self.assertFalse(skill_orchestrator.verified_stage_output('', 'storyboard'))


if __name__ == '__main__':
    unittest.main()
