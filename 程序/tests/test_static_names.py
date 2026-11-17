# -*- coding: utf-8 -*-
"""第 63 期：静态找「引用了却没定义的名字」——就是用户报的 `folder` 那一类崩溃。

用户报的弹窗原文是「制图未完成：name folder is not defined」：`native_assets.run` 里
生成图挪了目录，批次记录那一半没跟着改，`folder` 只被用、没被定义。这种错跑再多界面用例也
逮不到（那一整条路没有用例），只能在源码上静态盯。

只用 ast（本机运行环境里没有 symtable）。宁可漏报、不许误报：看不懂的一律放过。
真跑得起来的模块列表由 ROOT 下的 *.py 决定，与 run_selftests 同源。

运行：python test_static_names.py
"""
import ast
from tests.architecture._scan import PACKAGE_NAMES
import builtins
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, PROGRAM)
os.chdir(PROGRAM)

DUNDER = {'__file__', '__name__', '__doc__', '__package__', '__builtins__', '__spec__',
          '__loader__', '__debug__', '__path__', '__all__'}
KNOWN = set(dir(builtins)) | DUNDER


def args_of(node):
    out = set()
    for item in (getattr(node.args, 'posonlyargs', []) + node.args.args + node.args.kwonlyargs):
        out.add(item.arg)
    for item in (node.args.vararg, node.args.kwarg):
        if item is not None:
            out.add(item.arg)
    return out


def bindings(body):
    """这一层作用域里绑定了哪些名字（不进入嵌套函数的函数体）；顺带认一下 import *。"""
    out = set()
    star = [False]

    def walk(node):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.name == '*':
                    star[0] = True
                else:
                    out.add((alias.asname or alias.name).split('.')[0])
            return
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(node.name)
            for decorator in node.decorator_list:
                walk(decorator)
            args = getattr(node, 'args', None)
            if args is not None:
                for default in list(args.defaults) + [d for d in args.kw_defaults if d]:
                    walk(default)
            return
        if isinstance(node, ast.Lambda):
            for default in list(node.args.defaults) + [d for d in node.args.kw_defaults if d]:
                walk(default)
            return
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            out.add(node.id)
            return
        if isinstance(node, ast.ExceptHandler) and node.name:
            out.add(node.name)
        if isinstance(node, ast.Global):
            out.update(node.names)
        for child in ast.iter_child_nodes(node):
            walk(child)

    for node in body:
        walk(node)
    return out, star[0]


class _Visitor(ast.NodeVisitor):
    """逐层作用域记「读了哪些名字」，收尾时对着本层与所有外层的绑定名核一遍。"""

    def __init__(self, visible):
        self.problems = []
        self.visible = visible
        self.stack = [{'names': set(visible), 'loads': [], 'label': '<module>'}]

    def visit_Name(self, node):
        entry = self.stack[-1]
        if isinstance(node.ctx, ast.Load):
            entry['loads'].append(node.id)
        else:
            entry['names'].add(node.id)

    def visit_ExceptHandler(self, node):
        if node.name:
            self.stack[-1]['names'].add(node.name)
        self.generic_visit(node)

    def visit_Lambda(self, node):
        self._scope([node.body], args_of(node), '<lambda>')

    def visit_FunctionDef(self, node):
        self._scope(list(node.body), args_of(node), node.name)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        self._scope(list(node.body), set(), node.name)

    def _scope(self, body, names, label):
        owned, _star = bindings(body)
        scope = {'names': set(names) | owned, 'loads': [], 'label': label}
        self.stack.append(scope)
        for item in body:
            self.visit(item)
        self.stack.pop()
        known = set()
        for layer in self.stack:
            known |= layer['names']
        for name in scope['loads']:
            if name in scope['names'] or name in known or name in KNOWN:
                continue
            self.problems.append((label, name))

    def run(self, tree):
        for node in tree.body:
            self.visit(node)
        for name in self.stack[0]['loads']:
            if name in self.stack[0]['names'] or name in KNOWN:
                continue
            self.problems.append(('<module>', name))
        return self.problems


def undefined_names(source, filename='<source>'):
    """返回 [(作用域名, 名字)]：引用了却没定义的。import * 的文件一律放过（说不清）。"""
    tree = ast.parse(source, filename=filename)
    visible, star = bindings(tree.body)
    if star:
        return []
    return _Visitor(visible).run(tree)


def scan_file(path):
    return undefined_names(Path(path).read_text(encoding='utf-8'), Path(path).name)


class CheckerTests(unittest.TestCase):
    """先证明这把尺子量得准：真错要报，容易看走眼的几处不许报。"""

    def test_a_name_that_is_only_used_is_reported(self):
        found = undefined_names('def cleanup(path):\n    pass\n\n\ndef run():\n'
                                '    cleanup(folder)\n')
        self.assertEqual(found, [('run', 'folder')])

    def test_names_defined_later_in_the_module_are_fine(self):
        self.assertEqual(undefined_names('def a():\n    b()\n\n\ndef b():\n    pass\n'), [])

    def test_names_bound_later_in_the_same_scope_are_fine(self):
        self.assertEqual(undefined_names('def outer():\n    def inner():\n        return flag\n'
                                         '    flag = 1\n    return inner\n'), [])

    def test_parameters_locals_except_names_and_imports_are_fine(self):
        self.assertEqual(undefined_names('import os\n\n\ndef a(x):\n    try:\n        pass\n'
                                         '    except ValueError as exc:\n        print(exc, x, os)\n'
                                         '    total = 0\n    return total\n'), [])

    def test_comprehension_and_class_names_are_fine(self):
        self.assertEqual(undefined_names('class A:\n    pass\n\n\n'
                                         'def a(rows):\n    return [row for row in rows]\n'), [])

    def test_an_import_star_file_is_left_alone(self):
        self.assertEqual(undefined_names('from os import *\n\n\ndef a():\n    return getcwd()\n'), [])


class ProjectTests(unittest.TestCase):
    """本项目所有模块都不许有这一类名字。"""

    def modules(self):
        files = list(Path(PROGRAM).glob('*.py'))
        for package in PACKAGE_NAMES:
            directory = Path(PROGRAM) / package
            if directory.is_dir():
                files += [p for p in directory.rglob('*.py') if p.name != '__init__.py']
        return sorted(files)

    def test_every_module_defines_the_names_it_uses(self):
        broken = []
        for path in self.modules():
            try:
                found = scan_file(path)
            except SyntaxError as exc:
                broken.append('%s 语法错：%s' % (path.name, exc))
                continue
            for scope, name in found:
                broken.append('%s：%s 里用了没定义的 %s' % (path.name, scope, name))
        self.assertEqual(broken, [], '这些名字只在用、没在定义（用户看到的是「制图未完成：name '
                                    'xxx is not defined」）：\n' + '\n'.join(broken))

    def test_the_scan_reaches_the_known_module(self):
        """别把「一个文件都没扫到」当成通过。"""
        names = {path.name for path in self.modules()}
        self.assertIn('native_assets.py', names)
        self.assertGreater(len(names), 50)


if __name__ == '__main__':
    unittest.main(verbosity=2)
