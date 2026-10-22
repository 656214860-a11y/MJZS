"""R1446：真实 Tk 双尺寸布局；临时项目不接触用户登记或配置。"""
import tempfile
import time
import unittest
from pathlib import Path
import tkinter as tk
from tkinter import ttk, font

from app_metadata import APP_NAME
from desktop import Desktop, PAGE
from skip_reasons import PLATFORM_TK_DISPLAY
import test_desktop_startup_perf as startup_fixtures
import project_stages
from ui_tokens import CONTROL_HEIGHT, DESKTOP_LAYOUT


class CompactDesktopGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:cls.win = tk.Tk()
        except tk.TclError as exc:raise unittest.SkipTest(PLATFORM_TK_DISPLAY + ': ' + str(exc))
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
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            cls.win.update()
            time.sleep(.005)

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
                self.assertEqual(d.app_title.cget('text'), APP_NAME)
                self.assertAlmostEqual(d.idea_log.winfo_rooty(), d.list.winfo_rooty(), delta=2)
                self.assertLess(d.title.winfo_rooty(), d.app_title.winfo_rooty() + d.app_title.winfo_height())
                self.assertAlmostEqual(d.title.winfo_rootx(), d.idea_log.winfo_rootx(), delta=2)
                gear, title = d.pet.gear.canvas, d.app_title
                self.assertAlmostEqual(gear.winfo_rooty()+gear.winfo_height()/2, title.winfo_rooty()+title.winfo_reqheight()/2, delta=2)
                self.assertAlmostEqual(gear.winfo_rootx(), title.winfo_rootx()+title.winfo_reqwidth()+DESKTOP_LAYOUT['gear_gap'], delta=2)
                row_height = int(ttk.Style(self.win).lookup('Project.Treeview', 'rowheight'))
                rows = int(d.list.cget('height'))
                chrome = d.list.winfo_reqheight() - rows * row_height
                self.assertGreaterEqual(rows, DESKTOP_LAYOUT['project_min_rows'])
                self.assertEqual(rows, (d.list.winfo_height()-chrome)//row_height)
                previous_bottom = d.list.winfo_rooty()+d.list.winfo_height()
                for widget in (*d.project_buttons, *d.nav):
                    self.assertGreaterEqual(widget.winfo_rooty(), previous_bottom)
                    previous_bottom = widget.winfo_rooty()+widget.winfo_height()
                self.assertEqual(len(d.nav), 14, '14 个阶段按钮都要在侧栏里')
                canvas = d.sidebar_canvas
                for widget in (*d.project_buttons, *d.nav):
                    self.reveal(widget)
                    self.assertGreaterEqual(widget.winfo_rooty(), canvas.winfo_rooty()-1)
                    self.assertLessEqual(widget.winfo_rooty()+widget.winfo_height(),
                                         canvas.winfo_rooty()+canvas.winfo_height()+1)
                    self.assertGreaterEqual(widget.winfo_height(), widget.winfo_reqheight())
                self.assertLessEqual(d.script_box.winfo_rooty()+d.script_box.winfo_height(), d.canvas.winfo_rooty()+d.canvas.winfo_height()+2)
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
                        self.assertAlmostEqual(d.title.winfo_rootx(), anchor.winfo_rootx(), delta=2)
                        self.assertEqual(d.header_slogan.cget('text'), '✦  把灵感变成故事')
                        self.assertLessEqual(d.project_label.winfo_rooty()-(d.app_title.winfo_rooty()+d.app_title.winfo_height()), DESKTOP_LAYOUT['project_label_gap'])
                        pets = (d.pet.canvas, d.pet.paws, d.pet.caption)
                        for pet in pets:
                            self.assertTrue(pet.winfo_ismapped())
                            self.assertGreaterEqual(rect(pet)[0], rect(d.body)[0])
                            self.assertGreaterEqual(rect(pet)[1], rect(d.body)[1])
                            self.assertLessEqual(rect(pet)[2], rect(d.body)[2])
                            self.assertLessEqual(rect(pet)[3], rect(d.body)[3])
                            self.assertLessEqual(rect(pet)[3], rect(d.pet_layer)[3])
                        if d.header_slogan.winfo_ismapped():
                            self.assertAlmostEqual(d.header_slogan.winfo_rooty()+d.header_slogan.winfo_height()/2, d.title.winfo_rooty()+d.title.winfo_height()/2, delta=2)
                            self.assertGreaterEqual(rect(d.header_slogan)[0], rect(d.title)[2])
                            for pet in pets:separate(d.header_slogan, pet)
                        else:
                            available=min(rect(p)[0] for p in pets)-rect(d.title)[2]
                            self.assertLess(available, d.header_slogan.winfo_reqwidth()+2*DESKTOP_LAYOUT['slogan_gap'])
                        if stage == 'script':
                            self.assertAlmostEqual(d.idea_log.winfo_rooty(), d.list.winfo_rooty(), delta=2)
                            for pet in pets:separate(d.idea_log, pet)
        finally:
            d.show(PAGE['script']); self.pump()

    def test_project_tree_tracks_visible_rows_and_leaves_space_below_navigation(self):
        self.resize(942, 1032)
        d = self.desktop
        tree = d.list
        tree.delete(*tree.get_children())
        tree.insert('', 'end', iid='test-group', text='项目', open=True)
        for i in range(5):tree.insert('test-group', 'end', iid=f'test-{i}', text=str(i))
        d.schedule_sidebar_fit(); self.pump()
        self.assertEqual(int(tree.cget('height')), 6)
        self.assertAlmostEqual(tree.winfo_height(), tree.winfo_reqheight(), delta=2)
        self.assertLessEqual(d.project_buttons[0].winfo_rooty()-(tree.winfo_rooty()+tree.winfo_height()), 2*DESKTOP_LAYOUT['row_gap']+2)
        tree.item('test-group', open=False)
        tree.event_generate('<<TreeviewClose>>'); self.pump()
        self.assertEqual(int(tree.cget('height')), 3)
        tree.item('test-group', open=True)
        tree.event_generate('<<TreeviewOpen>>'); self.pump()
        self.assertEqual(int(tree.cget('height')), 6)
        tree.delete('test-0', 'test-1')
        d.schedule_sidebar_fit(); self.pump()
        self.assertEqual(int(tree.cget('height')), 4)

    def control_height(self):
        """用 setup_styles 配好的默认按钮量全局控件高度，不写死像素。"""
        reference = ttk.Button(self.win, text='控件高度', style='TButton')
        self.win.update_idletasks()
        height = reference.winfo_reqheight()
        reference.destroy()
        return height

    def test_project_buttons_match_global_control_height(self):
        self.resize(942, 1032)
        d = self.desktop
        expected = self.control_height()
        self.assertAlmostEqual(expected, CONTROL_HEIGHT, delta=2)
        for button in d.project_buttons:
            self.assertAlmostEqual(button.winfo_height(), expected, delta=2)
            self.assertGreaterEqual(button.winfo_height(), button.winfo_reqheight())

    def test_actions_hint_and_full_file_details(self):
        self.resize(800, 600)
        d = self.desktop
        for button in d.idea_row.winfo_children():
            if 'text' not in button.keys():continue
            style = ttk.Style(button)
            font_spec = style.lookup(button.cget('style') or 'TButton', 'font')
            self.assertGreaterEqual(button.winfo_width(), font.Font(root=button, font=font_spec).measure(button.cget('text')))
            self.assertLessEqual(button.winfo_rootx()+button.winfo_width(), d.idea_row.winfo_rootx()+d.idea_row.winfo_width())
        self.assertEqual(d.idea_input_hint.place_info()['anchor'], 'w')
        self.assertAlmostEqual(d.idea_input_hint.winfo_rootx(),
                               d.idea_input.winfo_rootx() + d.idea_input.bbox('1.0')[0],
                               delta=2)
        self.assertFalse(d.list.item('group:completed', 'open'))
        self.assertIn('empty-group', d.list.item('group:completed', 'tags'))
        d.list.item('group:completed', open=True)
        self.assertTrue(d.list.item('group:completed', 'open'))
        tree = d.script_tree  # R1776：四类文件合并为一张表，行提示按行取
        self.assertTrue(tree.get_children())
        self.assertEqual(str(tree.heading('#0', 'anchor')), 'center')
        self.assertEqual(str(tree.heading('name', 'anchor')), 'center')
        self.assertEqual(set(d.script_row_category.values()), {'setting', 'outline', 'character', 'script'},
                         '四类文件都出现在同一张表里')
        for item in tree.get_children():
            with self.subTest(item=item):
                details = d.script_file_tips.text_for(item)
                self.assertIn(Path(item).name, details)
                expected = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(Path(item).stat().st_mtime))
                self.assertIn(expected, details)


if __name__ == '__main__':unittest.main()
