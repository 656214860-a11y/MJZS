import ast
import unittest

from tests.architecture._scan import ROOT, parse_desktop


class KeyframeReplaceBoundaryTests(unittest.TestCase):
    def test_l2_lifecycle_service_only_accepts_l3_publishers(self):
        tree = ast.parse((ROOT / 'keyframe_lifecycle_service.py').read_text(encoding='utf-8'))
        names = {'delete_keyframe', 'restore_keyframe', 'replace_keyframe'}
        methods = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
        self.assertEqual(names, {node.name for node in methods})
        for method in methods:
            calls = [node for node in ast.walk(method) if isinstance(node, ast.Call)]
            self.assertFalse(any(isinstance(node.func, ast.Name)
                                 and node.func.id in {'save', 'save_bytes'} for node in calls),
                             method.name + ' 不得在 L2 直写阶段成果')
            self.assertTrue(any(argument.arg == 'publish' for argument in method.args.kwonlyargs),
                            method.name + ' 必须接收 L3 发布器')

    def test_keyframe_page_delegates_replace_persistence_to_service(self):
        tree = parse_desktop()
        desktop = ast.Module(body=[member for cls in tree.body if isinstance(cls, ast.ClassDef) for member in cls.body], type_ignores=[])  # R1504：Desktop 方法分布在 desktop.py 与迁出的 Mixin 类里
        method = next(node for node in desktop.body if isinstance(node, ast.FunctionDef) and node.name == 'storyboard')
        calls = [node for node in ast.walk(method) if isinstance(node, ast.Call)]
        delegated = [node for node in calls if isinstance(node.func, ast.Name)
                     and node.func.id == 'replace_stage_keyframe']
        self.assertEqual(1, len(delegated))
        self.assertFalse(delegated[0].keywords,
                         '桌面层不得自行注入发布器，必须委托 L3 编排入口')
        prohibited = {'save', 'save_bytes', 'write_text', 'write_bytes', 'copy2', 'remove_temporary_file'}
        self.assertFalse(any(isinstance(node.func, ast.Name) and node.func.id in prohibited
                             for node in calls))
