# -*- coding: utf-8 -*-
import tempfile
import unittest
from pathlib import Path

from agent.core import read, save
from legacy_adoption_service import record_legacy_adoption
from stage_layout import ARCHIVE


class LegacyAdoptionServiceTests(unittest.TestCase):
    def test_record_publishes_linked_paths_to_the_archive_log(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / '项目'
            linked = [project / 'writing', project / 'storyboard']
            target = record_legacy_adoption(
                project, linked, now='2026-09-28 10:00:00',
                gateway={'publish_json': save, 'make_dir': lambda folder: folder.mkdir(parents=True, exist_ok=True)})
            self.assertEqual(project / ARCHIVE / 'logs' / '旧目录归位.json', target)
            self.assertEqual({'at': '2026-09-28 10:00:00', 'linked': [str(path) for path in linked]}, read(target))
