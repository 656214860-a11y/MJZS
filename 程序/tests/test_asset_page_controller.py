from __future__ import annotations

import unittest

from orchestrator.asset_page_controller import AssetPageController


class AssetPageControllerTests(unittest.TestCase):
    def setUp(self):
        self.registry = {
            'CHAR_001': {'status': '待导入'},
            'LOC_001': {'status': '已导入'},
            'PROP_001': {'status': '待导入'},
        }

    def test_category_rows_and_default_checks_follow_current_asset_kind(self):
        checks = {}
        controller = AssetPageController(self.registry, checks, 'characters')
        controller.initialize_checks()
        self.assertEqual([asset_id for asset_id, _asset in controller.rows()], ['CHAR_001'])
        self.assertEqual(checks, {'CHAR_001': True})
        self.assertTrue(controller.has_pending())

    def test_checked_ids_and_manual_completed_targets_keep_category_boundary(self):
        checks = {'CHAR_001': True, 'LOC_001': True, 'PROP_001': False}
        controller = AssetPageController(self.registry, checks, 'all')
        selected = controller.checked_ids()
        self.assertEqual(selected, ['CHAR_001', 'LOC_001'])
        self.assertEqual(controller.imported_ids(selected), ['LOC_001'])

    def test_work_ids_prefer_checked_visible_rows_then_selected_row(self):
        checks = {'CHAR_001': True, 'LOC_001': False}
        controller = AssetPageController(self.registry, checks, 'all')
        self.assertEqual(controller.work_ids(['CHAR_001', 'LOC_001'], 'LOC_001'),
                         (['CHAR_001'], 'checked'))
        checks['CHAR_001'] = False
        self.assertEqual(controller.work_ids(['CHAR_001', 'LOC_001'], 'LOC_001'),
                         (['LOC_001'], 'shown'))
