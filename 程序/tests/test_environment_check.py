"""环境自检：只读核对外部依赖；探测函数全部注入，不启动程序、不联网。"""
import tempfile
from unittest import mock
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
            with mock.patch.object(env.comfy_runtime, 'executable', return_value=None):
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


    def test_version_parsing_covers_release_and_git_builds(self):
        self.assertEqual(env.parse_version('ffmpeg version 6.1.1-essentials_build Copyright'), (6, 1))
        self.assertEqual(env.parse_version('ffmpeg version n7.0.2-static'), (7, 0))
        self.assertEqual(env.parse_version('Blender 4.2.1 LTS\n\tbuild date'), (4, 2))
        self.assertIsNone(env.parse_version('ffmpeg version N-112233-gabcdef'))
        self.assertIsNone(env.parse_version(''))

    def test_versions_below_the_minimum_become_hints_and_never_launch_without_a_probe(self):
        rows = [env.row('ffmpeg', 'FFmpeg', env.OK, r'C:\f\ffmpeg.exe'), env.row('blender', 'Blender', env.OK, r'C:\b\blender.exe'),
                env.row('ffprobe', 'FFprobe', env.MISSING, '未配置也不在 PATH')]
        probed = []

        def probe(key, exe):
            probed.append(key)
            return {'ffmpeg': (3, 9), 'blender': (4, 2)}[key]
        out = {item['key']: item for item in env.apply_versions(rows, probe)}
        self.assertEqual(probed, ['ffmpeg', 'blender'], '缺失的程序不探测')
        self.assertEqual(out['ffmpeg']['status'], env.WARN)
        self.assertIn('低于建议最低 4.4', out['ffmpeg']['detail'])
        self.assertIn('升级', out['ffmpeg']['next'])
        self.assertEqual((out['blender']['status'], out['blender']['detail']), (env.OK, r'C:\b\blender.exe；版本 4.2'))
        self.assertEqual(out['ffprobe']['status'], env.MISSING)

    def test_unreadable_version_keeps_the_status_and_says_so(self):
        out = env.apply_versions([env.row('ffmpeg', 'FFmpeg', env.OK, 'x.exe')], lambda key, exe: None)[0]
        self.assertEqual(out['status'], env.OK)
        self.assertIn('版本无法识别', out['detail'])

    def test_probe_failure_is_none_and_run_checks_probes_only_when_asked(self):
        def boom(*args, **kwargs):
            raise OSError('nope')
        self.assertIsNone(env.probe_version('ffmpeg', 'x.exe', run=boom))
        with tempfile.TemporaryDirectory() as folder:
            exe = Path(folder) / 'ffmpeg.exe'
            exe.write_bytes(b'x')
            calls = []
            kwargs = dict(config={'ffmpeg': str(exe), 'ffprobe': str(exe)}, settings={}, models={}, profiles=[],
                          find_blender=lambda: None)
            with mock.patch.object(env.comfy_runtime, 'executable', return_value=None):
                plain = env.run_checks(Path(folder), **kwargs)
                probed = env.run_checks(Path(folder), probe=lambda key, path: calls.append(key) or (6, 0), **kwargs)
        self.assertNotIn('版本', plain[0]['detail'])
        self.assertIn('版本 6.0', probed[0]['detail'])
        self.assertEqual(calls, ['ffmpeg', 'ffprobe'])

if __name__ == '__main__':
    unittest.main()
