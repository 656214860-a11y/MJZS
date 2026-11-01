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
OPTIONAL_LOCKS = {'reference_mode', 'splice_mode', 'style_base', 'style_directors'}
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
        import stage_config
        import workflow_settings
        if self.panel is not None:
            self.panel.destroy()
            self.panel = None
        self.win.deiconify()
        self.win.geometry('%dx%d' % (width, height))
        name = next(iter(workflow_settings.WORKFLOW_PRESETS))
        stage_config.put_workflow(self.root, {
            'name': name, 'lock': {name: {'aspect_ratio': '9:16'}}})
        self.panel = skill_panel.Panel(self.win, self.desktop, 'script',
                                       compact=False, scroll=True)
        self.panel.pack(fill='both', expand=True)
        if expand:
            self.panel.toggle_optional_locks()
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

    def _rows(self, fields):
        groups = []
        for field in sorted(fields, key=lambda item: (item.winfo_rooty(), item.winfo_rootx())):
            y = field.winfo_rooty()
            if groups and abs(y - groups[-1][0]) <= 2:
                groups[-1][1].append(field)
            else:
                groups.append([y, [field]])
        return [sorted(group, key=lambda item: item.winfo_rootx()) for _y, group in groups]

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
                    self.assertLessEqual(gap, slack + SPACING['md'] * 2,
                                         '%s 标签与下拉框相距 %dpx' % (label.cget('text'), gap))

    def test_lock_dropdowns_fill_ordered_rows(self):
        import script_contract
        wide_rows = None
        for name, width, height in SIZES:
            with self.subTest(size=name):
                panel = self._build(width, height, expand=True)
                keys = ['workflow'] + [
                    item['key'] for item in script_contract.PRODUCTION_LOCK_DEFINITIONS
                    if panel.lock_fields.field_visible(item['key'])]
                expected = [panel.workflow_box]
                expected.extend(panel.lock_inputs[key] for key in keys[1:])
                fields = [entry.master for entry in expected]
                # 按钮与提示也是锁流式布局的项，纳入「每行填满」与越界检查。
                layout_items = fields + [panel.more_locks_button, panel.lock_notice]
                self.assertEqual(expected,
                                 sorted(expected, key=lambda entry: (
                                     entry.master.winfo_rooty(), entry.master.winfo_rootx())),
                                 '总控与制作锁必须按定义顺序从左到右、从上到下排列')
                rows = self._rows(layout_items)
                container = panel.workflow_coordinator
                right = container.winfo_rootx() + container.winfo_width()
                for field in layout_items:
                    self.assertLessEqual(field.winfo_rootx() + field.winfo_width(), right + 1,
                                         '控件折行后仍越出配置区：%s' % field)
                # 契约变更（统一下拉框尺寸）：不再把行拉满，改为字段等宽、下拉框同宽。
                widths = {entry.winfo_width() for entry in expected}
                self.assertEqual(len(widths), 1, '下拉框宽度必须统一：%s' % sorted(widths))
                # 契约变更（R1982）：标签列按列收窄——同列字段等宽、上下对齐，
                # 各列标签区只取本列最宽标签，短标签列的下拉框左移，不再留大片空白。
                lock_fields = set(fields)
                columns, widths_by_column, labels_by_column = {}, {}, {}
                for row in rows:
                    if row[0] not in lock_fields:
                        continue  # 以按钮/提示开头的行（展开选填锁后）不参与列对齐
                    # 契约变更（下拉框缩短 1/3）：1280 宽一行放得下 6 项，「更多制作锁」按钮与提示
                    # 落在行中间，其后字段的横向位置随提示宽度浮动；列对齐只比较行首连续的字段。
                    cells = []
                    for item in row:
                        if item not in lock_fields:
                            break
                        cells.append(item)
                    for index, item in enumerate(cells):
                        columns.setdefault(index, set()).add(item.winfo_rootx())
                        widths_by_column.setdefault(index, set()).add(item.winfo_width())
                        labels_by_column.setdefault(index, []).append(item)
                for index, xs in columns.items():
                    self.assertEqual(len(xs), 1, '第 %d 列没有上下对齐：%s' % (index + 1, sorted(xs)))
                    self.assertEqual(len(widths_by_column[index]), 1,
                                     '第 %d 列字段宽度不一致' % (index + 1))
                for index, items in labels_by_column.items():
                    if index == 0:
                        continue  # 第一列还要和预设／厂商等行对齐，另测
                    widest = max(item.winfo_children()[0].winfo_reqwidth() for item in items)
                    entry_x = min(item.winfo_children()[1].winfo_rootx() - item.winfo_rootx()
                                  for item in items)
                    self.assertLessEqual(entry_x, widest + STAGE_PANEL_LAYOUT['field_gap'] + 1,
                                         '第 %d 列标签区比本列最宽标签还宽' % (index + 1))
                if wide_rows is None:
                    wide_rows = len(rows)
                elif name == 'min':
                    self.assertGreater(len(rows), wide_rows, '窗口变窄后应增加行数而不是横向裁切')

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

    def test_existing_lock_workflow_and_skill_actions_still_work(self):
        import skill_panel
        import stage_config
        panel = self._build(1280, 800)
        self.assertIs(panel.workflow_box.master.master, panel.lock_fields)
        for key in OPTIONAL_LOCKS:
            self.assertFalse(panel.lock_fields.field_visible(key), key)
        panel.toggle_optional_locks()
        self._settle()
        for key in OPTIONAL_LOCKS:
            self.assertTrue(panel.lock_fields.field_visible(key), key)
        entry = panel.lock_inputs['aspect_ratio']
        entry.delete(0, 'end')
        entry.insert(0, '16:9')
        entry.event_generate('<FocusOut>')
        self._settle()
        self.assertEqual(stage_config.workflow_lock(self.root)['aspect_ratio'], '16:9')
        panel.toggle_optional_locks()
        self._settle()
        for key in OPTIONAL_LOCKS:
            self.assertFalse(panel.lock_fields.field_visible(key), key)
        panel.skill_action.set(skill_panel.MANAGE_ALL)
        with patch.object(panel, 'check_all_skills') as check_all:
            panel.choose_skill_action()
            check_all.assert_called_once_with(True)
        panel.workflow_choice.set(skill_panel.NO_MASTER)
        panel.choose_workflow()
        self.assertEqual(stage_config.current_workflow(self.root).get('name') or '', '')

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
        """R1982：第一列（预设／总控／厂商／SKILL）下拉框左缘对齐，标签区不按「视频模型版本」留宽。"""
        for name, width, height in SIZES:
            with self.subTest(size=name):
                panel = self._build(width, height)
                boxes = [panel.presets, panel.workflow_box, panel.providers, panel.skill_action_box]
                xs = {box.winfo_rootx() for box in boxes}
                self.assertLessEqual(max(xs) - min(xs), 1, '第一列下拉框没有左缘对齐：%s' % sorted(xs))
                from production_lock_fields import label_pixel_width
                long_px = label_pixel_width(panel, ['视频模型版本'], style='Muted.TLabel')
                short_px = label_pixel_width(panel, ['风格'], style='Muted.TLabel')
                offset = panel.presets.winfo_rootx() - panel.presets.master.winfo_rootx()
                if panel.lock_fields.column_px.get(0, 0) <= short_px:
                    self.assertLess(offset, long_px, '第一列标签区仍按最长标签留宽')

    def test_more_locks_button_sits_next_to_material_source(self):
        """更多制作锁按钮紧跟素材来源，成为制作锁流式布局里的一项。"""
        panel = self._build(1280, 800, expand=True)
        button = panel.more_locks_button
        source = panel.lock_inputs['material_source']
        self.assertLessEqual(abs(button.winfo_rooty() - source.winfo_rooty()), 2,
                             '更多制作锁按钮应与素材来源下拉框同一行')
        self.assertGreaterEqual(button.winfo_rootx(),
                                source.winfo_rootx() + source.winfo_width(),
                                '按钮应排在素材来源右侧')

    def test_skill_action_dropdown_width_fits_content_not_row(self):
        """SKILL 下拉框按内容定宽，不再撑满整行余宽。"""
        panel = self._build(1280, 800)
        box = panel.skill_action_box
        # 契约变更：全页下拉框统一宽度，与制作锁下拉框同宽，不再撑满整行。
        lock_width = panel.lock_inputs['aspect_ratio'].winfo_width()
        self.assertEqual(box.winfo_width(), lock_width, 'SKILL 下拉框应与其他下拉框同宽')

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
