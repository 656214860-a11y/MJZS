# -*- coding: utf-8 -*-
"""O32：剪辑输出规格来自项目的画幅／分辨率／帧率，预演预览与正式交付分开。"""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import script_contract


class OutputSpecContractTests(unittest.TestCase):
    def test_default_delivery_spec_is_1080_class(self):
        spec = script_contract.resolve_output_spec()
        self.assertEqual(spec['aspect_ratio'], '16:9')
        self.assertEqual(spec['resolution'], '1920x1080')
        self.assertEqual((spec['width'], spec['height']), (1920, 1080))
        self.assertEqual(spec['fps'], 30)

    def test_portrait_square_and_wide_locks_follow_the_project_aspect(self):
        self.assertEqual(script_contract.resolve_output_spec({'aspect_ratio': '9:16'})['resolution'], '1080x1920')
        self.assertEqual(script_contract.resolve_output_spec({'aspect_ratio': '1:1'})['resolution'], '1080x1080')
        self.assertEqual(script_contract.resolve_output_spec({'aspect_ratio': '21:9'})['resolution'], '2520x1080')

    def test_explicit_resolution_and_fps_override_derived_values(self):
        spec = script_contract.resolve_output_spec({'aspect_ratio': '16:9', 'resolution': '1280x720', 'fps': '60'})
        self.assertEqual(spec['resolution'], '1280x720')
        self.assertEqual(spec['fps'], 60)

    def test_bad_values_fall_back_without_raising(self):
        spec = script_contract.resolve_output_spec({'aspect_ratio': 'wide', 'resolution': 'abc', 'fps': 'abc'})
        self.assertEqual(spec['resolution'], '1920x1080')
        self.assertEqual(spec['fps'], 30)
        self.assertEqual(script_contract.resolve_output_spec({'fps': '0'})['fps'], 30)
        self.assertEqual(script_contract.resolve_output_spec({'fps': '300'})['fps'], 30)

    def test_odd_resolution_is_rounded_even_for_h264(self):
        spec = script_contract.resolve_output_spec({'resolution': '1921x1081'})
        self.assertEqual((spec['width'], spec['height']), (1922, 1082))

    def test_preview_keeps_low_resolution_and_project_aspect(self):
        default = script_contract.preview_spec()
        self.assertEqual(default['resolution'], '1280x720')
        self.assertEqual(default['fps'], 24)
        portrait = script_contract.preview_spec({'aspect_ratio': '9:16'})
        self.assertEqual((portrait['width'], portrait['height']), (720, 1280))
        self.assertEqual(portrait['aspect_ratio'], '9:16')

    def test_output_filter_pads_and_never_crops(self):
        """REQ-S12-05：等比缩放（decrease）后居中留边（pad），绝不裁切（无 crop）。"""
        text = script_contract.output_filter(script_contract.resolve_output_spec({'aspect_ratio': '9:16'}))
        self.assertIn('scale=1080:1920:force_original_aspect_ratio=decrease', text)
        self.assertIn('pad=1080:1920:(ow-iw)/2:(oh-ih)/2', text)
        self.assertIn('fps=30', text)
        self.assertNotIn('crop', text)

    def test_overlay_and_loudness_follow_the_spec(self):
        small = script_contract.overlay_metrics({'height': 720})
        large = script_contract.overlay_metrics({'height': 1080})
        self.assertEqual((small['fontsize'], small['x'], small['y']), (28, 30, 30))
        self.assertGreater(large['fontsize'], small['fontsize'])
        self.assertGreater(large['x'], small['x'])
        self.assertEqual(script_contract.loudness_filter(script_contract.resolve_output_spec()),
                         'loudnorm=I=-16:TP=-1.5:LRA=11')

    def test_describe_output_spec_is_one_line(self):
        self.assertEqual(script_contract.describe_output_spec(script_contract.resolve_output_spec()),
                         '1920x1080 · 30fps · 16:9')

    def test_locks_can_declare_resolution_and_fps(self):
        keys = {item['key'] for item in script_contract.PRODUCTION_LOCK_DEFINITIONS}
        self.assertLessEqual({'aspect_ratio', 'resolution', 'fps'}, keys)
        self.assertLessEqual({'输出分辨率', '输出帧率'}, set(script_contract.BRIEF_EXTRACTION_LABELS))


class EngineOutputSpecTests(unittest.TestCase):
    """REQ-S12-05：Studio 的输出规格取自项目制作锁（workflow_lock → resolve_output_spec），
    缺省才用出厂默认；output_spec_text 供界面在导出前显示实际规格。"""

    def test_studio_spec_reads_the_project_lock(self):
        import engine
        with tempfile.TemporaryDirectory() as temporary:
            studio = engine.Studio.__new__(engine.Studio)
            studio.root = Path(temporary)
            with patch('stage_config.workflow_lock', return_value={'aspect_ratio': '9:16'}):
                spec = studio.output_spec()
                text = studio.output_spec_text()
        self.assertEqual((spec['width'], spec['height']), (1080, 1920))
        self.assertEqual(text, '1080x1920 · 30fps · 9:16')

    def test_studio_spec_falls_back_without_a_lock(self):
        import engine
        with tempfile.TemporaryDirectory() as temporary:
            studio = engine.Studio.__new__(engine.Studio)
            studio.root = Path(temporary)
            with patch('stage_config.workflow_lock', return_value={}):
                self.assertEqual(studio.output_spec_text(), '1920x1080 · 30fps · 16:9')


class PreviewAssemblySpecTests(unittest.TestCase):
    def commands_for(self, root, spec):
        from edit_service import assemble_image_timeline
        commands = []
        def execute(command, **options):
            commands.append(command)
            return SimpleNamespace(stdout=json.dumps({
                'streams': [{'codec_type': 'video'}, {'codec_type': 'audio'}], 'format': {'duration': '2'}}))
        image = root / 'shot.png'
        image.write_bytes(b'x')
        assemble_image_timeline([image], [2], root / 'voice.wav', root / 'animatic.mp4',
            ffmpeg='ffmpeg', ffprobe='ffprobe',
            write_temporary=lambda path, raw: path.write_bytes(raw), run=execute, spec=spec)
        return commands[0]

    def test_preview_uses_the_project_aspect_at_low_resolution(self):
        with tempfile.TemporaryDirectory() as temporary:
            command = ' '.join(self.commands_for(Path(temporary), script_contract.preview_spec({'aspect_ratio': '9:16'})))
        self.assertIn('scale=720:1280:force_original_aspect_ratio=decrease', command)
        self.assertIn('-r 24', command)

    def test_preview_defaults_stay_at_1280x720(self):
        with tempfile.TemporaryDirectory() as temporary:
            command = ' '.join(self.commands_for(Path(temporary), None))
        self.assertIn('scale=1280:720:force_original_aspect_ratio=decrease', command)
        self.assertIn('-r 24', command)


class AnimaticForwardingTests(unittest.TestCase):
    def test_build_bundle_forwards_spec_to_assembly(self):
        import animatic_service
        from project_context_factory import project_context
        from stage_execution_service import publish_animatic_bundle
        captured = {}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'storyboard.json'
            source.write_text(json.dumps({'shots': [{'id': 's1', 'prompt': '门边的人', 'duration': 2}]}), encoding='utf-8')
            reference = root / 'ref.png'
            reference.write_bytes(b'reference')
            audio = root / 'voice.wav'
            audio.write_bytes(b'audio')
            def render(workspace, *_args):
                target = workspace / 'image.png'
                target.write_bytes(b'image')
                return target
            def assemble(images, durations, sound, target, **kwargs):
                captured.update(kwargs)
                target.write_bytes(b'video')
                return target
            spec = script_contract.preview_spec({'aspect_ratio': '9:16'})
            result = animatic_service.build_bundle(project_context(root), source, [reference], audio,
                {'ffmpeg': 'stub', 'ffprobe': 'stub'},
                publish=lambda artifacts: publish_animatic_bundle(root, artifacts, validate=lambda _: True),
                write_temporary=lambda path, raw: path.write_bytes(raw), render=render, assemble=assemble,
                spec=spec)
        self.assertTrue(result.ok)
        self.assertEqual(captured.get('spec'), spec)


if __name__ == '__main__':
    unittest.main(verbosity=2)