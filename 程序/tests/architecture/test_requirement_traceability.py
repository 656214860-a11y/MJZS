"""文档先行的需求锚定棘轮（AGENTS §2.7 第 4 条）。

需求按阶段拆在 ``docs/stages/Sxx_*.md``（每个文件 ``## 需求`` 节里的 ``- **REQ-Sxx-nn** 状态`` 行）。
标 ✅ 的需求必须有测试锚定（测试名 ``test_req_s10_03_*`` 或 docstring/注释写 ``REQ-S10-03``，
支持 ``REQ-S10-01/02/03`` 斜杠简写）。历史上补写文档时已有一批 ✅ 没有锚点，
登记在 ``维护记录/需求锚定基线.json``：

- 新增的 ✅ 需求没有测试锚定即失败（补测试，或降为 🟡）；
- 基线里的编号一旦有了锚点、或不再是 ✅，必须从基线删除（只许减少）；
- 测试里引用了阶段文件里不存在的编号即失败（编号删除后不复用）；
- 每条需求的定义行只许写在它所属阶段的 ``Sxx_*.md`` 里（正文里的跨阶段引用不受限）。
"""
import ast
import json
import re
import sys
import unittest
from pathlib import Path

_SCRIPT_ROOT = Path(__file__).resolve().parents[2]
if str(_SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_ROOT))

from tests.architecture._scan import ROOT

STAGE_DIR = ROOT / 'docs' / 'stages'
BASELINE = ROOT / '维护记录' / '需求锚定基线.json'
ROW = re.compile(r'^- \*\*(REQ-S\d+-\d+)\*\*\s*(\S+)', re.M)
DOC_ANCHOR = re.compile(r'(?i)req-s(\d+)-(\d+(?:/\d+)*)')
NAME_ANCHOR = re.compile(r'(?i)req_s(\d+)_(\d+)')


def stage_files():
    """按阶段顺序返回 ``docs/stages`` 下的阶段文件。"""
    files = sorted(STAGE_DIR.glob('S*.md'))
    if not files:
        raise AssertionError('docs/stages 下找不到阶段文件')
    return files


def requirement_rows():
    """逐文件产出 ``(阶段文件, 编号, 状态)``，用于定位需求写在哪个阶段文件。"""
    for path in stage_files():
        for matched in ROW.finditer(path.read_text(encoding='utf-8')):
            yield path, matched.group(1), matched.group(2)


def requirement_status():
    return {rid: mark for _, rid, mark in requirement_rows()}


def anchored_requirements():
    found = set()
    for path in (ROOT / 'tests').rglob('*.py'):
        if path.name == Path(__file__).name:
            continue
        found.update(_anchor_ids(path.read_text(encoding='utf-8', errors='ignore')))
    return found


def find_anchors(requirement_id):
    """返回锚定指定需求的 ``(测试文件, 测试类或方法)``，供 --find 命令查询。"""
    wanted = requirement_id.strip().upper()
    hits = set()
    for path in (ROOT / 'tests').rglob('*.py'):
        if path.resolve() == Path(__file__).resolve():
            continue
        text = path.read_text(encoding='utf-8', errors='ignore')
        if wanted not in _anchor_ids(text):
            continue
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError:
            scopes = []
        else:
            scopes = _test_scopes(tree)
        for matched in DOC_ANCHOR.finditer(text):
            ids = {f'REQ-S{matched.group(1)}-{number}'
                   for number in matched.group(2).split('/')}
            if wanted in ids:
                line = text.count('\n', 0, matched.start()) + 1
                for target in _targets_at(scopes, line):
                    hits.add((path.relative_to(ROOT).as_posix(), target))
        for matched in NAME_ANCHOR.finditer(text):
            if f'REQ-S{matched.group(1)}-{matched.group(2)}' == wanted:
                line = text.count('\n', 0, matched.start()) + 1
                for target in _targets_at(scopes, line):
                    hits.add((path.relative_to(ROOT).as_posix(), target))
    return sorted(hits)


def _anchor_ids(text):
    found = set()
    for matched in DOC_ANCHOR.finditer(text):
        for number in matched.group(2).split('/'):
            found.add(f'REQ-S{matched.group(1)}-{number}')
    for matched in NAME_ANCHOR.finditer(text):
        found.add(f'REQ-S{matched.group(1)}-{matched.group(2)}')
    return found


def _test_scopes(tree):
    """收集测试类与方法的作用域 ``(起, 止, 名称, 报告目标)``。"""
    scopes = []

    def visit(node, prefix=''):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                name = f'{prefix}{child.name}'
                methods = [f'{name}.{item.name}' for item in child.body
                           if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                           and item.name.startswith('test')]
                scopes.append((child.lineno, child.end_lineno, name, methods or [name]))
                visit(child, name + '.')
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = f'{prefix}{child.name}'
                if child.name.startswith('test'):
                    scopes.append((child.lineno, child.end_lineno, name, [name]))
                visit(child, name + '.')

    visit(tree)
    return scopes


def _targets_at(scopes, line):
    candidates = [scope for scope in scopes if scope[0] <= line <= scope[1]]
    if not candidates:
        return ['<module>']
    return max(candidates, key=lambda scope: scope[0])[3]


def untested_done_requirements():
    status = requirement_status()
    anchored = anchored_requirements()
    return {rid for rid, mark in status.items() if mark == '✅' and rid not in anchored}


class RequirementTraceabilityTests(unittest.TestCase):
    def test_requirement_ids_are_unique(self):
        ids = [rid for _, rid, _ in requirement_rows()]
        self.assertEqual(len(ids), len(set(ids)), '需求编号重复；删除的编号不得复用')

    def test_requirements_stay_in_their_stage_file(self):
        for path, rid, _ in requirement_rows():
            stage = path.name.split('_', 1)[0]
            self.assertTrue(
                rid.startswith('REQ-%s-' % stage),
                '%s 写在了 %s，应写在 %s 的阶段文件里' % (rid, path.name, stage))

    def test_tests_do_not_reference_unknown_requirements(self):
        unknown = sorted(anchored_requirements() - set(requirement_status()))
        self.assertEqual(unknown, [], '测试引用了阶段文件里不存在的编号')

    def test_new_done_requirement_needs_a_test_anchor(self):
        baseline = set(json.loads(BASELINE.read_text(encoding='utf-8'))['untested_done'])
        new = sorted(untested_done_requirements() - baseline)
        self.assertEqual(new, [],
                         '以下 ✅ 需求没有测试锚定：补测试（docstring 写 REQ-xx），或降为 🟡')

    def test_baseline_only_shrinks(self):
        baseline = set(json.loads(BASELINE.read_text(encoding='utf-8'))['untested_done'])
        stale = sorted(baseline - untested_done_requirements())
        self.assertEqual(stale, [],
                         '以下编号已有测试锚定或不再是 ✅，请从 维护记录/需求锚定基线.json 删除')


def _find_main(argv):
    if len(argv) != 1 or not re.fullmatch(r'(?i)REQ-S\d+-\d+', argv[0]):
        print('用法：python -B tests/architecture/test_requirement_traceability.py --find REQ-Sxx-nn')
        return 2
    hits = find_anchors(argv[0])
    if not hits:
        print(f'未找到锚定 {argv[0].upper()} 的测试')
        return 1
    for path, target in hits:
        print(f'{path}: {target}')
    return 0


if __name__ == '__main__':
    if len(sys.argv) >= 2 and sys.argv[1] == '--find':
        sys.exit(_find_main(sys.argv[2:]))
    unittest.main()
