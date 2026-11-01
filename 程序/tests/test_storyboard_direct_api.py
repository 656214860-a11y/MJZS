# -*- coding: utf-8 -*-
"""初步分镜选 API 模型时的直连执行器（REQ-S03-53）：不经 Qwen、合格 JSON 才发布、
手动与三虎同一执行器、强制停止能中断请求。模型请求全部用假适配器，不调用真实 API。"""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


def good_episode(**extra):
    data = {'episode_id': 'EP001', 'title': '雨夜', 'duration': 6, 'prompt_language': 'zh',
            'source_script': '', 'shots': [{
                'id': 'SH001', 'title': '开场', 'duration': 6, 'characters': [], 'location': '街头', 'props': [],
                'frame': 'frames/SH001.png', 'frame_prompt': '雨夜街头静止画面',
                'video_prompt': '镜头缓推，雨夜街头，行人撑伞走过。', 'dialogue': []}]}
    data.update(extra)
    return data


class FakeAdapter:
    """按顺序返回预置回复；记录每次请求。block 给了就一直等到被取消。"""

    def __init__(self, *replies, block=None):
        self.replies = list(replies)
        self.calls = []
        self.block = block

    def stream(self, messages, options=None, model='', system='', on_chunk=None, cancelled=None):
        self.calls.append({'messages': list(messages), 'system': system})
        if self.block is not None:
            self.block.set()
            while not (cancelled and cancelled()):
                threading.Event().wait(0.01)
            return {'ok': False, 'text': '', 'error': '请求已取消', 'error_class': 'cancelled', 'model': model}
        text = self.replies.pop(0)
        return {'ok': True, 'text': text, 'error': '', 'model': model, 'response_meta': {'finish_reason': 'stop'}}

    chat = stream


class DirectApiTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.project = Path(temp.name).resolve() / '项目'
        self.script = self.project / '02剧本结构' / 'EP001_雨夜.md'
        self.script.parent.mkdir(parents=True)
        self.script.write_text('第一场 街头\n' + '雨夜，行人匆匆。' * 800, encoding='utf-8')
        self.config = {'engine': 'qwen', 'model': 'deepseek-v4-pro', 'program': ''}
        self.messages = []

    def run_batch(self, adapter, **extra):
        import storyboard_direct_api as api
        return api.run_batch(self.project, self.config, 'SKILL正文', scripts=[self.script], adapter=adapter,
                             record={'name': 'deepseek-v4-pro'}, report=self.messages.append, **extra)

    def boards(self):
        return sorted(self.project.rglob('*_分镜.json'))

    def test_req_s03_53_direct_model_only_for_pool_models(self):
        """REQ-S03-53：引擎为 qwen 且所选模型在模型池里才直连；桌面程序和本机 Codex／Claude 不直连。"""
        import storyboard_direct_api as api
        pool = {'deepseek-v4-pro': {'name': 'deepseek-v4-pro', 'call_mode': 'API'},
                'desk': {'name': 'desk', 'call_mode': 'Desktop'}}
        with patch('model_pool.pool', return_value=pool):
            self.assertEqual('deepseek-v4-pro', api.direct_model(self.config)[0])
            self.assertIsNone(api.direct_model({'engine': 'qwen', 'model': 'desk'}))
            self.assertIsNone(api.direct_model({'engine': 'qwen', 'model': 'missing'}))
            self.assertIsNone(api.direct_model({'engine': 'codex', 'model': 'deepseek-v4-pro'}))

    def test_req_s03_53_valid_json_is_published_without_qwen(self):
        """REQ-S03-53：合格 JSON 发布分镜与同名文档，全程不碰 qwen_adapter，请求里带完整剧本不截断。"""
        adapter = FakeAdapter(json.dumps(good_episode(), ensure_ascii=False))
        with patch('qwen_adapter.window_title') as qwen, patch('qwen_adapter.submit_existing') as submit:
            results = self.run_batch(adapter)
        qwen.assert_not_called()
        submit.assert_not_called()
        self.assertTrue(results[0]['ok'], results)
        boards = self.boards()
        self.assertEqual(1, len(boards))
        saved = json.loads(boards[0].read_text(encoding='utf-8'))
        self.assertEqual('EP001', saved['episode_id'])
        self.assertTrue(saved['source_script'].endswith('EP001_雨夜.md'))
        self.assertEqual(1, len(list(self.project.rglob('分镜文档/*.md'))))
        request = ''.join(str(m.get('content', '')) for m in adapter.calls[0]['messages'])
        self.assertIn('雨夜，行人匆匆。' * 800, request)
        self.assertIn('SKILL正文', adapter.calls[0]['system'])
        self.assertTrue(any('EP001' in text for text in self.messages))

    def test_req_s03_53_invalid_json_retries_once_then_writes_nothing(self):
        """REQ-S03-53：不合格带错误清单重试一次，仍不合格不落盘并给出原因。"""
        adapter = FakeAdapter(json.dumps(good_episode(duration=99)), '不是JSON')
        results = self.run_batch(adapter)
        self.assertEqual(2, len(adapter.calls))
        retry = ''.join(str(m.get('content', '')) for m in adapter.calls[1]['messages'])
        self.assertIn('duration', retry)
        self.assertFalse(results[0]['ok'])
        self.assertTrue(results[0]['error'])
        self.assertEqual([], self.boards())

    def test_req_s03_53_retry_can_recover(self):
        """REQ-S03-53：第一次不合格、重试合格则发布。"""
        adapter = FakeAdapter(json.dumps(good_episode(duration=99)), json.dumps(good_episode()))
        self.assertTrue(self.run_batch(adapter)[0]['ok'])
        self.assertEqual(1, len(self.boards()))

    def test_req_s03_53_manual_and_auto_share_one_executor(self):
        """REQ-S03-53：手动按钮与三虎 _start_storyboard 都经 open_flow_agent，分流点只有一处；其他阶段不进直连。"""
        import desktop_idea_chat as chat
        host = Mock(root=self.project, worker=False, projects=Mock(info={'projects': []}))
        request = chat._FlowAgentRequest('storyboard', '手动制作分镜', '任务', None, None, self.config,
                                         False, False, False)
        with patch('workflow_settings.current', return_value=self.config), \
                patch('storyboard_direct_api.direct_model', return_value=('deepseek-v4-pro', {'name': 'x'})), \
                patch('desktop_storyboard_direct.run_storyboard_direct') as direct, \
                patch('qwen_adapter.window_title') as qwen:
            chat._FlowAgentLaunch(host, request).build()
        direct.assert_called_once()
        qwen.assert_not_called()
        request = chat._FlowAgentRequest('video_prompt', '视频提示词', '任务', None, None, self.config, False, False, False)
        with patch('workflow_settings.current', return_value=self.config), \
                patch('storyboard_direct_api.direct_model', return_value=('m', {})) as model, \
                patch('desktop_storyboard_direct.run_storyboard_direct') as direct, \
                patch('qwen_adapter.window_title', return_value='Q'):
            chat._FlowAgentLaunch(host, request).build()
        direct.assert_not_called()
        model.assert_not_called()

    def test_req_s03_53_stop_interrupts_request_and_writes_nothing(self):
        """REQ-S03-53：workflow_engines.terminate 能中断进行中的直连请求，停止后不落盘；重复启动被拒。"""
        import storyboard_direct_api as api
        import workflow_engines
        started = threading.Event()
        adapter = FakeAdapter(block=started)
        job = api.launch(self.project, self.config, 'SKILL正文', scripts=[self.script], adapter=adapter,
                         record={'name': 'm'}, report=self.messages.append)
        self.assertTrue(started.wait(5))
        with self.assertRaisesRegex(ValueError, '正在直连制作'):
            api.launch(self.project, self.config, 'SKILL正文', scripts=[self.script], adapter=adapter, record={})
        workflow_engines.terminate(self.project)
        job.join(5)
        self.assertFalse(job.is_alive())
        self.assertEqual([], self.boards())
        self.assertFalse(job.results[0]['ok'])


if __name__ == '__main__':
    unittest.main()
