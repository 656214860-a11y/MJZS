"""已迁移的表格页不得重新绕过统一 DataTable。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import ROOT, parse, parse_desktop


EXCLUDED_PARTS = {"tests", "tasks_round", "维护记录", ".git", "__pycache__"}


class DataTableBoundaryTests(unittest.TestCase):
    def test_only_project_navigation_uses_raw_treeview_recursively(self):
        """表格一律经 DataTable；仅项目导航保留树形选择器语义。"""
        actual = {}
        for path in ROOT.rglob('*.py'):
            if (path.name == 'ui_widgets.py'
                    or any(part in EXCLUDED_PARTS for part in path.parts)):
                continue
            calls = [node for node in ast.walk(parse(path)) if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Attribute) and node.func.attr == 'Treeview']
            if calls:
                actual[str(path.relative_to(ROOT))] = len(calls)
        self.assertEqual(actual, {'desktop_project_pages.py': 2},  # R2897：侧栏项目树改分组筛选＋选择器，desktop.py 不再有树；项目选择弹窗与首页仍各一处
                         
                         '业务数据表必须通过 DataTable；项目树是唯一语义导航例外')

    def test_continuity_tables_use_data_table_not_a_page_treeview(self):
        tree = parse_desktop()
        desktop = ast.Module(body=[member for cls in tree.body if isinstance(cls, ast.ClassDef) for member in cls.body], type_ignores=[])  # R1499：Desktop 方法分布在 desktop.py 与迁出的 Mixin 类里
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
        tree = parse_desktop()
        desktop = ast.Module(body=[member for cls in tree.body if isinstance(cls, ast.ClassDef) for member in cls.body], type_ignores=[])  # R1499：Desktop 方法分布在 desktop.py 与迁出的 Mixin 类里
        method = next(node for node in desktop.body if isinstance(node, ast.FunctionDef)
                      and node.name == 'assets')
        direct = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute) and node.func.attr == 'Treeview']
        self.assertEqual(direct, [], '资产管理页不得退回业务层直接构造 ttk.Treeview')

    def test_recovery_dialog_tables_use_data_table_not_a_page_treeview(self):
        tree = parse_desktop()
        desktop = ast.Module(body=[member for cls in tree.body if isinstance(cls, ast.ClassDef) for member in cls.body], type_ignores=[])  # R1499：Desktop 方法分布在 desktop.py 与迁出的 Mixin 类里
        method = next(node for node in desktop.body if isinstance(node, ast.FunctionDef)
                      and node.name == 'open_recycle_recovery')
        direct = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute) and node.func.attr == 'Treeview']
        self.assertEqual(direct, [], '回收站恢复对话框必须通过 DataTable 构造表格')

    def test_project_selection_pages_use_data_table_not_a_page_treeview(self):
        tree = parse_desktop()
        desktop = ast.Module(body=[member for cls in tree.body if isinstance(cls, ast.ClassDef) for member in cls.body], type_ignores=[])  # R1499：Desktop 方法分布在 desktop.py 与迁出的 Mixin 类里
        methods = [node for node in desktop.body if isinstance(node, ast.FunctionDef)
                   and node.name in {'__init__', '_init_window_and_sidebar', 'choose_project', 'project_home'}]  # R1808：__init__ 的侧栏段切到 _init_window_and_sidebar，计数断言不变
        direct = [node for method in methods for node in ast.walk(method)
                  if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                  and node.func.attr == 'Treeview']
        self.assertEqual(len(direct), 1,
                         'R2897 侧栏项目树改选择器后，仅项目主页保留树形导航选择器')

    def test_script_file_lists_use_data_table_not_a_page_treeview(self):
        tree = parse_desktop()
        desktop = ast.Module(body=[member for cls in tree.body if isinstance(cls, ast.ClassDef) for member in cls.body], type_ignores=[])  # R1499：Desktop 方法分布在 desktop.py 与迁出的 Mixin 类里
        # R1817：writing 的闭包改写成了 _WritingPage 类，页面构造代码现在在类里；薄方法和新类两处都扫
        methods = [node for node in desktop.body if isinstance(node, ast.FunctionDef) and node.name == 'writing'] + [cls for cls in tree.body if isinstance(cls, ast.ClassDef) and cls.name == '_WritingPage']
        self.assertEqual(len(methods), 2)
        direct = [node for method in methods for node in ast.walk(method) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute) and node.func.attr == 'Treeview']
        self.assertEqual(direct, [], '剧本文件列表必须通过 DataTable 构造表格')

    def test_keyframe_table_uses_data_table_not_a_page_treeview(self):
        tree = parse_desktop()
        desktop = ast.Module(body=[member for cls in tree.body if isinstance(cls, ast.ClassDef) for member in cls.body], type_ignores=[])  # R1499：Desktop 方法分布在 desktop.py 与迁出的 Mixin 类里
        # R1814：storyboard 的闭包改写成了 _FirstFramePage 类，页面构造代码现在在类里；薄方法和新类两处都扫
        methods = [node for node in desktop.body if isinstance(node, ast.FunctionDef) and node.name == 'storyboard']             + [cls for cls in tree.body if isinstance(cls, ast.ClassDef) and cls.name == '_FirstFramePage']
        self.assertEqual(len(methods), 2)
        direct = [node for method in methods for node in ast.walk(method) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute) and node.func.attr == 'Treeview']
        self.assertEqual(direct, [], '首帧管理页必须通过 DataTable 构造表格')

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
        self.assertEqual(direct, [], '首帧批量制作弹窗必须通过 DataTable 构造表格')

    def test_local_previs_uses_data_table_not_a_page_treeview(self):
        tree = parse(ROOT / 'local_previs.py')
        method = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                      and node.name == 'show')
        direct = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute) and node.func.attr == 'Treeview']
        self.assertEqual(direct, [], '白模预演页必须通过 DataTable 构造表格')

    def test_main_workbench_uses_data_table_not_a_page_treeview(self):
        tree = parse(ROOT / 'app.py')
        app = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'App')
        method = next(node for node in app.body if isinstance(node, ast.FunctionDef) and node.name == '__init__')
        direct = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute) and node.func.attr == 'Treeview']
        self.assertEqual(direct, [], '主工作台的数据表必须通过 DataTable 构造')

    def test_asset_picker_uses_data_table_not_a_page_treeview(self):
        tree = parse(ROOT / 'app.py')
        app = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'App')
        method = next(node for node in app.body if isinstance(node, ast.FunctionDef)
                      and node.name == 'open_asset_picker')
        direct = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute) and node.func.attr == 'Treeview']
        self.assertEqual(direct, [], '资产选择弹窗必须通过 DataTable 构造表格')

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
        self.assertEqual(direct, [], '参考图候选墙必须通过 DataTable 构造表格')

    def test_final_storyboard_files_use_data_table_not_a_page_treeview(self):
        tree = parse(ROOT / 'storyboard_files.py')
        # R1813：show_final 的闭包改写成了 _FinalStoryboardPage 类，页面构造代码现在在类里；两处都扫
        methods = [node for node in tree.body
                   if (isinstance(node, ast.FunctionDef) and node.name == 'show_final')
                   or (isinstance(node, ast.ClassDef) and node.name == '_FinalStoryboardPage')]
        self.assertEqual(len(methods), 2)
        direct = [node for method in methods for node in ast.walk(method) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute) and node.func.attr == 'Treeview']
        self.assertEqual(direct, [], '分镜文件页必须通过 DataTable 构造表格')
