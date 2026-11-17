# -*- coding: utf-8 -*-
"""O34：交接包可离线校验（清单＋文件摘要＋覆盖与缺项如实标注）。"""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

import file_cache
from domain.handoff_service import BUNDLE_MANIFEST_NAME, verify_manifest
from stage_execution_service import publish_handoff_bundle, verify_handoff_bundle
from domain.handoff_service import publish_bundle

SUBTITLE = '1\n00:00:00,000 --> 00:00:03,000\n你好\n'.encode('utf-8')


def _build_bundle(root):
    (root / 'clip.mp4').write_bytes(b'clip-data')
    shot1 = {'id': 'SH001', 'duration': 3}
    shot2 = {'id': 'SH002', 'duration': 4}
    rows = [(shot1, {'file': 'clip.mp4', 'version': 1, 'review': 'pass', 'qc_pass': True})]
    result = publish_bundle(root, [shot1, shot2], rows, subtitle=SUBTITLE, publish=publish_handoff_bundle)
    assert result.ok, result.reason
    return result.data


class ManifestBuildTests(unittest.TestCase):
    """REQ-S12-14：交接包含 NNN_<镜头>.mp4 编号视频、镜头顺序.json、导入剪映说明.txt
    与交接包清单.json；清单记录文件摘要与镜头覆盖（缺镜不补齐、如实标注）。"""

    def test_manifest_records_files_summary_and_coverage(self):
        with tempfile.TemporaryDirectory() as folder:
            out = _build_bundle(Path(folder))
            manifest = json.loads((out / BUNDLE_MANIFEST_NAME).read_text(encoding='utf-8'))
            self.assertEqual(manifest['kind'], 'media')
            self.assertEqual(manifest['label'], '素材交接包')
            self.assertEqual(manifest['shots'],
                             {'included': ['SH001'], 'expected': 2, 'missing': ['SH002']})
            self.assertTrue(manifest['subtitle'])
            self.assertEqual([item['shot'] for item in manifest['sources']], ['SH001'])
            self.assertEqual(manifest['sources'][0]['version'], 1)
            names = [item['name'] for item in manifest['files']]
            self.assertNotIn(BUNDLE_MANIFEST_NAME, names, '清单不自列')
            entry = next(item for item in manifest['files'] if item['name'] == '001_SH001.mp4')
            self.assertEqual(entry['size'], len(b'clip-data'))
            self.assertEqual(entry['sha256'], file_cache.file_digest(out / '001_SH001.mp4'))
            self.assertEqual(manifest['count'], len(manifest['files']))


class OfflineVerifyTests(unittest.TestCase):
    """REQ-S12-14：「校验交接包」离线按清单核对文件与摘要；声明含字幕却没有对白.srt 即失败。"""

    def test_intact_bundle_passes_and_reports_declared_missing(self):
        with tempfile.TemporaryDirectory() as folder:
            out = _build_bundle(Path(folder))
            report = verify_handoff_bundle(out)
            self.assertTrue(report['ok'], report['problems'])
            self.assertEqual(report['problems'], [])
            self.assertEqual(report['missing'], ['SH002'])
            self.assertEqual(report['label'], '素材交接包')
            self.assertGreater(report['count'], 0)

    def test_missing_changed_and_resized_files_all_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            video = _build_bundle(Path(folder)) / '001_SH001.mp4'
            video.unlink()
            report = verify_handoff_bundle(video.parent)
            self.assertFalse(report['ok'])
            self.assertIn('文件缺失或读不动：001_SH001.mp4', report['problems'])
        with tempfile.TemporaryDirectory() as folder:
            video = _build_bundle(Path(folder)) / '001_SH001.mp4'
            video.write_bytes(b'CLIP-DATA')          # 同长度、不同内容
            report = verify_handoff_bundle(video.parent)
            self.assertFalse(report['ok'])
            self.assertIn('文件内容与清单不符：001_SH001.mp4', report['problems'])
        with tempfile.TemporaryDirectory() as folder:
            video = _build_bundle(Path(folder)) / '001_SH001.mp4'
            video.write_bytes(b'clip')               # 长度不同
            report = verify_handoff_bundle(video.parent)
            self.assertFalse(report['ok'])
            self.assertIn('文件大小不符：001_SH001.mp4', report['problems'])

    def test_verification_refuses_entries_outside_the_bundle(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / '包'
            out.mkdir()
            (Path(folder) / 'evil.txt').write_bytes(b'x')
            (out / BUNDLE_MANIFEST_NAME).write_text(json.dumps(
                {'label': '素材交接包', 'files': [{'name': '../evil.txt', 'size': 1, 'sha256': 'x'}]},
                ensure_ascii=False), encoding='utf-8')
            report = verify_handoff_bundle(out)
            self.assertFalse(report['ok'])
            self.assertIn('文件缺失或读不动：../evil.txt', report['problems'])

    def test_missing_or_broken_manifest_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            empty = Path(folder) / '空包'
            empty.mkdir()
            report = verify_handoff_bundle(empty)
            self.assertFalse(report['ok'])
            self.assertIn('缺少交接包清单', report['problems'][0])
        with tempfile.TemporaryDirectory() as folder:
            broken = Path(folder) / '坏包'
            broken.mkdir()
            (broken / BUNDLE_MANIFEST_NAME).write_bytes(b'{ broken')
            report = verify_handoff_bundle(broken)
            self.assertFalse(report['ok'])
            self.assertIn('读不出来或格式坏了', report['problems'][0])


class ManifestRuleTests(unittest.TestCase):
    def _probe(self, name):
        return 5, 'abc'

    def test_claims_complete_but_shot_missing_fails(self):
        report = verify_manifest({'files': [{'name': 'a', 'size': 5, 'sha256': 'abc'}],
                                  'shots': {'included': ['SH001'], 'expected': 2, 'missing': []}},
                                 self._probe)
        self.assertFalse(report['ok'])
        self.assertIn('清单声明镜头齐全，却只记录了 1/2 镜', report['problems'])

    def test_declared_missing_is_not_a_failure(self):
        report = verify_manifest({'files': [{'name': 'a', 'size': 5, 'sha256': 'abc'}],
                                  'shots': {'included': ['SH001'], 'expected': 2, 'missing': ['SH002']}},
                                 self._probe)
        self.assertTrue(report['ok'], report['problems'])
        self.assertEqual(report['missing'], ['SH002'])

    def test_declared_subtitle_without_file_fails(self):
        report = verify_manifest({'files': [{'name': 'a', 'size': 5, 'sha256': 'abc'}],
                                  'subtitle': True}, self._probe)
        self.assertFalse(report['ok'])
        self.assertIn('清单声明含字幕，包里却没有对白.srt', report['problems'])

    def test_empty_and_malformed_manifests_fail(self):
        self.assertFalse(verify_manifest(None, self._probe)['ok'])
        self.assertIn('清单没有记录任何文件', verify_manifest({'files': []}, self._probe)['problems'])


if __name__ == '__main__':
    unittest.main()
