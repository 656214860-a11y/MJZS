# -*- coding: utf-8 -*-
"""自动列宽测量缓存回归：窗口缩放/每次刷新不再重复量同一批文字，且列宽结果不变。运行：python test_column_fit.py"""
from skip_reasons import (
    MISSING_NODE,
    PLATFORM_DIRECTORY_LINK,
    PLATFORM_TKINTER,
    PLATFORM_TK_DISPLAY,
    PLATFORM_WORKING_SET,
    REQUIRES_BUNDLED_SKILL,
)
import os, sys, unittest
from unittest import mock
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); os.chdir(HERE)


class FakeFont:
    def __init__(self, name, width):
        self.name = name
        self.width = width
        self.calls = 0

    def measure(self, text):
        self.calls += 1
        return self.width


class SqueezeFloorTests(unittest.TestCase):
    """第 26 期第 2 条：每列至少放得下自己的表头。"""

    def setUp(self):
        import responsive_ui
        self.ui = responsive_ui

    def test_a_handwritten_narrow_column_is_lifted_to_its_floor(self):
        out = self.ui.squeeze([130, 90, 360], 2000, [64, 120, 132])
        self.assertEqual(out, [130, 120, 360], '手写死的 90 比下限 120 还窄，要抬到放得下表头')

    def test_the_wide_columns_pay_for_the_lift(self):
        out = self.ui.squeeze([130, 90, 360], 400, [64, 120, 132])
        for width, floor in zip(out, [64, 120, 132]):
            self.assertGreaterEqual(width, floor, '每一列都不许低于自己的下限：%r' % (out,))

    def test_nothing_changes_when_it_already_fits(self):
        self.assertEqual(self.ui.squeeze([130, 140, 360], 2000, [64, 96, 132]), [130, 140, 360])


class FillColumnsTests(unittest.TestCase):
    """第 53 期第 4 条：内容框变宽时怎么把余量分给每一列（分镜定稿那张表就靠它）。

    用户报的是「列宽不跟着界面大小变、内容显示不全」：光靠最后一列 stretch，前三列会一直
    卡在量出来的宽度上。fill_columns 把整个内容框铺满，四列一起动。
    """

    def setUp(self):
        import responsive_ui
        self.ui = responsive_ui

    def test_room_to_spare_is_shared_by_every_column(self):
        widths = [200, 80, 100, 240]
        out = self.ui.fill_columns(widths, widths, [56, 56, 56, 56], 800)
        self.assertEqual(sum(out), 800, "正好铺满内容框，右边不留空白带")
        for before, after in zip(widths, out):
            self.assertGreater(after, before, "内容和内容框都放得下时，余量按比例分给每一列")

    def test_a_clipped_column_is_filled_before_the_spare_is_shared(self):
        out = self.ui.fill_columns([360, 80, 100, 240], [600, 80, 100, 240], [56, 56, 56, 56], 800)
        self.assertEqual(sum(out), 800)
        self.assertGreaterEqual(out[0], 360, "被裁掉的那一列先把内容补回来（长分镜名不再被裁）")
        self.assertLessEqual(out[0], 600, "最多补到内容宽度为止，不白占")

    def test_too_narrow_falls_back_to_squeeze(self):
        widths = [200, 80, 100, 240]
        self.assertEqual(self.ui.fill_columns(widths, widths, [56, 56, 56, 56], 200),
                         self.ui.squeeze(widths, 200, [56, 56, 56, 56]),
                         "装不下就按比例缩、缩到下限钉住——与 squeeze 同一条规矩")

    def test_floors_are_never_undershot(self):
        out = self.ui.fill_columns([200, 80, 100, 240], [200, 80, 100, 240], [90, 90, 90, 90], 700)
        for width, floor in zip(out, [90, 90, 90, 90]):
            self.assertGreaterEqual(width, floor, "每一列都不许低于自己的下限")

    def test_no_room_leaves_the_widths_alone(self):
        self.assertEqual(self.ui.fill_columns([200, 80], [200, 80], [56, 56], 0), [200, 80])


class MeasureCacheTests(unittest.TestCase):
    def setUp(self):
        import responsive_ui
        self.ui = responsive_ui
        responsive_ui._measure_cache.clear()

    def test_measure_reuses_result_for_same_font_and_text(self):
        font = FakeFont('fake-font-a', 42)
        self.assertEqual(self.ui.measure(font, "镜头001"), 42)
        self.assertEqual(self.ui.measure(font, "镜头001"), 42)
        self.assertEqual(font.calls, 1)

    def test_measure_separates_fonts_and_texts(self):
        first = FakeFont('fake-font-b', 10)
        second = FakeFont('fake-font-c', 20)
        self.assertEqual(self.ui.measure(first, "x"), 10)
        self.assertEqual(self.ui.measure(second, "x"), 20)
        self.assertEqual(self.ui.measure(first, "y"), 10)
        self.assertEqual((first.calls, second.calls), (2, 1))


class ColumnFitTests(unittest.TestCase):
    def setUp(self):
        try:
            import tkinter as tk
        except Exception:
            self.skipTest(PLATFORM_TKINTER)
        from tkinter import ttk
        import responsive_ui, storyboard_files
        self.ui, self.sf = responsive_ui, storyboard_files
        self.win = tk.Tk(); self.win.withdraw()
        self.addCleanup(self.win.destroy)
        self.tree = ttk.Treeview(self.win,
                                 columns=("file", "status", "content", "time", "location"),
                                 show="tree headings")
        for column in self.tree["columns"]:
            self.tree.heading(column, text=column)
        for i in range(6):
            self.tree.insert("", "end", iid="r%d" % i, text="",
                             values=("EP00%d_分镜.json" % i, "已采用", "第%d集 · 测试 · 60镜" % i,
                                     "09-19 23:0%d" % (i % 10), "storyboard/分镜拆分/EP0.json"))
        self.win.update_idletasks()
        self.ui._measure_cache.clear()

    def test_fill_fit_second_pass_measures_nothing_new(self):
        """第 53 期第 4 条：fill=True 那一支也走同一份测量缓存，第二次一个都不重量。"""
        self.sf.fit_final_columns(self.tree)
        widths = [self.tree.column(column, 'width') for column in self.tree['columns']]
        cached = len(self.ui._measure_cache)
        self.assertGreater(cached, 0)
        self.sf.fit_final_columns(self.tree)
        self.assertEqual(len(self.ui._measure_cache), cached)
        self.assertEqual([self.tree.column(column, 'width') for column in self.tree['columns']], widths)

    def test_fill_is_remembered_for_the_next_resize(self):
        """下一轮 <Configure> 重排走的是记下来的那一份参数——fill 得一起记，不然一缩回就丢。"""
        self.sf.fit_final_columns(self.tree)
        self.assertEqual(self.tree._view_fit_args[0], {'file': self.tree._view_fit_args[0]['file']})
        self.assertTrue(self.tree._view_fit_args[2], 'fill=True 要记在树上')

    def test_second_fit_measures_nothing_new_and_keeps_widths(self):
        self.sf.fit_file_columns(self.tree)
        widths = [self.tree.column(column, 'width') for column in self.tree['columns']]
        cached = len(self.ui._measure_cache)
        self.assertGreater(cached, 0)
        self.sf.fit_file_columns(self.tree)
        self.assertEqual(len(self.ui._measure_cache), cached)   # 第二次全部命中缓存
        self.assertEqual([self.tree.column(column, 'width') for column in self.tree['columns']], widths)

    def test_unchanged_columns_are_not_reconfigured(self):
        """列宽没变化时不再写回同一列：重复写同一列会让整张表重新排版。"""
        self.sf.fit_file_columns(self.tree)
        with mock.patch.object(self.tree, 'column', wraps=self.tree.column) as spy:
            self.sf.fit_file_columns(self.tree)
            writes = [call for call in spy.call_args_list if call.kwargs]
        self.assertEqual(writes, [], "第二次自动列宽不该再配置任何列")

    def test_changed_column_is_reconfigured(self):
        self.sf.fit_file_columns(self.tree)
        self.tree.column('file', width=999)
        self.sf.fit_file_columns(self.tree)
        self.assertNotEqual(int(self.tree.column('file', 'width')), 999)

    def test_configure_column_sets_every_option_when_one_changes(self):
        self.ui.configure_column(self.tree, 'file', 130, minwidth=100, stretch=False, anchor='center')
        self.assertEqual(int(self.tree.column('file', 'width')), 130)
        self.assertEqual(int(self.tree.column('file', 'minwidth')), 100)
        self.assertEqual(int(self.tree.column('file', 'stretch')), 0)
        self.assertEqual(str(self.tree.column('file', 'anchor')), 'center')
        self.ui.configure_column(self.tree, 'file', 130, minwidth=100, stretch=False, anchor='w')
        self.assertEqual(str(self.tree.column('file', 'anchor')), 'w')
        self.assertEqual(int(self.tree.column('file', 'width')), 130)

    def test_cached_fonts_reuse_objects_until_style_changes(self):
        from tkinter import ttk
        body, heading = self.ui.cached_fonts(self.tree)
        self.assertIs(self.ui.cached_fonts(self.tree)[0], body)
        ttk.Style(self.tree).configure('Treeview', font=('Microsoft YaHei UI', 15))
        self.addCleanup(ttk.Style(self.tree).configure, 'Treeview', font=('Microsoft YaHei UI', 10))
        self.assertIsNot(self.ui.cached_fonts(self.tree)[0], body)


if __name__ == "__main__":
    unittest.main()
