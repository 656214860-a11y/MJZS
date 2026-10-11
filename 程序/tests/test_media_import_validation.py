"""媒体导入的真实解码、失败保全和有界文件发布回归。"""
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent.core import command, copy_file_new, file_hash, save
from agent.media import MediaValidationError, validate_import
from stage_execution_service import import_stage_audio, import_delivery_master, import_animatic_audio


TOOLS = {'ffmpeg': 'D:/Tools/ffmpeg/bin/ffmpeg.exe', 'ffprobe': 'D:/Tools/ffmpeg/bin/ffprobe.exe'}


def wav_bytes():
    pcm = b'\0\0' * 8000
    return (b'RIFF' + struct.pack('<I', 36 + len(pcm)) + b'WAVEfmt '
            + struct.pack('<IHHIIHH', 16, 1, 1, 8000, 16000, 2, 16)
            + b'data' + struct.pack('<I', len(pcm)) + pcm)


class MediaImportValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.media = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.media.cleanup)
        cls.video = Path(cls.media.name) / 'valid.mp4'
        command([TOOLS['ffmpeg'], '-nostdin', '-v', 'error', '-f', 'lavfi', '-i',
                 'color=c=black:s=32x32:r=10:d=1', '-f', 'lavfi', '-i',
                 'sine=frequency=440:sample_rate=8000:duration=1', '-c:v', 'libx264',
                 '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', '-movflags', '+faststart', cls.video])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        save(self.root / 'config.json', TOOLS)
        self.audio = self.root / 'input.wav'
        self.audio.write_bytes(wav_bytes())

    def test_actual_audio_video_and_animatic_import_keep_sources(self):
        for service, source, stage in ((import_stage_audio, self.audio, '11配音与字幕'),
                                       (import_animatic_audio, self.audio, '04分镜预演'),
                                       (import_delivery_master, self.video, '13质检交付')):
            with self.subTest(stage=stage):
                before = file_hash(source)
                result = service(self.root, source)
                self.assertTrue(result.ok, result.reason)
                self.assertTrue(result.data.is_relative_to(self.root / stage))
                self.assertEqual(file_hash(result.data), before)
                self.assertEqual(file_hash(source), before)
        self.assertEqual(list(self.root.rglob('*.tmp')), [])

    def test_fake_and_truncated_files_are_not_published(self):
        broken = [('fake.wav', b'not audio', import_stage_audio),
                  ('fake.mp4', b'not video', import_delivery_master),
                  ('truncated.wav', wav_bytes()[:4000], import_stage_audio),
                  ('truncated.mp4', self.video.read_bytes()[:self.video.stat().st_size // 2], import_delivery_master)]
        for name, data, service in broken:
            with self.subTest(name=name):
                path = self.root / name
                path.write_bytes(data)
                result = service(self.root, path)
                self.assertFalse(result.ok)
                self.assertTrue(result.recoverable)
                self.assertEqual(path.read_bytes(), data)
        self.assertEqual(list((self.root / '11配音与字幕').rglob('*.wav')), [])
        self.assertEqual(list((self.root / '13质检交付').rglob('*.mp4')), [])
        self.assertEqual(list(self.root.rglob('*.tmp')), [])

    def test_only_audio_in_mp4_cannot_be_imported_as_master(self):
        source = self.root / 'only-audio.mp4'
        command([TOOLS['ffmpeg'], '-nostdin', '-v', 'error', '-i', self.audio, '-c:a', 'aac', source])
        result = import_delivery_master(self.root, source)
        self.assertFalse(result.ok)
        self.assertIn('视频', result.reason)

    def test_required_audio_policy_is_explicit(self):
        source = self.root / 'silent.mp4'
        command([TOOLS['ffmpeg'], '-nostdin', '-v', 'error', '-i', self.video, '-an', '-c:v', 'copy', source])
        result = import_delivery_master(self.root, source)
        self.assertFalse(result.ok)
        self.assertIn('必要音轨', result.reason)
        save(self.root / 'config.json', dict(TOOLS, require_audio=False))
        self.assertTrue(import_delivery_master(self.root, source).ok)

    def test_zero_duration_rejected_before_decode(self):
        with patch('agent.media.probe', return_value={'format': {'duration': '0'}, 'streams': [{'codec_type': 'audio'}]}), \
                patch('agent.media.command') as decode:
            with self.assertRaises(MediaValidationError):
                validate_import(self.audio, TOOLS, 'audio')
        decode.assert_not_called()

    def test_album_art_does_not_count_as_a_video_stream(self):
        from agent.media import media_facts
        data = {'format': {'duration': 1}, 'streams': [
            {'codec_type': 'video', 'width': 32, 'height': 32, 'disposition': {'attached_pic': 1}},
            {'codec_type': 'audio'}]}
        with self.assertRaises(MediaValidationError):
            media_facts('video', data)

    def test_existing_target_survives_collision_and_validation_failure(self):
        from project_stages import audio
        folder = audio(self.root)
        folder.mkdir(parents=True)
        existing = folder / 'input_abcdef.wav'
        existing.write_bytes(b'previous-adopted-audio')
        with patch('audio_import_service.uuid.uuid4') as uuid:
            uuid.return_value.hex = 'abcdef123456'
            with self.assertLogs('audio_import_service', level='ERROR'):
                result = import_stage_audio(self.root, self.audio)
        self.assertFalse(result.ok)
        self.assertEqual(existing.read_bytes(), b'previous-adopted-audio')
        self.audio.write_bytes(b'broken')
        result = import_stage_audio(self.root, self.audio)
        self.assertFalse(result.ok)
        self.assertEqual(existing.read_bytes(), b'previous-adopted-audio')
        self.assertEqual(list(self.root.rglob('*.tmp')), [])


class StreamPublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source.bin'
        with self.source.open('wb') as stream:
            for _ in range(5):
                stream.write(b'x' * 1024 * 1024)
        self.target = self.root / 'published.bin'

    def test_no_whole_file_read_and_validate_only_private_copy(self):
        seen = []
        def validate(path):
            seen.append(path)
            self.assertFalse(self.target.exists())
            self.assertNotEqual(path, self.source)
            self.assertEqual(file_hash(path), file_hash(self.source))
            return True
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('整文件读取')):
            copy_file_new(self.target, self.source, validate)
        self.assertEqual(len(seen), 1)
        self.assertEqual(file_hash(self.target), file_hash(self.source))
        self.assertEqual(list(self.root.glob('*.tmp')), [])

    def test_validation_and_publish_failure_keep_existing_and_clean_temp(self):
        self.target.write_bytes(b'old')
        with self.assertRaisesRegex(ValueError, '校验'):
            copy_file_new(self.target, self.source, lambda _: False)
        self.assertEqual(self.target.read_bytes(), b'old')
        with patch('agent.core.os.link', side_effect=OSError('disk failure')), self.assertRaises(OSError):
            copy_file_new(self.target, self.source, lambda _: True)
        self.assertEqual(self.target.read_bytes(), b'old')
        self.assertEqual(list(self.root.glob('*.tmp')), [])

    def test_changed_source_or_temporary_copy_is_rejected(self):
        original_hash = file_hash
        def changed(path):
            if path == self.source:
                self.source.write_bytes(b'replaced')
            return original_hash(path)
        with patch('agent.core.file_hash', side_effect=changed), self.assertRaisesRegex(OSError, '源文件'):
            copy_file_new(self.target, self.source, lambda _: True)
        self.assertFalse(self.target.exists())
        def corrupt(path):
            path.write_bytes(b'different')
            return True
        with self.assertRaisesRegex(OSError, '临时文件'):
            copy_file_new(self.target, self.source, corrupt)
        self.assertFalse(self.target.exists())
        self.assertEqual(list(self.root.glob('*.tmp')), [])

    def test_copy_memory_does_not_grow_with_file_size(self):
        import tracemalloc
        with self.source.open('wb') as stream:
            for _ in range(64):
                stream.write(b'x' * 1024 * 1024)
        tracemalloc.start()
        try:
            copy_file_new(self.target, self.source, lambda _: True)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertLess(peak, 8 * 1024 * 1024)
        self.assertEqual(self.target.stat().st_size, 64 * 1024 * 1024)
        self.assertEqual(file_hash(self.target), file_hash(self.source))


if __name__ == '__main__':
    unittest.main()
