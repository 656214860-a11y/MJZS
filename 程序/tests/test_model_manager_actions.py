"""模型管理窗：Provider 下拉按大小写去重；「保存这条」在左侧，底行右对齐 [取消][保存]。"""
import unittest
from unittest import mock

import infra.model_pool as model_pool
import pet_models_ui
from domain import speech_api
import speech_settings_ui
from tests.test_ui_batch7_settings_models import Batch7Case, _button, _buttons


CLI_RECORDS = {
    'claude-code-cli': {'label': 'Claude Code Cli', 'model': 'claude', 'provider': 'desktop',
                        'provider_label': 'Anthropic', 'call_mode': 'CLI'},
    'kimi': {'label': 'Kimi', 'model': 'kimi-k2', 'provider': 'Moonshot',
             'base_url': 'https://api.moonshot.cn/v1'},
    'kimi-2': {'label': 'Kimi 2', 'model': 'kimi-k3', 'provider': 'moonshot',
               'base_url': 'https://api.moonshot.cn/v1'},
}


class ProviderChoicesTests(Batch7Case):
    def test_provider_values_have_no_case_duplicates(self):
        records = {key: model_pool.record(value, key) for key, value in CLI_RECORDS.items()}
        self.pet.agent_model_records = lambda: dict(records)
        win = self._show(pet_models_ui.open_manager(self.pet))
        # REQ-UI-MODEL-PAGE-2：API 路线内置 9 项主流预设＋已存自定义厂商（大小写去重）；Desktop/CLI 保留内建厂商去重。
        values = [str(item) for item in win._pet_provider_box.cget('values')]
        folded = [item.casefold() for item in values]
        self.assertEqual(len(folded), len(set(folded)), values)
        self.assertIn('Anthropic (Claude)', values, 'API 预设包含 Anthropic')
        self.assertEqual(sum(item == 'moonshot' for item in folded), 1, values)
        win._pet_mode.set('Desktop')
        win.update()
        local_vals = [str(item) for item in win._pet_provider_box.cget('values')]
        local_folded = [item.casefold() for item in local_vals]
        self.assertEqual(len(local_folded), len(set(local_folded)), local_vals)
        self.assertIn('anthropic', local_vals, '本地厂商保留内建项')
        self.assertNotIn('Anthropic', local_vals)

    def test_provider_dropdown_drops_openai_compatible_defaults_to_custom_and_is_sorted(self):
        win = self._show(pet_models_ui.open_manager(self.pet))
        values = [str(item) for item in win._pet_provider_box.cget('values')]
        self.assertNotIn('OpenAI 兼容接口', values)
        self.assertIn('DeepSeek 官方', values)
        self.assertEqual(win._pet_provider.get(), '自定义中转')
        win._pet_mode.set('Desktop')
        win.update()
        local_vals = [str(item) for item in win._pet_provider_box.cget('values')]
        self.assertEqual(local_vals, sorted(local_vals, key=str.casefold))

    def test_top_down_form_aligns_primary_inputs_and_folds_advanced_params(self):
        """REQ-UI-MODEL-PAGE-2：右侧改为 DSH 风格自上而下单列表单，核心输入共享左竖线、高级参数折叠。"""
        win = self._show(pet_models_ui.open_manager(self.pet))
        win.update_idletasks()
        card = win._pet_route_cards()[0]
        self.assertFalse(win._pet_advanced_section.is_open(), '高级参数默认折叠')
        self.assertFalse(card.route_adv.is_open(), '路线协议与环境变量默认折叠')
        edges = {win._pet_entries['label'].winfo_rootx(), win._pet_entries['model'].winfo_rootx(),
                 card.base_url_entry.winfo_rootx(), card.model_entry.winfo_rootx()}
        self.assertEqual(len(edges), 1, f'自上而下核心输入左沿应对齐：{edges}')


class ManagerActionTests(Batch7Case):
    def _manager(self):
        return self._show(pet_models_ui.open_manager(self.pet))

    def test_save_sits_right_of_delete_in_top_bar_without_legacy_bottom_bar(self):
        win = self._manager()
        delete, save = _button(win, '删除'), _button(win, '保存')
        self.assertGreater(save.winfo_rootx(), delete.winfo_rootx())
        self.assertEqual(save.winfo_rooty(), delete.winfo_rooty())
        for removed in ('关闭', '保存并关闭', '保存这条', '取消'):
            self.assertFalse([b for b in _buttons(win) if str(b.cget('text')) == removed], removed)

    def test_blank_form_closes_without_saving(self):
        # REQ-UI-MODEL-PAGE-2：去掉底栏取消按钮，Esc／窗口关闭走 cancel() 且干净表单直接关窗不保存。
        win = self._manager()
        with mock.patch.object(self.pet, 'save_pool') as save_pool:
            win.event_generate('<Escape>')
            win.update()
            save_pool.assert_not_called()
        self.assertFalse(win.winfo_exists())

    def test_close_with_filled_form_does_not_save(self):
        win = self._manager()
        win._pet_entries['model'].insert(0, 'kimi-k2')
        with mock.patch.object(self.pet, 'save_pool') as save_pool:
            win.event_generate('<Escape>')
            win.update()
            save_pool.assert_not_called()
        self.assertFalse(win.winfo_exists())


class SpeechSettingsTests(Batch7Case):
    """REQ-S01-71 / UX-SETTINGS-MODELS：语音识别并入模型管理左上角分段，独立弹窗壳仍兼容可用。"""
    def _dialog(self):
        manager = self._show(pet_models_ui.open_manager(self.pet))
        self.assertFalse([b for b in _buttons(manager) if str(b.cget('text')) == '语音识别…'],
                         '独立「语音识别…」按钮已取消并入左上角分类分段')
        self.assertIn('语音识别', manager._pet_mode_buttons)
        with mock.patch.object(speech_api, 'read_settings', return_value=dict(speech_api.DEFAULTS)), \
                mock.patch.object(speech_api, 'api_key', return_value=''):
            dialog = speech_settings_ui.open_speech_settings(self.pet, manager)
        return self._show(dialog)

    def test_fields_show_settings_and_missing_key(self):
        win = self._dialog()
        self.assertEqual(win._pet_speech_vars['model'].get(), 'qwen3-asr-flash-realtime')
        self.assertEqual(win._pet_speech_vars['silence_ms'].get(), '400')
        self.assertIn('没找到这个密钥', win._pet_speech_key_state.get())
        win.update_idletasks()
        self.assertGreaterEqual(win.winfo_height(), win.winfo_reqheight(), '不写死高度，表单不被裁掉')
        scroll = win._pet_speech_scroll
        self.assertGreaterEqual(win.winfo_width(), win.winfo_reqwidth())
        self.assertGreater(scroll.canvas.winfo_height(), 0)
        self.assertLessEqual(win.winfo_height(), win.winfo_screenheight())
        self._assert_actions_visible(win)
        # 高屏可以一次容纳表单；只在明确受限的短窗里要求发生滚动。
        win.geometry('%dx600' % win.winfo_width())
        win.update()
        self.assertGreater(scroll.form.winfo_reqheight(), scroll.canvas.winfo_height())
        self.assertTrue(scroll.scroll.winfo_ismapped(), '长表单必须提供可见滚动条')
        region = tuple(float(value) for value in scroll.canvas.cget('scrollregion').split())
        self.assertGreaterEqual(region[3], scroll.form.winfo_reqheight())
        self.assertGreaterEqual(scroll.canvas.winfo_width(), scroll.form.winfo_reqwidth())
        self._assert_actions_visible(win)

    def _assert_actions_visible(self, win):
        canvas = win._pet_speech_scroll.canvas
        for label in ('恢复默认', '保存', '取消'):
            button = _button(win, label)
            self.assertTrue(button.winfo_ismapped())
            self.assertGreaterEqual(button.winfo_rooty(), canvas.winfo_rooty() + canvas.winfo_height())
            self.assertLessEqual(button.winfo_rooty() + button.winfo_height(),
                                 win.winfo_rooty() + win.winfo_height())

    def test_scrollbar_and_keyboard_reach_last_field_in_short_window(self):
        """REQ-S01-71：600 高窗口的视口、末尾替换框与固定动作都可用。"""
        win = self._dialog()
        win.geometry('%dx%d' % (win.winfo_width(), 600))
        win.update()
        scroll = win._pet_speech_scroll
        # 实际末尾文本框通过原生控件树找到，不以源码位置代替几何。
        fields = [child for child in scroll.form.winfo_children()[0].winfo_children()
                  if child.winfo_class() == 'Text']
        self.assertEqual(len(fields), 1)
        last = fields[0]
        scroll.canvas.yview_moveto(1.0)
        win.update()
        self.assertGreater(scroll.canvas.yview()[0], 0)
        self.assertGreaterEqual(last.winfo_rooty(), scroll.canvas.winfo_rooty())
        self.assertLessEqual(last.winfo_rooty() + last.winfo_height(),
                             scroll.canvas.winfo_rooty() + scroll.canvas.winfo_height())
        self._assert_actions_visible(win)
        scroll.canvas.yview_moveto(0)
        previous = last.tk.call('tk_focusPrev', str(last))
        win.nametowidget(str(previous)).focus_force()
        win.update()
        win.nametowidget(str(previous)).event_generate('<Tab>')
        win.update()
        self.assertEqual(win.focus_get(), last)
        self.assertGreater(scroll.canvas.yview()[0], 0, 'Tab 到底部字段时应自动滚入视口')
        self.assertGreaterEqual(last.winfo_rooty(), scroll.canvas.winfo_rooty())
        self.assertLessEqual(last.winfo_rooty() + last.winfo_height(),
                             scroll.canvas.winfo_rooty() + scroll.canvas.winfo_height())
        self._assert_actions_visible(win)
        # 每个原有输入项（含离线／词典／AI）聚焦后都完整进入视口。
        controls = [child for child in scroll.form.winfo_children()[0].winfo_children()
                    if child.winfo_class() in ('TEntry', 'TCombobox', 'Text')]
        self.assertGreaterEqual(len(controls), len(speech_settings_ui.SPEECH_FIELDS))
        for field in reversed(controls):
            field.focus_force()
            win.update()
            self.assertGreaterEqual(field.winfo_rooty(), scroll.canvas.winfo_rooty())
            self.assertLessEqual(field.winfo_rooty() + field.winfo_height(),
                                 scroll.canvas.winfo_rooty() + scroll.canvas.winfo_height())
        scroll.canvas.yview_moveto(0)
        controls[0].event_generate('<MouseWheel>', delta=-120)
        win.update()
        self.assertGreater(scroll.canvas.yview()[0], 0, '字段上的滚轮也必须滚动表单')
        self._assert_actions_visible(win)

    def test_cancel_does_not_save_form_or_dictionary(self):
        win = self._dialog()
        win._pet_speech_vars['language'].set('en')
        with mock.patch.object(speech_settings_ui.speech_api, 'save_settings') as save_settings, \
                mock.patch.object(speech_settings_ui.speech_api, 'save_dictionary') as save_dict:
            _button(win, '取消').invoke()
        save_settings.assert_not_called()
        save_dict.assert_not_called()
        self.assertFalse(win.winfo_exists())

    def test_download_start_cancel_and_completion_survive_scrolling(self):
        """REQ-S01-71：复用原下载器，滚动不影响开始、取消和完成回调。"""
        from domain import offline_asr_setup
        win = self._dialog()
        runner, _state, progress, button = win._pet_speech_setup
        with mock.patch.object(offline_asr_setup, 'OfflineSetupRunner') as factory, \
                mock.patch.object(offline_asr_setup, 'environment_ready', return_value=False):
            factory.return_value.start.return_value = True
            factory.return_value.running = True
            button.invoke()
            self.assertIs(runner['obj'], factory.return_value)
            self.assertEqual(button.cget('text'), '取消下载')
            callback = factory.call_args.args[1]
            callback({'type': 'progress', 'message': '下载进度 50%'})
            win.update()
            self.assertEqual(progress.get(), '下载进度 50%')
            win._pet_speech_scroll.canvas.yview_moveto(1)
            button.invoke()
            factory.return_value.cancel.assert_called_once_with()
            self.assertIn('正在取消', progress.get())
            callback({'type': 'done'})
            win.update()
            self.assertIsNone(runner['obj'])
            self.assertEqual(button.cget('text'), '下载离线语音包…')
            self.assertEqual(win._pet_speech_hint.get(), '离线语音包安装完成')
            self._assert_actions_visible(win)

    def test_invalid_value_keeps_dialog_open_with_reason(self):
        win = self._dialog()
        win._pet_speech_vars['timeout'].set('0')
        with mock.patch.object(speech_settings_ui.speech_api, 'save_settings', side_effect=ValueError('timeout 必须是 3–120 之间的整数')):
            _button(win, '保存').invoke()
        self.assertTrue(win.winfo_exists())
        self.assertIn('timeout 必须是', win._pet_speech_hint.get())

    def test_save_passes_form_then_closes_and_reset_restores_defaults(self):
        win = self._dialog()
        win._pet_speech_vars['language'].set('en')
        _button(win, '恢复默认').invoke()
        self.assertEqual(win._pet_speech_vars['language'].get(), 'zh')
        win._pet_speech_vars['model'].set('qwen3-asr-flash-realtime-2026')
        with mock.patch.object(speech_settings_ui.speech_api, 'save_settings') as save_settings, \
                mock.patch.object(speech_settings_ui.speech_api, 'save_dictionary') as save_dict:
            _button(win, '保存').invoke()
        self.assertEqual(save_settings.call_args.args[0]['model'], 'qwen3-asr-flash-realtime-2026')
        save_dict.assert_called_once(), '词典与设置同窗保存'
        self.assertFalse(win.winfo_exists())

if __name__ == '__main__':
    unittest.main()
