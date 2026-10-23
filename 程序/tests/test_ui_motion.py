"""微交互组件契约：行悬停淡入、加载转圈、空态提示（ui_motion）及其在 DataTable/BusyState 的接线。"""
import tkinter as tk
import unittest
from tkinter import ttk
from types import SimpleNamespace

import ui_motion
from skip_reasons import PLATFORM_TK_DISPLAY
from desktop_project_pages import ProjectPagesMixin
from ui_tokens import (COLORS, DESKTOP_LAYOUT, EMPTY_ICON_SIZE, ROW_HOVER_STEPS, ROW_HOVER_TAG,
                       SPACING, SPINNER_SIZE)
from ui_widgets import BusyState, DataTable, setup_styles


class MotionBase(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(PLATFORM_TK_DISPLAY)
        self.root.withdraw()
        setup_styles(self.root)

    def tearDown(self):
        if hasattr(self, 'root'):
            self.root.destroy()

    def pump(self, rounds=12, delay_ms=20):
        for _ in range(rounds):
            self.root.update()
            self.root.after(delay_ms)
            self.root.update()


class BlendTests(unittest.TestCase):
    def test_blend_endpoints_and_midpoint(self):
        self.assertEqual(ui_motion.blend('#000000', '#ffffff', 0), '#000000')
        self.assertEqual(ui_motion.blend('#000000', '#ffffff', 1), '#ffffff')
        self.assertEqual(ui_motion.blend('#000000', '#ffffff', 0.5), '#808080')


class RowHoverTests(MotionBase):
    def make_tree(self):
        frame = ttk.Frame(self.root)
        frame.pack(fill='both', expand=True)
        tree = ttk.Treeview(frame, show='tree', height=4)
        tree.pack(fill='both', expand=True)
        for name in ('a', 'b', 'c'):
            tree.insert('', 'end', iid=name, text=name, tags=('keep',))
        self.root.deiconify()
        self.root.update()
        return tree

    def move_to(self, tree, row):
        # 直接投递指针位置：真实鼠标可能正好停在测试窗口上，会让 event_generate 结果不稳。
        x, y, w, h = tree.bbox(row)
        tree._row_hover._moved(SimpleNamespace(x=x + 4, y=y + h // 2))

    def test_hover_adds_tag_fades_to_hover_surface_and_keeps_other_tags(self):
        tree = self.make_tree()
        ui_motion.bind_row_hover(tree)
        self.move_to(tree, 'b')
        self.assertEqual(tree.item('b', 'tags'), ('keep', ROW_HOVER_TAG))
        self.pump(ROW_HOVER_STEPS * 3)
        self.assertEqual(str(tree.tag_configure(ROW_HOVER_TAG, 'background')).lower(),
                         COLORS['surface_hover'].lower())

    def test_hover_moves_between_rows_and_clears_on_leave(self):
        tree = self.make_tree()
        ui_motion.bind_row_hover(tree)
        self.move_to(tree, 'a')
        self.move_to(tree, 'c')
        self.assertEqual(tree.item('a', 'tags'), ('keep',))
        self.assertIn(ROW_HOVER_TAG, tree.item('c', 'tags'))
        tree._row_hover._left()
        self.assertEqual(tree.item('c', 'tags'), ('keep',))

    def test_selected_row_is_not_tagged_and_selection_clears_hover(self):
        tree = self.make_tree()
        ui_motion.bind_row_hover(tree)
        tree.selection_set('a')
        self.root.update()
        self.move_to(tree, 'a')
        self.assertEqual(tree.item('a', 'tags'), ('keep',))
        self.move_to(tree, 'b')
        tree.selection_set('b')
        self.root.update()
        self.assertEqual(tree.item('b', 'tags'), ('keep',))

    def test_bind_is_idempotent(self):
        tree = self.make_tree()
        self.assertIs(ui_motion.bind_row_hover(tree), ui_motion.bind_row_hover(tree))

    def test_rows_deleted_while_hovered_do_not_raise(self):
        tree = self.make_tree()
        ui_motion.bind_row_hover(tree)
        self.move_to(tree, 'b')
        tree.delete('b')
        tree._row_hover._left()
        self.assertEqual(tree._row_hover.row, "")
        self.assertEqual(tree.get_children(), ('a', 'c'))

    def test_data_table_installs_hover_automatically(self):
        table = DataTable(self.root, columns=[('name', '名称', 120)])
        table.pack()
        self.assertIsNotNone(getattr(table.tree, '_row_hover', None))


class SpinnerTests(MotionBase):
    def test_spinner_rotates_and_stops(self):
        spinner = ui_motion.Spinner(self.root)
        spinner.pack()
        self.assertEqual(int(spinner.cget('width')), SPINNER_SIZE)
        self.assertFalse(spinner.running)
        spinner.start()
        first = spinner.itemcget('arc', 'start')
        self.pump(6)
        self.assertTrue(spinner.running)
        self.assertNotEqual(spinner.itemcget('arc', 'start'), first)
        spinner.stop()
        self.assertFalse(spinner.running)
        frozen = spinner.itemcget('arc', 'start')
        self.pump(4)
        self.assertEqual(spinner.itemcget('arc', 'start'), frozen)

    def test_hosted_spinner_appears_only_while_busy_and_matches_host_background(self):
        host = ttk.Label(self.root, text='状态', style='PaleGreenHint.TLabel')
        host.pack(fill='x')
        spinner = ui_motion.Spinner(self.root, host=host)
        status = tk.StringVar()
        busy = BusyState(status, spinner=spinner)
        self.root.update()
        self.assertEqual(spinner.winfo_manager(), '')
        busy.set_busy(True, message='处理中')
        self.root.update()
        self.assertEqual(spinner.winfo_manager(), 'place')
        self.assertTrue(spinner.running)
        self.assertEqual(spinner.cget('bg'),
                         ttk.Style(self.root).lookup('PaleGreenHint.TLabel', 'background'))
        busy.set_busy(False)
        self.root.update()
        self.assertEqual(spinner.winfo_manager(), '')
        self.assertFalse(spinner.running)

    def test_destroying_spinner_cancels_animation(self):
        spinner = ui_motion.Spinner(self.root)
        spinner.pack()
        spinner.start()
        job = spinner._job
        self.assertIsNotNone(job)
        errors = []
        self.root.report_callback_exception = lambda *info: errors.append(info[1])
        spinner.destroy()
        self.pump(3)  # 已销毁后不得再有定时器抛 TclError
        self.assertFalse(spinner.running)
        self.assertNotIn(job, self.root.tk.splitlist(self.root.tk.call('after', 'info')))
        self.assertEqual(errors, [])


class EmptyStateTests(MotionBase):
    def test_icon_is_cached_on_root_and_does_not_pollute_base(self):
        first = ui_motion.empty_icon(self.root)
        self.assertIs(first, ui_motion.empty_icon(self.root))
        self.assertEqual(first.width(), first.height())
        self.assertGreaterEqual(first.width(), EMPTY_ICON_SIZE)

    def test_empty_state_shows_icon_above_text_and_hides(self):
        host = ttk.Frame(self.root, width=300, height=200)
        host.pack()
        state = ui_motion.EmptyState(host, '还没有内容')
        state.show(True)
        self.root.update()
        self.assertEqual(str(state.label.cget('compound')), 'top')
        self.assertTrue(str(state.label.cget('image')))
        self.assertEqual(state.winfo_manager(), 'place')
        state.show(False)
        self.assertEqual(state.winfo_manager(), '')

    def test_data_table_empty_label_has_icon_and_keeps_contract(self):
        table = DataTable(self.root, columns=[('name', '名称', 120)], empty_text='暂无项目')
        table.pack(fill='both', expand=True)
        self.root.update()
        self.assertEqual(table.empty_label.cget('text'), '暂无项目')
        self.assertEqual(str(table.empty_label.cget('compound')), 'top')
        self.assertTrue(str(table.empty_label.cget('image')))

    def test_project_list_overlay_follows_whether_any_project_exists(self):
        frame = ttk.Frame(self.root)
        frame.pack(fill='both', expand=True)
        tree = ttk.Treeview(frame, show='tree')
        tree.pack(fill='both', expand=True)
        tree._empty_state = ui_motion.EmptyState(frame, '空', anchor_widget=tree)
        host = SimpleNamespace(projects=SimpleNamespace(info={'projects': []}),
                               project_row_text=lambda p: p['name'])
        ProjectPagesMixin.fill_projects(host, tree)
        self.assertEqual(tree._empty_state.winfo_manager(), 'place')
        host.projects.info['projects'] = [{'name': 'x', 'path': 'C:/nowhere/x', 'status': 'making'}]
        ProjectPagesMixin.fill_projects(host, tree)
        self.assertEqual(tree._empty_state.winfo_manager(), '')


class BreathingRoomTokenTests(unittest.TestCase):
    def test_new_layout_gaps_come_from_the_4px_scale(self):
        for key in ('nav_gap', 'section_gap', 'sidebar_padding'):
            self.assertIn(DESKTOP_LAYOUT[key], SPACING.values(), key)
        for value in DESKTOP_LAYOUT['body_padding'] + tuple(DESKTOP_LAYOUT['status_gap']):
            self.assertIn(value, SPACING.values())
        self.assertGreater(DESKTOP_LAYOUT['body_padding'][0], 14)


if __name__ == '__main__':
    unittest.main()
