# -*- coding: utf-8 -*-
"""REQ-S01-53/54/55/56：客户端档案、PE 分类、探测与投递降级。"""
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import client_profiles
import desktop_send_choice
import environment_check
import infra.model_pool as model_pool
import workflow_engines
import workflow_settings


def fake_pe(path, subsystem):
    data = bytearray(0x200)
    data[:2] = b'MZ'
    struct.pack_into('<I', data, 0x3c, 0x80)
    data[0x80:0x84] = b'PE\0\0'
    struct.pack_into('<H', data, 0x80 + 24, 0x10b)
    struct.pack_into('<H', data, 0x80 + 24 + 68, subsystem)
    Path(path).write_bytes(data)
    return str(path)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    return path


class ProfileLoadingTests(unittest.TestCase):
    def test_req_s01_53_builtin_wins_and_user_entries_append(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            builtin = write_json(root / 'builtin.json', {
                'schema_version': 1,
                'profiles': [{'id': 'same', 'kind': 'desktop', 'display': '内置',
                              'delivery': 'paste'}],
            })
            user = write_json(root / 'user.json', {
                'profiles': [
                    {'id': 'same', 'kind': 'desktop', 'display': '用户覆盖'},
                    {'id': 'new-one', 'kind': 'cli'},
                ],
            })
            rows = client_profiles.load_profiles(builtin, user, refresh=True)
            self.assertEqual(rows['same']['display'], '内置')
            self.assertEqual(rows['new-one']['kind'], 'cli')
            self.assertEqual(rows['new-one']['delivery'], 'cli_stdin')
            self.assertEqual(rows['new-one']['detect']['exe_names'], [])

    def test_req_s01_53_missing_schema_and_bad_json_are_tolerated(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            builtin = write_json(root / 'builtin.json', {
                'profiles': [{'id': 'legacy', 'kind': 'desktop'}],
            })
            user = root / 'user.json'
            user.write_text('{bad json', encoding='utf-8')
            rows = client_profiles.load_profiles(builtin, user, refresh=True)
            self.assertEqual(rows['legacy']['delivery'], 'paste')
            self.assertEqual(rows['legacy']['display'], 'legacy')

    def test_req_s01_56_builtin_catalog_covers_every_known_client(self):
        rows = client_profiles.load_profiles(refresh=True)
        expected = {'chatgpt-desktop', 'codex-cli', 'claude-desktop', 'claude-code',
                    'qwen-code', 'opencode-desktop', 'opencode-cli', 'gemini-desktop',
                    'deepseek-harness', 'deepseek-harness-cli'}
        self.assertEqual(expected, set(rows))
        for item in rows.values():
            self.assertTrue(item['process_names'])
            self.assertTrue(item['delivery'])

    def test_req_s01_56_startup_read_does_not_scan_directories(self):
        with patch.object(Path, 'glob', side_effect=AssertionError('startup scan')):
            with patch.object(Path, 'rglob', side_effect=AssertionError('startup scan')):
                rows = client_profiles.load_profiles(refresh=True)
        self.assertTrue(rows)

    def test_req_s01_56_versioned_app_glob_finds_executable(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / 'app-1.15.0'
            folder.mkdir()
            exe = fake_pe(folder / 'Gemini.exe', 2)
            profile = {'id': 'gemini', 'kind': 'desktop', 'detect': {
                'known_globs': [str(Path(td) / 'app-*' / 'Gemini.exe')]}}
            self.assertEqual(client_profiles.detect_executable(profile), exe)


class PeClassificationTests(unittest.TestCase):
    def test_req_s01_55_gui_and_console_subsystems_are_read_without_execution(self):
        with tempfile.TemporaryDirectory() as td:
            gui = fake_pe(Path(td) / 'gui.exe', 2)
            console = fake_pe(Path(td) / 'console.exe', 3)
            broken = Path(td) / 'broken.exe'
            broken.write_bytes(b'MZ' + b'\0' * 10)
            self.assertEqual(client_profiles.pe_subsystem(gui), 'gui')
            self.assertEqual(client_profiles.pe_subsystem(console), 'console')
            self.assertEqual(client_profiles.pe_subsystem(broken), '')

    def test_req_s01_55_gui_adaptation_never_runs_the_file(self):
        with tempfile.TemporaryDirectory() as td:
            gui = fake_pe(Path(td) / 'My Desktop.exe', 2)
            runner = Mock(side_effect=AssertionError('GUI must not execute'))
            result = client_profiles.adapt_executable(gui, 'My Desktop', run=runner,
                                                      save_profile=False)
            self.assertTrue(result['ok'])
            self.assertEqual(result['profile']['kind'], 'desktop')
            self.assertEqual(result['profile']['delivery'], 'paste')
            runner.assert_not_called()

    def test_req_s01_55_console_probe_uses_timeout_and_parses_common_flags(self):
        with tempfile.TemporaryDirectory() as td:
            script = Path(td) / 'fake_cli.py'
            script.write_text('print("usage: fake --prompt TEXT")', encoding='utf-8')
            result = client_profiles.probe_cli([sys.executable, str(script)], timeout=5)
            self.assertTrue(result['ok'])
            self.assertEqual(result['invoke'], ['--prompt', '{prompt}'])
            self.assertEqual(result['delivery'], 'cli_arg')

            sleeper = Path(td) / 'sleeper.py'
            sleeper.write_text('import time; time.sleep(2)', encoding='utf-8')
            timeout = client_profiles.probe_cli([sys.executable, str(sleeper)], timeout=0.2)
            self.assertFalse(timeout['ok'])
            self.assertIn('超时', timeout['reason'])

    def test_req_s01_55_probe_exceptions_have_interactive_fallback(self):
        def failed(*args, **kwargs):
            raise OSError('denied')
        result = client_profiles.probe_cli(['missing.exe'], run=failed)
        self.assertFalse(result['ok'])
        self.assertEqual(result['invoke'], [])
        self.assertEqual(result['delivery'], 'cli_stdin')

    def test_req_s01_55_console_adaptation_records_derived_profile(self):
        with tempfile.TemporaryDirectory() as td:
            console = fake_pe(Path(td) / 'tool.exe', 3)
            completed = SimpleNamespace(stdout='usage: tool --prompt TEXT', stderr='', returncode=0)
            result = client_profiles.adapt_executable(
                console, 'Tool', run=lambda *a, **k: completed, save_profile=False)
            self.assertTrue(result['ok'])
            self.assertEqual(result['profile']['kind'], 'cli')
            self.assertEqual(result['profile']['invoke'], ['--prompt', '{prompt}'])

    def test_req_s01_55_saving_console_path_does_not_execute(self):
        with tempfile.TemporaryDirectory() as td:
            console = fake_pe(Path(td) / 'tool.exe', 3)
            runner = Mock(side_effect=AssertionError('save must not probe'))
            result = client_profiles.adapt_executable(
                console, 'Tool', run=runner, save_profile=False, probe=False)
            self.assertTrue(result['ok'])
            self.assertEqual(result['profile']['delivery'], 'cli_stdin')
            self.assertEqual(result['profile']['invoke'], [])
            runner.assert_not_called()

    def test_req_s01_55_cmd_probe_wraps_comspec(self):
        with tempfile.TemporaryDirectory() as td:
            launcher = Path(td) / 'tool.cmd'
            launcher.write_text('@echo off', encoding='utf-8')
            seen = []
            def run(command, **kwargs):
                seen.append(command)
                return SimpleNamespace(stdout='usage: tool --prompt TEXT', stderr='', returncode=0)
            result = client_profiles.probe_cli([str(launcher)], run=run)
            self.assertTrue(result['ok'])
            shell = client_profiles.os.environ.get('COMSPEC') or 'cmd.exe'
            self.assertEqual(seen[0][:3], [shell, '/c', str(launcher)])

    def test_req_s01_55_pet_manager_fills_model_id_from_path(self):
        import pet_models_ui

        class Var:
            def __init__(self, value=''):
                self.value = value
            def get(self):
                return self.value
            def set(self, value):
                self.value = value
            def insert(self, index, text):
                self.value = self.value[:index] + text + self.value[index:]

        with tempfile.TemporaryDirectory() as td:
            gui = fake_pe(Path(td) / 'New Tool.exe', 2)
            mode = Var('CLI')
            entries = {'model': Var('')}
            with patch.object(client_profiles, 'save_user_profile'):
                adapted, switched = pet_models_ui._derive_client_profile(
                    gui, 'New Tool', mode, entries, probe=False)
        self.assertTrue(adapted['ok'])
        self.assertEqual(switched, 'Desktop')
        self.assertEqual(mode.get(), 'Desktop')
        self.assertEqual(entries['model'].get(), adapted['profile']['id'])


class DeliveryFallbackTests(unittest.TestCase):
    def host(self):
        return SimpleNamespace(status=Mock(), notifier=Mock(),
                               async_=lambda fn, done: done(fn()))

    def test_req_s01_54_paste_exception_falls_back_to_clipboard(self):
        host = self.host()
        finish = Mock()
        with patch('contract.platform_tools.launch_windows_app'), \
                patch('codex_paste.paste_existing', side_effect=RuntimeError('uia failed')):
            desktop_send_choice.deliver_desktop_app(
                host, finish, 'r', 'task.md', '任务', '正文', r'C:\Tool.exe', 'Tool')
        self.assertEqual(finish.call_args.args[1], 'failed')
        self.assertIn('剪贴板', finish.call_args.args[2])
        self.assertIn('手动粘贴', finish.call_args.args[2])

    def test_req_s01_54_clipboard_delivery_does_not_call_paste(self):
        host = self.host()
        finish = Mock()
        with patch('contract.platform_tools.launch_windows_app'), \
                patch('codex_paste.paste_existing') as paste:
            desktop_send_choice.deliver_desktop_app(
                host, finish, 'r', 'task.md', '任务', '正文', r'C:\Tool.exe', 'Tool',
                delivery='clipboard')
        paste.assert_not_called()
        self.assertEqual(finish.call_args.args[1], 'prepared')
        self.assertIn('剪贴板', finish.call_args.args[2])

    def test_req_s01_54_missing_program_is_manual_not_a_crash(self):
        host = self.host()
        finish = Mock()
        with patch('contract.platform_tools.launch_windows_app') as launch:
            desktop_send_choice.deliver_desktop_app(
                host, finish, 'r', 'task.md', '任务', '正文', '', 'Tool')
        launch.assert_not_called()
        self.assertEqual(finish.call_args.args[1], 'prepared')
        self.assertIn('.exe', finish.call_args.args[2])


class UnknownClientRoutingTests(unittest.TestCase):
    def test_req_s01_55_client_cli_counts_as_local_attachment_mode(self):
        import stage_execution_service
        with patch('writing_api.model_label', return_value=''), \
                patch('workflow_engines.current_config',
                      return_value={'engine': 'client-cli', 'model': 'dsh'}), \
                patch('model_pool.desktop_engine', return_value='client-cli'):
            self.assertTrue(stage_execution_service.idea_attachment_local_mode('p'))

    def test_req_s01_55_unknown_desktop_profile_routes_without_unknown_engine_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            exe = fake_pe(root / 'Mystery.exe', 2)
            builtin = write_json(root / 'builtin.json', {'profiles': []})
            user = write_json(root / 'user.json', {'profiles': [{
                'id': 'mystery', 'kind': 'desktop', 'display': 'Mystery',
                'detect': {'exe_names': ['Mystery.exe']}, 'process_names': ['Mystery'],
                'delivery': 'paste'}]})
            with patch.object(client_profiles, 'BUILTIN_FILE', builtin), \
                    patch.object(client_profiles, 'USER_FILE', user), \
                    patch.object(client_profiles, 'detect_executable', return_value=exe):
                client_profiles.clear_cache()
                self.assertEqual(model_pool.desktop_engine('mystery'), 'desktop-app')
                self.assertEqual(workflow_settings.find_program(
                    {'engine': 'desktop-app', 'program': '', 'client_profile': 'mystery'}), exe)

    def test_req_s01_55_unknown_cli_profile_routes_to_interactive_window(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            exe = str(root / 'tool.exe')
            Path(exe).write_bytes(b'not executed')
            profile = {'id': 'tool', 'kind': 'cli', 'display': 'Tool',
                       'delivery': 'cli_stdin', 'invoke': []}
            config = {'engine': 'client-cli', 'client_profile': profile, 'model': ''}
            process = Mock()
            with patch.object(client_profiles, 'profile_for_config', return_value=profile), \
                    patch.object(workflow_engines, 'find_program', return_value=exe), \
                    patch.object(workflow_engines, 'reserve_stage_process_slot', return_value='slot'), \
                    patch.object(workflow_engines, 'register_process'), \
                    patch.object(workflow_engines, 'launch_windows_app', return_value=process) as launch:
                result = workflow_engines.launch_interactive(root, 'writing', '任务', '内容', config)
            self.assertIn('交互式窗口', result['reason'])
            self.assertNotIn('已复制到剪贴板', result['reason'])
            self.assertEqual(launch.call_args.kwargs['args'], [exe])
            self.assertEqual(result['engine'], 'Tool')


class EnvironmentRowsTests(unittest.TestCase):
    def test_req_s01_56_every_builtin_profile_has_one_environment_row(self):
        rows = environment_check.check_client_profiles(
            find=lambda item: 'C:/fake/' + item['id'] + '.exe')
        keys = [item['key'] for item in rows]
        self.assertEqual(set(keys), set(client_profiles.load_profiles(refresh=True)))
        self.assertTrue(all(item['status'] == environment_check.OK for item in rows))

    def test_req_s01_56_production_run_checks_uses_profile_rows(self):
        rows = environment_check.run_checks(
            config={}, settings={}, models={}, which=lambda name: None,
            find_blender=lambda: None, find_profile=lambda item: 'C:/fake/' + item['id'])
        keys = [item['key'] for item in rows]
        self.assertIn('deepseek-harness', keys)
        self.assertIn('opencode-cli', keys)


class BuiltinEnginePrecedenceTests(unittest.TestCase):
    """R1706b 回归：内建 CLI 引擎优先于同名客户端档案，不得被改判为桌面。"""

    def test_regression_r1706b_builtin_cli_models_keep_cli_call_mode(self):
        for name in ('opencode', 'qwen', 'claude-code', 'claude', 'claude-code-cli'):
            with self.subTest(name=name):
                self.assertNotEqual(model_pool.desktop_engine(name), 'desktop-app',
                                    '内建引擎 %s 不应命中桌面档案' % name)
                self.assertEqual(model_pool.call_mode(
                    {'provider': 'desktop', 'model': name}), 'CLI',
                    '内建引擎 %s 的调用方式仍是 CLI' % name)

    def test_regression_r1706b_new_clients_still_use_the_profile_fallback(self):
        # 旧名不再由档案改判调用方式，但档案仍负责找到它们的桌面程序。
        for legacy in ('gemini', 'google-gemini', 'codex-desktop'):
            with self.subTest(legacy=legacy):
                self.assertEqual(model_pool.desktop_engine(legacy), '')
        self.assertEqual(client_profiles.profile_for_mode('gemini', 'Desktop')['id'],
                         'gemini-desktop')
        self.assertEqual(model_pool.desktop_engine('deepseek-harness'), 'desktop-app')
        self.assertEqual(model_pool.desktop_engine('dsh'), 'client-cli')
        self.assertEqual(model_pool.call_mode(
            {'provider': 'desktop', 'model': 'dsh'}), 'CLI')


class CliProfileSelectionRegressionTests(unittest.TestCase):
    """R1706c 回归：client-cli 分支只能取 CLI 档案，不能命中共用别名的桌面档案。"""

    def test_regression_r1706c_client_cli_branch_selects_cli_profile(self):
        with tempfile.TemporaryDirectory() as td:
            record = {
                'label': 'opencode CLI',
                'provider': 'desktop',
                'model': 'opencode',
                'call_mode': 'CLI',
                'program': 'C:/tools/opencode-cli.exe',
            }
            config = workflow_settings.current(
                Path(td), 'writing', model_snapshot=('opencode', record))
        self.assertEqual(config['engine'], 'client-cli')
        self.assertEqual(config['client_profile'], 'opencode-cli')
        self.assertEqual(config['delivery'], 'cli_file')


if __name__ == '__main__':
    unittest.main()
