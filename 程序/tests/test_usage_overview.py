"""项目用量总览：只读汇总已落盘的模型调用事件，缺用量不当 0。"""
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import model_diagnostics
import pet_llm
import usage_overview as uo


def call(folder, model, stage, usage, ok=True, day='2026-10-14'):
    stamp = datetime.strptime(day + ' 10:00:00', '%Y-%m-%d %H:%M:%S')
    result = {'ok': ok, 'status': 200 if ok else 500, 'model': model, 'usage': usage, 'text': 'SECRET 正文'}
    return model_diagnostics.record(folder, result, {'stage': stage}, at=stamp)


class UsageOverviewTests(unittest.TestCase):
    def test_cost_per_minute_keeps_unknown_overheads_separate(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = pet_llm.RequestLedger(folder)
            ledger.settle('fixture', kind='seconds', amount=10); ledger.save()
            table = {'rates': {'seconds': 0.2}, 'version': 'fixture', 'currency': 'CNY'}
            cost = uo.cost_per_minute(folder, 60, table)
            self.assertEqual(cost['known_per_minute'], 2)
            self.assertIsNone(cost['total_per_minute'])
            cost = uo.cost_per_minute(folder, 30, table, dict(gpu=0, storage=1, bandwidth=0, human=2))
            self.assertEqual(cost['total_per_minute'], 10)
            with self.assertRaises(ValueError): uo.cost_per_minute(folder, float('inf'), table)

    def test_nonfinite_event_usage_is_unknown(self):
        bucket = uo._blank()
        uo._add(bucket, {'ok': False, 'usage': {'total_tokens': float('inf')}})
        self.assertEqual(bucket['unknown_usage'], 1)
        self.assertEqual(bucket['total_tokens'], 0)

    def test_summarize_groups_by_model_stage_and_day_without_inventing_zero(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            logs = root / 'logs'
            call(logs, 'm-a', 'script', {'prompt_tokens': 100, 'completion_tokens': 50, 'cached_tokens': 20})
            call(logs, 'm-a', 'script', {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 99}, day='2026-10-15')
            call(logs, 'm-b', 'storyboard', {}, ok=False)               # 没上报用量
            call(root, 'm-b', 'pet', {'total_tokens': 7})                 # 三虎事件落在项目根
            (logs / 'model_diagnostics' / 'broken.json').write_text('{bad', encoding='utf-8')
            summary = uo.summarize(root, {'tokens': {'label': 'Token（每天）', 'used': 5, 'limit': 10}})
            total = summary['total']
            self.assertEqual((total['calls'], total['ok'], total['failed'], total['unknown_usage']), (4, 3, 1, 1))
            self.assertEqual(total['prompt_tokens'], 110)
            self.assertEqual(total['total_tokens'], 150 + 99 + 7)       # 无 total 时用输入＋输出
            self.assertEqual(summary['by_model']['m-a']['calls'], 2)
            self.assertEqual(summary['by_model']['m-b']['unknown_usage'], 1)
            self.assertEqual(summary['by_stage']['script']['total_tokens'], 249)
            self.assertEqual(list(summary['by_day']), ['2026-10-14', '2026-10-15'])
            self.assertEqual(summary['skipped_files'], 1)
            text = uo.report_text(summary)
            self.assertIn('未上报用量（不计为 0）', text)
            self.assertIn('损坏', text)
            self.assertNotIn('SECRET', text)

    def test_empty_project_and_request_ledger_section(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertIn('还没有可汇总', uo.report_text(uo.summarize(root)))
            ledger = pet_llm.RequestLedger(root)
            ledger.reserve('v1', 'seconds', 5)
            ledger.settle('v1', kind='seconds', amount=5.0)
            ledger.save()
            summary = uo.summarize(root)
            self.assertEqual(summary['total']['calls'], 0)
            text = uo.report_text(summary)
            self.assertIn('请求台账', text)
            self.assertIn('seconds：已结算 5', text)


if __name__ == '__main__':
    unittest.main()
