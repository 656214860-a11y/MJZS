"""文档入口唯一性：迁移后的登记脚本不遗漏职责目录或重复权威。"""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from tests.architecture._scan import ROOT

SPEC = importlib.util.spec_from_file_location('doc_registry_subject',
    ROOT / '维护记录' / '基准脚本' / 'doc_registry.py')
subject = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(subject)


class DocRegistryMigrationTests(unittest.TestCase):
    def test_registry_and_scopes_follow_docs_entrance(self):
        self.assertEqual(subject.REGISTRY, ROOT / 'docs/records/工程文档登记表.md')
        self.assertEqual(subject.SCOPES, ('*.md', 'docs/**/*.md', 'governance/**/*.md'))
        self.assertNotIn('说明/*.md', subject.SCOPES)

    def test_all_current_documents_are_registered(self):
        rows = subject.registry_rows()
        files = subject.disk_paths()
        self.assertEqual(subject.collect_errors(rows, files), [])
        for name in ('docs/requirements/产品需求规格.md',
                     'docs/records/账户设计条款迁移映射.md',
                     'governance/decisions/0001-directory-layout.md'):
            self.assertIn(name, rows)

    def test_external_document_is_rejected_before_reading(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            program = base / 'program'
            program.mkdir()
            outside = base / 'private.md'
            outside.write_text('private document marker, must not be read', encoding='utf-8')
            with patch.object(subject, 'PROGRAM', program):
                with self.assertRaises(ValueError):
                    subject.doc_stats(outside)

    def test_linked_document_is_rejected_before_reading(self):
        with tempfile.TemporaryDirectory() as temporary:
            program = Path(temporary)
            path = program / 'docs' / 'linked.md'
            path.parent.mkdir()
            path.write_text('source', encoding='utf-8')
            with patch.object(subject, 'PROGRAM', program), patch.object(Path, 'is_symlink', return_value=True), patch.object(Path, 'read_text', side_effect=AssertionError('must not read linked text')):
                with self.assertRaises(ValueError):
                    subject.doc_stats(path)

    def test_duplicate_registry_path_is_not_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            program = Path(temporary)
            table = program / 'registry.md'
            row = '| docs/specs/account.md | 全局 | 全局 | 权威 | R3836 | 开发 |\n'
            table.write_text(row + row, encoding='utf-8')
            with patch.object(subject, 'PROGRAM', program), patch.object(subject, 'REGISTRY', table):
                with self.assertRaisesRegex(ValueError, '重复登记'):
                    subject.registry_rows()

    def test_duplicate_current_authority_is_rejected(self):
        rows = {
            'docs/specs/账户.md': {'性质': '权威'},
            'docs/records/账户.md': {'性质': '权威'},
        }
        self.assertEqual(len(subject.duplicate_topics(rows)), 1)
        rows['docs/records/账户.md']['性质'] = '派生'
        self.assertEqual(subject.duplicate_topics(rows), [])

    def test_unregistered_and_missing_documents_still_fail(self):
        rows = {'docs/specs/known.md': {'层级': '全局', '阶段': '全局', '性质': '权威'}}
        problems = subject.collect_errors(rows, {'docs/specs/unknown.md'})
        self.assertTrue(any('已登记但不存在' in issue for issue in problems))
        self.assertTrue(any('存在但未登记' in issue for issue in problems))


if __name__ == '__main__':
    unittest.main()
