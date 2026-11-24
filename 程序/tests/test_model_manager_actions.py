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
        values = [str(item) for item in win._pet_provider_box.cget('values')]
        folded = [item.casefold() for item in values]
        self.assertEqual(len(folded), len(set(folded)), values)
        self.assertIn('anthropic', values, '保留内建项')
        self.assertNotIn('Anthropic', values)
        self.assertEqual(sum(item == 'moonshot' for item in folded), 1, values)

    def test_provider_dropdown_drops_openai_compatible_defaults_to_custom_and_is_sorted(self):
        win = self._show(pet_models_ui.open_manager(self.pet))
        values = [str(item) for item in win._pet_provider_box.cget('values')]
        self.assertNotIn('OpenAI 兼容接口', values)
        self.assertEqual(values, sorted(values, key=str.casefold))
        self.assertEqual(win._pet_provider.get(), '自定义')

    def test_paired_boxes_share_one_width_and_right_labels_hug_their_box(self):
        win = self._show(pet_models_ui.open_manager(self.pet))
        win.update_idletasks()
        form = win._pet_provider_box.master
        # 调用方式已移到左上角页签，不再是表单下拉；成对字段（Provider｜功能、模型 ID｜显示名、
        # 密钥名｜协议）仍是 col1/col3 两列等宽、右标签靠右。
        pairs = []
        for slave in form.grid_slaves():
            info = slave.grid_info()
            if int(info['column']) == 1 and int(info['columnspan']) == 1 and slave.winfo_class() != 'Frame':
                other = form.grid_slaves(row=info['row'], column=3)
                if other:
                    pairs.append((slave, other[0]))
        self.assertGreaterEqual(len(pairs), 3)
        for left, right in pairs:
            self.assertAlmostEqual(left.winfo_width(), right.winfo_width(), delta=1)
            self.assertGreater(right.winfo_rootx() - left.winfo_rootx() - left.winfo_width(), 0)
        label = form.grid_slaves(row=0, column=2)[0]
        self.assertEqual(str(label.grid_info()['sticky']), 'e')


class ManagerActionTests(Batch7Case):
    def _manager(self):
        return self._show(pet_models_ui.open_manager(self.pet))

    def test_save_one_sits_after_delete_on_the_left(self):
        win = self._manager()
        delete, save = _button(win, '删除这条'), _button(win, '保存这条')
        bottom_save = _button(win, '保存')
        self.assertGreater(save.winfo_rootx(), delete.winfo_rootx())
        self.assertGreater(bottom_save.winfo_rootx(), save.winfo_rootx())
        self.assertFalse([b for b in _buttons(win) if str(b.cget('text')) == '关闭'])
        self.assertFalse([b for b in _buttons(win) if str(b.cget('text')) == '保存并关闭'])

    def test_blank_form_closes_without_saving(self):
        # UX-MODEL-PAGE 契约变更：独立「关闭」改为底行「取消」（DES《05》§15.2），仍只关窗不保存。
        win = self._manager()
        with mock.patch.object(self.pet, 'save_pool') as save_pool:
            _button(win, '取消').invoke()
            save_pool.assert_not_called()
        self.assertFalse(win.winfo_exists())

    def test_close_with_filled_form_does_not_save(self):
        # UX-MODEL-PAGE 契约变更：「关闭」改为底行「取消」；程序化填入不算未保存改动，取消直关不保存。
        win = self._manager()
        win._pet_entries['model'].insert(0, 'kimi-k2')
        with mock.patch.object(self.pet, 'save_pool') as save_pool:
            _button(win, '取消').invoke()
            save_pool.assert_not_called()
        self.assertFalse(win.winfo_exists())


class SpeechSettingsTests(Batch7Case):
    """REQ-S01-71：模型管理底栏「语音识别…」打开设置弹窗，保存走 speech_api.save_settings。"""
    def _dialog(self):
        manager = self._show(pet_models_ui.open_manager(self.pet))
        save = _button(manager, '保存这条')
        entry = _button(manager, '语音识别…')
        self.assertGreater(entry.winfo_rootx(), save.winfo_rootx(), '入口在左侧按钮组末尾')
        original, opened = speech_settings_ui.open_speech_settings, []
        opener = lambda pet, parent=None: opened.append(original(pet, parent))
        with mock.patch.object(speech_api, 'read_settings', return_value=dict(speech_api.DEFAULTS)), \
                mock.patch.object(speech_api, 'api_key', return_value=''), \
                mock.patch.object(pet_models_ui, 'open_speech_settings', opener):
            entry.invoke()
        self.assertEqual(len(opened), 1)
        return self._show(opened[0])

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
