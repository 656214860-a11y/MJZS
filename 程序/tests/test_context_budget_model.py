# -*- coding: utf-8 -*-
"""上下文预算：模型窗口相关预估与分项报告回归（O36）。"""
import unittest
from unittest.mock import Mock, patch

from contract import workflow_context_budget as budget
import writing_api


class PresetContextLengthTests(unittest.TestCase):
    def test_model_names_never_supply_unknown_windows(self):
        for model_id in ('deepseek-v4.1-flash-1017', 'gemini-3.5-flash',
                         'qwen3', 'claude-sonnet-4', 'gpt-4o'):
            with self.subTest(model_id=model_id):
                self.assertEqual(budget.preset_context_length(model_id), '')

    def test_case_and_family_boundaries_do_not_supply_windows(self):
        for model_id in ('deepseek', 'DeEpSeEk-V4', 'DEEPSEEK4',
                         'deepseek_v4', 'deepseek.v4', 'deepseek:latest'):
            with self.subTest(model_id=model_id):
                self.assertEqual(budget.preset_context_length(model_id), '')

    def test_empty_unknown_and_similar_words_have_no_preset(self):
        for model_id in (None, '', ' ', 'unknown-model', 'OpenAI 兼容',
                         'deepseeker', 'geminist', 'qwenish', 'claudette',
                         'gptastic', 'vendor/deepseek-v4'):
            with self.subTest(model_id=model_id):
                self.assertEqual(budget.preset_context_length(model_id), '')


class TokenEstimateTests(unittest.TestCase):
    def test_estimate_covers_chinese_english_code_and_image_payloads(self):
        self.assertEqual(budget.estimate_tokens(''), 0)
        chinese = budget.estimate_tokens('中文')
        english = budget.estimate_tokens('abcd')
        self.assertEqual(chinese, 4)
        self.assertEqual(english, 2)
        self.assertGreater(chinese, english)
        code = 'def f():\n    return 1\n' * 10
        # 代码主要是 ASCII，密度低于 1 token/字符。
        self.assertLess(budget.estimate_tokens(code), len(code))
        image = 'data:image/png;base64,' + 'A' * 3000
        self.assertLess(budget.estimate_tokens(image), 3000 // 2)

    def test_estimate_is_monotonic(self):
        self.assertLessEqual(budget.estimate_tokens('abc'), budget.estimate_tokens('abcabc'))


class SectionReportTests(unittest.TestCase):
    def test_report_splits_sections_and_names_dominant(self):
        sections = budget.budget_sections(system='规则', stage='任务' * 100, history='历史' * 500)
        report = budget.context_budget_report(sections, context_limit=8000,
                                              output_reserved=2048, stage='剧本对话')
        self.assertEqual(set(report['sections']), {'system', 'stage', 'history'})
        self.assertEqual(report['dominant'][0]['name'], 'history')
        self.assertEqual(report['context_limit'], 8000)
        self.assertEqual(report['output_reserved'], 2048)
        self.assertEqual(report['projected_tokens'],
                         report['input_tokens'] + 2048 + report['safety_margin'])

    def test_large_model_keeps_output_room(self):
        sections = budget.budget_sections(history='中' * 1000)
        report = budget.context_budget_report(sections, context_limit=128000, output_reserved=4096)
        self.assertFalse(report['exceeded'])
        self.assertGreater(report['token_remaining'], 0)

    def test_small_model_flags_exceeded(self):
        sections = budget.budget_sections(history='中' * 3000)
        report = budget.context_budget_report(sections, context_limit=8192, output_reserved=4096)
        self.assertTrue(report['exceeded'])
        self.assertLess(report['token_remaining'], 0)

    def test_unknown_section_name_rejected(self):
        with self.assertRaises(ValueError):
            budget.budget_sections(screenshot='x')


class PrepareContextTests(unittest.TestCase):
    def test_report_attaches_fingerprint_for_same_snapshot(self):
        prompt, info = budget.prepare_request_context('任务正文' * 50, '初步分镜',
                                                      'stage_summary', report=True)
        self.assertEqual(info['fingerprint'], budget.text_fingerprint(prompt))
        self.assertEqual(info['limit'], budget.REQUEST_CONTEXT_MAX_CHARS)
        self.assertEqual(info['remaining'], budget.REQUEST_CONTEXT_MAX_CHARS - len(prompt))
        self.assertIn('stage', info['sections'])

    def test_success_returns_identical_text(self):
        source = '正文' * 10
        prompt, _info = budget.prepare_request_context(source, '初步分镜', report=True)
        self.assertEqual(prompt, source)

    def test_model_window_overflow_raises_with_advice_without_truncating(self):
        sections = budget.budget_sections(history='中' * 5000)
        with self.assertRaises(ValueError) as caught:
            budget.prepare_request_context('短正文', '初步分镜', sections=sections,
                                           context_limit=8192, output_reserved=4096)
        message = str(caught.exception)
        self.assertIn('超过模型上下文', message)
        self.assertIn('未截断', message)
        self.assertIn('主要占用', message)


class WritingAdapterBudgetTests(unittest.TestCase):
    def test_unknown_window_rejects_before_adapter_and_metering(self):
        raw = Mock()
        adapter = writing_api.WritingRequestAdapter(
            raw, {'context_length': '', 'rpm': 10}, 'gpt-4o', project='synthetic-project')
        with patch('infra.model_pool.wait_for_rpm') as rpm, \
                patch('infra.pet_llm.RequestLedger') as ledger:
            result = adapter.chat([{'role': 'user', 'content': '短正文'}],
                                  options={'max_tokens': 100}, system='规则')
        rpm.assert_not_called()
        ledger.assert_not_called()
        self.assertFalse(result['ok'])
        self.assertEqual(result['reason'], 'context_window_unknown')
        self.assertIn('context_length', result['error'])
        self.assertIn('供应商', result['error'])
        raw.chat.assert_not_called()
        self.assertEqual(adapter.request_usage['calls'], 0)

    def test_small_model_rejects_with_sections_and_dominant(self):
        raw = Mock()
        adapter = writing_api.WritingRequestAdapter(raw, {'context_length': 8000}, 'small')
        result = adapter.chat([{'role': 'user', 'content': '中' * 2200}],
                              options={'max_tokens': 4096}, system='规则')
        self.assertFalse(result['ok'])
        self.assertEqual(result['reason'], 'context_budget_exceeded')
        raw.chat.assert_not_called()
        self.assertEqual(result['context_budget']['output_reserved'], 4096)
        self.assertIn('history', result['context_budget']['sections'])
        self.assertEqual(result['context_budget']['dominant'][0]['name'], 'history')
        self.assertTrue(result['context_budget']['fingerprint'])

    def test_large_model_keeps_output_room(self):
        raw = Mock()
        raw.chat.return_value = {'ok': True, 'text': '正文', 'usage': {}, 'data': {}}
        adapter = writing_api.WritingRequestAdapter(raw, {'context_length': 128000}, 'large')
        result = adapter.chat([{'role': 'user', 'content': '中文' * 200}],
                              options={'max_tokens': 4096}, system='规则')
        self.assertTrue(result['ok'])
        self.assertLess(result['context_budget']['projected_tokens'],
                        result['context_budget']['context_limit'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
