import unittest
from pathlib import Path

from video_source_evidence import submitted_sources


class SubmittedSourcesTests(unittest.TestCase):
    def test_wan_and_seedance_capture_submitted_bytes_not_current_files(self):
        digest = 'sha256:' + 'a' * 64
        white_digest = 'sha256:' + 'b' * 64
        variants = [
            {'input': {'media': [{'type': 'first_frame', 'url': digest},
                                 {'type': 'reference_video', 'url': white_digest}]}},
            {'content': [{'type': 'image_url', 'image_url': {'url': digest}},
                         {'type': 'video_url', 'role': 'reference_video', 'video_url': {'url': white_digest}}]},
        ]
        for preview in variants:
            with self.subTest(preview=preview):
                result = submitted_sources(preview, 'frame.png', {'path': 'white.mp4', 'sha256': 'stale'})
                self.assertEqual(result['first_frame']['sha256'], 'a' * 64)
                self.assertEqual(result['first_frame']['category'], 'image')
                self.assertEqual(result['white_model_reference']['sha256'], 'b' * 64)
                self.assertEqual(result['first_frame']['path'], str(Path('frame.png').resolve()))

    def test_unused_white_is_not_declared_and_invalid_digest_is_rejected(self):
        result = submitted_sources({'input': {'img_url': 'sha256:' + 'c' * 64}}, 'frame.png', {'path': 'unused.mp4'})
        self.assertNotIn('white_model_reference', result)
        with self.assertRaises(ValueError):
            submitted_sources({'input': {'img_url': 'https://unknown'}}, 'frame.png')
