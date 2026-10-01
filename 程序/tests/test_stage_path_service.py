from datetime import date
from pathlib import Path
import tempfile
import unittest

import stage_path_service as paths


class StagePathServiceTests(unittest.TestCase):
    def test_new_writes_use_numbered_stage_directory(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(paths.write_dir(td, 'script'), Path(td) / '01剧本准备')
            self.assertEqual(paths.write_dir(td, 'structure'), Path(td) / '02剧本结构')
            self.assertNotIn(Path(td) / 'writing', paths.read_dirs(td, 'script')[:1])

    def test_old_writing_is_read_only_during_compatibility_window(self):
        with tempfile.TemporaryDirectory() as td:
            legacy = Path(td) / 'writing'
            self.assertIn(legacy, paths.legacy_read_dirs(td, 'script', today=date(2026, 9, 26)))
            self.assertEqual(paths.legacy_read_dirs(td, 'script', today=date(2027, 4, 1)), ())

    def test_unknown_stage_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                paths.write_dir(td, 'unknown')
