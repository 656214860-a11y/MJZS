# -*- coding: utf-8 -*-
"""domain.voice_ai：语音识别文本的模板化 AI 优化（chat 注入式，纯逻辑）。"""
import unittest

import domain.voice_ai as voice_ai
import voice_ai as voice_ai_flat


class FakeChat:
    """记录调用并回放预置结果的 chat 替身。"""
    def __init__(self, result=None, error=None):
        self.result, self.error = result, error
        self.calls = []

    def __call__(self, messages, options=None, model='', system=''):
        self.calls.append({'messages': messages, 'options': options,
                           'model': model, 'system': system})
        if self.error is not None:
            raise self.error
        return self.result


class BuildRequestTests(unittest.TestCase):
    def test_templates_produce_system_prompts(self):
        for template in ('fix', 'polish', 'translate'):
            messages, options, system, problem = voice_ai.build_request('你好', {'template': template})
            self.assertEqual(problem, '')
            self.assertEqual(messages, [{'role': 'user', 'content': '你好'}])
            self.assertTrue(system, template)
            self.assertEqual(options['max_tokens'], 2048)

    def test_custom_template_uses_prompt_and_rejects_empty(self):
        messages, _options, system, problem = voice_ai.build_request(
            '文本', {'template': 'custom', 'prompt': '把它改成诗'})
        self.assertIn('把它改成诗', system)
        self.assertEqual(problem, '')
        _m, _o, _s, problem = voice_ai.build_request('文本', {'template': 'custom', 'prompt': '  '})
        self.assertIn('自定义提示词为空', problem)

    def test_unknown_template_rejected(self):
        _m, _o, _s, problem = voice_ai.build_request('文本', {'template': 'warp'})
        self.assertIn('模板不认识', problem)


class CleanResultTests(unittest.TestCase):
    def test_strips_and_removes_fences(self):
        self.assertEqual(voice_ai.clean_result('  你好。  '), '你好。')
        self.assertEqual(voice_ai.clean_result('```\n修正后文本\n```'), '修正后文本')
        self.assertEqual(voice_ai.clean_result(''), '')
        self.assertEqual(voice_ai.clean_result(None), '')


class OptimizeTextTests(unittest.TestCase):
    def test_success_returns_cleaned_text(self):
        chat = FakeChat({'ok': True, 'text': '```\n他说子进程好。\n```'})
        result = voice_ai.optimize_text('他说子进成好', chat=chat, model='m1',
                                        config={'template': 'fix'})
        self.assertTrue(result['ok'])
        self.assertEqual(result['text'], '他说子进程好。')
        call = chat.calls[0]
        self.assertEqual(call['model'], 'm1')
        self.assertIn('语音识别文本校对', call['system'])
        self.assertEqual(call['messages'][0]['content'], '他说子进成好')

    def test_failures_keep_source_and_give_reason(self):
        cases = [
            (FakeChat({'ok': False, 'reason': '余额不足'}), '余额不足'),
            (FakeChat({'ok': True, 'text': '   '}), '返回为空'),
            (FakeChat({'ok': True, 'text': 'x' * 20001}), '过长'),
            (FakeChat(None, error=RuntimeError('boom')), '调用失败'),
            (FakeChat('not-a-dict'), '格式不正确'),
        ]
        for chat, expected in cases:
            result = voice_ai.optimize_text('原文', chat=chat, config={'template': 'fix'})
            self.assertFalse(result['ok'], expected)
            self.assertEqual(result['text'], '原文', '失败保留原文')
            if expected:
                self.assertIn(expected, result['reason'])

    def test_empty_input_and_bad_template(self):
        chat = FakeChat({'ok': True, 'text': 'x'})
        result = voice_ai.optimize_text('  ', chat=chat)
        self.assertFalse(result['ok'])
        self.assertEqual(chat.calls, [], '空文本不发请求')
        result = voice_ai.optimize_text('文本', chat=chat, config={'template': 'warp'})
        self.assertFalse(result['ok'])
        self.assertEqual(chat.calls, [], '坏模板不发请求')


class FacadeTests(unittest.TestCase):
    def test_flat_facade_is_domain_entity(self):
        self.assertIs(voice_ai_flat, voice_ai)


if __name__ == '__main__':
    unittest.main()
