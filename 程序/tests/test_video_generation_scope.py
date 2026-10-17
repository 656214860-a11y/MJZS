"""REQ-S10-01/02/03/04/05/06/10/12/14/15/17/22/30/32/40：视频生成阶段的锁、依赖、门禁、提交守卫、采用口径、SKILL 与层级归属。"""
import importlib.util
import tempfile
import unittest
from pathlib import Path

import engine
import pet_bus
import script_contract
import stage_completion_service
import stage_flow
import stage_layout
import stage_parallel
import stage_path_service
import video_lifecycle_service
import video_source_evidence
import video_task_state
from service_contract import UserError

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / 'skills' / '10视频生成SKILL'
SKILLS = ('pipeline-video-generation', 'video-batch-submit', 'video-multi-model-route',
          'video-quality-check', 'video-retry')


def _layers():
    spec = importlib.util.spec_from_file_location('_layers_s10', ROOT / 'tests' / 'architecture' / '_layers.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.LAYERS


class VideoGenerationScopeTests(unittest.TestCase):
    def test_req_s10_01_video_is_tenth_of_thirteen_stages_with_its_own_directory(self):
        self.assertEqual(len(pet_bus.STAGES), 13)
        self.assertEqual(pet_bus.STAGES.index('video'), 9)
        self.assertEqual(stage_layout.dirname_of('video'), '10视频生成')
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(stage_path_service.write_dir(td, 'video').name, '10视频生成')
        self.assertEqual(stage_path_service.LEGACY_NUMBERED['video'], '09视频生成')

    def test_req_s10_02_video_stage_collects_three_production_locks(self):
        self.assertEqual(script_contract.STAGE_LOCK_REQUIREMENTS['video'],
                         ('aspect_ratio', 'video_model_version', 'delivery_format'))

    def test_req_s10_03_flow_dependency_names_keyframe_only(self):
        self.assertEqual(stage_flow.DEPENDS['video'], ('keyframe',))
        self.assertEqual(stage_flow.DEPENDS['edit'], ('video', 'audio'))

    def test_req_s10_04_sg05_gates_previs_to_video_and_passes_an_empty_project(self):
        row = stage_parallel.gate_for('video')
        self.assertEqual((row['id'], row['from'], row['to']), ('SG-05', 'previs', 'video'))
        with tempfile.TemporaryDirectory() as td:
            result = stage_parallel.previs_ready(Path(td))
        self.assertTrue(result['ok'])
        self.assertFalse(result['started'])

    def test_req_s10_05_video_is_a_paid_stage(self):
        self.assertIn('video', stage_flow.PAID_STAGES)

    def test_req_s10_06_video_runs_serial_in_small_batches_with_rate_limit(self):
        spec = stage_parallel.CONFIG['video']
        self.assertTrue(spec['serial'])
        self.assertEqual((spec['min'], spec['max'], spec['limit']), (2, 3, 3))
        self.assertEqual(spec['retry']['attempts'], 2)
        self.assertEqual([s for s in pet_bus.STAGES if stage_parallel.rate_limited(s)], ['video'])

    def test_req_s10_10_unfinished_or_ready_shot_blocks_resubmission(self):
        block = video_task_state.submission_block_reason
        self.assertEqual(block([]), '')
        self.assertEqual(block([{'state': 'failed'}]), '')
        self.assertEqual(block([{'state': 'rejected'}]), '')
        for state in ('submitting', 'unknown', 'queued', 'running', 'succeeded'):
            with self.subTest(state=state):
                self.assertTrue(block([{'state': state}]))
        self.assertTrue(block([{'state': 'downloaded', 'review': 'pass'}]))
        self.assertEqual(block([{'state': 'downloaded', 'review': 'revise'}]), '')

    def test_req_s10_10_active_states_are_the_uncertain_ones(self):
        self.assertEqual(video_task_state.ACTIVE, {'submitting', 'unknown', 'queued', 'running', 'succeeded'})
        self.assertEqual(video_lifecycle_service.UNCERTAIN_STATES, frozenset(video_task_state.ACTIVE))

    def test_req_s10_12_unattended_video_is_local_only(self):
        import local_video
        with self.assertRaisesRegex(ValueError, '只支持本地 ComfyUI'):
            local_video.auto_plan('.', 'episode.json', studio=object())

    def test_req_s10_12_local_api_accepts_loopback_http_only(self):
        import local_video
        for url in ('https://127.0.0.1:8189', 'http://example.com:8189', 'http://127.0.0.1:8189/x'):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    local_video.LocalAPI(url)
        self.assertEqual(local_video.LocalAPI('http://127.0.0.1:8189').url, 'http://127.0.0.1:8189')

    def test_req_s10_14_provider_cancel_or_expiry_never_auto_resubmits(self):
        for status in ('canceled', 'cancelled', 'expired'):
            with self.subTest(status=status):
                self.assertIn('不会自动重新提交', video_task_state.provider_failure_reason({'provider_status': status}))
        self.assertIn('原因未知', video_task_state.provider_failure_reason({}))

    def test_req_s10_14_source_evidence_requires_sha256_digest(self):
        with self.assertRaisesRegex(ValueError, '摘要'):
            video_source_evidence.submitted_sources({'input': {'img_url': 'plain-url'}}, 'frame.png')
        digest = 'sha256:' + 'a' * 64
        found = video_source_evidence.submitted_sources({'input': {'img_url': digest}}, 'frame.png')
        self.assertEqual(found['first_frame']['sha256'], 'a' * 64)

    def test_req_s10_15_only_downloaded_qc_pass_and_reviewed_versions_are_approved(self):
        good = {'version': 1, 'state': 'downloaded', 'qc_pass': True, 'review': 'pass'}
        rows = [good, {'version': 2, 'state': 'downloaded', 'qc_pass': False, 'review': 'pass'},
                {'version': 3, 'state': 'downloaded', 'qc_pass': True, 'review': 'pending'},
                {'version': 4, 'state': 'queued', 'qc_pass': True, 'review': 'pass'}]
        self.assertEqual(engine.approved_versions(rows), [good])

    def test_req_s10_15_pinned_approved_version_wins_over_latest_approved(self):
        first = {'version': 1, 'state': 'downloaded', 'qc_pass': True, 'review': 'pass', 'pinned': True}
        second = {'version': 2, 'state': 'downloaded', 'qc_pass': True, 'review': 'pass'}
        self.assertIs(engine.adopted_edit_version([first, second])[0], first)
        self.assertIs(engine.adopted_edit_version([{**first, 'pinned': False}, second])[0], second)
        self.assertEqual(engine.adopted_edit_version([{'state': 'queued'}]), (None, engine.ADOPT_UNAPPROVED))

    def test_req_s10_17_delete_refuses_shot_with_uncertain_task(self):
        result = video_lifecycle_service.mark_video_deleted(
            'episode.json', 'S1', [{'state': 'running'}], gateway={'publish_json': lambda *_: None})
        self.assertIsInstance(result, UserError)

    def test_req_s10_22_completion_needs_every_shot_approved_via_injected_check(self):
        with tempfile.TemporaryDirectory() as td:
            ok, _ = stage_completion_service.completion_evidence(td, 'video', lambda: ('digest', []))
            self.assertTrue(ok)
            ok, detail = stage_completion_service.completion_evidence(td, 'video', lambda: (None, ['S1 尚未验收']))
            self.assertFalse(ok)
            self.assertIn('验收', detail)

    def test_req_s10_30_five_skills_exist_for_the_stage(self):
        for name in SKILLS:
            with self.subTest(name=name):
                self.assertTrue((SKILL_DIR / (name + '.skill.md')).is_file())

    def test_req_s10_32_pipeline_skill_is_serial_paid_and_depends_on_previs(self):
        text = (SKILL_DIR / 'pipeline-video-generation.skill.md').read_text(encoding='utf-8')
        for line in ('dependsOn: [pipeline-previs]', 'parallelizable: false', 'paid: true'):
            self.assertIn(line, text)

    def test_req_s10_40_cloud_and_local_video_pages_are_ui_layer_engine_is_orchestration(self):
        layers = _layers()
        self.assertEqual((layers['cloud_video'], layers['local_video']), (4, 4))
        self.assertEqual(layers['engine'], 3)
        self.assertEqual(layers['cloud_video_service'], 2)


if __name__ == '__main__':
    unittest.main()
