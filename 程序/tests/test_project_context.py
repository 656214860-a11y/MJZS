import tempfile
import unittest
from pathlib import Path


class ProjectContextTests(unittest.TestCase):
    def test_l3_builds_frozen_context_with_resolved_stage_path(self):
        from stage_execution_service import project_context
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'project'; root.mkdir()
            settings = {'model': 'test'}
            context = project_context(root, settings_snapshot=settings, cache='cache')
            settings['model'] = 'changed'
            self.assertEqual(context.root, root)
            self.assertEqual(context.stage_resolver('delivery').name, '12质检交付')
            self.assertEqual(context.settings_snapshot, {'model': 'test'})
            self.assertEqual(context.cache, 'cache')

    def test_delivery_service_consumes_context_not_project_root(self):
        from delivery_import_service import import_final_master
        from stage_execution_service import project_context
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'project'; root.mkdir()
            source = Path(folder) / 'master.mp4'; source.write_bytes(b'video')
            result = import_final_master(project_context(root), source)
            self.assertTrue(result.ok)
            self.assertEqual(result.data.parent.name, '12质检交付')
