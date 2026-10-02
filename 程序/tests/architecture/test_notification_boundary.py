"""首迁失败反馈必须经过统一通知分发器。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import ROOT, parse


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
            count = len(_display_messageboxes(parse(ROOT / filename)))
            if count > maximum:
                actual[filename] = f'{count}>{maximum}'
        self.assertEqual(actual, {}, '业务页历史裸通知数量只能下降：' + str(actual))
LEGACY_MESSAGEBOX_MAX = {
    'app.py': 7, 'asset_detail.py': 4, 'asset_prompt_rules.py': 2,
    'asset_reference_import.py': 2, 'background_characters.py': 3,
    'cloud_assets.py': 1, 'cloud_video.py': 3, 'desktop.py': 13,
    'desktop_launcher.py': 1, 'keyframe_comfy.py': 1, 'local_previs.py': 8,
    'native_assets.py': 2, 'prompt_window.py': 1, 'qwen_setup.py': 2,
    'reference_wall.py': 2, 'seedream_settings.py': 1, 'skill_panel.py': 8,
    'storyboard_files.py': 2, 'tts_settings.py': 1, 'white_model.py': 2,
    'workflow_settings.py': 1, 'agent/prompt_optimizer.py': 2,
}

def _display_messageboxes(tree):
    return [node for node in ast.walk(tree) if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
            and node.func.value.id == 'messagebox'
            and node.func.attr in {'showerror', 'showwarning', 'showinfo'}]
