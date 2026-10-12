# -*- coding: utf-8 -*-
"""O37：「测试连接成功」与「完整工作流支持」分开。

一次最小请求只证明连通与鉴权，不证明长文本、流式、中断、工具或阶段文档可用。
这里把探测结果拆成连通性／协议兼容／模型标识／能力声明／完整任务五个维度分别核，
并覆盖验收点名的几种情况：伪兼容协议、仅 reasoning 无正文、流式中断、超长输出、模型切换。
一律不联网：传输函数都是假的，密钥用临时目录里的 .env。
"""
import tempfile
import unittest
from pathlib import Path

import model_pool

ABSENT_KEY = 'CODEX_TEST_KEY_ABSENT'


def env_dir(root, keys=('DEEPSEEK_API_KEY',)):
    """造一个程序目录：.env 里放指定的几个密钥名（值只要形状合法）。"""
    root = Path(root)
    (root / '.env').write_text(''.join('%s=sk-test-%d\n' % (name, index)
                                       for index, name in enumerate(keys)), encoding='utf-8')
    return root


def dimensions(result):
    return {entry['key']: entry for entry in result['checks']}


def item(model='m', **extra):
    value = {'model': model, 'base_url': 'https://x.test/v1', 'key_env': 'DEEPSEEK_API_KEY'}
    value.update(extra)
    return model_pool.record(value)


def reply(model='m', text='pong', finish='stop', **message):
    body = {'content': text}
    body.update(message)
    return {'ok': True, 'status': 200,
            'data': {'model': model, 'choices': [{'finish_reason': finish, 'message': body}]}}


class LayeredProbeTests(unittest.TestCase):
    def test_a_minimal_probe_separates_connectivity_from_full_workflow(self):
        with tempfile.TemporaryDirectory() as td:
            env_dir(td)
            result = model_pool.probe(item(), lambda *args: reply(), td)
        dims = dimensions(result)
        self.assertEqual(list(dims), [key for key, _label in model_pool.PROBE_DIMENSIONS])
        self.assertTrue(dims['connectivity']['ok'])
        self.assertTrue(dims['protocol']['ok'])
        self.assertTrue(dims['model_id']['ok'])
        self.assertIsNone(dims['full_task']['ok'], '最小请求证不了完整任务')
        self.assertEqual(result['full_task'], model_pool.PROBE_FULL_TASK_STATE)
        self.assertIn('完整任务：未验证', result['summary'])

    def test_a_pseudo_compatible_protocol_is_flagged_despite_http_200(self):
        with tempfile.TemporaryDirectory() as td:
            env_dir(td)
            result = model_pool.probe(item(), lambda *args: {'ok': True, 'status': 200,
                                                             'data': {'error': {'code': 1}}}, td)
        protocol = dimensions(result)['protocol']
        self.assertFalse(protocol['ok'], '200 但没有该协议的字段，不能算协议兼容')
        self.assertIn('伪兼容', protocol['detail'])

    def test_a_reasoning_only_reply_has_no_usable_body(self):
        with tempfile.TemporaryDirectory() as td:
            env_dir(td)
            answer = reply(text='', reasoning_content='想了一长串')
            record = item(capabilities='reasoning')
            result = model_pool.probe(record, lambda *args: answer, td)
            verdict = model_pool.verify_sample(record, lambda *args: answer, td)
        capabilities = dimensions(result)['capabilities']
        self.assertFalse(capabilities['ok'])
        self.assertIn('仅返回推理', capabilities['detail'])
        self.assertFalse(verdict['ok'], '只有推理、没有正文，完整任务不算通过')
        self.assertFalse(dimensions(verdict)['full_task']['ok'])

    def test_a_truncated_answer_fails_the_full_task_check(self):
        with tempfile.TemporaryDirectory() as td:
            env_dir(td)
            verdict = model_pool.verify_sample(
                item(), lambda *args: reply(text='半截正文', finish='length'), td)
        full = dimensions(verdict)['full_task']
        self.assertFalse(full['ok'])
        self.assertIn('截断', full['detail'])

    def test_an_interrupted_stream_is_reported_not_hidden(self):
        with tempfile.TemporaryDirectory() as td:
            env_dir(td)
            verdict = model_pool.verify_sample(
                item(), lambda *args: {'ok': False, 'status': 0, 'error': '请求已取消'}, td)
        full = dimensions(verdict)['full_task']
        self.assertFalse(verdict['ok'])
        self.assertFalse(full['ok'])
        self.assertIn('中断', full['detail'])

    def test_a_switched_model_on_the_server_side_is_caught(self):
        with tempfile.TemporaryDirectory() as td:
            env_dir(td)
            result = model_pool.probe(item('deepseek-v4-pro'),
                                      lambda *args: reply(model='gpt-4o-mini'), td)
        model_id = dimensions(result)['model_id']
        self.assertFalse(model_id['ok'])
        self.assertIn('deepseek-v4-pro', model_id['detail'])
        self.assertIn('gpt-4o-mini', model_id['detail'])

    def test_a_matching_server_model_passes(self):
        with tempfile.TemporaryDirectory() as td:
            env_dir(td)
            result = model_pool.probe(item('deepseek-v4-pro'),
                                      lambda *args: reply(model='deepseek-v4-pro'), td)
        self.assertTrue(dimensions(result)['model_id']['ok'])

    def test_a_dead_endpoint_never_claims_protocol_or_full_task(self):
        with tempfile.TemporaryDirectory() as td:
            env_dir(td)
            result = model_pool.probe(item(), lambda *args: {'ok': False, 'status': 401,
                                                             'error': 'HTTP 401：unauthorized'}, td)
        dims = dimensions(result)
        self.assertFalse(dims['connectivity']['ok'])
        self.assertIsNone(dims['protocol']['ok'])
        self.assertIsNone(dims['full_task']['ok'])

    def test_the_anthropic_protocol_shape_counts_as_compatible(self):
        with tempfile.TemporaryDirectory() as td:
            env_dir(td)
            payload = {'model': 'claude-opus-5.5', 'type': 'message', 'stop_reason': 'end_turn',
                       'content': [{'type': 'text', 'text': '收到'}]}
            result = model_pool.probe(item('claude-opus-5.5', wire_api='messages'),
                                      lambda *args: {'ok': True, 'status': 200, 'data': payload}, td)
        dims = dimensions(result)
        self.assertTrue(dims['protocol']['ok'])
        self.assertEqual(result['signals']['response_model'], 'claude-opus-5.5')


class ConfigVersionTests(unittest.TestCase):
    def test_config_version_names_the_effective_request_identity(self):
        version = model_pool.config_version({'model': 'claude-opus-5.5', 'wire_api': 'messages',
                                             'base_url': 'https://api.b.ai/v1', 'key_env': 'B_KEY'})
        self.assertIn('messages', version)
        self.assertIn('https://api.b.ai/v1', version)
        self.assertIn('claude-opus-5.5', version)
        self.assertIn('B_KEY', version)


class SmallSampleVerifyTests(unittest.TestCase):
    def test_verify_sample_sends_one_small_real_request(self):
        seen = {}

        def send(url, payload, head, timeout):
            seen.update(url=url, payload=payload)
            return reply(text='收到')

        with tempfile.TemporaryDirectory() as td:
            env_dir(td)
            record = item()
            outcome = model_pool.verify_sample(record, send, td)
        self.assertTrue(outcome['ok'])
        self.assertEqual(outcome['content_length'], 2)
        self.assertEqual(seen['payload']['max_tokens'], model_pool.VERIFY_TOKENS)
        self.assertEqual(seen['payload']['messages'][0]['content'], model_pool.SAMPLE_PROMPT)
        self.assertEqual(outcome['config_version'], model_pool.config_version(record))

    def test_verify_sample_without_a_key_never_calls_out(self):
        calls = []
        with tempfile.TemporaryDirectory() as td:
            outcome = model_pool.verify_sample(model_pool.record(
                {'model': 'm', 'base_url': 'https://x.test/v1', 'key_env': ABSENT_KEY}),
                lambda *args: calls.append(args), td)
        self.assertFalse(outcome['ok'])
        self.assertEqual(calls, [])
        self.assertIn(ABSENT_KEY, outcome['error'])


class HealthLedgerTests(unittest.TestCase):
    def test_the_latest_full_task_is_recorded_with_its_config_version(self):
        with tempfile.TemporaryDirectory() as td:
            entry = model_pool.record_health(
                item('deepseek-v4-flash'),
                {'at': '2026-10-12T09:00:00', 'ok': True, 'config_version': 'chat · x · m · k',
                 'content_length': 12, 'finish_reason': 'stop', 'error': ''}, td)
            self.assertEqual(model_pool.health_of(item('deepseek-v4-flash'), program=td), entry)
            self.assertTrue(model_pool.health(program=td)['deepseek-v4-flash']['ok'])
        self.assertEqual(entry['config_version'], 'chat · x · m · k')

    def test_a_second_model_does_not_overwrite_the_first(self):
        with tempfile.TemporaryDirectory() as td:
            model_pool.record_health(item('a'), {'ok': True, 'at': '1'}, td)
            model_pool.record_health(item('b'), {'ok': False, 'at': '2'}, td)
            table = model_pool.health(program=td)
        self.assertEqual(sorted(table), ['a', 'b'])


class BreakdownCopyTests(unittest.TestCase):
    def test_the_breakdown_lists_all_five_dimensions_and_the_version(self):
        import pet_models_ui
        with tempfile.TemporaryDirectory() as td:
            result = model_pool.probe(item(), lambda *args: {'ok': True, 'status': 200,
                                                             'data': {}}, td)
            text = pet_models_ui.probe_breakdown(result, item(), td)
        for label in ('连通性', '协议兼容', '模型标识', '能力声明', '完整任务'):
            self.assertIn(label, text)
        self.assertIn('配置版本', text)
        self.assertIn('最近完整任务', text)
        self.assertIn('未验证', text)

    def test_the_success_sentence_still_reports_the_latency(self):
        import pet_models_ui

        class Pet:
            program = ''

        with tempfile.TemporaryDirectory() as td:
            env_dir(td)
            Pet.program = td
            Pet.probe_transport = lambda *args: reply()
            said = pet_models_ui.probe_line(item(), Pet)
        self.assertIn('连接成功，延迟', said)
        self.assertIn('ms', said)


if __name__ == '__main__':
    unittest.main()
