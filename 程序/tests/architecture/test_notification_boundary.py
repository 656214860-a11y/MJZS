"""首迁失败反馈必须经过统一通知分发器。"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

from tests.architecture._scan import EXCLUDED_PARTS, ROOT, entity_file, parse, module_scan_files


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
            if (path.name.startswith('test') or EXCLUDED_PARTS.intersection(relative.parts)
                    or path.name == 'ui_widgets.py'):
                continue
            count = len(_display_messageboxes(parse(path)))
            if count:
                direct[str(relative)] = count
        self.assertEqual(direct, {}, '生产模块不得绕过统一通知入口：' + str(direct))

    def test_ui_modules_do_not_import_messagebox(self):
        imported = {
            path.name for path in (ROOT / 'ui').glob('*.py')
            if _imports_messagebox(parse(path))
        }
        unexpected = imported - UI_MESSAGEBOX_IMPORT_ALLOWED
        self.assertEqual(unexpected, set(), '界面模块不得引入 messagebox：' + str(sorted(unexpected)))
        stale = UI_MESSAGEBOX_IMPORT_ALLOWED - imported
        self.assertEqual(stale, set(), '允许名单里的模块已不再引入 messagebox，请从名单移除：' + str(sorted(stale)))

    def test_notification_calls_never_render_the_bound_exception(self):
        """EC-3：提示调用的文字参数不得直接渲染所在 except 绑定的异常变量。"""
        violations = []
        for path in _notification_scan_files():
            for lineno, detail in _exception_text_leaks(parse(path)):
                violations.append('%s:%d %s' % (path.relative_to(ROOT).as_posix(), lineno, detail))
        self.assertEqual(sorted(violations), [],
                         '失败提示里的异常原文请经 error_codes.user_text()：\n'
                         + '\n'.join(sorted(violations)))

    def test_exception_text_guard_canary(self):
        """金丝雀：对源码字符串求值——违规写法抓得到，已迁移与无关写法不抓。"""
        cases = (
            ("try:\n    work()\nexcept Exception as e:\n    notify(win, str(e))", 1),
            ("try:\n    work()\nexcept Exception as exc:\n"
             "    self.notifier.error('导出失败：'+str(exc), title='导出')", 1),
            ("try:\n    work()\nexcept Exception as e:\n    self.notifier.warning(str(e))", 1),
            ("try:\n    work()\nexcept (ValueError,OSError) as exc:\n"
             "    notify(win, '保存失败：%s' % exc, title='保存')", 1),
            ("try:\n    work()\nexcept Exception as e:\n    notify(win, f'失败：{e}')", 1),
            ("try:\n    work()\nexcept Exception as e:\n    log(str(e))\n    notify(win, '失败')", 0),
            ("try:\n    work()\nexcept Exception as e:\n"
             "    notify(win, error_codes.user_text(e))", 0),
            ("try:\n    work()\nexcept Exception as exc:\n"
             "    notify(win, '失败：%s' % error_codes.user_text(exc))", 0),
            ("try:\n    work()\nexcept Exception:\n    notify(win, str(e))", 0),
            ("def show(text):\n    notify(win, str(text))", 0),
        )
        for source, expected in cases:
            with self.subTest(canary=source):
                self.assertEqual(len(_exception_text_leaks(ast.parse(source))), expected)

UI_MESSAGEBOX_IMPORT_ALLOWED = {'asset_detail.py', 'reference_wall.py', 'storyboard_files.py'}

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

def _imports_messagebox(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name == 'tkinter.messagebox' for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            if node.module == 'tkinter.messagebox':
                return True
            if node.module == 'tkinter' and any(alias.name == 'messagebox' for alias in node.names):
                return True
    return False


def _display_messageboxes(tree):
    return [node for node in ast.walk(tree) if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
            and node.func.value.id == 'messagebox'
            and node.func.attr in {'showerror', 'showwarning', 'showinfo'}]


def _notification_scan_files():
    """EC-3 守卫口径：ui/ 全部模块、desktop.py、app.py、agent/prompt_optimizer.py。"""
    return (*sorted((ROOT / 'ui').glob('*.py')),
            ROOT / 'desktop.py', ROOT / 'app.py', ROOT / 'agent' / 'prompt_optimizer.py')


def _is_notification_call(node):
    """守卫口径的提示调用：裸 ``notify(...)`` 与 ``*.notifier.error/warning(...)``。"""
    func = node.func
    if isinstance(func, ast.Name):
        return func.id == 'notify'
    return (isinstance(func, ast.Attribute) and func.attr in {'error', 'warning'}
            and isinstance(func.value, ast.Attribute) and func.value.attr == 'notifier')


def _is_user_text_call(node):
    """``error_codes.user_text(e)``／``user_text(e)``——统一出口包装，内部名字不算泄漏。"""
    func = node.func
    return ((isinstance(func, ast.Attribute) and func.attr == 'user_text')
            or (isinstance(func, ast.Name) and func.id == 'user_text'))


def _renders_exception(node, name):
    """参数子树里把 ``except`` 绑定的 ``name`` 原文搬进文字：``str(e)``／``'…' % e``／``f'…{e}…'``。"""
    stack = [node]
    while stack:
        child = stack.pop()
        if isinstance(child, ast.Call) and _is_user_text_call(child):
            continue
        if isinstance(child, ast.Name) and child.id == name:
            return True
        stack.extend(ast.iter_child_nodes(child))
    return False


def _exception_text_leaks(tree):
    """返回 ``(行号, 说明)``：提示调用的文字参数直接渲染所在 except 绑定的异常变量。"""
    leaks = []

    def visit(node, bound):
        if isinstance(node, ast.ExceptHandler):
            names = bound | ({node.name} if isinstance(node.name, str) else set())
            for child in node.body:
                visit(child, names)
            return
        if isinstance(node, ast.Call) and _is_notification_call(node) and bound:
            for arg in (*node.args, *(keyword.value for keyword in node.keywords)):
                hit = next((name for name in bound if _renders_exception(arg, name)), None)
                if hit is not None:
                    leaks.append((node.lineno, '通知调用直接渲染异常变量 ' + hit))
                    break
        for child in ast.iter_child_nodes(node):
            visit(child, bound)

    for node in tree.body:
        visit(node, frozenset())
    return leaks
