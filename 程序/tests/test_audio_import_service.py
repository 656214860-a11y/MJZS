import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import audio_import_service


class AudioImportServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'input.wav'
        self.source.write_bytes(b'audio bytes')

    def test_imports_audio_to_the_numbered_audio_stage(self):
        def publish(target, data, validate, update_index):
            self.assertTrue(validate(data)); target.write_bytes(data); update_index(target)
        with patch('audio_import_service.uuid.uuid4') as created:
            created.return_value.hex = 'abcdef123456'
            target = audio_import_service.import_audio(self.root, self.source, publish=publish)
        self.assertEqual(target, self.root / '10配音与字幕' / '音频' / 'input_abcdef.wav')
        self.assertEqual(target.read_bytes(), b'audio bytes')
        self.assertTrue(self.source.is_file())

    def test_rejects_empty_or_unsupported_input_before_writing(self):
        empty = self.root / 'empty.mp3'
        empty.touch()
        with self.assertRaisesRegex(ValueError, '音频文件为空'):
            audio_import_service.import_audio(self.root, empty, publish=lambda *_args: None)
        unsupported = self.root / 'input.txt'
        unsupported.write_bytes(b'content')
        with self.assertRaisesRegex(ValueError, 'WAV、MP3、M4A 或 AAC'):
            audio_import_service.import_audio(self.root, unsupported, publish=lambda *_args: None)
        self.assertFalse((self.root / '10配音与字幕').exists())

    def test_accepts_injected_publisher_for_formal_release(self):
        calls = []

        def publish(target, data, validate, update_index):
            calls.append((target, data, validate(data)))
            target.write_bytes(data)
            update_index(target)

        with patch('audio_import_service.uuid.uuid4') as created:
            created.return_value.hex = 'abcdef123456'
            target = audio_import_service.import_audio(self.root, self.source, publish=publish)

        self.assertEqual(target.read_bytes(), b'audio bytes')
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1:], (b'audio bytes', True))
