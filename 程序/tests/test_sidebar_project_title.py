"""R2056：侧栏顶部写当前项目名。

R2897：侧栏项目树改为分组筛选＋项目选择器后，「分组默认收起／展开保持」的
侧栏树契约随之移除；项目列表分组只保留在项目首页树上（非空组默认展开）。
"""
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk

from app_metadata import APP_NAME
from desktop_project_pages import ProjectPagesMixin
from ui_tokens import DESKTOP_LAYOUT


class Host(ProjectPagesMixin):
    def __init__(self, root, projects, current=None):
        self.app_title = ttk.Label(root, text=APP_NAME)
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

    def test_title_follows_current_project_and_falls_back_to_app_name(self):
        host = Host(self.tk, self.items)
        host.refresh_sidebar_title()
        self.assertEqual(host.app_title.cget('text'), APP_NAME)
        host.root = Path('C:/p/a')
        host.refresh_sidebar_title()
        self.assertEqual(host.app_title.cget('text'), '摄影侠')
        host.root = Path('C:/p/b')
        host.refresh_sidebar_title()
        text = host.app_title.cget('text')
        self.assertEqual(len(text), DESKTOP_LAYOUT['sidebar_title_chars'])
        self.assertTrue(text.endswith('…'))
        host.root = None
        host.refresh_sidebar_title()
        self.assertEqual(host.app_title.cget('text'), APP_NAME)


if __name__ == '__main__':
    unittest.main()
