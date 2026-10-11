import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class DeliveryImportTests(unittest.TestCase):
    def test_imports_video_to_delivery_and_keeps_source(self):
        from stage_execution_service import import_delivery_master, project_context
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'project'; root.mkdir()
            source = Path(folder) / 'master.mp4'; source.write_bytes(b'video')
            with patch('agent.media.validate_import', return_value={'decoded': True}):
                result = import_delivery_master(root, source)
            self.assertTrue(result.ok)
            target = result.data
            self.assertEqual(target.parent, project_context(root).stage_resolver('delivery'))
            self.assertEqual(target.read_bytes(), b'video')
            self.assertTrue(source.is_file())

    def test_rejects_non_video_or_empty_source(self):
        from stage_execution_service import import_delivery_master
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'project'; root.mkdir()
            empty = Path(folder) / 'empty.mp4'; empty.write_bytes(b'')
            other = Path(folder) / 'other.txt'; other.write_bytes(b'x')
            for source in (empty, other):
                result = import_delivery_master(root, source)
                self.assertFalse(result.ok)
                self.assertTrue(result.recoverable)
                self.assertIn('请选择' if source == other else '为空', result.reason)

    def test_accepts_injected_publisher_for_formal_release(self):
        from delivery_import_service import import_final_master
        from stage_execution_service import project_context
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'project'; root.mkdir()
            source = Path(folder) / 'master.mp4'; source.write_bytes(b'video')
            calls = []

            def publish(target, source):
                calls.append((target, source))
                target.write_bytes(source.read_bytes())

            result = import_final_master(project_context(root), source, publish=publish)
            self.assertTrue(result.ok)
            target = result.data
            self.assertEqual(target.parent, project_context(root).stage_resolver('delivery'))
            self.assertEqual(target.read_bytes(), b'video')
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][1:], (source,))

    def test_filesystem_failure_is_a_non_displayable_system_result(self):
        from service_contract import SystemError
        from stage_execution_service import import_delivery_master
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'project'; root.mkdir()
            source = Path(folder) / 'master.mp4'; source.write_bytes(b'video')
            with patch.object(Path, 'is_file', side_effect=OSError('介质不可读')):
                result = import_delivery_master(root, source)
        self.assertIsInstance(result, SystemError)
        self.assertFalse(result.ok)
        self.assertTrue(result.recoverable)

    def test_rejects_missing_l3_publisher(self):
        from delivery_import_service import import_final_master
        from stage_execution_service import project_context
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'project'; root.mkdir()
            source = Path(folder) / 'master.mp4'; source.write_bytes(b'video')
            with self.assertRaisesRegex(TypeError, 'L3'):
                import_final_master(project_context(root), source)
