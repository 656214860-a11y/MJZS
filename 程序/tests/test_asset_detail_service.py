import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent.core import read, save
from asset_detail_service import bind_canonical_view, bind_variant_thumbnail


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
        dest = bind_canonical_view(self.project, self.base, 'CHAR_001', 'front', self.source)
        self.assertEqual(dest.read_bytes(), b'png-data')
        row = read(self.index)['CHAR_001']
        self.assertEqual(row['canon_board_views']['front'], 'assets/正典板/CHAR_001_front.png')
        self.assertEqual(row['canonical_board'], 'assets/正典板/CHAR_001_front.png')

    def test_variant_thumbnail_updates_only_target_variant(self):
        dest = bind_variant_thumbnail(self.project, self.base, 'CHAR_001', 'happy', self.source)
        self.assertEqual(dest.name, 'CHAR_001_happy_变体.png')
        rows = read(self.index)['CHAR_001']['state_variants']
        self.assertEqual(rows[0]['reference_image'], 'assets/正典板/CHAR_001_happy_变体.png')

    def test_index_failure_restores_previous_image_and_index(self):
        dest = self.base / 'assets/正典板/CHAR_001_front.png'
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b'old-image')
        old_index = self.index.read_bytes()
        with patch('asset_detail_service.update_fields', side_effect=OSError('index failed')):
            with self.assertRaisesRegex(OSError, 'index failed'):
                bind_canonical_view(self.project, self.base, 'CHAR_001', 'front', self.source)
        self.assertEqual(dest.read_bytes(), b'old-image')
        self.assertEqual(self.index.read_bytes(), old_index)
