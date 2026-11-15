"""SPLAYOUT 阶段配置页下拉框布局：标签贴近、按行填满、内容完整。"""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

try:
    import tkinter as tk
    from tkinter import font as tkfont
    from tkinter import ttk
except ImportError:  # pragma: no cover - 无 tkinter 的平台仍要能导入本模块
    tk = None
    tkfont = None
    ttk = None

try:
    from skip_reasons import PLATFORM_TKINTER
except ImportError:  # pragma: no cover - 测试路径已由 run_selftests 注入
    PLATFORM_TKINTER = "平台限制：当前环境没有可用 tkinter；安装可用 Tk 后应恢复执行"

from ui_tokens import SPACING, STAGE_PANEL_LAYOUT


ARROW_WIDTH = 32
SIZES = (('wide', 1280, 800), ('mid', 920, 615), ('min', 560, 430))


def _descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from _descendants(child)


def _values(entry):
    values = entry.cget('values')
    if isinstance(values, str):
        try:
            return tuple(entry.tk.splitlist(values))
        except tk.TclError:
            return (values,) if values else ()
    return tuple(values)


class DropdownLayoutTests(unittest.TestCase):
    def setUp(self):
        win = None
        if tk is not None:
            try:
                win = tk.Tk()
            except tk.TclError:
                win = None
        if win is None:
            self.skipTest(PLATFORM_TKINTER)
        self.win = win
        self.win.withdraw()
        self.addCleanup(self.win.destroy)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name) / 'project'
        app = Path(self.tmp.name) / 'program'
        root.mkdir()
        app.mkdir()
        self.root = root
        self.desktop = SimpleNamespace(win=self.win, root=root, app=app,
                                       status=tk.StringVar(master=self.win, value=''))
        self.panel = None

    def _build(self, width, height, *, expand=False):
        import skill_panel
        if self.panel is not None:
            self.panel.destroy()
            self.panel = None
        self.win.deiconify()
        self.win.geometry('%dx%d' % (width, height))
        # R2862：总控预设与内联制作锁已删；expand 参数保留仅为兼容旧调用点。
        self.panel = skill_panel.Panel(self.win, self.desktop, 'script',
                                       compact=False, scroll=True)
        self.panel.pack(fill='both', expand=True)
        self._settle()
        return self.panel

    def _settle(self):
        for _ in range(4):
            self.win.update_idletasks()
            self.win.update()

    def _font(self, widget):
        spec = widget.cget('font')
        if not spec:
            style = widget.cget('style') or 'TLabel'
            spec = ttk.Style(self.win).lookup(style, 'font')
        return tkfont.Font(root=self.win, font=spec or 'TkDefaultFont')

    def _labeled_pairs(self):
        pairs = []
        for parent in _descendants(self.panel):
            children = parent.winfo_children()
            for index, child in enumerate(children[:-1]):
                following = children[index + 1]
                if (isinstance(child, ttk.Label) and str(child.cget('text') or '').strip()
                        and isinstance(following, ttk.Combobox)):
                    pairs.append((child, following))
        return pairs

    def _gap(self, label, entry):
        text_right = label.winfo_rootx() + self._font(label).measure(label.cget('text'))
        return entry.winfo_rootx() - text_right

    def test_labels_sit_next_to_their_dropdowns(self):
        for name, width, height in SIZES:
            with self.subTest(size=name):
                self._build(width, height, expand=True)
                pairs = self._labeled_pairs()
                self.assertTrue(pairs, '没有找到任何「标签＋下拉框」对')
                # 标签列统一宽度（下拉框上下对齐）：空隙 = 本标签与最宽标签的差 + 一档间距。
                column = max(self._font(l).measure(l.cget('text')) for l, _e in pairs)
                for label, entry in pairs:
                    gap = self._gap(label, entry)
                    self.assertGreaterEqual(gap, -1,
                                            '%s 标签与下拉框重叠' % label.cget('text'))
                    slack = column - self._font(label).measure(label.cget('text'))
                    # +xs 容差：标签左缩进与边框各占数像素，属布局固有像素差。
                    self.assertLessEqual(gap, slack + SPACING['md'] * 2 + SPACING['xs'],
                                         '%s 标签与下拉框相距 %dpx' % (label.cget('text'), gap))

    def test_dropdowns_show_current_and_longest_option_at_all_sizes(self):
        for name, width, height in SIZES:
            with self.subTest(size=name):
                self._build(width, height, expand=True)
                entries = [widget for widget in _descendants(self.panel)
                           if isinstance(widget, ttk.Combobox)
                           and widget.winfo_ismapped() and widget.winfo_width() > 1]
                self.assertTrue(entries)
                for entry in entries:
                    # 契约变更：框体统一宽度；当前值若放不下，弹出列表须加宽到能显示最长选项。
                    entry._fit_popdown()
                    texts = list(_values(entry))
                    font = self._font(entry)
                    longest = max([font.measure(str(text)) for text in texts] or [0])
                    offset = ttk.Style(self.win).lookup(entry.cget('style'), 'postoffset') or '0 0 0 0'
                    extra = int(str(offset).split()[2])
                    self.assertGreaterEqual(entry.winfo_width() + extra, longest,
                                            '弹出列表放不下最长选项：%s' % entry)

    def test_skill_action_row_flows_checkboxes_without_overflow(self):
        for name, width, height in SIZES:
            with self.subTest(size=name):
                panel = self._build(width, height, expand=True)
                row = panel.skill_action_row
                right = row.winfo_rootx() + row.winfo_width()
                visible = [child for child in row.winfo_children()
                           if child.winfo_ismapped() and child.winfo_width() > 1]
                self.assertTrue(visible)
                for child in visible:
                    self.assertLessEqual(child.winfo_rootx() + child.winfo_width(), right + 1,
                                         '操作行子项越出右侧边界')

    def test_configuration_gives_height_back_to_skill_notes(self):
        panel = self._build(1280, 800)
        config_height = panel.form_body.winfo_height()
        notes_height = panel.note_list.master.winfo_height()
        # 契约变更（统一下拉框尺寸）：制作锁等宽后 1280 宽下排成两行，比旧版多一行（约 58px）；
        # 配置区允许比说明区高出这一行，说明区仍须保有可读高度。
        self.assertLess(config_height, notes_height + 80,
                        '配置区 %dpx 相比技能说明区 %dpx 过高' % (config_height, notes_height))
        self.assertGreater(notes_height, 200, '技能说明区没有拿回高度')

    def test_skill_actions_and_lock_entry_still_work(self):
        # R2862：总控选择与内联制作锁已删；面板保留 SKILL 批量操作与制作锁弹窗入口。
        import skill_panel
        panel = self._build(1280, 800)
        self.assertIsNotNone(panel.lock_button, '制作锁弹窗入口应存在')
        self.assertIsNotNone(panel.lock_hint)
        panel.skill_action.set(skill_panel.MANAGE_ALL)
        with patch.object(panel, 'check_all_skills') as check_all:
            panel.choose_skill_action()
            check_all.assert_called_once_with(True)
        window = panel.open_lock_dialog()
        self.assertIsNotNone(window, '制作锁弹窗应能打开')
        window.destroy()

    # ── SPTOKEN 裁决：最小窗口尺寸 + 布局参数令牌化 ──────────────────────────
    def _open_stage_config_window(self):
        import skill_panel
        self.win.deiconify()
        self.win.geometry('1200x800+0+0')
        self.win.update_idletasks()
        panel = skill_panel.open_for_page(self.desktop, 0)
        window = panel.winfo_toplevel()
        self.addCleanup(window.destroy)
        window.update_idletasks()
        return window

    def test_stage_config_window_minsize_equals_token(self):
        window = self._open_stage_config_window()
        min_width = STAGE_PANEL_LAYOUT['min_width']
        min_height = STAGE_PANEL_LAYOUT['min_height']
        if self.win.winfo_screenwidth() >= min_width and self.win.winfo_screenheight() >= min_height:
            self.assertEqual(window.minsize(), (min_width, min_height))

    def test_stage_config_window_cannot_shrink_below_token_minimum(self):
        window = self._open_stage_config_window()
        min_width = min(STAGE_PANEL_LAYOUT['min_width'], self.win.winfo_screenwidth())
        min_height = min(STAGE_PANEL_LAYOUT['min_height'], self.win.winfo_screenheight())
        window.geometry('400x300')
        window.update_idletasks()
        self.assertGreaterEqual(window.winfo_width(), min_width)
        self.assertGreaterEqual(window.winfo_height(), min_height)

    def test_sp_layout_spacing_comes_from_stage_panel_layout_token(self):
        import production_lock_fields
        import skill_panel
        flow = production_lock_fields.FlowFields(self.win)
        self.addCleanup(flow.destroy)
        self.assertEqual(flow.gap, STAGE_PANEL_LAYOUT['field_gap'])
        self.assertEqual(flow.row_gap, STAGE_PANEL_LAYOUT['row_gap'])
        label = production_lock_fields.CompactLabel(self.win, text='预设')
        self.addCleanup(label.destroy)
        self.assertEqual(int(label.cget('width')), STAGE_PANEL_LAYOUT['label_width'])
        # 静态检查：布局模块的间距来源指向新令牌，不再临时挑 SPACING 档位。
        for module in (skill_panel, production_lock_fields):
            source = Path(module.__file__).read_text(encoding='utf-8')
            self.assertIn('STAGE_PANEL_LAYOUT', source,
                          '%s 未引用 STAGE_PANEL_LAYOUT 令牌' % module.__name__)


    def test_first_column_dropdowns_align_and_hug_short_labels(self):
        """R2862 后面板只剩 SKILL 操作下拉：标签与下拉框相邻、宽度走令牌。"""
        for name, width, height in SIZES:
            with self.subTest(size=name):
                panel = self._build(width, height)
                box = panel.skill_action_box
                self.assertEqual(int(box.cget('width')),
                                 STAGE_PANEL_LAYOUT['select_width'])
                label = panel.flow_skill_label
                gap = self._gap(label, box)
                self.assertGreaterEqual(gap, -1, 'SKILL 标签与下拉框重叠')
                self.assertLessEqual(gap, SPACING['md'] * 2 + SPACING['xs'],
                                     'SKILL 标签与下拉框相距 %dpx' % gap)

    def test_skill_action_dropdown_width_fits_content_not_row(self):
        """SKILL 下拉框按令牌定宽，不撑满整行余宽。"""
        panel = self._build(1280, 800)
        box = panel.skill_action_box
        self.assertEqual(int(box.cget('width')), STAGE_PANEL_LAYOUT['select_width'])
        row_width = panel.skill_action_row.winfo_width()
        self.assertLess(box.winfo_width(), row_width,
                        'SKILL 下拉框不应撑满整行')

    def test_first_checkbox_sits_next_to_skill_dropdown(self):
        """第一个 SKILL 勾选框与下拉框同一行，位于其右侧。"""
        panel = self._build(1280, 800)
        box = panel.skill_action_box
        boxes = list(panel.registered_boxes.values())
        self.assertTrue(boxes, '脚本阶段应至少有一个注册 SKILL 勾选框')
        first = boxes[0]
        self.assertLessEqual(abs(first.winfo_rooty() - box.winfo_rooty()), 2,
                             '第一个勾选框应与 SKILL 下拉框同一行')
        self.assertGreaterEqual(first.winfo_rootx(),
                                box.winfo_rootx() + box.winfo_width(),
                                '勾选框应排在下拉框右侧')

    def test_checkboxes_stay_within_container_at_min_size(self):
        """最小窗口档下所有勾选框都在容器内，不被横向截断。"""
        panel = self._build(560, 430)
        container = panel.skill_action_row
        right = container.winfo_rootx() + container.winfo_width()
        for name, box in panel.registered_boxes.items():
            self.assertLessEqual(box.winfo_rootx() + box.winfo_width(), right + 1,
                                 '窄窗下勾选框被截断：%s' % name)


if __name__ == '__main__':
    unittest.main()
