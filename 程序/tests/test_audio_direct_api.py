# -*- coding: utf-8 -*-
"""音频脚本选 API 模型时的直连执行器（REQ-S11-50）：不经 Qwen、合格才发布、同一执行器骨架、
强制停止能中断。模型请求全部用假适配器，不调用真实 API。"""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

GOOD_SCRIPT = ('# 配音脚本\n\n## SH001 开场\n- 林夏｜平静，语速中｜今天会下雨吗\n'
               '- 老周｜低沉，语速慢｜带伞吧\n')
GOOD_SRT = ('1\n00:00:00,500 --> 00:00:02,500\n今天会下雨吗\n\n'
            '2\n00:00:03,000 --> 00:00:05,000\n带伞吧\n')


def reply(script=GOOD_SCRIPT, srt=GOOD_SRT):
    return '=====配音脚本.md=====\n%s\n=====SRT=====\n%s\n' % (script, srt)


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


class AudioDirectTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.project = Path(temp.name).resolve() / '项目'
        self.source = self.project / '07分镜定稿' / 'EP001_分镜.json'
        self.source.parent.mkdir(parents=True)
        self.source.write_text(json.dumps({'episode_id': 'EP001', 'title': '雨夜', 'duration': 6, 'shots': [{
            'id': 'SH001', 'title': '开场', 'duration': 6, 'dialogue': [
                {'speaker': '林夏', 'text': '今天会下雨吗'}, {'speaker': '老周', 'text': '带伞吧'}]}]},
            ensure_ascii=False), encoding='utf-8')
        self.config = {'engine': 'qwen', 'model': 'deepseek-v4-pro', 'program': ''}
        self.messages = []

    def run_batch(self, adapter):
        from orchestrator import audio_direct_api as api
        return api.run_batch(self.project, self.config, 'SKILL正文', source=self.source, adapter=adapter,
                             record={'name': 'deepseek-v4-pro'}, report=self.messages.append)

    def outputs(self):
        return sorted(p for p in self.project.rglob('*') if p.is_file() and p != self.source)

    def test_req_s11_50_valid_reply_is_published_without_qwen(self):
        """REQ-S11-50：合格回复发布配音脚本与 SRT，请求里带对白与 SKILL，不经 Qwen。"""
        adapter = FakeAdapter(reply())
        result = self.run_batch(adapter)
        self.assertTrue(result['ok'], result)
        names = [p.name for p in self.outputs()]
        self.assertIn('配音脚本.md', names)
        self.assertEqual(1, sum(n.endswith('.srt') for n in names))
        self.assertEqual(1, len(adapter.calls))
        self.assertIn('SKILL正文', adapter.calls[0]['system'])
        self.assertIn('带伞吧', adapter.calls[0]['messages'][0]['content'])
        srt = next(p for p in self.outputs() if p.suffix == '.srt')
        self.assertEqual('字幕', srt.parent.name)
        self.assertEqual('音频', next(p for p in self.outputs() if p.name == '配音脚本.md').parent.name)

    def test_req_s11_50_bad_timeline_retries_once_then_writes_nothing(self):
        """REQ-S11-50：时间轴重叠两次都不合格 → 不落盘并给出原因。"""
        bad = GOOD_SRT.replace('00:00:03,000', '00:00:02,000')
        adapter = FakeAdapter(reply(srt=bad), reply(srt=bad))
        result = self.run_batch(adapter)
        self.assertFalse(result['ok'])
        self.assertIn('重叠', result['error'])
        self.assertEqual(2, len(adapter.calls))
        self.assertIn('重叠', adapter.calls[1]['messages'][-1]['content'])
        self.assertEqual([], self.outputs())

    def test_req_s11_50_missing_dialogue_is_rejected(self):
        """REQ-S11-50：SRT 漏掉分镜里的一句对白 → 不合格。"""
        srt = '1\n00:00:00,500 --> 00:00:02,500\n今天会下雨吗\n'
        result = self.run_batch(FakeAdapter(reply(srt=srt), reply(srt=srt)))
        self.assertFalse(result['ok'])
        self.assertIn('带伞吧', result['error'])
        self.assertEqual([], self.outputs())

    def test_req_s11_50_numbering_and_overrun_and_missing_sections(self):
        """REQ-S11-50：编号不连续、越过总时长、缺少分隔段都不合格。"""
        from orchestrator import audio_direct_api as api
        episode = json.loads(self.source.read_text(encoding='utf-8'))
        skip = GOOD_SRT.replace('2\n00:00:03', '3\n00:00:03')
        over = GOOD_SRT.replace('00:00:05,000', '00:00:09,000')
        for text, word in ((reply(srt=skip), '编号'), (reply(srt=over), '总时长'), ('只有文字', '分隔')):
            with self.assertRaises(ValueError) as caught:
                api.validate_reply(text, episode)
            self.assertIn(word, str(caught.exception))

    def test_req_s11_50_retry_can_recover_and_backs_up_old_script(self):
        """REQ-S11-50：重试后合格可发布；已有配音脚本先备份到历史版本。"""
        self.assertTrue(self.run_batch(FakeAdapter('乱写', reply()))['ok'])
        self.assertTrue(self.run_batch(FakeAdapter(reply(script=GOOD_SCRIPT + '- 备注｜新版\n')))['ok'])
        history = [p for p in self.outputs() if p.parent.name == '历史版本']
        self.assertEqual(1, len(history))
        self.assertIn('配音脚本', history[0].name)

    def test_req_s11_50_stop_interrupts_request_and_writes_nothing(self):
        """REQ-S11-50：强制停止中断请求，不落盘。"""
        from orchestrator import audio_direct_api as api
        from infra.workflow_process_registry import cancel_project_requests
        started = threading.Event()
        adapter = FakeAdapter(block=started)
        job = api.launch(self.project, self.config, 'SKILL正文', source=self.source, adapter=adapter,
                         record={'name': 'x'}, report=self.messages.append)
        self.assertTrue(started.wait(5))
        self.assertEqual(1, cancel_project_requests(self.project))
        job.join(5)
        self.assertFalse(job.is_alive())
        self.assertTrue(job.results[0]['stopped'])
        self.assertEqual([], self.outputs())

    def test_req_s11_50_shares_executor_skeleton_with_storyboard(self):
        """REQ-S11-50：直连判定与作业骨架与初步分镜是同一份，不另立第二套。"""
        from orchestrator import audio_direct_api as api
        from orchestrator import storyboard_direct_api as sb
        self.assertIs(api.direct_model, sb.direct_model)
        self.assertTrue(issubclass(api.Job, sb.Job))
        pool = {'deepseek-v4-pro': {'name': 'deepseek-v4-pro', 'call_mode': 'API'}}
        with patch('model_pool.pool', return_value=pool):
            self.assertEqual('deepseek-v4-pro', api.direct_model(self.config)[0])
            self.assertIsNone(api.direct_model({'engine': 'codex', 'model': 'deepseek-v4-pro'}))


if __name__ == '__main__':
    unittest.main()
