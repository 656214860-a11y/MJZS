import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent.core import read, save
from asset_detail_service import bind_canonical_view, bind_variant_thumbnail
from stage_execution_service import bind_asset_canonical_view, bind_asset_variant_thumbnail
from service_contract import SystemError, UserError


class AssetDetailServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'project'
        self.base = self.project / '04资产管理'
        self.index = self.base / 'assets/资产清单/assets.json'
        save(self.project / 'config.json', {'episode_dir': '04资产管理'})
        save(self.index, {'CHAR_001': {'name': '小满', 'state_variants': [{'state_id': 'happy', 'label': '开心'}]}})
        self.source = self.project / 'source.png'
        self.source.write_bytes(b'png-data')

    def tearDown(self):
        self.temp.cleanup()

    def test_canonical_view_copies_and_updates_index(self):
        dest = bind_asset_canonical_view(self.project, self.base, 'CHAR_001', 'front', self.source)
        self.assertEqual(dest.read_bytes(), b'png-data')
        row = read(self.index)['CHAR_001']
        self.assertEqual(row['canon_board_views']['front'], 'assets/正典板/CHAR_001_front.png')
        self.assertEqual(row['canonical_board'], 'assets/正典板/CHAR_001_front.png')

    def test_variant_thumbnail_updates_only_target_variant(self):
        dest = bind_asset_variant_thumbnail(self.project, self.base, 'CHAR_001', 'happy', self.source)
        self.assertEqual(dest.name, 'CHAR_001_happy_变体.png')
        rows = read(self.index)['CHAR_001']['state_variants']
        self.assertEqual(rows[0]['reference_image'], 'assets/正典板/CHAR_001_happy_变体.png')

    def test_index_failure_restores_previous_image_and_index(self):
        dest = self.base / 'assets/正典板/CHAR_001_front.png'
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b'old-image')
        old_index = self.index.read_bytes()
        with patch('asset_detail_service.update_fields', side_effect=OSError('index failed')):
            with self.assertLogs('asset_detail_service', level='ERROR'), self.assertRaisesRegex(ValueError, '资产图片绑定失败'):
                bind_asset_canonical_view(self.project, self.base, 'CHAR_001', 'front', self.source)
        self.assertEqual(dest.read_bytes(), b'old-image')
        self.assertEqual(self.index.read_bytes(), old_index)

    def test_l2_rejects_missing_l3_gateway(self):
        with self.assertRaisesRegex(RuntimeError, '必须由 L3 注入'):
            bind_canonical_view(self.project, self.base, 'CHAR_001', 'front', self.source)

    def test_both_l2_bindings_return_published_paths(self):
        from stage_execution_service import asset_detail_gateway
        for function, view in ((bind_canonical_view, 'front'), (bind_variant_thumbnail, 'happy')):
            with self.subTest(function=function.__name__):
                result = function(self.project, self.base, 'CHAR_001', view, self.source,
                                  gateway=asset_detail_gateway())
                self.assertTrue(result.ok)
                self.assertFalse(result.recoverable)
                self.assertEqual(result.data.read_bytes(), b'png-data')

    def test_invalid_inputs_return_user_error_without_publication(self):
        from stage_execution_service import asset_detail_gateway
        cases = ((bind_canonical_view, '../bad', 'front', self.source),
                 (bind_canonical_view, 'CHAR_001', 'front', self.project / 'missing.png'),
                 (bind_variant_thumbnail, 'CHAR_001', 'missing', self.source))
        old_index = self.index.read_bytes()
        with patch('asset_detail_service.update_fields') as update:
            for function, aid, view, source in cases:
                with self.subTest(aid=aid, view=view, source=source):
                    result = function(self.project, self.base, aid, view, source, gateway=asset_detail_gateway())
                    self.assertIsInstance(result, UserError)
                    self.assertFalse(result.ok)
            update.assert_not_called()
        self.assertEqual(self.index.read_bytes(), old_index)

    def test_io_failures_return_controlled_error_and_do_not_leave_new_image(self):
        from stage_execution_service import asset_detail_gateway
        for function, view in ((bind_canonical_view, 'front'), (bind_variant_thumbnail, 'happy')):
            for point in ('shutil.copy2', 'update_fields'):
                with self.subTest(function=function.__name__, point=point), self.assertLogs('asset_detail_service', level='ERROR'):
                    with patch('asset_detail_service.' + point, side_effect=OSError('private-location')):
                        result = function(self.project, self.base, 'CHAR_001', view, self.source,
                                          gateway=asset_detail_gateway())
                    self.assertIsInstance(result, SystemError)
                    self.assertIsNone(result.data)
                    self.assertNotIn('private-location', result.reason)
                    self.assertFalse(list((self.base / 'assets/正典板').glob('*')))

    def test_programming_errors_propagate_after_rollback(self):
        from stage_execution_service import asset_detail_gateway
        before = self.index.read_bytes()
        for failure in (TypeError('broken'), KeyError('broken'), ValueError('publisher bug')):
            with self.subTest(failure=type(failure).__name__), patch('asset_detail_service.update_fields', side_effect=failure):
                with self.assertRaises(type(failure)):
                    bind_canonical_view(self.project, self.base, 'CHAR_001', 'front', self.source,
                                        gateway=asset_detail_gateway())
            self.assertEqual(self.index.read_bytes(), before)
            self.assertFalse(list((self.base / 'assets/正典板').glob('*')))

    def test_l3_checks_failed_binding_results(self):
        for name, function, view in (('bind_canonical_view', bind_asset_canonical_view, 'front'),
                                     ('bind_variant_thumbnail', bind_asset_variant_thumbnail, 'happy')):
            with self.subTest(name=name), patch('asset_detail_service.' + name, return_value=SystemError('失败')):
                with self.assertRaisesRegex(ValueError, '失败'):
                    function(self.project, self.base, 'CHAR_001', view, self.source)
