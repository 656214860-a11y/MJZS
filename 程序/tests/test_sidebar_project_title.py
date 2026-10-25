"""R2056：侧栏顶部写当前项目名；项目分组默认收起，用户展开后刷新不再收回。"""
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk

from app_metadata import APP_NAME
from desktop_project_pages import ProjectPagesMixin
from ui_tokens import DESKTOP_LAYOUT


class Host(ProjectPagesMixin):
    def __init__(self, root, projects, current=None):
        self.list = ttk.Treeview(root, show='tree')
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

    def test_groups_collapsed_by_default_and_user_choice_survives_refresh(self):
        host = Host(self.tk, self.items)
        host.fill_projects(host.list)
        self.assertFalse(host.list.item('group:making', 'open'))
        host.list.item('group:making', open=True)
        host.fill_projects(host.list)
        self.assertTrue(host.list.item('group:making', 'open'))
        self.assertFalse(host.list.item('group:completed', 'open'))

    def test_other_trees_keep_opening_non_empty_groups(self):
        host = Host(self.tk, self.items)
        other = ttk.Treeview(self.tk, show='tree')
        host.fill_projects(other)
        self.assertTrue(other.item('group:making', 'open'))

    def test_title_follows_current_project_and_falls_back_to_app_name(self):
        host = Host(self.tk, self.items)
        host.fill_projects(host.list)
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
