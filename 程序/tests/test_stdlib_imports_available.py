"""随附解释器的 Lib 是裁剪版；生产模块用到的标准库必须都在其中，否则只在用户机器上启动失败。

背景：启动错误.log 曾记录 ``Standard library module 'colorsys' was not found``。本测试用随附解释器
静态扫描生产代码（程序/*.py 与 agent/）的全部 import（含函数内），标准库名必须能 find_spec；
包在 try/except 里的可选导入除外。
"""
import ast
import importlib.util
import sys
import unittest
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
SOURCES = sorted(list(PROGRAM.glob('*.py')) + list((PROGRAM / 'agent').rglob('*.py')))


def _guarded(tree):
    """返回处于 try 体内且带 ImportError/Exception 处理器的 import 节点。"""
    guarded = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        names = {getattr(h.type, 'id', None) if h.type is not None else 'Exception' for h in node.handlers}
        names |= {e.id for h in node.handlers if isinstance(h.type, ast.Tuple) for e in h.type.elts if isinstance(e, ast.Name)}
        if names & {'ImportError', 'ModuleNotFoundError', 'Exception', 'BaseException'}:
            for stmt in node.body:
                for inner in ast.walk(stmt):
                    if isinstance(inner, (ast.Import, ast.ImportFrom)):
                        guarded.add(inner)
    return guarded


class StdlibImportsAvailable(unittest.TestCase):
    def test_every_stdlib_import_exists_in_bundled_runtime(self):
        self.assertGreater(len(SOURCES), 200)
        local = {p.stem for p in PROGRAM.glob('*.py')} | {p.name for p in PROGRAM.iterdir() if p.is_dir()}
        missing = []
        for path in SOURCES:
            tree = ast.parse(path.read_text(encoding='utf-8', errors='replace'))
            guarded = _guarded(tree)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    names = [node.module]
                else:
                    continue
                if node in guarded:
                    continue
                for name in names:
                    top = name.split('.')[0]
                    if top in local or top not in sys.stdlib_module_names:
                        continue
                    try:
                        found = importlib.util.find_spec(name)
                    except (ImportError, ValueError):
                        found = None
                    if found is None:
                        missing.append(f'{path.relative_to(PROGRAM)}:{node.lineno} {name}')
        self.assertEqual(missing, [], '随附 Python 缺少下列标准库：\n' + '\n'.join(missing))


if __name__ == '__main__':
    unittest.main()
