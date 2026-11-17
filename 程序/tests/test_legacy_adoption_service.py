# -*- coding: utf-8 -*-
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from agent.core import read, save
from domain.legacy_adoption_service import record_legacy_adoption
from stage_layout import ARCHIVE
from contract.service_contract import SystemError, success


class LegacyAdoptionServiceTests(unittest.TestCase):
    def test_record_publishes_linked_paths_to_the_archive_log(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / '项目'
            linked = [project / 'writing', project / 'storyboard']
            result = record_legacy_adoption(
                project, linked, now='2026-09-28 10:00:00',
                gateway={'publish_json': save, 'make_dir': lambda folder: folder.mkdir(parents=True, exist_ok=True)})
            self.assertTrue(result.ok)
            target = result.data
            self.assertEqual(project / ARCHIVE / 'logs' / '旧目录归位.json', target)
            self.assertEqual({'at': '2026-09-28 10:00:00', 'linked': [str(path) for path in linked]}, read(target))

    def test_io_failures_are_controlled_and_do_not_publish_after_mkdir_failure(self):
        for failing in ('make_dir', 'publish_json'):
            with self.subTest(failing=failing):
                gateway = {'make_dir': Mock(), 'publish_json': Mock()}
                gateway[failing].side_effect = OSError('private-path-detail')
                with self.assertLogs('legacy_adoption_service', level='ERROR'):
                    result = record_legacy_adoption(Path('project'), [], gateway=gateway)
                self.assertIsInstance(result, SystemError)
                self.assertIsNone(result.data)
                self.assertNotIn('private-path-detail', result.reason)
                if failing == 'make_dir':
                    gateway['publish_json'].assert_not_called()

    def test_programming_errors_propagate(self):
        with self.assertRaises(TypeError):
            record_legacy_adoption(Path('project'), [])
        for failing in ('make_dir', 'publish_json'):
            gateway = {'make_dir': Mock(), 'publish_json': Mock()}
            gateway[failing].side_effect = TypeError('bug')
            with self.subTest(failing=failing), self.assertRaises(TypeError):
                record_legacy_adoption(Path('project'), [], gateway=gateway)

    def test_l3_preserves_path_and_rejects_failed_result(self):
        from stage_execution_service import record_stage_legacy_adoption
        target = Path('archive/log.json')
        with patch('domain.legacy_adoption_service.record_legacy_adoption', return_value=success(target)):
            self.assertIs(target, record_stage_legacy_adoption(Path('project'), []))
        with patch('domain.legacy_adoption_service.record_legacy_adoption', return_value=SystemError('保存失败')):
            with self.assertRaisesRegex(ValueError, '保存失败'):
                record_stage_legacy_adoption(Path('project'), [])
