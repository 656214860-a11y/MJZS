# -*- coding: utf-8 -*-
"""ui_settings.json 只能由 infra/project_settings.py 写：AST 源码扫描（W6B-FIX-P1）。"""
import ast, os, sys, unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

ROOT = Path(__file__).resolve().parents[1]

SKIP_TOP = {'tests', 'tasks_round', 'docs', '维护记录', 'logs'}
SKIP_FILE = 'infra/project_settings.py'
WRITE_METHODS = ('write_text', 'write_bytes')
SETTINGS_NAME = 'ui_settings.json'

# 保留清单：相对路径 → 理由。每个文件都必须仍能被扫出至少一处，不许留过期条目。
RETAINED = {
    'scripts/acceptance_stage_op_walkthrough.py':
        '验收走查脚本往它自己建的临时项目里写夹具，不随应用运行。',
}


def direct_writes(source_text):
    """返回一段源码里直接写 ui_settings.json 的行号列表。"""
    tree = ast.parse(source_text)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            value, targets = node.value, node.targets
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            value, targets = node.value, [node.target]
        else:
            continue
        if SETTINGS_NAME in ast.unparse(value):
            names.update(ast.unparse(target) for target in targets)
    hits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute):
            name, obj = func.attr, ast.unparse(func.value)
        elif isinstance(func, ast.Name):
            name, obj = func.id, ''
        else:
            continue
        if name == 'save' and node.args:
            first = ast.unparse(node.args[0])
            if SETTINGS_NAME in first or first in names:
                hits.append(node.lineno)
        elif name in WRITE_METHODS and (SETTINGS_NAME in obj or obj in names):
            hits.append(node.lineno)
    return hits


def _scan_product():
    found = []
    for path in sorted(ROOT.rglob('*.py')):
        rel = path.relative_to(ROOT).as_posix()
        parts = rel.split('/')
        if parts[0] in SKIP_TOP or '__pycache__' in parts or rel == SKIP_FILE:
            continue
        try:
            text = path.read_text(encoding='utf-8')
        except (OSError, UnicodeError):
            continue
        if SETTINGS_NAME not in text:
            continue
        found.extend('%s:%d' % (rel, line) for line in direct_writes(text))
    return found


class SingleWriteEntryTests(unittest.TestCase):
    def test_scanner_recognizes_direct_write_forms(self):
        positives = [
            "save(Path(p)/'ui_settings.json', d)",
            "f = p/'ui_settings.json'\nsave(f, d)",
            "(p/'ui_settings.json').write_text('x')",
            "self.f = p/'ui_settings.json'\nself.f.write_bytes(b'')",
        ]
        for source in positives:
            self.assertTrue(direct_writes(source), source)
        negatives = [
            "save(p/'config.json', d)",
            "save_prefs(p, d)",
            "read(p/'ui_settings.json')",
        ]
        for source in negatives:
            self.assertEqual(direct_writes(source), [], source)

    def test_only_project_settings_writes_prefs_file(self):
        found = _scan_product()
        unexpected = [item for item in found
                      if item.rsplit(':', 1)[0] not in RETAINED]
        self.assertEqual(unexpected, [])
        for rel in RETAINED:
            self.assertTrue(any(item.rsplit(':', 1)[0] == rel for item in found),
                            '保留清单条目已过期：' + rel)


if __name__ == "__main__":
    unittest.main(verbosity=2)
