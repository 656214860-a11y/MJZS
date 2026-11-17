"""本地 Agent 剧本任务须给出当前采用剧本的绝对路径，即使它在其他模型目录下。"""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from orchestrator import workflow_tasks

SCRIPT = '# 第1集：测试\n\n## 正文\n### 场景 1：街道\n阿明：我要找到真相。\n动作：阿明推开门。\n'


class CurrentScriptNoticeTests(unittest.TestCase):
    def _project(self, td):
        path = Path(td) / '01剧本准备' / 'Anthropic' / 'Claude Desktop' / '创意_20261014' / '项目剧本' / '测试_自然剧本.md'
        path.parent.mkdir(parents=True)
        path.write_text(SCRIPT, encoding='utf-8')
        return path

    def test_other_model_script_path_reaches_initial_and_followup_tasks(self):
        with tempfile.TemporaryDirectory() as td, patch(
                'workflow_settings.model_name', return_value='Claude Code CLI'):
            script = self._project(td).resolve().as_posix()
            for text in (
                    workflow_tasks.script_prompt(td, None, 'writing', creative_text='改', agent_delivery=True, bounded_input=True),
                    workflow_tasks.script_followup(None, 'writing', project=td, creative_text='改', agent_delivery=True, bounded_input=True)):
                self.assertIn('【当前自然剧本】' + script, text)
                self.assertIn('不得脱离它从零另写', text)

    def test_no_script_and_api_path_emit_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(workflow_tasks._current_script_notice(td), '')
            self._project(td)
            self.assertNotIn('【当前自然剧本】', workflow_tasks.script_prompt(td, None, 'writing', creative_text='改'))


if __name__ == '__main__':
    unittest.main()
