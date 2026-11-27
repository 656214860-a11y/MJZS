"""首迁页面不得退回手写 PhotoImage。"""
import ast
import unittest

from tests.architecture._scan import EXCLUDED_PARTS as _BASE_EXCLUDED_PARTS, ROOT as PROGRAM, entity_file


EXCLUDED_PARTS = _BASE_EXCLUDED_PARTS | {"skills"}
# UI 图标经 IconLoader、缩略图经 asset_thumbs；圆角按钮/卡片底图由 ui_widgets 用标准库生成（2026-10-21 起）。
PHOTOIMAGE_OWNERS = {"ui_icons.py", "asset_thumbs.py", "ui_rounded.py"}


class UiIconsBoundaryTests(unittest.TestCase):
    def test_photoimage_creation_has_only_icon_and_thumbnail_owners(self):
        """UI 图标只能经共享加载器；资产媒体缩略图保留专用缓存实现。"""
        offenders = []
        for path in PROGRAM.rglob("*.py"):
            if (path.name in PHOTOIMAGE_OWNERS
                    or EXCLUDED_PARTS.intersection(path.relative_to(PROGRAM).parts)):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "PhotoImage"):
                    offenders.append(f"{path.relative_to(PROGRAM)}:{node.lineno}")
        self.assertEqual(offenders, [], "页面图标必须经 IconLoader：" + "; ".join(offenders))

    def test_video_back_uses_shared_icon_loader(self):
        tree = ast.parse(entity_file('video_navigation').read_text(encoding='utf-8'))
        show_back = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'show_back')
        source = ast.unparse(show_back)
        self.assertIn('IconLoader.return_arrow', source)
        self.assertNotIn('PhotoImage(', source)
