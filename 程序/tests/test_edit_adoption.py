# -*- coding: utf-8 -*-
"""O33：剪辑／交付统一采用版本、粗剪覆盖率与可恢复的成片发布清单。"""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

import engine
from engine import (ADOPT_MISSING, ADOPT_REPLACED, ADOPT_UNAPPROVED, adoption_summary,
                    adopted_edit_version, read_edit_bundle)


def _version(number, *, review='pass', state='downloaded', qc_pass=True, file=None, sha256=''):
    return {'version': number, 'review': review, 'state': state, 'qc_pass': qc_pass,
            'file': file or ('episode/videos/SH001_v%d.mp4' % number), 'sha256': sha256}


class AdoptedVersionTests(unittest.TestCase):
    """「最新」和「采用」要分开：界面显示的采用版必须与真实成片来源同一版。"""

    def test_newest_failing_version_does_not_replace_the_adopted_one(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            target = root / 'episode' / 'videos' / 'SH001_v1.mp4'
            target.parent.mkdir(parents=True)
            target.write_bytes(b'v1')
            good = _version(1, file='episode/videos/SH001_v1.mp4', sha256=engine.file_hash(target))
            bad = _version(2, review='pending', qc_pass=False, file='episode/videos/SH001_v2.mp4')
            self.assertEqual(adopted_edit_version([good, bad], root), (good, ''))
            summary = adoption_summary(root, [good, bad])
            self.assertIs(summary['adopted'], good)
            self.assertIs(summary['latest'], bad)
            self.assertFalse(summary['latest_is_adopted'])
            self.assertIs(summary['source'], good)

    def test_missing_and_replaced_files_are_not_adopted(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'episode' / 'videos').mkdir(parents=True)
            missing = _version(1, file='episode/videos/gone.mp4', sha256='x')
            self.assertEqual(adopted_edit_version([missing], root), (None, ADOPT_MISSING))
            replaced = root / 'episode' / 'videos' / 'SH001_v1.mp4'
            replaced.write_bytes(b'new')
            stale = _version(1, file='episode/videos/SH001_v1.mp4', sha256='old')
            self.assertEqual(adopted_edit_version([stale], root), (None, ADOPT_REPLACED))

    def test_an_unapproved_only_shot_reports_unapproved(self):
        pending = _version(1, review='pending', qc_pass=False)
        self.assertEqual(adopted_edit_version([pending], Path('.')), (None, ADOPT_UNAPPROVED))
        summary = adoption_summary(Path('.'), [pending])
        self.assertIsNone(summary['adopted'])
        self.assertEqual(summary['reason_text'], '尚未验收')
        self.assertIs(summary['source'], pending)
        self.assertFalse(summary['latest_is_adopted'])


class EditBundleTests(unittest.TestCase):
    """成片＋质检＋来源清单先合成一份可恢复清单，索引任一份写失败都还能核对来源。"""

    def _publish(self, out):
        master = out / 'MASTER.mp4'
        master.write_bytes(b'film')
        report = {'errors': [], 'output_spec': '1920x1080@30',
                  'coverage': {'included': ['SH001', 'SH002'], 'expected': 3, 'duration': 10.0,
                               'skipped': ['SH003 缺少已下载、质检及验收通过的视频']}}
        chosen = [({'id': 'SH001'}, {'version': 1, 'sha256': 'a'}, Path('x')),
                  ({'id': 'SH002'}, {'version': 2, 'sha256': 'b'}, Path('y'))]
        engine.Studio.publish_edit_bundle(None, out, master, report, chosen)

    def test_bundle_records_the_actual_overlay_font_digest(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td); master = out / 'MASTER.mp4'; master.write_bytes(b'film')
            font = out / 'font.ttc'; font.write_bytes(b'test-only font fixture')
            chosen = [({'id': 'S01', 'post_overlay': 'title'}, {'version': 1, 'sha256': 'source'}, Path('clip'))]
            engine.Studio.publish_edit_bundle(None, out, master, {}, chosen)
            bundle = json.loads((out / 'edit_bundle.json').read_text(encoding='utf-8'))
            self.assertEqual(bundle['fonts'], [{'path': 'font.ttc', 'sha256': engine.file_hash(font)}])

    def test_bundle_binds_master_and_indexes(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            self._publish(out)
            bundle = json.loads((out / 'edit_bundle.json').read_text(encoding='utf-8'))
            self.assertEqual(bundle['master'], 'MASTER.mp4')
            self.assertEqual(bundle['master_sha256'], engine.file_hash(out / 'MASTER.mp4'))
            self.assertEqual([item['shot'] for item in bundle['manifest']], ['SH001', 'SH002'])
            self.assertEqual(bundle['coverage']['included'], ['SH001', 'SH002'])
            index = json.loads((out / 'edit_manifest.json').read_text(encoding='utf-8'))
            self.assertEqual([item['shot'] for item in index], ['SH001', 'SH002'])

    def test_bundle_recovers_source_when_index_write_failed(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            self._publish(out)
            (out / 'qc.json').unlink()          # 第二份文件没写成功
            recovered = read_edit_bundle(out)
            self.assertEqual(recovered['master'], 'MASTER.mp4')
            self.assertEqual([item['shot'] for item in recovered['manifest']], ['SH001', 'SH002'])
            self.assertEqual(recovered['coverage']['expected'], 3)

    def test_legacy_index_still_reads(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            (out / 'edit_manifest.json').write_text(
                json.dumps([{'shot': 'SH001', 'version': 1}], ensure_ascii=False), encoding='utf-8')
            recovered = read_edit_bundle(out)
            self.assertTrue(recovered['legacy'])
            self.assertEqual(recovered['master'], 'MASTER.mp4')
            self.assertEqual(recovered['manifest'], [{'shot': 'SH001', 'version': 1}])

    def test_empty_directory_has_no_bundle(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(read_edit_bundle(Path(td)))


if __name__ == '__main__':
    unittest.main()
