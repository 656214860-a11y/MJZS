"""R2056→R2933：项目名的可见位置随侧栏改版迁移。

R2056 时侧栏顶部浮层写当前项目名；R2933 删掉该浮层后，
`refresh_sidebar_title()` 对缺失的 `app_title` 直接返回（安全 no-op），
项目名改由 `mark_current_project()` 写进窗口标题「… · 当前项目：…」。

R2897：侧栏项目树改为分组筛选＋项目选择器后，「分组默认收起／展开保持」的
侧栏树契约随之移除；项目列表分组只保留在项目首页树上（非空组默认展开）。
"""
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk

from contract.app_metadata import APP_NAME
from desktop_project_pages import ProjectPagesMixin


class _Win:
    def __init__(self):
        self._title = ''

    def title(self, text=None):
        if text is None:
            return self._title
        self._title = text
        return None


class Host(ProjectPagesMixin):
    def __init__(self, root, projects, current=None):
        # R2933：真 Desktop 已无 app_title；假宿主同样不再提供。
        self.win = _Win()
        self.projects = type('P', (), {'info': {'projects': projects}})()
        self.root = Path(current) if current else None

    def project_row_text(self, p):
        return p['name']


class SidebarProjectTitleTests(unittest.TestCase):
    def setUp(self):
        self.tk = tk.Tk()
        self.tk.withdraw()
        self.addCleanup(self.tk.destroy)
        self.items = [{'name': '摄影侠', 'path': 'C:/p/a', 'status': 'making'},
                      {'name': '一百块流浪记很长的名字', 'path': 'C:/p/b', 'status': 'making'}]

    def test_project_trees_open_non_empty_groups(self):
        host = Host(self.tk, self.items)
        tree = ttk.Treeview(self.tk, show='tree')
        host.fill_projects(tree)
        self.assertTrue(tree.item('group:making', 'open'))
        self.assertFalse(tree.item('group:completed', 'open'))

    def test_refresh_sidebar_title_is_a_safe_noop_without_the_widget(self):
        """R2933：app_title 已删，refresh_sidebar_title 不得抛错。"""
        host = Host(self.tk, self.items)
        host.refresh_sidebar_title()
        host.root = Path('C:/p/a')
        host.refresh_sidebar_title()
        self.assertFalse(hasattr(host, 'app_title'))

    def test_window_title_carries_the_current_project_name(self):
        """项目名改由窗口标题承载：「漫剧助手 · V… · 当前项目：<目录名>」。"""
        host = Host(self.tk, self.items)
        host.root = Path('C:/p/摄影侠')
        host.mark_current_project()
        self.assertIn('当前项目：摄影侠', host.win.title())
        host.root = Path('C:/p/b')
        host.mark_current_project()
        self.assertIn('当前项目：b', host.win.title())
        host.root = None
        host.mark_current_project()
        self.assertNotIn('当前项目：', host.win.title())


if __name__ == '__main__':
    unittest.main()
