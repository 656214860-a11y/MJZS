"""项目用量总览：只读汇总已落盘的模型调用事件，缺用量不当 0。"""
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from infra import model_diagnostics
import infra.pet_llm as pet_llm
import usage_overview as uo


def call(folder, model, stage, usage, ok=True, day='2026-10-14'):
    stamp = datetime.strptime(day + ' 10:00:00', '%Y-%m-%d %H:%M:%S')
    result = {'ok': ok, 'status': 200 if ok else 500, 'model': model, 'usage': usage, 'text': 'SECRET 正文'}
    return model_diagnostics.record(folder, result, {'stage': stage}, at=stamp)


class UsageOverviewTests(unittest.TestCase):
    def test_unpriced_comfy_import_reconcile_and_source_change(self):
        from agent.core import save
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / 'workflows/comfy_custom.json'
            job = {'state': 'queued', 'workflow': {'1': {'class_type': 'CustomCloudNode'}}}
            save(path, job)
            ledger = pet_llm.RequestLedger(folder)
            self.assertEqual(ledger.import_legacy_video_costs(include_unpriced=True), 1)
            self.assertEqual(ledger.import_legacy_video_costs(include_unpriced=True), 0)
            row = ledger.entries[0]
            self.assertEqual(row['kind'], 'requests')
            receipt = root / 'receipt.txt'; receipt.write_text('offline receipt fixture')
            with self.assertRaisesRegex(ValueError, '进行中'):
                ledger.reconcile_cost(row['id'], 'requests', '2', 'CNY', receipt, 'tester')
            job['state'] = 'downloaded'; save(path, job)
            original = path.read_bytes()
            ledger.import_legacy_video_costs(include_unpriced=True)
            ledger.reconcile_cost(row['id'], 'requests', '2', 'CNY', receipt, 'tester')
            table = {'rates': {}, 'version': 'fixture', 'currency': 'CNY'}
            overheads = dict(gpu=0, storage=0, bandwidth=0)
            cost = uo.cost_per_minute(folder, 60, table, overheads)
            self.assertEqual(cost['total_per_minute'], 2)
            self.assertEqual(path.read_bytes(), original)
            job['files'] = ['changed.png']; save(path, job)
            self.assertFalse(uo.cost_per_minute(folder, 60, table, overheads)['complete'])
            with self.assertRaisesRegex(ValueError, '来源已变化'):
                ledger.check_legacy_video_costs('')
            ledger.import_legacy_video_costs(include_unpriced=True)
            self.assertIsNone(ledger.entries[0]['budget_cost'])
            self.assertEqual(len(ledger.entries[0]['cost_reconciliations']), 1)
            self.assertFalse(uo.cost_per_minute(folder, 60, table, overheads)['complete'])

    def test_comfy_jobs_without_ledger_cannot_claim_complete_cost(self):
        from agent.core import save
        with tempfile.TemporaryDirectory() as folder:
            ledger = pet_llm.RequestLedger(folder)
            ledger.settle('fixture', kind='seconds', amount=10); ledger.save()
            table = {'rates': {'seconds': 0.2}, 'version': 'fixture', 'currency': 'CNY'}
            overheads = dict(gpu=0, storage=0, bandwidth=0, human=0)
            path = Path(folder) / 'workflows' / 'comfy_local.json'
            for state in ('submitting', 'queued', 'unknown', 'failed', 'downloaded'):
                save(path, {'state': state, 'workflow': {}, 'cost_request_id': 'missing'})
                cost = uo.cost_per_minute(folder, 60, table, overheads)
                self.assertEqual(cost['known_per_minute'], 2)
                self.assertIsNone(cost['total_per_minute'])
                self.assertIsNone(cost['including_human_per_minute'])
                self.assertEqual(cost['untracked_comfy'], ['comfy_local.json'])
            self.assertIn('Comfy 费用覆盖缺项', uo.report_text(uo.summarize(folder)))
            path.write_text('{broken', encoding='utf-8')
            self.assertFalse(uo.cost_per_minute(folder, 60, table, overheads)['complete'])
            save(path, {'cost_request_id': 'fixture'})
            self.assertTrue(uo.cost_per_minute(folder, 60, table, overheads)['complete'])
            self.assertEqual(len(pet_llm.RequestLedger(folder).load().entries), 1)

    def test_labor_time_and_full_cost_survive_profile_read_without_assuming_unknown_zero(self):
        from agent.core import save
        with tempfile.TemporaryDirectory() as folder:
            ledger = pet_llm.RequestLedger(folder)
            ledger.settle('fixture', kind='seconds', amount=10); ledger.save()
            config = {'duration_seconds': 30, 'human_minutes': 15,
                'price_table': {'rates': {'seconds': 0.2}, 'version': 'fixture', 'currency': 'CNY'},
                'overheads': {'gpu': 0, 'storage': 1, 'bandwidth': 0, 'human': 2}}
            profile = Path(folder) / 'cost_profile.json'
            save(profile, config)
            summary = uo.summarize(folder)
            cost = summary['cost']
            self.assertEqual(cost['total_per_minute'], 6)
            self.assertEqual(cost['including_human_per_minute'], 10)
            self.assertEqual(cost['human_minutes_per_finished_minute'], 30)
            self.assertIn('人工编辑耗时：15 分钟', uo.report_text(summary))
            self.assertIn('含人工全成本：10 CNY', uo.report_text(summary))
            for value in (None, -1, True, float('inf')):
                config['human_minutes'] = value
                save(profile, config)
                result = uo.summarize(folder)['cost']
                self.assertIsNone(result['human_minutes'])
                self.assertEqual(result['including_human_per_minute'], 10)
            config['human_minutes'] = 0
            config['overheads']['human'] = None
            save(profile, config)
            result = uo.summarize(folder)['cost']
            self.assertEqual(result['human_minutes'], 0)
            self.assertIsNone(result['including_human_per_minute'])
            config['overheads']['human'] = 0
            config['overheads']['storage'] = None
            save(profile, config)
            self.assertIsNone(uo.summarize(folder)['cost']['including_human_per_minute'])

    def test_cost_per_minute_keeps_unknown_overheads_separate(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = pet_llm.RequestLedger(folder)
            ledger.settle('fixture', kind='seconds', amount=10); ledger.save()
            table = {'rates': {'seconds': 0.2}, 'version': 'fixture', 'currency': 'CNY'}
            cost = uo.cost_per_minute(folder, 60, table)
            self.assertEqual(cost['known_per_minute'], 2)
            self.assertIsNone(cost['total_per_minute'])
            cost = uo.cost_per_minute(folder, 30, table, dict(gpu=0, storage=1, bandwidth=0, human=2))
            self.assertEqual(cost['total_per_minute'], 6)
            self.assertEqual(cost['human_per_minute'], 4)
            cost = uo.cost_per_minute(folder, 30, table, dict(gpu=0, storage=1, bandwidth=0))
            self.assertTrue(cost['complete'])
            self.assertEqual(cost['total_per_minute'], 6)
            self.assertIsNone(cost['human_per_minute'])
            summary = uo.summarize(folder)
            summary['cost'] = cost
            self.assertIn('人工编辑费用：未知', uo.report_text(summary))
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

    def write_video_fixture(self, root, versions, *, adopted_version=None, adopted_sha=''):
        from agent.core import save
        save(root / 'data' / 'state.json', {'shots': {'S01': versions}})
        if adopted_version is not None:
            save(root / '10视频生成' / 'output' / 'video_manifest.json', {
                'stage': 'video', 'shots': [{'id': 'S01', 'adopted_version': adopted_version,
                                             'sha256': adopted_sha, 'file': 'adopted.mp4'}]})
        save(root / 'cost_profile.json', {
            'duration_seconds': 30,
            'price_table': {'version': 'fixture', 'currency': 'CNY', 'model_rates': {
                'video-m': {'videos': '0.5', 'seconds': '0.2'},
                'free-m': {'videos': '0', 'seconds': '0'}}},
            'overheads': {'gpu': 0, 'storage': 0, 'bandwidth': 0}})

    def test_video_attempt_costs_link_retry_billing_adopted_version_and_total(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.write_video_fixture(root, [
                {'version': 1, 'state': 'failed', 'seconds': 5, 'task_id': 'remote-1',
                 'money_request_id': 'video:r1', 'retry_reason': 'initial', 'charged': True},
                {'version': 2, 'state': 'downloaded', 'seconds': 5, 'task_id': 'remote-2',
                 'money_request_id': 'video:r2', 'retry_reason': 'explicit_after_failed',
                 'sha256': 'sha-v2', 'file': 'data/S01/v002/S01.mp4', 'charged': True}],
                adopted_version=2, adopted_sha='sha-v2')
            ledger = pet_llm.RequestLedger(root)
            ledger.authorize_units('video:r1', 'video-m', 'video', 'videos', {'seconds': 5})
            ledger.settle_units('video:r1')
            ledger.authorize_units('video:r2', 'video-m', 'video', 'videos', {'seconds': 5})
            ledger.settle_units('video:r2', amount=1)
            summary = uo.summarize(root)
            rows = {row['version']: row for row in summary['video_attempts']['rows']}
            self.assertEqual(set(rows), {1, 2})
            self.assertFalse(rows[1]['adopted'])
            self.assertTrue(rows[2]['adopted'])
            self.assertEqual(rows[1]['cost']['bill_state'], 'unknown')
            self.assertEqual(rows[1]['cost']['amount'], '1')
            self.assertEqual(rows[2]['cost']['bill_state'], 'estimated')
            self.assertEqual(rows[2]['cost']['amount'], '1')
            totals = summary['video_attempts']['totals']['by_currency']['CNY']
            self.assertEqual(totals['estimated'], '1')
            self.assertEqual(totals['held_or_unknown'], '1')
            self.assertEqual(totals['known_total'], '1')
            text = uo.report_text(summary)
            self.assertIn('视频逐尝试费用', text)
            self.assertIn('S01 v1：failed；未采用；费用 1 CNY', text)
            self.assertIn('S01 v2：downloaded；采用；费用 1 CNY', text)
            self.assertIn('供应商用量或结果未知', text)
            self.assertIn('冻结费率估算', text)
            self.assertIn('重试原因 explicit_after_failed', text)
            self.assertIn('设置→预算→费用核对', text)

    def test_video_attempt_costs_distinguish_missing_evidence_and_confirmed_zero(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.write_video_fixture(root, [
                {'version': 1, 'state': 'failed', 'seconds': 5,
                 'money_request_id': 'video:missing-rate', 'retry_reason': 'initial'},
                {'version': 2, 'state': 'downloaded', 'seconds': 5,
                 'money_request_id': 'video:unreconciled', 'retry_reason': 'explicit_after_failed'},
                {'version': 3, 'state': 'downloaded', 'seconds': 5,
                 'money_request_id': 'video:zero', 'retry_reason': 'explicit_after_revision'},
                {'version': 4, 'state': 'failed', 'seconds': 5,
                 'money_request_id': 'video:no-ledger', 'retry_reason': 'explicit_after_failed'}],
                adopted_version=3)
            ledger = pet_llm.RequestLedger(root)
            ledger.authorize_units('video:missing-rate', 'missing-m', 'video', 'videos', {'seconds': 5})
            ledger.settle_units('video:missing-rate', amount=1)
            ledger.authorize_units('video:unreconciled', 'video-m', 'video', 'videos', {'seconds': 5})
            ledger.settle_units('video:unreconciled', amount=1)
            ledger.authorize_units('video:zero', 'free-m', 'video', 'videos', {'seconds': 5})
            ledger.settle_units('video:zero', amount=1)
            receipt = root / 'receipt.txt'
            receipt.write_text('offline zero invoice fixture', encoding='utf-8')
            ledger.reconcile_cost('video:zero', 'videos', '0', 'CNY', receipt, 'tester')
            rows = {row['version']: row for row in uo.summarize(root)['video_attempts']['rows']}
            self.assertEqual(rows[1]['cost']['bill_state'], 'missing_rate')
            self.assertIsNone(rows[1]['cost']['amount'])
            self.assertEqual(rows[2]['cost']['bill_state'], 'estimated')
            self.assertEqual(rows[3]['cost']['bill_state'], 'reconciled')
            self.assertEqual(rows[3]['cost']['amount'], '0')
            self.assertIn('确认零费用', rows[3]['cost']['label'])
            self.assertEqual(rows[4]['cost']['bill_state'], 'missing')
            self.assertTrue(rows[4]['cost']['manual_check_required'])
            text = uo.report_text(uo.summarize(root))
            self.assertIn('缺费率或未计价', text)
            self.assertIn('缺供应商账单核对', text)
            self.assertIn('请求号在请求台账中缺失', text)
            self.assertIn('未知不记为 0，确认无费用须核对为 0', text)
            config = root / 'cost_profile.json'
            data = uo.read_json(config)
            del data['duration_seconds']
            from agent.core import save
            save(config, data)
            summary = uo.summarize(root)
            self.assertIn('缺交付时长', summary['cost_error'])
            self.assertIn('缺交付时长', uo.report_text(summary))

    def test_duplicate_remote_task_is_not_counted_on_the_duplicate_attempt(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.write_video_fixture(root, [
                {'version': 1, 'state': 'downloaded', 'seconds': 5, 'money_request_id': 'video:r1'},
                {'version': 2, 'state': 'downloaded', 'seconds': 5, 'money_request_id': 'video:r2'}],
                adopted_version=2)
            ledger = pet_llm.RequestLedger(root)
            ledger.authorize_units('video:r1', 'video-m', 'video', 'videos', {'seconds': 5})
            ledger.settle_units('video:r1', amount=1, remote_task_id='same-remote')
            ledger.authorize_units('video:r2', 'video-m', 'video', 'videos', {'seconds': 5})
            ledger.settle_units('video:r2', amount=1, remote_task_id='same-remote')
            result = uo.video_attempt_costs(root, pet_llm.RequestLedger(root).load())
            rows = {row['version']: row for row in result['rows']}
            self.assertEqual(rows[1]['cost']['bill_state'], 'estimated')
            self.assertEqual(rows[1]['cost']['amount'], '1')
            self.assertEqual(rows[2]['cost']['bill_state'], 'duplicate')
            self.assertIsNone(rows[2]['cost']['amount'])
            self.assertFalse(rows[2]['cost']['manual_check_required'])
            self.assertIn('video:r1', rows[2]['cost']['label'])
            totals = result['totals']['by_currency']['CNY']
            self.assertEqual(totals['known_total'], '1')
            self.assertEqual(totals['held_or_unknown'], '0')
            text = uo.report_text(uo.summarize(root))
            self.assertIn('不重复计列', text)
            self.assertIn('同一远端任务已并入请求 video:r1', text)
            orphan = {'id': 'video:orphan', 'state': 'duplicate', 'remote_task_id': 'missing-owner',
                      'money_state': 'reserved', 'budget_cost': '1', 'currency': 'CNY'}
            cost = uo._attempt_cost_fact([orphan])
            self.assertEqual(cost['bill_state'], 'duplicate')
            self.assertTrue(cost['manual_check_required'])
            self.assertIn('费用未知', cost['label'])

    def test_same_shot_version_in_multiple_workspaces_does_not_share_legacy_rows_or_adoption(self):
        from agent.core import save
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.write_video_fixture(root, [
                {'version': 1, 'state': 'downloaded', 'seconds': 5, 'local_request': 'root-old'}],
                adopted_version=1)
            save(root / 'cloud_video' / 'session' / 'data' / 'state.json', {'shots': {'S01': [
                {'version': 1, 'state': 'downloaded', 'seconds': 5, 'local_request': 'cloud-old'}]}})
            ledger = pet_llm.RequestLedger(root)
            row = ledger.settle('video:S01:v1:seconds', kind='seconds', amount=5)
            row.update(budget_cost='9', currency='CNY', money_state='estimated')
            ledger.save()
            workspace_ledger = pet_llm.RequestLedger(root / 'cloud_video' / 'session')
            workspace_ledger.settle('video:S01:v1:seconds', kind='seconds', amount=5)
            workspace_ledger.save()
            result = uo.video_attempt_costs(root, pet_llm.RequestLedger(root).load())
            rows = {row['workspace']: row for row in result['rows']}
            self.assertEqual(rows['.']['cost']['bill_state'], 'estimated')
            self.assertEqual(rows['.']['cost']['amount'], '9')
            self.assertEqual(rows['cloud_video/session']['cost']['bill_state'], 'missing_rate')
            self.assertIsNone(rows['cloud_video/session']['cost']['amount'])
            self.assertIsNone(rows['.']['adopted'])
            self.assertIsNone(rows['cloud_video/session']['adopted'])
            self.assertTrue(any('多个视频工作集' in item for item in result['errors']))

    def test_legacy_video_cost_group_appears_on_the_matching_attempt(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.write_video_fixture(root, [
                {'version': 1, 'state': 'downloaded', 'seconds': 5, 'local_request': 'old-1'}],
                adopted_version=1)
            ledger = pet_llm.RequestLedger(root)
            ledger.settle('video:S01:v1:seconds', kind='seconds', amount=5)
            ledger.save()
            ledger = pet_llm.RequestLedger(root)
            self.assertEqual(ledger.import_legacy_video_costs(include_unpriced=True), 1)
            group = next(row for row in ledger.entries if row.get('cost_only'))
            receipt = root / 'legacy-receipt.txt'
            receipt.write_text('offline legacy invoice fixture', encoding='utf-8')
            ledger.reconcile_cost(group['id'], group['kind'], '2', 'CNY', receipt, 'tester')
            result = uo.video_attempt_costs(root, pet_llm.RequestLedger(root).load())
            row = result['rows'][0]
            self.assertEqual(row['request_ids'], [group['id']])
            self.assertEqual(row['cost']['bill_state'], 'reconciled')
            self.assertEqual(row['cost']['amount'], '2')
            self.assertEqual(result['totals']['by_currency']['CNY']['known_total'], '2')

    def test_confirmed_edit_bundle_overrides_video_stage_manifest_for_adopted_version(self):
        from agent.core import save
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.write_video_fixture(root, [
                {'version': 1, 'state': 'failed', 'seconds': 5, 'money_request_id': 'video:r1'},
                {'version': 2, 'state': 'downloaded', 'seconds': 5, 'sha256': 'sha-v2',
                 'money_request_id': 'video:r2'}], adopted_version=1)
            output = root / '13质检交付' / '导出成片' / 'fixture' / 'master.mp4'
            output.parent.mkdir(parents=True)
            output.write_bytes(b'master')
            save(output.parent / 'edit_bundle.json', {
                'master': 'master.mp4', 'master_sha256': 'master-sha',
                'manifest': [{'shot': 'S01', 'version': 2, 'sha256': 'sha-v2'}]})
            evidence = {'duration_seconds': 30,
                        'outputs': [{'path': '13质检交付/导出成片/fixture/master.mp4', 'sha256': 'master-sha'}]}
            result = uo.video_attempt_costs(root, pet_llm.RequestLedger(root), evidence)
            self.assertEqual(result['adoption_basis'], 'confirmed_edit_bundle')
            rows = {row['version']: row for row in result['rows']}
            self.assertFalse(rows[1]['adopted'])
            self.assertTrue(rows[2]['adopted'])


if __name__ == '__main__':
    unittest.main()


class ScenarioEstimateTests(unittest.TestCase):
    """O12：不付费估算表——有费率才算金额，缺任何一项都保持未知，不补零。"""

    TABLE = {"currency": "CNY", "version": "test", "model_rates": {
        "img-m": {"images": "0.2"}, "vid-m": {"seconds": "0.5"}}}

    def scenario(self, stages=True):
        return {"shots": 60, "candidates": 2, "attempts": 1, "stages": [
            {"name": "首帧", "model": "img-m", "kind": "images", "quantities": {"images": 120}},
            {"name": "视频", "model": "vid-m", "kind": "videos", "quantities": {"seconds": 300}},
        ] if stages else []}

    def test_configured_rates_multiply_quantities_by_candidates_and_attempts(self):
        result = uo.estimate_scenario(self.scenario(), self.TABLE)
        self.assertTrue(result["complete"])
        self.assertAlmostEqual(result["amount"], 120 * 0.2 + 300 * 0.5)
        self.assertEqual([row["amount"] for row in result["stages"]], [24.0, 150.0])
        self.assertEqual(result["candidates"], 2)

    def test_one_missing_rate_keeps_the_whole_amount_unknown(self):
        table = {**self.TABLE, "model_rates": {"img-m": {"images": "0.2"}}}
        result = uo.estimate_scenario(self.scenario(), table)
        self.assertFalse(result["complete"])
        self.assertIsNone(result["amount"])
        self.assertEqual(result["unknown_stages"],
                         [{"stage": "视频", "model": "vid-m", "kind": "videos"}])
        self.assertEqual(result["stages"][0]["amount"], 24.0)

    def test_price_table_without_version_or_currency_is_unknown(self):
        table = {"model_rates": {"img-m": {"images": "0.2"}}}
        result = uo.estimate_scenario(self.scenario(), table)
        self.assertIsNone(result["amount"])
        self.assertIsNone(result["table_version"])
        self.assertEqual(len(result["unknown_stages"]), 2)

    def test_unknown_unit_and_empty_scenario_are_not_guessed(self):
        with self.assertRaises(ValueError):
            uo.estimate_scenario({"stages": [{"model": "m", "kind": "frames", "quantities": {}}]}, self.TABLE)
        empty = uo.estimate_scenario({"shots": 0}, self.TABLE)
        self.assertFalse(empty["complete"])
        self.assertIsNone(empty["amount"])
        self.assertIsNone(empty["candidates"])

