# -*- coding: utf-8 -*-
"""REQ-S01-90 / DES-S01-90：内容区右缘图标列「项目文件」入口与右侧停靠面板。

覆盖契约：入口仅在「有项目＋非会员页/参考网站页」时显示；图标列是共享布局、
与画布同高且在列顶留白；面板默认隐藏，点图标钮向左停靠展开（主内容区收窄），
收起钮／再点／面板外按下／Esc／切页／切项目均收起；打开后文件列表照旧渐进
填表，面板宽度按最长文件名动态调整。
"""
import tempfile
import time
import types
import unittest
from pathlib import Path

import tk_test_support

from desktop import Desktop, PAGE
from desktop_page_registry import PAGE_ACCOUNT, PAGE_SITES
from ui_tokens import SPACING
from contract import project_stages
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
        d.files_panel._user_panel_width = None
        d.files_panel._resize_start = None
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
        # R2998：入口在右侧图标列顶端，不再在标题行；R3060 起列挂 panel_area——
        # 面板停靠列的父级，打开时图标恒为内容区最右竖条。
        rail = d.files_panel.rail
        self.assertEqual(str(button.winfo_parent()), str(rail))
        self.assertEqual(str(rail.winfo_parent()), str(d.panel_area))
        # 独立成列：列贴内容区右缘、与画布同高；图标在列顶，下方留白给后续图标。
        area = d.panel_area
        self.assertLessEqual(abs(rail.winfo_rootx() + rail.winfo_width()
                                 - (area.winfo_rootx() + area.winfo_width())), 2,
                             '图标列右缘贴内容区右缘')
        self.assertLessEqual(abs(rail.winfo_rooty() - area.winfo_rooty()), 2)
        self.assertLessEqual(abs(rail.winfo_height() - area.winfo_height()), 2,
                             '图标列与画布同高')
        script = d.nav[PAGE['script']]
        row_center = script.winfo_rooty() + d.sidebar_canvas.canvasy(0) + script.winfo_height() // 2
        self.assertLessEqual(abs(button.winfo_rooty() + button.winfo_height() // 2 - row_center), 1)
        ordered = d.sidebar.pack_slaves()
        self.assertEqual(ordered.index(d.account_button), ordered.index(d.settings_rail_button) + 1)
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
        # R3060：画布列与停靠列同在 panel_area 内；面板右缘贴停靠列（＝内容区）右缘。
        area = d.panel_area
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
        """右箭头收起钮已删除；再点项目文件图标、面板外左键、Esc 三条关闭路径有效，面板内按下不收起。"""
        d = self.desktop
        self.assertFalse(hasattr(d, 'script_toggle'), '右侧右箭头按钮已删除')
        self.assertFalse(hasattr(d.files_panel, 'script_toggle'), '面板内右箭头按钮已删除')
        d.show(PAGE['script']); self.pump(.2)
        d.files_panel.open_panel(); self.pump(.1)
        self.assertTrue(d.files_panel._open)
        d.script_tree.event_generate('<Button-1>', x=5, y=5)
        self.pump(.05)
        self.assertTrue(d.files_panel._open, '面板内按下不收起')
        d.files_button.invoke(); self.pump(.05)
        self.assertFalse(d.files_panel._open, '再点项目文件图标收起')
        d.files_panel.open_panel(); self.pump(.1)
        d.canvas.event_generate('<Button-1>', x=20, y=20); d.win.update()
        self.pump(.05)
        self.assertFalse(d.files_panel._open, '面板外按下左键收起')
        d.files_panel.open_panel(); self.pump(.2)
        d.win.focus_force()
        d.win.update_idletasks()
        d.win.event_generate('<Escape>', when='now')
        d.win.update()
        self.pump(.5)
        self.assertFalse(d.files_panel._open, 'Esc 收起')

    def test_import_icon_sits_below_project_files_icon_in_rail(self):
        """导入文件图标位于最右图标列「项目文件」图标正下方，且随项目与页面显隐同步。"""
        d = self.desktop
        panel = d.files_panel
        d.show(PAGE['script']); self.pump(.15)
        self.assertEqual(str(panel.import_button.winfo_parent()), str(panel.rail))
        self.assertTrue(panel.import_button.winfo_ismapped(), '有项目时导入图标可见')
        self.assertGreater(panel.import_button.winfo_rooty(), panel.button.winfo_rooty(),
                           '导入图标应位于「项目文件」图标下方')
        self.assertLessEqual(abs(panel.import_button.winfo_rootx() - panel.button.winfo_rootx()), 2,
                             '两个图标在同一垂直图标列对齐')
        d.show(PAGE_ACCOUNT); self.pump(.1)
        self.assertNotEqual(str(panel.import_button.winfo_manager()), 'pack', '会员页隐藏导入图标')
        d.show(PAGE['script']); self.pump(.1)
        self.assertEqual(str(panel.import_button.winfo_manager()), 'pack', '切回生产页恢复导入图标')

    def test_single_row_search_group_card_header_sort_and_kind_override(self):
        """半宽搜索框与分组同行、六列顺序、可排序表头、阶段三角图标、二级目录卡、改类型与自动刷新。"""
        from infra import file_index
        d = self.desktop
        panel = d.files_panel
        d.show(PAGE['script']); self.pump(.2)
        panel.open_panel()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and len(self.file_items()) < 4:
            self.pump(.05)
        # 1. 已移除旧控件：无刷新按钮、全部类型框、全部状态框、排序框、右箭头按钮
        for removed in ('index_refresh_button', 'kind_box', 'status_box', 'sort_box', 'script_toggle'):
            self.assertFalse(hasattr(panel, removed), removed + ' 应已删除')
        # 2. 搜索框与分组按钮同行，搜索框占筛选条约一半宽度，默认显示「搜索文件」占位提示
        self.assertEqual(panel.keyword_entry._placeholder, '搜索文件')
        self.assertEqual(panel.keyword_var.get(), '')
        self.assertLessEqual(abs(panel.keyword_entry.winfo_rooty() - panel.group_button.winfo_rooty()), 8,
                             '搜索框与分组下拉应在同一行')
        bar_w = panel.filter_bar.winfo_width()
        entry_w = panel.keyword_entry.winfo_width()
        self.assertGreater(entry_w, 0)
        self.assertLessEqual(entry_w, bar_w * 0.62, '搜索框默认约占停靠面板一半宽度')
        # 3. 6 列顺序与时间列格式（YYYY-MM-DD，不含时分秒）
        tree = panel.script_tree
        self.assertEqual(tuple(tree['columns']), ('name', 'status', 'kind', 'mtime', 'size', 'meta'))
        first_item = self.file_items()[0]
        vals = tree.item(first_item, 'values')
        self.assertEqual(len(vals), 6)
        self.assertRegex(vals[3], r'^\d{4}-\d{2}-\d{2}$', '时间列应省略时分秒')
        # 4. 表头排序：状态/类型/时间/大小可排序，文件名与时长／分辨率不可排序
        for sortable in ('status', 'kind', 'mtime', 'size'):
            self.assertTrue(str(tree.heading(sortable, 'command')), sortable + ' 应可点击排序')
        for unsortable in ('name', 'meta'):
            self.assertEqual(str(tree.heading(unsortable, 'command')), '', unsortable + ' 不应有排序命令')
        panel.sort_by_column('size')
        self.assertEqual(panel.sort_column, 'size')
        self.assertTrue(panel.sort_desc)
        panel.sort_by_column('size')
        self.assertFalse(panel.sort_desc)
        panel.sort_by_column('name')
        self.assertEqual(panel.sort_column, 'size', '点击文件名不改变排序')
        panel.sort_by_column('meta')
        self.assertEqual(panel.sort_column, 'size', '点击时长／分辨率不改变排序')
        # 5. 默认按类型分组，设定/大纲/角色卡归为「参考」，自然剧本归为「剧本」
        top_groups = tuple(tree.get_children())
        self.assertIn('kind-group:参考', top_groups)
        self.assertIn('kind-group:剧本', top_groups)
        # 6. 分组二级目录卡同步列出类型/阶段/状态/日期条目，选「阶段」时单阶段也显示三角图标
        panel.group_menu.show()
        self.pump(.1)
        self.assertTrue(panel.group_menu.is_open())
        stage_items = panel.group_menu.secondary_items('阶段')
        self.assertTrue(any(label == '全部阶段' for label, _v, _c in stage_items))
        status_items = panel.group_menu.secondary_items('状态')
        self.assertEqual([label for label, _v, _c in status_items], ['全部状态', '定稿', '草稿', '归档'])
        panel.group_menu.close()
        panel.select_group_option('阶段', 'script')
        self.pump(.3)
        self.assertIn('tree', str(tree.cget('show')), '单阶段分组也应显示可折叠三角图标')
        self.assertEqual(tree.get_children(), ('stage-group:script',))
        # 7. 手动更改文件类型持久化并生效
        panel.select_group_option('类型', None)
        self.pump(.3)
        target_item = next(i for i in self.file_items() if '角色卡_样例.md' in i)
        panel.change_file_kind(target_item, '设定')
        self.pump(.3)
        self.assertEqual(panel.script_tree.set(target_item, 'kind'), '设定')
        self.assertIn('kind-group:设定', panel.script_tree.get_children())
        panel.change_file_kind(target_item, '')
        self.pump(.3)
        self.assertEqual(panel.script_tree.set(target_item, 'kind'), '参考')
        # 8. 自动刷新：file_index.update 变更后无需手动刷新按钮即可自动同步面板
        auto_file = project_stages.writing(self.project) / '项目大纲' / '自动刷新验证.md'
        auto_file.parent.mkdir(parents=True, exist_ok=True)
        auto_file.write_text('# 自动刷新', encoding='utf8')
        try:
            file_index.update(self.project, [auto_file])
            deadline = time.monotonic() + 3
            rel = auto_file.relative_to(self.project).as_posix()
            while time.monotonic() < deadline and rel not in self.file_items():
                self.pump(.05)
            self.assertIn(rel, self.file_items(), '索引变更应自动刷新右侧面板')
        finally:
            auto_file.unlink(missing_ok=True)
            file_index.update(self.project, [auto_file], removed=True)
            panel.collapse(); self.pump(.1)

    def test_page_and_project_switch_reset_panel(self):
        """REQ-S01-94（R3191，D11）：切工作页保持打开；项目根变化收起并允许下次打开重扫。"""
        d = self.desktop
        d.show(PAGE['script']); self.pump(.2)
        d.files_panel.open_panel(); self.pump(.1)
        self.assertTrue(d.files_panel._open)
        d.show(PAGE['storyboard']); self.pump(.2)
        self.assertTrue(d.files_panel._open, '切工作页保持面板打开（REQ-S01-94）')
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

    def file_items(self):
        tree = self.desktop.script_tree
        def leaves(parent=''):
            for item in tree.get_children(parent):
                children = tree.get_children(item)
                if children:
                    yield from leaves(item)
                elif not str(item).startswith('stage-group:'):
                    yield item
        return list(leaves())

    def test_open_panel_lists_project_files(self):
        """打开面板后四类准备文件经渐进批次进入同一条列表。"""
        d = self.desktop
        d.show(PAGE['script']); self.pump(.2)
        d.files_panel.open_panel()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and len(self.file_items()) < 4:
            self.pump(.05)
        self.assertGreaterEqual(len(self.file_items()), 4, '分组视图中四类文件都进列表')
        self.assertTrue(d.script_box.winfo_ismapped())
        self.assertEqual(str(d.script_title.cget('text')), '项目文件 · 剧本准备')
        names = [d.script_tree.item(item, 'values')[0] for item in self.file_items()]
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

    def test_file_list_width_independent_of_longest_filename(self):
        d = self.desktop
        d.show(PAGE['script']); self.pump(.2)
        long_name = '一个需要完整显示而不被截断的很长文件名称_项目设定.md'
        target = (project_stages.writing(self.project) / '测试提供方' / '测试模型'
                  / '创意_20261015' / '项目设定')
        (target / long_name).write_text('长名测试', encoding='utf8')
        try:
            d.files_panel.open_panel()
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and long_name not in d.files_panel._full_labels.values():
                self.pump(.05)
            self.assertIn(long_name, d.files_panel._full_labels.values())
            wide_w = d.script_box.winfo_width()
            from infra.storage_maintenance import recycle_paths
            recycle_paths(d.root, [target / long_name], '删除项目剧本')
            d.files_panel.refresh_file_index()
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and any(
                    long_name in d.script_tree.item(i, 'values')[0]
                    for i in self.file_items()):
                self.pump(.05)
            self.pump(.5)   # 等 finish() 里的 _fit_script_width 与几何重排落定
            self.assertNotIn(long_name, [d.script_tree.item(i, 'values')[0]
                                         for i in self.file_items()])
            self.assertEqual(d.script_box.winfo_width(), wide_w)
        finally:
            (target / long_name).unlink(missing_ok=True)
            d.files_panel.collapse(); self.pump(.1)


class FilesPanelResizeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.win = tk_test_support.make_root()
        cls.temp = tempfile.TemporaryDirectory(prefix='r-ux-dock-resize-')
        app, cls.project = startup_fixtures.DesktopStartupPerfTests._startup_app(
            cls.temp.name, remembered=True)
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
        d.files_panel._user_panel_width = None
        d.files_panel._resize_start = None
        if getattr(d, 'page_index', None) != PAGE['script']:
            d.show(PAGE['script'])
        self.pump(.2)

    def _open_panel(self):
        d = self.desktop
        d.files_panel.open_panel()
        self.pump(.3)

    def test_drag_left_widens_panel(self):
        d = self.desktop
        d.show(PAGE['script']); self.pump(.2)
        self._open_panel()
        panel = d.files_panel
        sizer = panel.script_width_sizer
        before = int(sizer.cget('width'))
        start_x = 1000
        panel._start_resize(types.SimpleNamespace(x_root=start_x, widget=panel.resize_grip))
        panel._do_resize(types.SimpleNamespace(x_root=start_x - 120, widget=panel.resize_grip))
        after = int(sizer.cget('width'))
        self.assertEqual(after, before + 120)
        self.assertTrue(panel._open)
        panel._end_resize(types.SimpleNamespace(x_root=start_x - 120, widget=panel.resize_grip))
        panel.collapse(); self.pump(.1)

    def test_drag_clamps_to_limits(self):
        from desktop_files_panel import SCRIPT_LIST_MIN_WIDTH
        d = self.desktop
        d.show(PAGE['script']); self.pump(.2)
        self._open_panel()
        panel = d.files_panel
        sizer = panel.script_width_sizer
        # 向右拖过头 -> 最小宽
        panel._start_resize(types.SimpleNamespace(x_root=1000, widget=panel.resize_grip))
        panel._do_resize(types.SimpleNamespace(x_root=1000 + 100000, widget=panel.resize_grip))
        self.assertEqual(int(sizer.cget('width')), SCRIPT_LIST_MIN_WIDTH)
        # 向左拖过头 -> 手动上限
        panel._start_resize(types.SimpleNamespace(x_root=1000, widget=panel.resize_grip))
        cap = panel._manual_cap()
        panel._do_resize(types.SimpleNamespace(x_root=1000 - 100000, widget=panel.resize_grip))
        self.assertEqual(int(sizer.cget('width')), cap)
        panel._end_resize(types.SimpleNamespace(x_root=1000, widget=panel.resize_grip))
        panel.collapse(); self.pump(.1)

    def test_manual_width_persists(self):
        d = self.desktop
        d.show(PAGE['script']); self.pump(.2)
        self._open_panel()
        panel = d.files_panel
        sizer = panel.script_width_sizer
        panel._start_resize(types.SimpleNamespace(x_root=500, widget=panel.resize_grip))
        panel._do_resize(types.SimpleNamespace(x_root=450, widget=panel.resize_grip))
        manual = int(sizer.cget('width'))
        panel._end_resize(types.SimpleNamespace(x_root=450, widget=panel.resize_grip))
        recorded = panel._user_panel_width
        self.assertEqual(recorded, manual)
        # 再次 _fit_script_width
        panel._fit_script_width()
        self.assertEqual(panel._user_panel_width, recorded)
        # fill_script_list
        panel.fill_script_list()
        self.pump(.2)
        self.assertEqual(panel._user_panel_width, recorded)
        # collapse + open
        panel.collapse(); self.pump(.1)
        panel.open_panel(); self.pump(.3)
        self.assertEqual(panel._user_panel_width, recorded)
        panel.collapse(); self.pump(.1)

    def test_double_click_restores_auto(self):
        d = self.desktop
        d.show(PAGE['script']); self.pump(.2)
        self._open_panel()
        panel = d.files_panel
        sizer = panel.script_width_sizer
        # 自动宽度
        panel._user_panel_width = None
        panel._fit_script_width()
        self.pump(.2)
        auto = int(sizer.cget('width'))
        # 拖动
        panel._start_resize(types.SimpleNamespace(x_root=500, widget=panel.resize_grip))
        panel._do_resize(types.SimpleNamespace(x_root=400, widget=panel.resize_grip))
        panel._end_resize(types.SimpleNamespace(x_root=400, widget=panel.resize_grip))
        self.assertIsNotNone(panel._user_panel_width)
        # 双击恢复
        panel._restore_auto_width(types.SimpleNamespace(x_root=400, widget=panel.resize_grip))
        self.assertIsNone(panel._user_panel_width)
        self.pump(.2)
        self.assertEqual(int(sizer.cget('width')), auto)
        panel.collapse(); self.pump(.1)

    def test_outside_press_allows_grip(self):
        d = self.desktop
        d.show(PAGE['script']); self.pump(.2)
        self._open_panel()
        panel = d.files_panel
        event = types.SimpleNamespace(widget=panel.resize_grip)
        panel._outside_press(event)
        self.assertTrue(panel._open)
        panel.collapse(); self.pump(.1)

    def test_grouped_text_files_align_close_to_left_edge(self):
        """无缩略图分组视图下，#0 仅留展开箭头宽度，目录名与文件名紧贴左侧边界。"""
        from contract import stage_path_service
        from infra import file_index
        from ui.desktop_files_panel_index import TREE_DISCLOSURE_WIDTH
        d = self.desktop
        s2_dir = stage_path_service.write_dir(d.root, 'script_structure')
        s2_dir.mkdir(parents=True, exist_ok=True)
        extra = s2_dir / '左对齐验证结构稿.md'
        extra.write_text('# 结构稿\n', encoding='utf-8')
        try:
            file_index.rebuild(d.root)
            d.show(PAGE['script']); self.pump(.2)
            self._open_panel()
            panel = d.files_panel
            panel.show_stage(None)
            self.pump(.3)
            tree = panel.script_tree
            self.assertEqual(int(tree.column('#0', 'width')), TREE_DISCLOSURE_WIDTH)
            groups = tree.get_children()
            self.assertGreaterEqual(len(groups), 2)
            box = tree.bbox(groups[0], 'name')
            self.assertTrue(box, '分组行应已渲染可见')
            self.assertLessEqual(box[0], TREE_DISCLOSURE_WIDTH + 4,
                                 '分组目录名应紧贴左边界，不留过宽空白')
            panel.collapse(); self.pump(.1)
        finally:
            extra.unlink(missing_ok=True)
            file_index.rebuild(d.root)


class FilesPanelImportTests(unittest.TestCase):
    """REQ-S01-103：面板「导入文件」入口——本机文件复制进当前阶段写入目录并列进索引。

    无 Tk：面板用 ``__new__`` 替身＋注入的文件对话框／同名决策，只走临时目录；
    复制语义断言直接打 ``desktop_files_panel_filters.import_into_stage``。
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ux-fp-import-')
        base = Path(self.temp.name)
        self.root = base / '演示项目'
        self.root.mkdir()
        self.local = base / '本机素材'
        self.local.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def _write(self, folder, name, data=b'data'):
        path = Path(folder) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def _panel(self, *, stage='assets', page_index=4, chosen=(), decisions=(), library_view=False):
        """建无 Tk 面板替身：注入多选结果与「覆盖／保留两份／取消」决策序列。"""
        from ui.desktop_files_panel import ProjectFilesPanel
        state = {'chosen': tuple(str(p) for p in chosen), 'decisions': list(decisions),
                 'conflict_calls': [], 'refreshes': [], 'status': []}
        panel = ProjectFilesPanel.__new__(ProjectFilesPanel)
        panel.page = types.SimpleNamespace(
            root=self.root, page_index=page_index, win=None,
            status=types.SimpleNamespace(set=lambda text: state['status'].append(text)),
            file_dialog=types.SimpleNamespace(
                open_files=lambda **kw: state['chosen']),
            safe=lambda fn: fn())
        panel._open = True
        panel.stage_filter = stage
        panel.library_view = library_view
        panel._ask_import_conflict = lambda name: (
            state['conflict_calls'].append(name), state['decisions'].pop(0))[1]
        panel.fill_script_list = lambda: state['refreshes'].append('refresh')
        panel.show_stage = lambda value: state['refreshes'].append(('stage', value))
        return panel, state

    def _import(self, root=None):
        from ui.desktop_files_panel_filters import import_into_stage
        return import_into_stage

    def test_import_entry_copies_file_into_stage_write_dir(self):
        """入口存在并把本机文件复制进当前阶段写入目录，走面板刷新后进入索引列表。"""
        from contract.stage_path_service import write_dir
        from infra import file_index
        source = self._write(self.local, '角色参考.png', b'PNG-DATA')
        panel, state = self._panel(chosen=(source,))
        panel.import_files()        # 缺陷期：面板没有导入入口 → AttributeError
        target = write_dir(self.root, 'assets') / '角色参考.png'
        self.assertTrue(target.is_file(), '副本应落在 05资产管理 写入目录')
        self.assertEqual(target.read_bytes(), b'PNG-DATA')
        self.assertTrue(source.is_file())
        self.assertEqual(source.read_bytes(), b'PNG-DATA', '原文件不动')
        self.assertIn('refresh', state['refreshes'], '复制完成后走面板现有索引刷新')
        relative = target.relative_to(self.root).as_posix()
        rows = {row.path for row in file_index.rows(self.root)}
        self.assertIn(relative, rows, '导入文件应进入项目索引并出现在面板列表')
        self.assertFalse(file_index.is_functional(relative), '导入文件应是面板可见类型')

    def test_import_multi_select_copies_each(self):
        """文件对话框多选：几份文件逐份复制进同一阶段目录。"""
        first = self._write(self.local, '甲.png', b'A')
        second = self._write(self.local, '乙.png', b'B')
        result = self._import()(self.root, 'assets', [first, second])
        stage_dir = self.root / '05资产管理'
        self.assertEqual((stage_dir / '甲.png').read_bytes(), b'A')
        self.assertEqual((stage_dir / '乙.png').read_bytes(), b'B')
        self.assertEqual(len(result['imported']), 2)
        self.assertEqual(first.read_bytes(), b'A', '原文件不动')
        self.assertEqual(second.read_bytes(), b'B', '原文件不动')

    def test_import_same_name_overwrite_replaces(self):
        """同名选「覆盖」：目标被替换、原件不动。"""
        target = self._write(self.root / '05资产管理', '旧图.png', b'OLD')
        source = self._write(self.local, '旧图.png', b'NEW')
        asked = []
        result = self._import()(self.root, 'assets', [source],
                                conflict=lambda name: (asked.append(name), 'overwrite')[1])
        self.assertEqual(asked, ['旧图.png'], '同名必须先询问')
        self.assertEqual(target.read_bytes(), b'NEW')
        self.assertEqual(len(result['imported']), 1)
        self.assertEqual(source.read_bytes(), b'NEW', '原文件不动')

    def test_import_same_name_keep_both_renames(self):
        """同名选「保留两份」：旧文件保留，新文件按 (N) 递增命名。"""
        target = self._write(self.root / '05资产管理', '旧图.png', b'OLD')
        source = self._write(self.local, '旧图.png', b'NEW')
        result = self._import()(self.root, 'assets', [source],
                                conflict=lambda name: 'rename')
        self.assertEqual(target.read_bytes(), b'OLD', '旧文件不被覆盖')
        renamed = self.root / '05资产管理' / '旧图(2).png'
        self.assertTrue(renamed.is_file(), '保留两份时应自动改名导入')
        self.assertEqual(renamed.read_bytes(), b'NEW')
        self.assertEqual(len(result['imported']), 1)

    def test_import_same_name_cancel_no_op(self):
        """同名选「取消」：不写新文件，目标与原文件都不动。"""
        target = self._write(self.root / '05资产管理', '旧图.png', b'OLD')
        source = self._write(self.local, '旧图.png', b'NEW')
        result = self._import()(self.root, 'assets', [source],
                                conflict=lambda name: 'cancel')
        self.assertEqual(target.read_bytes(), b'OLD')
        self.assertFalse((self.root / '05资产管理' / '旧图(2).png').exists())
        self.assertEqual(source.read_bytes(), b'NEW', '原文件不动')
        self.assertFalse(result['imported'])
        self.assertEqual(result['skipped'], ['旧图.png'])

    def test_import_never_overwrites_without_asking(self):
        """无决策回调等同「取消」：同名绝不静默覆盖。"""
        target = self._write(self.root / '05资产管理', '旧图.png', b'OLD')
        source = self._write(self.local, '旧图.png', b'NEW')
        result = self._import()(self.root, 'assets', [source])
        self.assertEqual(target.read_bytes(), b'OLD', '不询问时绝不覆盖')
        self.assertEqual(result['skipped'], ['旧图.png'])

    def test_import_rejects_unlisted_type(self):
        """阶段类型白名单之外的文件被点名拒绝，不复制。"""
        source = self._write(self.local, '破解工具.exe', b'EXE')
        result = self._import()(self.root, 'assets', [source])
        self.assertFalse(result['imported'])
        self.assertEqual(len(result['rejected']), 1)
        self.assertIn('破解工具.exe', result['rejected'][0][0])
        self.assertTrue(result['rejected'][0][1], '拒绝要给出原因文案')
        self.assertFalse((self.root / '05资产管理' / '破解工具.exe').exists())
        self.assertTrue(source.is_file(), '原文件不动')

    def test_import_half_write_leaves_no_partial_file(self):
        """复制中途失败：不留半文件、不残留临时文件，旧目标不被改动。"""
        source = self._write(self.local, '半份.png', b'FULL')
        existing = self._write(self.root / '05资产管理', '半份.png', b'OLD')

        def flaky(target, _source, overwrite):
            stray = target.with_name(target.name + '.ab12cd.tmp')
            stray.write_bytes(b'half')
            raise OSError('模拟写入中断')
        result = self._import()(self.root, 'assets', [source],
                                conflict=lambda name: 'overwrite', copier=flaky)
        self.assertFalse(result['imported'])
        self.assertEqual(len(result['rejected']), 1)
        stage_dir = self.root / '05资产管理'
        self.assertEqual([p.name for p in stage_dir.iterdir() if p.name != '半份.png'], [],
                         '失败不留半个文件或临时残留')
        self.assertEqual(existing.read_bytes(), b'OLD', '覆盖失败时旧文件不受影响')

    def test_import_target_never_escapes_project(self):
        """目标名剥离目录段：「..」「盘符」路径段进不了项目外的位置。"""
        from ui.desktop_files_panel_filters import _import_target
        from contract.stage_path_service import write_dir
        stage_dir = write_dir(self.root, 'assets')
        for raw in ('sub\\..\\图.png', 'C:\\别的盘\\图.png', '..\\..\\图.png'):
            _dir, target = _import_target(self.root, 'assets', raw)
            self.assertEqual(target.parent, stage_dir)
            self.assertTrue(target.resolve().is_relative_to(self.root.resolve()),
                            '目标路径不越出项目目录：' + raw)
        for bad in ('..', '', 'CON.png', 'x<.png'):
            with self.assertRaises(ValueError, msg=bad):
                _import_target(self.root, 'assets', bad)

    def test_import_files_dialog_uses_stage_suffixes(self):
        """入口多选对话框的 filetypes 按当前阶段允许后缀给出。"""
        seen = {}
        panel, _state = self._panel(stage='audio', page_index=10)
        panel.page.file_dialog = types.SimpleNamespace(
            open_files=lambda **kw: seen.update(kw) or ())
        panel.import_files()
        self.assertIn('filetypes', seen)
        patterns = seen['filetypes'][0][1]
        self.assertIn('*.mp3', patterns)
        self.assertIn('*.srt', patterns)
        self.assertNotIn('*.png', patterns, '配音与字幕阶段不收图片')


if __name__ == '__main__':
    unittest.main()
