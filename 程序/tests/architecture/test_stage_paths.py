from __future__ import annotations

from datetime import date
from pathlib import Path
import tempfile
import unittest

import stage_layout
from contract import stage_path_service


class StagePathServiceTests(unittest.TestCase):
    def test_every_runtime_stage_writes_to_its_numbered_stage_root(self) -> None:
        """新写路径只有阶段服务能决定，绝不能回到 legacy 英文目录。"""
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw)
            for _folder, stage, _name, _purpose, _inputs, _outputs in stage_layout.STAGES:
                target = stage_path_service.write_dir(project, stage)
                self.assertEqual(target.parent, project)
                self.assertIn(target.name, stage_layout.names())
                self.assertNotIn(target.name, {'writing', 'episode', 'storyboard', 'assets'})

    def test_legacy_paths_are_read_only_and_expire(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw)
            historic = stage_path_service.legacy_read_dirs(project, 'script', date(2027, 3, 31))
            self.assertEqual(historic, (project / 'writing',))
            self.assertEqual(stage_path_service.legacy_read_dirs(project, 'script', date(2027, 4, 1)), ())
            roots = stage_path_service.read_dirs(project, 'script', date(2027, 3, 31))
            self.assertEqual(roots[0], stage_path_service.write_dir(project, 'script'))
            self.assertEqual(roots[1:], historic)

    def test_unknown_stage_never_creates_an_unregistered_path(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            with self.assertRaises(ValueError):
                stage_path_service.write_dir(Path(raw), 'unregistered-stage')
