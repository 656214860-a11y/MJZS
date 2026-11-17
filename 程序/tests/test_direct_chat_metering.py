# -*- coding: utf-8 -*-
"""R2178 J11：edit_habits／skill_notes 直连 API 文本模型也要过计量入口（授权 → 发送 → 结算）。"""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from orchestrator import edit_habits
from orchestrator import skill_notes
from infra.pet_llm import request_ledger_path


def _budget_zero(root):
    (Path(root) / 'cost_profile.json').write_text(json.dumps({'budget_amount': '0', 'price_table': {
        'currency': 'CNY', 'version': 'fixture', 'model_rates': {
            'm': {'prompt_tokens': '0.01', 'completion_tokens': '0.01'}}}}), encoding='utf-8')


def _patched(module, adapter):
    choice = SimpleNamespace(ok=True, record={'model': 'm'}, model='m')
    return (mock.patch.object(module.model_pool, 'pool', return_value=[]),
            mock.patch.object(module.model_router, 'resolve_agent_model', return_value=choice),
            mock.patch.object(module.model_pool, 'desktop_engine', return_value=False),
            mock.patch.object(module.model_router, 'PoolAdapter', return_value=adapter))


class DirectChatMeteringTests(unittest.TestCase):
    def _run(self, module, build, call, adapter, root):
        patches = _patched(module, adapter)
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        return getattr(module, build)(*call)

    def test_edit_habits_summary_is_refused_by_the_money_budget_before_sending(self):
        with tempfile.TemporaryDirectory() as td:
            _budget_zero(td)
            adapter = mock.Mock()
            summarize = self._run(edit_habits, '_api_summarizer', ('p', td), adapter, td)
            with self.assertRaises(ValueError):
                summarize([{'before': 'a', 'after': 'b'}])
            adapter.chat.assert_not_called()

    def test_edit_habits_summary_settles_the_reported_usage(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = mock.Mock()
            adapter.chat.return_value = {'ok': True, 'text': '[]', 'data': {'usage': {
                'prompt_tokens': 10, 'completion_tokens': 2}}}
            summarize = self._run(edit_habits, '_api_summarizer', ('p', td), adapter, td)
            self.assertEqual(summarize([{'before': 'a', 'after': 'b'}]), '[]')
            self.assertTrue(request_ledger_path(td).exists())

    def test_skill_notes_translation_is_refused_by_the_money_budget_before_sending(self):
        with tempfile.TemporaryDirectory() as td:
            _budget_zero(td)
            adapter = mock.Mock()
            translate = self._run(skill_notes, '_api_translator', ('p', td), adapter, td)
            with self.assertRaises(ValueError):
                translate(['hello'])
            adapter.chat.assert_not_called()


if __name__ == '__main__':
    unittest.main()
