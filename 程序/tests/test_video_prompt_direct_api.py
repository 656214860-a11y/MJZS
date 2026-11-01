# -*- coding: utf-8 -*-
"""视频提示词渲染选 API 模型时的直连执行器（REQ-S10-50）：入口键有效、不经 Qwen、合格才落盘、
同一执行器骨架、强制停止能中断。模型请求全部用假适配器，不调用真实 API。"""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SIG = 'a' * 64


def good(text='SH001 林夏在雨中抬头，镜头缓推，环境雨声。'):
    return json.dumps({'shot_id': 'SH001', 'source_signature': SIG, 'video_prompt': text}, ensure_ascii=False)


class FakeAdapter:
    def __init__(self, *replies, block=None):
        self.replies, self.calls, self.block = list(replies), [], block

    def stream(self, messages, options=None, model='', system='', on_chunk=None, cancelled=None):
        self.calls.append({'messages': list(messages), 'system': system})
        if self.block is not None:
            self.block.set()
            while not (cancelled and cancelled()):
                threading.Event().wait(0.01)
            return {'ok': False, 'text': '', 'error': '请求已取消', 'error_class': 'cancelled', 'model': model}
        return {'ok': True, 'text': self.replies.pop(0), 'error': '', 'model': model,
                'response_meta': {'finish_reason': 'stop'}}

    chat = stream


class VideoPromptDirectTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.project = Path(temp.name).resolve() / '项目'
        self.output = self.project / '10视频生成' / 'video_prompts' / 'SH001.json'
        self.output.parent.mkdir(parents=True)
        self.context = {'shot_id': 'SH001', 'episode_id': 'EP001', 'source_signature': SIG,
                        'shot': {'id': 'SH001', 'duration': 5, 'action': '林夏抬头'}, 'assets': [], 'model': 'm'}
        self.config = {'engine': 'qwen', 'model': 'deepseek-v4-pro', 'program': ''}
        self.messages = []

    def direct(self, draft=''):
        return {'context': self.context, 'output': self.output, 'draft': draft}

    def run_batch(self, adapter, draft=''):
        import video_prompt_direct_api as api
        return api.run_batch(self.project, self.config, 'SKILL正文', direct=self.direct(draft), adapter=adapter, record={'name': 'deepseek-v4-pro'},
                             report=self.messages.append)

    def test_req_s10_50_flow_key_used_by_media_page_is_known(self):
        """REQ-S10-50：视频页调 open_flow_agent 用的工作流键必须是 FLOWS 里有的 video_prompt（原 'final' 抛未知入口）。"""
        import desktop_media_pages
        import workflow_settings
        key = desktop_media_pages.VIDEO_PROMPT_FLOW
        self.assertEqual('video_prompt', key)
        self.assertIn(key, workflow_settings.FLOWS)
        self.assertIn('qwen', workflow_settings.defaults(key)['profiles'])
        with self.assertRaises(ValueError):
            workflow_settings.defaults('final')

    def test_req_s10_50_valid_reply_writes_json_with_serializer(self):
        """REQ-S10-50：合格回复由 JSON 序列化器写入 video_prompts/<镜头>.json，请求带 SKILL 与镜头上下文。"""
        adapter = FakeAdapter(good('他说："带伞吧"\n然后离开。'))
        result = self.run_batch(adapter)
        self.assertTrue(result['ok'], result)
        record = json.loads(self.output.read_text(encoding='utf-8'))
        self.assertEqual(['shot_id', 'source_signature', 'video_prompt'], sorted(record))
        self.assertEqual('他说："带伞吧"\n然后离开。', record['video_prompt'])
        self.assertIn('SKILL正文', adapter.calls[0]['system'])
        self.assertIn('林夏抬头', adapter.calls[0]['messages'][0]['content'])

    def test_req_s10_50_bad_replies_retry_once_then_write_nothing(self):
        """REQ-S10-50：镜头号不符／校验值不符／空提示词／超长／非 JSON，两次都不合格不落盘并给出原因。"""
        cases = ((good().replace('"SH001"', '"SH009"'), '镜头'),
                 (good().replace(SIG, 'b' * 64), '校验值'),
                 (good('   '), '空'),
                 (good('字' * 1501), '1500'),
                 ('没有 JSON', 'JSON'))
        for bad, word in cases:
            with self.subTest(word=word):
                adapter = FakeAdapter(bad, bad)
                result = self.run_batch(adapter)
                self.assertFalse(result['ok'])
                self.assertIn(word, result['error'])
                self.assertEqual(2, len(adapter.calls))
                self.assertIn(word, adapter.calls[1]['messages'][-1]['content'])
                self.assertFalse(self.output.exists())

    def test_req_s10_50_retry_recovers_and_backs_up_previous_result(self):
        """REQ-S10-50：重试后合格可落盘；已有结果先备份到 历史版本。"""
        self.assertTrue(self.run_batch(FakeAdapter('乱写', good()))['ok'])
        self.assertTrue(self.run_batch(FakeAdapter(good('第二版提示词')))['ok'])
        history = list((self.output.parent / '历史版本').glob('*.json'))
        self.assertEqual(1, len(history))
        self.assertIn('林夏在雨中', history[0].read_text(encoding='utf-8'))

    def test_req_s10_50_stop_interrupts_request_and_writes_nothing(self):
        """REQ-S10-50：强制停止中断请求，不落盘。"""
        import video_prompt_direct_api as api
        from workflow_process_registry import cancel_project_requests
        started = threading.Event()
        job = api.launch(self.project, self.config, 'SKILL正文', direct=self.direct(),
                         adapter=FakeAdapter(block=started), record={'name': 'x'}, report=self.messages.append)
        self.assertTrue(started.wait(5))
        self.assertEqual(1, cancel_project_requests(self.project))
        job.join(5)
        self.assertFalse(job.is_alive())
        self.assertTrue(job.results[0]['stopped'])
        self.assertFalse(self.output.exists())

    def test_req_s10_50_shares_executor_skeleton_with_storyboard(self):
        """REQ-S10-50：模型判定与作业骨架与初步分镜是同一份，不另立第二套。"""
        import storyboard_direct_api as sb
        import video_prompt_direct_api as api
        self.assertIs(api.direct_model, sb.direct_model)
        self.assertTrue(issubclass(api.Job, sb.Job))

    def test_req_s10_50_build_routes_api_model_to_direct(self):
        """REQ-S10-50：build() 对 video_prompt 带直连载荷且选了 API 模型时走直连，不进入 Qwen 排队。"""
        import desktop_idea_chat as chat
        pool = {'deepseek-v4-pro': {'name': 'deepseek-v4-pro', 'call_mode': 'API'}}
        host = SimpleNamespace(root=self.project, worker=None)
        direct = {'context': self.context, 'output': self.output, 'draft': ''}
        request = chat._FlowAgentRequest('video_prompt', '提示词渲染', 'p', None, None, None, False, False, False, direct)
        with patch('model_pool.pool', return_value=pool), patch('workflow_settings.current', return_value=self.config), \
                patch.object(chat, '_run_video_prompt_direct') as run:
            chat._FlowAgentLaunch(host, request).build()
        run.assert_called_once()
        self.assertEqual(direct, run.call_args.args[2])

    def test_req_s10_50_build_does_not_route_without_payload_or_for_other_engines(self):
        """REQ-S10-50：没有直连载荷、或引擎不是 qwen 时不分流。"""
        import desktop_idea_chat as chat
        pool = {'deepseek-v4-pro': {'name': 'deepseek-v4-pro', 'call_mode': 'API'}}
        direct = {'context': self.context, 'output': self.output, 'draft': ''}
        for payload, config in ((None, self.config), (direct, dict(self.config, engine='codex'))):
            host = SimpleNamespace(root=self.project, worker=None, projects=SimpleNamespace(info={'projects': []}),
                                   async_=lambda *_a, **_k: None)
            request = chat._FlowAgentRequest('video_prompt', '提示词渲染', 'p', None, None, None, False, False, False, payload)
            with patch('model_pool.pool', return_value=pool), patch('workflow_settings.current', return_value=config), \
                    patch.object(chat, '_run_video_prompt_direct') as run:
                try:
                    chat._FlowAgentLaunch(host, request).build()
                except Exception:  # 非直连路径后续依赖真实宿主，这里只关心没有分流
                    pass
                run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
