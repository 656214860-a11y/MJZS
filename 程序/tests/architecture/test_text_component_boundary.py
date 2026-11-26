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
    "ui_usage_detail.py": ("HintLabel",),
}
FORBIDDEN_OPTIONS = frozenset({"font", "foreground", "fg"})
RAW_LABELS = frozenset({"tkinter.Label", "tkinter.ttk.Label"})

# L4-U8a（L4-F9）：ui/ 下每个模块里自写字体、颜色的 Label 调用数，只许下降、不许新增。
# 值等于实测：多一处即失败；少了也失败，把登记调小，降到 0 就删掉那一行，不要调大。
# 提示、说明、进度文字用 HintLabel／DescriptionBlock／ProgressLabel，弱化的单行文字用样式 Muted.TLabel。
STYLED_LABEL_CAPS = {
    'asset_detail.py': 11,
    'desktop_shared_menus.py': 6,
    'stage_model_picker.py': 5,
    'desktop_account_page.py': 4,
    'pet_cloud.py': 2,
    'desktop_media_pages.py': 3,
    'desktop_page_nav.py': 3,
    'ui_status_bar.py': 2,
    'desktop_file_card.py': 2,
    'desktop_idea_bubbles.py': 1,
    'desktop_project_pages.py': 2,
    'pet_settings_ui.py': 2,
    'speech_settings_ui.py': 2,
    'ui_media.py': 2,
    'ui_media_player.py': 2,
    'ui_param_panel.py': 2,
    'ui_stage_popups.py': 2,
    'ui_task_progress.py': 2,
    'desktop_login_gate.py': 1,
    'desktop_script_pages.py': 1,
    'pet_models_ui.py': 1,
    'ui_hitl.py': 1,
    'ui_tooltip.py': 1,
    'ui_usage_indicator.py': 1,
    'white_model.py': 1,
}


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


def _styled_label_count(tree):
    """一棵语法树里带 font／fg／foreground 的 tkinter.Label、ttk.Label 调用数。"""
    return sum(name in RAW_LABELS and bool(FORBIDDEN_OPTIONS & {key.arg for key in node.keywords})
               for node, name in _resolved_calls(tree))


def _styled_label_counts():
    """ui/ 下每个模块的实测数；为 0 的不列。"""
    counts = {path.name: _styled_label_count(parse(path)) for path in sorted((ROOT / 'ui').glob('*.py'))}
    return {name: count for name, count in counts.items() if count}


def _styled_label_drift(actual, caps):
    """实测对登记：返回（超过登记的, 登记该调小或删除的）两张清单。"""
    over = ['%s 有 %d 处 > 登记 %d' % (name, count, caps.get(name, 0))
            for name, count in sorted(actual.items()) if count > caps.get(name, 0)]
    stale = []
    for name, cap in sorted(caps.items()):
        count = actual.get(name, 0)
        if not count:
            stale.append('%s 实际 0 处，请从登记表删除' % name)
        elif count < cap:
            stale.append('%s 实际 %d 处，登记 %d，请下调到 %d' % (name, count, cap, count))
    return over, stale


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

    def test_hand_styled_labels_only_decrease(self):
        """ui/ 全部模块：自写字体、颜色的 Label 只许减少，登记值等于实测（L4-F9）。"""
        over, stale = _styled_label_drift(_styled_label_counts(), STYLED_LABEL_CAPS)
        self.assertEqual(over, [], '提示文字请用 HintLabel/DescriptionBlock/ProgressLabel 或样式 '
                                   'Muted.TLabel，不要调大登记值：' + '; '.join(over))
        self.assertEqual(stale, [], '数量已下降，请同步调小登记值：' + '; '.join(stale))

    def test_hand_styled_label_ratchet_catches_drift(self):
        """金丝雀：对源码字符串求值，证明数得出违规、多了少了都报；不改生产文件。"""
        for source, expected in (
            ('import tkinter as tk\ntk.Label(root, font="bad")\ntk.Label(root, text="ok")', 1),
            ('from tkinter import ttk\nttk.Label(root, foreground="red")\nttk.Label(root, fg="red", font="bad")', 2),
            ('from tkinter.ttk import Label as L\nL(root, foreground="red")', 1),
            ('from tkinter import ttk\nttk.Label(root, style="Muted.TLabel")\nttk.Button(root, font="bad")', 0),
            ('from ui_widgets import HintLabel\nHintLabel(root, text="ok")', 0),
        ):
            with self.subTest(canary=source):
                self.assertEqual(_styled_label_count(ast.parse(source)), expected)
        self.assertEqual(_styled_label_drift({'a.py': 2}, {'a.py': 2}), ([], []))
        over, stale = _styled_label_drift({'a.py': 3, 'new.py': 1}, {'a.py': 2})
        self.assertEqual((len(over), stale), (2, []))
        over, stale = _styled_label_drift({'a.py': 1}, {'a.py': 2, 'gone.py': 1})
        self.assertEqual((over, len(stale)), ([], 2))
        self.assertIn('下调到 1', stale[0])
        self.assertIn('删除', stale[1])
