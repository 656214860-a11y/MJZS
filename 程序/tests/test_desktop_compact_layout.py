"""R1446：真实 Tk 双尺寸布局；临时项目不接触用户登记或配置。"""
import tempfile
import time
import unittest
from pathlib import Path
import tkinter as tk
from tkinter import ttk, font

from app_metadata import APP_NAME
from desktop import Desktop
from skip_reasons import PLATFORM_TK_DISPLAY
import test_desktop_startup_perf as startup_fixtures
import project_stages
from ui_tokens import DESKTOP_LAYOUT, SPACING
from ui_widgets import SecondaryButton


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

    def test_header_sidebar_and_file_area_remain_visible_after_shrink_and_grow(self):
        d = self.desktop
        for width, height in ((942, 1032), (800, 600), (942, 1032)):
            with self.subTest(size=(width, height)):
                self.resize(width, height)
                self.assertEqual(d.app_title.cget('text'), APP_NAME)
                self.assertAlmostEqual(d.idea_log.winfo_rooty(), d.list.winfo_rooty(), delta=2)
                self.assertLess(d.title.winfo_rooty(), d.app_title.winfo_rooty() + d.app_title.winfo_height())
                self.assertGreater(d.title.winfo_rootx(), d.canvas.winfo_rootx())
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
                    self.assertLessEqual(previous_bottom, self.win.winfo_rooty()+height)
                    self.assertGreaterEqual(widget.winfo_height(), widget.winfo_reqheight())
                self.assertLessEqual(d.script_box.winfo_rooty()+d.script_box.winfo_height(), d.canvas.winfo_rooty()+d.canvas.winfo_height()+2)
                self.assertLessEqual(d.content.winfo_height(), d.canvas.winfo_height()+2)

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

    def test_project_buttons_are_half_the_previous_layout_height(self):
        self.resize(942, 1032)
        d = self.desktop
        # 重建改动前的网格分配规则，用同一 Tk 字体/DPI 测旧按钮实际高度，
        # 不把截图的 45px 硬写成跨机器标准。
        old = ttk.Frame(self.win, padding=DESKTOP_LAYOUT['sidebar_padding'])
        old.place(x=0, y=0, width=d.sidebar.winfo_width(), height=d.sidebar.winfo_height())
        old.grid_propagate(False)
        old.columnconfigure(0, weight=1)
        old_buttons=[]
        try:
            for row, source in enumerate(d.sidebar.winfo_children()):
                if source is d.list:
                    item = ttk.Treeview(old, show='tree', height=3, style='Project.Treeview')
                    weight = 3
                elif source in d.project_buttons:
                    item = SecondaryButton(old, text=source.cget('text'), style='Compact.TButton')
                    old_buttons.append(item);weight=1
                else:
                    item = ttk.Frame(old, height=source.winfo_reqheight())
                    weight = 1 if source in d.nav else 0
                old.rowconfigure(row, weight=weight, minsize=SPACING['xs'] if isinstance(source, ttk.Separator) else 0)
                item.grid(row=row, column=0, sticky='nsew', pady=DESKTOP_LAYOUT['row_gap'])
            self.win.update_idletasks()
            for before, after in zip(old_buttons, d.project_buttons):
                self.assertAlmostEqual(after.winfo_height(), before.winfo_height()/2, delta=2)
        finally:old.destroy()

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
        for category, tree in d.script_trees.items():
            with self.subTest(category=category):
                self.assertTrue(tree.get_children())
                item = tree.get_children()[0]
                details = d.script_file_tips[category].text_for(item)
                self.assertIn(Path(item).name, details)
                expected = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(Path(item).stat().st_mtime))
                self.assertIn(expected, details)
                self.assertEqual(str(tree.heading('#0', 'anchor')), 'center')
                self.assertEqual(str(tree.heading('name', 'anchor')), 'center')


if __name__ == '__main__':unittest.main()
