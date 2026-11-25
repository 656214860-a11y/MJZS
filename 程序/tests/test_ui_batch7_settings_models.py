"""UI 批次 7：设置窗与模型窗——表单列对齐、保存／取消位置、最小尺寸动作区、错误不锁屏。

全部用真 Tk 根窗口量几何；项目根是 ``tempfile`` 空目录，不打开、不读取任何用户项目，
也不读 ``private/`` 或真实密钥。
"""
import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk
from types import SimpleNamespace
from unittest import mock

import infra.model_pool as model_pool
import pet_models_ui
import pet_settings_ui
from skip_reasons import PLATFORM_TKINTER, PLATFORM_WINDOWS_ONLY
from ui_tokens import COLORS


def _descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from _descendants(child)


def _buttons(widget):
    return [child for child in _descendants(widget)
            if child.winfo_class() in ('TButton', 'Button')]


def _button(widget, text):
    for button in _buttons(widget):
        if str(button.cget('text')) == text and button.winfo_ismapped():
            return button
    raise AssertionError('找不到可见按钮：%s' % text)


class _Best(SimpleNamespace):
    ok = True
    label = '自动'
    reason = ''


class FakePet:
    """只回答设置页会问的问题；不写盘、不发请求、不打开用户项目。"""

    def __init__(self, win, program):
        self.win = win
        self.program = Path(program)
        self.codex_home = Path(program)
        self.project = None
        self.agent = None
        self.notice = ''
        self.anim = True
        self.autostart = False
        self.snooze = '免打扰（10 分钟）'
        self.level_value = 'semi'
        self.token = {}
        self.limits = {'tokens': 2000000, 'image': 200, 'firstframe': 200,
                       'video': 100, 'voice': 100}
        self.tasks = {key: value for key, value in model_pool.TASKS_DEFAULT.items()}

    # 基础功能
    def pet_settings(self):
        return {'name': '三虎', 'anim': self.anim, 'dnd': (22, 7), 'autostart': self.autostart}

    def set_anim(self, value):
        self.anim = bool(value)
        return self.anim

    def set_dnd(self, start, end):
        if not 0 <= start <= 23 or not 0 <= end <= 23 or start == end:
            return None
        self.dnd = (start, end)
        return self.dnd

    def snooze_label(self):
        return self.snooze

    def toggle_snooze(self):
        return self.snooze

    def set_autostart(self, value):
        self.autostart = bool(value)
        return self.autostart

    def autostart_label(self):
        return '开机自启（测试）'

    # 自动化等级
    def level(self, _payload=None):
        return self.level_value

    def set_level(self, value):
        self.level_value = value
        return value

    def set_paw_level(self, value):
        return self.set_level(value)

    # 模型配置
    def agent_model_records(self):
        return {}

    def agent_model_tasks(self):
        return dict(self.tasks)

    def resolve_agent_model(self, _key, records=None):
        self.resolved_with_records = getattr(self, 'resolved_with_records', []) + [records]
        return _Best()

    def save_agent_models(self, _chosen):
        return True

    def open_model_manager(self):
        return None

    # 预算
    def budget_limits(self):
        return dict(self.limits)

    def budget_usage(self):
        return {'used': {}}

    def save_budget_limits(self, values):
        saved = {}
        for kind, text in values.items():
            if str(text).strip():
                number = int(text)
                if number <= 0:
                    raise ValueError('预算要填正整数。')
                saved[kind] = number
            else:
                saved[kind] = self.limits[kind]
        self.limits = saved
        return saved

    # Token 节省
    def token_settings(self):
        return dict(self.token)

    def set_token_settings(self, table):
        self.token = dict(table)
        return table

    # 模型管理
    def confirm_start(self, _title, _text):
        return True

    def save_pool(self, _item, _previous=''):
        return True

    def delete_pool_model(self, _model_id):
        return True


class Batch7Case(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except Exception:
            self.skipTest(PLATFORM_TKINTER)
        self.root.withdraw()
        self.addCleanup(lambda: self.root.winfo_exists() and self.root.destroy())
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pet = FakePet(self.root, self.tmp.name)

    def _show(self, window, geometry=None):
        self.root.deiconify()
        self.root.update()
        window.transient(self.root)
        if geometry:
            window.geometry(geometry)
        window.deiconify()
        window.update()
        self.addCleanup(lambda: window.winfo_exists() and window.destroy())
        return window

    def _settings_window(self):
        scanner = mock.patch('pet_settings_ui.token_saver.scan', return_value={})
        scanner.start()
        self.addCleanup(scanner.stop)
        return self._show(pet_models_ui.open_settings(self.pet))

    def _manager_window(self):
        return self._show(pet_models_ui.open_manager(self.pet))

    def _hub(self, tab='basic'):
        scanner = mock.patch('pet_settings_ui.token_saver.scan', return_value={})
        scanner.start()
        self.addCleanup(scanner.stop)
        return self._show(pet_settings_ui.open_hub(self.pet, tab))


class ActionAreaTests(Batch7Case):
    def test_model_settings_save_is_right_of_close(self):
        win = self._settings_window()
        save, close = _button(win, '保存'), _button(win, '关闭')
        self.assertGreater(save.winfo_rootx(), close.winfo_rootx(),
                           '保存必须在关闭右边')
        self.assertEqual(str(save.cget('style')), 'Tokens.Primary.TButton')
        self.assertEqual(str(close.cget('style')), 'Tokens.Secondary.TButton')

    def test_model_settings_page_reads_the_pool_once_for_options_and_statuses(self):
        """三虎模型配置首绘只取一次模型池快照；四个自动状态不再各自重读并重规范化。"""
        records = {}
        calls = []
        def load_records():
            calls.append('read')
            return records
        self.pet.agent_model_records = load_records
        self._settings_window()
        self.assertEqual(calls, ['read'], '模型设置页构建时只能读一次模型池')
        self.assertEqual(getattr(self.pet, 'resolved_with_records', []), [records],
                         '「自动」状态解析必须复用同一份快照')

    def test_model_manager_save_is_rightmost_primary_with_cancel_beside_it(self):
        # UX-MODEL-PAGE 契约变更：底行右对齐 [取消][保存]，保存＝写入并关闭；不再有独立「关闭」。
        win = self._manager_window()
        cancel, save = _button(win, '取消'), _button(win, '保存')
        self.assertGreater(save.winfo_rootx(), cancel.winfo_rootx(),
                           '保存必须在取消右边')
        self.assertEqual(str(save.cget('style')), 'Tokens.Primary.TButton')
        self.assertFalse([b for b in _buttons(win) if str(b.cget('text')) == '关闭'],
                         '不再有独立「关闭」按钮与保存并列')

    def test_settings_hub_action_bar_stays_visible_at_minimum_size(self):
        win = self._hub()
        width, height = win.minsize()
        self.assertGreater(width, 1)
        win.geometry('%dx%d' % (width, height))
        win.update()
        save, close = _button(win, '保存'), _button(win, '关闭')
        self.assertGreater(save.winfo_rootx(), close.winfo_rootx(),
                           '设置窗底部保存也必须在关闭右边')
        bottom = win.winfo_rooty() + win.winfo_height()
        for button in (save, close):
            self.assertTrue(button.winfo_ismapped(), button.cget('text'))
            self.assertLessEqual(button.winfo_rooty() + button.winfo_height(), bottom,
                                 '动作区不得掉出窗口底边')

    def test_model_manager_action_bar_stays_visible_at_minimum_size(self):
        win = self._manager_window()
        win.geometry('%dx%d' % pet_models_ui.MANAGER_MIN)
        win.update()
        cancel, save = _button(win, '取消'), _button(win, '保存')
        bottom = win.winfo_rooty() + win.winfo_height()
        for button in (cancel, save):
            self.assertTrue(button.winfo_ismapped(), button.cget('text'))
            self.assertLessEqual(button.winfo_rooty() + button.winfo_height(), bottom,
                                 '动作区不得掉出窗口底边')


class ManagerHintTests(Batch7Case):
    def test_delete_and_probe_need_a_row_and_a_model_id(self):
        """没选行就删、没填模型 ID 就测，只写非模态提示；填了 ID 才去测并把结论写进提示。"""
        win = self._manager_window()
        hint = win._pet_hint
        _button(win, '删除这条').invoke()
        self.assertEqual(hint.get(), '先选一条。')
        win._pet_entries['model'].delete(0, 'end')
        _button(win, '测试连接').invoke()
        self.assertEqual(hint.get(), '先填模型 ID。')
        win._pet_entries['model'].insert(0, 'gpt-test')
        with mock.patch('pet_models_ui.probe_line', return_value='连通（测试）') as probe:
            _button(win, '测试连接').invoke()
        self.assertEqual(probe.call_args[0][0]['model'], 'gpt-test')
        self.assertEqual(hint.get(), '连通（测试）')


class SaveButtonStateTests(Batch7Case):
    def test_save_button_greys_out_on_pages_with_nothing_to_save(self):
        """窗口级「保存」跟着页走：自动生效的页置灰，有 save／apply 的页恢复。"""
        win = self._hub('budget')
        save = _button(win, '保存')
        self.assertNotIn('disabled', save.state(), '预算页有保存语义')
        for tab in ('basic', 'dev'):
            pet_settings_ui.select(win, tab)
            win.update()
            self.assertIn('disabled', save.state(), '「%s」没有可保存内容' % tab)
        for tab in ('model', 'level', 'token', 'budget'):
            pet_settings_ui.select(win, tab)
            win.update()
            self.assertNotIn('disabled', save.state(), '「%s」应恢复保存' % tab)
        disabled = dict(ttk.Style(win).map('Tokens.Primary.TButton', 'foreground')).get('disabled')
        self.assertEqual(str(disabled), COLORS['disabled_text'],
                         '禁用字色沿用 disabled_text 令牌')


class FormAlignmentTests(Batch7Case):
    def test_hub_budget_and_model_inputs_share_one_left_edge(self):
        """同一窗口切页后仍用同一条输入竖线，不因各页标签长短跳列。"""
        win = self._hub('budget')
        entries = [child for child in _descendants(win)
                   if child.winfo_class() == 'TEntry' and child.winfo_ismapped()]
        self.assertEqual(len(entries), 5, '预算五类输入')
        budget_x = {widget.winfo_rootx() for widget in entries}
        self.assertEqual(len(budget_x), 1)
        pet_settings_ui.select(win, 'model')
        win.update()
        combos = [child for child in _descendants(win)
                  if child.winfo_class() == 'TCombobox' and child.winfo_ismapped()]
        self.assertEqual(len(combos), 4)
        self.assertEqual({combo.winfo_rootx() for combo in combos}, budget_x,
                         '预算页与模型页的输入列必须同一条竖线')

    def test_settings_model_inputs_share_one_left_edge(self):
        win = self._hub('model')
        combos = [child for child in _descendants(win)
                  if child.winfo_class() == 'TCombobox' and child.winfo_ismapped()]
        self.assertEqual(len(combos), 4, '默认／对话／升级／降级四个下拉框')
        edges = {combo.winfo_rootx() for combo in combos}
        self.assertEqual(len(edges), 1, '四个输入控件必须落在同一竖线：%r' % edges)

    def test_manager_inputs_share_one_left_edge(self):
        win = self._manager_window()
        entries = win._pet_entries
        # 调用方式已移到左上角页签；Provider｜功能、模型 ID｜显示名各并一行后，
        # 左半边输入列（Provider、模型 ID、根地址、密钥名）同一竖线，右半边（功能、显示名）另有一条。
        edges = {entries[key].winfo_rootx() for key in ('model', 'base_url', 'key_env')}
        edges.add(win._pet_provider_box.winfo_rootx())
        self.assertEqual(len(edges), 1, '模型管理左输入列必须落在同一竖线：%r' % edges)
        right = {entries['label'].winfo_rootx(), win._pet_modality_box.winfo_rootx()}
        self.assertEqual(len(right), 1, '右半边的功能、显示名必须落在同一竖线：%r' % right)

    def test_manager_fields_use_content_widths_and_keep_pair_alignment(self):
        """紧凑表单契约：普通字段不再拉满半行；长地址才横跨弹性列，左右输入竖线仍对齐。"""
        win = self._manager_window()
        win.update()
        entries = win._pet_entries
        edges = {entries[key].winfo_rootx() for key in ('model', 'base_url', 'key_env')}
        edges.add(win._pet_provider_box.winfo_rootx())
        self.assertEqual(len(edges), 1, '左输入列必须落在同一竖线：%r' % edges)
        right = {entries['label'].winfo_rootx(), win._pet_modality_box.winfo_rootx()}
        self.assertEqual(len(right), 1, '右输入列必须落在同一竖线：%r' % right)
        quarter = max(1, win.winfo_width() // 4)
        for key in ('model', 'label', 'key_env', 'note'):
            self.assertLess(entries[key].winfo_width(), quarter,
                            '%s 是普通内容宽字段，不得拉满半行' % key)
        self.assertLess(entries['timeout'].winfo_width(), entries['note'].winfo_width(),
                        '短数值字段要比文本备注更窄')
        self.assertGreater(entries['base_url'].winfo_width(), entries['model'].winfo_width(),
                           'API 根地址是长值字段，应使用弹性跨列宽度')
        wire = next(child for child in win._pet_provider_box.master.winfo_children()
                    if child.winfo_class() == 'TCombobox'
                    and int(child.grid_info().get('row', -1)) == int(entries['key_env'].grid_info()['row']))
        self.assertEqual(wire.winfo_rootx(), win._pet_modality_box.winfo_rootx(), '协议与右半边同一竖线')
        self.assertLess(wire.winfo_width(), win.winfo_width() // 2,
                        '协议下拉按内容取宽，不得独占半行')
        style = ttk.Style(win)
        style.configure('Flat.Tokens.Combobox.TCombobox', padding=(0, 0))
        flat = ttk.Combobox(wire.master, style='Flat.Tokens.Combobox.TCombobox', width=14)
        flat.grid(row=99, column=0)
        win.update()
        grow = wire.winfo_height() - flat.winfo_height()   # 目标约三分之一，像素取整后允许 25%～45%
        self.assertGreaterEqual(grow * 4, flat.winfo_height(), '下拉框比零内边距时高出约三分之一')
        self.assertLessEqual(grow * 20, flat.winfo_height() * 9, '但不过分增高')

    def test_manager_long_values_remain_editable_and_inside_narrow_widths(self):
        """窄屏回归：长根地址／程序路径仍是可编辑输入框，可见控件不越过表单右缘。"""
        win = self._manager_window()
        entries = win._pet_entries
        long_url = 'https://api.example.test/' + 'very-long-path/' * 8 + 'v1'
        entries['base_url'].insert(0, long_url)
        self.assertEqual(entries['base_url'].get(), long_url)
        self.assertNotIn('readonly', entries['base_url'].state(), '长 API 根地址必须仍可编辑')
        win._pet_mode.set('Desktop')
        win.update()
        long_path = 'C:/Apps/' + 'deep-folder/' * 10 + 'Tool.exe'
        entries['program'].insert(0, long_path)
        self.assertEqual(entries['program'].get(), long_path)
        self.assertNotIn('readonly', entries['program'].state(), '长程序路径必须仍可编辑')

        def assert_inside_form(mode):
            win._pet_mode.set(mode)
            for width in (pet_models_ui.MANAGER_MIN[0], 990, 1180):
                win.geometry('%dx%d' % (width, pet_models_ui.MANAGER_MIN[1]))
                win.update()
                form = entries['model'].master
                edge = form.winfo_rootx() + form.winfo_width()
                for widget in _descendants(form):
                    if not widget.winfo_ismapped():
                        continue
                    self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(), edge + 1,
                                         (mode, width, widget, widget.winfo_rootx() + widget.winfo_width(), edge))

        assert_inside_form('Desktop')
        assert_inside_form('API')

    def test_label_columns_use_the_same_token_width(self):
        """标签列宽来自 ui_tokens.FORM_LABEL_WIDTH（加上中文实测），不是各页手写值。"""
        from ui_tokens import FORM_LABEL_WIDTH
        width = pet_models_ui.form_column_width(('默认模型', '密钥名（.env 里的变量名）'))
        self.assertGreaterEqual(width, FORM_LABEL_WIDTH)
        self.assertEqual(width, pet_models_ui.form_column_width(('默认模型', '密钥名（.env 里的变量名）')))


class RecoverableErrorTests(Batch7Case):
    def test_manager_save_failure_uses_non_modal_error(self):
        win = self._manager_window()
        win._pet_mode.set('Desktop')
        win.update()
        win._pet_entries['program'].insert(0, 'C:/definitely/missing.exe')
        with mock.patch.object(pet_models_ui, 'NotificationDispatcher') as dispatcher:
            _button(win, '保存这条').invoke()
        self.assertTrue(dispatcher.return_value.error.called,
                        '保存失败必须走统一错误入口')
        kwargs = dispatcher.return_value.error.call_args.kwargs
        self.assertFalse(kwargs.get('modal', False), '可恢复错误不得默认模态')

    def test_budget_save_failure_uses_non_modal_error(self):
        win = self._hub('budget')
        seams = win._pet_seams['budget']
        seams['fields']['video'].set('0')
        with mock.patch.object(pet_models_ui, 'NotificationDispatcher') as dispatcher:
            self.assertIsNone(seams['save']())
        self.assertTrue(dispatcher.return_value.error.called)
        self.assertFalse(dispatcher.return_value.error.call_args.kwargs.get('modal', False))
        self.assertIn('正整数', str(dispatcher.return_value.error.call_args.args))


class HubDefaultTabTests(Batch7Case):
    """UI 批次 7c：齿轮无参打开设置窗时，默认落在分页第一项「基础功能」。"""

    def _open_without_tab(self):
        scanner = mock.patch('pet_settings_ui.token_saver.scan', return_value={})
        scanner.start()
        self.addCleanup(scanner.stop)
        return self._show(pet_settings_ui.open_hub(self.pet))

    def test_open_without_tab_lands_on_basic_with_built_content(self):
        win = self._open_without_tab()
        self.assertEqual(pet_settings_ui.current(win), 'basic',
                         '无参打开必须落在「基础功能」，不能停在空窗')
        basic = win._pet_pages['basic']
        self.assertTrue(basic.winfo_ismapped(), '基础功能页必须真的摆出来')
        texts = [str(child.cget('text')) for child in _descendants(basic) if 'text' in child.keys()]
        self.assertIn('基础功能', texts, '内容区的抬头已构建')
        self.assertIn('宠物名字', texts, '基础功能表单已构建')
        self.assertTrue(any(child.winfo_class() == 'TSpinbox' for child in _descendants(basic)),
                        '免打扰时段输入已构建')
        self.assertIn('disabled', _button(win, '保存').state(),
                      '基础功能没有可保存内容，底部保存应置灰')

    def test_explicit_model_tab_still_lands_on_the_model_page(self):
        win = self._hub('model')
        self.assertEqual(pet_settings_ui.current(win), 'model')
        self.assertTrue(win._pet_pages['model'].winfo_ismapped())
        self.assertFalse(win._pet_pages['basic'].winfo_ismapped(),
                         '显式传 model 时不应再摆着基础功能页')

    def test_lazy_page_switch_keeps_content_frozen_until_layout_settles(self):
        """切到未建过的设置页时旧页像素留在屏幕上，表单排版完成后一次性重画。"""
        if sys.platform != 'win32':
            self.skipTest(PLATFORM_WINDOWS_ONLY)
        win = self._open_without_tab()
        stack = win._pet_pages['basic'].master
        original = win._pet_page_builders['model']
        visible_while_building = []
        import ctypes
        def build_model_page(frame):
            visible_while_building.append(
                bool(ctypes.windll.user32.IsWindowVisible(int(stack.winfo_id()))))
            return original(frame)
        win._pet_page_builders['model'] = build_model_page
        pet_settings_ui.select(win, 'model')
        self.assertEqual(visible_while_building, [False], '懒加载表单半成品不得上屏')
        self.assertTrue(bool(ctypes.windll.user32.IsWindowVisible(int(stack.winfo_id()))),
                        '排版完成后必须立即解冻')


class ModelListAutoHeightTests(Batch7Case):
    """模型列表自适应高度：少几条就少几行，不再在列表下方留大片空白。"""

    def _records(self, count):
        return {('model-%d' % i): model_pool.record(
            {'call_mode': 'API', 'model': 'model-%d' % i, 'label': '模型 %d' % i,
             'capabilities': ['text'], 'modality': 'text'}, 'model-%d' % i)
            for i in range(count)}

    def _reload(self, win, count):
        records = self._records(count)
        with mock.patch.object(self.pet, 'agent_model_records', return_value=records):
            win._pet_reload()
        win.update_idletasks()
        win.update()
        return win._pet_tree

    def test_model_list_shrinks_to_actual_row_count(self):
        """加载 3 条模型后，列表高度收缩到 3 行，而非停留在初始高度留下空白。"""
        win = self._manager_window()
        win.update()
        initial = int(win._pet_tree.cget('height'))
        self.assertGreater(initial, 3, '初始高度应大于 3 行（否则无从验证收缩）')
        tree = self._reload(win, 3)
        self.assertEqual(int(tree.cget('height')), 3,
                         '3 条模型应显示 3 行，下方不留空白')

    def test_model_list_grows_with_more_rows_but_not_beyond_content(self):
        """行数多时随窗口高度伸展，但绝不超过实际条目数（无空行）。"""
        win = self._manager_window()
        win.update()
        tree = self._reload(win, 5)
        self.assertLessEqual(int(tree.cget('height')), 5,
                             '高度不得超过实际条目数，避免底部空行')
        self.assertGreaterEqual(int(tree.cget('height')), 2,
                                '至少保留 2 行可见')


class ModelManagerUxTests(Batch7Case):
    """UX-MODEL-PAGE（DES《05》§15 模型管理页按键清单）：默认值预填、底行 [取消][保存]、
    未保存改动在切换行／新建／离开时先确认。"""

    def _type(self, win, key, text):
        """模拟真实改动：键入文本再把表单弄脏。隐藏桌面合成按键事件不可靠
        （test_desktop_compact_layout「搜索框过滤」同此结论），改用「功能」下拉
        <<ComboboxSelected>>——虚拟事件由 Tk 内部派发，与真实用户挑选等效。"""
        win._pet_entries[key].insert('end', text)
        self.assertTrue(win._pet_entries[key].bind('<KeyRelease>'),
                        '%s 输入框缺少 <KeyRelease> 未保存改动绑定' % key)
        win._pet_modality_box.event_generate('<<ComboboxSelected>>')

    def test_mode_segments_are_compact_and_keyboard_accessible(self):
        """API／Desktop／CLI 不再是 Notebook 大页签：小型分段按钮可聚焦、可用方向键与回车切换。"""
        win = self._manager_window()
        win.update()
        control = win._pet_mode_control
        buttons = win._pet_mode_buttons
        self.assertIsInstance(control, pet_models_ui.ModeSegmentedControl)
        self.assertEqual(tuple(buttons), pet_models_ui.MODES)
        self.assertFalse([child for child in _descendants(win) if isinstance(child, ttk.Notebook)],
                         '模型管理不再使用 Notebook 大页签')
        save = _button(win, '保存')
        for mode, button in buttons.items():
            expected = (pet_models_ui.MODE_SEGMENT_SELECTED_STYLE if mode == win._pet_mode.get()
                        else pet_models_ui.MODE_SEGMENT_STYLE)
            self.assertEqual(str(button.cget('style')), expected, mode)
            self.assertLess(button.winfo_height(), save.winfo_height(),
                            '%s 分段按钮必须小于普通动作按钮' % mode)
            self.assertTrue(button.bind('<Return>'), '%s 缺少回车切换绑定' % mode)
            self.assertTrue(button.bind('<space>'), '%s 缺少空格切换绑定' % mode)
        buttons['API'].focus_force()
        win.update()
        self.assertEqual(str(win.focus_get()), str(buttons['API']), '分段按钮必须能拿到键盘焦点')
        self.assertTrue(buttons['API'].bind('<Right>'), '分段按钮缺少方向键绑定')
        buttons['API'].event_generate('<Right>')
        win.update()
        self.assertEqual(win._pet_mode.get(), 'Desktop', '右方向键应切到下一段')
        self.assertEqual(str(win.focus_get()), str(buttons['Desktop']), '方向键切换后焦点跟着走')
        self.assertEqual(str(buttons['Desktop'].cget('style')), pet_models_ui.MODE_SEGMENT_SELECTED_STYLE)
        self.assertEqual(str(buttons['API'].cget('style')), pet_models_ui.MODE_SEGMENT_STYLE)
        buttons['API'].focus_set()
        buttons['API'].event_generate('<Return>')
        win.update()
        self.assertEqual(win._pet_mode.get(), 'API', '回车应切回聚焦的分段')

    def test_mode_switch_filters_cached_rows_without_rereading_the_pool(self):
        """API／Desktop／CLI 切页只换过滤条件；不重复读模型池，显式刷新仍会重读。"""
        records = {'api-1': model_pool.record({'model': 'api-1', 'call_mode': 'API'}, 'api-1'),
                   'desk-1': model_pool.record({'model': 'desk-1', 'call_mode': 'Desktop'}, 'desk-1')}
        self.pet.agent_model_records = lambda: dict(records)
        win = self._manager_window()
        calls = []
        original = self.pet.agent_model_records
        def counted():
            calls.append('read')
            return original()
        self.pet.agent_model_records = counted
        win._pet_mode.set('Desktop')
        win.update()
        win._pet_mode.set('CLI')
        win.update()
        self.assertEqual(calls, [], '分段切换不得重复读模型池')
        win._pet_reload()
        self.assertEqual(len(calls), 1, '显式刷新仍要重读模型池')

    def test_mode_switch_table_stays_frozen_until_rows_and_height_settle(self):
        """真窗口切分段时列表区域先保持旧像素，行插入与自适应高度落定后一次性重画。"""
        if sys.platform != 'win32':
            self.skipTest(PLATFORM_WINDOWS_ONLY)
        win = self._manager_window()
        manager = win._pet_reload.__self__
        freezer = manager._rows_paint_freeze
        self.assertIsNotNone(freezer)
        self.assertFalse(freezer.frozen)
        win._pet_mode.set('Desktop')
        self.assertTrue(freezer.frozen, '清空并重建列表期间必须冻结绘制')
        import ctypes
        handle = int(manager.table_shell.winfo_id())
        self.assertFalse(ctypes.windll.user32.IsWindowVisible(handle), '半成品列表不得上屏')
        win.update_idletasks()
        self.assertFalse(freezer.frozen, '行高与布局落定后立即解冻，不等超时')
        self.assertTrue(ctypes.windll.user32.IsWindowVisible(handle))

    def test_mode_segment_click_preserves_unsaved_changes_guard(self):
        """分段切换仍走未保存改动确认；拒绝时回到原段，表单内容不被覆盖。"""
        win = self._manager_window()
        buttons = win._pet_mode_buttons
        self._type(win, 'note', '未保存改动')
        with mock.patch.object(self.pet, 'confirm_start', return_value=False) as confirm:
            buttons['Desktop'].invoke()
            win.update()
        self.assertTrue(confirm.called)
        self.assertEqual(win._pet_mode.get(), 'API')
        self.assertEqual(win._pet_mode_control.current(), 'API', '拒绝后分段高亮必须弹回 API')
        self.assertEqual(str(buttons['API'].cget('style')), pet_models_ui.MODE_SEGMENT_SELECTED_STYLE)
        self.assertEqual(win._pet_entries['note'].get(), '未保存改动')
        with mock.patch.object(self.pet, 'confirm_start', return_value=True):
            buttons['Desktop'].invoke()
            win.update()
        self.assertEqual(win._pet_mode.get(), 'Desktop')
        self.assertEqual(win._pet_mode_control.current(), 'Desktop')

    def test_new_entry_prefills_mainstream_defaults(self):
        win = self._manager_window()
        for key, value in (('context_length', '262144'), ('max_output', '8192'),
                           ('temperature', '0.7'), ('timeout', '120'), ('retries', '2')):
            self.assertEqual(win._pet_entries[key].get(), value, key)
        _button(win, '新建一条').invoke()
        self.assertEqual(win._pet_entries['context_length'].get(), '262144',
                         '新建一条同样预填 256K')

    def test_saved_record_values_are_not_overwritten_by_defaults(self):
        record = model_pool.record({'model': 'mine', 'base_url': 'https://x.test/v1',
                                    'call_mode': 'API', 'context_length': 64000,
                                    'temperature': '0.9'}, 'mine')
        self.pet.agent_model_records = lambda: {'mine': record}
        win = self._manager_window()
        win._pet_tree.selection_set('mine')
        win._pet_tree.event_generate('<<TreeviewSelect>>')
        win.update()
        self.assertEqual(win._pet_entries['context_length'].get(), '64000', '已存值不被默认覆盖')
        self.assertEqual(win._pet_entries['temperature'].get(), '0.9')
        self.assertEqual(win._pet_entries['max_output'].get(), '', '没存过的字段不冒默认')

    def test_save_writes_then_closes_and_failure_stays_with_reason(self):
        win = self._manager_window()
        win._pet_entries['model'].insert(0, 'm-1')
        with mock.patch.object(self.pet, 'save_pool') as save_pool:
            _button(win, '保存').invoke()
        self.assertTrue(save_pool.called, '保存必须先写池')
        self.assertFalse(win.winfo_exists(), '保存成功后关窗')
        win = self._manager_window()
        win._pet_entries['model'].insert(0, 'm-2')
        with mock.patch.object(self.pet, 'save_pool', side_effect=ValueError('写入失败')), \
                mock.patch.object(pet_models_ui, 'NotificationDispatcher') as dispatcher:
            _button(win, '保存').invoke()
        self.assertTrue(dispatcher.return_value.error.called, '失败要给原因')
        self.assertTrue(win.winfo_exists(), '保存失败留在页内')

    def test_cancel_confirms_only_when_there_are_unsaved_changes(self):
        win = self._manager_window()
        with mock.patch.object(self.pet, 'confirm_start') as confirm:
            _button(win, '取消').invoke()
        confirm.assert_not_called()
        self.assertFalse(win.winfo_exists())
        win = self._manager_window()
        self._type(win, 'note', '手改的备注')
        with mock.patch.object(self.pet, 'confirm_start', return_value=False) as confirm:
            _button(win, '取消').invoke()
        confirm.assert_called_once()
        self.assertTrue(win.winfo_exists(), '拒绝确认后留在页内')
        with mock.patch.object(self.pet, 'confirm_start', return_value=True):
            _button(win, '取消').invoke()
        self.assertFalse(win.winfo_exists())

    def test_row_switch_confirms_unsaved_changes(self):
        records = {key: model_pool.record({'model': key, 'base_url': 'https://x.test/v1',
                                           'call_mode': 'API'}, key)
                   for key in ('a-1', 'b-2')}
        self.pet.agent_model_records = lambda: dict(records)
        win = self._manager_window()
        win._pet_tree.selection_set('a-1')
        win._pet_tree.event_generate('<<TreeviewSelect>>')
        win.update()
        self.assertEqual(win._pet_entries['model'].get(), 'a-1')
        self._type(win, 'note', '未保存改动')
        with mock.patch.object(self.pet, 'confirm_start', return_value=False) as confirm:
            win._pet_tree.selection_set('b-2')
            win._pet_tree.event_generate('<<TreeviewSelect>>')
            win.update()
        self.assertTrue(confirm.called)
        self.assertEqual(tuple(win._pet_tree.selection()), ('a-1',), '拒绝后选区留在原条目')
        self.assertEqual(win._pet_entries['model'].get(), 'a-1', '拒绝后表单不被覆盖')
        with mock.patch.object(self.pet, 'confirm_start', return_value=True):
            win._pet_tree.selection_set('b-2')
            win._pet_tree.event_generate('<<TreeviewSelect>>')
            win.update()
        self.assertEqual(win._pet_entries['model'].get(), 'b-2')

    def test_secondary_actions_stay_off_the_save_row_at_three_widths(self):
        win = self._manager_window()
        for width in (pet_models_ui.MANAGER_MIN[0], 990, 1180):
            win.geometry('%dx%d' % (width, pet_models_ui.MANAGER_MIN[1]))
            win.update()
            save = _button(win, '保存')
            self.assertEqual(_button(win, '取消').winfo_rooty(), save.winfo_rooty(),
                             '取消与保存同排')
            for label in ('新建一条', '测试连接', '删除这条', '保存这条', '语音识别…'):
                button = _button(win, label)
                self.assertNotEqual(button.winfo_rooty(), save.winfo_rooty(),
                                    '%s 不与保存同排' % label)
            edge = win.winfo_rootx() + win.winfo_width()
            bottom = win.winfo_rooty() + win.winfo_height()
            for label in ('取消', '保存', '新建一条', '测试连接', '删除这条', '保存这条', '语音识别…'):
                button = _button(win, label)
                self.assertTrue(button.winfo_ismapped(), (width, label))
                self.assertLessEqual(button.winfo_rootx() + button.winfo_width(), edge,
                                     (width, label))
                self.assertLessEqual(button.winfo_rooty() + button.winfo_height(), bottom,
                                     (width, label))


if __name__ == '__main__':
    unittest.main()

