# -*- coding: utf-8 -*-
import tempfile
import unittest
from pathlib import Path

from project_stages import audio
from stage_completion_service import completion_evidence, media_output_folders


class CompletionEvidenceTests(unittest.TestCase):
    def test_missing_project_keeps_lightweight_host_compatible(self):
        self.assertEqual(completion_evidence(None, 'keyframe'), (True, ''))

    def test_audio_file_is_verifiable_without_a_tk_desktop(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            folder = audio(root); folder.mkdir(parents=True)
            (folder / 'line.srt').write_text('字幕', encoding='utf-8')
            self.assertEqual(completion_evidence(root, 'audio'), (True, ''))

    def test_video_uses_injected_desktop_adapter_callback(self):
        with tempfile.TemporaryDirectory() as td:
            ok, detail = completion_evidence(Path(td), 'video', lambda: ('digest', False))
            self.assertTrue(ok)
            self.assertIn('全部下载', detail)

    def test_media_output_folders_keeps_delivery_formats_separate(self):
        root = Path('project')
        folders, suffixes = media_output_folders(root, 'delivery')
        self.assertEqual(len(folders), 1)
        self.assertEqual(suffixes, {'.mp4', '.mov', '.mkv', '.zip'})


if __name__ == '__main__':
    unittest.main()
