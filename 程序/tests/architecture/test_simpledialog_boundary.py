"""生产代码禁止再直调 tkinter.simpledialog；统一文本输入入口为 ui_widgets.ask_string。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import ROOT, production_files_recursive


def _simpledialog_refs(tree):
    """返回 tree 中所有 simpledialog 引用（导入或名字引用）的行号。

    覆盖四类回退形态：``import tkinter.simpledialog``、``from tkinter import
    simpledialog``、``from tkinter.simpledialog import askstring`` 与裸
    ``simpledialog.xxx`` 名字引用；迁移完成后白名单为空，任何一处即红。
    """
    refs = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == 'simpledialog' or alias.name.startswith('tkinter.simpledialog'):
                    refs.append(node.lineno)
        elif isinstance(node, ast.ImportFrom):
            if node.module and 'simpledialog' in node.module:
                refs.append(node.lineno)
            for alias in node.names:
                if alias.name == 'simpledialog':
                    refs.append(node.lineno)
        elif isinstance(node, ast.Name) and node.id == 'simpledialog':
            refs.append(node.lineno)
    return sorted(set(refs))


class SimpleDialogBoundaryTests(unittest.TestCase):
    def test_production_modules_have_no_simpledialog(self):
        """simpledialog 已全部迁入 ui_widgets.ask_string：生产模块零容忍（白名单为空）。"""
        actual = {}
        for path in production_files_recursive():
            refs = _simpledialog_refs(ast.parse(path.read_text(encoding='utf-8'), filename=str(path)))
            if refs:
                actual[path.name] = refs
        self.assertEqual(actual, {}, '生产模块必须经 ui_widgets.ask_string 输入文本：' + str(actual))
