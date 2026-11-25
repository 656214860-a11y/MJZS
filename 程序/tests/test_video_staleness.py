# -*- coding: utf-8 -*-
"""视频输入指纹与过期判定：镜头内容、首帧、参考资产同口径；历史无签名显式无法判定。"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
os.chdir(HERE)

from domain import video_staleness


class VideoStalenessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.source = self.root / 'episode.json'
        self.frame = self.root / 'frames/SH001.png'
        self.frame.parent.mkdir(parents=True)
        self.frame.write_bytes(b'frame-v1')
        self.asset_image = self.root / 'asset.png'
        self.asset_image.write_bytes(b'asset-v1')
        (self.root / 'assets.json').write_text(json.dumps({
            'CHAR_001': {'name': '阿黎', 'image': 'asset.png', 'description': '银发'}
        }, ensure_ascii=False), encoding='utf-8')
        self.shot = {'id': 'SH001', 'duration': 5, 'characters': ['CHAR_001'],
                     'video_prompt': '阿黎转身', 'frame': 'frames/SH001.png',
                     'upload_assets': True}
        self.source.write_text(json.dumps({'shots': [self.shot]}, ensure_ascii=False), encoding='utf-8')

    def signature(self, backend='cloud'):
        return video_staleness.input_signature(self.source, self.shot, backend)

    def version(self, **values):
        backend = values.pop('backend', 'cloud')
        row = {'version': 1, 'state': 'downloaded', 'review': 'pending',
               'file': 'data/SH001/v001/SH001.mp4',
               video_staleness.INPUT_SIGNATURE_FIELD: self.signature(backend)}
        if backend == 'comfy':
            row['backend'] = 'comfy'
        row.update(values)
        return row

    def video_file(self):
        path = self.root / 'data/SH001/v001/SH001.mp4'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'video')
        return path

    def test_same_inputs_keep_same_signature(self):
        first = self.signature()
        self.assertEqual(first, self.signature())
        self.assertFalse(video_staleness.version_is_stale(self.source, self.shot, self.version()))

    def test_display_only_storyboard_title_does_not_mark_stale(self):
        row = self.version()
        self.shot['title'] = '新的展示标题'
        self.source.write_text(json.dumps({'shots': [self.shot]}, ensure_ascii=False), encoding='utf-8')
        self.assertFalse(video_staleness.version_is_stale(self.source, self.shot, row))

    def test_explicit_defaults_do_not_mark_stale(self):
        row = self.version()
        self.shot['generate_audio'] = True
        self.shot['upload_assets'] = True
        self.shot['upload_asset_ids'] = ['CHAR_001']
        self.assertFalse(video_staleness.version_is_stale(self.source, self.shot, row))

    def test_video_prompt_change_marks_stale(self):
        row = self.version()
        self.shot['video_prompt'] = '阿黎停下'
        self.assertTrue(video_staleness.version_is_stale(self.source, self.shot, row))

    def test_asset_rename_and_text_edit_do_not_mark_video_stale(self):
        row = self.version()
        rows = json.loads((self.root / 'assets.json').read_text(encoding='utf-8'))
        rows['CHAR_001']['name'] = '新名字'
        rows['CHAR_001']['description'] = '文字设定改过但图片未变'
        (self.root / 'assets.json').write_text(json.dumps(rows, ensure_ascii=False), encoding='utf-8')
        self.assertFalse(video_staleness.version_is_stale(self.source, self.shot, row))

    def test_frame_content_change_marks_stale_but_same_bytes_do_not(self):
        row = self.version()
        self.frame.write_bytes(b'frame-v1')
        self.assertFalse(video_staleness.version_is_stale(self.source, self.shot, row))
        self.frame.write_bytes(b'frame-version-2')
        self.assertTrue(video_staleness.version_is_stale(self.source, self.shot, row))

    def test_selected_asset_image_change_marks_stale(self):
        row = self.version()
        self.asset_image.write_bytes(b'asset-version-2')
        self.assertTrue(video_staleness.version_is_stale(self.source, self.shot, row))

    def test_unselected_cloud_asset_change_does_not_mark_stale(self):
        other = self.root / 'other.png'
        other.write_bytes(b'other-v1')
        rows = json.loads((self.root / 'assets.json').read_text(encoding='utf-8'))
        rows['PROP_002'] = {'name': '纸伞', 'image': 'other.png'}
        (self.root / 'assets.json').write_text(json.dumps(rows, ensure_ascii=False), encoding='utf-8')
        self.shot['props'] = ['PROP_002']
        self.shot['upload_asset_ids'] = ['CHAR_001']
        row = self.version()
        other.write_bytes(b'other-v2')
        self.assertFalse(video_staleness.version_is_stale(self.source, self.shot, row))
        self.asset_image.write_bytes(b'asset-version-2')
        self.assertTrue(video_staleness.version_is_stale(self.source, self.shot, row))

    def test_comfy_uses_local_selection_not_cloud_selection(self):
        self.shot['local_asset_ids'] = []
        row = self.version(backend='comfy')
        self.asset_image.write_bytes(b'asset-version-2')
        self.assertFalse(video_staleness.version_is_stale(self.source, self.shot, row))
        self.shot['local_asset_ids'] = ['CHAR_001']
        self.assertTrue(video_staleness.version_is_stale(self.source, self.shot, row))

    def test_legacy_version_without_signature_is_unknown_not_current(self):
        self.video_file()
        row = self.version()
        row.pop(video_staleness.INPUT_SIGNATURE_FIELD)
        row['signature'] = '0' * 64
        self.assertFalse(video_staleness.version_is_stale(self.source, self.shot, row))
        self.assertEqual(video_staleness.version_status(self.source, self.shot, row, self.root),
                         video_staleness.STATUS_LEGACY_UNKNOWN)

    def test_status_distinguishes_missing_stale_revise_and_current(self):
        row = self.version()
        self.assertEqual(video_staleness.version_status(self.source, self.shot, row, self.root),
                         video_staleness.STATUS_MISSING)
        self.video_file()
        self.assertEqual(video_staleness.version_status(self.source, self.shot, row, self.root),
                         video_staleness.STATUS_CURRENT)
        self.frame.write_bytes(b'frame-version-2')
        self.assertEqual(video_staleness.version_status(self.source, self.shot, row, self.root),
                         video_staleness.STATUS_STALE)
        row['review'] = 'revise'
        self.assertEqual(video_staleness.version_status(self.source, self.shot, row, self.root),
                         video_staleness.STATUS_REVISE)

    def test_stale_shots_reads_current_storyboard_and_latest_downloaded_version(self):
        row = self.version()
        versions = {'SH001': [row]}
        self.assertEqual(video_staleness.stale_shots(self.source, {'SH001'}, versions), [])
        self.shot['duration'] = 6
        self.source.write_text(json.dumps({'shots': [self.shot]}, ensure_ascii=False), encoding='utf-8')
        self.assertEqual(video_staleness.stale_shots(self.source, {'SH001'}, versions), ['SH001'])


if __name__ == '__main__':
    unittest.main()
