"""The final storyboard page delegates editing state to its controller."""
import ast
import unittest

from tests.architecture._scan import ROOT


class StoryboardEditBoundaryTests(unittest.TestCase):
    def test_final_editor_delegates_document_persistence(self):
        tree = ast.parse((ROOT / 'storyboard_files.py').read_text(encoding='utf-8'))
        imported = {name.name for node in tree.body if isinstance(node, ast.ImportFrom)
                    and node.module == 'storyboard_final_controller' for name in node.names}
        self.assertIn('FinalStoryboardController', imported)
        show_final = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'show_final')
        ask_save = next(node for node in ast.walk(show_final)
                        if isinstance(node, ast.FunctionDef) and node.name == 'ask_save')
        calls = [node for node in ast.walk(ask_save) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute) and node.func.attr == 'save_edited']
        self.assertEqual(len(calls), 1)
        direct = [node.lineno for node in ast.walk(ask_save) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Name) and node.func.id == 'save']
        self.assertEqual(direct, [], '定稿正文编辑不得直接保存: ' + str(direct))
