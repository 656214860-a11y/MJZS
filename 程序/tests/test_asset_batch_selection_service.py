import unittest

from asset_batch_selection_service import initial_excluded, pending_rows, scope_label, selectable_rows


class AssetBatchSelectionServiceTests(unittest.TestCase):
    def setUp(self):
        self.rows = {
            'CHAR_001': {'status': '待生成'},
            'LOC_001': {'status': '已导入'},
            'PROP_001': {'status': '待生成'},
        }

    def test_selectable_rows_filters_kind_and_imported_assets(self):
        self.assertEqual([aid for aid, _asset in selectable_rows(self.rows, {'CHAR', 'LOC'})], ['CHAR_001'])

    def test_pending_rows_excludes_unchecked_assets_without_mutating_input(self):
        excluded = {'CHAR_001'}
        self.assertEqual(pending_rows(self.rows, {'CHAR', 'PROP'}, excluded), [('PROP_001', self.rows['PROP_001'])])
        self.assertEqual(excluded, {'CHAR_001'})

    def test_scope_labels_cover_every_supported_scope(self):
        self.assertEqual(scope_label('all', []), '全部资产')
        self.assertEqual(scope_label('adopted', ['a', 'b']), '已采用的 2 份分镜')
        self.assertEqual(scope_label('current', [], 'EP001'), '当前分镜 EP001')

    def test_workflow_preselection_excludes_only_unselected_ids(self):
        self.assertEqual(initial_excluded(self.rows, 'workflow', ['CHAR_001']), {'LOC_001', 'PROP_001'})
        self.assertEqual(initial_excluded(self.rows, 'comfy', ['CHAR_001']), set())
