"""显式返工保留旧成果；本地/云端及单镜/批量共享安全提交口径。"""
import copy
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from agent.core import save, read
from engine import Studio
from local_video import LocalStudio
from video_task_state import submission_block_reason
from ui_widgets import BusyState


class VideoRevisionTests(unittest.TestCase):
    def test_submission_persists_execution_identity_in_both_backends(self):
        from contract.platform_tools import ExecutionControl, execution_scope
        for cls in (Studio, LocalStudio):
            with self.subTest(backend=cls.__name__):
                studio = self.studio(cls, [])
                self.dependencies(studio)
                control = ExecutionControl()
                with execution_scope(control):
                    studio.submit('SH001')
                saved = read(studio.db)['shots']['SH001'][0]
                self.assertEqual(saved['execution']['run_id'], control.run_id)
                self.assertEqual(saved['execution']['task_id'], 'SH001')
                self.assertTrue(saved['execution']['attempt_id'])
                self.assertEqual(saved['retry_reason'], 'initial')
                self.assertGreaterEqual(saved['submitted_at'], saved['created'])

    def test_cloud_sends_frozen_payload_and_records_actual_reference_bytes(self):
        import base64
        import hashlib
        from agent.wan import WanAdapter
        from agent.volcengine import VolcengineAdapter
        for cls, mode in ((WanAdapter, 'wan'), (VolcengineAdapter, 'seedance')):
            with self.subTest(provider=mode):
                studio = self.studio(Studio, [])
                self.dependencies(studio)
                studio.cfg.update(base_url='https://example.invalid', model='fixture')
                frame = self.root / 'frame.png'
                original = b'\x89PNG\r\n\x1a\noriginal'
                frame.write_bytes(original)
                asset = self.root / 'asset.png'
                asset.write_bytes(b'\x89PNG\r\n\x1a\nactual-reference')
                prepared = dict(studio.shot('SH001'), _reference_mode=mode,
                    _asset_references=[{'path': str(asset), 'id': 'CHAR_001', 'sha256': 'stale'}])
                api = cls(studio.cfg)
                build = api.payload
                sent = []
                def payload(shot, path):
                    result = build(shot, path)
                    frame.write_bytes(b'\x89PNG\r\n\x1a\nchanged-after-freeze')
                    return result
                def send(*, payload):
                    sent.append(payload)
                    return {'id': 'task-id', 'output': {'task_id': 'task-id'}}
                api.call = send
                studio.client.return_value = api
                with patch.object(api, 'payload', side_effect=payload) as builds, patch(
                        'agent.shot_assets.prepare', return_value=prepared):
                    studio.submit('SH001')
                manifest = read(self.root / 'data/SH001/v001/assets_manifest.json')
                image = (sent[0]['input']['media'][0]['url'] if mode == 'wan'
                         else sent[0]['content'][1]['image_url']['url'])
                digest = hashlib.sha256(base64.b64decode(image.split(',', 1)[1])).hexdigest()
                self.assertEqual(manifest['first_frame']['sha256'], digest)
                self.assertEqual(digest, hashlib.sha256(original).hexdigest())
                self.assertEqual(manifest['assets'][0]['sha256'], hashlib.sha256(asset.read_bytes()).hexdigest())
                self.assertEqual(builds.call_count, 1)
                self.assertEqual(studio.frame.call_count, 1)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_provider_terminal_reason_survives_restart_without_resubmission(self):
        from agent.wan import WanAdapter
        from agent.volcengine import VolcengineAdapter
        from video_progress import status_detail
        for cls, raw, label in (
                (WanAdapter, {'output': {'task_status': 'CANCELED'}}, '已取消'),
                (VolcengineAdapter, {'status': 'cancelled'}, '已取消'),
                (VolcengineAdapter, {'status': 'expired'}, '已过期'),
                (WanAdapter, {'output': {'task_status': 'FAILED'}}, '原因未知')):
            with self.subTest(provider=cls.__name__, response=raw):
                studio = self.studio(Studio, [])
                api = self.dependencies(studio)
                studio.submit('SH001')
                adapter = cls({'base_url': 'https://example.invalid'})
                adapter.call = Mock(return_value=raw)
                api.poll.side_effect = adapter.poll
                self.assertIn(label, studio.poll('SH001'))
                saved = read(studio.db)['shots']['SH001'][-1]
                self.assertTrue(saved['charged'])
                self.assertEqual(saved['state'], 'failed')
                self.assertIn(label, status_detail(saved))
                self.assertIn('重做', status_detail(saved))
                api.submit.assert_called_once()
                # 重新读取磁盘并再次查询终态，只查询原任务。
                restarted = object.__new__(Studio)
                restarted.__dict__.update(studio.__dict__)
                restarted.poll('SH001')
                api.submit.assert_called_once()
                self.assertEqual(len(studio.state()['shots']['SH001']), 1)

    def studio(self, cls, versions):
        studio = object.__new__(cls)
        studio.root = self.root
        studio.db = self.root / 'data/state.json'
        studio.episode_path = self.root / 'episode.json'
        studio.cfg = {'live_enabled': True, 'ffmpeg': 'ffmpeg', 'ffprobe': 'ffprobe'}
        studio.episode = {'shots': [{'id': 'SH001', 'duration': 5, 'video_prompt': 'new prompt'}]}
        studio.frame = Mock(return_value=self.root / 'frame.png')
        studio.remaining = Mock(return_value=100)
        save(studio.db, {'shots': {'SH001': copy.deepcopy(versions)}})
        return studio

    def dependencies(self, studio):
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch('white_model.validate_video_submission', return_value=None))
        if isinstance(studio, LocalStudio):
            api = Mock(url='http://127.0.0.1:8189')
            api.call.return_value = {'prompt_id': 'local-new-task'}
            def upload(path, *, evidence=None):
                if evidence is not None:
                    evidence.update(path=str(path), sha256='a' * 64)
                return 'frame.png'
            api.upload.side_effect = upload
            stack.enter_context(patch('local_video.LocalAPI', return_value=api))
            stack.enter_context(patch('local_video.prepare_graph', return_value=({'114': {'inputs': {}}}, {})))
            stack.enter_context(patch('local_video.png_size', return_value=(32, 32)))
            stack.enter_context(patch('h3_reference_adapter.attach', return_value=[]))
            stack.enter_context(patch('native_apps.open_comfy'))
            stack.enter_context(patch('native_apps.wait_comfy'))
            stack.enter_context(patch('local_video.preflight'))
            stack.enter_context(patch('local_video.command'))
        else:
            api = Mock()
            api.payload.return_value = {'prompt': 'new prompt'}
            api.submit.return_value = 'cloud-new-task'
            studio.client = Mock(return_value=api)
            prepared = dict(studio.shot('SH001'), _reference_mode='first_frame', _asset_references=[])
            stack.enter_context(patch('api_models.ensure_cloud_model'))
            stack.enter_context(patch('agent.shot_assets.prepare', return_value=prepared))
            stack.enter_context(patch('engine.command'))
        return api

    def money_policy(self, cap='0.5'):
        save(self.root / 'cost_profile.json', {'budget_amount': cap, 'price_table': {
            'currency': 'CNY', 'version': 'test', 'model_rates': {'video-m': {'seconds': '0.1'}}}})

    def test_local_submission_persists_sources_before_generation(self):
        studio = self.studio(LocalStudio, [])
        api = self.dependencies(studio)
        def submit(path, payload=None):
            manifest = read(self.root / 'data/SH001/v001/assets_manifest.json')
            self.assertEqual(manifest['first_frame']['category'], 'image')
            self.assertEqual(manifest['first_frame']['sha256'], 'a' * 64)
            self.assertEqual(manifest['assets'][0]['id'], 'CHAR_001')
            self.assertEqual(manifest['assets'][0]['sha256'], 'a' * 64)
            return {'prompt_id': 'local-new-task'}
        api.call.side_effect = submit
        asset = {'id': 'CHAR_001', 'name': '角色', 'path': str(self.root / 'asset.png'),
                 'picture': 1, 'node_id': 'ref'}
        with patch('h3_reference_adapter.attach', return_value=[asset]), patch('local_video.prepare_graph',
                return_value=({'114': {'inputs': {}}, 'ref': {'inputs': {}}}, {})):
            studio.submit('SH001')

    def test_money_rejection_does_not_submit_or_consume_seconds(self):
        from pet_llm import RequestLedger
        self.money_policy('0')
        studio = self.studio(Studio, [])
        studio.cfg['model'] = 'video-m'
        api = self.dependencies(studio)
        with self.assertRaisesRegex(ValueError, '视频未发送'):
            studio.submit('SH001')
        api.submit.assert_not_called()
        version = studio.state()['shots']['SH001'][-1]
        self.assertTrue(version['not_submitted'])
        self.assertFalse(version['charged'])
        self.assertEqual(RequestLedger(self.root).load().entries, [])

    def test_video_cloud_sessions_share_project_budget(self):
        from pet_llm import RequestLedger
        self.money_policy()
        for name, allowed in [('first', True), ('second', False)]:
            studio = self.studio(Studio, [])
            studio.root = self.root / 'cloud_video' / name
            studio.db = studio.root / 'data/state.json'
            save(studio.db, {'shots': {'SH001': []}})
            studio.cfg['model'] = 'video-m'
            api = self.dependencies(studio)
            if allowed:
                studio.submit('SH001')
                api.submit.assert_called_once()
            else:
                with self.assertRaisesRegex(ValueError, '视频未发送'):
                    studio.submit('SH001')
                api.submit.assert_not_called()
        rows = RequestLedger(self.root).load().entries
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['budget_cost'], '0.5')
        self.assertEqual(rows[0]['amount'], 1)

    def test_cloud_success_settles_before_download_and_retry_does_not_charge_twice(self):
        from pet_llm import RequestLedger
        self.money_policy()
        studio = self.studio(Studio, [])
        studio.cfg['model'] = 'video-m'
        api = self.dependencies(studio)
        studio.submit('SH001')
        api.poll.return_value = {'status': 'succeeded', 'usage': {'total_tokens': 123}}
        api.download_video.side_effect = TimeoutError('download test')
        for _ in range(2):
            with self.assertRaisesRegex(RuntimeError, '下载中断'):
                studio.poll('SH001')
        api.submit.assert_called_once()
        ledger = RequestLedger(self.root).load()
        self.assertEqual(len(ledger.entries), 1)
        self.assertEqual(ledger.entries[0]['budget_cost'], '0.5')
        self.assertEqual(ledger.entries[0]['money_state'], 'estimated')
        version = studio.state()['shots']['SH001'][-1]
        self.assertEqual(version['usage']['total_tokens'], 123)
        studio.record_video_usage('SH001', version)
        self.assertEqual(len(RequestLedger(self.root).load().entries), 1)

    def test_failed_submission_preserves_unknown_money_after_restart(self):
        from pet_llm import RequestLedger
        self.money_policy()
        studio = self.studio(Studio, [])
        studio.cfg['model'] = 'video-m'
        api = self.dependencies(studio)
        api.submit.side_effect = TimeoutError('submit test')
        with self.assertRaisesRegex(RuntimeError, '提交连接中断'):
            studio.submit('SH001')
        version = studio.state()['shots']['SH001'][-1]
        row = RequestLedger(self.root).load()._find(version['money_request_id'])
        self.assertEqual(row['money_state'], 'unknown')
        self.assertEqual(row['budget_cost'], '0.5')
        with self.assertRaises(ValueError):studio.submit('SH001')
        self.assertEqual(api.submit.call_count, 1)

    def test_revise_creates_new_version_and_preserves_old_for_both_backends(self):
        for cls in (Studio, LocalStudio):
            with self.subTest(backend=cls.__name__):
                old = {'version': 1, 'state': 'downloaded', 'review': 'revise', 'file': 'data/SH001/v001/SH001.mp4'}
                source = self.root / old['file']
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_bytes(b'old-content')
                studio = self.studio(cls, [old])
                api = self.dependencies(studio)
                studio.submit('SH001')
                versions = studio.state()['shots']['SH001']
                self.assertEqual(versions[0], old)
                self.assertEqual(source.read_bytes(), b'old-content')
                self.assertEqual(len(versions), 2)
                self.assertEqual(versions[-1]['version'], 2)
                self.assertEqual(versions[-1]['state'], 'queued')
                self.assertEqual(versions[-1]['review'], 'pending')
                with self.assertRaisesRegex(ValueError, '未完成|不确定'):
                    studio.submit('SH001')
                (api.call if cls is LocalStudio else api.submit).assert_called_once()

    def test_pass_pending_and_unknown_never_resubmit(self):
        for cls in (Studio, LocalStudio):
            for review in ('pass', 'pending', 'revise'):
                versions = [{'version': 1, 'state': 'downloaded', 'review': review}]
                if review == 'revise': versions.append({'version': 2, 'state': 'unknown'})
                with self.subTest(backend=cls.__name__, review=review):
                    studio = self.studio(cls, versions)
                    api = self.dependencies(studio)
                    with self.assertRaises(ValueError): studio.submit('SH001')
                    self.assertEqual(studio.state()['shots']['SH001'], versions)
                    api.submit.assert_not_called()
                    api.call.assert_not_called()

    def test_failed_rework_can_retry_but_any_unresolved_history_blocks(self):
        rejected = [{'state': 'downloaded', 'review': 'revise'}, {'state': 'rejected'}]
        self.assertEqual(submission_block_reason(rejected), '')
        self.assertTrue(submission_block_reason([{'state': 'unknown'}, {'state': 'downloaded', 'review': 'revise'}]))
        self.assertTrue(submission_block_reason([{'state': 'downloaded', 'review': 'pass'}, {'state': 'failed'}]))

    def test_batch_filters_same_as_manual_gate(self):
        from app import pending_checked_shots
        records = {'new': [], 'revise': [{'state': 'downloaded', 'review': 'revise'}],
                   'pass': [{'state': 'downloaded', 'review': 'pass'}],
                   'pending': [{'state': 'downloaded', 'review': 'pending'}],
                   'unknown': [{'state': 'downloaded', 'review': 'revise'}, {'state': 'unknown'}]}
        studio = SimpleNamespace(episode={'shots': [{'id': sid} for sid in records]}, state=lambda: {'shots': records})
        self.assertEqual(pending_checked_shots(studio, list(records)), ['new', 'revise'])

    def test_single_button_allows_explicit_revise_and_retains_pass_skip(self):
        from app import App
        for review in ('revise', 'pass', 'pending'):
            with self.subTest(review=review):
                studio = self.studio(LocalStudio, [{'state': 'downloaded', 'review': review}])
                studio.submit = Mock(return_value='queued')
                app = SimpleNamespace(studio=studio, sid=lambda: 'SH001', edit_checks={'SH001': True},
                    write=Mock(), ensure_frame=Mock(return_value=True), prompt=Mock(), save_options=Mock(),
                    local_submit_error={}, progress_text=Mock(), task_progress=Mock(), local_messages=Mock(),
                    busy_state=BusyState(Mock(), spinner=Mock()))
                app.prompt.get.return_value = 'new prompt'
                app.run = lambda work: work()
                with patch('app.assert_prompt_editable'):
                    App.generate(app)
                self.assertEqual(studio.submit.call_count, 1 if review == 'revise' else 0)

    def test_batch_button_only_submits_revise_and_confirms_its_cost(self):
        from app import App
        for cls in (Studio, LocalStudio):
            with self.subTest(backend=cls.__name__):
                studio = self.studio(cls, [{'state': 'downloaded', 'review': 'revise'}])
                studio.episode['shots'] += [{'id': 'SH002', 'duration': 8}, {'id': 'SH003', 'duration': 9}]
                state = studio.state()
                state['shots']['SH002'] = [{'state': 'downloaded', 'review': 'pass'}]
                state['shots']['SH003'] = [{'state': 'unknown'}]
                save(studio.db, state)
                studio.submit = Mock(return_value='queued')
                app = SimpleNamespace(studio=studio, sid=lambda: 'SH001', prompt=Mock(),
                                      write=Mock(), confirm_submit=Mock(return_value=True))
                app.prompt.get.return_value = 'new prompt'
                app.run = lambda work: work()
                with patch('app.work_targets', return_value=(['SH001', 'SH002', 'SH003'], 'checked')):
                    App.generate_checked(app)
                studio.submit.assert_called_once_with('SH001')
                if cls is Studio:
                    self.assertEqual(app.confirm_submit.call_args.args[2], 5)
                else:
                    app.confirm_submit.assert_not_called()

    def test_local_auto_plan_polls_rework_but_never_starts_it_automatically(self):
        from local_video import auto_plan
        old = {'state': 'downloaded', 'review': 'revise'}
        studio = self.studio(LocalStudio, [old])
        plan = auto_plan(self.root, studio.episode_path, studio=studio)
        self.assertEqual(plan[0], [])
        self.assertTrue(plan[2])
        for state in ('queued', 'running', 'unknown', 'succeeded'):
            save(studio.db, {'shots': {'SH001': [old, {'state': state}]}})
            plan = auto_plan(self.root, studio.episode_path, studio=studio)
            self.assertEqual(plan[0], [])
            self.assertEqual(plan[1], ['SH001'])
