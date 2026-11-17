"""`read_json` 同名不同义：只许现有三处定义，禁止再新增。

R1854 登记时三处语义各不相同，调用方看名字分不出：
- `file_cache.read_json`：正式 JSON 读取权威（AGENTS §2.2），文件坏或缺失时抛错，返回拷贝；
- `agent/core.py` 的 `read_json`：失败返回调用方给的默认值；
- `video_navigation.read_json`：页面级包装，坏文件即 `{}`（R722 起底层委托 file_cache）。
新代码读正式 JSON 请直接用 `file_cache.read_json()`，需要容错时在调用处显式处理，不要再造一个同名函数。
"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import ROOT, parse, production_runtime_files

NAME = 'read_json'
REGISTERED = frozenset({'agent/core.py', 'file_cache.py', 'ui/video_navigation.py'})


def _definitions() -> dict[str, list[int]]:
    found = {}
    for path in production_runtime_files():
        lines = [node.lineno for node in ast.walk(parse(path))
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == NAME]
        if lines:
            found[path.relative_to(ROOT).as_posix()] = lines
    return found


class ReadJsonDefinitionTests(unittest.TestCase):
    def test_no_new_read_json_definitions(self):
        found = _definitions()
        extra = sorted('%s:%s' % (name, ','.join(map(str, lines)))
                       for name, lines in found.items() if name not in REGISTERED)
        self.assertEqual(extra, [], '读正式 JSON 请用 file_cache.read_json()，不要再定义同名函数：'
                         + ', '.join(extra))

    def test_registered_definitions_still_exist_once(self):
        found = _definitions()
        self.assertEqual({name: len(found.get(name, [])) for name in REGISTERED},
                         {name: 1 for name in REGISTERED},
                         '登记的定义被删除或改名后，请同步缩小登记表')


if __name__ == '__main__':
    unittest.main()
