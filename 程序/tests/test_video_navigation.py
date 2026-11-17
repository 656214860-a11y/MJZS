import tempfile
import unittest
from pathlib import Path

from agent.core import save
from infra.file_cache import clear
import video_navigation


class VideoNavigationCacheTests(unittest.TestCase):
    def tearDown(self):
        clear()

    def test_display_reader_observes_atomic_republish(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'config.json'
            save(path, {'model': 'first'})
            self.assertEqual(video_navigation.read_json(path), {'model': 'first'})
            save(path, {'model': 'second'})
            self.assertEqual(video_navigation.read_json(path), {'model': 'second'})

    def test_display_reader_keeps_bad_file_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'broken.json'
            path.write_text('{', encoding='utf-8')
            self.assertEqual(video_navigation.read_json(path), {})


if __name__ == '__main__':
    unittest.main()
