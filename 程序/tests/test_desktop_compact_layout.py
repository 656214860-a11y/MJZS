"""R1446：真实 Tk 双尺寸布局；临时项目不接触用户登记或配置。"""
import tempfile
import time
import unittest
from unittest import mock
import tk_test_support
from widget_test_support import widget_list
from pathlib import Path
import tkinter as tk
from tkinter import ttk, font

from contract.app_metadata import APP_NAME
from desktop import Desktop, PAGE
from skip_reasons import PLATFORM_TK_DISPLAY
import test_desktop_startup_perf as startup_fixtures
from contract import project_stages
from ui_tokens import DESKTOP_LAYOUT


class CompactDesktopGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.win = tk_test_support.make_root()
        cls.temp = tempfile.TemporaryDirectory(prefix='r1446-geometry-')
        app, cls.project = startup_fixtures.DesktopStartupPerfTests._startup_app(cls.temp.name, remembered=True)
        # 每一类都放长名称文件，悬停详情必须来自既有扫描结果。
        for directory in ('项目设定', '项目大纲', '角色卡', '项目剧本'):
            target = (project_stages.writing(cls.project) / '测试提供方' / '测试模型'
                      / '创意_20261015' / directory)
            target.mkdir(parents=True)
            (target / ('一个需要悬停才能读完的很长文件名称_' + directory + '.md')).write_text('测试正文', encoding='utf8')
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

    def resize(self, width, height):
        self.win.geometry(f'{width}x{height}')
        self.pump()
        self.assertEqual((self.win.winfo_width(), self.win.winfo_height()), (width, height))

    def reveal(self, widget):
        """把侧栏控件滚到视口内；只动侧栏画布，不依赖真实指针或焦点。"""
        canvas = self.desktop.sidebar_canvas
        self.win.update_idletasks()
        box = canvas.bbox('all')
        total = max(1, box[3] - box[1]) if box else 1
        offset = widget.winfo_rooty() - canvas.winfo_rooty() + canvas.canvasy(0)
        canvas.yview_moveto(max(0.0, min(1.0, offset / total)))
        self.pump(.08)

    def test_header_sidebar_and_file_area_remain_visible_after_shrink_and_grow(self):
        d = self.desktop
        for width, height in ((942, 1032), (800, 600), (990, 632), (942, 1032)):
            with self.subTest(size=(width, height)):
                self.resize(width, height)
                # 上一档可能把侧栏留在底部；每档从顶部量起，后续断言才不受滚动位置影响。
                d.sidebar_canvas.yview_moveto(0);d.align_header();self.pump(.05)
                # R3016：页标题进统一底栏左区段；侧栏图标轨顶到滚动区上沿。
                self.assertIn('当前项目：', d.win.title())
                self.assertEqual(str(d.status_bar._segments['page'][1].winfo_parent()),
                                 str(d.status_bar.left_zone))
                # R3016：顶部标题行已删，聊天框紧贴内容区顶部。
                content_top=d.canvas.winfo_rooty()
                self.assertGreaterEqual(d.idea_log.winfo_rooty(),content_top-1)
                self.assertLessEqual(d.idea_log.winfo_rooty()-content_top,40,
                                     '聊天框应紧贴内容区顶部')
                # R2946：设置入口是图标轨末尾的轨钮，三虎簇在 pet_dock，都钉在侧栏左下角、不参与滚动。
                self.assertIsNone(d.pet.gear, '真桌面不再建底栏齿轮')
                gear, dock = d.settings_rail_button, d.pet_dock
                self.assertEqual(str(dock.winfo_parent()), str(d.sidebar_dock))
                self.assertGreaterEqual(gear.winfo_rooty(), d.sidebar_canvas.winfo_rooty())
                self.assertLessEqual(dock.winfo_rooty()+dock.winfo_height(),
                                     d.sidebar_area.winfo_rooty()+d.sidebar_area.winfo_height()+1)
                # R2897 图标轨：项目区之后依次是14 个导航钮、设置钮和会员钮。
                rail=[*d.nav,d.settings_rail_button,d.account_button]
                previous_bottom = d.project_block.winfo_rooty()+d.project_block.winfo_height()
                for widget in rail:
                    self.assertGreaterEqual(widget.winfo_rooty(), previous_bottom)
                    previous_bottom = widget.winfo_rooty()+widget.winfo_height()
                self.assertEqual(len(d.nav), 14, '14 个阶段按钮都要在侧栏里')
                canvas = d.sidebar_canvas
                # REQ-UI-SIDEBAR-1：项目区＝「项目」主图标＋名称列表；四个原入口收进
                # 按需展开的右侧二级列，不占侧栏滚动轨，量 rail_widgets 时不含它们。
                self.assertTrue(d.project_button.winfo_ismapped())
                self.assertTrue(d.project_name_list.winfo_ismapped())
                rail_widgets=tuple(rail)
                for widget in rail_widgets:
                    self.reveal(widget)
                    self.assertGreaterEqual(widget.winfo_rooty(), canvas.winfo_rooty()-1)
                    self.assertLessEqual(widget.winfo_rooty()+widget.winfo_height(),
                                         canvas.winfo_rooty()+canvas.winfo_height()+1)
                    self.assertGreaterEqual(widget.winfo_height(), widget.winfo_reqheight())
                # R2962：文件栏改右侧停靠面板（默认收起）；R3060 起面板停靠列与输入框同列，
                # 全高覆盖画布＋共享输入区，底边不越出停靠列、且延伸到画布底边以下。
                d.files_panel.open_panel();self.pump(.05)
                self.assertTrue(d.files_panel._open,'有项目时入口允许打开文件面板')
                self.assertLessEqual(d.script_box.winfo_rooty()+d.script_box.winfo_height(),
                                     d.panel_area.winfo_rooty()+d.panel_area.winfo_height()+2)
                self.assertGreater(d.script_box.winfo_rooty()+d.script_box.winfo_height(),
                                   d.canvas.winfo_rooty()+d.canvas.winfo_height(),
                                   'R3060：面板全高停靠，底边延伸到共享输入框一侧')
                # 共享输入框与聊天框同宽：面板打开时两者右缘一致。
                self.assertAlmostEqual(d.shared_input.winfo_rootx()+d.shared_input.winfo_width(),
                                       d.canvas.winfo_rootx()+d.canvas.winfo_width(), delta=2,
                                       msg='输入框宽度须与聊天框一致')
                d.files_panel.collapse();self.pump(.05)
                self.assertLessEqual(d.content.winfo_height(), d.canvas.winfo_height()+2)

    def test_header_geometry_across_stages_and_sizes(self):
        d = self.desktop
        def rect(w):
            return (w.winfo_rootx(), w.winfo_rooty(),
                    w.winfo_rootx()+w.winfo_width(), w.winfo_rooty()+w.winfo_height())
        def separate(a, b):
            ax, ay, ar, ab = rect(a); bx, by, br, bb = rect(b)
            self.assertTrue(ar <= bx or br <= ax or ab <= by or bb <= ay,
                            f'{a}: {rect(a)} overlaps {b}: {rect(b)}')
        try:
            for width, height in ((800, 600), (990, 632), (942, 1032)):
                self.resize(width, height)
                for stage in ('script', 'storyboard', 'assets'):
                    with self.subTest(size=(width,height), stage=stage):
                        d.show(PAGE[stage]); self.pump()
                        anchor = d.idea_log if stage == 'script' else d.content
                        # R3016：页标题进统一底栏左区；侧栏图标轨顶到上沿。
                        self.assertTrue(d.status_bar._segments['page'][1].winfo_ismapped())
                        # R3016：页头标语删除；Token 指示器 pack 在统一底栏左区。
                        self.assertFalse(hasattr(d, 'header_slogan'), '页头不再有标语')
                        self.assertEqual(str(d.usage_indicator.master), str(d.status_bar.left_zone))
                        self.assertAlmostEqual(d.usage_indicator.winfo_rooty() + d.usage_indicator.winfo_height() / 2,
                                               d.status_bar.winfo_rooty() + d.status_bar.winfo_height() / 2,
                                               delta=max(2, d.status_bar.winfo_height()))
                        # 三虎簇钉在侧栏底栏：头像在 pet_dock 内、不碰标题行与正文。
                        pets = (d.pet.canvas, d.pet.paws, d.pet.caption)
                        for pet in pets:
                            self.assertTrue(pet.winfo_ismapped())
                            self.assertEqual(str(pet.winfo_parent()), str(d.pet_dock))
                            self.assertGreaterEqual(rect(pet)[0], rect(d.sidebar_area)[0])
                            self.assertLessEqual(rect(pet)[2], rect(d.sidebar_area)[2] + 1)
                            self.assertGreaterEqual(rect(pet)[1], rect(d.sidebar_area)[1])
                            self.assertLessEqual(rect(pet)[3], rect(d.sidebar_area)[3] + 1)
                            self.assertLessEqual(rect(pet)[3], rect(d.sidebar_dock)[3] + 1)
                        if stage == 'script':
                            # R3016：顶部标题行已删——聊天框贴内容区顶部，不再与侧栏项目区顶逐像素对齐。
                            content_top=d.canvas.winfo_rooty()
                            self.assertGreaterEqual(d.idea_log.winfo_rooty(),content_top-1)
                            self.assertLessEqual(d.idea_log.winfo_rooty()-content_top,40,
                                                 '聊天框应紧贴内容区顶部')
                            for pet in pets:separate(d.idea_log, pet)
        finally:
            d.show(PAGE['script']); self.pump()

    def test_project_icon_buttons_are_compact_rail_controls(self):
        """REQ-UI-SIDEBAR-1：常驻轨上只剩单个「项目」主图标；四个原入口收进
        二级列，同为纯图标 RailIcon 钮，配 Tooltip。"""
        self.resize(942, 1032)
        d = self.desktop
        self.assertEqual(d.project_button.cget('style'), 'RailIcon.TButton')
        self.assertEqual(str(d.project_button.cget('compound')), 'image')
        self.assertTrue(d.project_button.cget('image'))
        self.assertGreaterEqual(d.project_button.winfo_height(),
                                d.project_button.winfo_reqheight())
        if getattr(d, '_sidebar_expand_kind', None) != 'project':
            d.project_button.invoke(); self.pump()
        try:
            for button in d.project_buttons:
                self.assertEqual(button.cget('style'), 'RailIcon.TButton')
            for state, button in d.project_group_buttons.items():
                # 当前组是 Selected.RailIcon.TButton，其余组是 RailIcon.TButton。
                self.assertIn(button.cget('style'),
                              ('RailIcon.TButton', 'Selected.RailIcon.TButton'))
            for button in (*d.project_buttons, *d.project_group_buttons.values()):
                self.assertEqual(str(button.cget('compound')), 'image')
                self.assertTrue(button.cget('image'))
                self.assertGreaterEqual(button.winfo_height(), button.winfo_reqheight())
        finally:
            if getattr(d, '_sidebar_expand_kind', None) == 'project':
                d.project_button.invoke(); self.pump()

    def test_actions_hint_and_full_file_details(self):
        self.resize(800, 600)
        d = self.desktop
        # R2923：动作栏与静态占位提示删除；发送/附件/语音/模型/技能图标收进共享输入框。
        self.assertFalse(hasattr(d, 'idea_row'), '动作栏容器已随 R2923 删除')
        self.assertFalse(hasattr(d, 'recon_button'), '「采风」按钮已随 R2923 删除')
        self.assertFalse(hasattr(d, 'idea_input_hint'), '静态占位提示已随 R2923 删除')
        self.assertTrue(d.shared_input.winfo_ismapped(), '共享输入框可见')
        # R2942：四类文件合成一条「项目文件」列表，每个文件一行提示。
        # R2946：侧栏项目区＝分组筛选图标＋新建/打开；
        # 「●」当前标记与组筛选状态都走 _picker_items。
        # REQ-UI-SIDEBAR-1：分组二级图标改为切换列表过滤（再点回「全部」），不再各弹选择层。
        self.assertEqual(d._project_group, 'making')
        self.assertTrue(any(Path(p['path']) == d.root for p in d._picker_items), '当前项目应在在制作组里')
        making_paths = sorted(p['path'] for p in d.projects.info['projects']
                              if p.get('status', 'making') == 'making')
        self.assertEqual(sorted(p['path'] for p in d._picker_items), making_paths)
        if getattr(d, '_sidebar_expand_kind', None) != 'project':
            d.project_button.invoke(); self.pump()
        try:
            d.project_group_buttons['completed'].invoke()
            self.assertEqual(d._project_group, 'completed')
            self.assertEqual(d.project_group_buttons['completed'].cget('style'), 'Selected.RailIcon.TButton')
            self.assertEqual(d.project_group_buttons['making'].cget('style'), 'RailIcon.TButton')
            completed_paths = sorted(p['path'] for p in d.projects.info['projects']
                                     if p.get('status', 'making') == 'completed')
            self.assertEqual(sorted(p['path'] for p in d._picker_items), completed_paths)
            d.project_group_buttons['making'].invoke()
            self.assertEqual(d._project_group, 'making')
            self.assertEqual(sorted(p['path'] for p in d._picker_items), making_paths)
            # 再点当前分组回到「全部」：状态点此时区分在制作／已完成。
            d.project_group_buttons['making'].invoke()
            self.assertEqual(d._project_group, 'all')
            all_paths = sorted(p['path'] for p in d.projects.info['projects'])
            self.assertEqual(sorted(p['path'] for p in d._picker_items), all_paths)
        finally:
            if getattr(d, '_sidebar_expand_kind', None) == 'project':
                d.project_button.invoke(); self.pump()
        # 选择层真开一次：浮层里有「●」标当前项目的行，点外部即关。
        # REQ-UI-SIDEBAR-1：分组钮收在二级列里，开层前先展开二级列让锚点可见。
        d.set_project_group('making', popup=True); self.pump()
        top = getattr(d, '_sidebar_popup_win', None)
        self.assertIsNotNone(top, '点分组图标要弹出项目选择层')
        labels = []
        def collect(widget):
            for child in widget.winfo_children():
                if isinstance(child, tk.Label):labels.append(str(child.cget('text')))
                collect(child)
        collect(top)
        self.assertTrue(any(t.startswith('● ') for t in labels), '选择层里当前项目带 ● 标记')
        d._close_sidebar_popup(); self.pump()
        self.assertIsNone(getattr(d, '_sidebar_popup_win', None), '点外部后选择层收起')
        if getattr(d, '_sidebar_expand_kind', None) == 'project':
            d.project_button.invoke(); self.pump()   # REQ-UI-SIDEBAR-1：收起项目二级列
        # R2962：文件栏迁为右侧停靠面板，默认隐藏；断言列表内容前先打开并等渐进批次。
        expected_categories = {'setting', 'outline', 'character', 'script'}
        d.files_panel.open_panel()
        deadline = time.monotonic() + 3.0
        categories = set()
        while time.monotonic() < deadline:
            self.pump(.05)
            categories = {d.script_row_category[item] for item in d.files_panel.all_script_items()}
            if expected_categories <= categories:
                break
        self.assertEqual(categories, expected_categories, '四类文件都出现在同一条列表里')
        tree = d.script_tree
        self.assertTrue(tree.get_children())
        self.assertEqual(str(tree.heading('#0', 'anchor')), 'center')
        self.assertEqual(str(tree.heading('name', 'anchor')), 'center')
        files = d.files_panel.all_script_items()
        self.assertTrue(files)
        for item in files:
            with self.subTest(item=item):
                details = d.script_file_tips.text_for(item)
                path = Path(item) if Path(item).is_absolute() else Path(d.root) / item
                self.assertIn(path.name, details)
                expected = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(path.stat().st_mtime))
                self.assertIn(expected, details)

    def test_sidebar_popup_clamps_to_anchor_monitor(self):
        """R2950：主窗在副屏时选择层钳位取锚点所在显示器，不被主屏宽度拽回主屏。"""
        self.resize(942, 1032)
        d = self.desktop
        # 把窗口挪到副屏坐标系（隐藏测试桌面坐标是虚拟的，直接给几何即可）。
        self.win.geometry('+2500+80'); self.pump()
        # REQ-UI-SIDEBAR-1：分组钮收在二级列里，选择层统一锚在常驻的「项目」主图标上。
        try:
            with mock.patch('desktop_page_nav.monitor_bounds', return_value=(1920, 0, 3840, 1080)):
                d.set_project_group('making', popup=True); self.pump()
                top = getattr(d, '_sidebar_popup_win', None)
                self.assertIsNotNone(top, '点分组图标要弹出项目选择层')
                anchor = d.project_button
                self.assertTrue(anchor.winfo_ismapped(), '锚点须在侧栏里可见')
                self.assertGreaterEqual(anchor.winfo_rootx(), 1920)
                self.assertGreaterEqual(top.winfo_rootx(), 1920,
                                        '副屏上的选择层不得被钳回主屏（旧代码按主屏宽度钳位）')
                self.assertAlmostEqual(top.winfo_rootx(), anchor.winfo_rootx(), delta=2,
                                       msg='选择层应贴在锚点正下方')
        finally:
            d._close_sidebar_popup(); self.pump()


class SidebarExpandColumnTests(unittest.TestCase):
    """REQ-UI-SIDEBAR-1：侧栏项目入口合并、二级图标列与项目名称列表（UX-SIDEBAR-PROJECT）。

    隐藏桌面真 Tk：项目主图标展开/收起二级列、二级图标驱动分组与原动作、
    项目名称列表的过滤/高亮/切换/高度钳制、资产管理的二级图标列、
    以及右侧文件图标列与侧栏共用 ExpandIconColumn 部件。
    """

    @classmethod
    def setUpClass(cls):
        cls.win = tk_test_support.make_root()
        cls.temp = tempfile.TemporaryDirectory()
        app, cls.project = startup_fixtures.DesktopStartupPerfTests._startup_app(
            cls.temp.name, remembered=True)
        cls.desktop = Desktop(cls.win, root=app)
        cls.pump(0.2, idle_first=True)

    @classmethod
    def pump(cls, seconds=0.05, idle_first=False):
        tk_test_support.pump(cls.win, seconds, idle_first=idle_first)

    def setUp(self):
        # invoke 是开关式：每条用例进来前保证二级列处于收起态，断言才确定。
        d = self.desktop
        if getattr(d, '_sidebar_expand_kind', None) == 'project':
            d.project_button.invoke()
            self.pump()

    @classmethod
    def tearDownClass(cls):
        try:
            startup_fixtures.cancel_timers(cls.desktop)
        except Exception:
            pass
        try:
            cls.win.destroy()
        except Exception:
            pass
        cls.temp.cleanup()

    def test_project_button_expands_and_collapses_secondary_column(self):
        d = self.desktop
        column = getattr(d, '_project_expand_column', None)
        self.assertIsNotNone(column, '缺少项目二级图标列（REQ-UI-SIDEBAR-1）')
        frame = column.frame
        # 初始收起：列不占位；记住聊天区左缘与宽度，展开／收起都不许挤占聊天区。
        self.assertFalse(frame.winfo_ismapped())
        body_x, body_w = d.body.winfo_rootx(), d.body.winfo_width()
        # 展开：四个项目二级图标在项目区内部 2×2 展开，与项目列表框同宽，不挤占聊天区。
        d.project_button.invoke()
        self.pump()
        self.assertTrue(frame.winfo_ismapped())
        self.assertGreaterEqual(
            frame.winfo_rootx(), d.project_block.winfo_rootx() - 1)
        self.assertLessEqual(
            frame.winfo_rootx() + frame.winfo_width(),
            d.project_block.winfo_rootx() + d.project_block.winfo_width() + 1)
        self.assertLessEqual(
            frame.winfo_rootx() + frame.winfo_width(), d.body.winfo_rootx() + 1)
        self.assertEqual((d.body.winfo_rootx(), d.body.winfo_width()),
                         (body_x, body_w), '展开项目二级图标不得挤占右侧聊天框')
        # 四个原项目入口都在二级列里
        for key in ('making', 'completed'):
            self.assertIn(key, d.project_group_buttons)
        for button in (d.project_new_button, d.project_open_button):
            self.assertTrue(button.winfo_ismapped())
        # 键盘可达：二级列每颗钮可 Tab 聚焦、绑上下键与 Enter。
        # 伪造键盘事件在本仓库不可靠（见 test_final_viewer 第 56 期注记），
        # 这里断言绑定与 takefocus 真实存在，触发路径由各自动作测试覆盖。
        rail_buttons = [*d.project_group_buttons.values(),
                        d.project_new_button, d.project_open_button]
        for button in rail_buttons:
            self.assertTrue(button.bind('<Up>'), '二级图标缺少上键绑定')
            self.assertTrue(button.bind('<Down>'), '二级图标缺少下键绑定')
            self.assertTrue(button.bind('<Return>'), '二级图标缺少 Enter 绑定')
            self.assertTrue(int(button.cget('takefocus') or 0),
                            '二级图标不可 Tab 聚焦')
        # 再点主图标收起
        d.project_button.invoke()
        self.pump()
        self.assertFalse(frame.winfo_ismapped())
        # 点空白收起
        d.project_button.invoke()
        self.pump()
        d.body.event_generate('<Button-1>', x=4, y=4)
        self.pump()
        self.assertFalse(frame.winfo_ismapped())
        # Esc 收起（隐藏桌面上后建的 Tk 根无焦点，按键事件只经焦点窗口投递，
        # 先 focus_force 再合成，与 test_hover_card_states 同一惯例）
        d.project_button.invoke()
        self.pump()
        self.win.focus_force()
        self.win.event_generate('<Escape>')
        self.pump()
        self.assertFalse(frame.winfo_ismapped())

    def test_secondary_icons_drive_group_filter_and_original_actions(self):
        d = self.desktop
        d.project_button.invoke()
        self.pump()
        # 在制作 → 已完成 → 全部 → 在制作
        d.project_group_buttons['completed'].invoke()
        self.pump()
        self.assertEqual(d._project_group, 'completed')
        self.assertEqual(d.project_group_buttons['completed'].cget('style'),
                         'Selected.RailIcon.TButton')
        self.assertEqual(d.project_group_buttons['making'].cget('style'),
                         'RailIcon.TButton')
        d.project_group_buttons['completed'].invoke()
        self.pump()
        self.assertEqual(d._project_group, 'all')
        d.project_group_buttons['making'].invoke()
        self.pump()
        self.assertEqual(d._project_group, 'making')
        # 新建／打开目录复用原动作，动作后收起二级列
        with mock.patch.object(d, 'new') as m_new, \
                mock.patch.object(d, 'open_current_project') as m_open:
            d.project_new_button.invoke()
            m_new.assert_called_once_with()
            self.assertFalse(d._project_expand_column.frame.winfo_ismapped())
            d.project_button.invoke()
            self.pump()
            d.project_open_button.invoke()
            m_open.assert_called_once_with()

    def test_project_name_list_rows_filter_highlight_and_pick(self):
        d = self.desktop
        lst = getattr(d, 'project_name_list', None)
        self.assertIsNotNone(lst, '缺少项目切换胶囊（REQ-UI-SIDEBAR-1）')
        self.pump()
        # 窄侧栏显示当前项目名胶囊与分组计数；不再保留搜索框与项目管理按钮。
        self.assertFalse(hasattr(lst, 'search'), '侧栏项目区不再保留筛选输入框')
        self.assertFalse(hasattr(lst, 'manage'), '侧栏项目区不再保留项目管理按钮')
        self.assertIn('▸', str(lst.count_label.cget('text')))
        body_x, body_w = d.body.winfo_rootx(), d.body.winfo_width()
        card = lst.open_card()
        self.pump()
        try:
            self.assertIsNotNone(card, '悬停／点击胶囊应弹出宽项目卡片')
            self.assertGreaterEqual(card.winfo_width(), 280, '项目卡片应够宽以完整展示中文项目名')
            self.assertGreaterEqual(card.winfo_rootx(),
                                    d.sidebar_area.winfo_rootx() + d.sidebar_area.winfo_width() - 1)
            self.assertEqual((d.body.winfo_rootx(), d.body.winfo_width()),
                             (body_x, body_w), '弹出项目卡片不得挤占右侧聊天框')
            tree = lst.table.tree
            rows = tree.get_children()
            expected = len(getattr(d, '_picker_items', []))
            self.assertEqual(len(rows), expected)
            for iid in rows:
                vals = tree.item(iid, 'values')
                self.assertRegex(str(vals[0]), r'^[●○] ')
            current = [i for i in rows if 'current' in tree.item(i, 'tags')]
            if getattr(d, 'root', None) is not None:
                self.assertTrue(current, '当前项目没有高亮行')
                self.assertEqual(Path(current[0]), Path(d.root))
            # 键盘：Enter 触发切换，走 request_project_switch
            self.assertTrue(tree.bind('<Return>'), '项目行缺少 Enter 绑定')
            fake = {'name': '键盘切换目标',
                    'path': str(d.root.parent / '键盘切换目标_x')}
            d.projects.info['projects'].append(fake)
            try:
                d._sync_project_picker()
                self.pump()
                targets = [i for i in tree.get_children()
                           if Path(i) != Path(getattr(d, 'root', '') or '')]
                self.assertTrue(targets, '补登记后应有可切换的非当前项目行')
                tree.selection_set(targets[0])
                with mock.patch.object(d, 'request_project_switch') as m_switch:
                    lst._activate_selected()
                    self.pump()
                    m_switch.assert_called_once_with(targets[0])
                self.assertIsNone(lst._card_win, '选择项目后宽项目卡片自动收起')
            finally:
                d.projects.info['projects'].remove(fake)
                d._sync_project_picker()
                self.pump()
        finally:
            lst.close_card()
            self.pump()

    def test_project_list_height_clamps_and_three_widths_fit(self):
        d = self.desktop
        lst = getattr(d, 'project_name_list', None)
        self.assertIsNotNone(lst)
        for width, height in ((942, 1032), (800, 600), (990, 632)):
            self.win.geometry('%dx%d+100+100' % (width, height))
            self.pump()
            self.assertLessEqual(d.project_block.winfo_width(),
                                 d.sidebar_area.winfo_width() + 1)
            self.assertLessEqual(lst.trigger.winfo_width(),
                                 d.project_block.winfo_width() + 1)
        # 一级主图标放大并相对侧栏居中，二级图标更小且靠右展开
        sb_left = d.sidebar_area.winfo_rootx()
        self.assertGreaterEqual(d.project_button.winfo_rootx() - sb_left, 16,
                                '一级主图标应相对侧栏左缘居中')
        d.project_button.invoke()
        self.pump()
        try:
            self.assertGreater(d.project_button.winfo_width(),
                               d.project_new_button.winfo_width(),
                               '一级主图标应大于二级图标')
            expand_frame = d._project_expand_column.frame
            self.assertGreaterEqual(
                expand_frame.winfo_rootx() + expand_frame.winfo_width(),
                d.project_button.winfo_rootx() + d.project_button.winfo_width(),
                '项目二级图标应相对主图标靠右')
        finally:
            d.project_button.invoke()
            self.pump()
        self.win.geometry('942x1032+100+100')
        self.pump()

    def test_assets_nav_opens_secondary_icon_column(self):
        d = self.desktop
        d.show(PAGE['assets'])
        self.pump()
        d.nav[PAGE['assets']].invoke()
        self.pump()
        top = getattr(d, '_sidebar_popup_win', None)
        self.assertIsNotNone(top, '点资产管理要在右侧展开二级图标列')
        buttons = [w for w in widget_list(top, (ttk.Button, tk.Button))
                   if str(w.cget('text')) == '资产清单']
        self.assertEqual(len(buttons), 1, '二级列里只有「资产清单」一项')
        self.assertEqual(getattr(buttons[0], '_rail_icon_name', ''), 'asset_list')
        # 一级图标靠左，二级图标紧贴其右且落在侧栏／项目列表框宽度内，不占聊天区。
        anchor = d.nav[PAGE['assets']]
        self.assertGreaterEqual(
            top.winfo_rootx(),
            anchor.winfo_rootx() + anchor.winfo_width() - 1)
        self.assertLessEqual(
            top.winfo_rootx() + top.winfo_width(),
            d.sidebar_area.winfo_rootx() + d.sidebar_area.winfo_width() + 1)
        self.assertLessEqual(
            top.winfo_rootx() + top.winfo_width(), d.body.winfo_rootx() + 1,
            '资产二级图标不得占用右侧聊天框空间')
        # 再点图标收起并回资产管理主页
        d.nav[PAGE['assets']].invoke()
        self.pump()
        self.assertIsNone(getattr(d, '_sidebar_popup_win', None))
        # 展开后点「资产清单」走原 open_asset_roster 动作
        d.nav[PAGE['assets']].invoke()
        self.pump()
        top = getattr(d, '_sidebar_popup_win', None)
        self.assertIsNotNone(top)
        buttons = [w for w in widget_list(top, (ttk.Button, tk.Button))
                   if str(w.cget('text')) == '资产清单']
        self.assertEqual(len(buttons), 1)
        with mock.patch.object(d, 'open_asset_roster') as m_roster:
            buttons[0].invoke()
            self.pump()
            m_roster.assert_called_once_with()
        self.assertIsNotNone(getattr(d, '_asset_popup_win', None),
                             '点选「资产清单」不再顺手收起入口；只能再点资产管理收起')
        d.nav[PAGE['assets']].invoke()
        self.pump()
        self.assertIsNone(getattr(d, '_asset_popup_win', None))

    def test_asset_roster_flyout_stays_open_across_pages_until_assets_clicked(self):
        """界面单卡第 10 项：资产清单入口跨页保留，外部点击／Esc／换页都不收，只有再点资产管理收起。"""
        d = self.desktop
        d.show(PAGE['assets'])
        self.pump()
        d.nav[PAGE['assets']].invoke()
        self.pump()
        top = getattr(d, '_asset_popup_win', None)
        self.assertIsNotNone(top, '点资产管理要展开资产清单入口')
        # Esc 与主窗内其他位置点击都不再关闭这层；它要作为跨页排查入口保留。
        self.win.event_generate('<Escape>')
        self.pump()
        self.assertIs(getattr(d, '_asset_popup_win', None), top)
        d.body.event_generate('<Button-1>', x=8, y=8)
        self.pump()
        self.assertIs(getattr(d, '_asset_popup_win', None), top)
        # 换页也不收：用户可以从任意页直接点进资产清单。
        d.show(PAGE['script'])
        self.pump()
        self.assertIs(getattr(d, '_asset_popup_win', None), top)
        self.assertTrue(top.winfo_exists())
        # 只有再次点击「资产管理」主图标才收起。
        d.nav[PAGE['assets']].invoke()
        self.pump()
        self.assertIsNone(getattr(d, '_asset_popup_win', None))
        self.assertFalse(top.winfo_exists())

    def test_files_panel_stage_rail_shares_expand_column(self):
        """右侧文件图标列与侧栏二级列共用 ExpandIconColumn 部件。"""
        from ui.desktop_expand_column import ExpandIconColumn
        d = self.desktop
        panel = getattr(d, 'files_panel', None)
        self.assertIsNotNone(panel)
        column = getattr(panel, '_rail_column', None)
        self.assertIsInstance(column, ExpandIconColumn,
                              '右侧图标列没有复用 ExpandIconColumn')
        for stage, button in getattr(panel, 'stage_buttons', {}).items():
            self.assertTrue(getattr(button, '_rail_icon_name', ''),
                            '阶段图标缺少 _rail_icon_name: %s' % stage)
        self.assertEqual(getattr(panel, 'library_button', None) is not None
                         and panel.library_button._rail_icon_name,
                         'library')
        self.assertEqual(getattr(panel, 'recycle_button', None) is not None
                         and panel.recycle_button._rail_icon_name,
                         'recycle')


class EntryDialogLayoutTests(unittest.TestCase):
    """REQ-UI-L5-1：应用入口弹窗统一单列布局——说明文本＋一个强调色主按钮＋文字式次按钮。

    启动自检致命提示与安全模式二选一都走 ``desktop_launcher.entry_dialog``；
    主按钮判「是」，次按钮／Esc／关闭判「否」。
    """

    @classmethod
    def setUpClass(cls):
        cls.win = tk_test_support.make_root()

    @classmethod
    def tearDownClass(cls):
        cls.win.destroy()

    def _buttons(self):
        tops = [w for w in self.win.winfo_children()
                if isinstance(w, tk.Toplevel) and w.winfo_exists()]
        self.assertTrue(tops, '入口弹窗没有建出来')
        return [w for w in widget_list(tops[0]) if isinstance(w, ttk.Button)]

    def _invoke_later(self, text):
        def click():
            for button in self._buttons():
                if str(button.cget('text')) == text:
                    button.invoke()
                    return
        self.win.after(30, click)

    def test_entry_dialog_primary_returns_true(self):
        import desktop_launcher
        self._invoke_later('安全启动')
        result = desktop_launcher.entry_dialog(
            self.win, '应用入口', '说明第一行。\n说明第二行。',
            primary='安全启动', secondary='正常启动')
        self.assertTrue(result, '点强调色主按钮应判「是」')

    def test_entry_dialog_layout_contract(self):
        import desktop_launcher
        seen = {}
        def peek():
            buttons = self._buttons()
            for button in buttons:
                seen[str(button.cget('text'))] = str(button.cget('style'))
            self.assertEqual(len(buttons), 2, '提示窗只留一个主按钮与一个次要入口')
            for button in buttons:
                if str(button.cget('text')) == '正常启动':
                    button.invoke()
                    return
        self.win.after(30, peek)
        result = desktop_launcher.entry_dialog(
            self.win, '应用入口', '说明。', primary='安全启动', secondary='正常启动')
        self.assertFalse(result, '点文字式次按钮应判「否」')
        self.assertEqual(seen.get('安全启动'), 'Tokens.Primary.TButton')
        self.assertEqual(seen.get('正常启动'), 'Tokens.Text.TButton',
                         '次要入口用 Tokens.Text.TButton 文字样式')

    def test_safe_start_ask_returns_yes_result_code(self):
        """``desktop_launcher.entry_confirm`` 供 startup_gate 注入：确认按 Win32 IDYES 语义返回。"""
        import desktop_launcher
        import infra.diagnostic_capture as diagnostic_capture
        self._invoke_later('安全启动')
        code = desktop_launcher.entry_confirm('说明文本', '应用入口', 0, parent=self.win)
        self.assertEqual(code, getattr(diagnostic_capture, '_IDYES', 6))


if __name__ == '__main__':unittest.main()
