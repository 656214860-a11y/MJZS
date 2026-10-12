# -*- coding: utf-8 -*-
"""上下文预算：模型窗口相关预估与分项报告回归（O36）。"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import hollmwood_roles
import workflow_context_budget as budget
import writing_api
from agent.core import save_text
from model_router import ModelAdapter


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


class HollmwoodBudgetTests(unittest.TestCase):
    def test_role_budget_uses_model_window_and_reserves_output(self):
        with tempfile.TemporaryDirectory() as folder:
            hollmwood_roles._ensure_context_budget('writer', '规则', '剧本' * 100, folder, 1,
                                                   publish_log=save_text, context_limit=200000,
                                                   output_reserved=8192)
            with self.assertRaises(hollmwood_roles.RoleExecutionError) as caught:
                hollmwood_roles._ensure_context_budget('writer', '规则', '剧本' * 100, folder, 2,
                                                       publish_log=save_text, context_limit=2000,
                                                       output_reserved=8192)
            self.assertIn('上下文过长', str(caught.exception))
            self.assertIn('模型上下文', str(caught.exception))

    def test_four_roles_all_reserve_output_room(self):
        with tempfile.TemporaryDirectory() as folder:
            for step, role in enumerate(hollmwood_roles.ROLE_ORDER, start=1):
                hollmwood_roles._ensure_context_budget(role, '规则', '简报' * 50, folder, step,
                                                       publish_log=save_text, context_limit=64000,
                                                       output_reserved=8192)

    def test_ask_reads_record_context_length_before_calling_model(self):
        program = Path(hollmwood_roles.__file__).resolve().parent
        class NeverCalled(ModelAdapter):
            def __init__(self):
                super().__init__(program=program)
                self.record = {'context_length': 4000}
                self.calls = 0
            def chat(self, *args, **kwargs):
                self.calls += 1
                return {'ok': True, 'text': '不应调用', 'error': ''}

        with tempfile.TemporaryDirectory() as folder:
            adapter = NeverCalled()
            with self.assertRaises(hollmwood_roles.RoleExecutionError):
                hollmwood_roles._ask(adapter, 'writer-model', 'writer', '规则',
                                     '剧本' * 100, folder, 1, None, publish_log=save_text)
            self.assertEqual(adapter.calls, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
