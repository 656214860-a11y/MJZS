# -*- coding: utf-8 -*-
"""来源账本：区分「源仍在」与「源仍是这一版」。"""
import json
import tempfile
import unittest
from pathlib import Path

from contract import artifact_lineage as lineage


class LineageStatusTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / '项目'
        self.root.mkdir(parents=True)
        self.addCleanup(self._tmp.cleanup)

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    def test_same_path_content_change_is_stale_but_still_available(self):
        """源同路径内容变了只标过期，不隐藏、不改写用户成品。"""
        source = self.write('01剧本准备/原稿.md', '第一版')
        artifact = self.write('02剧本结构/p_结构剧本_正稿.md', '# 结构剧本')
        lineage.record(self.root, artifact, source, '结构剧本')
        self.assertEqual(lineage.source_status(self.root, artifact), lineage.CURRENT)
        self.assertTrue(lineage.source_available(self.root, artifact))
        source.write_text('第二版', encoding='utf-8')
        self.assertEqual(lineage.source_status(self.root, artifact), lineage.STALE)
        self.assertTrue(lineage.source_available(self.root, artifact))
        source.write_text('第一版', encoding='utf-8')
        self.assertEqual(lineage.source_status(self.root, artifact), lineage.CURRENT)

    def test_unrelated_file_change_keeps_current(self):
        source = self.write('原稿.md', '甲')
        artifact = self.write('成果/story.json', '{}')
        lineage.record(self.root, artifact, source, '分镜定稿')
        self.write('别的/无关文件.md', '乙')
        self.write('原稿.md.bak', '丙')
        self.assertEqual(lineage.source_status(self.root, artifact), lineage.CURRENT)

    def test_deleted_source_reports_missing_and_unavailable(self):
        source = self.write('原稿.md', '甲')
        artifact = self.write('成果/story.json', '{}')
        lineage.record(self.root, artifact, source, '分镜定稿')
        source.unlink()
        report = lineage.check(self.root, artifact)
        self.assertEqual(report['status'], lineage.MISSING)
        self.assertEqual(report['sources'][0]['status'], lineage.MISSING)
        self.assertFalse(lineage.source_available(self.root, artifact))

    def test_project_without_ledger_is_unknown_and_not_hidden(self):
        artifact = self.write('成果/story.json', '{}')
        self.assertEqual(lineage.source_status(self.root, artifact), lineage.UNKNOWN)
        self.assertIsNone(lineage.source_available(self.root, artifact))

    def test_legacy_single_source_entry_is_still_readable(self):
        """迁移前只记 source/source_sha256 的旧账本仍要能读出状态。"""
        self.write('原稿.md', '甲')
        artifact = self.write('成果/story.json', '{}')
        (artifact.parent / lineage.FILE_NAME).write_text(json.dumps({
            'version': 1, 'entries': [{
                'artifact': '成果/story.json', 'source': '原稿.md',
                'artifact_type': '分镜定稿', 'source_sha256': 'deadbeef'}]},
            ensure_ascii=False), encoding='utf-8')
        self.assertEqual(lineage.source_status(self.root, artifact), lineage.STALE)
        self.assertTrue(lineage.source_available(self.root, artifact))

    def test_multi_source_reports_role_level_status(self):
        script = self.write('分镜/EP001.json', '{}')
        assets = self.write('资产/assets.json', '{}')
        lines = self.write('台词/EP001.json', '{}')
        config = self.write('配置/模型.json', '{}')
        artifact = self.write('06分镜定稿/EP001/episode.json', '{}')
        lineage.record(self.root, artifact, script, '分镜定稿', sources={
            '分镜': script, '资产': assets, '台词': lines, '模型配置': config})
        report = lineage.check(self.root, artifact)
        self.assertEqual(report['status'], lineage.CURRENT)
        self.assertEqual({row['role'] for row in report['sources']},
                         {'分镜', '资产', '台词', '模型配置'})
        lines.write_text('{"changed": true}', encoding='utf-8')
        report = lineage.check(self.root, artifact)
        self.assertEqual(report['status'], lineage.STALE)
        by_role = {row['role']: row['status'] for row in report['sources']}
        self.assertEqual(by_role['台词'], lineage.STALE)
        self.assertEqual(by_role['分镜'], lineage.CURRENT)
        self.assertEqual(by_role['资产'], lineage.CURRENT)

    def test_record_overwrites_previous_sources_for_same_artifact(self):
        a = self.write('a.md', '甲')
        b = self.write('b.md', '乙')
        artifact = self.write('成果/x.json', '{}')
        lineage.record(self.root, artifact, a, '首帧', sources={'主': a, '旧': b})
        lineage.record(self.root, artifact, a, '首帧')
        report = lineage.check(self.root, artifact)
        self.assertEqual([row['role'] for row in report['sources']], ['source'])
        b.write_text('乙改', encoding='utf-8')
        self.assertEqual(lineage.source_status(self.root, artifact), lineage.CURRENT)

    def test_affected_lists_stale_deliverables_only(self):
        src = self.write('原稿.md', '甲')
        other = self.write('无关.md', '丙')
        structure = self.write('结构/正稿.md', '# 结构')
        board = self.write('定稿/episode.json', '{}')
        lineage.record(self.root, structure, src, '结构剧本')
        lineage.record(self.root, board, other, '分镜定稿')
        src.write_text('甲改', encoding='utf-8')
        self.assertEqual({item['artifact'] for item in lineage.affected(self.root)},
                         {'结构/正稿.md'})
        self.assertEqual({item['artifact'] for item in lineage.affected(self.root, src)},
                         {'结构/正稿.md'})
        self.assertEqual(lineage.affected(self.root, other), [])

    def test_explicit_adopt_registers_a_legacy_artifact(self):
        source = self.write('原稿.md', '甲')
        artifact = self.write('成果/x.json', '{}')
        self.assertEqual(lineage.source_status(self.root, artifact), lineage.UNKNOWN)
        lineage.adopt(self.root, artifact, source, '白模')
        self.assertEqual(lineage.source_status(self.root, artifact), lineage.CURRENT)

    def test_status_covers_every_pipeline_artifact_type(self):
        """结构、分镜、首帧、白模、音频、剪辑都能登记并检出过期。"""
        for index, kind in enumerate(('结构剧本', '分镜定稿', '首帧', '白模', '音频', '剪辑')):
            with self.subTest(kind=kind):
                source = self.write('源/%d.md' % index, '甲')
                artifact = self.write('成果/%d.json' % index, '{}')
                lineage.record(self.root, artifact, source, kind)
                self.assertEqual(lineage.check(self.root, artifact)['artifact_type'], kind)
                self.assertEqual(lineage.source_status(self.root, artifact), lineage.CURRENT)
                source.write_text('乙', encoding='utf-8')
                self.assertEqual(lineage.source_status(self.root, artifact), lineage.STALE)


if __name__ == '__main__':
    unittest.main()
