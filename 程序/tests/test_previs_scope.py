"""REQ-S09-01/02/03/04/10/12/24/26/30/31/33/40：白模预演阶段的依赖、锁、门禁、证据与目录契约。"""
import json
import tempfile
import unittest
from pathlib import Path

import previs_routing
import project_stages
import script_contract
import stage_flow
import stage_parallel
import stage_path_service
import white_model_ref
import white_model_service as wm
from project_context import ProjectContext

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills' / '09白模预演SKILL' / 'pipeline-previs.skill.md'


def _publish(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')


def _context(root):
    return ProjectContext.snapshot(root, lambda stage: Path(root), {}, None)


class PrevisContractTests(unittest.TestCase):
    def test_req_s09_01_sg04_guards_entry_and_sg05_guards_exit(self):
        gates = {row['id']: row for row in stage_parallel.GATES}
        self.assertEqual((gates['SG-04']['from'], gates['SG-04']['to'], gates['SG-04']['check']),
                         ('keyframe', 'previs', 'frames_ready'))
        self.assertEqual((gates['SG-05']['from'], gates['SG-05']['to'], gates['SG-05']['check']),
                         ('previs', 'video', 'previs_ready'))

    def test_req_s09_02_depends_on_keyframe_and_video_does_not_depend_on_previs(self):
        self.assertEqual(stage_flow.DEPENDS['previs'], ('keyframe',))
        self.assertNotIn('previs', stage_flow.DEPENDS['video'])

    def test_req_s09_03_three_required_locks_and_no_stage_specific_collection(self):
        self.assertEqual(script_contract.STAGE_LOCK_REQUIREMENTS['previs'],
                         ('aspect_ratio', 'video_model_version', 'delivery_format'))

    def test_req_s09_04_batch_serial_two_retries_then_manual(self):
        row = stage_parallel.CONFIG['previs']
        self.assertEqual(row['unit'], stage_parallel.BATCH)
        self.assertEqual((row['min'], row['max']), (2, 3))
        self.assertTrue(row['serial'])
        self.assertEqual(row['retry']['attempts'], 2)
        self.assertEqual(row['retry']['on_exhaust'], stage_parallel.ON_MANUAL)

    def test_req_s09_04_brief_requires_in_order_shots(self):
        self.assertIn('禁止并行', stage_parallel.brief_block('previs'))

    def test_req_s09_10_three_levels_map_to_three_routes(self):
        self.assertEqual(set(previs_routing.LEVELS), {'simple', 'medium', 'complex'})
        self.assertEqual(previs_routing.ROUTES, {'simple': '无需白模', 'medium': '线上简单白模',
                                                 'complex': 'Agent 自动制作'})

    def test_req_s09_12_routing_refuses_a_bare_path_instead_of_project_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(TypeError):
                previs_routing.overrides_file(tmp)

    def test_req_s09_40_skill_depends_on_keyframe_and_is_not_parallel(self):
        text = SKILL.read_text(encoding='utf-8')
        self.assertIn('dependsOn: [pipeline-keyframe]', text)
        self.assertIn('parallelizable: false', text)
        for lock in ('aspect_ratio', 'video_model_version', 'delivery_format'):
            self.assertIn(lock, text)

    def test_req_s09_stage_directory_is_09_and_legacy_08_is_read_only(self):
        self.assertEqual(project_stages.STAGES['previs'], '09白模预演')
        self.assertEqual(stage_path_service.LEGACY_NUMBERED['previs'], '08白模预演')
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(stage_path_service.write_dir(tmp, 'previs').name, '09白模预演')


class PrevisGateTests(unittest.TestCase):
    def test_req_s09_33_sg05_passes_but_is_not_started_without_adopted_storyboard(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = stage_parallel.previs_ready(Path(tmp))
        self.assertTrue(result['ok'])
        self.assertFalse(result['started'])


class PrevisEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.source = self.base / 'episode.json'
        self.source.write_text(json.dumps({'episode_id': 'EP001', 'shots': [
            {'id': 'EP001_S01', 'action': '追逐', 'duration': 5}]}), encoding='utf-8')
        self.shot_dir = self.base / 'shot'
        self.shot_dir.mkdir()
        self.preview = self.shot_dir / 'preview.mp4'
        self.preview.write_bytes(b'0123456789')

    def _record(self):
        wm.record_evidence(self.shot_dir, 'EP001_S01', self.source, publish=_publish,
                           media={'duration': 5, 'has_video': True}, preview=self.preview)
        record = wm.read_record(self.shot_dir)
        record['preview'] = str(self.preview)
        return record

    def test_req_s09_31_record_without_evidence_is_unbound(self):
        self.assertEqual(wm.evidence_state({'preview': str(self.preview)}, self.preview,
                                           self.source, 'EP001_S01'), 'unbound')

    def test_req_s09_31_registered_evidence_is_ok_until_source_shot_changes(self):
        record = self._record()
        self.assertEqual(wm.evidence_state(record, self.preview, self.source, 'EP001_S01'), 'ok')
        self.source.write_text(json.dumps({'episode_id': 'EP001', 'shots': [
            {'id': 'EP001_S01', 'action': '站定，微笑，缓慢转头', 'duration': 7}]}), encoding='utf-8')
        self.assertEqual(wm.evidence_state(record, self.preview, self.source, 'EP001_S01'), 'changed')

    def test_req_s09_31_changed_preview_media_invalidates_without_deleting_it(self):
        record = self._record()
        self.preview.write_bytes(b'0123456789-longer')
        self.assertEqual(wm.evidence_state(record, self.preview, self.source, 'EP001_S01'), 'changed')
        self.assertTrue(self.preview.is_file())

    def test_req_s09_31_empty_preview_is_not_registered_as_evidence(self):
        empty = self.shot_dir / 'empty.mp4'
        empty.write_bytes(b'')
        self.assertIsNone(wm.record_evidence(self.shot_dir, 'EP001_S01', self.source,
                                             publish=_publish, preview=empty))

    def test_req_s09_31_source_digest_ignores_fields_outside_the_scheduling_set(self):
        shot = {'id': 'S1', 'action': '追逐', 'duration': 5}
        self.assertEqual(wm.shot_digest(shot), wm.shot_digest(dict(shot, duration=5.0, note='备注')))
        self.assertNotEqual(wm.shot_digest(shot), wm.shot_digest(dict(shot, camera='环绕')))


class PrevisImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.shot_dir = self.base / 'shot'

    def test_req_s09_24_video_is_copied_and_original_is_kept(self):
        source = self.base / 'made.mp4'
        source.write_bytes(b'video-bytes')
        target = wm.import_previs_media(self.shot_dir, 'S1', source, publish=_publish)
        self.assertTrue(source.is_file())
        self.assertEqual(target.read_bytes(), b'video-bytes')
        self.assertEqual(wm.read_record(self.shot_dir)['preview'], str(target))

    def test_req_s09_24_project_file_goes_to_project_file_key(self):
        source = self.base / 'scene.blend'
        source.write_bytes(b'blend')
        target = wm.import_previs_media(self.shot_dir, 'S1', source, publish=_publish)
        record = wm.read_record(self.shot_dir)
        self.assertEqual(record['project_file'], str(target))
        self.assertNotIn('preview', record)

    def test_req_s09_24_rejects_empty_unknown_format_and_path_like_shot_id(self):
        empty = self.base / 'empty.mp4'
        empty.write_bytes(b'')
        text = self.base / 'note.txt'
        text.write_text('x', encoding='utf-8')
        good = self.base / 'ok.mp4'
        good.write_bytes(b'x')
        for source, sid in ((empty, 'S1'), (text, 'S1'), (good, '../S1'), (good, '..')):
            with self.subTest(source=source.name, sid=sid):
                with self.assertRaises(ValueError):
                    wm.import_previs_media(self.shot_dir, sid, source, publish=_publish)
        self.assertTrue(empty.is_file() and text.is_file() and good.is_file())
        self.assertEqual(wm.read_record(self.shot_dir), {})


class PrevisDirectoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.workspace = self.base / 'workspace'
        self.project = self.base / '我的项目'
        self.project.mkdir()

    def test_req_s09_30_with_project_id_directory_is_identity_episode_shot(self):
        (self.project / 'config.json').write_text(json.dumps({'project_id': 'abc123'}), encoding='utf-8')
        found = wm.shot_directory(_context(self.project), 'EP001_S01', self.workspace)
        self.assertEqual(found, (self.workspace / 'abc123' / 'EP001' / 'EP001_S01').resolve())

    def test_req_s09_30_without_project_id_falls_back_to_legacy_layout(self):
        found = wm.shot_directory(_context(self.project), 'S09', self.workspace)
        self.assertEqual(found, (self.workspace / '我的项目' / 'S09').resolve())

    def test_req_s09_30_shot_directory_rejects_path_like_shot_ids(self):
        for sid in ('', '..', '../x', 'a/b'):
            with self.subTest(sid=sid):
                with self.assertRaises(ValueError):
                    wm.shot_directory(_context(self.project), sid, self.workspace)

    def test_req_s09_30_workspace_defaults_to_user_data_not_blender_install(self):
        self.assertEqual(wm.default_workspace().name, '白模项目')
        self.assertEqual(wm.default_workspace().parent.name, '漫剧制作助手')


class WhiteModelReferenceTests(unittest.TestCase):
    def test_req_s09_26_only_wan_r2v_and_seedance_accept_reference_video(self):
        providers = {row[0] for row in white_model_ref.SUPPORT}
        self.assertEqual(providers, {'wan', 'volcengine'})
        self.assertIsNotNone(white_model_ref.support('wan', 'wan2.7-r2v'))
        self.assertIsNotNone(white_model_ref.support('volcengine', 'doubao-seedance-2-0-pro'))
        self.assertIsNone(white_model_ref.support('local', 'anything'))
        self.assertEqual(white_model_ref.DEFAULT_MAX_MB, 20)

    def test_req_s09_26_unsupported_reason_names_which_models_work(self):
        text = white_model_ref.unsupported_reason('local', '')
        self.assertIn(white_model_ref.supported_text(), text)


if __name__ == '__main__':
    unittest.main()
