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
                for label, entry in pairs:
                    gap = self._gap(label, entry)
                    self.assertGreaterEqual(gap, -1,
                                            '%s 标签与下拉框重叠' % label.cget('text'))
                    self.assertLessEqual(gap, SPACING['md'],
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
                self.assertEqual(expected,
                                 sorted(expected, key=lambda entry: (
                                     entry.master.winfo_rooty(), entry.master.winfo_rootx())),
                                 '总控与制作锁必须按定义顺序从左到右、从上到下排列')
                rows = self._rows(fields)
                container = panel.workflow_coordinator
                right = container.winfo_rootx() + container.winfo_width()
                for field in fields:
                    self.assertLessEqual(field.winfo_rootx() + field.winfo_width(), right + 1,
                                         '控件折行后仍越出配置区：%s' % field)
                for row in rows[:-1]:
                    row_right = max(field.winfo_rootx() + field.winfo_width() for field in row)
                    self.assertGreaterEqual(row_right, right - SPACING['md'],
                                            '第 %d 行没有填满' % (rows.index(row) + 1))
                    self.assertLessEqual(row_right, right + 1)
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
                    texts = list(_values(entry))
                    current = entry.get()
                    if current:
                        texts.append(current)
                    font = self._font(entry)
                    needed = max([font.measure(str(text)) for text in texts] or [0]) + ARROW_WIDTH
                    self.assertGreaterEqual(entry.winfo_width(), needed,
                                            '下拉框内容被裁：%s 需要 %dpx，实际 %dpx'
                                            % (entry, needed, entry.winfo_width()))

    def test_skill_action_row_has_no_right_blank(self):
        for name, width, height in SIZES:
            with self.subTest(size=name):
                panel = self._build(width, height, expand=True)
                row = panel.skill_action_row
                right = row.winfo_rootx() + row.winfo_width()
                visible = [child for child in row.winfo_children()
                           if child.winfo_ismapped() and child.winfo_width() > 1]
                self.assertTrue(visible)
                row_right = max(child.winfo_rootx() + child.winfo_width() for child in visible)
                self.assertLessEqual(row_right, right + 1)
                self.assertGreaterEqual(row_right, right - SPACING['md'],
                                        'SKILL 操作行右侧仍留空白 %dpx' % (right - row_right))

    def test_configuration_gives_height_back_to_skill_notes(self):
        panel = self._build(1280, 800)
        config_height = panel.form_body.winfo_height()
        notes_height = panel.note_list.master.winfo_height()
        self.assertLess(config_height, notes_height,
                        '配置区 %dpx 应比技能说明区 %dpx 矮' % (config_height, notes_height))
        self.assertGreater(notes_height, 380, '技能说明区没有拿回高度')

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


if __name__ == '__main__':
    unittest.main()
