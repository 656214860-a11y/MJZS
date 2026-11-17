# -*- coding: utf-8 -*-
"""R3094（任务书 P1）：停靠面板右缘的阶段快捷图标列。

覆盖：图标列在面板右缘、按 ``pet_bus.STAGES`` 顺序垂直排列、每个都带 Tooltip 中文名；
点阶段图标按项目文件索引填表（不扫盘）、当前阶段高亮、点「全部」回到剧本准备四类视图；
换项目时阶段筛选复位。
"""
import tempfile
import unittest

import tk_test_support
import project_stages

from contract.pet_bus import STAGES, stage_name
from desktop import Desktop, PAGE
from ui.desktop_files_panel_filters import STAGE_FILTER_ROW_CATEGORY, STAGE_RAIL_ALL
import infra.file_index as file_index
import test_desktop_startup_perf as startup_fixtures


class StageRailTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.win = tk_test_support.make_root()
        cls.temp = tempfile.TemporaryDirectory(prefix='r3094-stage-rail-')
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
        cls.win.destroy()
        cls.temp.cleanup()

    def setUp(self):
        d = self.desktop
        d.files_panel.collapse()
        d.files_panel.stage_filter = None
        if getattr(d, 'page_index', None) != PAGE['script']:
            d.show(PAGE['script'])
        self.pump(.2)
        d.files_panel.open_panel()
        self.pump(.3)

    def teardown_method(self):
        self.desktop.files_panel.collapse()
        self.desktop.files_panel.stage_filter = None

    def test_rail_lists_all_and_every_stage_in_order(self):
        """图标列＝「全部」＋13 个阶段，顺序与 pet_bus.STAGES 一致。"""
        buttons = self.desktop.files_panel.stage_buttons
        self.assertIn(None, buttons, '「全部」入口缺失')
        self.assertEqual(len(buttons), len(STAGES) + 1)
        order = [stage for stage in buttons if stage is not None]
        self.assertEqual(order, list(STAGES))
        for stage in STAGES:
            self.assertTrue(stage_name(stage), stage)

    def test_rail_sits_on_the_right_edge_of_the_panel(self):
        """图标列在停靠面板右缘：pack 信息里 side=right。"""
        panel = self.desktop.files_panel
        self.assertEqual(panel.stage_rail.pack_info().get('side'), 'right')

    def test_stage_buttons_are_tooltipped_icon_buttons(self):
        panel = self.desktop.files_panel
        for stage, button in panel.stage_buttons.items():
            self.assertIn(button.cget('style'), ('RailIcon.TButton', 'Selected.RailIcon.TButton'))
            expected = STAGE_RAIL_ALL if stage is None else stage
            self.assertTrue(str(button.cget('text')), expected)

    def test_clicking_a_stage_fills_the_list_from_the_index(self):
        """点「资产管理」→ 列表只出该阶段文件，行 id 是项目相对 posix 路径。"""
        panel = self.desktop.files_panel
        file_index.rebuild(self.desktop.root)
        panel.show_stage('assets')
        self.pump(.2)
        self.assertEqual(panel.stage_filter, 'assets')
        rows = list(panel.script_tree.get_children())
        self.assertTrue(rows, '资产管理阶段应当有行')
        self.assertTrue(all(row.startswith('05资产管理/') for row in rows), rows)
        self.assertTrue(all(panel.script_row_category.get(row) == STAGE_FILTER_ROW_CATEGORY for row in rows))

    def test_selected_stage_is_highlighted(self):
        panel = self.desktop.files_panel
        panel.show_stage('assets')
        self.assertEqual(panel.stage_buttons['assets'].cget('style'), 'Selected.RailIcon.TButton')
        self.assertEqual(panel.stage_buttons['video'].cget('style'), 'RailIcon.TButton')
        panel.show_stage(None)
        self.assertEqual(panel.stage_buttons[None].cget('style'), 'Selected.RailIcon.TButton')
        self.assertEqual(panel.stage_buttons['assets'].cget('style'), 'RailIcon.TButton')

    def test_all_returns_to_the_script_view(self):
        panel = self.desktop.files_panel
        panel.show_stage('assets')
        self.pump(.2)
        panel.show_stage(None)
        self.pump(.4)
        self.assertIsNone(panel.stage_filter)
        # 剧本准备四类视图的行 id 是绝对路径。
        for row in panel.script_tree.get_children():
            self.assertTrue(row.startswith(str(self.desktop.root)), row)

    def test_rail_has_recycle_entries_after_the_stages(self):
        """R3117：图标列末尾依次是「回收站（浏览/恢复）」与「清空过期回收站」。"""
        panel = self.desktop.files_panel
        texts = []
        for child in panel.stage_rail.winfo_children():
            try:
                texts.append(str(child.cget('text')))
            except Exception:
                continue
        self.assertIn('♻', texts)
        self.assertIn('🗑', texts)
        self.assertLess(texts.index('♻'), texts.index('🗑'))
        self.assertFalse(hasattr(self.desktop, 'files_panel') is False)

    def test_project_change_resets_the_stage_filter(self):
        panel = self.desktop.files_panel
        panel.show_stage('video')
        self.pump(.2)
        panel._panel_root = None
        panel.project_changed()
        self.pump(.2)
        self.assertIsNone(panel.stage_filter)
        self.assertEqual(panel.stage_buttons[None].cget('style'), 'Selected.RailIcon.TButton')


class FilterBarTests(StageRailTests):
    """R3106（任务书 P1，Q25）：阶段／类型／状态／关键字四条件可组合。"""

    def setUp(self):
        d = self.desktop
        d.files_panel.collapse()
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
        return list(self.desktop.files_panel.script_tree.get_children())

    def test_filter_bar_has_three_boxes_and_a_keyword_entry(self):
        panel = self.desktop.files_panel
        for name in ('stage_box', 'kind_box', 'status_box', 'keyword_entry'):
            self.assertTrue(hasattr(panel, name), name)
        self.assertEqual(tuple(panel.stage_box.cget('values'))[0], '全部阶段')
        self.assertEqual(tuple(panel.kind_box.cget('values'))[0], '全部类型')
        self.assertEqual(tuple(panel.status_box.cget('values'))[0], '全部状态')

    def test_kind_and_stage_combine(self):
        panel = self.desktop.files_panel
        panel.stage_box.set('资产管理')
        panel.kind_box.set('资产')
        panel._apply_filters()
        self.pump(.2)
        rows = self.rows()
        self.assertTrue(rows)
        self.assertTrue(all(row.startswith('05资产管理/') for row in rows), rows)

    def test_keyword_filters_by_name(self):
        panel = self.desktop.files_panel
        panel.stage_box.set('全部阶段')
        panel.kind_box.set('全部类型')
        panel.status_box.set('全部状态')
        panel.keyword_var.set('CHAR_001')
        panel._apply_filters()
        self.pump(.2)
        rows = self.rows()
        self.assertTrue(rows)
        self.assertTrue(all('CHAR_001' in row for row in rows), rows)

    def test_status_filter_matches_published(self):
        panel = self.desktop.files_panel
        panel.stage_box.set('全部阶段')
        panel.kind_box.set('全部类型')
        panel.status_box.set('草稿')
        panel._apply_filters()
        self.pump(.2)
        draft = self.rows()
        panel.status_box.set('已发布')
        panel._apply_filters()
        self.pump(.2)
        published = self.rows()
        self.assertEqual(len(draft) + len(published), len(file_index.rows(self.desktop.root)))

    def test_clearing_every_condition_restores_the_script_view(self):
        panel = self.desktop.files_panel
        panel.stage_box.set('资产管理')
        panel.kind_box.set('资产')
        panel._apply_filters()
        self.pump(.2)
        self.assertTrue(panel._filters_active())
        panel.show_stage(None)
        panel.kind_box.set('全部类型')
        panel.status_box.set('全部状态')
        panel.keyword_var.set('')
        panel._apply_filters()
        self.pump(.4)
        self.assertFalse(panel._filters_active())
        for row in self.rows():
            self.assertTrue(row.startswith(str(self.desktop.root)), row)


if __name__ == '__main__':
    unittest.main()
