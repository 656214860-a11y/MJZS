# -*- coding: utf-8 -*-
"""REQ-S01-90 / DES-S01-90：内容区右缘图标列「项目文件」入口与右侧停靠面板。

覆盖契约：入口仅在「有项目＋非会员页/参考网站页」时显示；图标列是共享布局、
与画布同高且在列顶留白；面板默认隐藏，点图标钮向左停靠展开（主内容区收窄），
收起钮／再点／面板外按下／Esc／切页／切项目均收起；打开后文件列表照旧渐进
填表，面板宽度按最长文件名动态调整。
"""
import tempfile
import time
import unittest
from pathlib import Path

import tk_test_support

from desktop import Desktop, PAGE
from desktop_page_registry import PAGE_ACCOUNT, PAGE_SITES
from ui_tokens import SPACING
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
        """入口＝内容区右缘图标列顶的纯图标钮（RailIcon 样式＋图片＋无文字），列内下方留白。"""
        d = self.desktop
        button = d.files_button
        self.assertEqual(button.cget('style'), 'RailIcon.TButton')
        self.assertEqual(str(button.cget('compound')), 'image')
        self.assertTrue(button.cget('image'), '入口要用 project_files PNG 图标')
        self.assertEqual(button.cget('text'), '', '入口是纯图标钮，不显示文字')
        self.assertTrue(button.winfo_ismapped(), '有项目时入口可见')
        # R2998：入口在右侧图标列（canvas.master 内最右竖条）顶端，不再在标题行。
        rail = d.files_panel.rail
        self.assertEqual(str(button.winfo_parent()), str(rail))
        self.assertEqual(str(rail.winfo_parent()), str(d.canvas.master))
        # 独立成列：列贴内容区右缘、与画布同高；图标在列顶，下方留白给后续图标。
        area = d.canvas.master
        self.assertLessEqual(abs(rail.winfo_rootx() + rail.winfo_width()
                                 - (area.winfo_rootx() + area.winfo_width())), 2,
                             '图标列右缘贴内容区右缘')
        self.assertLessEqual(abs(rail.winfo_rooty() - area.winfo_rooty()), 2)
        self.assertLessEqual(abs(rail.winfo_height() - area.winfo_height()), 2,
                             '图标列与画布同高')
        self.assertLessEqual(button.winfo_rooty() - rail.winfo_rooty(),
                             SPACING['sm'] + 2, '图标钮在列顶')
        self.assertGreater(rail.winfo_height(), button.winfo_height() + SPACING['lg'],
                           '列内下方预留空间给后续图标')

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
        area = d.canvas.master
        width_before = d.canvas.winfo_width()
        d.files_button.invoke(); self.pump(.1)
        self.assertTrue(d.files_panel._open, '点击后打开面板')
        self.assertEqual(str(d.script_box.winfo_manager()), 'pack')
        # R2998：面板停靠在图标列左侧——面板右缘贴图标列左缘，图标列仍在最右；
        # 画布被收窄（面板向左展开）。
        rail = d.files_panel.rail
        self.assertLessEqual(abs(d.script_box.winfo_rootx() + d.script_box.winfo_width()
                                 - rail.winfo_rootx()), 2,
                             '面板右缘贴图标列左缘')
        self.assertLessEqual(abs(rail.winfo_rootx() + rail.winfo_width()
                                 - (area.winfo_rootx() + area.winfo_width())), 2,
                             '面板打开后图标列仍在最右')
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

    def test_icon_column_shared_across_work_pages(self):
        """图标列是共享布局：切到别的工作页入口仍在同一根列里，不重建。"""
        d = self.desktop
        rail = d.files_panel.rail
        for stage in ('script', 'storyboard', 'assets'):
            with self.subTest(stage=stage):
                d.show(PAGE[stage]); self.pump(.15)
                self.assertEqual(str(d.files_button.winfo_parent()), str(rail),
                                 stage + ' 页入口仍在同一图标列')
                self.assertTrue(d.files_button.winfo_ismapped(), stage + ' 页入口可见')
        d.show(PAGE['script']); self.pump(.1)

    def test_file_list_width_fits_longest_filename(self):
        """面板宽度按最长文件名动态调整：长文件名撑宽列表，宽度有上限。"""
        from tkinter import font as tkfont
        from desktop_files_panel import SCRIPT_CELL_OVERHEAD, SCRIPT_PANEL_MAX_WIDTH
        d = self.desktop
        d.show(PAGE['script']); self.pump(.2)
        long_name = '一个需要完整显示而不被截断的很长文件名称_项目设定.md'
        target = (project_stages.writing(self.project) / '测试提供方' / '测试模型'
                  / '创意_20261015' / '项目设定')
        (target / long_name).write_text('长名测试', encoding='utf8')
        try:
            d.files_panel.open_panel()
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and not any(
                    long_name in d.script_tree.item(i, 'values')[0]
                    for i in d.script_tree.get_children()):
                self.pump(.05)
            self.pump(.3)   # 等 finish() 里的 _fit_script_width 落定
            children = d.script_tree.get_children()
            self.assertTrue(children, '列表应有行')
            values = [str(d.script_tree.item(i, 'values')[0]) for i in children]
            font = tkfont.Font(root=d.win, font=('Microsoft YaHei UI', 9))
            needed = max(font.measure(v) for v in values) + SCRIPT_CELL_OVERHEAD
            cap = min(int(d.canvas.master.winfo_width() * .5), SCRIPT_PANEL_MAX_WIDTH)
            # 面板宽＝sizer＋盒内边距，应不小于「最长行宽＋留白」与上限的较小值。
            self.assertGreaterEqual(d.script_box.winfo_width(), min(needed, cap),
                                    '面板宽应跟上最长文件名（上限内）')
            self.assertGreater(d.script_box.winfo_width(), 200, '长文件名把面板撑宽')
        finally:
            (target / long_name).unlink(missing_ok=True)
            d.files_panel.collapse(); self.pump(.1)


if __name__ == '__main__':
    unittest.main()
