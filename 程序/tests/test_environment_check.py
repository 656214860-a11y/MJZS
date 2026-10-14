"""环境自检：只读核对外部依赖；探测函数全部注入，不启动程序、不联网。"""
import tempfile
import unittest
from pathlib import Path

import environment_check as env


class EnvironmentCheckTests(unittest.TestCase):
    def test_ffmpeg_prefers_configured_path_then_path_then_missing(self):
        with tempfile.TemporaryDirectory() as folder:
            exe = Path(folder) / 'ffmpeg.exe'
            exe.write_bytes(b'x')
            ok = env.check_ffmpeg({'ffmpeg': str(exe), 'ffprobe': str(exe)}, which=lambda name: None)
            self.assertEqual([item['status'] for item in ok], [env.OK, env.OK])
            fallback = env.check_ffmpeg({'ffmpeg': r'Z:\none\ffmpeg.exe'}, which=lambda name: '/usr/bin/' + name)
            self.assertEqual(fallback[0]['status'], env.WARN)
            self.assertEqual(fallback[1]['status'], env.OK)
            missing = env.check_ffmpeg({}, which=lambda name: None)
            self.assertTrue(all(item['status'] == env.MISSING and item['next'] for item in missing))

    def test_optional_tools_are_hints_not_failures(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(env.check_comfy({'comfy_exe': ''})['status'], env.WARN)
            exe = Path(folder) / 'ComfyUI.exe'
            exe.write_bytes(b'x')
            self.assertEqual(env.check_comfy({'comfy_exe': str(exe)})['status'], env.OK)
        self.assertEqual(env.check_blender(lambda: None)['status'], env.WARN)
        self.assertEqual(env.check_blender(lambda: Path('B/blender.exe'))['status'], env.OK)

    def test_desktop_programs_flag_gui_claude_used_as_cli(self):
        gui = r'C:\Program Files\WindowsApps\Claude_1_x64__x\app\Claude.exe'

        def find(config):
            if config['engine'] == 'codex':
                raise ValueError('未找到')
            return gui if config['engine'] == 'claude' else r'C:\x\Claude Desktop.exe'
        rows = {item['key']: item for item in env.check_desktop_programs(find)}
        self.assertEqual(rows['codex']['status'], env.WARN)
        self.assertEqual(rows['claude-desktop-app']['status'], env.OK)
        self.assertEqual(rows['claude']['status'], env.WARN)
        self.assertIn('图形', rows['claude']['next'])

    def test_model_keys_count_presence_without_exposing_values(self):
        models = {'a': {'label': 'A', 'provider': 'openai-compatible', 'key_env': 'K_A'},
                  'b': {'label': 'B', 'provider': 'openai-compatible', 'key_env': 'K_B'},
                  'd': {'label': 'D', 'provider': 'desktop', 'key_env': ''}}
        secret = 'sk-never-shown'
        both = env.check_model_keys(models, key_of=lambda item, program: secret)
        self.assertEqual(both['status'], env.OK)
        some = env.check_model_keys(models, key_of=lambda item, program: secret if item['key_env'] == 'K_A' else '')
        self.assertEqual(some['status'], env.WARN)
        self.assertIn('B', some['detail'])
        none = env.check_model_keys(models, key_of=lambda item, program: '')
        self.assertEqual(none['status'], env.MISSING)
        for row in (both, some, none):
            self.assertNotIn(secret, str(row))
        self.assertEqual(env.check_model_keys({'d': models['d']})['status'], env.WARN)

    def test_run_checks_and_report_are_read_only_and_complete(self):
        rows = env.run_checks(config={}, settings={}, models={}, which=lambda name: None,
                              find_blender=lambda: None,
                              find_program=lambda config: (_ for _ in ()).throw(ValueError('未找到')),
                              key_of=lambda item, program: '')
        keys = [item['key'] for item in rows]
        self.assertEqual(keys, ['ffmpeg', 'ffprobe', 'comfyui', 'blender', 'claude-desktop-app', 'codex', 'claude', 'keys'])
        text = env.report_text(rows)
        self.assertIn(env.summary(rows), text)
        self.assertIn('下一步', text)
        self.assertTrue(all(item['status'] in env.STATUS_TEXT for item in rows))


if __name__ == '__main__':
    unittest.main()
