# -*- coding: utf-8 -*-
"""资产／首帧出图选 API 模型（engine=qwen）时程序直连执行 image_agent_runner（REQ-S05-50、REQ-S08-52）：
不经 open_flow_agent／Qwen、成功与失败状态文件语义兼容、强制停止能中断、Codex／Claude 引擎行为不变。
全部使用假执行体，不调用真实 ComfyUI 或 API。"""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


class _Status:
    def __init__(self):
        self.messages = []

    def set(self, text):
        self.messages.append(text)


class ImageDirectJobTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.project = Path(temp.name).resolve() / '项目'
        self.folder = self.project / 'workflows' / 'Imagen资产批次' / 'b1'
        self.folder.mkdir(parents=True)
        self.manifest = self.folder / '批次.json'
        self.manifest.write_text(json.dumps({'assets': []}), encoding='utf-8')
        self.config = {'engine': 'qwen', 'model': 'deepseek-v4-pro', 'program': ''}

    def state(self):
        return json.loads((self.folder / '执行状态.json').read_text(encoding='utf-8'))

    def run_job(self, fake):
        from orchestrator import image_direct
        with patch('image_agent_runner._execute', side_effect=fake):
            job = image_direct.launch(self.project, self.config, manifest=self.manifest)
            job.join(5)
        self.assertFalse(job.is_alive())
        return job

    def test_req_s05_50_success_writes_complete_state_without_qwen(self):
        """REQ-S05-50：直连成功写 complete，不触碰 qwen_adapter／open_flow_agent。"""
        def fake(project, manifest, stop=None):
            (self.folder / 'CHAR001.png').write_bytes(b'png')
        with patch('orchestrator.qwen_adapter.window_title', side_effect=AssertionError('不应走 Qwen')):
            job = self.run_job(fake)
        self.assertTrue(job.results[0]['ok'])
        self.assertEqual('complete', self.state()['state'])
        self.assertTrue((self.folder / 'CHAR001.png').is_file())

    def test_req_s05_50_failure_writes_failed_state_with_reason(self):
        """REQ-S05-50／S08-52：失败写 failed 并说明原因。"""
        def fake(project, manifest, stop=None):
            raise ValueError('ComfyUI 未启动')
        job = self.run_job(fake)
        self.assertFalse(job.results[0]['ok'])
        self.assertEqual('failed', self.state()['state'])
        self.assertIn('ComfyUI 未启动', self.state()['message'])
        from asset_batch_lifecycle import status
        from stage_execution_service import asset_batch_gateway
        self.assertEqual('failed', status(self.manifest, gateway=asset_batch_gateway())['state'])

    def test_req_s05_50_stop_interrupts_runner(self):
        """REQ-S05-50／S08-52：强制停止置位 stop，执行体退出，状态为 failed 并说明已停止。"""
        from orchestrator import image_direct
        from infra.workflow_process_registry import cancel_project_requests
        started = threading.Event()

        def fake(project, manifest, stop=None):
            started.set()
            if not stop.wait(5):
                raise AssertionError('stop 从未被置位')
            raise ValueError('尚未出图：CHAR001')
        with patch('image_agent_runner._execute', side_effect=fake):
            job = image_direct.launch(self.project, self.config, manifest=self.manifest)
            self.assertTrue(started.wait(5))
            self.assertEqual(1, cancel_project_requests(self.project))
            job.join(5)
        self.assertFalse(job.is_alive())
        self.assertTrue(job.results[0]['stopped'])
        self.assertEqual('failed', self.state()['state'])
        self.assertIn('停止', self.state()['message'])

    def test_req_s05_50_execute_stop_defaults_to_fresh_event(self):
        """REQ-S05-50：execute／_execute 的 stop 可选，默认行为不变（子进程协议入口照旧）。"""
        import inspect
        import image_agent_runner as runner
        self.assertIsNone(inspect.signature(runner.execute).parameters['stop'].default)
        self.assertIsNone(inspect.signature(runner._execute).parameters['stop'].default)

    def test_req_s05_50_busy_project_rejects_second_job(self):
        """REQ-S05-50：同一项目已有直连作业时拒绝第二个。"""
        from orchestrator import image_direct
        release = threading.Event()

        def fake(project, manifest, stop=None):
            release.wait(5)
        with patch('image_agent_runner._execute', side_effect=fake):
            first = image_direct.launch(self.project, self.config, manifest=self.manifest)
            with self.assertRaises(ValueError):
                image_direct.launch(self.project, self.config, manifest=self.manifest)
            release.set()
            first.join(5)


class ImageDirectRoutingTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.project = Path(temp.name).resolve() / '项目'
        self.project.mkdir()

    def build(self, engine, direct):
        import desktop_idea_chat as chat
        config = {'engine': engine, 'model': 'deepseek-v4-pro', 'program': ''}
        host = SimpleNamespace(root=self.project, worker=None, projects=SimpleNamespace(info={'projects': []}),
                               async_=lambda *_a, **_k: None)
        request = chat._FlowAgentRequest('assets', '资产管理', 'p', None, None, None, False, False, False, direct)
        with patch('workflow_settings.current', return_value=config), \
                patch('desktop_image_direct.run_image_direct') as run:
            try:
                chat._FlowAgentLaunch(host, request).build()
            except Exception:  # 非直连路径后续依赖真实宿主，这里只关心有没有分流
                pass
        return run

    def test_req_s05_50_build_routes_qwen_engine_to_direct(self):
        """REQ-S05-50／S08-52：assets 带直连载荷且引擎为 qwen 时走直连。"""
        direct = {'image': self.project / '批次.json'}
        run = self.build('qwen', direct)
        run.assert_called_once()
        self.assertEqual(direct, run.call_args.args[1])

    def test_req_s05_50_build_keeps_other_engines_and_missing_payload(self):
        """REQ-S05-50／S08-52：codex／claude 引擎或没有载荷时不分流。"""
        direct = {'image': self.project / '批次.json'}
        for engine, payload in (('codex', direct), ('claude', direct), ('qwen', None)):
            self.build(engine, payload).assert_not_called()

    def test_req_s05_50_asset_launch_uses_direct_entry_for_qwen_only(self):
        """REQ-S05-50：资产批次 qwen 引擎经 open_direct_flow_agent，不再 open_flow_agent；codex 引擎仍 open_flow_agent 并带回执。"""
        import asset_skill_batch
        for engine in ('qwen', 'codex'):
            app = MagicMock()
            app.flow_processes = {}
            app.status = _Status()
            app.root = self.project
            base = self.project / '资产库'
            base.mkdir(exist_ok=True)
            asset = {'name': '林夏', 'image_prompt': 'x', 'reference_images': []}
            config = {'engine': engine, 'skill': 's', 'model': 'm', 'program': ''}
            with patch('contract.prop_assets.requires_asset', return_value=True), \
                    patch('asset_skill_batch.image_ready', return_value=False), \
                    patch('asset_batch_lifecycle.reconcile', return_value={}), \
                    patch('asset_reference_images.snapshot', side_effect=lambda _b, a: a), \
                    patch('asset_reference_images.resolve', return_value=[]), \
                    patch('asset_prompt_rules.issues', return_value=[]), \
                    patch('asset_skill_batch.asset_prompt', return_value='提示词'), \
                    patch('workflow_settings.current', return_value=config), \
                    patch('stage_parallel.brief_block', return_value=''), \
                    patch('asset_skill_batch.watch'):
                asset_skill_batch.launch(app, self.project, base, [('CHAR_001', asset)])
            if engine == 'qwen':
                app.open_flow_agent.assert_not_called()
                app.open_direct_flow_agent.assert_called_once()
                self.assertIn('image', app.open_direct_flow_agent.call_args.args[3])
            else:
                app.open_flow_agent.assert_called_once()
                self.assertIn('on_receipt', app.open_flow_agent.call_args.kwargs)
                app.open_direct_flow_agent.assert_not_called()


if __name__ == '__main__':
    unittest.main()
