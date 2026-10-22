"""三虎错误列表必须有上限：pet_* 模块不得再写 `self.errors = []`。

R1853 前 `Pet`／`Cloud`／`Agent`／`StageQueue` 的 `errors` 是普通 list，150 ms 心跳里的持续异常会
无限累积；现统一用 `pet_bus.ErrorLog`（只留 `ERROR_LIMIT` 条，`total` 记累计）。唯一例外是
`pet_bus.Bus`：它在 `_record_error` 里按 `error_limit` 自行裁剪。
"""
from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

from tests.architecture._scan import ROOT, parse, production_runtime_files

ALLOWED = frozenset({('pet_bus.py', 'Bus')})


def _unbounded(node: ast.AST) -> bool:
    if isinstance(node, ast.List):
        return True
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == 'list')


def _sites(path: Path, name: str) -> list[str]:
    sites = []
    for cls in ast.walk(parse(path)):
        if not isinstance(cls, ast.ClassDef) or (name, cls.name) in ALLOWED:
            continue
        for node in ast.walk(cls):
            if isinstance(node, ast.Assign):
                targets, value = node.targets, node.value
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                targets, value = [node.target], node.value
            else:
                continue
            if _unbounded(value) and any(isinstance(t, ast.Attribute) and t.attr == 'errors'
                                         for t in targets):
                sites.append('%s:%d' % (name, node.lineno))
    return sites


def _pet_files():
    return [path for path in production_runtime_files() if path.stem.startswith('pet_')]


class PetErrorLogBoundaryTests(unittest.TestCase):
    def test_pet_errors_use_bounded_error_log(self):
        bad = sorted({site for path in _pet_files()
                      for site in _sites(path, path.relative_to(ROOT).as_posix())})
        self.assertEqual(bad, [], 'errors 请用 pet_bus.ErrorLog()，不要用无上限 list：' + ', '.join(bad))

    def test_detector_catches_plain_list(self):
        with tempfile.TemporaryDirectory() as folder:
            sample = Path(folder) / 'pet_sample.py'
            sample.write_text('class A:\n    def __init__(self):\n        self.errors = []\n'
                              '        self.other = []\n'
                              'class B:\n    def __init__(self):\n        self.errors: list = list()\n'
                              'class C:\n    def __init__(self):\n        self.errors = ErrorLog()\n',
                              encoding='utf-8')
            self.assertEqual(_sites(sample, 'pet_sample.py'), ['pet_sample.py:3', 'pet_sample.py:7'])


if __name__ == '__main__':
    unittest.main()
