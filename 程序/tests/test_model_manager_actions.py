"""模型管理窗：Provider 下拉按大小写去重；「保存这条」在左侧，「保存并关闭」先存后关。"""
import unittest
from unittest import mock

import model_pool
import pet_models_ui
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


class ManagerActionTests(Batch7Case):
    def _manager(self):
        return self._show(pet_models_ui.open_manager(self.pet))

    def test_save_one_sits_after_delete_on_the_left(self):
        win = self._manager()
        delete, save = _button(win, '删除这条'), _button(win, '保存这条')
        close = _button(win, '保存并关闭')
        self.assertGreater(save.winfo_rootx(), delete.winfo_rootx())
        self.assertGreater(close.winfo_rootx(), save.winfo_rootx())
        self.assertFalse([b for b in _buttons(win) if str(b.cget('text')) == '关闭' and b.winfo_ismapped()])

    def test_blank_form_closes_without_saving(self):
        win = self._manager()
        with mock.patch.object(self.pet, 'save_pool') as save_pool:
            _button(win, '保存并关闭').invoke()
            save_pool.assert_not_called()
        self.assertFalse(win.winfo_exists())

    def test_failed_save_keeps_window_open(self):
        win = self._manager()
        win._pet_entries['model'].insert(0, 'kimi-k2')
        with mock.patch.object(self.pet, 'save_pool', side_effect=ValueError('密钥名不对')):
            _button(win, '保存并关闭').invoke()
        self.assertTrue(win.winfo_exists())
        self.assertIn('密钥名不对', win._pet_hint.get())

    def test_successful_save_then_closes(self):
        win = self._manager()
        win._pet_entries['model'].insert(0, 'kimi-k2')
        with mock.patch.object(self.pet, 'save_pool', return_value=True) as save_pool:
            _button(win, '保存并关闭').invoke()
        save_pool.assert_called_once()
        self.assertEqual(save_pool.call_args.args[0]['model'], 'kimi-k2')
        self.assertFalse(win.winfo_exists())


if __name__ == '__main__':
    unittest.main()
