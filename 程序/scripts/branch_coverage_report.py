"""L0/L1 决策点分支覆盖率度量（零第三方依赖），供「先记基线、后设棘轮」使用。

与 ``coverage_report.py`` 同源思路（``sys.settrace``、只采产品模块、定向用例），
但口径不同：这里不测行覆盖，而测**结构化分支点的双结果覆盖**——
``if``／``while``／``for``／``try``（含 ``except*``）／``match`` 每个决策点
要求「两个方向都被真实执行过」才算覆盖，单测命中不算。

诚实边界（写进基线 JSON 的 ``metric`` 字段，门禁同步断言）：

- 决策点集合只含 AST 可判定的结构化分支；``if x: y`` 单行复合语句、
  ``case`` 体与 ``case`` 头同行、表达式内短路（``and``／``or``／三元／推导式 if）
  在行粒度下不可分辨，一律不计入分母。
- ``while`` 的「退出」口径＝条件首次判假（含 ``while-else``）；纯 ``break``／
  ``return`` 离开循环不算退出——``while True`` 这类条件恒真的循环改用
  「循环体→走出整个 while 范围（含 return）」作为第二结果。
- ``for`` 的「耗尽」口径＝迭代器走完（含 ``for-else``）；``break`` 离开不算。
- ``try`` 只统计带 ``except``／``except*`` 的节点（``try/finally`` 无分支可言）；
  两个结果＝「任一 handler 被进入」与「未进 handler 的干净路径」。
- ``match`` 两个结果＝「任一 case 体被进入」与「全部 case 落空走出 match」；
  末位 ``case _``（不可反驳）时不存在落空路径，只要求前者。
- 动态证据按 ``(文件, co_qualname, 行)`` 归属代码对象作用域，嵌套函数／类／
  推导式不会把内层返回误记到外层分支上；异常路径只记真实发生的，不做推断。
- 分母是「本次测量时刻」的决策点数；模块新增分支后必须重跑工具刷新基线，
  门禁 ``tests/architecture/test_branch_coverage_floor.py`` 只对基线记录值负责。

用法（工作目录＝程序，随附解释器）：
  python -B scripts/branch_coverage_report.py tests.test_artifact_schema ... \\
      --json 维护记录/分支覆盖率基线.json

退出码同 ``coverage_report.py``：0＝测量完成且目标用例全通过；1＝用例有失败
（覆盖率不可信，不写基线）；2＝参数错误。
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
import threading
import unittest
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
EXIT_LINE = -1  # 伪行号：return 事件代表的「走出当前代码对象」


def l01_modules():
    """L0/L1 顶层生产模块：_layers.LAYERS 登记层 0/1 且磁盘存在 .py。"""
    if str(PROGRAM) not in sys.path:
        sys.path.insert(0, str(PROGRAM))
    from tests.architecture._layers import LAYERS
    return tuple(sorted(name for name, layer in LAYERS.items()
                        if layer in (0, 1) and (PROGRAM / (name + '.py')).is_file()))


# ---------- 静态侧：决策点与行区间 ----------

def _entry_line(stmt):
    """语句首个可执行行；带装饰器的 def/class 从装饰器行起算。"""
    lines = [stmt.lineno]
    for dec in getattr(stmt, 'decorator_list', ()):
        lines.append(dec.lineno)
    return min(lines)


def _end_line(stmt):
    return stmt.end_lineno or stmt.lineno


def _region(stmts):
    """语句块的连续行区间 (start, end)；空块返回 None。"""
    if not stmts:
        return None
    return (min(_entry_line(s) for s in stmts), max(_end_line(s) for s in stmts))


def _in(region, line):
    return region is not None and region[0] <= line <= region[1]


def _scope_qualname(chain):
    """与 co_qualname 同规则：函数父级的子级带 ``<locals>.`` 前缀。"""
    parts = []
    for index, (kind, name) in enumerate(chain):
        prefix = '<locals>.' if index and chain[index - 1][0] == 'func' else ''
        parts.append(prefix + name)
    return '.'.join(parts) if parts else '<module>'


def _child_bodies(stmt):
    """stmt 的直接子语句块列表（不含本节点自身判定）。"""
    if isinstance(stmt, (ast.If, ast.While, ast.For, ast.AsyncFor)):
        return [stmt.body, stmt.orelse]
    if isinstance(stmt, (ast.Try, ast.TryStar)):
        return [stmt.body, stmt.orelse, stmt.finalbody] + [h.body for h in stmt.handlers]
    if isinstance(stmt, (ast.With, ast.AsyncWith)):
        return [stmt.body]
    if isinstance(stmt, ast.Match):
        return [case.body for case in stmt.cases]
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return [stmt.body]
    return []


def _iter_stmts(stmts, chain):
    """产出 (stmt, scope_chain)；scope_chain 为 ('func',名)/('class',名) 元组序列。"""
    for stmt in stmts:
        yield stmt, chain
        child = chain
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            child = chain + (('func', stmt.name),)
        elif isinstance(stmt, ast.ClassDef):
            child = chain + (('class', stmt.name),)
        for body in _child_bodies(stmt):
            yield from _iter_stmts(body, child)


def _wildcard_case(case):
    pattern = case.pattern
    return (isinstance(pattern, ast.MatchAs) and pattern.name is None
            and pattern.pattern is None)


def _decision_points(tree):
    """返回决策点列表；每项含 kind、scope 及各证据所需的行区间。"""
    points = []
    for stmt, chain in _iter_stmts(tree.body, ()):
        scope = _scope_qualname(chain)
        if isinstance(stmt, (ast.If, ast.While, ast.For, ast.AsyncFor)):
            body_entry = _entry_line(stmt.body[0])
            if body_entry <= stmt.lineno:
                continue  # 单行复合语句：测试与体同一行，行粒度不可分辨
            point = {'kind': 'loop' if isinstance(stmt, (ast.While, ast.For, ast.AsyncFor)) else 'if',
                     'scope': scope, 'line': stmt.lineno,
                     'test': (stmt.lineno, body_entry), 'body': _region(stmt.body),
                     'entry': body_entry}
            if (isinstance(stmt, ast.While) and isinstance(stmt.test, ast.Constant)
                    and bool(stmt.test.value)):
                point['constant_true'] = True
                point['span'] = (stmt.lineno, _end_line(stmt))
            points.append(point)
        elif isinstance(stmt, (ast.Try, ast.TryStar)):
            if not stmt.handlers:
                continue  # try/finally 无分支
            head = (stmt.lineno, _end_line(stmt.body[-1]))
            handlers = [(h.lineno, _end_line(h.body[-1])) for h in stmt.handlers]
            points.append({'kind': 'try', 'scope': scope, 'line': stmt.lineno,
                           'head': head, 'handlers': handlers,
                           'handler_entries': [h.lineno for h in stmt.handlers],
                           'else': _region(stmt.orelse)})
        elif isinstance(stmt, ast.Match):
            cases = []
            bad = False
            for case in stmt.cases:
                sel_end = case.pattern.end_lineno or case.pattern.lineno
                if case.guard is not None:
                    sel_end = max(sel_end, case.guard.end_lineno or case.guard.lineno)
                entry = _entry_line(case.body[0])
                if entry <= sel_end:
                    bad = True  # case 体与 case 头同行，不可分辨
                    break
                cases.append({'sel': (case.pattern.lineno, sel_end), 'entry': entry})
            if bad or not cases:
                continue
            subject_end = stmt.subject.end_lineno or stmt.subject.lineno
            selector = [(stmt.lineno, subject_end)] + [c['sel'] for c in cases]
            point = {'kind': 'match', 'scope': scope, 'line': stmt.lineno,
                     'span': (stmt.lineno, _end_line(stmt)), 'selector': selector,
                     'entries': [c['entry'] for c in cases]}
            if not _wildcard_case(stmt.cases[-1]):
                point['need_none'] = True
            points.append(point)
    return points


# ---------- 动态侧：settrace 归集（文件, co_qualname）作用域内的行弧与访问行 ----------

def _resolve_cache():
    return {}


def _make_tracer(tracked):
    """tracked: {解析后路径: 模块名}；返回 (global_tracer, arcs, visited)。"""
    arcs = set()
    visited = set()
    cache = {}

    def resolve(filename):
        if filename not in cache:
            try:
                cache[filename] = Path(filename).resolve()
            except (OSError, ValueError):
                cache[filename] = None
        return cache[filename]

    def global_tracer(frame, event, arg):
        if event != 'call':
            return None
        rel = tracked.get(resolve(frame.f_code.co_filename))
        if rel is None:
            return None
        scope = frame.f_code.co_qualname
        state = {'last': None}

        def local(frame, event, arg):
            if event == 'line':
                line = frame.f_lineno
                if state['last'] is not None:
                    arcs.add((rel, scope, state['last'], line))
                state['last'] = line
                visited.add((rel, scope, line))
            elif event == 'return':
                if state['last'] is not None:
                    arcs.add((rel, scope, state['last'], EXIT_LINE))
                state['last'] = None
            return local
        return local
    return global_tracer, arcs, visited


# ---------- 证据判定 ----------

def _scope_events(arcs, visited, rel, scope):
    scoped_arcs = [(s, d) for r, sc, s, d in arcs if r == rel and sc == scope]
    scoped_lines = {line for r, sc, line in visited if r == rel and sc == scope}
    return scoped_arcs, scoped_lines


def _branch_outcome(point, scoped_arcs, scoped_lines):
    """if/loop：taken＝体入口被访问；exited＝测试行→体外（或 while-True 体→循环外）。"""
    test_lo, test_hi = point['test']
    body_lo, body_hi = point['body']
    taken = point['entry'] in scoped_lines
    if point.get('constant_true'):
        span_lo, span_hi = point['span']
        exited = any(body_lo <= src <= body_hi and (dst == EXIT_LINE or not span_lo <= dst <= span_hi)
                     for src, dst in scoped_arcs)
    else:
        exited = any(test_lo <= src < test_hi
                     and not (test_lo <= dst < test_hi) and not (body_lo <= dst <= body_hi)
                     for src, dst in scoped_arcs)
    return taken and exited


def _try_outcome(point, scoped_arcs, scoped_lines):
    handler_hit = any(entry in scoped_lines for entry in point['handler_entries'])
    head_lo, head_hi = point['head']
    else_r = point['else']
    handler_regions = point['handlers']

    def in_head(line):
        return head_lo <= line <= head_hi

    def in_else(line):
        return _in(else_r, line)

    def in_handler(line):
        return any(lo <= line <= hi for lo, hi in handler_regions)

    clean = any((in_head(src) or in_else(src))
                and not in_head(dst) and not in_handler(dst)
                for src, dst in scoped_arcs)
    return handler_hit and clean


def _match_outcome(point, scoped_arcs, scoped_lines):
    matched = any(entry in scoped_lines for entry in point['entries'])
    if not matched:
        return False
    if not point.get('need_none'):
        return True
    span_lo, span_hi = point['span']

    def in_selector(line):
        return any(lo <= line <= hi for lo, hi in point['selector'])

    none_hit = any(in_selector(src) and (dst == EXIT_LINE or not span_lo <= dst <= span_hi)
                   for src, dst in scoped_arcs)
    return none_hit


def _covered(point, scoped_arcs, scoped_lines):
    if point['kind'] == 'try':
        return _try_outcome(point, scoped_arcs, scoped_lines)
    if point['kind'] == 'match':
        return _match_outcome(point, scoped_arcs, scoped_lines)
    return _branch_outcome(point, scoped_arcs, scoped_lines)


def measure(targets):
    names = l01_modules()
    tracked = {}
    points_by_module = {}
    for name in names:
        path = PROGRAM / (name + '.py')
        tracked[path.resolve()] = name + '.py'
        try:
            tree = ast.parse(path.read_text(encoding='utf-8', errors='replace'))
        except SyntaxError:
            continue
        points = _decision_points(tree)
        if points:
            points_by_module[name + '.py'] = points
    global_tracer, arcs, visited = _make_tracer(tracked)
    sys.path[:0] = [str(PROGRAM), str(PROGRAM / 'tests')]
    previous = sys.gettrace()
    sys.settrace(global_tracer)
    threading.settrace(global_tracer)
    try:
        suite = unittest.TestLoader().loadTestsFromNames(list(targets))
        result = unittest.TextTestRunner(verbosity=1).run(suite)
    finally:
        sys.settrace(previous)
        threading.settrace(None)
    # 按 (模块, 作用域) 预分组，避免逐点全扫
    arc_by_scope = {}
    line_by_scope = {}
    for rel, scope, src, dst in arcs:
        arc_by_scope.setdefault((rel, scope), []).append((src, dst))
    for rel, scope, line in visited:
        line_by_scope.setdefault((rel, scope), set()).add(line)
    rows = []
    total_points = total_covered = 0
    for filename in sorted(points_by_module):
        module_points = points_by_module[filename]
        covered = 0
        for point in module_points:
            scoped_arcs = arc_by_scope.get((filename, point['scope']), [])
            scoped_lines = line_by_scope.get((filename, point['scope']), set())
            if _covered(point, scoped_arcs, scoped_lines):
                covered += 1
        total_points += len(module_points)
        total_covered += covered
        rows.append({'module': filename, 'points': len(module_points), 'covered': covered,
                     'percent': round(100.0 * covered / len(module_points), 1)})
    # 无决策点的 L0/L1 模块同样登记（percent=100，棘轮含义：新增分支必须被测到）
    for name in names:
        filename = name + '.py'
        if filename not in points_by_module:
            rows.append({'module': filename, 'points': 0, 'covered': 0, 'percent': 100.0})
    rows.sort(key=lambda row: (row['percent'], row['module']))
    return {'tool': 'scripts/branch_coverage_report.py',
            'scope': 'L0/L1 顶层模块定向测量（tests/architecture/_layers.py 登记层 0/1；'
                     '不是全量套件分支覆盖率）',
            'metric': '决策点双结果覆盖：if/loop 体进入且条件走完；try handler 进入且干净路径走完；'
                      'match case 进入且（无 case _ 时）落空路径走完。单行复合语句与表达式短路不计。',
            'targets': list(targets), 'tests_ok': result.wasSuccessful(),
            'points_total': total_points, 'points_covered': total_covered,
            'modules': rows, 'modules_total': len(rows)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('targets', nargs='+', help='unittest 目标名，如 tests.test_artifact_schema')
    parser.add_argument('--json', type=Path, default=None, help='把结果写入该 JSON 路径')
    parser.add_argument('--quiet', action='store_true', help='只打印有决策点的模块')
    args = parser.parse_args(argv)
    report = measure(args.targets)
    for row in report['modules']:
        if row['points'] or not args.quiet:
            print('%-46s %5.1f%%  %3d/%3d' % (row['module'], row['percent'], row['covered'], row['points']))
    print('模块：%d；决策点：%d/%d；目标用例：%s'
          % (report['modules_total'], report['points_covered'], report['points_total'],
             '全通过' if report['tests_ok'] else '存在失败／错误'))
    if not report['tests_ok']:
        print('目标用例未全通过，覆盖率不可信，未写入基线。')
        return 1
    if args.json is not None:
        target = args.json if args.json.is_absolute() else PROGRAM / args.json
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        print('已写入 %s' % target)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
