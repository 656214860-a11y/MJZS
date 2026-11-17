"""首迁失败反馈必须经过统一通知分发器。"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

from tests.architecture._scan import ROOT, entity_file, parse, module_scan_files


class NotificationBoundaryTests(unittest.TestCase):
    def test_desktop_safe_uses_the_notification_dispatcher(self):
        tree = parse(ROOT / "desktop.py")
        method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                      and node.name == "safe")
        messagebox_errors = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                             and isinstance(node.func, ast.Attribute)
                             and isinstance(node.func.value, ast.Name)
                             and node.func.value.id == "messagebox"
                             and node.func.attr == "showerror"]
        notifier_errors = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                           and isinstance(node.func, ast.Attribute)
                           and isinstance(node.func.value, ast.Attribute)
                           and node.func.value.attr == "notifier"
                           and node.func.attr == "error"]
        self.assertEqual(messagebox_errors, [], "首迁错误链不得退回裸 messagebox")
        self.assertEqual(len(notifier_errors), 1, "Desktop.safe 必须经统一通知入口")

    def test_desktop_display_notifications_do_not_increase(self):
        tree = parse(ROOT / "desktop.py")
        self.assertLessEqual(len(_display_messageboxes(tree)), LEGACY_MESSAGEBOX_MAX['desktop.py'],
                             'Desktop 历史裸通知数量只能下降')

    def test_business_pages_have_no_direct_display_messagebox_calls(self):
        actual = {}
        for filename, maximum in LEGACY_MESSAGEBOX_MAX.items():
            count = len(_display_messageboxes(parse(entity_file(Path(filename).stem) if '/' not in filename else ROOT / filename)))
            if count > maximum:
                actual[filename] = f'{count}>{maximum}'
        self.assertEqual(actual, {}, '业务页不得绕过统一通知入口：' + str(actual))

    def test_all_root_business_modules_use_the_notification_entry(self):
        direct = {
            path.name: len(_display_messageboxes(parse(path)))
            for path in module_scan_files() if path.name != 'ui_widgets.py'
            if _display_messageboxes(parse(path))
        }
        self.assertEqual(direct, {}, '根目录业务模块不得直接显示 messagebox：' + str(direct))

    def test_all_production_modules_use_the_notification_entry(self):
        direct = {}
        for path in ROOT.rglob('*.py'):
            relative = path.relative_to(ROOT)
            if (path.name.startswith('test') or 'tests' in relative.parts
                    or 'tasks_round' in relative.parts or '维护记录' in relative.parts
                    or 'voice_asr_venv' in relative.parts
                    or path.name == 'ui_widgets.py'):
                continue
            count = len(_display_messageboxes(parse(path)))
            if count:
                direct[str(relative)] = count
        self.assertEqual(direct, {}, '生产模块不得绕过统一通知入口：' + str(direct))
LEGACY_MESSAGEBOX_MAX = {
    'app.py': 0, 'asset_detail.py': 0, 'asset_prompt_rules.py': 0,
    'asset_reference_import.py': 0, 'background_characters.py': 0,
    'cloud_assets.py': 0, 'cloud_video.py': 0, 'desktop.py': 0,
    'desktop_launcher.py': 0, 'keyframe_comfy.py': 0, 'local_previs.py': 0,
    'native_assets.py': 0, 'prompt_window.py': 0, 'qwen_setup_dialog.py': 0,
    'reference_wall.py': 0, 'seedream_settings.py': 0, 'skill_panel.py': 0,
    'storyboard_files.py': 0, 'tts_settings.py': 0, 'white_model.py': 0,
    'workflow_settings_dialog.py': 0, 'agent/prompt_optimizer.py': 0,
}

def _display_messageboxes(tree):
    return [node for node in ast.walk(tree) if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
            and node.func.value.id == 'messagebox'
            and node.func.attr in {'showerror', 'showwarning', 'showinfo'}]
