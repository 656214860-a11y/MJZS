"""R1446：真实 Tk 双尺寸布局；临时项目不接触用户登记或配置。"""
import tempfile
import time
import unittest
from unittest import mock
import tk_test_support
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
                # R2897 图标轨：项目区之后依次是账号钮、14 个阶段钮与末尾设置钮。
                rail=[d.account_button,*d.nav,d.settings_rail_button]
                previous_bottom = d.project_block.winfo_rooty()+d.project_block.winfo_height()
                for widget in rail:
                    self.assertGreaterEqual(widget.winfo_rooty(), previous_bottom)
                    previous_bottom = widget.winfo_rooty()+widget.winfo_height()
                self.assertEqual(len(d.nav), 14, '14 个阶段按钮都要在侧栏里')
                canvas = d.sidebar_canvas
                rail_widgets=(*d.project_group_buttons.values(),
                              d.project_new_button,d.project_open_button,*rail)
                for widget in rail_widgets:
                    self.reveal(widget)
                    self.assertGreaterEqual(widget.winfo_rooty(), canvas.winfo_rooty()-1)
                    self.assertLessEqual(widget.winfo_rooty()+widget.winfo_height(),
                                         canvas.winfo_rooty()+canvas.winfo_height()+1)
                    self.assertGreaterEqual(widget.winfo_height(), widget.winfo_reqheight())
                # R2962：文件栏改右侧停靠面板（默认收起）；打开后底边仍不得越出内容区。
                d.files_panel.open_panel();self.pump(.05)
                self.assertTrue(d.files_panel._open,'有项目时入口允许打开文件面板')
                self.assertLessEqual(d.script_box.winfo_rooty()+d.script_box.winfo_height(), d.canvas.winfo_rooty()+d.canvas.winfo_height()+2)
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
        """R2897：新建/打开与分组筛选都是纯图标 RailIcon 钮，配 Tooltip，不再占整行文字。"""
        self.resize(942, 1032)
        d = self.desktop
        for button in d.project_buttons:
            self.assertEqual(button.cget('style'), 'RailIcon.TButton')
        for state, button in d.project_group_buttons.items():
            # 当前组是 Selected.RailIcon.TButton，其余组是 RailIcon.TButton。
            self.assertIn(button.cget('style'), ('RailIcon.TButton', 'Selected.RailIcon.TButton'))
        for button in (*d.project_buttons, *d.project_group_buttons.values()):
            self.assertEqual(str(button.cget('compound')), 'image')
            self.assertTrue(button.cget('image'))
            self.assertGreaterEqual(button.winfo_height(), button.winfo_reqheight())

    def test_actions_hint_and_full_file_details(self):
        self.resize(800, 600)
        d = self.desktop
        # R2923：动作栏与静态占位提示删除；发送/附件/语音/模型/技能图标收进共享输入框。
        self.assertFalse(hasattr(d, 'idea_row'), '动作栏容器已随 R2923 删除')
        self.assertFalse(hasattr(d, 'recon_button'), '「采风」按钮已随 R2923 删除')
        self.assertFalse(hasattr(d, 'idea_input_hint'), '静态占位提示已随 R2923 删除')
        self.assertTrue(d.shared_input.winfo_ismapped(), '共享输入框可见')
        # R2942：四类文件合成一条「项目文件」列表，每个文件一行提示。
        # R2946：侧栏项目区＝分组筛选图标（点了弹项目选择层）＋新建/打开；
        # 「●」当前标记与组筛选状态都走 _picker_items。
        self.assertEqual(d._project_group, 'making')
        self.assertTrue(any(Path(p['path']) == d.root for p in d._picker_items), '当前项目应在在制作组里')
        making_paths = sorted(p['path'] for p in d.projects.info['projects']
                              if p.get('status', 'making') == 'making')
        self.assertEqual(sorted(p['path'] for p in d._picker_items), making_paths)
        d.set_project_group('completed')
        self.assertEqual(d._project_group, 'completed')
        self.assertEqual(d.project_group_buttons['completed'].cget('style'), 'Selected.RailIcon.TButton')
        self.assertEqual(d.project_group_buttons['making'].cget('style'), 'RailIcon.TButton')
        completed_paths = sorted(p['path'] for p in d.projects.info['projects']
                                 if p.get('status', 'making') == 'completed')
        self.assertEqual(sorted(p['path'] for p in d._picker_items), completed_paths)
        # R2946：点分组图标＝切组＋弹出该组项目选择层；两组各弹各的列表。
        posted = []
        real_post = d._post_project_picker
        d._post_project_picker = lambda state=None: posted.append(d._project_group)
        try:
            d.project_group_buttons['making'].invoke()
            self.assertEqual(posted, ['making'], '点「在制作」图标要弹选择层')
            d.project_group_buttons['completed'].invoke()
            self.assertEqual(posted, ['making', 'completed'], '点「已完成」图标也要弹')
        finally:
            d._post_project_picker = real_post
        self.assertEqual(d._project_group, 'completed')
        # 选择层真开一次：浮层里有「●」标当前项目的行，点外部即关。
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
        # R2962：文件栏迁为右侧停靠面板，默认隐藏；断言列表内容前先打开并等渐进批次。
        d.files_panel.open_panel();self.pump(.4)
        self.assertEqual(set(d.script_row_category.values()), {'setting', 'outline', 'character', 'script'},
                         '四类文件都出现在同一条列表里')
        tree = d.script_tree
        self.assertTrue(tree.get_children())
        self.assertEqual(str(tree.heading('#0', 'anchor')), 'center')
        self.assertEqual(str(tree.heading('name', 'anchor')), 'center')
        for item in tree.get_children():
            with self.subTest(item=item):
                details = d.script_file_tips.text_for(item)
                self.assertIn(Path(item).name, details)
                expected = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(Path(item).stat().st_mtime))
                self.assertIn(expected, details)

    def test_sidebar_popup_clamps_to_anchor_monitor(self):
        """R2950：主窗在副屏时选择层钳位取锚点所在显示器，不被主屏宽度拽回主屏。"""
        self.resize(942, 1032)
        d = self.desktop
        # 把窗口挪到副屏坐标系（隐藏测试桌面坐标是虚拟的，直接给几何即可）。
        self.win.geometry('+2500+80'); self.pump()
        try:
            with mock.patch('desktop_page_nav.monitor_bounds', return_value=(1920, 0, 3840, 1080)):
                d.set_project_group('making', popup=True); self.pump()
                top = getattr(d, '_sidebar_popup_win', None)
                self.assertIsNotNone(top, '点分组图标要弹出项目选择层')
                anchor = d.project_group_buttons['making']
                self.assertGreaterEqual(anchor.winfo_rootx(), 1920)
                self.assertGreaterEqual(top.winfo_rootx(), 1920,
                                        '副屏上的选择层不得被钳回主屏（旧代码按主屏宽度钳位）')
                self.assertAlmostEqual(top.winfo_rootx(), anchor.winfo_rootx(), delta=2,
                                       msg='选择层应贴在锚点正下方')
        finally:
            d._close_sidebar_popup(); self.pump()


if __name__ == '__main__':unittest.main()
