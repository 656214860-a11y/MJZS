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
        from stage_execution_service import project_context, publish_stage_bytes
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'project'; root.mkdir()
            source = Path(folder) / 'master.mp4'; source.write_bytes(b'video')
            result = import_final_master(project_context(root), source, publish=publish_stage_bytes)
            self.assertTrue(result.ok)
            self.assertEqual(result.data.parent.name, '12质检交付')

    def test_asset_project_services_accept_injected_context(self):
        from asset_batch_service import auto_settings
        from asset_batch_state_service import ledger_path, read_ledger
        from asset_context import library_dir
        from asset_generated_import_service import pending_generated
        from stage_execution_service import project_context
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'project'; root.mkdir()
            context = project_context(root)
            (root / 'config.json').write_text('{}', encoding='utf-8')
            ledger = root / 'workflows' / '资产批量记录.json'
            ledger.parent.mkdir()
            ledger.write_text('{"CHAR_001": {}}', encoding='utf-8')
            self.assertEqual(ledger_path(context=context), ledger)
            self.assertEqual(read_ledger(context=context), {'CHAR_001': {}})
            self.assertEqual(library_dir(context=context), root / '04资产管理')
            self.assertEqual(auto_settings(context=context), {})
            self.assertEqual(pending_generated(None, root / '04资产管理', context=context), [])
