"""Animatic 的路径、发布与人工确认契约；仅使用临时项目。"""
import json
import tempfile
import unittest
from unittest.mock import Mock, patch
from pathlib import Path

import animatic_service as service
import stage_layout
from pet_bus import STAGES
from stage_path_service import read_dirs, write_dir
from stage_execution_service import publish_animatic_bundle
from project_context_factory import project_context


class AnimaticTests(unittest.TestCase):
    def test_existing_storyboard_prompt_contract_is_supported(self):
        shots = service.shots_of({'shots': [{'id': 'SH001', 'duration': 10, 'video_prompt': '门边的人'}]})
        self.assertEqual(shots[0]['prompt'], '门边的人')
        self.assertEqual(shots[0]['seconds'], 10)

    def test_formal_assets_require_confirmation_and_online_model(self):
        from stage_execution_service import require_formal_asset_generation
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                require_formal_asset_generation(temporary, online_model=True)
            with patch('stage_parallel.evaluate', return_value={'ok': True}):
                with self.assertRaisesRegex(ValueError, '线上 API'):
                    require_formal_asset_generation(temporary, online_model=False)
                require_formal_asset_generation(temporary, online_model=True)

    def test_animatic_skill_tools_open_the_correct_stage(self):
        import skill_tools
        for tool in ('animatic.generate', 'animatic.validate'):
            self.assertEqual(skill_tools.PAGES[tool][0], STAGES.index('animatic'))
            self.assertEqual(skill_tools.status_of(tool), 'page')
        self.assertEqual(skill_tools.PAGES['asset.plan'][0], STAGES.index('assets'))

    def test_generated_bundle_requires_confirmation_and_detects_source_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'storyboard_draft.json'
            source.write_text(json.dumps({'shots': [{'id': 's1', 'prompt': '门边的人', 'duration': 2}]}), encoding='utf-8')
            reference = root / 'reference.png'
            reference.write_bytes(b'reference')
            audio = root / 'temporary.wav'
            audio.write_bytes(b'audio')
            def render(workspace, *_args):
                target = workspace / 'image.png'
                target.write_bytes(b'image')
                return target
            def assemble(images, durations, sound, target, **_kwargs):
                self.assertEqual(durations, [2])
                self.assertEqual(sound, audio)
                self.assertEqual(len(images), 1)
                target.write_bytes(b'video')
                return target
            def publish(artifacts):
                self.assertTrue(service.validate_bundle(artifacts))
                manifest = json.loads(artifacts[service.MANIFEST])
                manifest['confirmed'] = dict.fromkeys(service.CONFIRMATIONS, True)
                forged = dict(artifacts, **{service.MANIFEST: json.dumps(manifest).encode('utf-8')})
                self.assertFalse(service.validate_bundle(forged))
                return publish_animatic_bundle(root, artifacts, validate=lambda _: True)
            result = service.build_bundle(project_context(root), source, [reference], audio,
                {'ffmpeg': 'stub', 'ffprobe': 'stub'}, publish=publish,
                write_temporary=lambda path, raw: path.write_bytes(raw), render=render, assemble=assemble)
            self.assertTrue(result.ok)
            self.assertFalse(service.evidence(root)[0])
            self.assertTrue(service.evidence(root, require_confirmation=False)[0])
            from stage_execution_service import confirm_animatic
            confirm_animatic(root, rhythm=True, duration=True, dialogue_sync=True)
            self.assertTrue(service.evidence(root)[0])
            source.write_text('{}', encoding='utf-8')
            self.assertFalse(service.evidence(root)[0])

    def test_render_failure_never_publishes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'storyboard_draft.json'
            source.write_text(json.dumps({'shots': [{'id': 's1', 'prompt': '草图', 'duration': 1}]}), encoding='utf-8')
            reference = root / 'reference.png'
            reference.write_bytes(b'reference')
            publisher = Mock()
            with self.assertRaisesRegex(RuntimeError, 'unknown submission'):
                service.build_bundle(project_context(root), source, [reference], reference, {},
                    publish=publisher, write_temporary=Mock(),
                    render=Mock(side_effect=RuntimeError('unknown submission')), assemble=Mock())
            publisher.assert_not_called()

    def test_only_known_generation_failures_are_retried(self):
        from comfy_service import ComfyGenerationFailed, ComfySubmissionUncertain
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'storyboard_draft.json'
            source.write_text(json.dumps({'shots': [{'id': 's1', 'prompt': '草图', 'duration': 1}]}), encoding='utf-8')
            reference = root / 'reference.png'
            reference.write_bytes(b'reference')
            for error, count in [(ComfyGenerationFailed('failed'), 3), (ComfySubmissionUncertain('unknown'), 1)]:
                render = Mock(side_effect=error)
                with self.assertRaises((ValueError, ComfySubmissionUncertain)):
                    service.build_bundle(project_context(root), source, [reference], reference,
                        {'retry_attempts': 2}, publish=Mock(), write_temporary=Mock(), render=render, assemble=Mock())
                self.assertEqual(render.call_count, count)

    def test_stage_order_and_layout(self):
        self.assertEqual(STAGES[STAGES.index('storyboard') + 1], 'animatic')
        self.assertEqual(STAGES[STAGES.index('animatic') + 1], 'assets')
        self.assertTrue(stage_layout.validate_stage_contract())

    def test_old_directory_is_only_a_read_candidate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertEqual(write_dir(root, 'assets'), root / '05资产管理')
            self.assertIn(root / '04资产管理', read_dirs(root, 'assets'))
            self.assertFalse((root / '04资产管理').exists())

    def test_shots_require_prompt_duration_and_unique_id(self):
        shot = {'id': 's1', 'prompt': '角色站在门边', 'duration': 2}
        self.assertEqual(service.shots_of({'shots': [shot]})[0]['seconds'], 2)
        for rows in ([], [shot, shot], [dict(shot, duration=0)], [dict(shot, id='../escape')]):
            with self.assertRaises(ValueError):
                service.shots_of({'shots': rows})

    def test_publication_rejects_escape_and_rolls_back_index_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = write_dir(root, 'animatic')
            folder.mkdir()
            manifest = folder / service.MANIFEST
            manifest.write_bytes(b'old')
            with self.assertRaises(ValueError):
                publish_animatic_bundle(root, {service.MANIFEST: b'{}', '../escape': b'x'}, validate=lambda _: True)
            def fail():
                raise RuntimeError('index failure')
            with self.assertRaises(RuntimeError):
                publish_animatic_bundle(root, {service.MANIFEST: b'new'}, validate=lambda _: True, update_index=fail)
            self.assertEqual(manifest.read_bytes(), b'old')
            self.assertFalse((folder / 'animatic_index.json').exists())

    def test_confirmation_cannot_replace_missing_media(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = write_dir(root, 'animatic')
            folder.mkdir()
            (folder / service.MANIFEST).write_text(json.dumps({'kind': 'animatic', 'confirmed':
                dict.fromkeys(service.CONFIRMATIONS, True)}), encoding='utf-8')
            self.assertFalse(service.evidence(root)[0])


if __name__ == '__main__':
    unittest.main()
