# -*- coding: utf-8 -*-
"""宠物贴片自检（模型池、默认档位、开机自启、菜单反馈、日报与项目记忆）：自原 test_pet_ui.py 按测试类拆分，断言与夹具原样保留。"""
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
if PROGRAM not in sys.path:
    sys.path.insert(0, PROGRAM)
os.chdir(PROGRAM)

from pet_ui_test_support import (
    _Event,
    _Point,
    _Registry,
    PetTestCase,
    FakeWinreg,
)
import infra.model_pool as model_pool
import model_secrets
import pet_models_ui
import pet_agent
import pet_bus
import pet_report
import stage_flow
from ui import pet_cloud
import ui.pet_ui as pet_ui
import selftest_sandbox

selftest_sandbox.isolate(pet_ui)

class ModelPoolTests(PetTestCase):
    """第 43 期：模型设置＝模型池（规格《三虎模型设置》）——右键两栏 ＋ 两扇窗 ＋ 即时生效。"""

    def _walk(self, widget, kind):
        found = []
        if isinstance(widget, kind):
            found.append(widget)
        for child in widget.winfo_children():
            found.extend(self._walk(child, kind))
        return found

    def test_local_provider_survives_save_and_reload(self):
        win = self.pet.open_model_manager()
        self.addCleanup(win.destroy)
        win._pet_mode.set('Desktop')
        win._pet_entries['model'].delete(0, 'end')
        win._pet_entries['model'].insert(0, 'Google Gemini 4 Argon')
        win._pet_provider.set('Google')
        buttons = {str(w.cget('text')): w for w in self._walk(win, self.ttk.Button)}
        buttons['保存'].invoke()
        win.update()
        self.assertEqual(win._pet_provider.get(), 'Google')
        records = model_pool.pool(program=self.pet.program)
        picked = next(key for key, item in records.items() if item['model'] == 'Google Gemini 4 Argon')
        win._pet_select_model(picked)
        win.update()
        self.assertEqual(win._pet_provider.get(), 'Google')
        item = records[picked]
        self.assertEqual(item['provider'], 'desktop')
        self.assertEqual(model_pool.provider_name(picked, item), 'Google')

    def test_search_reports_progress_and_background_failure(self):
        import threading
        import tkinter as tk
        from unittest.mock import patch
        win = self.pet.open_model_manager()
        self.addCleanup(win.destroy)
        win._pet_mode.set('Desktop')
        win._pet_entries['model'].insert(0, 'Google Gemini 4 Argon')
        release = threading.Event()
        self.addCleanup(release.set)
        def find(*args):
            release.wait(1)
            raise RuntimeError('测试搜寻异常')
        with patch('workflow_settings.find_model_program', side_effect=find):
            win._pet_detect_program(quiet=False)
            self.assertIn('正在搜寻', win._pet_hint.get())
            release.set()
            done = tk.BooleanVar(master=win)
            win.after(250, lambda: done.set(True))
            win.wait_variable(done)
        self.assertIn('测试搜寻异常', win._pet_hint.get())

    def test_search_late_result_does_not_overwrite_new_mode(self):
        import threading
        import tkinter as tk
        from unittest.mock import patch
        win = self.pet.open_model_manager()
        self.addCleanup(win.destroy)
        win._pet_mode.set('Desktop')
        win._pet_entries['model'].insert(0, 'Gemini')
        release = threading.Event()
        self.addCleanup(release.set)
        def find(*args):
            release.wait(1)
            return 'C:/old/Gemini.exe'
        with patch('workflow_settings.find_model_program', side_effect=find):
            win._pet_detect_program(quiet=False)
            win._pet_mode.set('API')
            release.set()
            done = tk.BooleanVar(master=win)
            win.after(200, lambda: done.set(True))
            win.wait_variable(done)
        self.assertEqual(win._pet_entries['program'].get(), '')
        self.assertNotIn('已自动找到', win._pet_hint.get())

    def test_search_preserves_manual_path_and_can_close_while_running(self):
        import threading
        import tkinter as tk
        from unittest.mock import patch
        win = self.pet.open_model_manager()
        win._pet_mode.set('Desktop')
        win._pet_entries['model'].insert(0, 'Gemini')
        release = threading.Event()
        self.addCleanup(release.set)
        def find(*args):
            release.wait(1)
            return 'C:/found/Gemini.exe'
        with patch('workflow_settings.find_model_program', side_effect=find):
            win._pet_detect_program(quiet=False)
            win._pet_entries['program'].insert(0, 'C:/manual/Gemini.exe')
            release.set()
            done = tk.BooleanVar(master=win)
            win.after(200, lambda: done.set(True))
            win.wait_variable(done)
            self.assertEqual(win._pet_entries['program'].get(), 'C:/manual/Gemini.exe')
            release.clear()
            win._pet_detect_program(quiet=False)
            win.destroy()
            release.set()
            self.win.update()

    def test_explicit_modes_override_old_record_and_search_current_model(self):
        from unittest.mock import patch
        win = self.pet.open_model_manager()
        self.addCleanup(win.destroy)
        # 页签化后列表按调用方式过滤：先切到 Desktop 页签，claude-desktop-app 才在列表里。
        win._pet_mode.set('Desktop')
        win._pet_select_model('claude-desktop-app')
        win.update()
        self.assertEqual(win._pet_mode.get(), 'Desktop')
        entries = win._pet_entries
        entries['model'].delete(0, 'end')
        entries['model'].insert(0, 'Google Gemini 4')
        self.assertEqual(entries['program'].get(), '')
        with patch('workflow_settings.find_model_program', side_effect=ValueError('未找到 Gemini')) as find:
            win._pet_detect_program(quiet=False)
            import tkinter as tk
            done = tk.BooleanVar(master=win)
            win.after(200, lambda: done.set(True))
            win.wait_variable(done)
        find.assert_called_once_with('Google Gemini 4', 'Desktop')
        self.assertEqual(entries['program'].get(), '')
        self.assertIn('未找到 Gemini', win._pet_hint.get())
        win._pet_mode.set('API')
        self.assertFalse(win._pet_program_row.winfo_manager())
        self.assertTrue(all(w.winfo_manager() for w in win._pet_api_controls))
        self.assertEqual(win._pet_read_form()['call_mode'], 'API')
        win._pet_mode.set('CLI')
        self.assertTrue(win._pet_program_row.winfo_manager())
        self.assertTrue(all(not w.winfo_manager() for w in win._pet_api_controls))
        self.assertEqual(win._pet_read_form()['call_mode'], 'CLI')

    def test_manager_layout_leaves_room_for_the_model_list(self):
        """说明与标题同一行；紧凑输入框纵向内边距归零；非密钥表单项为可编辑预设下拉；本地调用时「模型 ID」叫「程序名」。"""
        import pet_models_ui
        from tkinter import ttk
        from ui_widgets import LineInput
        win = self.pet.open_model_manager()
        self.addCleanup(win.destroy)
        win.update_idletasks()
        notes = [w for w in self._walk(win, ttk.Label) if w.cget('text') == pet_models_ui.NOTE_MANAGER]
        titles = [w for w in self._walk(win, ttk.Label) if w.cget('text') == pet_models_ui.MANAGER_TITLE]
        self.assertEqual(len(notes), 1)
        self.assertIn(notes[0].master, [title.master for title in titles], '说明跟在标题右侧，同一行')
        regular = LineInput(win); self.addCleanup(regular.destroy)
        compact = win._pet_search_entry
        self.assertIsInstance(compact, pet_models_ui.CompactLineInput)
        self.assertLessEqual(compact.winfo_reqheight(), regular.winfo_reqheight() * 0.7)
        self.assertEqual(win._pet_entries['note'].winfo_class(), 'TCombobox')
        label = win._pet_labels['model']
        for mode, text in (('Desktop', '程序名'), ('CLI', '程序名'), ('API', '模型 ID')):
            win._pet_mode.set(mode)
            self.assertEqual(label.cget('text'), text, mode)

    def test_desktop_form_hides_api_fields_and_persists_application(self):
        from unittest.mock import patch
        win = self.pet.open_model_manager()
        self.addCleanup(win.destroy)
        # 页签化后列表按调用方式过滤：先切 Desktop 页签才能选到 claude-desktop-app。
        win._pet_mode.set('Desktop')
        win._pet_select_model('claude-desktop-app')
        win.update()
        # R1423 用户要求：本机 Claude 显示厂商名，表单仍是应用路径
        self.assertEqual(win._pet_provider.get(), 'anthropic')
        self.assertEqual(win._pet_program_row.winfo_manager(), 'grid')
        self.assertTrue(all(not w.winfo_manager() for w in win._pet_api_controls))
        executable = self.pet.program / 'Claude.exe'
        executable.write_bytes(b'test executable; never launched')
        win._pet_entries['program'].insert(0, str(executable))
        buttons = {str(w.cget('text')): w for w in self._walk(win, self.ttk.Button)}
        with patch('model_pool.probe', side_effect=AssertionError('desktop must not use HTTP')):
            buttons['检查程序'].invoke()
        buttons['保存'].invoke()
        self.assertEqual(model_pool.pool(program=self.pet.program)['claude-desktop-app']['program'], str(executable))
        self.assertEqual(model_pool.pool(program=self.pet.program)['claude-desktop-app']['call_mode'], 'Desktop')
        win._pet_mode.set('API')
        win._pet_select_model('gpt-4o')
        win.update()
        self.assertFalse(win._pet_program_row.winfo_manager())
        self.assertTrue(all(w.winfo_manager() for w in win._pet_api_controls))

    def test_typing_model_id_automatically_searches_after_debounce(self):
        import tkinter as tk
        from unittest.mock import patch
        win = self.pet.open_model_manager()
        self.addCleanup(win.destroy)
        win._pet_mode.set('Desktop')
        model = win._pet_entries['model']
        done = tk.BooleanVar(master=win)
        with patch('workflow_settings.find_model_program', return_value='C:/apps/Gemini.exe') as find:
            model.delete(0, 'end')
            model.insert(0, 'Google')
            model.delete(0, 'end')
            model.insert(0, 'Google Gemini 4')
            win.after(600, lambda: done.set(True))
            win.wait_variable(done)
        find.assert_called_once_with('Google Gemini 4', 'Desktop')
        self.assertEqual(win._pet_entries['program'].get(), 'C:/apps/Gemini.exe')

    def test_anthropic_provider_keeps_desktop_form_for_local_claude(self):
        """R1423：本机 Claude 选 anthropic 仍是应用路径表单，存储协议仍为 desktop。"""
        win = self.pet.open_model_manager()
        self.addCleanup(win.destroy)
        # 页签化后列表按调用方式过滤：先切 Desktop 页签才能选到 claude-desktop-app。
        win._pet_mode.set('Desktop')
        win._pet_select_model('claude-desktop-app')
        win.update()
        win._pet_provider.set('anthropic')
        win._pet_provider_box.event_generate('<<ComboboxSelected>>')
        win.update()
        self.assertEqual(win._pet_program_row.winfo_manager(), 'grid')
        self.assertTrue(all(not w.winfo_manager() for w in win._pet_api_controls))
        executable = self.pet.program / 'Claude.exe'
        executable.write_bytes(b'test executable; never launched')
        win._pet_entries['program'].delete(0, 'end')
        win._pet_entries['program'].insert(0, str(executable))
        buttons = {str(w.cget('text')): w for w in self._walk(win, self.ttk.Button)}
        buttons['保存'].invoke()
        saved = model_pool.pool(program=self.pet.program)['claude-desktop-app']
        self.assertEqual(saved['provider'], 'desktop')
        self.assertEqual(saved['program'], str(executable))
        self.assertEqual(saved['wire_api'], 'chat')
        # 新建模型：模型 ID 是本机引擎、Provider 选 anthropic，同样显示应用路径。
        buttons['+ 新建模型'].invoke()
        win._pet_entries['model'].insert(0, 'claude-desktop-app')
        win._pet_entries['model'].event_generate('<KeyRelease>')
        win._pet_provider.set('anthropic')
        win.update()
        self.assertEqual(win._pet_program_row.winfo_manager(), 'grid')
        self.assertTrue(all(not w.winfo_manager() for w in win._pet_api_controls))
        # 调用方式由新增选择器决定，不再被模型名称隐式切换。
        win._pet_mode.set('API')
        win._pet_entries['model'].delete(0, 'end')
        win._pet_entries['model'].insert(0, 'claude-opus-api')
        win._pet_entries['model'].event_generate('<KeyRelease>')
        win._pet_provider.set('anthropic')
        win.update()
        self.assertFalse(win._pet_program_row.winfo_manager())
        self.assertTrue(all(w.winfo_manager() for w in win._pet_api_controls))

    def test_cli_entry_pointing_at_claude_desktop_gui_is_rejected(self):
        """R1425：命令行 Claude 条目不能保存为 Claude Desktop 图形程序路径。"""
        win = self.pet.open_model_manager()
        self.addCleanup(win.destroy)
        buttons = {str(w.cget('text')): w for w in self._walk(win, self.ttk.Button)}
        buttons['+ 新建模型'].invoke()
        win._pet_mode.set('CLI')
        entries = win._pet_entries
        entries['label'].insert(0, 'Claude Code Cli')
        entries['model'].insert(0, 'claude code')
        win._pet_provider.set('desktop')
        win.update()
        gui = self.pet.program / 'WindowsApps' / 'Claude_2.1.0.0_x64__x' / 'app' / 'Claude.exe'
        gui.parent.mkdir(parents=True)
        gui.write_bytes(b'test executable; never launched')
        entries['program'].delete(0, 'end')
        entries['program'].insert(0, str(gui))
        buttons['保存'].invoke()
        self.assertIn('图形界面', win._pet_hint.get())
        self.assertNotIn('claude code', model_pool.pool(program=self.pet.program))

    def model_menu(self):
        index = self.pet.menu_index['model']
        return self.pet.menu.nametowidget(self.pet.menu.entrycget(index, 'menu'))

    def menu_labels(self, menu):
        return ['---' if menu.type(index) == 'separator' else menu.entrycget(index, 'label')
                for index in range(menu.index('end') + 1)]

    def test_the_shipped_pool_and_auto_are_the_only_menu_entries(self):
        labels = self.menu_labels(self.model_menu())
        self.assertEqual(labels[0], '✓ 自动')
        self.assertIn('DeepSeek V4 Flash', labels)
        self.assertIn('DeepSeek V4 Pro', labels)
        self.assertIn('GPT-4o', labels)
        self.assertIn('Qwen-Max', labels)
        self.assertEqual(labels[-1], '+ 新增模型…')

    def test_the_probe_message_reports_how_long_it_took(self):
        """规格：成功那句写「连接成功，延迟 xxx ms」，失败写清原因（HTTP 码 ＋ 错误）。"""
        original = model_secrets.PROTECTOR
        def protector(data, decrypt=False, label=''):
            payload = bytes(data)
            if decrypt:
                if not payload.startswith(b'test:'):
                    raise ValueError('bad test secret')
                return payload[5:][::-1]
            return b'test:' + payload[::-1]
        model_secrets.PROTECTOR = protector
        self.addCleanup(setattr, model_secrets, 'PROTECTOR', original)
        record = model_pool.save_local_key({'model': 'm', 'base_url': 'https://x.test/v1'},
                                           'sk-test-1234', self.pet.program)
        self.pet.probe_transport = lambda url, body, head, timeout: {'ok': True, 'status': 200, 'data': {}}
        said = pet_models_ui.probe_line(record, self.pet)
        self.assertIn('连接成功，延迟', said)
        self.assertIn('ms', said)
        self.pet.probe_transport = lambda url, body, head, timeout: {'ok': False, 'status': 401,
                                                                     'error': 'HTTP 401：unauthorized'}
        self.assertIn('HTTP 401', pet_models_ui.probe_line(record, self.pet))

    def test_api_configuration_lists_desktop_agents_in_the_model_pool(self):
        """桌面 Agent 是阶段配置可选模型，不是模型管理底部的启动按钮。"""
        records = model_pool.pool(program=self.pet.program)
        self.assertIn('chatgpt-desktop', records)
        self.assertIn('claude-desktop', records)
        win = self.pet.open_model_manager()
        self.addCleanup(win.destroy)
        self.assertFalse(hasattr(win, '_pet_open_claude'))

    def test_the_settings_entry_is_a_single_command_keeping_entries_constant(self):
        """UX-SANHU-FIX：右键删除重复 7 项设置级联，保留单一「打开设置…」入口与 SETTINGS_ENTRIES 契约常量。"""
        import pet_settings_ui
        self.assertIn('settings', self.pet.menu_index)
        index = self.pet.menu_index['settings']
        self.assertEqual(self.pet.menu.type(index), 'command')
        self.assertEqual(self.pet.menu.entrycget(index, 'label'), '打开设置…')
        self.assertEqual(pet_ui.SETTINGS_ENTRIES, tuple(pet_settings_ui.TABS),
                         'SETTINGS_ENTRIES 常量仍与设置页 TABS 同步')

    def test_switching_a_model_persists_and_ticks_it(self):
        self.assertEqual(self.pet.set_tier('deepseek-v4-pro'), 'deepseek-v4-pro')
        self.assertIn('已切换到 DeepSeek V4 Pro', self.pet.notice)
        self.assertEqual(self.pet.agent.client.config['pro_model'], 'deepseek-v4-pro')
        self.assertEqual(self.pet.agent.client.config['flash_model'], 'deepseek-v4-pro')
        self.assertIn('✓ DeepSeek V4 Pro', self.menu_labels(self.model_menu()))
        tasks = model_pool.agent_models(program=self.pet.program)
        self.assertEqual(tasks['default'], 'deepseek-v4-pro', '写盘读回来还是这一档')

    def test_unknown_model_is_refused(self):
        self.assertEqual(self.pet.set_tier('不存在'), self.pet.tier)

    def test_deleting_the_current_model_falls_back_to_auto(self):
        self.pet.set_tier('deepseek-v4-pro')
        self.pet.delete_pool_model('deepseek-v4-pro')
        self.assertEqual(self.pet.tier, model_pool.AUTO)

    def test_the_fallback_rides_along_in_the_client_config(self):
        self.pet.set_tier('deepseek-v4-pro')
        fallback = self.pet.agent.client.config['fallback']
        self.assertEqual(fallback['pro_model'], 'deepseek-v4-flash')

    def test_an_external_tier_can_still_be_plugged_in(self):
        before = dict(pet_ui.TIER_MODELS)

        def restore():
            pet_ui.TIER_MODELS.clear()
            pet_ui.TIER_MODELS.update(before)
            pet_ui.TIER_CYCLE = tuple(pet_ui.TIER_MODELS)
            pet_ui.TIER_NAMES = {key: value[0] for key, value in pet_ui.TIER_MODELS.items()}

        self.addCleanup(restore)
        options = self.pet.register_model('local', '本地 Llama', {'force_tier': 'local'})
        self.assertEqual(options['local'], '本地 Llama')
        self.assertIn('本地 Llama', self.menu_labels(self.model_menu()))
        self.assertEqual(self.pet.set_tier('local'), 'local')
        self.assertEqual(self.pet.agent.client.config['force_tier'], 'local')
        self.assertIn('本地 Llama', self.pet.model_label())

    def test_the_settings_window_lists_the_four_dimensions(self):
        win = self.pet.open_model_settings()
        self.addCleanup(win.destroy)
        combos = self._walk(win, self.ttk.Combobox)
        self.assertEqual(len(combos), 4)
        self.assertEqual(combos[0].get(), model_pool.AUTO_LABEL, '默认模型开局是「自动」')
        self.assertEqual(combos[1].get(), 'DeepSeek V4 Pro')
        self.assertEqual(combos[2].get(), 'DeepSeek V4 Pro')
        self.assertEqual(combos[3].get(), 'DeepSeek V4 Flash')

    def test_saving_claude_code_refreshes_the_open_stage_model_picker(self):
        """R2862 契约：阶段面板不再内嵌模型下拉，模型选择收口到 StageModelPicker；
        「存池即刷 open 选择器」的契约平移到它身上（provider 下拉已不存在）。"""
        from unittest.mock import patch
        import stage_model_picker
        import stage_config
        import workflow_settings
        workflow_settings.clear_desktop_installation_cache()
        self.addCleanup(workflow_settings.clear_desktop_installation_cache)
        finder = patch.object(workflow_settings, 'find_program', return_value='test-claude.exe')
        finder.start()
        self.addCleanup(finder.stop)
        picker = stage_model_picker.StageModelPicker(self.win, self.fake, 'script')
        self.addCleanup(picker.destroy)
        stage_config.put(self.fake.root, 'script', model='claude-desktop')
        picker.refresh_models()
        self.pet.save_pool({'label': 'Claude Code Cli', 'model': 'claude code',
                            'provider': 'desktop'})
        self.assertIn('Claude Code Cli', [label for options in picker.groups.values() for _id, label in options])
        self.assertEqual(picker.model_id(), 'claude-desktop')
        picker.set_model('claude code')
        self.assertEqual(picker.model_id(), 'claude code')
        self.assertEqual(model_pool.desktop_engine(picker.model_id()), 'claude')

    def test_the_manager_adds_and_deletes_a_model(self):
        win = self.pet.open_model_manager()
        self.addCleanup(win.destroy)
        self.pet.save_pool({'label': '本地 Llama', 'model': 'llama-3-8b',
                            'base_url': 'http://127.0.0.1:8000/v1', 'key_env': '', 'wire_api': 'chat'})
        self.assertIn('本地 Llama', self.menu_labels(self.model_menu()))
        self.pet.delete_pool_model('llama-3-8b')
        self.assertNotIn('本地 Llama', self.menu_labels(self.model_menu()))

    def test_manager_delete_uses_the_currently_selected_row_and_persists_it(self):
        """列表刷新后，删除按钮也只能删除当前高亮的模型，重读配置不得复活。"""
        win = self.pet.open_model_manager()
        self.addCleanup(win.destroy)
        self.pet.asker = lambda _title, _text: True
        self.pet.save_pool({'label': '删除目标', 'model': 'delete-target',
                            'base_url': 'http://127.0.0.1:8000/v1', 'key_env': '', 'wire_api': 'chat'})
        win._pet_reload()
        win._pet_select_model('delete-target')
        self.assertEqual(win._pet_delete_one(), 'delete-target')
        self.assertNotIn('delete-target', self.pet.agent_model_records())
        self.assertNotIn('delete-target', model_pool.pool(program=self.pet.program))

    def test_manager_can_delete_builtin_claude_desktop(self):
        win = self.pet.open_model_manager()
        self.addCleanup(win.destroy)
        self.pet.asker = lambda _title, _text: True
        # 页签化后列表按调用方式过滤：先切 Desktop 页签才能选到 claude-desktop-app。
        win._pet_mode.set('Desktop')
        win._pet_select_model('claude-desktop-app')
        self.assertEqual(win._pet_delete_one(), 'claude-desktop-app')
        self.assertNotIn('claude-desktop-app', self.pet.agent_model_records())
        self.assertNotIn('claude-desktop-app', model_pool.pool(program=self.pet.program))
        win._pet_reload()
        self.assertNotIn('claude-desktop-app', win._pet_cards.item_ids())

    def test_save_and_close_right_after_delete_does_not_save_it_back(self):
        """R2166：删完表单还停在那一条，紧接着保存并关窗不得把它按表单内容存回模型池。

        REQ-UI-MODEL-PAGE-2（2026-11-26 重构）：底栏已取消，右顶栏为「保存」，关窗统一经 ×／Esc（`_pet_cancel`）。"""
        win = self.pet.open_model_manager()
        self.addCleanup(lambda: win.winfo_exists() and win.destroy())
        self.pet.asker = lambda _title, _text: True
        self.pet.save_pool({'label': '删后关窗', 'model': 'delete-then-close',
                            'base_url': 'http://127.0.0.1:8000/v1', 'key_env': '', 'wire_api': 'chat'})
        win._pet_reload()
        win._pet_select_model('delete-then-close')
        self.assertEqual(win._pet_entries['model'].get(), 'delete-then-close')
        self.assertEqual(win._pet_delete_one(), 'delete-then-close')
        self.assertEqual(win._pet_entries['model'].get(), '', '删掉之后表单不能还停在那一条')

        def walk(widget):
            for child in widget.winfo_children():
                yield child
                yield from walk(child)

        def button(text):
            return [child for child in walk(win)
                    if child.winfo_class() == 'TButton' and str(child.cget('text')) == text][0]
        button('保存').invoke()
        self.assertNotIn('delete-then-close', model_pool.pool(program=self.pet.program))
        win._pet_cancel()
        self.assertFalse(win.winfo_exists())
        self.assertNotIn('delete-then-close', model_pool.pool(program=self.pet.program))

    def test_the_manager_refills_a_custom_provider_name(self):
        """自定义厂商保存后重新选中，输入框必须仍显示用户填写的名字。"""
        win = self.pet.open_model_manager()
        self.addCleanup(win.destroy)
        self.pet.save_pool({'label': '自定义 GPT', 'model': 'custom-gpt',
                            'provider': '我的厂商', 'base_url': 'https://example.invalid/v1'})
        win._pet_reload()
        win._pet_select_model('custom-gpt')
        self.win.update_idletasks()
        self.assertEqual(win._pet_provider.get(), '我的厂商')

    def test_the_manager_stores_a_typed_key_encrypted_and_shows_only_four_characters(self):
        """规格里的第二种放法：密钥直接输进来 → 系统加密存本机，界面只露前 4 位 ＋ ****。"""
        original = model_secrets.PROTECTOR
        def protector(data, decrypt=False, label=''):
            payload = bytes(data)
            if decrypt:
                if not payload.startswith(b'test:'):
                    raise ValueError('bad test secret')
                return payload[5:][::-1]
            return b'test:' + payload[::-1]
        model_secrets.PROTECTOR = protector
        self.addCleanup(setattr, model_secrets, 'PROTECTOR', original)
        win = self.pet.open_model_manager()
        self.addCleanup(win.destroy)
        entries = win._pet_entries
        entries['label'].insert(0, '我的本地模型')
        entries['model'].insert(0, 'llama-3-8b')
        entries['base_url'].insert(0, 'http://127.0.0.1:8000/v1')
        win._pet_key_entry.insert(0, 'sk-local-abcdef')
        item = win._pet_save_key()
        self.assertIsNotNone(item, win._pet_hint.get())
        records = self.pet.agent_model_records()
        self.assertIn('llama-3-8b', records, '存密钥时顺手把这条也写进池子')
        self.assertEqual(records['llama-3-8b']['key_env'], 'MODEL_LLAMA_3_8B_KEY')
        self.assertEqual(model_pool.local_key_of(records['llama-3-8b'], self.pet.program),
                         'sk-local-abcdef')
        self.assertEqual(model_pool.status(records['llama-3-8b'], self.pet.program), (True, '可用'))
        shown = win._pet_key_state()
        self.assertIn('sk-l****', shown)
        self.assertNotIn('sk-local-abcdef', shown, '整把密钥不许摆到界面上')
        self.assertEqual(win._pet_key_entry.get(), '', '存完把输入框清掉，不回显整把密钥')
        self.assertIn('我的本地模型', self.menu_labels(self.model_menu()))
        self.assertTrue(win._pet_clear_key())
        self.assertEqual(model_pool.local_key_of(records['llama-3-8b'], self.pet.program), '')


class DefaultLevelTests(PetTestCase):
    """第 44 期：出厂默认档＝半自动（用户附件《模型管理》关键决策第 5 条）。

    这一档「免费步骤自己跑、花钱的先问一句」，所以默认状态下三虎真的在干活；等级仍可随时
    由那排猫爪／设置页改，改完写进配置，下次开机照用户选的来。
    """

    def setUp(self):
        super().setUp()
        self.now = 1000.0
        self.pet.clock = lambda: self.now

    def test_a_fresh_pet_starts_in_hint_mode(self):
        self.assertEqual(pet_agent.DEFAULT_LEVEL, 'hint')
        self.assertEqual(self.pet.agent.level, 'hint')

    def test_new_fixture_has_no_previous_automatic_blocker(self):
        self.assertIs(self.pet.auto, stage_flow.AUTO)
        self.assertIsNone(self.pet.auto.blocked)
        self.assertFalse(self.pet.auto.armed)
        self.assertEqual(self.pet.auto.history, [])

    def test_the_hint_level_does_not_wake_the_next_step(self):
        """第 64 期任务 7：默认档＝只提醒——只看着、不替用户推进下一步。"""
        self.assertEqual(self.pet.agent.level, 'hint')
        self.pet.machine.start('script')
        self.pet.machine.complete('script')
        self.assertEqual(self.pet.tune_advance(at=self.now), '')
        self.assertEqual(self.fake.advances, [])

    def test_the_automatic_levels_wake_the_next_step(self):
        """半自动／全自动档：下一步会被叫醒（开机第一拍只叫醒、不出声）。"""
        self.pet.agent.set_level('semi')
        self.pet.machine.start('script')
        self.pet.machine.complete('script')
        self.assertEqual(self.pet.tune_advance(at=self.now), '')
        self.assertEqual(self.fake.advances, ['script_structure'],
                         '剧本完成后先进入正式的结构剧本阶段')

    def test_the_default_level_never_runs_paid_steps(self):
        """第 64 期任务 7：默认「只提醒」档连免费步骤都不代跑，更不会自己花钱。"""
        decision = self.pet.agent.approve('video.generate')
        self.assertFalse(decision['run'], '会花钱的按钮不代按')
        self.assertFalse(decision['confirm'], '只提醒档只提示，不弹确认框')

    def test_the_chosen_level_is_what_the_next_start_uses(self):
        self.pet.set_level('hint')
        saved = pet_agent.load_settings(program=self.pet.program)
        self.assertEqual(saved['level'], 'hint', '用户选过的档盖过出厂那一档')


class AutostartTests(unittest.TestCase):
    """开机自启：只用假注册表，真注册表一行都不写。"""

    def test_command_points_at_the_launcher_next_to_the_program(self):
        command = pet_ui.autostart_command(PROGRAM)
        self.assertIn('启动漫剧制作助手.pyw', command)
        self.assertTrue(command.startswith('"'))

    def test_toggle_writes_then_removes_the_run_entry(self):
        api = FakeWinreg()
        control = pet_ui.Autostart(api=api)
        self.assertTrue(control.available)
        self.assertEqual(control.get(), '')
        self.assertFalse(control.enabled())
        self.assertTrue(control.toggle(PROGRAM))
        self.assertIn('启动漫剧制作助手.pyw', api.values[pet_ui.AUTOSTART_NAME])
        self.assertTrue(control.enabled())
        self.assertFalse(control.toggle(PROGRAM))
        self.assertEqual(api.values, {})

    def test_clear_is_idempotent(self):
        self.assertTrue(pet_ui.Autostart(api=FakeWinreg()).clear())

    def test_without_winreg_everything_degrades(self):
        control = pet_ui.Autostart(api=None)
        self.assertFalse(control.available)
        self.assertIsNone(control.get())
        self.assertFalse(control.set('x'))
        self.assertFalse(control.clear())
        self.assertFalse(control.toggle(PROGRAM))

    def test_broken_registry_is_reported_not_raised(self):
        self.assertIsNone(pet_ui.Autostart(api=FakeWinreg(fail_read=True)).get())
        self.assertFalse(pet_ui.Autostart(api=FakeWinreg(fail_write=True)).set('x'))


class AutostartMenuTests(PetTestCase):
    """第 19 期：开机自启默认开着，功能栏里不再占一行（标签仍跟着注册表走）。"""

    def test_label_follows_the_registry(self):
        self.pet._autostart = pet_ui.Autostart(api=FakeWinreg())
        self.assertEqual(self.pet.autostart_label(), '开机自启（未开启）')
        self.assertTrue(self.pet.toggle_autostart())
        self.assertEqual(self.pet.autostart_label(), '开机自启（已开启）')
        self.assertFalse(self.pet.toggle_autostart())
        self.assertEqual(self.pet.autostart_label(), '开机自启（未开启）')

    def test_label_without_a_registry_says_unsupported(self):
        self.pet._autostart = pet_ui.Autostart(api=None)
        self.assertEqual(self.pet.autostart_label(), '开机自启（本机不支持）')
        self.assertFalse(self.pet.toggle_autostart())

    def test_the_run_entry_is_written_by_default(self):
        """attach 不传 autostart 就把 Run 项补上；传 False 则一个字节都不动注册表。"""
        api = FakeWinreg()
        self.pet._autostart = pet_ui.Autostart(api=api)
        self.assertTrue(self.pet.autostart_default())
        self.assertIn('启动漫剧制作助手.pyw', api.values[pet_ui.AUTOSTART_NAME])
        api2 = FakeWinreg()
        quiet = pet_ui.attach(self.fake, autostart=False)
        self.assertIsInstance(quiet, pet_ui.Pet)

    def test_an_unsupported_registry_is_not_an_error(self):
        self.pet._autostart = pet_ui.Autostart(api=None)
        self.assertFalse(self.pet.autostart_default())
        self.assertEqual(self.pet.errors, [])


class MenuFeedbackTests(PetTestCase):
    """第 13／19 期：右键菜单的每一项都必须说一句，不再有「点了没提示」的项。"""

    # 自己就是「看得见的开关」的项单列用例，不进「逐项都要说话」那条循环。
    EXCLUDED = ('向三虎提问',)

    def menu_items(self):
        """菜单上**点得动**的那几项（第 60 期第 2 条起栏里多了几行灰色小标题：它们也是
        type='command'，但 state='disabled'，不是给用户按的）。"""
        items = []
        for index in range(self.pet.menu.index('end') + 1):
            if self.pet.menu.type(index) != 'command':
                continue
            if str(self.pet.menu.entrycget(index, 'state')) == 'disabled':
                continue
            items.append((index, self.pet.menu.entrycget(index, 'label')))
        return items

    def index_of(self, label):
        for index, text in self.menu_items():
            if text == label:
                return index
        raise AssertionError('菜单里没有这一项：' + label)

    def test_the_menu_keeps_only_the_daily_entries(self):
        labels = [text for _index, text in self.menu_items()]
        self.assertIn('向三虎提问', labels)
        self.assertIn(pet_ui.PANEL_MENU_LABEL, labels)      # 第 44 期：附件里的说法「打开三虎面板」
        for gone in ('独立小窗（桌面常驻贴片）', '和宠物说话（云朵框）',
                     '显示主窗口（从常驻切回主界面）'):
            self.assertNotIn(gone, labels, gone + ' 已经搬走／删掉')
        for name in ('level', 'roam', 'tray', 'autostart', 'showmain', 'toast', 'window'):
            self.assertNotIn(name, self.pet.menu_index, name + ' 还挂在菜单上')
        # 第 44 期：'quit' 按附件摆回来了（最后一行），所以这几项里不再点名它。
        self.assertIn('quit', self.pet.menu_index)
        # 第 22 期：「暂停」与「稍后再说」回到一级栏，进度面板也回到功能栏。
        for name in ('pause', 'snooze', 'panel'):
            self.assertIn(name, self.pet.menu_index, name + ' 应当在一级功能栏上')

    def groups(self):
        """菜单按分隔线切成几块（逐块给出条目名）。"""
        blocks, current = [], []
        for index in range(self.pet.menu.index('end') + 1):
            if self.pet.menu.type(index) == 'separator':
                blocks.append(current)
                current = []
                continue
            current.append(str(self.pet.menu.entrycget(index, 'label')))
        blocks.append(current)
        return blocks

    def test_the_menu_is_split_into_four_blocks(self):
        """UX-SANHU-FIX：右键菜单重构为 4 块 3 条分隔线，按使用频率从上往下排列、删重补缺。"""
        blocks = self.groups()
        self.assertEqual(blocks[0], ['向三虎提问', '推进当前阶段', pet_ui.PANEL_MENU_LABEL],
                         '① 高频主操作（最顶部，不加小标题）')
        self.assertEqual(blocks[1], ['【任务控制】', self.pet.pause_label(), '重试失败项',
                                     pet_ui.DETAIL_MENU_LABEL, '跳过当前阻塞项'],
                         '② 任务控制')
        self.assertEqual(blocks[2], ['【常用工具】', self.pet.model_label(), '语音识别设置…',
                                     self.pet.theme_label(), self.pet.snooze_label(), '今日日报'],
                         '③ 常用工具')
        self.assertEqual(blocks[3], ['打开设置…', pet_ui.QUIT_LABEL],
                         '④ 设置入口与退出程序（退出固定最底行）')
        self.assertEqual(len(blocks), 4, '4 块结构清晰紧凑')

    def test_the_section_headings_are_readable_but_not_clickable(self):
        """中间两块各带一行灰色禁用小标题——用户扫一眼就知道去哪块找。"""
        headings = [(index, str(self.pet.menu.entrycget(index, 'label')))
                    for index in range(self.pet.menu.index('end') + 1)
                    if self.pet.menu.type(index) == 'command'
                    and str(self.pet.menu.entrycget(index, 'state')) == 'disabled']
        self.assertEqual([text for _index, text in headings],
                         ['【任务控制】', '【常用工具】'])
        for index, _text in headings:
            self.assertEqual(self.pet.menu.invoke(index), '', '标题按不动')

    def test_every_item_says_something_after_it_runs(self):
        import ui_tokens
        origin = ui_tokens.current_theme()
        self.addCleanup(ui_tokens.set_theme, origin)
        self.pet._autostart = pet_ui.Autostart(api=FakeWinreg())
        cloud = self.pet.cloud()
        for index, label in self.menu_items():
            if label in self.EXCLUDED:
                continue
            self.pet.notice = ''
            self.pet.bstate.last_broadcast = ''
            del cloud.lines[:]
            self.pet.menu.invoke(index)
            self.assertTrue(self.pet.notice, label + ' 没有留下提示')
            expected = ' '.join(self.pet.notice.split())
            if label in (pet_ui.PANEL_MENU_LABEL, pet_ui.DETAIL_MENU_LABEL):
                self.assertIn(self.pet.notice.splitlines()[0], cloud.transcript(),
                              label + ' 没有在三虎提示框展示内容')
            else:
                self.assertTrue(any(expected in line for line in cloud.lines),
                                label + ' 没有播报出去（云朵可保留完成／警告前缀）')

    def test_the_progress_entry_is_gone_but_the_voice_stays(self):
        """进度面板从功能栏搬走，改成三虎自己挑时机的圆形气泡。"""
        for gone in ('进度面板（主窗口右上角浮层）', '收集事件'):
            with self.assertRaises(AssertionError):
                self.index_of(gone)
        self.assertTrue(self.pet.progress_voice(force=True))
        self.assertEqual(self.pet.cloud().shape, pet_cloud.SHAPE_ROUND)

    def test_a_shown_menu_keeps_the_cloud_shut_and_says_it_afterwards(self):
        """第 47 期第 4 条：右键下拉栏显示期间三虎不冒云朵框；栏一收起，那句话补上。"""
        seen = []

        def fake_popup(x, y):
            seen.append(self.pet._menu_open)
            self.assertEqual(self.pet.broadcast('栏里冒出来的话'), '', '栏开着时先压住')
            self.assertFalse(self.pet.cloud_visible(), '栏开着时不冒云朵框')

        original = self.pet.menu.tk_popup
        self.pet.menu.tk_popup = fake_popup
        self.addCleanup(setattr, self.pet.menu, 'tk_popup', original)
        self.pet.popup_at(10, 20)
        self.assertEqual(seen, [True], '弹栏期间标记要是开着的')
        self.assertFalse(self.pet._menu_open, '栏收起后标记清掉')
        self.assertFalse(self.pet.bstate.held_broadcast, '压住的那句话已经补说出去')
        self.assertTrue(self.pet.cloud_visible(), '收起后补上那句话')
        self.assertIn('栏里冒出来的话', self.pet.cloud().transcript())

    def test_the_menu_entries_own_windows_are_not_blocked(self):
        """栏里那几项自己要开的东西照旧：栏开着时「向三虎提问」照样把对话打开。"""
        original = self.pet.menu.tk_popup
        self.pet.menu.tk_popup = lambda x, y: self.pet.menu.invoke(self.index_of('向三虎提问'))
        self.addCleanup(setattr, self.pet.menu, 'tk_popup', original)
        self.pet.popup_at(10, 20)
        self.assertTrue(self.pet.cloud().visible)
        self.assertEqual(self.pet.cloud().shape, pet_cloud.SHAPE_CLOUD, '开的是对话框，不是随手一句')

    def test_the_chat_entry_opens_the_cloud_and_says_so(self):
        self.pet.menu.invoke(self.index_of('向三虎提问'))
        self.assertIsNotNone(self.pet.chat)
        self.assertTrue(self.pet.cloud().visible)
        self.assertIn('云朵框已打开', self.pet.notice)

    def test_retrying_the_failures_says_what_happened(self):
        self.pet.menu.invoke(self.index_of('重试失败项'))
        self.assertIn('没有待确认的项', self.pet.notice)
        self.assertIn('没有待确认的项', self.pet.cloud().transcript())
        self.pet.agent.fail('keyframe', '超时', attempt=4)
        self.pet.menu.invoke(self.index_of('重试失败项'))
        self.assertIn('已重试失败项：1 项', self.pet.notice)
        self.assertNotIn('pet', self.fake.kicks)
        self.assertIn('keyframe', self.fake.advances)

    def test_collecting_the_events_says_how_many(self):
        """收集事件并进了进度气泡：时机由三虎自己挑。

        第 49 期第 3 条：一个事件都没抽到时就一个字都不说——「已收集 0 个事件」什么也没说。
        """
        self.assertEqual(self.pet.collect_events(), 0)
        self.assertNotIn('已收集', self.pet.notice, '抽到 0 个就别报数')
        self.pet.pump = lambda *args, **kwargs: 3
        self.pet.collect_events()
        self.assertIn('已收集 3 个事件', self.pet.notice, '真抽到了才报')

    def test_an_action_that_blows_up_is_recorded_and_still_speaks(self):
        def boom():
            raise RuntimeError('动作坏了')

        self.assertIsNone(self.pet.act(boom))
        self.assertTrue(any(name == 'act' for name, _text in self.pet.errors))
        self.assertTrue(self.pet.cloud().visible, '动作出错也要让用户看见')


class PetClickTests(PetTestCase):
    """第 16 期：单击三虎＝收起云朵框＋唤出功能下拉栏；等级／模型在子菜单里一次点到位。"""

    def test_clicking_the_pet_flips_the_cloud_both_ways(self):
        """第 19 期：单击直接开／关云朵框（原来借道下拉栏，才有「再点一下关不掉」）。"""
        self.assertIsNotNone(self.pet.open_chat())
        self.assertTrue(self.pet.cloud().visible)
        self.pet.flip_chat()
        self.assertFalse(self.pet.cloud().visible, '再点一下就是收起来')
        self.assertIsNone(self.pet.chat)
        self.assertTrue(self.pet.muted(), '刚点掉的云朵框要安静一会儿，别被自动播报顶回来')
        self.pet.flip_chat()
        self.assertTrue(self.pet.cloud().visible, '再点一下又打开')

    def test_a_single_click_waits_for_the_double_click(self):
        self.pet.pet_click(_Event(widget=self.pet.canvas))
        self.assertIsNotNone(self.pet._click_at, '单击等第二下：双击要接管')

    def test_a_double_click_cancels_the_pending_menu(self):
        self.pet.pet_click(_Event(widget=self.pet.canvas))
        self.assertIsNotNone(self.pet._click_at)
        self.pet.double_click()
        self.assertIsNone(self.pet._click_at, '双击＝和三虎说话，待唤出的菜单要撤掉')
        self.assertTrue(self.pet.cloud().visible)

    def test_the_menu_is_ordered_by_how_often_it_is_used(self):
        labels = [self.pet.menu.entrycget(index, 'label')
                  for index in range(self.pet.menu.index('end') + 1)
                  if self.pet.menu.type(index) == 'command']
        self.assertEqual(labels[0], '向三虎提问')
        self.assertLess(labels.index('推进当前阶段'), labels.index('重试失败项'))
        self.assertLess(labels.index('重试失败项'), labels.index(pet_ui.DETAIL_MENU_LABEL))
        self.assertNotIn('生成今日日报', labels, '旧文案已改为「今日日报」')
        self.assertIn('今日日报', labels)
        self.assertEqual(labels[-1], pet_ui.QUIT_LABEL, '「退出程序」固定在最后一行')

    def test_the_paws_set_the_level_directly(self):
        """等级从菜单搬到三虎身旁的猫爪上：点哪一爪就是哪一档，一次点到位。"""
        self.assertNotIn('level', self.pet.menu_index, '菜单里不再重复一栏等级')
        step = pet_ui.PAW_STEP
        self.pet.paw_click(_Point(step + pet_ui.PAW_SIZE // 2))
        self.assertEqual(self.pet.agent.level, pet_agent.LEVELS[1])
        self.assertEqual(self.pet.notice, pet_ui.LEVEL_SWITCH_NOTES[pet_agent.LEVELS[1]])
        self.pet.paw_click(_Point(pet_ui.PAW_SIZE // 2))
        self.assertEqual(self.pet.agent.level, pet_agent.LEVELS[0])
        self.assertIsNone(self.pet.paw_click(_Point(10 * step)), '超出范围的点击不认领')

    def test_the_model_submenu_sets_the_model_directly(self):
        """第 43 期：子菜单不再写死三档，条目来自模型池；点哪一条就是哪一条。"""
        index = self.pet.menu_index['model']
        self.assertEqual(self.pet.menu.type(index), 'cascade')
        sub = self.pet.menu.nametowidget(self.pet.menu.entrycget(index, 'menu'))
        self.assertEqual(sub.entrycget(0, 'label'), '✓ 自动')
        sub.invoke(2)
        self.assertEqual(self.pet.tier, 'deepseek-v4-pro')
        self.assertIn('已切换到 DeepSeek V4 Pro', self.pet.notice)


class ReportTests(PetTestCase):
    """第 6 期：日报／周报的数据来源、落盘位置与菜单接线。"""

    def menu_items(self):
        """菜单上**点得动**的那几项（第 60 期第 2 条起栏里多了几行灰色小标题：它们也是
        type='command'，但 state='disabled'，不是给用户按的）。"""
        items = []
        for index in range(self.pet.menu.index('end') + 1):
            if self.pet.menu.type(index) != 'command':
                continue
            if str(self.pet.menu.entrycget(index, 'state')) == 'disabled':
                continue
            items.append((index, self.pet.menu.entrycget(index, 'label')))
        return items

    def index_of(self, label):
        for index, text in self.menu_items():
            if text == label:
                return index
        raise AssertionError('菜单里没有这一项：' + label)

    def record(self, prompt, cached, tier='flash'):
        self.pet.agent.client.ledger.record('deepseek-v4-' + tier,
                                            {'prompt_tokens': prompt, 'completion_tokens': 10,
                                             'cached_tokens': cached}, tier=tier)

    def test_the_menu_carries_only_the_entries_that_are_left(self):
        """第 19 期精简：日报／周报、显示主窗口、收集事件都从功能栏搬走或删掉了。

        第 44 期：用户附件把「退出」摆回功能栏最后一行，所以它不再算「搬走的那一项」。
        """
        labels = [text for _index, text in self.menu_items()]
        for label in ('向三虎提问', '推进当前阶段', '今日日报', pet_ui.QUIT_LABEL):
            self.assertIn(label, labels)
        for gone in ('生成今日日报', '生成本周周报', '显示主窗口（从常驻切回主界面）',
                     '收集事件', '系统托盘（未开启）', '一键执行（重试＋补首帧＋日报）'):
            self.assertNotIn(gone, labels, gone + ' 已经搬走／删掉')
        self.assertEqual([text for text in labels if text.startswith('开机自启')], [],
                         '开机自启默认开着，不再占一行')

    def test_report_numbers_come_from_the_ledger(self):
        self.record(100, 80, 'flash')
        self.record(100, 0, 'pro')
        tokens = self.pet.report()['tokens']
        self.assertEqual((tokens['prompt'], tokens['completion'], tokens['cached']), (200, 20, 80))
        self.assertEqual((tokens['entries'], tokens['flash_entries']), (2, 1))
        self.assertEqual(tokens['hit_rate'], 0.4)
        self.assertEqual(tokens['flash_share'], 0.5)
        self.assertEqual(tokens['budget'], 2000000)

    def test_report_progress_matches_the_state_machine(self):
        self.pet.machine.start('script')
        self.pet.machine.detail('script', 3, 6)
        data = self.pet.report()
        self.assertEqual(data['percent'], round(100.0 * 0.5 / len(pet_bus.STAGES), 1))
        self.assertEqual((data['stage'], data['done_stages']), ('script', 0))
        self.assertEqual(data['total_stages'], len(pet_bus.STAGES))
        # gather() 把阶段表归一成 {阶段: 状态字符串}，日报正文也是这么用的。
        self.assertEqual(data['stages']['script'], 'running')
        self.assertEqual(data['project'], self.fake.root.name)

    def test_daily_report_writes_today_and_merges_the_summary(self):
        data, path = self.pet.daily_report()
        self.assertEqual(path, pet_report.report_path(self.fake.root, pet_report.day_key()))
        self.assertTrue(path.is_file())
        self.assertEqual(self.pet.report_path, path)
        self.assertIn('# 制作日报', path.read_text(encoding='utf-8'))
        self.assertEqual([row['day'] for row in pet_report.load_rows(self.fake.root)], [data['day']])

    def test_daily_report_without_a_project_is_a_noop(self):
        self.pet.desktop.root = None
        self.pet.core()
        self.assertEqual(self.pet.daily_report(), (None, None))
        self.assertIsNone(self.pet.report_path)

    def test_weekly_report_reads_the_daily_summary(self):
        self.pet.daily_report()
        path, totals = self.pet.weekly_report()
        self.assertEqual(path, pet_report.weekly_path(self.fake.root, pet_report.day_key()))
        self.assertEqual(self.pet.weekly_path, path)
        self.assertEqual(totals['days'], 1)
        self.assertIn('# 制作周报', path.read_text(encoding='utf-8'))

    def test_the_daily_report_still_works_without_a_menu_entry(self):
        """按钮搬走了，功能留着：一键执行与关软件那一眼照旧会出日报。"""
        with self.assertRaises(AssertionError):
            self.index_of('生成今日日报')
        self.assertIsNotNone(self.pet.daily_report()[0])
        self.assertTrue(self.pet.report_path.is_file())


class ShotStatsTests(unittest.TestCase):
    """shot_stats：只数 JSON 里记着的路径、且文件真的在盘上——首帧名带哈希后缀，按名字猜必然数错。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name) / '星空项目'
        self.work = self.project / 'storyboard' / '分镜拆分'
        self.work.mkdir(parents=True)
        self.frames = self.project / 'storyboard' / 'frames'
        self.frames.mkdir(parents=True)

    def write(self, shots, name='EP001_分镜.json'):
        path = self.work / name
        path.write_text(json.dumps({'episode_id': 'EP001', 'shots': shots}, ensure_ascii=False),
                        encoding='utf-8')
        return path

    def png(self, name):
        (self.frames / name).write_bytes(b'\x89PNG\r\n\x1a\n')

    def test_counts_shots_and_the_frames_that_really_exist(self):
        self.png('EP001_SH001_aaaa.png')
        path = self.write([{'id': 'SH001', 'frame': 'frames/EP001_SH001_aaaa.png'},
                           {'id': 'SH002', 'frame': 'frames/EP001_SH002_bbbb.png'},
                           {'id': 'SH003'}])
        self.assertEqual(pet_ui.shot_stats([path]), (3, 1))

    def test_deleted_frames_are_not_counted(self):
        self.png('EP001_SH001_aaaa.png')
        path = self.write([{'id': 'SH001', 'frame': 'frames/EP001_SH001_aaaa.png', 'frame_deleted': True}])
        self.assertEqual(pet_ui.shot_stats([path]), (1, 0))

    def test_frames_pointing_outside_the_storyboard_folder_are_not_counted(self):
        (self.project / 'outside.png').write_bytes(b'\x89PNG\r\n\x1a\n')
        path = self.write([{'id': 'SH001', 'frame': '../outside.png'}])
        self.assertEqual(pet_ui.shot_stats([path]), (1, 0))

    def test_junk_shots_are_ignored_but_the_rest_still_count(self):
        path = self.write(['乱写的', {'frame': 'frames/x.png'}, {'id': 'SH001'}])
        self.assertEqual(pet_ui.shot_stats([path]), (1, 0))

    def test_broken_json_and_missing_files_give_zero(self):
        bad = self.work / '坏.json'
        bad.write_text('{不是 JSON', encoding='utf-8')
        self.assertEqual(pet_ui.shot_stats([bad, self.work / '没有这个文件.json']), (0, 0))

    def test_shots_that_are_not_a_list_give_zero(self):
        path = self.work / '怪.json'
        path.write_text(json.dumps({'shots': {'SH001': {}}}), encoding='utf-8')
        self.assertEqual(pet_ui.shot_stats([path]), (0, 0))

    def test_no_paths_is_zero(self):
        self.assertEqual(pet_ui.shot_stats([]), (0, 0))
        self.assertEqual(pet_ui.shot_stats(None), (0, 0))


class AssetCountTests(unittest.TestCase):
    """asset_counts：登记的资产数＋真的有图的个数，口径与无人值守判断一致。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name) / '资产'
        self.base.mkdir()

    def test_counts_registered_and_ready_assets(self):
        (self.base / 'a.png').write_bytes(b'\x89PNG\r\n\x1a\n')
        (self.base / 'assets.json').write_text(json.dumps(
            {'ast_01': {'image': 'a.png'}, 'ast_02': {'image': 'b.png'}, 'ast_03': {}}), encoding='utf-8')
        self.assertEqual(pet_ui.asset_counts(self.base), (3, 1))

    def test_missing_library_is_zero(self):
        self.assertEqual(pet_ui.asset_counts(self.base / '不存在'), (0, 0))

    def test_broken_registry_is_zero(self):
        (self.base / 'assets.json').write_text('[1, 2]', encoding='utf-8')
        self.assertEqual(pet_ui.asset_counts(self.base), (0, 0))


class CountsTests(PetTestCase):
    """Pet.counts：日报里的真实计数全部来自盘上，读不出来的项写 0，绝不编。"""

    def test_empty_project_counts_everything_as_zero(self):
        counts = self.pet.counts()
        self.assertEqual(sorted(counts), sorted(pet_report.COUNT_KEYS))
        self.assertEqual(set(counts.values()), {0})

    def test_real_storyboard_frames_and_scripts_are_counted(self):
        work = self.fake.root / 'storyboard' / '分镜拆分'
        work.mkdir(parents=True)
        frames = self.fake.root / 'storyboard' / 'frames'
        frames.mkdir(parents=True)
        (frames / 'EP001_SH001_aaaa.png').write_bytes(b'\x89PNG\r\n\x1a\n')
        (work / 'EP001_分镜.json').write_text(json.dumps(
            {'episode_id': 'EP001', 'shots': [{'id': 'SH001', 'frame': 'frames/EP001_SH001_aaaa.png'},
                                              {'id': 'SH002'}]}, ensure_ascii=False), encoding='utf-8')
        writing = self.fake.root / 'writing'
        writing.mkdir(parents=True, exist_ok=True)
        (writing / '第1集剧本.md').write_text('# 剧本', encoding='utf-8')
        counts = self.pet.counts()
        self.assertEqual(counts['storyboards'], 1)
        self.assertEqual(counts['shots'], 2)
        self.assertEqual(counts['frames'], 1)
        self.assertEqual(counts['scripts'], 1)

    def test_a_broken_asset_library_is_reported_as_zero_not_raised(self):
        (self.fake.root / 'episode' / 'assets.json').write_text('[坏]', encoding='utf-8')
        self.assertEqual((self.pet.counts()['assets'], self.pet.counts()['ready_assets']), (0, 0))

    def test_report_data_carries_the_counts(self):
        data = self.pet.report()
        self.assertEqual(sorted(data['counts']), sorted(pet_report.COUNT_KEYS))


class TimingRowTests(PetTestCase):
    """面板与日报的耗时数字：全部来自状态机，没有产出单位就写「信息不足」。"""

    def measure(self, stage="keyframe", units=20, seconds=600.0):
        machine = self.pet.machine
        machine.start(stage)
        machine.detail(stage, units, units)
        machine.complete(stage)
        machine.elapsed[stage] = seconds
        return machine

    def test_the_panel_lists_the_two_new_rows(self):
        rows = dict(self.pet.rows())
        self.assertIn("阶段停留", rows)
        self.assertIn("平均单镜耗时", rows)

    def test_empty_measurements_say_so(self):
        rows = dict(self.pet.rows())
        self.assertEqual(rows["阶段停留"], "信息不足")
        self.assertEqual(rows["平均单镜耗时"], "信息不足")

    def test_the_panel_numbers_follow_the_machine(self):
        self.measure()
        rows = dict(self.pet.rows())
        self.assertEqual(rows["阶段停留"], "首帧管理 10:00")
        self.assertEqual(rows["平均单镜耗时"], "首帧管理 0:30/镜")

    def test_the_rows_are_named_pairs_of_label_and_value(self):
        rows = self.pet.rows()
        self.assertTrue(rows)
        for label, value in rows:
            self.assertTrue(str(label).strip(), "每一行都要有名字")
            self.assertIsInstance(value, str)

    def test_the_timings_payload_is_normalized(self):
        self.measure("assets", units=4, seconds=120.0)
        payload = self.pet.timings()
        self.assertEqual(payload["stages"]["assets"], 120.0)
        self.assertEqual(sorted(payload["units"]), sorted(pet_bus.STAGES))
        self.assertEqual(payload["rates"], {"assets": 30.0})

    def test_the_report_carries_the_timings(self):
        self.measure()
        data = self.pet.report()
        self.assertEqual(data["timings"]["rates"], {"keyframe": 30.0})
        self.assertEqual(data["timings"]["stages"]["keyframe"], 600.0)

    def test_the_daily_report_writes_the_two_lines(self):
        self.measure()
        _data, path = self.pet.daily_report()
        text = path.read_text(encoding="utf-8")
        self.assertIn("阶段停留：首帧管理 10:00", text)
        self.assertIn("平均耗时：首帧管理 0:30/镜", text)


class ProjectMemoryTests(PetTestCase):
    """第 37 期第 1 条：三虎要「记住所有项目」——登记表整本记下来，名字、状态、走到哪一步都答得出。"""

    def setUp(self):
        super().setUp()
        self.other = Path(self.tmp.name) / 'q'
        (self.other / '工作流任务' / '宠物').mkdir(parents=True)
        self.fake.projects = _Registry(str(self.fake.root), [
            {'name': '甲', 'path': str(self.fake.root)},
            {'name': '乙', 'path': str(self.other), 'status': 'completed'}])

    def test_every_project_is_remembered(self):
        rows = self.pet.projects_snapshot(force=True)
        self.assertEqual([row['name'] for row in rows], ['甲', '乙'])
        self.assertTrue(rows[0]['active'], '当前项目排最前')
        self.assertEqual(rows[1]['status'], '已完成')
        self.assertEqual(rows[0]['status'], '在制作')
        self.assertTrue(rows[0]['stage'], '每个项目都记住走到哪一步了')

    def test_the_list_is_cached_until_it_is_forced(self):
        first = self.pet.projects_snapshot(force=True)
        self.fake.projects.info['projects'].append({'name': '丙', 'path': str(self.other)})
        self.assertEqual(len(self.pet.projects_snapshot()), len(first), 'TTL 之内用缓存')
        self.assertEqual(len(self.pet.projects_snapshot(force=True)), len(first) + 1, '强制重读看得见新项目')

    def test_the_pet_reads_the_list_out_loud(self):
        text = self.pet.projects_text(force=True)
        self.assertIn('甲', text)
        self.assertIn('乙', text)
        self.assertIn('已完成', text)
        self.assertIn('2 个项目', text)

    def test_asking_about_projects_is_answered(self):
        result = self.pet.agent.dispatch('有哪些项目')
        self.assertEqual(result['plan']['intent'], 'projects')
        self.assertTrue(result['decision']['run'], '看一眼的事哪一档都放行')
        said = self.pet.run_plan(result)
        self.assertIn('甲', said)

    def test_the_model_also_sees_the_projects(self):
        context = self.pet.agent.context()
        self.assertIn('projects', context)
        self.assertIn('甲', ' '.join(context['projects']))
        self.assertIn('当前', ' '.join(context['projects']), '哪个是当前项目要说清')

    def test_no_projects_yet_says_so(self):
        self.fake.projects.info = {'active': None, 'projects': []}
        self.assertEqual(self.pet.projects_snapshot(force=True), [])
        self.assertIn('还没建过项目', self.pet.projects_text(force=True))

    def test_a_broken_registry_never_raises(self):
        self.fake.projects.info = {'active': None, 'projects': [{'name': '没路径'}, '不是对象']}
        self.assertEqual(self.pet.projects_snapshot(force=True), [])
        self.assertTrue(self.pet.projects_text(force=True))
        self.assertFalse(self.pet.errors, '坏数据只丢一行，不记成错误')

    def test_a_missing_host_registry_is_reported_not_read_from_disk(self):
        del self.fake.projects
        self.assertEqual(self.pet.projects_registry(), {})
        self.assertIn('projects.read', [name for name, _text in self.pet.errors],
                      '宿主没给登记表就报缺，不再自己去开 projects.json')
        self.assertEqual(self.pet.projects_snapshot(force=True), [])


if __name__ == '__main__':
    unittest.main()
