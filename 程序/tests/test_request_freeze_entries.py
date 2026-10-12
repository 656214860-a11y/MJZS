"""O15：各生成入口消费同一份请求快照（已勾选／本次实际加载，含版本摘要）。"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import model_pool
import stage_config
import workflow_settings
import writing_api
from agent.core import save
from tests.test_workflow import make_project


ROOT = Path(__file__).resolve().parents[1]


class RequestFreezeEntryTests(unittest.TestCase):
    """入口差异：直连 API 与桌面 Agent 投递都从一次捕获的快照取技能内容。"""

    def frozen_project(self, td, marker):
        project = make_project(td)
        skill = Path(td) / 'SKILL.md'
        skill.write_text(marker, encoding='utf-8')
        config = workflow_settings.defaults('writing')
        for profile in config['profiles'].values():
            workflow_settings.set_skills(profile, [str(skill)])
        save(workflow_settings.settings_path(project), {'flows': {'writing': config}})
        stage_config.put(project, 'script', model='gpt-4o', skills=[])
        return project, skill

    def test_capture_request_freezes_and_later_config_saves_only_affect_new_tasks(self):
        with tempfile.TemporaryDirectory() as td:
            project, skill = self.frozen_project(td, '第一版技能标记')
            with patch('model_pool.pool', return_value=model_pool.default_pool()):
                first = writing_api.capture_request(project)['settings']
                injection = first['skill_injection']
                self.assertEqual(len(injection['selected']), 1)
                self.assertEqual(len(injection['loaded']), 1)
                self.assertTrue(injection['loaded'][0]['sha256'])
                self.assertIn('第一版技能标记', first['frozen_skill_prompt'])
                # 保存新配置后，这一次的冻结快照不变；只有新任务读到新内容。
                skill.write_text('第二版技能标记', encoding='utf-8')
                stage_config.put(project, 'script', model='deepseek-v4-flash', skills=[])
                self.assertIn('第一版技能标记', first['frozen_skill_prompt'])
                self.assertNotIn('第二版技能标记', first['frozen_skill_prompt'])
                second = writing_api.capture_request(project)['settings']
                self.assertIn('第二版技能标记', second['frozen_skill_prompt'])
                self.assertNotEqual(second['skill_injection']['loaded'][0]['sha256'],
                                    injection['loaded'][0]['sha256'])

    def test_frozen_digest_is_identical_across_entries(self):
        with tempfile.TemporaryDirectory() as td:
            project, _skill = self.frozen_project(td, '入口差异技能标记')
            with patch('model_pool.pool', return_value=model_pool.default_pool()):
                direct = writing_api.capture_request(project)['settings']
                delivered = workflow_settings.freeze_skills(workflow_settings.current(project, 'writing'))
            self.assertEqual(direct['skill_injection']['loaded'][0]['sha256'],
                             delivered['skill_injection']['loaded'][0]['sha256'])
            self.assertEqual(direct['skill_injection']['selected'],
                             delivered['skill_injection']['selected'])

    def test_every_generation_entry_consumes_one_captured_snapshot(self):
        desktop = (ROOT / 'desktop.py').read_text(encoding='utf-8')
        api = (ROOT / 'writing_api.py').read_text(encoding='utf-8')
        self.assertIn('request_model = writing_api.capture_request(self.root)', desktop)
        self.assertIn('validate_selected_skills(self.root, stage)', desktop)
        self.assertIn('config = freeze_skills(config)', desktop)
        self.assertIn("request['settings'] = workflow_settings.freeze_skills(settings)", api)
        # 桌面所有阶段派发都只经 open_flow_agent 这一条投递入口。
        self.assertEqual(desktop.count('launch_interactive('), 1)
        start = desktop.index('def open_flow_agent(')
        flow = desktop[start:desktop.index('\n    def ', start + 5)]
        self.assertLess(flow.index('current(self.root,stage)'), flow.index('def build():'),
                        '配置快照必须先于工作线程内的提示词构建捕获')
