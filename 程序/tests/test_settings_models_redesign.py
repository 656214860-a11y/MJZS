# -*- coding: utf-8 -*-
"""UX-SETTINGS-MODELS 回归与验收自检：
1) 设置左栏 8 枚专属目录图标（与主界面 0 复用 + 24x24 + 日夜主题重染）；
2) 「模型配置」改为左栏标准目录项并在右侧内嵌显示（不弹 Toplevel）；
3) 模型管理移除「语音识别…」按钮，左上角分段纳入「语音识别」并原地展示配置；
4) 模型管理（含语音识别页）下方非密钥输入框全部升级为 5+ 主流预设的可编辑 SelectBox，
   密钥框按 C12 保持掩码输入，下拉联动、置脏与保存闭环可用。
"""
import io
import unittest
from pathlib import Path
from unittest import mock

import infra.model_pool as model_pool
import pet_models_tabs
import pet_models_ui
import pet_settings_ui
import speech_settings_ui
import ui_icons
import ui_tokens
from account_inputs import PasswordInput
from contract.pet_settings_contract import TABS
from desktop_page_registry import (ASSET_ROSTER_ICON, NAV_LOCK_ICON, PAGE_NAV_ICONS,
                                   PROJECT_ACTION_ICONS, PROJECT_GROUP_ICONS)
from domain import speech_api
from scripts.build_nav_icons import ICONS, STAGE_FILE_BASES
from tests.test_ui_batch7_settings_models import Batch7Case, _button, _buttons, _descendants
from ui_tokens import NAV_ICON_SIZE

MAIN_UI_ICON_KEYS = (
    set(PAGE_NAV_ICONS.values())
    | {ASSET_ROSTER_ICON, NAV_LOCK_ICON, 'settings', 'back', 'project_files',
       'library', 'library_settings', 'recycle', 'recycle_purge'}
    | set(PROJECT_GROUP_ICONS.values())
    | set(PROJECT_ACTION_ICONS.values())
)

EXPECTED_TABS = (
    ('basic', '基础功能'),
    ('model', '三虎模型配置'),
    ('model_config', '模型配置'),
    ('level', '自动化等级'),
    ('token', 'Token 节省'),
    ('budget', '预算'),
    ('skills', 'SKILL 管理'),
    ('dev', '开发信息'),
)

# REQ-UI-MODEL-PAGE-2 已退役旧「模型组/权重」UI 字段，其余 12 个非密钥单行字段均保持 5+ 预设可编辑下拉。
MODEL_DROPDOWN_FIELDS = (
    'model', 'label', 'base_url', 'key_env', 'context_length', 'note',
    'rpm', 'max_output', 'temperature', 'timeout', 'retries', 'program',
)

SPEECH_FIVE_PLUS_FIELDS = (
    'model', 'base_url', 'key_env', 'language', 'silence_ms', 'max_seconds',
    'timeout', 'offline.python', 'offline.cache_dir', 'offline.threads',
    'offline.vad_trailing_ms',
)


def _toplevels(root):
    return [w for w in root.winfo_children() if w.winfo_class() == 'Toplevel']


class SettingsIconZeroReuseTests(Batch7Case):
    """需求 A：8 枚设置专属图标与主界面 0 复用，且日夜主题自动重染。"""

    def test_eight_dedicated_settings_icons_do_not_overlap_main_ui_keys_or_codepoints(self):
        self.assertEqual(tuple(TABS), EXPECTED_TABS)
        tab_keys = [key for key, _title in TABS]
        self.assertEqual(set(pet_settings_ui.TAB_ICONS), set(tab_keys))
        settings_icons = list(pet_settings_ui.TAB_ICONS.values())
        self.assertEqual(len(settings_icons), 8)
        self.assertEqual(len(set(settings_icons)), 8, '8 个目录图标键必须互不重复')
        for icon_key in settings_icons:
            self.assertTrue(icon_key.startswith('settings_'), icon_key)
            self.assertNotIn(icon_key, MAIN_UI_ICON_KEYS, '严禁复用主界面图标键')
            self.assertIn(icon_key, ICONS, '必须在 build_nav_icons.ICONS 登记')
        settings_codepoints = [ICONS[k] for k in settings_icons]
        self.assertEqual(len(set(settings_codepoints)), 8, '8 枚设置图标码位必须互不重复')
        other_codepoints = (
            {cp for key, cp in ICONS.items() if key not in settings_icons}
            | set(STAGE_FILE_BASES.values())
        )
        self.assertTrue(set(settings_codepoints).isdisjoint(other_codepoints),
                        '设置图标码位不得与主界面/阶段图标码位重叠')
        from PIL import Image
        for icon_key in settings_icons:
            path = ui_icons._NAV_DIR / f'{icon_key}.png'
            self.assertTrue(path.is_file(), f'缺少图标文件: {path}')
            with Image.open(path) as img:
                rgba = img.convert('RGBA')
                self.assertEqual(rgba.size, (NAV_ICON_SIZE, NAV_ICON_SIZE), icon_key)
                self.assertIsNotNone(rgba.getchannel('A').getbbox(), f'{icon_key} 不应为空白图')

    def test_hub_left_rail_loads_all_eight_icons_and_retints_on_theme_switch(self):
        original_theme = ui_tokens.current_theme()
        self.addCleanup(lambda: (ui_tokens.set_theme(original_theme), ui_icons.retint_nav_icons()))
        ui_tokens.set_theme('day')
        win = self._hub('basic')
        self.assertEqual(len(win._pet_tabs), 8)
        images_before = {}
        for key, _title in EXPECTED_TABS:
            btn = win._pet_tabs[key]
            icon_key = pet_settings_ui.TAB_ICONS[key]
            self.assertEqual(btn._nav_icon_name, icon_key)
            self.assertEqual(str(btn.cget('compound')), 'left')
            img_raw = btn.cget('image')
            img_name = img_raw[0] if isinstance(img_raw, tuple) else str(img_raw)
            self.assertTrue(img_name, f'{key} 按钮缺少图标')
            images_before[key] = win.tk.call(img_name, 'cget', '-data')
        ui_tokens.set_theme('night')
        ui_icons.retint_nav_icons()
        win.update_idletasks()
        for key, _title in EXPECTED_TABS:
            btn = win._pet_tabs[key]
            img_raw = btn.cget('image')
            img_name = img_raw[0] if isinstance(img_raw, tuple) else str(img_raw)
            night_data = win.tk.call(img_name, 'cget', '-data')
            self.assertNotEqual(night_data, images_before[key], f'{key} 夜间主题重染后图标应换色')


class EmbeddedModelConfigTests(Batch7Case):
    """需求 B：「模型配置」成为左栏标准项，在右侧内嵌显示且绝不弹出 Toplevel。"""

    def test_clicking_model_config_tab_embeds_without_popup_and_wires_save_and_dirty(self):
        win = self._hub('basic')
        self.assertIn('model_config', win._pet_tabs)
        order = [str(w.cget('text')) for w in win._pet_nav.winfo_children()]
        self.assertEqual(order, [title for _key, title in EXPECTED_TABS])
        self.assertEqual(order[order.index('三虎模型配置') + 1], '模型配置')
        before_tops = set(_toplevels(self.root))
        with mock.patch.object(self.pet, 'open_model_manager') as popup:
            win._pet_tabs['model_config'].invoke()
            win.update()
        popup.assert_not_called()
        self.assertEqual(set(_toplevels(self.root)), before_tops, '不得新弹 Toplevel 窗口')
        self.assertEqual(pet_settings_ui.current(win), 'model_config')
        self.assertEqual(str(win._pet_tabs['model_config'].cget('style')), 'Selected.Nav.TButton')
        page = win._pet_pages['model_config']
        self.assertTrue(page.winfo_ismapped())
        seam = win._pet_seams['model_config']
        self.assertIn('manager', seam)
        self.assertFalse(win._pet_footer.winfo_ismapped())
        # 选下拉置脏 → 切页与关窗均触发确认守卫
        entries = seam['entries']
        entries['note'].set('备用兜底线路')
        entries['note'].event_generate('<<ComboboxSelected>>')
        win.update()
        self.assertTrue(pet_settings_ui.hub_dirty(win))
        with mock.patch.object(self.pet, 'confirm_start', return_value=False) as confirm:
            pet_settings_ui.select(win, 'basic')
            self.assertTrue(confirm.called)
            self.assertEqual(pet_settings_ui.current(win), 'model_config')
        with mock.patch('pet_settings_ui.ask_confirmation', return_value=False) as ask:
            self.assertFalse(pet_settings_ui.request_close(win))
            self.assertTrue(ask.called)
            self.assertTrue(win.winfo_exists())
        # 编辑区就地保存当前模型
        entries['model'].set('deepseek-chat')
        entries['model'].event_generate('<<ComboboxSelected>>')
        win.update()
        with mock.patch.object(self.pet, 'save_pool') as save_pool:
            _button(win, '保存当前').invoke()
        save_pool.assert_called_once()
        self.assertEqual(save_pool.call_args.args[0]['model'], 'deepseek-chat')
        self.assertTrue(win.winfo_exists())

    def test_embedded_model_config_keeps_actions_visible_at_hub_sizes(self):
        win = self._hub('model_config')
        for geometry in (pet_settings_ui.HUB_GEOMETRY, '%dx%d' % pet_settings_ui.HUB_MIN):
            win.geometry(geometry)
            win.update()
            bottom = win.winfo_rooty() + win.winfo_height()
            for label in ('+ 新建模型', '检测全部', '删除', '保存当前', '测试'):
                btn = _button(win, label)
                self.assertTrue(btn.winfo_ismapped(), (geometry, label))
                self.assertLessEqual(btn.winfo_rooty() + btn.winfo_height(), bottom + 1,
                                     (geometry, label))

    def test_standalone_open_manager_still_works(self):
        win = self._manager_window()
        self.assertTrue(win.winfo_exists())
        self.assertEqual(win.title(), pet_models_ui.MANAGER_TITLE)


class SpeechTabInModelManagerTests(Batch7Case):
    """需求 C：移除「语音识别…」按钮，在左上角分段纳入「语音识别」原地展示并保存。"""

    def test_no_speech_button_and_speech_segment_switches_in_place(self):
        self.assertEqual(pet_models_tabs.MODES, ('API', 'Desktop', 'CLI', '语音识别'))
        win = self._manager_window()
        self.assertFalse([b for b in _buttons(win) if str(b.cget('text')) == '语音识别…'],
                         '不得再保留独立「语音识别…」按钮')
        self.assertIn('语音识别', win._pet_mode_buttons)
        with mock.patch.object(speech_api, 'read_settings', return_value=dict(speech_api.DEFAULTS)), \
                mock.patch.object(speech_api, 'api_key', return_value=''):
            win._pet_mode_buttons['语音识别'].invoke()
            win.update()
        self.assertEqual(win._pet_mode.get(), '语音识别')
        for label in ('+ 新建模型', '检测全部', '删除'):
            self.assertFalse([b for b in _buttons(win)
                              if str(b.cget('text')) == label and b.winfo_ismapped()],
                             f'切到语音识别时应隐藏模型动作钮 {label}')
        self.assertFalse(win._pet_cards.winfo_ismapped(), '切到语音识别时应隐藏模型卡片列表')
        # 语音识别内嵌面板展示完整控件并可经底部保存
        manager = win._pet_reload.__self__
        speech = manager._speech_panel
        self.assertIsNotNone(speech)
        speech['vars']['model'].set('paraformer-realtime-v2')
        speech['field_widgets']['model'].event_generate('<<ComboboxSelected>>')
        win.update()
        self.assertTrue(speech['is_dirty']())
        # 脏状态切回 API 先确认，拒绝留原地
        with mock.patch.object(self.pet, 'confirm_start', return_value=False) as confirm:
            win._pet_mode_buttons['API'].invoke()
            win.update()
        self.assertTrue(confirm.called)
        self.assertEqual(win._pet_mode.get(), '语音识别')
        # 点底部「保存」保存语音设置
        with mock.patch.object(speech_settings_ui.speech_api, 'save_settings') as save_s, \
                mock.patch.object(speech_settings_ui.speech_api, 'save_dictionary') as save_d:
            _button(win, '保存语音设置').invoke()
        save_s.assert_called_once()
        self.assertEqual(save_s.call_args.args[0]['model'], 'paraformer-realtime-v2')
        save_d.assert_called_once()
        self.assertFalse(win.winfo_exists())

    def test_embedded_speech_tab_saves_in_place(self):
        win = self._hub('model_config')
        seam = win._pet_seams['model_config']
        with mock.patch.object(speech_api, 'read_settings', return_value=dict(speech_api.DEFAULTS)), \
                mock.patch.object(speech_api, 'api_key', return_value=''):
            seam['mode_buttons']['语音识别'].invoke()
            win.update()
        speech = seam['manager']._speech_panel
        speech['vars']['silence_ms'].set('600')
        speech['field_widgets']['silence_ms'].event_generate('<<ComboboxSelected>>')
        win.update()
        self.assertTrue(pet_settings_ui.hub_dirty(win))
        with mock.patch.object(speech_settings_ui.speech_api, 'save_settings') as save_s, \
                mock.patch.object(speech_settings_ui.speech_api, 'save_dictionary') as save_d:
            _button(win, '保存语音设置').invoke()
        save_s.assert_called_once()
        self.assertEqual(save_s.call_args.args[0]['silence_ms'], '600')
        save_d.assert_called_once()
        self.assertTrue(win.winfo_exists())


class FiveMainstreamDropdownsTests(Batch7Case):
    """需求 D：模型管理与语音识别下方非密钥输入框全部升级为 5+ 选项的可编辑 SelectBox；密钥框保持 C12 掩码。"""

    def test_model_manager_inputs_are_editable_selectboxes_with_five_presets_and_secret_masked(self):
        win = self._manager_window()
        entries = win._pet_entries
        provider_vals = tuple(str(v) for v in win._pet_provider_box.cget('values'))
        self.assertGreaterEqual(len(provider_vals), 5, provider_vals)
        self.assertNotIn('readonly', win._pet_provider_box.state())
        for key in MODEL_DROPDOWN_FIELDS:
            widget = entries[key]
            self.assertEqual(widget.winfo_class(), 'TCombobox', f'{key} 必须升级为 SelectBox')
            self.assertNotIn('readonly', widget.state(), f'{key} 必须保持可编辑 state=normal')
            vals = tuple(str(v) for v in widget.cget('values'))
            self.assertGreaterEqual(len(vals), 5, f'{key} 默认预设不足 5 项: {vals}')
        # 安全红线 C12：密钥框保持 PasswordInput 掩码且不提供下拉预设
        self.assertIsInstance(win._pet_key_entry, PasswordInput)
        self.assertEqual(win._pet_key_entry.mask, '*')
        self.assertEqual(str(win._pet_key_entry.local.cget('show')), '*')
        self.assertNotEqual(win._pet_key_entry.local.winfo_class(), 'TCombobox')

    def test_model_and_label_dropdowns_update_by_modality_and_mode_and_trigger_fill_label(self):
        win = self._manager_window()
        entries = win._pet_entries
        # 切换 API 模态：文本 / 图片 / 语音 / 视频各 5 个不同预设
        seen_sets = []
        for modality_label in ('文本', '图片', '语音', '视频'):
            win._pet_modality_box.set(modality_label)
            win._pet_modality_box.event_generate('<<ComboboxSelected>>')
            win.update()
            models = tuple(str(v) for v in entries['model'].cget('values'))
            labels = tuple(str(v) for v in entries['label'].cget('values'))
            self.assertEqual(len(models), 5, (modality_label, models))
            self.assertEqual(len(labels), 5, (modality_label, labels))
            seen_sets.append(models)
        self.assertEqual(len(set(seen_sets)), 4, '四种模态应对应各自 5 项主流模型')
        # 选回文本并在 model 下拉选中某项：自动置脏且联动 fill_label
        win._pet_modality_box.set('文本')
        win._pet_modality_box.event_generate('<<ComboboxSelected>>')
        win._pet_reload.__self__._dirty = False
        entries['label'].delete(0, 'end')
        entries['model'].set('deepseek-chat')
        entries['model'].event_generate('<<ComboboxSelected>>')
        win.update()
        self.assertTrue(win._pet_reload.__self__._dirty, '<<ComboboxSelected>> 必须置脏')
        self.assertTrue(entries['label'].get().strip(), '选中模型后应自动联动填充显示名')
        # 切到 Desktop / CLI：模型/显示名/程序路径各刷新为 5 项
        win._pet_reload.__self__._dirty = False
        for mode in ('Desktop', 'CLI'):
            win._pet_mode.set(mode)
            win.update()
            self.assertEqual(len(entries['model'].cget('values')), 5, mode)
            self.assertEqual(len(entries['label'].cget('values')), 5, mode)
            self.assertGreaterEqual(len(entries['program'].cget('values')), 5, mode)

    def test_speech_single_line_inputs_are_editable_selectboxes_with_five_presets(self):
        win = self._manager_window()
        with mock.patch.object(speech_api, 'read_settings', return_value=dict(speech_api.DEFAULTS)), \
                mock.patch.object(speech_api, 'api_key', return_value=''):
            win._pet_mode_buttons['语音识别'].invoke()
            win.update()
        speech = win._pet_reload.__self__._speech_panel
        for key in SPEECH_FIVE_PLUS_FIELDS:
            widget = speech['field_widgets'][key]
            self.assertEqual(widget.winfo_class(), 'TCombobox', f'语音字段 {key} 必须为 SelectBox')
            self.assertNotIn('readonly', widget.state(), f'语音字段 {key} 必须可编辑')
            vals = tuple(str(v) for v in widget.cget('values'))
            self.assertGreaterEqual(len(vals), 5, f'语音字段 {key} 预设不足 5 项: {vals}')
        for key in ('hotword', 'ai_prompt'):
            widget = speech['dict_widgets'][key]
            self.assertEqual(widget.winfo_class(), 'TCombobox', f'词典字段 {key} 必须为 SelectBox')
            self.assertNotIn('readonly', widget.state(), f'词典字段 {key} 必须可编辑')
            vals = tuple(str(v) for v in widget.cget('values'))
            self.assertGreaterEqual(len(vals), 5, f'词典字段 {key} 预设不足 5 项: {vals}')
        # 替换词表是多行文本域，保持 TextArea
        self.assertEqual(speech['dict_widgets']['replace'].winfo_class(), 'Text')


if __name__ == '__main__':
    unittest.main()
