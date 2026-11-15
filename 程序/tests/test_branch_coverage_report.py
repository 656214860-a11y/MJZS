# -*- coding: utf-8 -*-
"""branch_coverage_report：决策点静态判定与双结果证据逻辑。"""
import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import branch_coverage_report as bcr


def _points(src):
    return bcr._decision_points(ast.parse(src))


def _point(src, kind=None):
    points = _points(src)
    if kind is not None:
        points = [p for p in points if p['kind'] == kind]
    assert points, '没有产出决策点'
    return points[0]


class StaticShapeTests(unittest.TestCase):
    def test_if_produces_branch_point_with_regions(self):
        p = _point('def f(c):\n    if c:\n        x = 1\n    return x\n')
        self.assertEqual(p['kind'], 'if')
        self.assertEqual(p['scope'], 'f')
        self.assertEqual(p['test'], (2, 3))
        self.assertEqual(p['entry'], 3)
        self.assertEqual(p['body'], (3, 3))

    def test_elif_and_else_each_count(self):
        points = _points('def f(c):\n    if c == 1:\n        x = 1\n'
                         '    elif c == 2:\n        x = 2\n    else:\n        x = 3\n    return x\n')
        self.assertEqual(len(points), 2)
        self.assertTrue(all(p['kind'] == 'if' for p in points))

    def test_single_line_suite_is_skipped(self):
        self.assertEqual(_points('def f(c):\n    if c: return 1\n    return 0\n'), [])
        self.assertEqual(_points('def f(c):\n    while c: break\n'), [])

    def test_while_true_marks_constant_true(self):
        p = _point('def f():\n    while True:\n        break\n', 'loop')
        self.assertTrue(p['constant_true'])
        self.assertEqual(p['span'], (2, 3))

    def test_for_is_loop_kind(self):
        p = _point('def f(xs):\n    for x in xs:\n        print(x)\n    return 0\n', 'loop')
        self.assertFalse(p.get('constant_true'))

    def test_try_finally_without_handlers_is_skipped(self):
        self.assertEqual(_points('def f():\n    try:\n        x = 1\n    finally:\n        x = 2\n'), [])

    def test_try_star_counts_like_try(self):
        p = _point('def f():\n    try:\n        x = 1\n    except* ValueError:\n        x = 2\n', 'try')
        self.assertEqual(p['handler_entries'], [4])

    def test_match_needs_none_without_wildcard(self):
        p = _point('def f(x):\n    match x:\n        case 1:\n            a = 1\n        case _:\n            a = 2\n    return a\n', 'match')
        self.assertNotIn('need_none', p)
        p2 = _point('def f(x):\n    match x:\n        case 1:\n            a = 1\n        case 2:\n            a = 2\n    return a\n', 'match')
        self.assertTrue(p2['need_none'])

    def test_match_same_line_case_body_is_skipped(self):
        self.assertEqual(_points('def f(x):\n    match x:\n        case 1: a = 1\n        case _: a = 2\n'), [])

    def test_scope_qualnames_match_co_qualname_rules(self):
        src = ('def outer():\n'
               '    def inner():\n'
               '        if True:\n'
               '            pass\n'
               '    class C:\n'
               '        def m(self):\n'
               '            for i in range(3):\n'
               '                pass\n'
               '    return inner, C\n'
               'class Top:\n'
               '    def tm(self):\n'
               '        while False:\n'
               '            pass\n')
        scopes = {p['scope'] for p in _points(src)}
        self.assertEqual(scopes, {'outer.<locals>.inner', 'outer.<locals>.C.m', 'Top.tm'})

    def test_module_level_scope_is_module(self):
        p = _point('if True:\n    x = 1\n')
        self.assertEqual(p['scope'], '<module>')


class EvidenceTests(unittest.TestCase):
    """用手工弧/访问行驱动 _covered，验证双结果判定。"""

    def _if_point(self):
        return _point('def f(c):\n    if c:\n        x = 1\n    return x\n')

    def test_if_needs_both_outcomes(self):
        p = self._if_point()
        taken = bcr._covered(p, [(2, 3)], {2, 3, 4})
        exited = bcr._covered(p, [(2, 4)], {2, 4})
        both = bcr._covered(p, [(2, 3), (2, 4)], {2, 3, 4})
        self.assertFalse(taken)
        self.assertFalse(exited)
        self.assertTrue(both)

    def test_if_exit_via_return_counts(self):
        # if 是函数末语句：else 路径直接走出函数（隐式 return → EXIT 弧）
        p = _point('def f(c):\n    if c:\n        return 1\n')
        self.assertTrue(bcr._covered(p, [(2, 3), (3, bcr.EXIT_LINE), (2, bcr.EXIT_LINE)], {2, 3}))

    def test_backward_arc_to_loop_header_counts_as_exit(self):
        p = _point('def f(xs):\n    for i in xs:\n        if i:\n            pass\n', 'if')
        # if 假 → 回到 for 头（第 2 行，位于测试区间之前）也算走出 if
        self.assertTrue(bcr._covered(p, [(3, 2)], {3, 4}))

    def test_while_true_exit_needs_leaving_span(self):
        p = _point('def f():\n    while True:\n        x = 1\n        break\n')
        # 体内 break → 走出 while 范围（第 5 行 return 之后）
        covered = bcr._covered(p, [(4, 5)], {2, 3, 4})
        self.assertTrue(covered)
        # 体→测试行的回边不算退出
        not_covered = bcr._covered(p, [(3, 2)], {2, 3})
        self.assertFalse(not_covered)

    def test_try_needs_handler_and_clean(self):
        p = _point('def f():\n    try:\n        x = 1\n    except ValueError:\n        x = 2\n    return x\n', 'try')
        handler_and_clean = bcr._covered(p, [(3, 4), (3, 6)], {2, 3, 4, 6})
        handler_only = bcr._covered(p, [(3, 4), (5, 6)], {2, 3, 4, 5, 6})
        clean_only = bcr._covered(p, [(3, 6)], {2, 3, 6})
        self.assertTrue(handler_and_clean)
        self.assertFalse(handler_only)
        self.assertFalse(clean_only)

    def test_try_handler_arc_is_not_clean(self):
        p = _point('def f():\n    try:\n        x = 1\n    except ValueError:\n        x = 2\n    return x\n', 'try')
        # 只有 try→handler 的异常弧，没有干净路径
        self.assertFalse(bcr._covered(p, [(3, 4)], {2, 3, 4}))

    def test_match_wildcard_only_needs_case_entry(self):
        p = _point('def f(x):\n    match x:\n        case 1:\n            a = 1\n        case _:\n            a = 2\n    return a\n', 'match')
        self.assertTrue(bcr._covered(p, [], {2, 4}))
        self.assertFalse(bcr._covered(p, [], {2}))

    def test_match_without_wildcard_needs_none_path(self):
        p = _point('def f(x):\n    match x:\n        case 1:\n            a = 1\n        case 2:\n            a = 2\n    return a\n', 'match')
        matched_only = bcr._covered(p, [], {2, 4})
        matched_and_none = bcr._covered(p, [(5, 7)], {2, 4, 5, 7})
        self.assertFalse(matched_only)
        self.assertTrue(matched_and_none)

    def test_scope_isolation(self):
        p = self._if_point()
        # 同文件同行号但不同作用域的弧/访问不计入
        self.assertFalse(bcr._covered(p, [(2, 4)], {2, 4}))


class TracerTests(unittest.TestCase):
    def test_tracer_records_scoped_arcs_and_exit(self):
        src = ('def f(c):\n'
               '    x = 0\n'
               '    if c:\n'
               '        x = 1\n'
               '    return x\n')
        ns = {}
        exec(compile(src, 'tracer_probe.py', 'exec'), ns)
        tracked = {Path('tracer_probe.py').resolve(): 'tracer_probe.py'}
        gtracer, arcs, visited = bcr._make_tracer(tracked)
        sys.settrace(gtracer)
        try:
            ns['f'](1)
            ns['f'](0)
        finally:
            sys.settrace(None)
        scoped = [(s, d) for r, sc, s, d in arcs if r == 'tracer_probe.py' and sc == 'f']
        self.assertIn((3, 4), scoped)   # if → 体
        self.assertIn((3, 5), scoped)   # if → return（else 路径）
        self.assertIn((5, bcr.EXIT_LINE), scoped)
        self.assertIn(('tracer_probe.py', 'f', 4), visited)

    def test_nested_function_scope_isolated(self):
        src = ('def outer():\n'
               '    def inner():\n'
               '        return 7\n'
               '    while True:\n'
               '        inner()\n'
               '        break\n'
               '    return inner\n')
        ns = {}
        exec(compile(src, 'tracer_probe2.py', 'exec'), ns)
        tracked = {Path('tracer_probe2.py').resolve(): 'tracer_probe2.py'}
        gtracer, arcs, visited = bcr._make_tracer(tracked)
        sys.settrace(gtracer)
        try:
            ns['outer']()
        finally:
            sys.settrace(None)
        inner_arcs = [(s, d) for r, sc, s, d in arcs if sc == 'outer.<locals>.inner']
        outer_arcs = [(s, d) for r, sc, s, d in arcs if sc == 'outer']
        # inner 的 return→EXIT 只属于 inner 作用域，不污染 outer 的 while 判定
        self.assertIn((3, bcr.EXIT_LINE), inner_arcs)
        self.assertFalse(any(s == 3 for s, d in outer_arcs))


if __name__ == '__main__':
    unittest.main()
