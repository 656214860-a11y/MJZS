import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.image_fixtures import png
from agent.core import read, save
import keyframe_evidence as evidence
from keyframe_import import fingerprint, register
from stage_execution_service import replace_stage_keyframe


class KeyframeEvidenceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / 'episode.json'
        self.shot = {'id': 'SH001', 'frame': 'frames/SH001.png', 'frame_prompt': '街道'}
        self.episode = {'episode_id': 'EP001', 'shots': [self.shot]}
        save(self.source, self.episode)
        self.image = self.root / self.shot['frame']
        self.image.parent.mkdir()
        self.image.write_bytes(png())
        with evidence._LOCK:
            evidence._DECODED.clear()

    def receipt(self):
        self.shot['frame_evidence'] = evidence.make_evidence(
            self.source, self.episode, self.shot, self.image, expected_size=(16, 9))
        save(self.source, self.episode)

    def problem(self):
        return evidence.frame_problem(self.source, self.episode, self.shot, self.image)

    def test_corrupt_png_rejected_before_replacing_original(self):
        original = self.image.read_bytes()
        bad = original[:42] + original[-12:]
        result = replace_stage_keyframe(self.root, self.source, self.episode, self.shot, bad)
        self.assertFalse(result.ok)
        self.assertEqual(self.image.read_bytes(), original)
        self.assertNotIn('frame_evidence', read(self.source)['shots'][0])

    def test_dimensions_and_aspect_are_enforced(self):
        with self.assertRaisesRegex(ValueError, '尺寸'):
            evidence.make_evidence(self.source, self.episode, self.shot, self.image,
                                   expected_size=(9, 16))
        self.receipt()
        self.assertIn('画幅', evidence.frame_problem(self.source, self.episode, self.shot,
                                                   self.image, aspect_ratio='9:16'))
        self.assertEqual(evidence.frame_problem(self.source, self.episode, self.shot,
                                               self.image, aspect_ratio='16:9'), '')

    def test_legacy_frame_requires_explicit_reimport(self):
        self.assertIn('缺少来源', self.problem())
        result = replace_stage_keyframe(self.root, self.source, self.episode, self.shot,
                                        self.image.read_bytes())
        self.assertTrue(result.ok, (result.reason, result.data))
        self.episode = read(self.source)
        self.shot = self.episode['shots'][0]
        self.assertEqual(self.problem(), '')

    def test_external_replacement_even_same_mtime_requires_review(self):
        self.receipt()
        stamp = self.image.stat()
        self.image.write_bytes(png(color='blue'))
        os.utime(self.image, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        self.assertIn('外部替换', self.problem())

    def test_source_and_prompt_changes_require_review(self):
        self.receipt()
        original = copy.deepcopy(self.episode)
        for scope, key, value in (('episode', 'title', 'new'), ('shot', 'frame_prompt', '新街道')):
            self.episode = copy.deepcopy(original)
            self.shot = self.episode['shots'][0]
            target = self.episode if scope == 'episode' else self.shot
            target[key] = value
            self.assertIn('来源', self.problem())

    def test_generated_references_do_not_invalidate_other_shots(self):
        self.episode['shots'].append({'id': 'SH002', 'frame': 'frames/SH002.png'})
        self.receipt()
        self.episode['shots'][1].update(frame='frames/new.png', frame_evidence={'version': 1})
        self.assertEqual(self.problem(), '')
        self.episode['shots'][1]['frame_prompt'] = 'changed'
        self.assertIn('来源', self.problem())

    def test_cache_is_content_bound_and_does_not_decode_unchanged_images(self):
        self.receipt()
        with patch('keyframe_evidence.run_process', side_effect=AssertionError('unexpected decode')):
            self.assertEqual(self.problem(), '')
            self.assertEqual(evidence.image_facts(self.image.read_bytes())['width'], 16)
        self.image.write_bytes(b'\x89PNG\r\n\x1a\ninvalid')
        self.assertIn('损坏', self.problem())

    def test_reference_asset_replacement_or_metadata_change_invalidates(self):
        save(self.root / 'assets.json', {'CHAR_001': {'name': '主角', 'image': 'reference.png'}})
        ref = self.root / 'reference.png'
        ref.write_bytes(png())
        self.shot['characters'] = ['CHAR_001']
        self.receipt()
        self.assertEqual(self.problem(), '')
        ref.write_bytes(png(color='blue'))
        self.assertIn('来源', self.problem())
        ref.write_bytes(png())
        save(self.root / 'assets.json', {'CHAR_001': {'name': '主角', 'image': 'reference.png',
                                                    'description': 'new costume'}})
        self.assertIn('来源', self.problem())

    def test_late_generation_is_not_adopted_after_source_change(self):
        item = {'shot_id': self.shot['id'], 'shot_signature': fingerprint(self.shot),
                'source_evidence': evidence.source_evidence(self.source, self.episode, self.shot)}
        generated = self.root / 'generated.png'
        generated.write_bytes(png())
        self.image.unlink()
        self.episode['title'] = 'changed while generating'
        save(self.source, self.episode)
        with self.assertRaisesRegex(ValueError, '分镜或参考资产'):
            register(self.source, item, generated)
        self.assertTrue(generated.is_file())
        self.assertNotIn('frame_evidence', read(self.source)['shots'][0])

    def test_real_auto_import_records_valid_evidence(self):
        item = {'shot_id': self.shot['id'], 'shot_signature': fingerprint(self.shot),
                'source_evidence': evidence.source_evidence(self.source, self.episode, self.shot)}
        generated = self.root / 'generated.png'
        generated.write_bytes(png())
        self.image.unlink()
        self.image = register(self.source, item, generated)
        self.episode = read(self.source)
        self.shot = self.episode['shots'][0]
        self.assertEqual(self.problem(), '')
        self.assertTrue(generated.exists())

    def test_malformed_evidence_is_rejected_without_crashing(self):
        self.receipt()
        good = self.shot['frame_evidence']
        broken_values = (
            'text', ['list'],
            dict(good, source='not-a-dict'),
            dict(good, source={'references': 'nope'}),
            dict(good, source={'references': ['row']}),
            dict(good, source={'references': [{'id': 'A'}]}),
            dict(good, expected_size='wide'),
            dict(good, aspect_ratio=['9:16']),
        )
        for broken in broken_values:
            self.shot['frame_evidence'] = copy.deepcopy(broken) if isinstance(broken, dict) else broken
            self.assertIsInstance(self.problem(), str)

    def test_gate_rejects_bad_old_and_stale_images_and_accepts_verified_one(self):
        from stage_parallel import frames_ready
        from stage_completion_service import completion_evidence
        self.receipt()
        with patch('stage_parallel._adopted', return_value=[(self.source, [self.shot])]), \
                patch('stage_parallel.has_run', return_value=True):
            self.assertTrue(frames_ready(self.root)['ok'])
            self.assertTrue(completion_evidence(self.root, 'keyframe')[0])
            self.image.write_bytes(b'\x89PNG\r\n\x1a\ninvalid')
            result = frames_ready(self.root)
            self.assertFalse(result['ok'])
            self.assertFalse(completion_evidence(self.root, 'keyframe')[0])


    def test_seedream_rejection_keeps_frame_and_marks_uncertain(self):
        import keyframe_comfy
        import seedream_api
        with patch.object(seedream_api, 'load_profile',
                          return_value={'model': 'm', 'api_key': 'k', 'base_url': 'http://x'}), \
                patch.object(seedream_api, 'request_image', return_value=png()), \
                patch.object(keyframe_comfy, 'check_shot', return_value=('提示词', [])), \
                patch('keyframe_import.register',
                      side_effect=ValueError('生成期间分镜或参考资产已变化，图片保留但需重新导入确认')):
            message = keyframe_comfy.run_seedream(
                self.source, [{'id': 'SH001'}], {'aspect_ratio': '16:9'}, lambda _text: None)
        record = read(self.root / '首帧任务' / 'seedream_SH001.json')
        self.assertEqual(record['state'], 'uncertain')
        self.assertTrue(Path(record['file']).is_file())
        self.assertIn('未重复提交', message)


if __name__ == '__main__':
    unittest.main()
