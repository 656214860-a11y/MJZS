from datetime import date
from pathlib import Path
import tempfile
import unittest

from contract import stage_layout
from contract import stage_path_service as paths


class StagePathServiceTests(unittest.TestCase):
    def test_new_writes_use_numbered_stage_directory(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(paths.write_dir(td, 'script'), Path(td) / '01剧本准备')
            self.assertEqual(paths.write_dir(td, 'structure'), Path(td) / '02剧本结构')
            self.assertNotIn(Path(td) / 'writing', paths.read_dirs(td, 'script')[:1])

    def test_stage_aliases_resolve_like_canonical_ids(self):
        """历史阶段键拼写与规范 id 走同一目录口径；别名事实只在 stage_layout 维护一份。"""
        canonical = {row[1] for row in stage_layout.STAGES}
        for alias, stage_id in stage_layout.STAGE_ALIASES.items():
            self.assertIn(stage_id, canonical, alias + ' 必须指向规范阶段 id')
            with tempfile.TemporaryDirectory() as td:
                self.assertEqual(paths.write_dir(td, alias), paths.write_dir(td, stage_id))
                self.assertEqual(paths.read_dirs(td, alias), paths.read_dirs(td, stage_id))
                self.assertEqual(paths.legacy_read_dirs(td, alias, today=date(2026, 9, 26)),
                                 paths.legacy_read_dirs(td, stage_id, today=date(2026, 9, 26)))
        self.assertEqual(stage_layout.canonical_stage_id('structure'), 'script_structure')
        self.assertEqual(stage_layout.canonical_stage_id('frames'), 'keyframe')
        self.assertEqual(stage_layout.canonical_stage_id('editing'), 'edit')
        self.assertEqual(stage_layout.canonical_stage_id('script'), 'script')
        self.assertIsNone(stage_layout.canonical_stage_id('00_script'), '目录名别名不进入阶段键口径')
        self.assertIsNone(stage_layout.canonical_stage_id('unknown'))

    def test_old_writing_is_read_only_during_compatibility_window(self):
        with tempfile.TemporaryDirectory() as td:
            legacy = Path(td) / 'writing'
            self.assertIn(legacy, paths.legacy_read_dirs(td, 'script', today=date(2026, 9, 26)))
            self.assertEqual(paths.legacy_read_dirs(td, 'script', today=date(2027, 4, 1)), ())

    def test_unknown_stage_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                paths.write_dir(td, 'unknown')
