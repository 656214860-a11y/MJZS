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

    def test_recovery_dialog_tables_use_data_table_not_a_page_treeview(self):
        tree = parse(ROOT / 'desktop.py')
        desktop = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                       and node.name == 'Desktop')
        method = next(node for node in desktop.body if isinstance(node, ast.FunctionDef)
                      and node.name == 'open_recycle_recovery')
        direct = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute) and node.func.attr == 'Treeview']
        self.assertEqual(direct, [], '回收站恢复对话框不得退回业务层直接构造 ttk.Treeview')

    def test_project_selection_pages_use_data_table_not_a_page_treeview(self):
        tree = parse(ROOT / 'desktop.py')
        desktop = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                       and node.name == 'Desktop')
        methods = [node for node in desktop.body if isinstance(node, ast.FunctionDef)
                   and node.name in {'__init__', 'choose_project', 'project_home'}]
        direct = [node for method in methods for node in ast.walk(method)
                  if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                  and node.func.attr == 'Treeview']
        self.assertEqual(direct, [], '项目选择页面不得退回业务层直接构造 ttk.Treeview')

    def test_script_file_lists_use_data_table_not_a_page_treeview(self):
        tree = parse(ROOT / 'desktop.py')
        desktop = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                       and node.name == 'Desktop')
        method = next(node for node in desktop.body if isinstance(node, ast.FunctionDef)
                      and node.name == 'writing')
        direct = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute) and node.func.attr == 'Treeview']
        self.assertEqual(direct, [], '剧本文件列表不得退回业务层直接构造 ttk.Treeview')

    def test_keyframe_table_uses_data_table_not_a_page_treeview(self):
        tree = parse(ROOT / 'desktop.py')
        desktop = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                       and node.name == 'Desktop')
        method = next(node for node in desktop.body if isinstance(node, ast.FunctionDef)
                      and node.name == 'storyboard')
        direct = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute) and node.func.attr == 'Treeview']
        self.assertEqual(direct, [], '首帧管理页不得退回业务层直接构造 ttk.Treeview')

    def test_asset_batch_uses_data_table_not_a_page_treeview(self):
        tree = parse(ROOT / 'asset_batch.py')
        method = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                      and node.name == 'show')
        direct = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute) and node.func.attr == 'Treeview']
        self.assertEqual(direct, [], '资产批量生成弹窗不得退回业务层直接构造 ttk.Treeview')

    def test_asset_reference_windows_use_data_table_not_a_page_treeview(self):
        tree = parse(ROOT / 'asset_reference_images.py')
        methods = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                   and node.name in {'show', 'view_references'}]
        direct = [node for method in methods for node in ast.walk(method)
                  if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                  and node.func.attr == 'Treeview']
        self.assertEqual(direct, [], '资产参考图弹窗不得退回业务层直接构造 ttk.Treeview')

    def test_keyframe_comfy_uses_data_table_not_a_page_treeview(self):
        tree = parse(ROOT / 'keyframe_comfy.py')
        method = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                      and node.name == 'show')
        direct = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute) and node.func.attr == 'Treeview']
        self.assertEqual(direct, [], '首帧批量制作弹窗不得退回业务层直接构造 ttk.Treeview')

    def test_local_previs_uses_data_table_not_a_page_treeview(self):
        tree = parse(ROOT / 'local_previs.py')
        method = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                      and node.name == 'show')
        direct = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute) and node.func.attr == 'Treeview']
        self.assertEqual(direct, [], '白模预演页不得退回业务层直接构造 ttk.Treeview')

    def test_main_workbench_uses_data_table_not_a_page_treeview(self):
        tree = parse(ROOT / 'app.py')
        app = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'App')
        method = next(node for node in app.body if isinstance(node, ast.FunctionDef) and node.name == '__init__')
        direct = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute) and node.func.attr == 'Treeview']
        self.assertEqual(direct, [], '主工作台不得退回业务层直接构造 ttk.Treeview')

    def test_asset_picker_uses_data_table_not_a_page_treeview(self):
        tree = parse(ROOT / 'app.py')
        app = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'App')
        method = next(node for node in app.body if isinstance(node, ast.FunctionDef)
                      and node.name == 'open_asset_picker')
        direct = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute) and node.func.attr == 'Treeview']
        self.assertEqual(direct, [], '资产选择弹窗不得退回业务层直接构造 ttk.Treeview')

    def test_model_manager_uses_data_table_not_a_page_treeview(self):
        tree = parse(ROOT / 'pet_models_ui.py')
        method = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                      and node.name == 'open_manager')
        direct = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute) and node.func.attr == 'Treeview']
        self.assertEqual(direct, [], '模型管理页不得退回业务层直接构造 ttk.Treeview')

    def test_reference_wall_uses_data_table_not_a_page_treeview(self):
        tree = parse(ROOT / 'reference_wall.py')
        method = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                      and node.name == 'show')
        direct = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute) and node.func.attr == 'Treeview']
        self.assertEqual(direct, [], '参考图候选墙不得退回业务层直接构造 ttk.Treeview')

    def test_final_storyboard_files_use_data_table_not_a_page_treeview(self):
        tree = parse(ROOT / 'storyboard_files.py')
        method = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                      and node.name == 'show_final')
        direct = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute) and node.func.attr == 'Treeview']
        self.assertEqual(direct, [], '分镜文件页不得退回业务层直接构造 ttk.Treeview')
