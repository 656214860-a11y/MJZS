# -*- coding: utf-8 -*-
"""REQ-S01-90 / DES-S01-90：主界面右上角「项目文件」图标与右侧停靠面板。

覆盖契约：入口仅在「有项目＋非会员页/参考网站页」时显示；面板默认隐藏，
点图标钮向左停靠展开（主内容区收窄），收起钮／再点／面板外按下／Esc／
切页／切项目均收起；打开后文件列表照旧渐进填表。
"""
import tempfile
import time
import unittest
from pathlib import Path

import tk_test_support

from desktop import Desktop, PAGE
from desktop_page_registry import PAGE_ACCOUNT, PAGE_SITES
import project_stages
import test_desktop_startup_perf as startup_fixtures
from tests.ui_edges_support import make_minimal_project


class FilesPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.win = tk_test_support.make_root()
        cls.temp = tempfile.TemporaryDirectory(prefix='r2962-files-panel-')
        app, cls.project = startup_fixtures.DesktopStartupPerfTests._startup_app(
            cls.temp.name, remembered=True)
        # 四类准备文件各一份，让打开面板后能立刻看到渐进填表的结果。
        for directory in ('项目设定', '项目大纲', '角色卡', '项目剧本'):
            target = (project_stages.writing(cls.project) / '测试提供方' / '测试模型'
                      / '创意_20261015' / directory)
            target.mkdir(parents=True)
            (target / (directory + '_样例.md')).write_text('测试正文', encoding='utf8')
        cls.desktop = Desktop(cls.win, root=app)
        cls.pump(2)

    @classmethod
    def pump(cls, seconds=.2):
        tk_test_support.pump(cls.win, seconds, idle_first=False)

    @classmethod
    def tearDownClass(cls):
        cls.desktop.cancel_timers()
        cls.win.destroy()
        cls.temp.cleanup()

    def setUp(self):
        d = self.desktop
        d.files_panel.collapse()
        if getattr(d, 'page_index', None) != PAGE['script']:
            d.show(PAGE['script'])
        self.pump(.2)

    def test_entry_is_icon_only_rail_button(self):
        """入口＝标题行右侧纯图标钮（RailIcon 样式＋图片＋无文字），与项目目录图标同套。"""
        d = self.desktop
        button = d.files_button
        self.assertEqual(button.cget('style'), 'RailIcon.TButton')
        self.assertEqual(str(button.cget('compound')), 'image')
        self.assertTrue(button.cget('image'), '入口要用 project_files PNG 图标')
        self.assertEqual(button.cget('text'), '', '入口是纯图标钮，不显示文字')
        self.assertTrue(button.winfo_ismapped(), '有项目时入口可见')
        # 与左侧项目图标同一水平带：入口在标题行（body 顶部）里。
        self.assertEqual(str(button.winfo_parent()), str(d.title_row))

    def test_entry_visibility_follows_project_and_page(self):
        """有项目才显示；会员页与参考网站页隐藏，回到生产页恢复。"""
        d = self.desktop
        d.show(PAGE['script']); self.pump(.1)
        self.assertEqual(str(d.files_button.winfo_manager()), 'pack', '生产页显示入口')
        d.show(PAGE_ACCOUNT); self.pump(.1)
        self.assertNotEqual(str(d.files_button.winfo_manager()), 'pack', '会员页隐藏入口')
        self.assertFalse(d.files_panel._open, '切到会员页面板收起')
        d.show(PAGE_SITES); self.pump(.1)
        self.assertNotEqual(str(d.files_button.winfo_manager()), 'pack', '参考网站页隐藏入口')
        d.show(PAGE['script']); self.pump(.1)
        self.assertEqual(str(d.files_button.winfo_manager()), 'pack', '回到生产页恢复入口')
        # 无项目（首页路由）同样隐藏；恢复后重建剧本页，避免首页内容留到后续用例。
        root = d.root
        try:
            d.root = None
            d.show(PAGE['script']); self.pump(.1)
            self.assertNotEqual(str(d.files_button.winfo_manager()), 'pack', '无项目时隐藏入口')
        finally:
            d.root = root
        d.show(PAGE['script']); self.pump(.1)
        self.assertEqual(str(d.files_button.winfo_manager()), 'pack', '恢复项目后入口回来')

    def test_panel_hidden_by_default_and_toggles_docked_right(self):
        """默认隐藏；点图标钮后面板停靠右侧、画布收窄，再点收起。"""
        d = self.desktop
        d.show(PAGE['script']); self.pump(.2)
        self.assertFalse(d.files_panel._open, '默认隐藏文件列表')
        self.assertNotEqual(str(d.script_box.winfo_manager()), 'pack')
        # R3060：画布列与停靠列同在 panel_area 内；面板右缘贴停靠列（＝内容区）右缘。
        area = d.panel_area
        width_before = d.canvas.winfo_width()
        d.files_button.invoke(); self.pump(.1)
        self.assertTrue(d.files_panel._open, '点击后打开面板')
        self.assertEqual(str(d.script_box.winfo_manager()), 'pack')
        # 右侧停靠：面板右缘贴内容区右缘，画布被收窄（面板向左展开）。
        self.assertLessEqual(abs(d.script_box.winfo_rootx() + d.script_box.winfo_width()
                                 - (area.winfo_rootx() + area.winfo_width())), 2)
        self.assertLess(d.canvas.winfo_width(), width_before, '打开面板主内容区收窄')
        d.files_button.invoke(); self.pump(.1)
        self.assertFalse(d.files_panel._open, '再点图标钮收起')
        self.assertNotEqual(str(d.script_box.winfo_manager()), 'pack')
        self.assertGreaterEqual(d.canvas.winfo_width(), width_before - 2, '收起后画布恢复')

    def test_collapse_button_outside_press_and_escape(self):
        """收起钮、面板外左键、Esc 三条关闭路径；面板内按下不收起。"""
        d = self.desktop
        d.show(PAGE['script']); self.pump(.2)
        d.files_panel.open_panel(); self.pump(.1)
        self.assertTrue(d.files_panel._open)
        d.script_tree.event_generate('<Button-1>', x=5, y=5)
        self.pump(.05)
        self.assertTrue(d.files_panel._open, '面板内按下不收起')
        d.script_toggle.invoke(); self.pump(.05)
        self.assertFalse(d.files_panel._open, '面板收起钮收起')
        d.files_panel.open_panel(); self.pump(.1)
        d.canvas.event_generate('<Button-1>', x=20, y=20); d.win.update()
        self.pump(.05)
        self.assertFalse(d.files_panel._open, '面板外按下左键收起')
        d.files_panel.open_panel(); self.pump(.1)
        d.win.event_generate('<Escape>'); d.win.update()
        self.pump(.2)
        self.assertFalse(d.files_panel._open, 'Esc 收起')

    def test_page_and_project_switch_reset_panel(self):
        """切页自动收起；项目根变化收起并允许下次打开重扫。"""
        d = self.desktop
        d.show(PAGE['script']); self.pump(.2)
        d.files_panel.open_panel(); self.pump(.1)
        self.assertTrue(d.files_panel._open)
        d.show(PAGE['storyboard']); self.pump(.2)
        self.assertFalse(d.files_panel._open, '切页自动收起')
        d.show(PAGE['script']); self.pump(.2)
        d.files_panel.open_panel(); self.pump(.1)
        root = d.root
        with tempfile.TemporaryDirectory() as td2:
            other = make_minimal_project(td2)
            d.root = other
            d.files_panel.project_changed(); self.pump(.05)
            self.assertFalse(d.files_panel._open, '项目根变化收起')
            self.assertEqual(d.files_panel._panel_root, other)
        d.root = root
        d.files_panel.project_changed(); self.pump(.05)
        self.assertEqual(d.files_panel._panel_root, root)

    def test_open_panel_lists_project_files(self):
        """打开面板后四类准备文件经渐进批次进入同一条列表。"""
        d = self.desktop
        d.show(PAGE['script']); self.pump(.2)
        d.files_panel.open_panel()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and len(d.script_tree.get_children()) < 4:
            self.pump(.05)
        self.assertGreaterEqual(len(d.script_tree.get_children()), 4, '四类文件都进列表')
        self.assertTrue(d.script_box.winfo_ismapped())
        self.assertEqual(str(d.script_title.cget('text')), '项目文件')
        names = [d.script_tree.item(item, 'values')[0] for item in d.script_tree.get_children()]
        for expected in ('项目设定_样例.md', '项目大纲_样例.md', '角色卡_样例.md', '项目剧本_样例.md'):
            self.assertTrue(any(expected in name for name in names), expected + ' 应出现在列表')


if __name__ == '__main__':
    unittest.main()
