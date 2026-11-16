"""The final storyboard page delegates its selection preference to its controller."""
import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class StoryboardFinalSelectionBoundaryTests(unittest.TestCase):
    def test_final_viewer_delegates_selection_persistence(self):
        tree = ast.parse((ROOT / 'storyboard_files.py').read_text(encoding='utf-8'))
        imported = {name.name for node in tree.body if isinstance(node, ast.ImportFrom)
                    and node.module in {'storyboard_final_controller',
                                        'orchestrator.storyboard_final_controller'}
                    for name in node.names}
        self.assertIn('FinalStoryboardController', imported)
        show_final = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == '_FinalStoryboardPage')  # R1813：show_final 的闭包改写成了类，嵌套函数成了它的方法；断言不变
        choose = next(node for node in ast.walk(show_final) if isinstance(node, ast.FunctionDef) and node.name == 'choose')
        calls = [node for node in ast.walk(choose) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute) and node.func.attr == 'choose']
        self.assertEqual(len(calls), 1)
        direct = [node.lineno for node in ast.walk(choose) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Name) and node.func.id == 'save']
        self.assertEqual(direct, [], '定稿页不得直接保存查看偏好: ' + str(direct))

    def test_desktop_finalization_delegates_selection_persistence(self):
        tree = ast.parse((ROOT / 'desktop.py').read_text(encoding='utf-8'))
        desktop = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Desktop')
        apply_final = next(node for node in desktop.body if isinstance(node, ast.FunctionDef) and node.name == 'apply_final')
        calls = [node for node in ast.walk(apply_final) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == 'remember_final_view']
        self.assertEqual(len(calls), 1)
        direct = [node.lineno for node in ast.walk(apply_final) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Name) and node.func.id == 'save']
        self.assertEqual(direct, [], '定稿收尾不得直接保存查看偏好: ' + str(direct))
