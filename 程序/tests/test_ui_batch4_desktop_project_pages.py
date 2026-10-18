"""UI 批次 4：项目选择窗与项目首页的动作区在小窗口下不裁字。

真实 Tk 根窗口按 640×480、500×380、1280×800 三档量几何：每个动作按钮
``winfo_width() >= winfo_reqwidth()``、已经映射，主操作完整可点且不越过窗口底边。
项目根一律是 ``tempfile`` 里的两个空目录，不打开也不读取任何真实项目。
"""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path
from tkinter import ttk

import tkinter as tk

import desktop_project_pages
from desktop import Desktop
from desktop_project_pages import ProjectPagesMixin
from responsive_ui import FlowBar

PLATFORM_TKINTER = '当前环境无可用 Tkinter'
SIZES = ((640, 480), (500, 380), (1280, 800))
ENTER_DIALOG = '进入项目 →'
ENTER_HOME = '进入选中的项目 →'
HOME_ACTIONS = [ENTER_HOME, '＋ 创建新项目', '创建练习项目：雨夜修伞',
                '当前项目存储盘点（只读）', '恢复回收站内容…', '重建项目索引',
                '导出诊断包…', '运行状况…']
DIALOG_ACTIONS = [ENTER_DIALOG, '+ 新建项目', '恢复回收站内容…', '重新查找项目', '删除选中项目']


def _descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from _descendants(child)


class _Status:
    def __init__(self):
        self.value = ''

    def set(self, value):
        self.value = value

    def get(self):
        return self.value


class _Projects:
    def __init__(self, paths):
        self.info = {
            'active': str(paths[0]) if paths else None,
            'projects': [{'name': Path(path).name, 'path': str(path),
                          'created_at': index, 'status': 'making'}
                         for index, path in enumerate(paths)],
        }
        self.legacy_migration_pending = False


def _fill_projects(tree, projects):
    tree.delete(*tree.get_children())
    for item in projects.info['projects']:
        tree.insert('', 'end', iid=item['path'], text=item['name'])


class _HomeHarness(ProjectPagesMixin):
    """只提供项目首页需要的桌面属性；按钮工厂仍走生产的 Desktop.button。"""

    def __init__(self, root, projects):
        self.win = root
        self.projects = projects
        self.content = ttk.Frame(root)
        self.content.pack(fill='both', expand=True)
        self.status = _Status()
        self._project_home_tree = None
        self.pet = None
        # 本用例只量动作区几何，不触发任何项目动作。
        self.new = lambda: None
        self.create_practice_project = lambda: None
        self.show_project_storage = lambda: None
        self.open_recycle_recovery = lambda: None
        self.rebuild_project_index = lambda: None
        self.export_diagnostics_package = lambda: None

    def note(self, value):
        self.status.set(value)

    def fill_projects(self, tree):
        _fill_projects(tree, self.projects)

    def button(self, parent, text, fn):
        return Desktop.button(self, parent, text, fn)

    def safe(self, fn):
        return fn()


class _PickerHarness(ProjectPagesMixin):
    """只提供项目选择窗构建阶段用到的属性；不启动真实项目。"""

    def __init__(self, root, projects):
        self.win = root
        self.projects = projects
        self.status = _Status()
        self._startup_project_choice = False
        self._cleanup_project_path = None

    def fill_projects(self, tree):
        _fill_projects(tree, self.projects)

    def daily_project_choice(self):
        return None

    def safe(self, fn):
        return fn()


def _action_buttons(parent):
    bars = [widget for widget in _descendants(parent) if isinstance(widget, FlowBar)]
    if len(bars) != 1:
        raise AssertionError('动作区应由唯一的 FlowBar 承载，实际 %d 个' % len(bars))
    return [widget for widget in bars[0].winfo_children() if isinstance(widget, ttk.Button)]


class ProjectActionLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            probe = tk.Tk()
            probe.destroy()
            cls.tk = tk
        except Exception:
            cls.tk = None

    def _window(self, width, height):
        root = self.tk.Tk()
        root.geometry('%dx%d+40+40' % (width, height))
        root.update_idletasks()
        root.update()
        return root

    def assert_actions_fit(self, window, buttons, expected):
        window.update_idletasks()
        window.update()
        self.assertEqual([button.cget('text') for button in buttons], expected)
        for button in buttons:
            text = button.cget('text')
            self.assertTrue(button.winfo_ismapped(), text + ' 未映射到窗口')
            self.assertGreaterEqual(button.winfo_width(), button.winfo_reqwidth(),
                                    '%s 被压到 %d < 请求 %d，文字会裁切'
                                    % (text, button.winfo_width(), button.winfo_reqwidth()))
            self.assertGreaterEqual(button.winfo_rooty(), window.winfo_rooty(),
                                    text + ' 越过窗口顶边，不在可视区')
            self.assertLessEqual(button.winfo_rooty() + button.winfo_height(),
                                 window.winfo_rooty() + window.winfo_height() + 1,
                                 text + ' 越过窗口底边，不在可视区')

    def test_project_home_actions_fit_at_every_size(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as temp:
            paths = []
            for name in ('临时项目甲', '临时项目乙'):
                path = Path(temp) / name
                path.mkdir()
                paths.append(path)
            for width, height in SIZES:
                with self.subTest(size=(width, height)):
                    root = self._window(width, height)
                    try:
                        harness = _HomeHarness(root, _Projects(paths))
                        ProjectPagesMixin.project_home(harness)
                        buttons = _action_buttons(harness.content)
                        self.assert_actions_fit(root, buttons, HOME_ACTIONS)
                        enter = next(item for item in buttons if item.cget('text') == ENTER_HOME)
                        self.assertTrue(enter.winfo_ismapped())
                        self.assertGreaterEqual(enter.winfo_width(), enter.winfo_reqwidth())
                        self.assertEqual(enter.cget('style'), 'Tokens.Primary.TButton',
                                         '项目首页的主操作必须使用主按钮样式')
                    finally:
                        root.destroy()

    def test_project_picker_actions_fit_at_every_size(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as temp:
            paths = []
            for name in ('临时项目甲', '临时项目乙'):
                path = Path(temp) / name
                path.mkdir()
                paths.append(path)
            for width, height in SIZES:
                with self.subTest(size=(width, height)):
                    root = self._window(width, height)
                    try:
                        harness = _PickerHarness(root, _Projects(paths))
                        ProjectPagesMixin._choose_project_impl(harness)
                        root.update_idletasks()
                        root.update()
                        popups = [widget for widget in root.winfo_children()
                                  if isinstance(widget, self.tk.Toplevel) and widget.winfo_exists()]
                        self.assertEqual(len(popups), 1, '项目选择窗应当已经建立')
                        popup = popups[0]
                        popup.grab_release()
                        popup.attributes('-alpha', 1.0)
                        popup.geometry('%dx%d+40+40' % (width, height))
                        popup.update_idletasks()
                        popup.update()
                        buttons = _action_buttons(popup)
                        self.assert_actions_fit(popup, buttons, DIALOG_ACTIONS)
                        enter = next(item for item in buttons if item.cget('text') == ENTER_DIALOG)
                        self.assertTrue(enter.winfo_ismapped())
                        self.assertGreaterEqual(enter.winfo_width(), enter.winfo_reqwidth())
                        self.assertEqual(enter.cget('style'), 'Tokens.Primary.TButton',
                                         '项目选择窗的主操作必须使用主按钮样式')
                    finally:
                        root.destroy()

    def test_heading_and_padding_use_tokens(self):
        source = Path(desktop_project_pages.__file__).read_text(encoding='utf-8')
        self.assertNotIn("('Microsoft YaHei UI',17", source,
                         '页标题必须使用 FONTS 令牌，不得手写 17pt')
        self.assertIsNone(re.search(r'pad[xy]=\d', source),
                          '动作区不得再写数字 padx/pady，必须取 SPACING 令牌')
        self.assertNotIn('modal=True', source,
                         '可恢复错误/项目恢复提示必须保持非模态（破坏性确认仍走 confirm）')


if __name__ == '__main__':
    unittest.main()
