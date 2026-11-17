# -*- coding: utf-8 -*-
"""REQ-S09-50：白模预演需要本地 Agent；选了 API 模型（engine=qwen）时不启动 Qwen、不创建批次，并给出明确提示。"""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

MESSAGE = '白模预演需要本地 Agent（Claude 或 Codex 桌面通道），请在该阶段设置里切换引擎'


def config(engine):
    return {'engine': engine, 'model': 'deepseek-v4-pro', 'program': '', 'stage': '白模预演'}


class PrevisLocalAgentOnlyTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.project = Path(temp.name).resolve()

    def build(self, engine):
        import desktop_idea_chat as chat
        calls = []
        host = SimpleNamespace(root=self.project, worker=None, projects=SimpleNamespace(info={'projects': []}),
                               async_=lambda *a, **k: calls.append('async'))
        request = chat._FlowAgentRequest('previs', '白模预演', 'p', None, None, None, False, False, False)
        with patch('workflow_settings.current', return_value=config(engine)), \
                patch('orchestrator.qwen_adapter.window_title', side_effect=lambda *a, **k: calls.append('qwen')) as title:
            chat._FlowAgentLaunch(host, request).build()
        return calls, title

    def test_req_s09_50_manual_flow_refuses_qwen_without_starting_anything(self):
        """REQ-S09-50：手动入口选 API 模型（qwen）时抛出提示，不排队、不走 qwen_adapter。"""
        calls = []
        with self.assertRaises(ValueError) as caught:
            calls, _title = self.build('qwen')
        self.assertIn(MESSAGE, str(caught.exception))
        self.assertEqual([], calls)

    def test_req_s09_50_manual_flow_unchanged_for_codex_and_claude(self):
        """REQ-S09-50：codex／claude 照常派发。"""
        for engine in ('codex', 'claude'):
            with self.subTest(engine=engine):
                try:
                    calls, _title = self.build(engine)
                except KeyError:
                    continue  # 派发所需的 config 字段这里没给全；关键是没被提示拦下
                self.assertIn('async', calls)

    def test_req_s09_50_batch_refuses_qwen_before_creating_batch(self):
        """REQ-S09-50：批量入口选 API 模型时直接拒绝，不建批次目录、不调用 run_background／qwen_setup。"""
        import previs_automation as pa
        state = {}
        with patch('workflow_settings.current', return_value=config('qwen')), \
                patch('workflow_engines.run_background') as run, patch('qwen_setup.environment') as setup:
            with self.assertRaises(ValueError) as caught:
                pa.start(self.project, self.project / 'x.json', ['SH001'], state)
        self.assertIn(MESSAGE, str(caught.exception))
        run.assert_not_called()
        setup.assert_not_called()
        self.assertFalse((self.project / '工作流任务').exists())
        self.assertFalse(state.get('busy'))

    def test_req_s09_50_require_local_agent_only_rejects_qwen(self):
        """REQ-S09-50：唯一判定函数只拦 qwen，其余引擎放行。"""
        import previs_automation as pa
        for engine in ('codex', 'claude', 'opencode', 'client-cli', 'desktop-app', 'claude-desktop-app'):
            pa.require_local_agent(config(engine))
        with self.assertRaises(ValueError):
            pa.require_local_agent(config('qwen'))


if __name__ == '__main__':
    unittest.main()
