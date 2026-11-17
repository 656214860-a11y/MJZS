# -*- coding: utf-8 -*-
"""R3094（任务书 P1）：停靠面板右缘的阶段快捷图标列。

覆盖：图标列在面板右缘、按 ``pet_bus.STAGES`` 顺序垂直排列、每个都带 Tooltip 中文名；
点阶段图标按项目文件索引填表（不扫盘）、当前阶段高亮、点「全部」回到剧本准备四类视图；
换项目时阶段筛选复位。
"""
import tempfile
import unittest
from pathlib import Path

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

    def test_stage_icons_load_files_png(self):
        """REQ-S01-93（R3191）：13 个阶段钮挂 ``<stage>_files.png``，「全部」挂 ``project_files.png``。"""
        panel = self.desktop.files_panel
        for stage in STAGES:
            button = panel.stage_buttons[stage]
            self.assertTrue(button.cget('image'), f'{stage} 缺 PNG 图标')
            self.assertEqual(button._rail_icon_name, f'{stage}_files')
        all_button = panel.stage_buttons[None]
        self.assertTrue(all_button.cget('image'), '「全部」缺 project_files.png')
        self.assertEqual(all_button._rail_icon_name, 'project_files')

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
        for child in panel.stage_rail_form.winfo_children():
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
            finally:
                file_index.read_global_dir = original
        rows = list(panel.script_tree.get_children())
        self.assertEqual(rows, ['library:角色/CHAR_001.png'])


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
        self.assertNotIn('tree', shown.replace('headings', ''))

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


if __name__ == '__main__':
    unittest.main()
