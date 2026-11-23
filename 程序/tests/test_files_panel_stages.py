# -*- coding: utf-8 -*-
"""R3094（任务书 P1）：停靠面板右缘的阶段快捷图标列。

覆盖：图标列在面板右缘、按 ``pet_bus.STAGES`` 顺序垂直排列、每个都带 Tooltip 中文名；
点阶段图标按项目文件索引填表、首次索引后台扫描、当前阶段高亮、
``show_stage(None)`` 回到全项目分组视图（UX-C1：面板内不再放与入口重复的「全部文件」图标）；
换项目时阶段筛选复位。
"""
import tempfile
import time
import unittest
from pathlib import Path
import tkinter as tk
from tkinter import ttk

import tk_test_support
from contract import project_stages

from contract.pet_bus import STAGES, stage_name
from desktop import Desktop, PAGE
from ui.desktop_files_panel_filters import STAGE_FILTER_ROW_CATEGORY
import infra.file_index as file_index
import test_desktop_startup_perf as startup_fixtures


class StageRailTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.win = tk_test_support.make_root()
        cls.temp = tempfile.TemporaryDirectory(prefix='r3094-stage-rail-')
        import asset_thumbs
        cls.original_thumb_cache = asset_thumbs.CACHE_ROOT
        asset_thumbs.reset_worker()
        asset_thumbs.forget()
        asset_thumbs.CACHE_ROOT = Path(cls.temp.name) / '缩略图缓存'
        app, cls.project = startup_fixtures.DesktopStartupPerfTests._startup_app(
            cls.temp.name, remembered=True)
        target = project_stages.writing(cls.project) / '项目剧本'
        target.mkdir(parents=True, exist_ok=True)
        (target / '样例剧本.md').write_text('正文', encoding='utf8')
        asset_dir = project_stages.assets(cls.project) / 'assets'
        asset_dir.mkdir(parents=True, exist_ok=True)
        (asset_dir / 'CHAR_001.png').write_bytes(b'\x89PNG')
        cls.desktop = Desktop(cls.win, root=app)
        cls.pump(2)

    @classmethod
    def pump(cls, seconds=.2):
        tk_test_support.pump(cls.win, seconds, idle_first=False)

    @classmethod
    def tearDownClass(cls):
        cls.desktop.cancel_timers()
        import asset_thumbs
        asset_thumbs.reset_worker()
        asset_thumbs.forget()
        asset_thumbs.CACHE_ROOT = cls.original_thumb_cache
        cls.win.destroy()
        cls.temp.cleanup()

    def setUp(self):
        d = self.desktop
        d.files_panel.collapse()
        d.files_panel._reset_filters()
        if getattr(d, 'page_index', None) != PAGE['script']:
            d.show(PAGE['script'])
        self.pump(.2)
        d.files_panel.open_panel()
        self.wait_index()

    def teardown_method(self):
        self.desktop.files_panel.collapse()
        self.desktop.files_panel.stage_filter = None

    def wait_index(self, timeout=8):
        import time
        panel = self.desktop.files_panel
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.pump(.05)
            if not any('文件索引' in label or '素材库' in label
                       for label in self.desktop.task_queue.labels()) and not panel._index_render_job and not panel._index_loading:
                return
        self.fail('后台文件索引加载或批次渲染未完成')

    def rows(self):
        tree = self.desktop.files_panel.script_tree
        result = []
        for item in tree.get_children():
            children = tree.get_children(item)
            if children:
                result.extend(children)
            else:
                result.append(item)
        return result

    def test_rail_lists_all_and_every_stage_in_order(self):
        """UX-C1：图标列＝13 个阶段（无「全部文件」），顺序与 pet_bus.STAGES 一致。"""
        buttons = self.desktop.files_panel.stage_buttons
        self.assertNotIn(None, buttons, '面板内不应再有与入口重复的「全部文件」图标')
        self.assertEqual(len(buttons), len(STAGES))
        self.assertEqual(list(buttons), list(STAGES))
        for stage in STAGES:
            self.assertTrue(stage_name(stage), stage)

    def test_scroll_rail_requests_minimum_width_without_geometry_feedback(self):
        """R3971（任务书 L4-U1）：阶段图标列整列可见，且文件表高度不随刷新振荡。

        T1：1280×800 与 880×600 两档窗口下，13 个阶段钮＋资料库钮的
        实际宽度不小于各自请求宽度（R3214 把画布钉成 1px 的回归，按钮实际宽 1）。
        T2：880×600 下连续刷新 10 次，文件表高度始终不变（守住 R3214 的几何振荡修复）。
        """
        panel = self.desktop.files_panel
        win = self.win
        buttons = list(panel.stage_buttons.values()) + [panel.library_button]
        old_geo = win.geometry()
        try:
            for size in ('1280x800', '880x600'):
                win.geometry(size)
                self.pump(.5)
                for button in buttons:
                    self.assertTrue(button.winfo_ismapped(), '%s: %s' % (size, button))
                    self.assertGreaterEqual(
                        button.winfo_width(), button.winfo_reqwidth(),
                        '%s: %s 实际宽 %d < 请求宽 %d' % (size, button,
                                                        button.winfo_width(),
                                                        button.winfo_reqwidth()))
            win.geometry('880x600')
            heights = []
            for _ in range(10):
                self.pump(.1)
                heights.append(panel.script_tree.winfo_height())
            self.assertEqual(len(set(heights)), 1, heights)
        finally:
            win.geometry(old_geo)
            self.pump(.3)
        self.assertGreater(panel.stage_rail.winfo_width(), 1)

    def test_rail_sits_on_the_right_edge_of_the_panel(self):
        """图标列在停靠面板右缘：pack 信息里 side=right。"""
        panel = self.desktop.files_panel
        self.assertEqual(panel.stage_rail.pack_info().get('side'), 'right')

    def test_stage_buttons_are_tooltipped_icon_buttons(self):
        panel = self.desktop.files_panel
        for stage, button in panel.stage_buttons.items():
            self.assertIn(button.cget('style'), ('RailIcon.TButton', 'Selected.RailIcon.TButton'))
            self.assertTrue(str(button.cget('text')), stage)

    def test_stage_icons_load_files_png(self):
        """REQ-S01-93（R3191）：13 个阶段钮挂 ``<stage>_files.png``（UX-C1：不再挂「全部」）。"""
        panel = self.desktop.files_panel
        for stage in STAGES:
            button = panel.stage_buttons[stage]
            self.assertTrue(button.cget('image'), f'{stage} 缺 PNG 图标')
            self.assertEqual(button._rail_icon_name, f'{stage}_files')

    def test_rail_action_buttons_use_nav_png_icons(self):
        """UX-C1：设置／回收站／清空／素材库四个字符钮换成与侧栏同套 PNG。"""
        panel = self.desktop.files_panel
        expected = (
            (panel.library_settings_button, 'library_settings'),
            (panel.recycle_button, 'recycle'),
            (panel.recycle_purge_button, 'recycle_purge'),
            (panel.library_button, 'library'),
        )
        for button, icon_name in expected:
            self.assertTrue(button.cget('image'), f'{icon_name} 缺 PNG 图标')
            self.assertEqual(button._rail_icon_name, icon_name)
            self.assertEqual(str(button.cget('compound')), 'image')

    def test_missing_png_falls_back_to_emoji(self):
        """REQ-S01-93：PNG 缺失时图标钮退回 STAGE_RAIL_ICONS emoji 文本。"""
        from unittest import mock
        from ui_icons import IconLoader
        panel = self.desktop.files_panel

        def rebuild():
            for child in panel.stage_rail.winfo_children():
                child.destroy()
            panel._build_stage_rail()

        try:
            with mock.patch.object(IconLoader, 'nav_icon', return_value=None):
                rebuild()
            for stage, button in panel.stage_buttons.items():
                self.assertFalse(button.cget('image'), f'{stage} 应退回文本钮')
                self.assertTrue(str(button.cget('text')), stage)
        finally:
            rebuild()  # 恢复 PNG 版供后续用例。

    def test_stage_rail_scrolls_vertically_when_window_is_short(self):
        """REQ-S01-93：窗口矮于图标列需求高时图标列可竖向滚动，末尾入口仍可达。"""
        panel = self.desktop.files_panel
        panel.open_panel()
        self.pump(.3)
        win = self.win
        old_geo = win.geometry()
        try:
            win.geometry('560x380')
            self.pump(.4)
            canvas = panel.stage_rail_scroller.canvas
            self.assertTrue(canvas.winfo_ismapped())
            scrollregion = canvas.cget('scrollregion').split()
            self.assertGreater(float(scrollregion[3]), canvas.winfo_height(),
                               '矮窗口下图标列内容应超出可视区')
            canvas.yview_moveto(1.0)
            self.pump(.1)
            top, bottom = canvas.winfo_rooty(), canvas.winfo_rooty() + canvas.winfo_height()
            lib = panel.library_button
            self.assertGreaterEqual(lib.winfo_rooty(), top - 2,
                                    '滚到底后素材库钮应进入可视区')
            self.assertLessEqual(lib.winfo_rooty() + lib.winfo_height(), bottom + 2)
        finally:
            win.geometry(old_geo)
            self.pump(.3)

    def test_clicking_a_stage_fills_the_list_from_the_index(self):
        """点「资产管理」→ 列表只出该阶段文件，行 id 是项目相对 posix 路径。"""
        panel = self.desktop.files_panel
        file_index.rebuild(self.desktop.root)
        panel.show_stage('assets')
        self.wait_index()
        self.assertEqual(panel.stage_filter, 'assets')
        rows = self.rows()
        self.assertEqual(panel.script_tree.get_children(), ('05资产管理/assets/CHAR_001.png',))
        self.assertTrue(rows, '资产管理阶段应当有行')
        self.assertTrue(all(row.startswith('05资产管理/') for row in rows), rows)
        self.assertTrue(all(panel.script_row_category.get(row) == STAGE_FILTER_ROW_CATEGORY for row in rows))

    def test_selected_stage_is_highlighted(self):
        panel = self.desktop.files_panel
        panel.show_stage('assets')
        self.assertEqual(panel.stage_buttons['assets'].cget('style'), 'Selected.RailIcon.TButton')
        self.assertEqual(panel.stage_buttons['video'].cget('style'), 'RailIcon.TButton')
        panel.show_stage(None)
        # UX-C1：无「全部」钮；复位后所有阶段钮回到普通风格。
        self.assertEqual(panel.stage_buttons['assets'].cget('style'), 'RailIcon.TButton')
        self.assertTrue(all(button.cget('style') == 'RailIcon.TButton'
                            for button in panel.stage_buttons.values()))

    def test_all_returns_to_grouped_project_index(self):
        panel = self.desktop.files_panel
        panel.show_stage('assets')
        self.wait_index()
        panel.show_stage(None)
        self.wait_index()
        self.assertIsNone(panel.stage_filter)
        self.assertIn('stage-group:script', panel.script_tree.get_children())
        self.assertIn('stage-group:assets', panel.script_tree.get_children())
        self.assertTrue(any(row.endswith('CHAR_001.png') for row in self.rows()))
        self.assertTrue(any(panel.script_row_category[row] == 'script' for row in self.rows()))

    def test_rail_has_recycle_entries_after_the_stages(self):
        """R3117／UX-C1：图标列末尾依次是回收站与清空过期（PNG 图标，语义标签仍保留）。"""
        panel = self.desktop.files_panel
        children = list(panel.stage_rail_form.winfo_children())
        recycle_i = children.index(panel.recycle_button)
        purge_i = children.index(panel.recycle_purge_button)
        library_i = children.index(panel.library_button)
        self.assertLess(recycle_i, purge_i)
        self.assertLess(purge_i, library_i)
        self.assertEqual(panel.recycle_button._rail_icon_name, 'recycle')
        self.assertEqual(panel.recycle_purge_button._rail_icon_name, 'recycle_purge')

    def test_project_change_resets_the_stage_filter(self):
        panel = self.desktop.files_panel
        panel.show_stage('video')
        self.pump(.2)
        panel._panel_root = None
        panel.project_changed()
        self.pump(.2)
        self.assertIsNone(panel.stage_filter)
        self.assertTrue(all(button.cget('style') == 'RailIcon.TButton'
                            for button in panel.stage_buttons.values()))


class FilterBarTests(StageRailTests):
    """R3106（任务书 P1，Q25）：阶段／类型／状态／关键字四条件可组合。"""

    def setUp(self):
        d = self.desktop
        d.files_panel.collapse()
        d.files_panel.group_box.set('阶段')
        d.files_panel.group_mode = '阶段'
        d.files_panel.show_stage(None)
        if getattr(d, 'page_index', None) != PAGE['script']:
            d.show(PAGE['script'])
        self.pump(.2)
        d.files_panel.open_panel()
        self.pump(.3)
        file_index.rebuild(d.root)

    def tearDown(self):
        self.desktop.files_panel.collapse()

    def rows(self):
        return super().rows()

    def test_filter_bar_has_four_boxes_and_a_keyword_entry(self):
        """R3983（L4-U2）：阶段选择并入图标列，stage_box 控件不存在。"""
        panel = self.desktop.files_panel
        for name in ('kind_box', 'status_box', 'group_box', 'sort_box', 'keyword_entry'):
            self.assertTrue(hasattr(panel, name), name)
        self.assertFalse(hasattr(panel, 'stage_box'), '阶段下拉框已并入右侧图标列')
        self.assertEqual(tuple(panel.kind_box.cget('values'))[0], '全部类型')
        self.assertEqual(tuple(panel.status_box.cget('values'))[0], '全部状态')

    def test_kind_and_stage_combine(self):
        panel = self.desktop.files_panel
        panel.show_stage('assets')
        panel.kind_box.set('资产')
        panel._apply_filters()
        self.wait_index()
        rows = self.rows()
        self.assertTrue(rows)
        self.assertTrue(all(row.startswith('05资产管理/') for row in rows), rows)

    def test_keyword_filters_by_name(self):
        panel = self.desktop.files_panel
        panel.show_stage(None)
        panel.kind_box.set('全部类型')
        panel.status_box.set('全部状态')
        panel.keyword_var.set('CHAR_001')
        panel._apply_filters()
        self.wait_index()
        rows = self.rows()
        self.assertTrue(rows)
        self.assertTrue(all('CHAR_001' in row for row in rows), rows)

    def test_status_filter_matches_published(self):
        panel = self.desktop.files_panel
        panel.show_stage(None)
        panel.kind_box.set('全部类型')
        panel.status_box.set('草稿')
        panel._apply_filters()
        self.wait_index()
        draft = self.rows()
        panel.status_box.set('已发布')
        panel._apply_filters()
        self.wait_index()
        published = self.rows()
        self.assertEqual(len(draft) + len(published), len([r for r in file_index.rows(self.desktop.root) if not file_index.is_functional(r.path)]))

    def test_clearing_conditions_restores_full_index(self):
        panel = self.desktop.files_panel
        panel.show_stage('assets')
        panel.kind_box.set('资产')
        panel._apply_filters()
        self.wait_index()
        self.assertTrue(panel._filters_active())
        panel.show_stage(None)
        panel.kind_box.set('全部类型')
        panel.status_box.set('全部状态')
        panel.keyword_var.set('')
        panel._apply_filters()
        self.wait_index()
        self.assertFalse(panel._filters_active())
        self.assertTrue(self.rows())
        self.assertIn('stage-group:script', panel.script_tree.get_children())
        self.assertIn('stage-group:assets', panel.script_tree.get_children())


class FilterDedupTests(StageRailTests):
    """R3983（任务书 L4-U2）：筛选区去重——无阶段下拉框；四个下拉框按取值自适应宽。

    面板内宽放不下第二行时，「分组」「排序」连同名称整体换到第三行。
    """

    def _leaf_controls(self):
        """筛选条里所有已映射的非容器控件（下拉框、名称文字、关键字框、刷新钮）。"""
        panel = self.desktop.files_panel
        controls = []
        stack = [panel.filter_bar]
        while stack:
            widget = stack.pop()
            stack.extend(widget.winfo_children())
            if not isinstance(widget, (ttk.Frame, tk.Frame)) and widget.winfo_ismapped():
                controls.append(widget)
        return controls

    def _widen_panel(self):
        """面板宽按最长文件名收缩：放一个够长的名字把它撑到上限再量几何。"""
        panel = self.desktop.files_panel
        panel.show_stage('assets')
        root = Path(self.desktop.root)
        target = root / '05资产管理' / 'assets' / (
            '面板宽度撑满用样例素材文件名零一二三四五六七八九零一二三四五六七八九_0001.png')
        target.write_bytes(b'\x89PNG')
        self.desktop.files_panel.refresh_file_index()
        self.wait_index()
        return target, root

    def _restore_panel(self, target, root, win, old):
        """删掉撑宽用的文件并让面板收回去，不弄脏共用夹具。"""
        target.unlink(missing_ok=True)
        self.desktop.files_panel.refresh_file_index()
        self.wait_index()
        win.geometry(old)
        self.pump(.3)

    def test_filter_controls_sit_on_two_rows_at_wide_window(self):
        """T1：1280×800 下筛选区控件只占两行（按控件顶边坐标分组计数）。

        夹具文件名都很短，面板只有最窄宽；先放一个长名字撑到上限宽（§2.2 实测
        478）再量，收尾删掉并重建索引，不弄脏共用夹具。
        """
        panel = self.desktop.files_panel
        panel.open_panel()
        target, root = self._widen_panel()
        win = self.win
        old = win.geometry()
        try:
            win.geometry('1280x800')
            self.pump(.5)
            tops = sorted({widget.winfo_rooty() for widget in self._leaf_controls()})
            self.assertEqual(len(tops), 2, tops)
        finally:
            self._restore_panel(target, root, win, old)

    def test_each_dropdown_fully_shows_current_value(self):
        """T2：两档窗口下四个下拉框实际宽 ≥ 当前取值文字宽＋箭头区宽。

        箭头区宽度＝控件请求宽 − 字符宽×字符单位，覆盖内边距与下拉箭头；
        文字宽用该控件字体实测，不做全角×2 近似。长文件名撑宽面板避免
        夹具窄面板把换行后的框挤小。
        """
        from tkinter import font as tkfont
        from ui_tokens import COMBOBOX_FONT
        panel = self.desktop.files_panel
        panel.open_panel()
        target, root = self._widen_panel()
        win = self.win
        old = win.geometry()
        try:
            for size in ('1280x800', '880x600'):
                win.geometry(size)
                self.pump(.5)
                for name in ('kind_box', 'status_box', 'group_box', 'sort_box'):
                    box = getattr(panel, name)
                    font = tkfont.Font(root=box, font=COMBOBOX_FONT)
                    chrome = box.winfo_reqwidth() - font.measure('0') * int(box.cget('width'))
                    needed = font.measure(str(box.get())) + chrome
                    self.assertGreaterEqual(
                        box.winfo_width(), needed,
                        '%s %s：实际宽 %d < 取值「%s」宽 %d＋箭头区 %d'
                        % (size, name, box.winfo_width(), box.get(),
                           font.measure(str(box.get())), chrome))
        finally:
            self._restore_panel(target, root, win, old)

    def test_group_sort_pair_wraps_aligned_with_kind_box(self):
        """T3：880×600 下「分组」名称文字换行后左边缘与类型框左边缘一致。"""
        panel = self.desktop.files_panel
        panel.open_panel()
        target, root = self._widen_panel()
        win = self.win
        old = win.geometry()
        try:
            win.geometry('880x600')
            self.pump(.5)
            labels = [widget for widget in self._leaf_controls()
                      if isinstance(widget, ttk.Label)]
            group_label = next(widget for widget in labels
                               if str(widget.cget('text')) == '分组')
            self.assertEqual(group_label.winfo_rootx(), panel.kind_box.winfo_rootx())
            sort_label = next(widget for widget in labels
                              if str(widget.cget('text')) == '排序')
            self.assertGreater(sort_label.winfo_rooty(), panel.kind_box.winfo_rooty())
        finally:
            self._restore_panel(target, root, win, old)

    def test_clicking_stage_icon_updates_panel_title(self):
        """T4：点阶段图标后面板标题随之变化；复位全部＝「项目文件 · 全部阶段」。"""
        panel = self.desktop.files_panel
        before = str(panel.script_title.cget('text'))
        panel.stage_buttons['assets'].invoke()
        self.pump(.2)
        title = str(panel.script_title.cget('text'))
        self.assertNotEqual(title, before)
        self.assertIn(stage_name('assets'), title)
        panel.show_stage(None)
        self.pump(.2)
        self.assertEqual(str(panel.script_title.cget('text')), '项目文件 · 全部阶段')


class IndexLifecycleTests(StageRailTests):
    def render_rows(self, rows, library=False):
        panel = self.desktop.files_panel
        panel.cancel_script_load()
        panel._clear_index_tree()
        panel.library_view = library
        root = Path(self.desktop.root)
        panel._start_index_render(rows, {}, root, library, panel._index_generation,
                                  panel._index_context(root, library))
        self.win.update()

    def test_metadata_columns_use_index_fields_and_keep_filename_id(self):
        from datetime import datetime
        from contract.file_index_contract import FileRow
        panel = self.desktop.files_panel
        stamp = datetime(2026, 11, 16, 12, 34, 56).timestamp()
        row = FileRow(path='05资产管理/assets/原文件名.png', stage='assets', kind='资产',
                      size=1536, mtime=stamp, title='用户标题')
        self.render_rows([row])
        tree = panel.script_tree
        self.assertEqual(tuple(tree['columns']), ('name', 'kind', 'size', 'mtime', 'meta'))
        self.assertEqual([tree.heading(column, 'text') for column in tree['columns']],
                         ['文件名', '类型', '大小', '修改时间', '时长／分辨率'])
        self.assertEqual(tree.item(row.path, 'values'),
                         ('原文件名.png', '资产', '1.5 KB', '2026-11-16 12:34:56', ''))
        self.assertEqual(tree.parent(row.path), '')
        self.assertIn('原文件名.png', panel.script_row_details[row.path])
        self.assertIn('1536', panel.script_row_details[row.path])
        self.assertIn('2026-11-16 12:34:56', panel.script_row_details[row.path])
        self.assertLessEqual(panel.script_box.winfo_width(),
                             self.desktop.panel_area.winfo_width() * .5)
        # R4005（任务书 L4-U3，R4）：属性列不再靠横向滚动访问——放不下的列整列
        # 隐藏（displaycolumns），内容进悬停提示；表格横向滚动范围恒为 (0.0, 1.0)。
        first, last = tree.xview()
        self.assertEqual((first, last), (0.0, 1.0), '表格不再需要横向滚动')
        self.assertIn('资产', panel.script_row_details[row.path])
        self.assertIn('1.5 KB', panel.script_row_details[row.path])

    def test_three_group_modes_reparent_rows_across_stages(self):
        from datetime import datetime
        from unittest.mock import patch
        from contract.file_index_contract import FileRow
        panel = self.desktop.files_panel
        day = datetime(2026, 11, 16, 12).timestamp()
        rows = [FileRow(path='05资产管理/assets/跨阶段A.png', stage='assets', kind='资产', mtime=day),
                FileRow(path='08首帧生成/跨阶段B.png', stage='keyframe', kind='资产', mtime=day),
                FileRow(path='05资产管理/assets/跨阶段C.md', stage='assets', kind='设定',
                        mtime=day - 86400)]
        self.assertEqual(tuple(panel.group_box.cget('values')), ('阶段', '类型', '日期'))
        self.assertEqual(panel.group_box.get(), '阶段')
        for mode, groups, parents in (
                ('阶段', ('stage-group:assets', 'stage-group:keyframe'),
                 ('stage-group:assets', 'stage-group:keyframe', 'stage-group:assets')),
                ('类型', ('kind-group:设定', 'kind-group:资产'),
                 ('kind-group:资产', 'kind-group:资产', 'kind-group:设定')),
                ('日期', ('date-group:2026-11-16', 'date-group:2026-11-15'),
                 ('date-group:2026-11-16', 'date-group:2026-11-16', 'date-group:2026-11-15'))):
            with self.subTest(mode=mode):
                panel.group_box.set(mode)
                with patch.object(panel, '_reload_current_view'):
                    panel._apply_filters()
                self.render_rows(rows)
                self.assertEqual(panel.script_tree.get_children(), groups)
                self.assertEqual(tuple(panel.script_tree.parent(row.path) for row in rows), parents)
                for group in groups:
                    self.assertEqual(panel.script_row_category[group], '__file_group__')
                    self.assertNotIn(group, panel._index_rows)
                    panel.script_tree.selection_set(group)
                    from dataclasses import replace
                    from unittest.mock import Mock
                    opened = Mock()
                    services = replace(panel.page.writing_page_services, open_path=opened)
                    with patch.object(panel.page, 'writing_page_services', services):
                        panel.open_script_file()
                    opened.assert_not_called()
                    with self.assertRaises(ValueError):
                        panel.index_file_path(group)
                    with self.assertRaises(ValueError):
                        panel.delete_script()

    def test_group_modes_keep_status_keyword_and_global_library_filters(self):
        from datetime import datetime
        from unittest.mock import patch
        from contract.file_index_contract import FileRow
        from ui.desktop_files_panel_index import filtered_rows
        panel = self.desktop.files_panel
        stamp = datetime(2026, 11, 16, 12).timestamp()
        rows = [FileRow(path='05资产管理/assets/保留.png', stage='assets', kind='资产',
                        status='已发布', mtime=stamp),
                FileRow(path='08首帧生成/保留.png', stage='keyframe', kind='资产',
                        status='草稿', mtime=stamp),
                FileRow(path='08首帧生成/忽略.png', stage='keyframe', kind='资产',
                        status='已发布', mtime=stamp)]
        panel.stage_filter = None
        with patch('ui.desktop_files_panel_index.load_index', return_value=(rows, {}, {})):
            for mode in ('阶段', '类型', '日期'):
                panel.group_box.set(mode)
                panel.status_box.set('已发布')
                panel.keyword_entry.delete(0, 'end')
                panel.keyword_entry.insert(0, '保留')
                panel._apply_filters()
                self.wait_index()
                self.assertEqual(self.rows(), [rows[0].path], mode)
                self.assertEqual(panel.script_tree.set(rows[0].path, 'kind'), '资产')
        for mode, group in (('阶段', 'stage-group:library'), ('类型', 'kind-group:资产'),
                            ('日期', 'date-group:2026-11-16')):
            panel.group_mode = mode
            selected = filtered_rows(rows, ('assets', '资产', '已发布', '保留', '类型'), True)
            self.render_rows(selected, library=True)
            self.assertEqual(set(panel.script_tree.get_children()), {'library:' + row.path for row in rows[:2]})
            self.assertEqual(set(self.rows()), {'library:' + row.path for row in rows[:2]})
            self.assertTrue(all(panel.script_tree.parent(item) == '' for item in self.rows()))

    def test_missing_cache_rebuild_runs_off_tk_thread(self):
        import threading
        from unittest.mock import patch
        panel = self.desktop.files_panel
        path = file_index.index_path(self.desktop.root)
        path.unlink(missing_ok=True)
        original = file_index.rebuild
        calls = []

        def rebuild(*args, **kwargs):
            calls.append(threading.get_ident())
            return original(*args, **kwargs)

        with patch.object(file_index, 'rebuild', side_effect=rebuild):
            panel.fill_script_list()
            self.wait_index()
        self.assertTrue(calls)
        self.assertTrue(all(thread != threading.get_ident() for thread in calls))
        self.assertTrue(path.is_file())
        self.assertTrue(self.rows())

    def wait_for_index(self, ready, message):
        deadline = time.monotonic() + 5
        while not ready() and time.monotonic() < deadline:
            self.pump(.02)
        self.assertTrue(ready(), message)

    def test_late_result_after_collapse_is_discarded(self):
        import threading
        from unittest.mock import patch
        import ui.desktop_files_panel_index as module
        panel = self.desktop.files_panel
        entered, release = threading.Event(), threading.Event()
        original = module.load_index

        def slow(*args, **kwargs):
            result = original(*args, **kwargs)
            entered.set()
            release.wait(3)
            return result

        with patch.object(module, 'load_index', side_effect=slow):
            panel.fill_script_list()
            try:
                self.wait_for_index(entered.is_set, '后台索引读取未进入等待点')
                panel.collapse()
            finally:
                release.set()
            self.pump(.3)
        self.assertEqual(panel.script_tree.get_children(), ())

    def test_late_result_after_project_switch_is_discarded(self):
        import threading
        from unittest.mock import patch
        import ui.desktop_files_panel_index as module
        panel = self.desktop.files_panel
        release = threading.Event()
        original = module.load_index
        root = self.desktop.root

        def slow(*args, **kwargs):
            result = original(*args, **kwargs)
            release.wait(3)
            return result

        with patch.object(module, 'load_index', side_effect=slow):
            panel.fill_script_list()
            self.pump(.1)
            self.desktop.root = Path(self.temp.name) / '另一个项目'
            release.set()
            self.pump(.3)
            self.assertEqual(panel.script_tree.get_children(), ())
        self.desktop.root = root

    def test_render_is_batched_and_collapse_cancels_pending_rows(self):
        from contract.file_index_contract import FileRow
        from ui.desktop_files_panel_index import RENDER_BATCH
        panel = self.desktop.files_panel
        root = self.desktop.root
        panel.cancel_script_load()
        generation = panel._index_generation
        rows = [FileRow(path='05资产管理/assets/%03d.md' % index, stage='assets', kind='设定')
                for index in range(RENDER_BATCH * 3)]
        context = panel._index_context(root, False)
        panel._start_index_render(rows, {}, root, False, generation, context)
        self.assertEqual(len(self.rows()), RENDER_BATCH)
        heartbeat = []
        self.win.after(0, lambda: heartbeat.append(len(self.rows())))
        self.win.update()
        self.assertTrue(heartbeat)
        self.assertLess(heartbeat[0], len(rows))
        panel.collapse()
        count = len(self.rows())
        self.pump(.1)
        self.assertEqual(len(self.rows()), count)

    def test_group_order_sort_missing_and_real_thumbnail(self):
        import tkinter as tk
        import time
        panel = self.desktop.files_panel
        panel.show_stage(None)
        root = Path(self.desktop.root)
        first = root / '05资产管理/assets/真实缩略.png'
        first.parent.mkdir(parents=True, exist_ok=True)
        image = tk.PhotoImage(master=self.win, width=8, height=8)
        image.put('red', to=(0, 0, 8, 8))
        image.write(str(first), format='png')
        file_index.rebuild(root)
        data = file_index.read(root)
        from contract.file_index_contract import FileRow
        data['files'].append(FileRow(path='05资产管理/assets/不存在.png', stage='assets',
                                    kind='资产', missing=True, mtime=time.time() + 10).to_dict())
        from agent.core import save
        save(file_index.index_path(root), data)
        panel.sort_box.set('修改时间')
        panel._apply_filters()
        self.wait_index()
        self.wait_index()
        groups = panel.script_tree.get_children()
        ordered = ['stage-group:' + stage for stage in STAGES if 'stage-group:' + stage in groups]
        self.assertEqual(list(groups[:len(ordered)]), ordered)
        children = panel.script_tree.get_children('stage-group:assets')
        self.assertEqual(children[0], '05资产管理/assets/不存在.png')
        self.assertIn('missing', panel.script_tree.item(children[0], 'tags'))
        self.assertTrue(panel.script_tree.tag_configure('missing', 'foreground'))
        self.assertTrue(panel.script_tree.item('05资产管理/assets/真实缩略.png', 'image'))
        panel.script_tree.item('stage-group:assets', open=False)
        self.assertFalse(panel.script_tree.item('stage-group:assets', 'open'))

    def test_selected_filtered_file_recycles_without_deleting_project(self):
        from unittest.mock import patch
        from infra.storage_maintenance import recycle_base
        panel = self.desktop.files_panel
        root = Path(self.desktop.root)
        target = root / '05资产管理/assets/仅删此文件.md'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('真实项目文件', encoding='utf8')
        keep = root / '05资产管理/assets/保留此文件.md'
        keep.write_text('不应删除', encoding='utf8')
        panel.show_stage('assets')
        panel.keyword_var.set('仅删此文件')
        panel._apply_filters()
        panel.refresh_file_index()
        self.wait_index()
        relative = target.relative_to(root).as_posix()
        self.assertEqual(self.rows(), [relative])
        panel.script_tree.selection_set(relative)
        from dataclasses import replace
        services = replace(panel.page.writing_page_services, confirm=lambda *args, **kwargs: True)
        with patch.object(panel.page, 'writing_page_services', services), \
                patch.object(panel.page, 'delete_project') as delete_project:
            panel.delete_script()
            self.wait_index()
        delete_project.assert_not_called()
        self.assertFalse(target.exists())
        self.assertTrue(keep.is_file())
        self.assertTrue(root.is_dir())
        recycled = list(recycle_base(root).rglob(target.name))
        self.assertEqual(len(recycled), 1)
        self.assertEqual(recycled[0].read_text(encoding='utf8'), '真实项目文件')
        with self.assertRaises(ValueError):
            panel.index_file_path('stage-group:assets')

    def test_four_script_categories_keep_adoption_confirmation_and_history(self):
        from dataclasses import replace
        from types import SimpleNamespace
        from unittest.mock import Mock, patch
        panel = self.desktop.files_panel
        panel.show_stage(None)
        root = Path(self.desktop.root)
        folders = {'项目设定': ('setting', '设为项目设定定稿'),
                   '项目大纲': ('outline', '设为剧本大纲定稿'),
                   '角色卡': ('character', '设为角色卡定稿'),
                   '项目剧本': ('script', '采用此剧本')}
        paths = {}
        for folder in folders:
            target = root / '01剧本准备' / folder / (folder + '菜单测试.md')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('真实剧本文档', encoding='utf8')
            paths[folder] = target.relative_to(root).as_posix()
        panel.refresh_file_index()
        self.wait_for_index(lambda: set(paths.values()) <= panel.script_row_category.keys(),
                            '四类剧本文档未加载到文件面板')
        menu = Mock()
        services = replace(panel.page.writing_page_services, context_menu=lambda _win: menu)
        with patch.object(panel.page, 'writing_page_services', services):
            for folder, (category, action) in folders.items():
                item = paths[folder]
                self.assertEqual(panel.script_row_category[item], category)
                panel.script_tree.selection_set(item)
                panel.script_tree.see(item)
                self.pump(.05)
                bbox = panel.script_tree.bbox(item)
                menu.command.reset_mock()
                panel.script_menu(panel.script_tree, SimpleNamespace(y=bbox[1] + 1))
                labels = [call.args[0] for call in menu.command.call_args_list]
                self.assertIn(action, labels)
                self.assertIn('删除', labels)
                if category != 'script':
                    self.assertIn('历史快照／对比', labels)
        group = 'stage-group:script'
        panel.script_tree.selection_set(group)
        open_path = Mock()
        services = replace(panel.page.writing_page_services, open_path=open_path)
        with patch.object(panel.page, 'writing_page_services', services):
            panel.open_script_file()
        open_path.assert_not_called()
        self.assertEqual(panel.script_row_details.get(group, ''), '')

    def test_index_path_rejects_group_parent_absolute_and_directory(self):
        from contract.file_index_contract import FileRow
        panel = self.desktop.files_panel
        root = Path(self.desktop.root)
        for key, path in (('parent', '../逃逸.md'), ('absolute', str(root / '文件.md')),
                          ('directory', '05资产管理/assets')):
            panel._index_rows[key] = FileRow(path=path)
            with self.assertRaises(ValueError, msg=key):
                panel.index_file_path(key)
        panel.show_stage(None)
        self.wait_index()
        self.assertIn('stage-group:script', panel.script_tree.get_children())
        panel.script_tree.selection_set('stage-group:script')
        with self.assertRaises(ValueError):
            panel.delete_index_files()

    def test_refresh_discovers_external_file_and_retains_script_actions(self):
        panel = self.desktop.files_panel
        panel.show_stage(None)
        root = Path(self.desktop.root)
        path = root / '05资产管理/assets/外部新增.md'
        path.write_text('新文件', encoding='utf8')
        panel.refresh_file_index()
        self.wait_index()
        self.assertIn(path.relative_to(root).as_posix(), self.rows())
        scripts = [row for row in self.rows() if panel.script_row_category[row] == 'script']
        self.assertTrue(scripts)
        panel.script_tree.selection_set(scripts[0])
        self.assertTrue(panel.selected_script().is_file())


class DockContentTests(StageRailTests):
    """停靠面板只列当前页所属阶段的用户文件；功能文件不进列表。"""

    def test_filtered_rows_excludes_functional_files(self):
        """T6：filtered_rows 滤掉功能文件行，项目视图与素材库视图各断言一次。"""
        from datetime import datetime
        from contract.file_index_contract import FileRow
        from ui.desktop_files_panel_index import filtered_rows
        stamp = datetime(2026, 11, 16, 12).timestamp()
        rows = [FileRow(path='01剧本准备/docs/正文.md', stage='script', kind='剧本', mtime=stamp),
                FileRow(path='01剧本准备/docs/配置.json', stage='script', kind='其他', mtime=stamp)]
        for library in (False, True):
            with self.subTest(library=library):
                found = filtered_rows(rows, (None, None, None, '', '类型'), library)
                paths = [row.path for row in found]
                self.assertIn('01剧本准备/docs/正文.md', paths)
                self.assertFalse(any(path.endswith('.json') for path in paths), paths)

    def test_load_index_calls_discover_for_project_view(self):
        """T7：项目视图非刷新加载调 discover 并带阶段；全局库视图与刷新不调。"""
        from unittest.mock import patch
        from ui.desktop_files_panel_index import load_index
        root = Path(self.desktop.root)
        with patch.object(file_index, 'discover') as discover, \
                patch.object(file_index, 'rows', return_value=[]), \
                patch.object(file_index, 'global_rows', return_value=[]), \
                patch.object(file_index, 'rebuild'), \
                patch.object(file_index, 'rebuild_global'):
            load_index(root, stage='script_structure')
            discover.assert_called_once()
            self.assertEqual(discover.call_args.args[1], 'script_structure')
            discover.reset_mock()
            load_index(root, library=True)
            load_index(root, refresh=True)
            discover.assert_not_called()

    def test_structure_page_shows_only_structure_files(self):
        """T8：剧本结构页打开面板：只列该阶段用户文件、平铺无分组父行、无预览列。"""
        from contract.stage_path_service import read_dirs
        panel = self.desktop.files_panel
        root = Path(self.desktop.root)
        folder = read_dirs(root, 'script_structure')[0]
        folder.mkdir(parents=True, exist_ok=True)
        md = folder / '结构正稿.md'
        md.write_text('正文', encoding='utf8')
        data = folder / '结构数据.json'
        data.write_text('{}', encoding='utf8')
        self.addCleanup(md.unlink, missing_ok=True)
        self.addCleanup(data.unlink, missing_ok=True)
        file_index.rebuild(root)
        self.desktop.show(PAGE['script_structure'])
        self.wait_index()
        self.assertEqual(panel.stage_filter, 'script_structure')
        self.assertEqual(str(panel.script_title.cget('text')), '项目文件 · 剧本结构')
        self.assertEqual(self.rows(), [md.relative_to(root).as_posix()])
        children = panel.script_tree.get_children()
        self.assertFalse(any(item.startswith('stage-group:') for item in children), children)
        self.assertNotIn('tree', str(panel.script_tree['show']))

    def test_stage_filter_follows_page_and_keeps_user_choice(self):
        """T9：换页跟随新页阶段；用户手选阶段保持到下一次换页。"""
        panel = self.desktop.files_panel
        self.desktop.show(PAGE['video'])
        self.wait_index()
        self.assertEqual(panel.stage_filter, 'video')
        panel.show_stage('assets')
        self.wait_index()
        self.assertEqual(panel.stage_filter, 'assets')
        panel.collapse()
        panel.open_panel()
        self.wait_index()
        self.assertEqual(panel.stage_filter, 'assets')
        self.desktop.show(PAGE['audio'])
        self.wait_index()
        self.assertEqual(panel.stage_filter, 'audio')

    def test_new_file_appears_without_refresh(self):
        """T10：当前页阶段目录直接写新文件，收起再打开即出现，不点刷新。"""
        panel = self.desktop.files_panel
        root = Path(self.desktop.root)
        file_index.rebuild(root)
        self.wait_index()
        target = project_stages.writing(root) / '外部新增.md'
        target.write_text('新文件', encoding='utf8')
        self.addCleanup(target.unlink, missing_ok=True)
        panel.collapse()
        panel.open_panel()
        self.wait_index()
        self.assertIn(target.relative_to(root).as_posix(), self.rows())

    def test_multiple_groups_keep_stage_group_rows(self):
        """T11：「全部」多个分组时保留阶段分组父行，子行非空，预览列显示。"""
        panel = self.desktop.files_panel
        panel.show_stage(None)
        self.wait_index()
        children = panel.script_tree.get_children()
        self.assertIn('stage-group:script', children)
        self.assertIn('stage-group:assets', children)
        self.assertTrue(panel.script_tree.get_children('stage-group:script'))
        self.assertTrue(panel.script_tree.get_children('stage-group:assets'))
        self.assertIn('tree', str(panel.script_tree['show']))


class GlobalLibraryViewTests(StageRailTests):
    """R3143（任务书 P3，Q11）：面板里的全局素材库视图。"""

    def test_library_view_without_configured_dir_guides_the_user(self):
        panel = self.desktop.files_panel
        import infra.file_index as file_index
        with tempfile.TemporaryDirectory() as tmp:
            original = file_index.read_global_dir

            def _unset(program=None):
                return None
            file_index.read_global_dir = _unset
            try:
                panel.show_library()
            finally:
                file_index.read_global_dir = original
        self.assertTrue(panel.library_view)
        self.assertIn('尚未设置全局素材库目录', str(self.desktop.status.get()))
        self.assertEqual(list(panel.script_tree.get_children()), [])

    def test_global_first_scan_runs_in_background_and_filters_keep_library(self):
        import threading
        from unittest.mock import patch
        panel = self.desktop.files_panel
        with tempfile.TemporaryDirectory() as tmp:
            library = Path(tmp) / '共享'
            library.mkdir()
            (library / '唯一库文件.md').write_text('真实素材', encoding='utf8')
            calls = []
            original = file_index.rebuild_global

            def rebuild(*args, **kwargs):
                calls.append(threading.get_ident())
                return original(*args, **kwargs)

            with patch.object(file_index, 'read_global_dir', return_value=library), \
                    patch.object(file_index, 'rebuild_global', side_effect=rebuild):
                panel.show_library()
                self.wait_index()
                self.assertTrue(calls)
                self.assertTrue(all(call != threading.get_ident() for call in calls))
                self.assertEqual(self.rows(), ['library:唯一库文件.md'])
                panel.keyword_var.set('唯一库文件')
                panel._apply_filters()
                self.wait_index()
                self.assertTrue(panel.library_view)
                self.assertEqual(self.rows(), ['library:唯一库文件.md'])
                self.assertEqual(str(panel.status_box.cget('state')), 'disabled')
                panel.show_stage(None)
                self.pump(.3)
                self.assertFalse(panel.library_view)
                self.assertEqual(str(panel.status_box.cget('state')), 'readonly')

    def test_configure_library_persists_selection_and_refreshes(self):
        from unittest.mock import patch
        panel = self.desktop.files_panel
        with tempfile.TemporaryDirectory() as tmp:
            library = Path(tmp) / '共享'
            library.mkdir()
            with patch('ui_dialogs.FileDialog.directory', return_value=str(library)), \
                    patch('infra.file_index.read_global_dir', return_value=None), \
                    patch('infra.file_index.save_global_dir') as save, \
                    patch.object(panel, 'show_library') as show:
                panel.configure_library()
            save.assert_called_once_with(str(library))
            show.assert_called_once_with()

    def test_configure_library_cancel_leaves_configuration_untouched(self):
        from unittest.mock import patch
        panel = self.desktop.files_panel
        with patch('ui_dialogs.FileDialog.directory', return_value=''), \
                patch('infra.file_index.save_global_dir') as save:
            panel.configure_library()
        save.assert_not_called()

    def test_add_to_library_copies_selected_project_file(self):
        from unittest.mock import patch
        panel = self.desktop.files_panel
        with tempfile.TemporaryDirectory() as tmp:
            library = Path(tmp) / '共享'
            library.mkdir()
            relative = '01剧本准备/docs/新增素材.md'
            source = Path(self.desktop.root) / relative
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text('共享正文', encoding='utf-8')
            with patch('infra.file_index.read_global_dir', return_value=library):
                panel.add_to_library(str(source))
            self.assertEqual((library / relative).read_text(encoding='utf-8'), '共享正文')
            self.assertTrue(source.is_file())

    def test_open_library_row_uses_library_root(self):
        from unittest.mock import Mock, patch
        from types import SimpleNamespace
        panel = self.desktop.files_panel
        with tempfile.TemporaryDirectory() as tmp:
            library = Path(tmp) / '共享'
            library.mkdir()
            source = library / '样例.md'
            source.write_text('正文', encoding='utf-8')
            with patch('infra.file_index.read_global_dir', return_value=library), \
                    patch.object(panel, 'current_script_tree', return_value=SimpleNamespace(
                        selection=lambda: ('library:样例.md',))), \
                    patch.object(self.desktop, 'writing_page_services', SimpleNamespace(
                        open_path=Mock())) as services:
                panel.open_script_file()
            services.open_path.assert_called_once_with(source.resolve())

    def test_library_view_lists_library_relative_rows(self):
        panel = self.desktop.files_panel
        import infra.file_index as file_index
        with tempfile.TemporaryDirectory() as tmp:
            library = Path(tmp) / '素材库'
            (library / '角色').mkdir(parents=True)
            (library / '角色' / 'CHAR_001.png').write_bytes(b'\x89PNG')
            file_index.rebuild_global(library)
            original = file_index.read_global_dir
            file_index.read_global_dir = lambda program=None: library
            try:
                panel.show_library()
                self.wait_index()
                self.assertEqual(panel.script_tree.get_children(), ('library:角色/CHAR_001.png',))
                self.assertEqual(self.rows(), ['library:角色/CHAR_001.png'])
            finally:
                file_index.read_global_dir = original


class FileActionsTests(StageRailTests):
    """任务书 M5（REQ-S01-95/96）：预览列、时长／分辨率列、打开／在文件夹显示／另存为。"""

    def _index_row(self, iid, stage='视频生成', category=STAGE_FILTER_ROW_CATEGORY):
        """手工插一行并标成索引行（不依赖 file_index 内容）。"""
        panel = self.desktop.files_panel
        tree = panel.script_tree
        if iid not in tree.get_children():
            tree.insert('', 'end', iid=iid, text='', values=(iid.split('/')[-1], ''))
        panel.script_row_category[iid] = category
        panel.script_row_stage[iid] = stage
        tree.selection_set(iid)
        return iid

    def test_index_view_shows_preview_and_meta_columns(self):
        """REQ-S01-95：索引视图开 #0 预览列与「时长／分辨率」列；回剧本视图收回 #0。"""
        panel = self.desktop.files_panel
        panel.show_stage('assets')
        self.pump(.3)
        self.assertIn('tree', str(panel.script_tree.cget('show')))
        self.assertEqual(panel.script_tree.heading('meta')['text'], '时长／分辨率')
        panel.show_stage(None)
        self.pump(.3)
        shown = str(panel.script_tree.cget('show'))
        self.assertIn('headings', shown)
        self.assertIn('tree', shown.replace('headings', ''))

    def test_row_preview_media_returns_placeholder_box(self):
        """REQ-S01-95：视频行先拿到同画幅占位盒（后台封面落地后原位替换）。"""
        import asset_thumbs
        panel = self.desktop.files_panel
        clip = self.project / 'clip.mp4'
        clip.write_bytes(b'0')                      # 内容不重要，只走后缀分流
        image = panel._row_preview(clip)
        self.assertIsNotNone(image, '视频行应给占位盒')
        width, height = asset_thumbs.media_geometry('video', 40)
        self.assertEqual((image.width(), image.height()), (width, height))

    def test_row_preview_text_file_returns_none(self):
        """非媒体非图片（.md）不产预览图。"""
        panel = self.desktop.files_panel
        doc = self.project / '笔记.md'
        doc.write_text('x', encoding='utf8')
        self.assertIsNone(panel._row_preview(doc))

    def test_row_meta_reads_info_sidecar(self):
        """REQ-S01-95：「时长／分辨率」列读 M4 旁路记录；文件签名变化后重读。"""
        import json
        import asset_thumbs
        panel = self.desktop.files_panel
        clip = self.project / 'meta.mp4'
        clip.write_bytes(b'abc')
        stamp = asset_thumbs.file_stamp(clip)
        info = asset_thumbs.info_file(asset_thumbs.cache_key(clip, stamp, 40))
        info.parent.mkdir(parents=True, exist_ok=True)
        info.write_text(json.dumps({'duration': 2.5, 'width': 320, 'height': 180}),
                        encoding='utf-8')
        self.assertEqual(panel._row_meta_text(clip), '2.5s · 320×180')
        doc = self.project / 'meta.md'
        doc.write_text('x', encoding='utf8')
        self.assertEqual(panel._row_meta_text(doc), '')

    def test_index_row_menu_lists_three_actions(self):
        """REQ-S01-96：索引行右键给「打开／在文件夹中显示／另存为…」。"""
        from unittest.mock import patch
        panel = self.desktop.files_panel
        iid = self._index_row('视频/clip.mp4')
        tree = panel.script_tree
        bbox = tree.bbox(iid)
        labels = []
        event = type('E', (), {'y': bbox[1] + 2, 'x_root': 0, 'y_root': 0})()

        def capture(menu, _event):
            last = menu.menu.index('end')
            labels.extend(menu.menu.entrycget(i, 'label')
                          for i in range(last + 1) if last is not None)
            return 'break'

        import ui_widgets
        with patch.object(ui_widgets.ContextMenu, 'popup', capture):
            panel.script_menu(tree, event)
        for label in ('打开', '在文件夹中显示', '另存为…'):
            self.assertIn(label, labels)

    def test_save_as_cancel_writes_nothing(self):
        """REQ-S01-96：另存为取消＝零写入。"""
        from unittest.mock import patch
        panel = self.desktop.files_panel
        src = self.project / '素材' / 'a.png'
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_bytes(b'png')
        self._index_row('素材/a.png', stage='资产管理')
        with patch.object(self.desktop.file_dialog, 'save_file', return_value='') as ask:
            panel.save_as_file()
        self.assertTrue(ask.called)

    def test_save_as_prefills_project_stage_filename(self):
        """REQ-S01-96：预填 ``项目名_阶段名_原文件名``。"""
        from unittest.mock import patch
        panel = self.desktop.files_panel
        src = self.project / '素材' / 'a.png'
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_bytes(b'png')
        self._index_row('素材/a.png', stage='资产管理')
        seen = {}
        with tempfile.TemporaryDirectory() as tmp:
            target = str(Path(tmp) / 'out.png')
            def fake(parent=None, title=None, initialfile=None, defaultextension=None, **kw):
                seen['name'] = initialfile
                return target
            with patch.object(self.desktop.file_dialog, 'save_file', side_effect=fake):
                panel.save_as_file()
            self.assertEqual(seen['name'],
                             '%s_资产管理_a.png' % Path(self.project).name)
            self.assertEqual(Path(target).read_bytes(), b'png', '另存为应复制原文件')
            self.assertEqual(src.read_bytes(), b'png', '原件不应被移动或修改')

    def test_save_as_existing_target_asks_before_overwrite(self):
        """REQ-S01-96：目标已存在先询问；不同意不写。"""
        from unittest.mock import patch
        panel = self.desktop.files_panel
        src = self.project / '素材' / 'a.png'
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_bytes(b'new')
        self._index_row('素材/a.png', stage='资产管理')
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'out.png'
            target.write_bytes(b'old')
            with patch.object(self.desktop.file_dialog, 'save_file', return_value=str(target)),                  patch('desktop.confirm', return_value=False):
                panel.save_as_file()
            self.assertEqual(target.read_bytes(), b'old', '不同意覆盖时目标不应改动')
            with patch.object(self.desktop.file_dialog, 'save_file', return_value=str(target)),                  patch('desktop.confirm', return_value=True):
                panel.save_as_file()
            self.assertEqual(target.read_bytes(), b'new', '同意覆盖后应写入新内容')

    def test_save_as_failure_reports_reason(self):
        """REQ-S01-96：复制失败抛出带原因的错误，不静默。"""
        from unittest.mock import patch
        panel = self.desktop.files_panel
        src = self.project / '素材' / 'a.png'
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_bytes(b'png')
        self._index_row('素材/a.png', stage='资产管理')
        with patch.object(self.desktop.file_dialog, 'save_file',
                          return_value=str(src.parent / 'no_dir' / 'x' / 'a.png')):
            with self.assertRaises(OSError):
                panel.save_as_file()

    def test_show_in_folder_reveals_the_file(self):
        """REQ-S01-96：「在文件夹中显示」走 platform_tools.reveal_in_folder 定位文件本身。"""
        from unittest.mock import patch
        panel = self.desktop.files_panel
        src = self.project / '素材' / 'a.png'
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_bytes(b'png')
        self._index_row('素材/a.png')
        seen = {}
        import contract.platform_tools as platform_tools
        with patch.object(platform_tools, 'reveal_in_folder',
                          lambda path: seen.setdefault('path', Path(path))):
            panel.show_in_folder()
        self.assertEqual(seen['path'], src)


class FilenameDisplayTests(StageRailTests):
    """任务书 L4-U3：文件名列优先——其余列放不下就整列隐藏（内容进悬停提示）；
    只剩文件名列仍不够宽时文件名中间省略；表格不再需要横向滚动。"""

    LONG_NAME = '面板文件名完整显示样例素材ABCDEFGHIJKLMNOPQR_0001.png'
    LONG_ROW = '05资产管理/assets/' + LONG_NAME

    def _seed_long_file(self):
        panel = self.desktop.files_panel
        panel.show_stage('assets')
        self.assertEqual(len(self.LONG_NAME), 40, '样例文件名按任务卡取 40 个字符')
        root = Path(self.desktop.root)
        target = root / '05资产管理' / 'assets' / self.LONG_NAME
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b'\x89PNG')
        self.desktop.files_panel.refresh_file_index()
        self.wait_index()
        return target

    def _drop_long_file(self, target):
        target.unlink(missing_ok=True)
        self.desktop.files_panel.refresh_file_index()
        self.wait_index()

    def test_long_filename_fully_visible_at_wide_window(self):
        """T1：1280×800 下 40 字符文件名完整显示——显示文字是全名，
        文件名列可见宽 ≥ 文字像素宽＋单元格留白。"""
        from ui_tokens import SPACING
        panel = self.desktop.files_panel
        panel.open_panel()
        target = self._seed_long_file()
        win, old = self.win, self.win.geometry()
        try:
            win.geometry('1280x800')
            self.pump(.5)
            tree = panel.script_tree
            self.assertEqual(str(tree.item(self.LONG_ROW, 'values')[0]), self.LONG_NAME)
            font = panel._script_list_font()
            bbox = tree.bbox(self.LONG_ROW, 'name')
            self.assertTrue(bbox, '文件名列应处于可见区内')
            self.assertGreaterEqual(
                bbox[2], font.measure(self.LONG_NAME) + SPACING['sm'],
                '文件名列可见宽 %d < 文字宽 %d＋留白' % (bbox[2], font.measure(self.LONG_NAME)))
        finally:
            self._drop_long_file(target)
            win.geometry(old)
            self.pump(.3)

    def test_long_filename_middle_elided_at_narrow_window(self):
        """T2：880×600 下显示文字以全名前 8 字符开头、以扩展名结尾、含「…」，
        且显示文字像素宽 ≤ 文件名列可见宽。"""
        panel = self.desktop.files_panel
        panel.open_panel()
        target = self._seed_long_file()
        win, old = self.win, self.win.geometry()
        try:
            win.geometry('880x600')
            self.pump(.5)
            tree = panel.script_tree
            shown = str(tree.item(self.LONG_ROW, 'values')[0])
            self.assertTrue(shown.startswith(self.LONG_NAME[:8]), shown)
            self.assertTrue(shown.endswith('.png'), shown)
            self.assertIn('…', shown)
            font = panel._script_list_font()
            bbox = tree.bbox(self.LONG_ROW, 'name')
            name_w = bbox[2] if bbox else int(tree.column('name', 'width'))
            self.assertLessEqual(
                font.measure(shown), name_w,
                '显示文字宽 %d > 文件名列可见宽 %d' % (font.measure(shown), name_w))
        finally:
            self._drop_long_file(target)
            win.geometry(old)
            self.pump(.3)

    def test_table_never_scrolls_horizontally(self):
        """T3：两档窗口下表格横向滚动范围都是 (0.0, 1.0)。"""
        panel = self.desktop.files_panel
        panel.open_panel()
        target = self._seed_long_file()
        win, old = self.win, self.win.geometry()
        try:
            for size in ('1280x800', '880x600'):
                win.geometry(size)
                self.pump(.5)
                first, last = panel.script_tree.xview()
                self.assertAlmostEqual(first, 0.0, places=3, msg=size)
                self.assertAlmostEqual(last, 1.0, places=3, msg=size)
        finally:
            self._drop_long_file(target)
            win.geometry(old)
            self.pump(.3)

    def test_no_column_half_visible(self):
        """T4：任一显示列的右边缘不超过表格可见区右边缘（无半露列）。"""
        panel = self.desktop.files_panel
        panel.open_panel()
        target = self._seed_long_file()
        win, old = self.win, self.win.geometry()
        try:
            tree = panel.script_tree
            for size in ('1280x800', '880x600'):
                win.geometry(size)
                self.pump(.5)
                shown = [column for column in tree['displaycolumns']
                         if column != '#all'] or ['name', 'kind', 'size', 'mtime', 'meta']
                total = int(tree.column('#0', 'width')) + sum(
                    int(tree.column(column, 'width')) for column in shown)
                self.assertLessEqual(
                    total, tree.winfo_width() + 2,
                    '%s：显示列合计宽 %d 超出表格可见宽 %d'
                    % (size, total, tree.winfo_width()))
        finally:
            self._drop_long_file(target)
            win.geometry(old)
            self.pump(.3)

    def test_tooltip_keeps_full_name_and_hidden_columns(self):
        """T5：悬停提示带完整文件名，以及被隐藏各列的内容
        （类型、大小、修改时间、时长／分辨率）。"""
        from datetime import datetime
        from unittest.mock import patch
        from contract.file_index_contract import FileRow
        panel = self.desktop.files_panel
        stamp = datetime(2026, 11, 17, 8, 30, 0).timestamp()
        row = FileRow(path='05资产管理/assets/悬停样例.mp4', stage='assets',
                      kind='资产', size=2048, mtime=stamp)
        with patch.object(panel, '_row_meta_text', return_value='2.5s · 320×180'):
            panel.cancel_script_load()
            panel._clear_index_tree()
            panel.library_view = False
            root = Path(self.desktop.root)
            panel._start_index_render([row], {}, root, False, panel._index_generation,
                                      panel._index_context(root, False))
            self.win.update()
        details = panel.script_row_details[row.path]
        self.assertIn('悬停样例.mp4', details)
        self.assertIn('资产', details)
        self.assertIn('2.0 KB', details)
        self.assertIn('2026-11-17 08:30:00', details)
        self.assertIn('2.5s · 320×180', details)

    def test_elided_row_opens_the_full_filename(self):
        """T6：省略显示的行触发「打开」，拿到的路径仍是完整文件名对应的文件。"""
        from dataclasses import replace
        from unittest.mock import Mock, patch
        panel = self.desktop.files_panel
        panel.open_panel()
        target = self._seed_long_file()
        win, old = self.win, self.win.geometry()
        try:
            win.geometry('880x600')
            self.pump(.5)
            tree = panel.script_tree
            self.assertIn('…', str(tree.item(self.LONG_ROW, 'values')[0]),
                          '前置：该行应处于省略显示')
            tree.selection_set(self.LONG_ROW)
            opened = Mock()
            services = replace(panel.page.writing_page_services, open_path=opened)
            with patch.object(panel.page, 'writing_page_services', services):
                panel.open_script_file()
            opened.assert_called_once()
            opened_path = Path(opened.call_args.args[0])
            self.assertEqual(opened_path.name, self.LONG_NAME)
            self.assertTrue(opened_path.is_file())
        finally:
            self._drop_long_file(target)
            win.geometry(old)
            self.pump(.3)


class StageFileIconTests(unittest.TestCase):
    """R4013（任务书 L4-U4）：阶段文件图标＝导航图形原大小贴左上＋右下角统一文件标识。

    断言针对 PNG 像素本身：``<stage>_files.png`` 与 ``<nav>.png``（nav 名经
    ui.desktop_page_registry.NAV_STAGE_ICONS 取得，导航图固定在画布左上、
    越界按全透明比）在右下 50%×50% 角标区域之外逐像素一致；全部差异像素
    构成文件标识的外接矩形，须落在该区域内、宽高各 ≥35% 画布边长，且 13 张图
    完全一致；生成脚本重跑结果可复现。
    """

    @staticmethod
    def _nav_dir():
        from tests.architecture._scan import ROOT
        return ROOT / 'assets' / 'nav'

    @classmethod
    def _rgba(cls, name):
        from PIL import Image
        with Image.open(cls._nav_dir() / name) as image:
            return image.convert('RGBA')

    @staticmethod
    def _nav_pixel(nav, x, y):
        if 0 <= x < nav.width and 0 <= y < nav.height:
            return nav.getpixel((x, y))
        return (0, 0, 0, 0)

    @classmethod
    def _diff_box(cls, comp, nav):
        """合成图与导航图逐像素差异的外接矩形 (left, top, right, bottom)。"""
        xs, ys = [], []
        for y in range(comp.height):
            for x in range(comp.width):
                if comp.getpixel((x, y)) != cls._nav_pixel(nav, x, y):
                    xs.append(x)
                    ys.append(y)
        if not xs:
            return None
        return min(xs), min(ys), max(xs) + 1, max(ys) + 1

    @classmethod
    def _pairs(cls):
        from ui.desktop_page_registry import NAV_STAGE_ICONS
        return [(stage, cls._rgba(f'{stage}_files.png'),
                 cls._rgba(f'{NAV_STAGE_ICONS[stage]}.png')) for stage in STAGES]

    def test_stage_graphic_identical_to_nav_icon_outside_badge_region(self):
        """T1：右下 50%×50% 区域以外，_files 图与导航图逐像素一致。"""
        for stage, comp, nav in self._pairs():
            edge_x, edge_y = -(-comp.width // 2), -(-comp.height // 2)
            bad = [(x, y) for y in range(comp.height) for x in range(comp.width)
                   if not (x >= edge_x and y >= edge_y)
                   and comp.getpixel((x, y)) != self._nav_pixel(nav, x, y)]
            self.assertEqual(bad, [],
                             f'{stage}: 角标区域外 {len(bad)} 像素不同，首个 {bad[:1]}')

    def test_badge_diff_box_in_bottom_right_region(self):
        """T2：差异外接矩形落在右下 50%×50% 内，宽高各在画布边长 35%–45% 之间。"""
        import math
        for stage, comp, nav in self._pairs():
            box = self._diff_box(comp, nav)
            self.assertIsNotNone(box, f'{stage}: 与导航图没有任何差异，文件标识缺失')
            left, top, right, bottom = box
            self.assertGreaterEqual(left, -(-comp.width // 2),
                                    f'{stage} 差异越出右半区: {box} (画布 {comp.size})')
            self.assertGreaterEqual(top, -(-comp.height // 2),
                                    f'{stage} 差异越出下半区: {box} (画布 {comp.size})')
            self.assertGreaterEqual(right - left, math.ceil(comp.width * 0.35),
                                    f'{stage} 文件标识宽不足 35%: {box}')
            self.assertGreaterEqual(bottom - top, math.ceil(comp.height * 0.35),
                                    f'{stage} 文件标识高不足 35%: {box}')
            self.assertLessEqual(right - left, math.floor(comp.width * 0.45),
                                 f'{stage} 文件标识宽超 45%: {box}')
            self.assertLessEqual(bottom - top, math.floor(comp.height * 0.45),
                                 f'{stage} 文件标识高超 45%: {box}')

    def test_badge_diff_box_identical_across_stages(self):
        """T3：13 张图画布尺寸一致，差异外接矩形坐标完全相同。"""
        pairs = self._pairs()
        sizes = {comp.size for _stage, comp, _nav in pairs}
        self.assertEqual(len(sizes), 1, f'画布尺寸不统一: {sizes}')
        boxes = {stage: self._diff_box(comp, nav) for stage, comp, nav in pairs}
        self.assertEqual(len(set(boxes.values())), 1,
                         f'文件标识外接矩形不一致: {boxes}')

    def test_icon_regeneration_is_reproducible(self):
        """T4：重跑 scripts/build_nav_icons.py，assets/nav 下 PNG 字节不变。"""
        import subprocess
        import sys
        from tests.architecture._scan import ROOT
        nav_dir = self._nav_dir()
        before = {path.name: path.read_bytes() for path in nav_dir.glob('*.png')}
        subprocess.run([sys.executable, '-B',
                        str(ROOT / 'scripts' / 'build_nav_icons.py')],
                       check=True, capture_output=True, timeout=120)
        after = {path.name: path.read_bytes() for path in nav_dir.glob('*.png')}
        self.assertEqual(set(before), set(after))
        changed = [name for name in before if before[name] != after[name]]
        self.assertEqual(changed, [], f'重跑生成脚本改动了: {changed}')


if __name__ == '__main__':
    unittest.main()
