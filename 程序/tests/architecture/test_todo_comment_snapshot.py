"""冻结生产注释中的待办关键词，防止把说明性注释误作缺陷。"""
from __future__ import annotations

import ast
import io
import json
import tokenize
import unittest
from pathlib import Path

from tests.architecture._scan import module_scan_files, registry_key


ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / '维护记录' / 'TODO注释快照_20261003.json'
MARKERS = ('todo', '暂时', '待补', '后续再', '先这样')


def _scope_at(tree, line):
    candidates = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.lineno <= line <= getattr(node, 'end_lineno', node.lineno):
                candidates.append(node)
    return max(candidates, key=lambda node: node.lineno).name if candidates else '<module>'


def _comment_items(paths=None, *, root=ROOT):
    found = []
    for path in module_scan_files() if paths is None else paths:
        source = path.read_text(encoding='utf-8')
        tree = ast.parse(source, filename=str(path))
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type != tokenize.COMMENT:
                continue
            comment = token.string[1:].strip()
            if any(marker in comment.lower() for marker in MARKERS):
                found.append({
                    'file': (registry_key(path) if path.is_relative_to(ROOT)
                             else path.relative_to(root).as_posix()),
                    'scope': _scope_at(tree, token.start[0]),
                    'comment': comment,
                })
    return found


class TodoCommentSnapshotTests(unittest.TestCase):
    def test_keyword_comments_match_the_reviewed_snapshot(self):
        data = json.loads(SNAPSHOT.read_text(encoding='utf-8'))
        expected = [{key: item[key] for key in ('file', 'scope', 'comment')}
                    for item in data['items']]
        self.assertEqual(_comment_items(), expected)

    def test_every_snapshot_item_has_a_review_disposition(self):
        data = json.loads(SNAPSHOT.read_text(encoding='utf-8'))
        for item in data['items']:
            self.assertIn(item['classification'], {'A', 'B', 'C'})
            self.assertIn(item['disposition'], {'explanatory', 'pending', 'resolved'})
            self.assertTrue(item['reason'].strip())
