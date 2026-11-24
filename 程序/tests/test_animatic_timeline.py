"""离线验证预演合成命令与媒体核验，不调用外部进程。"""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from domain.edit_service import assemble_image_timeline


class AnimaticTimelineTests(unittest.TestCase):
    def render(self, root, info):
        self.commands = []
        def execute(command, **options):
            self.commands.append(command)
            self.assertTrue(options['check'])
            self.assertTrue(options['capture_output'])
            self.assertGreater(options['timeout'], 0)
            return SimpleNamespace(stdout=json.dumps(info))
        return assemble_image_timeline([root / '镜头.png'], [2], root / '临时.wav',
            root / 'animatic.mp4', ffmpeg='ffmpeg', ffprobe='ffprobe',
            write_temporary=lambda path, raw: path.write_bytes(raw), run=execute)

    def test_timeline_maps_audio_and_decodes_before_success(self):
        """REQ-S04-25：拼接后叠加声音、含视频与音频流、总时长匹配且完整解码后才算通过。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = self.render(root, {'streams': [{'codec_type': 'video'}, {'codec_type': 'audio'}],
                                       'format': {'duration': '2'}})
            self.assertEqual(result, root / 'animatic.mp4')
            self.assertEqual(len(self.commands), 4)
            self.assertIn('1:a:0', self.commands[1])
            self.assertIn('-xerror', self.commands[-1])
            self.assertEqual((root / 'animatic_concat.txt').read_text(), "file 'segment_0000.mp4'\n")

    def test_missing_audio_and_wrong_duration_are_rejected(self):
        """REQ-S04-25：缺音频流或总时长与各镜之和相差超过 1 秒即不发布。"""
        for streams, duration in [([{'codec_type': 'video'}], '2'),
                                  ([{'codec_type': 'video'}, {'codec_type': 'audio'}], '20')]:
            with self.subTest(streams=streams, duration=duration), tempfile.TemporaryDirectory() as temporary:
                with self.assertRaisesRegex(ValueError, '核验失败'):
                    self.render(Path(temporary), {'streams': streams, 'format': {'duration': duration}})

    def test_invalid_duration_never_starts_process(self):
        """REQ-S04-25：每镜时长必须有限且在 0–600 秒内，无效输入不得启动编码进程。"""
        def forbidden(*args, **kwargs):
            self.fail('无效输入不应启动进程')
        with self.assertRaises(ValueError):
            assemble_image_timeline(['image.png'], [float('nan')], 'audio.wav', 'out.mp4',
                ffmpeg='ffmpeg', ffprobe='ffprobe', write_temporary=forbidden, run=forbidden)


class MixedAudioRenderTests(unittest.TestCase):
    def test_req_s04_74_76_mixed_audio_runs_injected_command_in_scratch_area(self):
        """REQ-S04-74/76：混音命令由 L3 注入后原样执行，edit_service 不 import animatic_audio。"""
        from domain.edit_service import render_mixed_audio
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / 'mixed.wav'
            commands = []
            def execute(command, **options):
                commands.append(command)
                self.assertTrue(options['check'])
                self.assertTrue(options['capture_output'])
                return SimpleNamespace(stdout='')
            built = []
            def mix(path, total, **kwargs):
                built.append((path, total, kwargs))
                return ['ffmpeg', '-i', 'voice.wav', '-t', str(total), str(path)]
            result = render_mixed_audio(output, 4.5, ffmpeg='ffmpeg', run=execute,
                full_track='track.mp3', dialogue_clips=({'path': 'd1.mp3', 'start_ms': 500},),
                music='bgm.mp3', mix_command=mix)
            self.assertEqual(result, output)
            self.assertEqual(built, [(output, 4.5, {'full_track': 'track.mp3',
                'dialogue_clips': ({'path': 'd1.mp3', 'start_ms': 500},),
                'music': 'bgm.mp3', 'ffmpeg': 'ffmpeg'})])
            self.assertEqual(commands, [['ffmpeg', '-i', 'voice.wav', '-t', '4.5', str(output)]])

    def test_req_s04_76_mixed_audio_requires_l3_injected_command(self):
        """REQ-S04-76：未注入混音命令时拒绝编造 ffmpeg 参数。"""
        from domain.edit_service import render_mixed_audio
        with self.assertRaises(TypeError):
            render_mixed_audio('out.wav', 1.0, ffmpeg='ffmpeg')
