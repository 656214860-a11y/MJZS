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
        import contract.platform_tools as platform_tools
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
            save(root/'workflows/receipt.json', {'prompt_id': 'remote-image', 'state': 'queued',
                                                 'cost_request_id': 'asset:one'})
            from infra.pet_llm import request_ledger_path
            save(request_ledger_path(root), {'entries': [
                {'id': 'asset:one', 'money_state': 'reserved', 'budget_cost': '0.20', 'currency': 'CNY'}]})
            save(root/'cloud_video/session/data/state.json', {'shots': {'S001': [
                {'version': 1, 'state': 'unknown', 'local_request': 'attempt-one'},
                {'version': 2, 'state': 'downloaded', 'local_request': 'attempt-two', 'file': 'v2.mp4'}]}})
            save(root/'cloud_video/session/data/S001/v001/task_receipt.json',
                 {'shot': 'S001', 'version': 1, 'local_request': 'attempt-one', 'task_id': 'remote-video-one'})
            save(root/'cloud_video/session/data/S001/v001/request.json', {'model': 'video-model'})
            before = {str(p): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            one = task_center_service.project_snapshot(root)
            two = task_center_service.project_snapshot(root)
            self.assertEqual(one, two)
            self.assertEqual(len(one['tasks']), 3)
            self.assertTrue(all(r['project_id'] == 'project-one' for r in one['tasks']))
            image = next(r for r in one['tasks'] if r['task_id'] == 'CHAR_001')
            self.assertEqual(image['remote_task_id'], 'remote-image')
            self.assertEqual(image['state'], 'reconcile')
            self.assertEqual(image['cost_request_id'], 'asset:one')
            self.assertEqual(image['cost']['estimate'], '0.20')
            self.assertIn('资产', image['recovery'])
            video = [r for r in one['tasks'] if r['task_id'] == 'S001']
            self.assertEqual([r['attempt_id'] for r in video], ['attempt-one', 'attempt-two'])
            self.assertNotEqual(video[0]['state'], 'failed')
            self.assertEqual(video[0]['remote_task_id'], 'remote-video-one')
            self.assertEqual(video[0]['query_capability'], 'queryable')
            self.assertEqual(video[0]['request'], 'cloud_video/session/data/S001/v001/request.json')
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
        from infra.pet_llm import request_ledger_path
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

    def test_video_mismatched_receipt_is_reported_and_not_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save(root/'data/state.json', {'shots': {'S1': [
                {'version': 1, 'state': 'unknown', 'local_request': 'attempt-one'}]}})
            save(root/'data/S1/v001/task_receipt.json',
                 {'shot': 'S2', 'version': 1, 'local_request': 'attempt-other', 'task_id': 'wrong-remote'})
            data = task_center_service.project_snapshot(root)
            row = next(row for row in data['tasks'] if row['stage'] == 'video')
            self.assertIsNone(row['remote_task_id'])
            self.assertTrue(any('回执与版本记录不匹配' in item for item in data['errors']))

    def test_audio_restart_projects_success_and_legacy_408_without_writes(self):
        import hashlib
        from contract.project_stages import audio
        from infra.pet_llm import request_ledger_path
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save(root/'config.json', {'project_id': 'project-audio'})
            batch = audio(root)/'配音分句'/'配音批次_20260101'
            raw = b'audio-one'
            name = '001_S001_角色_1.0s.mp3'
            batch.mkdir(parents=True)
            (batch/name).write_bytes(raw)
            save(batch/'批次.json', {'signature': 'sig', 'lines': 2})
            save(batch/'时间轴.json', [
                {'shot_id': 'S001', 'text': '成功句', 'state': 'ok', 'file': name,
                 'sha256': hashlib.sha256(raw).hexdigest(), 'request_id': 'tts:ok',
                 'cost_request_id': 'tts:ok', 'voice': 'alloy', 'model': 'tts-a',
                 'endpoint': 'https://a.example/v1',
                 'execution': {'run_id': 'run-a', 'task_id': 'S001#001', 'attempt_id': 'tts:ok'}},
                {'shot_id': 'S001', 'text': '超时句', 'state': 'failed',
                 'error': 'TTS 请求失败（HTTP 408）', 'file': '', 'request_id': 'tts:408',
                 'voice': 'alloy', 'model': 'tts-a', 'endpoint': 'https://a.example/v1'}])
            save(request_ledger_path(root), {'entries': [
                {'id': 'tts:ok', 'money_state': 'estimated', 'budget_cost': '0.01', 'currency': 'CNY'}]})
            before = {str(p): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            data = task_center_service.project_snapshot(root)
            rows = [row for row in data['tasks'] if row['stage'] == 'audio']
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]['state'], 'recorded_ready')
            self.assertEqual(rows[0]['run_id'], 'run-a')
            self.assertEqual(rows[0]['attempt_id'], 'tts:ok')
            self.assertEqual(rows[0]['cost_request_id'], 'tts:ok')
            self.assertEqual(rows[0]['cost']['estimate'], '0.01')
            self.assertEqual(rows[1]['state'], 'reconcile')
            self.assertEqual(rows[1]['line_index'], 2)
            self.assertEqual(rows[1]['version'], '配音批次_20260101')
            self.assertEqual(rows[1]['query_capability'], 'manual')
            self.assertIn('无按请求号查单接口', rows[1]['query_action'])
            self.assertIn('人工', rows[1]['operation'])
            self.assertEqual(len(task_center_service.project_snapshot(root, task_id='S001')['tasks']), 2)
            found = task_center_service.project_snapshot(root, task_id='tts:408')['tasks']
            self.assertEqual([row['line_index'] for row in found], [2])
            self.assertEqual([row['line_index'] for row in task_center_service.project_snapshot(root, task_id='超时句')['tasks']], [2])
            text = '\n'.join(task_center_service.format_lines({'project_runtime': data}))
            for needle in ('句子：第 2 句', '批次/版本：配音批次_20260101', '请求号 tts:408', '可执行操作'):
                self.assertIn(needle, text)
            self.assertEqual(before, {str(p): p.read_bytes() for p in root.rglob('*') if p.is_file()})

    def test_audio_corrupt_timeline_is_visible_and_does_not_hide_video(self):
        from contract.project_stages import audio
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = audio(root)/'配音分句'/'批次坏'
            batch.mkdir(parents=True)
            (batch/'时间轴.json').write_text('{broken', encoding='utf-8')
            save(root/'data/state.json', {'shots': {'S9': [{'state': 'queued', 'task_id': 'remote'}]}})
            data = task_center_service.project_snapshot(root)
            self.assertTrue(any('时间轴.json' in item and '读取失败' in item for item in data['errors']))
            self.assertEqual(data['tasks'][0]['remote_task_id'], 'remote')
