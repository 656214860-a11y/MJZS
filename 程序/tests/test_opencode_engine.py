# -*- coding: utf-8 -*-
'''OpenCode CLI 引擎接入自检（R1688）。

事件夹具来自本机 opencode-cli.exe v2.0.32 的一次真实 `run --format json` 取样；
没有按猜测补造事件类型。
'''
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

PROGRAM = Path(__file__).resolve().parents[1]
if str(PROGRAM) not in sys.path:
    sys.path.insert(0, str(PROGRAM))

import infra.model_pool as model_pool
import skill_panel
import stage_execution_service
import workflow_engines
import workflow_settings


# 实机取样（--standalone，因默认托管服务在取样环境报 45278 端口被占用）。
OPENCODE_SAMPLE = ('{"type":"text","timestamp":1792272033160,'
                   '"sessionID":"ses_eb44327bcffe7Vps6dr94KA3G0",'
                   '"part":{"id":"prt_14bbcdaa4001CuIFj7QW2yryMK_text-0",'
                   '"sessionID":"ses_eb44327bcffe7Vps6dr94KA3G0",'
                   '"messageID":"msg_14bbcdaa4001CuIFj7QW2yryMK","type":"text",'
                   '"text":"好的","time":{"start":1792272030390,"end":1792272033160}}}')


FAKE_OPENCODE = '''
import json, os, pathlib, sys, time
args = sys.argv[1:]
mode = os.environ.get("OPENCODE_FAKE_MODE", "ok")
pathlib.Path("fake_args.json").write_text(json.dumps(args, ensure_ascii=False), encoding="utf-8")
pathlib.Path("fake_cwd.txt").write_text(os.getcwd(), encoding="utf-8")
try:
    prompt = pathlib.Path(args[args.index("--file") + 1]).read_text(encoding="utf-8")
except (ValueError, OSError):
    prompt = ""
pathlib.Path("fake_prompt.txt").write_text(prompt, encoding="utf-8")
if mode == "sleep":
    time.sleep(60)
    sys.exit(3)
if mode == "fail":
    sys.stdout.buffer.write(b'{"type":"error","message":"boom"}\\n')
    sys.stdout.buffer.flush()
    sys.exit(7)
if mode == "empty":
    sys.exit(0)
sys.stdout.buffer.write(FIXTURE.encode("utf-8") + b"\\n")
sys.stdout.buffer.flush()
'''.replace('FIXTURE', repr(OPENCODE_SAMPLE))


def install_fake_cli(project):
    (project / 'run').write_text(FAKE_OPENCODE, encoding='utf-8')


def opencode_config():
    return {'engine': 'opencode', 'program': sys.executable,
            'model': 'opencode/deepseek-v4.1-flash-free', 'stage': 'previs'}


class FindProgramTests(unittest.TestCase):
    def test_path_is_checked_before_the_desktop_install_scan(self):
        with tempfile.TemporaryDirectory() as td:
            exe = Path(td) / 'opencode-cli.exe'
            exe.write_bytes(b'MZ')
            with patch.dict(os.environ, {'PATH': td}, clear=False):
                found = workflow_settings.find_program({'engine': 'opencode', 'program': ''})
            self.assertEqual(found, str(exe))

    def test_the_newest_desktop_cli_is_used_from_appdata(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'ai.opencode.desktop' / 'cli'
            old = root / '1.0.0-x64' / 'opencode-cli.exe'
            new = root / '2.0.32-x64' / 'opencode-cli.exe'
            for path in (old, new):
                path.parent.mkdir(parents=True)
                path.write_bytes(b'MZ')
            os.utime(old, (1000, 1000))
            os.utime(new, (2000, 2000))
            with patch.dict(os.environ, {'PATH': '', 'APPDATA': td}, clear=False):
                found = workflow_settings.find_program({'engine': 'opencode', 'program': ''})
            self.assertEqual(found, str(new))

    def test_missing_cli_reports_the_install_hint(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {'PATH': '', 'APPDATA': td}, clear=False):
                with self.assertRaisesRegex(ValueError, 'OpenCode CLI'):
                    workflow_settings.find_program({'engine': 'opencode', 'program': ''})

    def test_cli_alias_resolves_to_the_opencode_engine(self):
        with patch.object(workflow_settings, 'find_program', return_value=r'C:\x\opencode-cli.exe') as find:
            found = workflow_settings.find_model_program('opencode-cli', 'CLI')
        self.assertEqual(found, r'C:\x\opencode-cli.exe')
        find.assert_called_once_with({'engine': 'opencode', 'program': ''})
class BackgroundCommandTests(unittest.TestCase):
    def test_opencode_attaches_the_prompt_file_and_avoids_directory_flags(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            report = project / 'out' / '制作报告.txt'
            report.parent.mkdir()
            prompt = report.with_suffix('.opencode-prompt.md')
            prompt.write_text('完整制作任务', encoding='utf-8')
            argv = workflow_engines.background_command(
                opencode_config(), project, project / 'out', report, prompt)
        self.assertEqual(argv[0], sys.executable)
        self.assertEqual(argv[1], 'run')
        self.assertIn('--auto', argv)
        self.assertEqual(argv[argv.index('--format') + 1], 'json')
        self.assertEqual(argv[argv.index('-m') + 1], 'opencode/deepseek-v4.1-flash-free')
        self.assertEqual(argv[argv.index('--file') + 1], str(prompt))
        self.assertEqual(argv[-1], '执行附件中的制作任务')
        self.assertNotIn('--cd', argv)
        self.assertNotIn('--add-dir', argv)
class RunBackgroundTests(unittest.TestCase):
    def test_success_writes_the_event_text_and_keeps_the_prompt_file(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            install_fake_cli(project)
            out = project / 'out'
            out.mkdir()
            report = out / '制作报告.txt'
            prompt = '完整制作提示词：' + '素材' * 3000
            with patch.dict(os.environ, {'OPENCODE_FAKE_MODE': 'ok',
                                         'PYTHONIOENCODING': 'utf-8'}, clear=False):
                workflow_engines.run_background(
                    opencode_config(), project, out, report, out / '运行日志.txt', prompt)
            self.assertEqual(report.read_text(encoding='utf-8'), '好的')
            prompt_file = out / '制作报告.opencode-prompt.md'
            self.assertEqual(prompt_file.read_text(encoding='utf-8'), prompt)
            self.assertEqual((project / 'fake_prompt.txt').read_text(encoding='utf-8'), prompt)
            self.assertEqual((project / 'fake_cwd.txt').read_text(encoding='utf-8'), str(project))
            argv = json.loads((project / 'fake_args.json').read_text(encoding='utf-8'))
            self.assertEqual(argv[argv.index('--file') + 1], str(prompt_file.resolve()))

    def test_nonzero_exit_raises_and_keeps_the_raw_event_stream(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            install_fake_cli(project)
            out = project / 'out'
            out.mkdir()
            report = out / '制作报告.txt'
            with patch.dict(os.environ, {'OPENCODE_FAKE_MODE': 'fail',
                                         'PYTHONIOENCODING': 'utf-8'}, clear=False):
                with self.assertRaisesRegex(ValueError, '执行失败'):
                    workflow_engines.run_background(
                        opencode_config(), project, out, report, out / '运行日志.txt', '任务')
            self.assertFalse(report.exists())
            self.assertTrue((out / '制作报告.response.jsonl').is_file())

    def test_empty_report_raises_instead_of_publishing_an_empty_file(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            install_fake_cli(project)
            out = project / 'out'
            out.mkdir()
            report = out / '制作报告.txt'
            with patch.dict(os.environ, {'OPENCODE_FAKE_MODE': 'empty',
                                         'PYTHONIOENCODING': 'utf-8'}, clear=False):
                with self.assertRaisesRegex(ValueError, '未返回制作报告正文'):
                    workflow_engines.run_background(
                        opencode_config(), project, out, report, out / '运行日志.txt', '任务')
            self.assertFalse(report.exists())

    def test_force_stop_ends_the_registered_opencode_process(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            install_fake_cli(project)
            out = project / 'out'
            out.mkdir()
            errors = []

            def work():
                try:
                    workflow_engines.run_background(
                        opencode_config(), project, out, out / '制作报告.txt',
                        out / '运行日志.txt', '任务')
                except Exception as exc:
                    errors.append(exc)

            try:
                with patch.dict(os.environ, {'OPENCODE_FAKE_MODE': 'sleep',
                                             'PYTHONIOENCODING': 'utf-8'}, clear=False):
                    thread = threading.Thread(target=work, daemon=True)
                    thread.start()
                    deadline = time.monotonic() + 10
                    alive = []
                    while time.monotonic() < deadline:
                        alive = workflow_engines.running(project)
                        if alive:
                            break
                        time.sleep(0.05)
                    self.assertTrue(alive, 'OpenCode 进程应由 _run 登记')
                    killed = workflow_engines.terminate(project)
                    thread.join(10)
                self.assertEqual(len(killed), 1)
                self.assertFalse(thread.is_alive())
                self.assertEqual(workflow_engines.running(project), [])
                self.assertTrue(errors)
            finally:
                workflow_engines.terminate(project)
class SettingsAndRoutingTests(unittest.TestCase):
    def test_defaults_and_load_carry_the_opencode_profile(self):
        defaults = workflow_settings.defaults('previs')
        self.assertIn('opencode', defaults['profiles'])
        self.assertEqual(defaults['engine'], 'codex')
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            (project / '工作流任务').mkdir()
            (project / '工作流任务' / '工作流调用设置.json').write_text(json.dumps({
                'flows': {'previs': {'engine': 'codex', 'profiles': {
                    'opencode': {'model': 'opencode/deepseek-v4.1-flash-free',
                                 'instructions': '只改本阶段', 'skills': []}}}}},
                ensure_ascii=False), encoding='utf-8')
            loaded = workflow_settings.load(project, 'previs')
        self.assertEqual(loaded['profiles']['opencode']['model'],
                         'opencode/deepseek-v4.1-flash-free')
        self.assertEqual(loaded['profiles']['opencode']['instructions'], '只改本阶段')

    def test_opencode_is_a_cli_engine_not_a_desktop_model(self):
        self.assertEqual(model_pool.call_mode({'provider': 'desktop', 'model': 'opencode'}), 'CLI')
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            with patch('workflow_engines.current_config', return_value={'engine': 'opencode'}), \
                 patch('writing_api.model_label', return_value=''):
                self.assertTrue(stage_execution_service.idea_attachment_local_mode(project))



if __name__ == '__main__':
    unittest.main(verbosity=2)
