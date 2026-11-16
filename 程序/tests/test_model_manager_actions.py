"""模型管理窗：Provider 下拉按大小写去重；「保存这条」在左侧，「关闭」只关窗不保存。"""
import unittest
from unittest import mock

import model_pool
import pet_models_ui
import speech_api
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
        close = _button(win, '关闭')
        self.assertGreater(save.winfo_rootx(), delete.winfo_rootx())
        self.assertGreater(close.winfo_rootx(), save.winfo_rootx())
        self.assertFalse([b for b in _buttons(win) if str(b.cget('text')) == '保存并关闭'])

    def test_blank_form_closes_without_saving(self):
        win = self._manager()
        with mock.patch.object(self.pet, 'save_pool') as save_pool:
            _button(win, '关闭').invoke()
            save_pool.assert_not_called()
        self.assertFalse(win.winfo_exists())

    def test_close_with_filled_form_does_not_save(self):
        # 契约有意变更：「保存并关闭」改为「关闭」，去掉保存；表单填了也只关窗。
        win = self._manager()
        win._pet_entries['model'].insert(0, 'kimi-k2')
        with mock.patch.object(self.pet, 'save_pool') as save_pool:
            _button(win, '关闭').invoke()
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
        self.assertGreaterEqual(win.winfo_width(), win.winfo_reqwidth())

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
