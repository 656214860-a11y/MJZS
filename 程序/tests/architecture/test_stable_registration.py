"""按语义锚定的登记在无关行平移后仍须有效。"""
from __future__ import annotations

import tempfile
import unittest
import json
from pathlib import Path

from tests.architecture.test_todo_comment_snapshot import _comment_items
from tests.architecture.test_unification_ratchet import _bare_json_loads
from tests.architecture.test_coverage_audit_ratchet import scan


class StableRegistrationTests(unittest.TestCase):
    def _source(self, root: Path, name: str, text: str) -> Path:
        path = root / name
        path.write_text(text, encoding='utf-8')
        return path

    def test_bare_json_registration_ignores_unrelated_leading_line(self):
        """REQ-LINEKEY-01：行前插入无关内容不制造新债务。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self._source(root, 'sample.py', 'import json\nvalue = json.loads(raw)\n')
            before = _bare_json_loads([path], root=root)
            path.write_text('\nimport json\nvalue = json.loads(raw)\n', encoding='utf-8')
            self.assertEqual(_bare_json_loads([path], root=root), before)

    def test_bare_json_registration_still_reports_add_and_remove(self):
        """REQ-LINEKEY-02：新增仍可见，删掉登记点也不能被伪装成未变。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self._source(root, 'sample.py', 'import json\na = json.loads(one)\n')
            registered = _bare_json_loads([path], root=root)
            path.write_text('import json\na = json.loads(one)\nb = json.loads(two)\n', encoding='utf-8')
            self.assertFalse(_bare_json_loads([path], root=root) <= registered)
            path.write_text('import json\n', encoding='utf-8')
            self.assertNotEqual(_bare_json_loads([path], root=root), registered)

    def test_todo_snapshot_ignores_unrelated_leading_line(self):
        """REQ-LINEKEY-03：注释快照按内容与作用域，而不是物理行。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self._source(root, 'sample.py', 'def run():\n    # TODO: retain this behavior\n    return 1\n')
            before = _comment_items([path], root=root)
            path.write_text('\ndef run():\n    # TODO: retain this behavior\n    return 1\n', encoding='utf-8')
            self.assertEqual(_comment_items([path], root=root), before)
            path.write_text('def run():\n    # TODO: retain this behavior\n    # TODO: newly introduced\n    return 1\n', encoding='utf-8')
            self.assertNotEqual(_comment_items([path], root=root), before)

    def test_coverage_registration_ignores_unrelated_leading_line(self):
        """REQ-LINEKEY-05：覆盖率审计的登记键也不能是物理行号。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self._source(root, 'sample.py', 'import subprocess\nsubprocess.run(["tool"])\n')
            before = scan('21', [path])
            path.write_text('\nimport subprocess\nsubprocess.run(["tool"])\n', encoding='utf-8')
            self.assertEqual(scan('21', [path]), before)
            path.write_text('import subprocess\nsubprocess.run(["tool"])\nsubprocess.run(["other"])\n', encoding='utf-8')
            self.assertFalse(scan('21', [path]) <= before)

    def test_registered_ledgers_no_longer_use_a_bare_line_number(self):
        """REQ-LINEKEY-04：迁移保留处置资料，但登记键不再是纯行号。"""
        root = Path(__file__).resolve().parents[2]
        ledger = json.loads((root / '维护记录' / '架构统一基数.json').read_text(encoding='utf-8'))
        points = [str(item['point']) for section in ledger.values() if isinstance(section, dict)
                  for item in section.get('items', []) if 'point' in item]
        snapshot = json.loads((root / '维护记录' / 'TODO注释快照_20261003.json').read_text(encoding='utf-8'))
        self.assertFalse(any(point.isdigit() for point in points))
        self.assertTrue(all('line' not in item for item in snapshot['items']))


if __name__ == '__main__':
    unittest.main()
