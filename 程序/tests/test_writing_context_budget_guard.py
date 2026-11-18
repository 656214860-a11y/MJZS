"""REQ-S01-31: final API budget uses one snapshot before authorization/network."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import writing_api
import workflow_settings
from contract.workflow_context_budget import REQUEST_CONTEXT_MAX_CHARS
from infra.model_router import PoolAdapter


class WritingContextBudgetGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        from infra.pet_llm import RequestLedger
        self.ledger = RequestLedger(self.root)
        self.ledger.authorize_model, self.ledger.settle_model = Mock(), Mock()
        self.raw = Mock(wire_api='chat.completions')
        self.raw.chat.return_value = self.raw.stream.return_value = {'ok': True, 'text': 'fixture'}
        for target, kwargs in (
                ('writing_api.stage_model_value.reasoning_options', {'return_value': {}}),
                ('pet_llm.RequestLedger', {'return_value': self.ledger}),
                ('writing_api.model_pool.pool', {'side_effect': AssertionError('must not reopen model pool')}),
                ('writing_api.model_pool.wait_for_rpm', {})):
            mocked = patch(target, **kwargs)
            value = mocked.start()
            self.addCleanup(mocked.stop)
            if target.endswith('wait_for_rpm'):
                self.rpm = value

    def adapter(self, record=None, model='deepseek-fixture', settings=None):
        with patch('writing_api.PoolAdapter', return_value=self.raw):
            return writing_api._writing_adapter(record or {}, model, project=self.root, settings=settings)

    def assert_refused(self, result, *, reason='context_budget_exceeded'):
        self.assertFalse(result['ok'])
        self.assertEqual(result['reason'], reason)
        self.assertEqual(result['status'], 0)
        self.assertEqual(result['text'], '')
        self.assertEqual(result['usage'], {})
        self.assertEqual(result['request_usage']['calls'], 0)
        self.raw.chat.assert_not_called()
        self.raw.stream.assert_not_called()
        self.ledger.authorize_model.assert_not_called()
        self.rpm.assert_not_called()

    def test_deepseek_explicit_window_is_in_final_report_and_reaches_real_adapter_once(self):
        transport = Mock(return_value={'ok': True, 'status': 200, 'data': {
            'choices': [{'message': {'content': 'controlled reply'}, 'finish_reason': 'stop'}]}})
        record = {'context_length': 128000, 'model': 'deepseek-fixture', 'base_url': 'https://example.invalid',
                  'wire_api': 'chat.completions', 'path': '/v1/chat/completions'}
        raw = PoolAdapter(record, 'deepseek-fixture', transport=transport, key='synthetic-test-only')
        adapter = writing_api.WritingRequestAdapter(raw, record, 'deepseek-fixture', project=self.root)
        result = adapter.chat([{'role': 'user', 'content': '任务'}], {'max_tokens': 100})
        self.assertTrue(result['ok'])
        self.assertEqual(result['text'], 'controlled reply')
        self.assertEqual(result['context_budget']['context_limit'], 128000)
        self.assertEqual(result['request_usage']['calls'], 1)
        transport.assert_called_once()
        self.ledger.authorize_model.assert_called_once()

    def test_explicit_small_window_is_not_overridden_by_preset_or_saved_budget(self):
        saved = {'skill_budget': {'model': 'deepseek-fixture', 'context_length': 128000, 'source': 'preset'}}
        result = self.adapter({'context_length': 1200, 'rpm': 5}, settings=saved).chat(
            [{'role': 'user', 'content': '任务' * 200}], {'max_tokens': 100})
        self.assert_refused(result)
        self.assertEqual(result['context_budget']['context_limit'], 1200)

    def test_matching_snapshot_is_reused_and_frozen_for_chat_and_stream(self):
        settings = {'skill_budget': {'model': 'custom-model', 'context_length': 8000, 'source': 'explicit'}}
        original = copy.deepcopy(settings)
        adapter = self.adapter(model='custom-model', settings=settings)
        settings['skill_budget']['context_length'] = 100
        for method in ('chat', 'stream'):
            result = getattr(adapter, method)([{'role': 'user', 'content': '任务'}], {'max_tokens': 100})
            self.assertTrue(result['ok'])
            self.assertEqual(result['context_budget']['context_limit'], original['skill_budget']['context_length'])
        self.raw.chat.assert_called_once()
        self.raw.stream.assert_called_once()

    def test_mismatched_snapshot_does_not_grant_unknown_model_a_window(self):
        settings = {'skill_budget': {'model': 'other-model', 'context_length': 128000, 'source': 'explicit'}}
        result = self.adapter({'rpm': 5}, model='custom-model', settings=settings).chat(
            [{'role': 'user', 'content': '任务'}], {'max_tokens': 100})
        self.assert_refused(result, reason='context_window_unknown')
        self.assertIn('custom-model', result['error'])
        self.assertIn('模型管理', result['error'])
        self.assertIn('补填', result['error'])

    def test_mismatched_snapshot_never_guesses_current_model_window(self):
        settings = {'skill_budget': {'model': 'other-model', 'context_length': 1000, 'source': 'explicit'}}
        result = self.adapter(settings=settings).chat([{'role': 'user', 'content': '任务'}], {'max_tokens': 100})
        self.assert_refused(result, reason='context_window_unknown')

    def test_unknown_window_refused_for_chat_and_stream_before_metering_or_rpm(self):
        for method in ('chat', 'stream'):
            with self.subTest(method=method):
                result = getattr(self.adapter({'rpm': 5}, model='custom-model'), method)(
                    [{'role': 'user', 'content': '任务'}], {'max_tokens': 100})
                self.assert_refused(result, reason='context_window_unknown')
                self.assertIn('custom-model', result['error'])

    def test_legacy_preset_snapshot_does_not_confirm_unknown_window(self):
        settings = {'skill_budget': {'model': 'deepseek-fixture', 'context_length': 128000, 'source': 'preset'}}
        result = self.adapter({'rpm': 5}, settings=settings).chat(
            [{'role': 'user', 'content': '任务'}], {'max_tokens': 100})
        self.assert_refused(result, reason='context_window_unknown')

    def test_model_override_cannot_reuse_other_snapshot_window(self):
        for method in ('chat', 'stream'):
            for override in ('qwen-fixture', 'custom-model'):
                with self.subTest(method=method, override=override):
                    result = getattr(self.adapter({'rpm': 5}, model='claude-fixture'), method)(
                        [{'role': 'user', 'content': '任务'}], {'max_tokens': 100}, model=override)
                    self.assert_refused(result, reason='model_snapshot_mismatch')
                    self.assertIn(override, result['error'])
                    self.assertIn('claude-fixture', result['error'])

    def test_empty_and_matching_model_use_chosen_at_real_send_boundary(self):
        for method in ('chat', 'stream'):
            for model in ('', 'deepseek-fixture'):
                with self.subTest(method=method, model=model):
                    result = getattr(self.adapter({'context_length': 128000}), method)(
                        [{'role': 'user', 'content': '任务'}], {'max_tokens': 100}, model=model)
                    self.assertTrue(result['ok'])
                    self.assertEqual(getattr(self.raw, method).call_args.kwargs['model'], 'deepseek-fixture')

    def test_each_complete_request_component_can_refuse_chat_and_stream(self):
        cases = {
            'task': ('', [{'role': 'user', 'content': '中' * 800}], {'max_tokens': 100}),
            'system': ('中' * 800, [{'role': 'user', 'content': '任务'}], {'max_tokens': 100}),
            'history': ('', [{'role': 'assistant', 'content': '中' * 800},
                            {'role': 'user', 'content': '任务'}], {'max_tokens': 100}),
            'tools': ('', [{'role': 'user', 'content': '任务'}],
                      {'max_tokens': 100, 'tools': [{'name': 'fixture', 'description': '中' * 800}]}),
            'output': ('', [{'role': 'user', 'content': '任务'}], {'max_tokens': 1600}),
        }
        for method in ('chat', 'stream'):
            for component, (system, messages, options) in cases.items():
                with self.subTest(method=method, component=component):
                    result = getattr(self.adapter({'context_length': 2000, 'rpm': 5}), method)(
                        messages, options, system=system)
                    self.assert_refused(result)
                    budget = result['context_budget']
                    self.assertGreater(budget['projected_tokens'], budget['context_limit'])
                    self.assertGreater(budget['safety_margin'], 0)

    def test_missing_max_tokens_counts_actual_adapter_default(self):
        result = self.adapter({'context_length': 1200}).chat([{'role': 'user', 'content': '任务'}])
        self.assert_refused(result)
        self.assertEqual(result['context_budget']['output_reserved'], 1024)

    def test_record_window_snapshot_does_not_change_after_first_round(self):
        record = {'context_length': 8000}
        adapter = writing_api.WritingRequestAdapter(self.raw, record, 'custom-model', project=self.root)
        record['context_length'] = 100
        result = adapter.chat([{'role': 'user', 'content': '任务'}], {'max_tokens': 100})
        self.assertTrue(result['ok'])
        self.assertEqual(result['context_budget']['context_limit'], 8000)

    def test_tool_round_rechecks_added_results_before_second_transport(self):
        self.raw.chat.return_value = {'ok': True, 'text': '', 'data': {'content': [
            {'type': 'tool_use', 'id': 'fixture-use', 'name': 'read_file', 'input': {'path': 'fixture.md'}}]}}
        adapter = self.adapter({'context_length': 14000}, model='claude-fixture')
        with patch('writing_api.writing_tools.execute', return_value={'text': '中' * 4000}), \
                patch('writing_api._record_model_diagnostic'):
            result = writing_api._reply_with_project_tools(adapter, 'claude-fixture', '规则', '任务', self.root)
        self.assertFalse(result['ok'])
        self.assertEqual(result['reason'], 'context_budget_exceeded')
        self.assertEqual(result['request_usage']['calls'], 1)
        self.raw.chat.assert_called_once()
        self.ledger.authorize_model.assert_called_once()
        self.assertGreater(result['context_budget']['projected_tokens'], 14000)

    def test_character_hard_guard_still_rejects_before_transport(self):
        result = self.adapter({'context_length': 1000000}).chat(
            [{'role': 'user', 'content': 'a' * (REQUEST_CONTEXT_MAX_CHARS + 1)}], {'max_tokens': 100})
        self.assert_refused(result)

    def test_freeze_character_error_names_skill_section_without_raising_cap(self):
        skill = self.root / 'SKILL.md'
        skill.write_text('---\nname: fixture\ndescription: test\n---\n' + 'a' * (REQUEST_CONTEXT_MAX_CHARS + 1), encoding='utf-8')
        config = {'engine': 'desktop-app', 'model': '', 'stage': 'writing', 'stage_skills': [],
                  'skills': [str(skill)], 'parameters': {'reference_depth': -1}}
        with patch('orchestrator.skill_inline._skill_roots_for_path', return_value=(self.root,)), \
                patch('domain.writing_quality.enabled', return_value=False):
            with self.assertRaises(ValueError) as raised:
                workflow_settings.freeze_skills(config, model_snapshot={})
        self.assertIn('SKILL/阶段指令', str(raised.exception))
        self.assertNotIn('主要占用：阶段文档/任务说明', str(raised.exception))


if __name__ == '__main__':
    unittest.main()
