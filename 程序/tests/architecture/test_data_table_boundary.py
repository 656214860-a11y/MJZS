"""已迁移的表格页不得重新绕过统一 DataTable。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import ROOT, parse


class DataTableBoundaryTests(unittest.TestCase):
    def test_continuity_tables_use_data_table_not_a_page_treeview(self):
        tree = parse(ROOT / 'desktop.py')
        desktop = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                       and node.name == 'Desktop')
        method = next(node for node in desktop.body if isinstance(node, ast.FunctionDef)
                      and node.name == 'continuity_page')
        direct = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute) and node.func.attr == 'Treeview']
        self.assertEqual(direct, [], '连贯性清单页不得退回业务层直接构造 ttk.Treeview')
        imports = [alias.name for node in tree.body if isinstance(node, ast.ImportFrom)
                   for alias in node.names if node.module == 'ui_widgets']
        self.assertIn('DataTable', imports)
    def test_storyboard_file_table_uses_data_table_not_a_page_treeview(self):
        tree = parse(ROOT / 'storyboard_table_ui.py')
        direct_treeviews = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                            and isinstance(node.func, ast.Attribute)
                            and node.func.attr == 'Treeview']
        self.assertEqual(direct_treeviews, [],
                         '首迁表格页不得退回业务层直接构造 ttk.Treeview')
        imports = [alias.name for node in tree.body if isinstance(node, ast.ImportFrom)
                   for alias in node.names if node.module == 'ui_widgets']
        self.assertIn('DataTable', imports)

    def test_asset_table_uses_data_table_not_a_page_treeview(self):
        tree = parse(ROOT / 'desktop.py')
        desktop = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                       and node.name == 'Desktop')
        method = next(node for node in desktop.body if isinstance(node, ast.FunctionDef)
                      and node.name == 'assets')
        direct = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute) and node.func.attr == 'Treeview']
        self.assertEqual(direct, [], '资产管理页不得退回业务层直接构造 ttk.Treeview')
