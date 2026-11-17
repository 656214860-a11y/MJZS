"""UI 批次 7：设置窗与模型窗——表单列对齐、保存／取消位置、最小尺寸动作区、错误不锁屏。

全部用真 Tk 根窗口量几何；项目根是 ``tempfile`` 空目录，不打开、不读取任何用户项目，
也不读 ``private/`` 或真实密钥。
"""
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
from skip_reasons import PLATFORM_TKINTER
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

    # 模型配置
    def agent_model_records(self):
        return {}

    def agent_model_tasks(self):
        return dict(self.tasks)

    def resolve_agent_model(self, _key):
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

    def test_model_manager_close_is_rightmost_primary(self):
        # 契约有意变更：「保存并关闭」改回「关闭」（不保存），仍作主操作贴最右；保存只走左侧「保存这条」。
        win = self._manager_window()
        save, close = _button(win, '保存这条'), _button(win, '关闭')
        self.assertGreater(close.winfo_rootx(), save.winfo_rootx(),
                           '关闭必须在保存这条右边')
        self.assertEqual(str(close.cget('style')), 'Tokens.Primary.TButton')

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
        save, close = _button(win, '保存这条'), _button(win, '关闭')
        bottom = win.winfo_rooty() + win.winfo_height()
        for button in (save, close):
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

    def test_manager_pairs_selects_on_equal_widths_and_taller_boxes(self):
        win = self._manager_window()
        win.update()
        entries = win._pet_entries
        # 两列等分剩余宽度，总宽为奇数像素时差 1px，属 Tk 整数取整，不可见。
        self.assertLessEqual(abs(win._pet_provider_box.winfo_width() - win._pet_modality_box.winfo_width()), 1,
                             'Provider 与功能两个下拉框等宽')
        wire = next(child for child in win._pet_provider_box.master.winfo_children()
                    if child.winfo_class() == 'TCombobox'
                    and int(child.grid_info().get('row', -1)) == int(entries['key_env'].grid_info()['row']))
        self.assertEqual(wire.winfo_rootx(), win._pet_modality_box.winfo_rootx(), '协议与右半边同一竖线')
        self.assertLessEqual(abs(wire.winfo_width() - win._pet_provider_box.winfo_width()), 1, '密钥名与协议并列且等宽')
        style = ttk.Style(win)
        style.configure('Flat.Tokens.Combobox.TCombobox', padding=(0, 0))
        flat = ttk.Combobox(wire.master, style='Flat.Tokens.Combobox.TCombobox', width=14)
        flat.grid(row=99, column=0)
        win.update()
        grow = wire.winfo_height() - flat.winfo_height()   # 目标约三分之一，像素取整后允许 25%～45%
        self.assertGreaterEqual(grow * 4, flat.winfo_height(), '下拉框比零内边距时高出约三分之一')
        self.assertLessEqual(grow * 20, flat.winfo_height() * 9, '但不过分增高')

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


if __name__ == '__main__':
    unittest.main()

