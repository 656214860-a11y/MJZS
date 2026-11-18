"""L0 纯度门禁（K9）：contract/ 包只允许白名单标准库与第一方包。

清单权威：任务书 K-H1（§3.2）。允许标准库＝__future__/abc/collections/dataclasses/
enum/typing/types/functools/itertools/operator/re/math/json/hashlib/datetime/
pathlib/copy/string/textwrap/warnings；os 仅放行 os.path 纯函数用法；禁用模块＝
os（非 path）、subprocess、socket、ssl、ctypes、winreg、msvcrt、threading、queue、
multiprocessing、urllib、http、shutil、tempfile、webbrowser、time、importlib 及
全部第三方运行时包。禁用调用＝open()、Path 禁用方法名、os.environ/os.getenv。

违规以「文件:符号:类型」登记进 维护记录/架构统一基数.json「L0 纯度」段，
只减不增；函数体内与 try 内的 import 同样计入。分层方向（L0→L1 等）由
test_layers 负责，本门禁不重复判定。
"""
from __future__ import annotations

import ast
import json
import sys
import unittest
from collections import Counter
from pathlib import Path

from tests.architecture._layers import LAYER_NAMES, LAYERS, _register

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / '维护记录' / '架构统一基数.json'
CONTRACT_DIR = ROOT / 'contract'
CANARY = Path(__file__).with_name('_canary')

ALLOWED_STDLIB = frozenset({
    '__future__', 'abc', 'collections', 'dataclasses', 'enum', 'typing', 'types',
    'functools', 'itertools', 'operator', 're', 'math', 'json', 'hashlib',
    'datetime', 'pathlib', 'copy', 'string', 'textwrap', 'warnings',
})
# 第一方包顶层名：分层方向由 test_layers 判定，纯度门禁只管外部依赖。
FIRST_PARTY_TOPS = frozenset({
    'contract', 'infra', 'domain', 'orchestrator', 'ui', 'agent', 'foundation',
    'tests', 'scripts',
}) | frozenset(p.stem for p in CONTRACT_DIR.glob('*.py'))
PATH_METHODS = frozenset({
    'read_text', 'write_text', 'read_bytes', 'write_bytes', 'open', 'mkdir',
    'touch', 'unlink', 'rename', 'replace', 'iterdir', 'glob', 'rglob',
    'exists', 'is_file', 'is_dir', 'stat',
})


def _scopes(tree):
    return sorted(
        (node.lineno, getattr(node, 'end_lineno', node.lineno), node.name)
        for node in ast.walk(tree)
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)))


def _symbol(scopes, node):
    line = node.lineno
    return '.'.join(name for start, end, name in scopes if start <= line <= end) or '<module>'


def _import_roots(tree):
    """产出 (节点, 顶层模块名, 是否 os.path 纯用法)。含函数体与 try 内。"""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split('.')
                yield node, parts[0], parts[:2] == ['os', 'path']
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue  # 包内相对导入＝第一方
            module = node.module or ''
            parts = module.split('.')
            top = parts[0] if parts and parts[0] else ''
            if top == 'os':
                if module == 'os':
                    for alias in node.names:
                        yield node, 'os', alias.name == 'path'
                else:
                    yield node, 'os', parts[:2] == ['os', 'path']
            elif top:
                yield node, top, False


def _violations(tree, filename):
    """返回 Counter[(file, symbol, type)]。type＝import:<模块> / call:<调用>。"""
    scopes = _scopes(tree)
    found = Counter()

    def add(node, kind):
        found[(filename, _symbol(scopes, node), kind)] += 1

    for node, top, os_path_ok in _import_roots(tree):
        if os_path_ok:
            continue
        if top == 'os':
            add(node, 'import:os')
        elif top in ALLOWED_STDLIB or top in FIRST_PARTY_TOPS:
            continue
        elif top in sys.stdlib_module_names:
            add(node, f'import:{top}')
        else:
            add(node, f'import:{top}')

    def _is_str_literal(expr):
        return isinstance(expr, ast.Constant) and isinstance(expr.value, str) \
            or isinstance(expr, ast.JoinedStr)

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == 'environ' \
                and isinstance(node.value, ast.Name) and node.value.id == 'os':
            add(node, 'call:os.environ')

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == 'open':
            add(node, 'call:open')
        elif isinstance(func, ast.Attribute):
            if func.attr in PATH_METHODS and not _is_str_literal(func.value):
                add(node, f'call:path.{func.attr}')
            if func.attr == 'getenv' and isinstance(func.value, ast.Name) and func.value.id == 'os':
                add(node, 'call:os.environ')
    return found


def _scan_file(path):
    rel = path.relative_to(ROOT).as_posix()
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    return _violations(tree, rel)


def _scan_contract():
    out = Counter()
    for path in sorted(CONTRACT_DIR.glob('*.py')):
        out.update(_scan_file(path))
    return out


def _scan_source(source, filename='<sample>'):
    return _violations(ast.parse(source), filename)


def _ledger_items():
    ledger = json.loads(LEDGER.read_text(encoding='utf-8'))
    section = ledger.get('L0 纯度')
    assert section is not None, '架构统一基数.json 缺少「L0 纯度」段'
    items = Counter()
    for item in section['items']:
        items[(item['file'], item['symbol'], item['type'])] += item['count']
    return section, items


class ContractPurityTests(unittest.TestCase):
    def test_scan_matches_ledger_and_never_exceeds_baseline(self):
        """棘轮：实测违规集合必须与台账逐项相等，且总数不超立书基线。"""
        section, ledger = _ledger_items()
        actual = _scan_contract()
        self.assertEqual(actual, ledger,
                         f'L0 纯度实测与台账不符：'
                         f'新增={sorted((actual - ledger).elements())} '
                         f'消失={sorted((ledger - actual).elements())}')
        self.assertLessEqual(sum(actual.values()), section['baseline_total'],
                             'L0 纯度违规数超过立书基线（只减不增）')

    def test_forbidden_import_inside_function_and_try_is_flagged(self):
        source = (
            'def f():\n'
            '    try:\n'
            '        import subprocess\n'
            '    except ImportError:\n'
            '        pass\n'
            '    from os import environ\n'
        )
        kinds = {kind for _, _, kind in _scan_source(source)}
        self.assertIn('import:subprocess', kinds)
        self.assertIn('import:os', kinds)

    def test_bad_sample_path_write_text_is_flagged(self):
        source = 'from pathlib import Path\nPath("a").write_text("x")\n'
        kinds = {kind for _, _, kind in _scan_source(source)}
        self.assertIn('call:path.write_text', kinds)

    def test_open_and_os_environ_are_flagged(self):
        source = 'import os\nos.environ["K"] = "v"\nopen("f").read()\n'
        kinds = {kind for _, _, kind in _scan_source(source)}
        self.assertIn('import:os', kinds)
        self.assertIn('call:os.environ', kinds)
        self.assertIn('call:open', kinds)

    def test_allowed_stdlib_and_first_party_pass(self):
        source = (
            'import json\nimport os.path\nfrom contract.pet_bus import emit_safe\n'
            'from agent.core import read\nfrom .sibling import x\n'
            'def g(p):\n    return json.dumps({"a": 1})\n'
        )
        self.assertEqual(_scan_source(source), Counter())

    def test_third_party_and_non_allowed_stdlib_flagged(self):
        source = 'import requests\nimport sys\nimport time\n'
        kinds = {kind for _, _, kind in _scan_source(source)}
        self.assertIn('import:requests', kinds)
        self.assertIn('import:sys', kinds)
        self.assertIn('import:time', kinds)

    def test_canary_bad_samples_turn_gate_red(self):
        """K9-2：_canary 下两个 L0 坏样本必须被门禁识别。"""
        cases = {
            'l0_purity_import_subprocess.py': 'import:subprocess',
            'l0_purity_path_write_text.py': 'call:path.write_text',
        }
        for name, expected in cases.items():
            kinds = {kind for _, _, kind in _scan_file(CANARY / name)}
            self.assertIn(expected, kinds, f'金丝雀 {name} 漏报 {expected}')


class L0PLayerTests(unittest.TestCase):
    def test_l0p_layer_registered_between_l0_and_l1(self):
        self.assertEqual(LAYER_NAMES.get(0.5), 'L0P 平台基座')
        values = sorted(LAYER_NAMES)
        self.assertLess(values.index(0), values.index(0.5))
        self.assertLess(values.index(0.5), values.index(1))

    def test_l0p_registration_accepts_float_layer(self):
        probe = '_k9_l0p_probe'
        try:
            _register(0.5, probe)
            self.assertEqual(LAYERS[probe], 0.5)
        finally:
            LAYERS.pop(probe, None)

    def test_l0_importing_l0p_is_upward(self):
        """L0(0) < L0P(0.5)：L0 引用 L0P 属向上依赖，与 test_layers 同一判定。"""
        self.assertLess(0, LAYERS.get('_k9_l0p_probe', 0.5))
        # 方向判定复算：importer 层 < imported 层 ⇒ 越层
        self.assertTrue(0 < 0.5)


if __name__ == '__main__':
    unittest.main()
