import tempfile
import unittest
from pathlib import Path

from agent.core import save
import task_center_service


class RuntimeProjectionTests(unittest.TestCase):
    def test_lifecycle_persists_project_and_run_for_restart(self):
        from desktop_automation_service import BackgroundTaskLifecycle
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            history = root/'history.json'
            life = BackgroundTaskLifecycle(history)
            life.submit(1, project=root)
            row = BackgroundTaskLifecycle(history).unresolved_records()[0]
            self.assertEqual(row['project'], str(root.resolve()))
            self.assertEqual(row['run_id'], life.execution_control(1).run_id)

    def test_execution_identity_is_shared_only_within_one_execution(self):
        import platform_tools
        control = platform_tools.ExecutionControl()
        with platform_tools.execution_scope(control):
            first = platform_tools.execution_metadata('video', 'S1', attempt='request-1')
            second = platform_tools.execution_metadata('video', 'S2', attempt='request-2')
        third = platform_tools.execution_metadata('video', 'S1', attempt='request-3')
        self.assertEqual(first['run_id'], second['run_id'])
        self.assertNotEqual(first['run_id'], third['run_id'])
        self.assertEqual(first['attempt_id'], 'request-1')

    def test_reopen_correlates_authorities_without_writing_or_resubmitting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save(root/'config.json', {'project_id': 'project-one'})
            save(root/'workflows/资产批量记录.json', {'CHAR_001': {
                'state': 'submitting', 'record': 'workflows/receipt.json'}})
            save(root/'workflows/receipt.json', {'prompt_id': 'remote-image', 'state': 'queued'})
            save(root/'cloud_video/session/data/state.json', {'shots': {'S001': [
                {'version': 1, 'state': 'unknown', 'local_request': 'attempt-one'},
                {'version': 2, 'state': 'downloaded', 'local_request': 'attempt-two', 'file': 'v2.mp4'}]}})
            before = {str(p): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            one = task_center_service.project_snapshot(root)
            two = task_center_service.project_snapshot(root)
            self.assertEqual(one, two)
            self.assertEqual(len(one['tasks']), 3)
            self.assertTrue(all(r['project_id'] == 'project-one' for r in one['tasks']))
            image = next(r for r in one['tasks'] if r['task_id'] == 'CHAR_001')
            self.assertEqual(image['remote_task_id'], 'remote-image')
            self.assertEqual(image['state'], 'reconcile')
            self.assertIn('资产', image['recovery'])
            video = [r for r in one['tasks'] if r['task_id'] == 'S001']
            self.assertEqual([r['attempt_id'] for r in video], ['attempt-one', 'attempt-two'])
            self.assertNotEqual(video[0]['state'], 'failed')
            self.assertEqual(video[1]['state'], 'recorded_ready')
            self.assertIsNone(video[0]['run_id'])
            self.assertEqual(before, {str(p): p.read_bytes() for p in root.rglob('*') if p.is_file()})

    def test_corrupt_authority_is_visible_and_does_not_hide_other_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save(root/'config.json', {'project_id': 'p'})
            ledger = root/'workflows/资产批量记录.json'
            ledger.parent.mkdir(parents=True)
            ledger.write_text('{broken', encoding='utf-8')
            save(root/'data/state.json', {'shots': {'S2': [{'state': 'queued', 'task_id': 'remote'}]}})
            data = task_center_service.project_snapshot(root)
            self.assertTrue(data['errors'])
            self.assertEqual(data['tasks'][0]['remote_task_id'], 'remote')
            text = '\n'.join(task_center_service.format_lines({'project_runtime': data}))
            self.assertIn('读取失败', text)
            self.assertIn('S2', text)

    def test_shot_query_links_attempt_timing_reason_and_verified_cost(self):
        import hashlib
        from pet_llm import request_ledger_path
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); bill=root/'bill.txt';bill.write_text('receipt')
            save(root/'data/state.json', {'shots': {'S1': [
                {'version':1,'state':'failed','error_code':'provider_error','money_request_id':'m1',
                 'created':10,'submitted_at':12,'running_observed_at':15,'succeeded_observed_at':20,
                 'download_started_at':21,'download_completed_at':25,'finished_at':26,
                 'execution':{'run_id':'r1','attempt_id':'a1'}},
                {'version':2,'state':'queued','task_id':'remote2','retry_reason':'explicit_after_failed',
                 'execution':{'run_id':'r2','attempt_id':'a2'}}], 'S2':[{'state':'unknown'}]}})
            save(request_ledger_path(root),{'entries':[{'id':'m1','money_state':'reconciled',
                'currency':'CNY','budget_cost':'3.50','cost_reconciliations':[{
                'amount':'3.50','currency':'CNY','previous_amount':'2.00','previous_money_state':'estimated',
                'evidence_path':str(bill),'evidence_sha256':hashlib.sha256(bill.read_bytes()).hexdigest()}]}]})
            data=task_center_service.project_snapshot(root,task_id='S1')
            self.assertEqual(len(data['tasks']),2)
            first,second=data['tasks']
            self.assertEqual(first['timings_s'],{'submission':2,'queue_observed':3,'run_observed':5,'download':4,'publication':1})
            self.assertEqual(first['cost']['difference'],'1.50')
            self.assertEqual(first['reason_code'],'provider_error')
            self.assertEqual(second['retry_reason'],'explicit_after_failed')
            self.assertIsNone(second['cost']['actual'])
            bill.write_text('changed')
            self.assertIsNone(task_center_service.project_snapshot(root,task_id='S1')['tasks'][0]['cost']['actual'])
