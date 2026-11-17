"""文字层级组件的页面边界：视觉参数只能留在 ui_widgets。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import ROOT, entity_file, parse


TEXT_PAGE_COMPONENTS = {
    "skill_panel.py": ("HintLabel", "DescriptionBlock", "ProgressLabel"),
    "agent/prompt_optimizer.py": ("DescriptionBlock",),
    "seedream_settings.py": ("DescriptionBlock", "ProgressLabel"),
    "qwen_setup_dialog.py": ("DescriptionBlock", "ProgressLabel"),
    "tts_settings.py": ("DescriptionBlock", "ProgressLabel"),
    "asset_batch.py": ("DescriptionBlock", "ProgressLabel"),
    "keyframe_comfy.py": ("DescriptionBlock", "ProgressLabel"),
}
FORBIDDEN_OPTIONS = frozenset({"font", "foreground", "fg"})


def _resolved_calls(tree):
    """静态导入/赋值别名；不声称处理动态 getattr 或跨函数数据流。"""
    names = {}
    nodes = list(ast.walk(tree))
    for node in nodes:
        if isinstance(node, ast.Import):
            for alias in node.names:
                names[alias.asname or alias.name.split('.')[0]] = alias.name if alias.asname else alias.name.split('.')[0]
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            for alias in node.names:
                names[alias.asname or alias.name] = node.module + '.' + alias.name
    def resolve(node):
        if isinstance(node, ast.Name):return names.get(node.id, '')
        if isinstance(node, ast.Attribute):
            base = resolve(node.value)
            return base + '.' + node.attr if base else ''
        return ''
    for _ in nodes:
        changed = False
        for node in nodes:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                value = resolve(node.value)
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Name) and value and target.id not in names:
                        names[target.id] = value; changed = True
        if not changed:break
    return [(node, resolve(node.func)) for node in nodes if isinstance(node, ast.Call)]


# 只冻结本批五处描述，不把标题、就绪/锁定语义色或窄缩略图文字冒充已迁移。
ASSET_DESCRIPTION_SITES = {
    '_gates_block': ("'理由：' + str(item.get('reason') or '')",),
    '_board_block': ('note',),
    '_anchor_block': ("title + '：' + text",),
    '_role_block': ("'负责：' + role", "'不继承：' + exclude"),
}


def _asset_description_violations(tree):
    resolved = {id(node):name for node, name in _resolved_calls(tree)}
    violations = []
    for function, expressions in ASSET_DESCRIPTION_SITES.items():
        scopes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == function]
        for expression in expressions:
            expected = ast.dump(ast.parse(expression, mode='eval').body)
            calls = [node for scope in scopes for node in ast.walk(scope) if isinstance(node, ast.Call)
                     and any(key.arg == 'text' and ast.dump(key.value) == expected for key in node.keywords)]
            if len(calls) != 1:
                violations.append(f'{function}: 缺失或重复描述 {expression}')
                continue
            call = calls[0]
            if (resolved[id(call)] != 'ui_widgets.DescriptionBlock'
                    or any(key.arg != 'text' for key in call.keywords)):
                violations.append(f'{function}:{call.lineno} 描述须经 DescriptionBlock 且不得覆写样式')
    return violations


class TextComponentBoundaryTests(unittest.TestCase):
    def test_migrated_pages_import_their_text_components(self):
        """已迁移页面必须继续经 ui_widgets 的文字语义组件。"""
        for filename, expected in TEXT_PAGE_COMPONENTS.items():
            tree = parse(entity_file(filename[:-3]))
            imported = {
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module == "ui_widgets"
                for alias in node.names
            }
            self.assertTrue(set(expected) <= imported,
                            f"{filename} 应导入：{', '.join(expected)}")
        self.assertEqual(_asset_description_violations(parse(entity_file('asset_detail'))), [])

    def test_migrated_pages_do_not_hand_style_raw_labels(self):
        """迁移页面的提示/说明/进度不得退回局部文字样式。"""
        violations = []
        for filename in TEXT_PAGE_COMPONENTS:
            tree = parse(entity_file(filename[:-3]))
            for node, resolved in _resolved_calls(tree):
                if resolved not in {'tkinter.Label', 'tkinter.ttk.Label'}:
                    continue
                options = {keyword.arg for keyword in node.keywords if keyword.arg}
                invalid = sorted(options & FORBIDDEN_OPTIONS)
                if invalid:
                    violations.append(f"{filename}:{node.lineno} {', '.join(invalid)}")
        self.assertEqual(violations, [],
                         "页面文字须用 HintLabel/DescriptionBlock/ProgressLabel："
                         + "; ".join(violations))
        for source in (
            'import tkinter as t\nt.Label(root, foreground="red")',
            'from tkinter import ttk as t\nt.Label(root, font="bad")',
            'import tkinter.ttk as t\nt.Label(root, fg="red")',
            'from tkinter.ttk import Label as L\nL(root, foreground="red")',
            'from tkinter import Label\nL = Label\nL(root, font="bad")',
        ):
            with self.subTest(canary=source):
                self.assertEqual(sum(name in {'tkinter.Label', 'tkinter.ttk.Label'}
                                     and bool({k.arg for k in node.keywords} & FORBIDDEN_OPTIONS)
                                     for node, name in _resolved_calls(ast.parse(source))), 1)
        source = entity_file('asset_detail').read_text(encoding='utf-8')
        for replacement in ('RawLabel', 'DescriptionBlock'):
            mutated = 'from tkinter.ttk import Label as RawLabel\n' + source.replace(
                "DescriptionBlock(foot, text=note)", f'{replacement}(foot, text=note, foreground="red")')
            with self.subTest(asset_canary=replacement):
                self.assertTrue(_asset_description_violations(ast.parse(mutated)))
