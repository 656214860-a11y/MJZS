# -*- coding: utf-8 -*-
"""engine_probe（第 8 轮的真机验证入口）自检。

运行：python test_engine_probe.py

这一份盯三件事：
1. **防漂**：验的开关必须是 `workflow_engines` 真会拼的那串、-p 那一次读的字段必须是
   `run_background` 真读的那三个——改了一边不改这边就红；
2. **找程序**与**结论**：装了／没装／开关漂了／-p 没成，四种结论各验一遍（拿假 runner 跑）；
3. **真进程那条路**：拿本机解释器当一次「CLI」，把 locate → --version → --help → 子进程 走通。
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, HERE)
os.chdir(HERE)

import engine_probe


def fake_cli(version='1.2.3 (Claude Code)', help_text=None, one_shot=None):
    """造一个假的 CLI：--version／--help／一次 -p 各回一份，好让结论可判。"""
    text = help_text if help_text is not None else (
        'Usage: claude [options] [command]\n'
        '  -p, --print                  打印模式\n'
        '  --output-format <format>     json / text\n'
        '  --permission-mode <mode>     default / acceptEdits\n'
        '  --add-dir <directories...>   额外目录\n'
        '  --session-id <uuid>          会话号\n'
        '  --resume <uuid>              接着某个会话\n'
        '  --name <title>               会话名\n')
    body = one_shot if one_shot is not None else json.dumps(
        {'result': '收到', 'is_error': False, 'permission_denials': [], 'session_id': 'x'})
    calls = []

    def runner(argv, stdin='', timeout=180, cwd=None):
        calls.append((list(argv), stdin))
        if '--version' in argv:
            return 0, version + '\n', ''
        if '--help' in argv:
            return 0, text, ''
        return 0, body, ''

    return runner, calls


class LocateTests(unittest.TestCase):
    def test_an_explicit_program_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / 'claude.exe'
            exe.write_bytes(b'MZ')
            found, tried = engine_probe.locate('claude', str(exe))
            self.assertEqual(found, str(exe))
            self.assertEqual(tried, [str(exe)])

    def test_a_missing_explicit_program_reports_it(self):
        found, tried = engine_probe.locate('claude', r'D:\不存在\claude.exe')
        self.assertIsNone(found)
        self.assertEqual(len(tried), 1)

    def test_the_lookup_order_matches_the_program(self):
        """先 PATH，再引擎自己的位置：与 workflow_settings.find_program 同一套口径。"""
        def which(name):
            return r'C:\bin\claude.exe' if name == 'claude.exe' else None
        found, tried = engine_probe.locate('claude', which=which, home=Path(r'D:\home'))
        self.assertEqual(found, r'C:\bin\claude.exe')
        self.assertEqual(tried[0], 'PATH 上的 claude.exe')

    def test_nothing_found_says_where_it_looked(self):
        found, tried = engine_probe.locate('claude', which=lambda name: None, home=Path(r'D:\home'))
        self.assertIsNone(found)
        self.assertEqual(len(tried), 2, '要说清找过哪两处')
        self.assertIn('claude.exe', tried[0])


class ContractTests(unittest.TestCase):
    """防漂：验的开关与字段必须是程序真正用的那一套。"""

    def body(self):
        return (Path(HERE) / 'workflow_engines.py').read_text(encoding='utf-8')

    def test_the_switches_come_from_the_real_builder(self):
        argv, _config = engine_probe.app_argv('claude', 'CLI.exe', '项目', '输出', '报告')
        for flag in ('-p', '--output-format', '--permission-mode', '--add-dir'):
            self.assertIn(flag, engine_probe.switches(argv),
                          'workflow_engines 拼出来的参数里该有 %s' % flag)
        self.assertEqual(argv[0], 'CLI.exe', '第一条就是我们要跑的那支 CLI')

    def test_the_help_goes_to_the_subcommand_the_program_uses(self):
        """`codex --help` 不列 exec 的开关：问错一层会把好好的契约误报成漂了（真机踩过）。"""
        self.assertEqual(
            engine_probe.help_argv('codex.exe', ['codex.exe', 'exec', '--color', 'never', '-']),
            ['codex.exe', 'exec', '--help'])
        self.assertEqual(
            engine_probe.help_argv('claude.exe', ['claude.exe', '-p', '--output-format', 'json']),
            ['claude.exe', '--help'])

    def test_the_session_switches_still_match_the_sibling_source(self):
        body = self.body()
        for flag in engine_probe.SESSION_SWITCHES['claude']:
            self.assertIn("'%s'" % flag, body,
                          'launch_interactive 里的 %s 改了名，engine_probe 要跟着改' % flag)

    def test_the_one_shot_keys_are_the_ones_the_runner_reads(self):
        body = self.body()
        for key in engine_probe.ONE_SHOT_KEYS:
            self.assertIn("result.get('%s'" % key, body,
                          'run_background 读的字段变了，engine_probe 要跟着改')


class VerdictTests(unittest.TestCase):
    def row(self, **kwargs):
        return engine_probe.probe(workdir=kwargs.pop('workdir', None), **kwargs)

    def test_a_complete_cli_verifies(self):
        runner, calls = fake_cli()
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / 'claude.exe'
            exe.write_bytes(b'MZ')
            row = self.row(runner=runner, program=str(exe), workdir=tmp)
        self.assertEqual(row['verdict'], 'verified', engine_probe.summary(row))
        self.assertEqual(row['missing'], [])
        self.assertTrue(row['one_shot']['ok'])
        self.assertIn('1.2.3', row['version'])
        self.assertEqual(len(calls), 3, '--version、--help、-p 各一次')
        self.assertEqual(calls[2][1], engine_probe.ONE_SHOT_PROMPT, '提示词从标准输入喂进去')

    def test_a_drifted_switch_is_named(self):
        runner, _calls = fake_cli(help_text='Usage: claude [options]\n  -p, --print\n')
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / 'claude.exe'
            exe.write_bytes(b'MZ')
            row = self.row(runner=runner, program=str(exe), workdir=tmp)
        self.assertEqual(row['verdict'], 'installed-switches-missing')
        self.assertIn('--output-format', row['missing'])
        self.assertIn('--output-format', engine_probe.summary(row))

    def test_a_drifted_switch_skips_the_real_call(self):
        runner, calls = fake_cli(help_text='Usage: claude [options]\n  -p, --print\n')
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / 'claude.exe'
            exe.write_bytes(b'MZ')
            row = self.row(runner=runner, program=str(exe), workdir=tmp)
        self.assertEqual(row['verdict'], 'installed-switches-missing')
        self.assertEqual(len(calls), 2, '开关已经对不上，就别再真跑那一次了')
        self.assertIn('没真跑', row['one_shot']['note'])

    def test_a_bad_one_shot_says_what_came_back(self):
        runner, _calls = fake_cli(one_shot='这不是 JSON')
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / 'claude.exe'
            exe.write_bytes(b'MZ')
            row = self.row(runner=runner, program=str(exe), workdir=tmp)
        self.assertEqual(row['verdict'], 'installed-one-shot-failed')
        self.assertIn('不是 JSON', row['one_shot']['note'])

    def test_a_missing_field_counts_as_not_verified(self):
        runner, _calls = fake_cli(one_shot=json.dumps({'result': '收到'}))
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / 'claude.exe'
            exe.write_bytes(b'MZ')
            row = self.row(runner=runner, program=str(exe), workdir=tmp)
        self.assertEqual(row['verdict'], 'installed-one-shot-failed')
        self.assertIn('permission_denials', row['one_shot']['missing'])

    def test_a_missing_cli_is_not_a_pass(self):
        row = engine_probe.probe('claude', which=lambda name: None, home=Path(r'D:\home'))
        self.assertEqual(row['verdict'], 'not-installed')
        self.assertFalse(row['ran'])
        self.assertIn('仍未验证', engine_probe.summary(row))

    def test_dry_run_says_it_did_not_really_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / 'claude.exe'
            exe.write_bytes(b'MZ')
            row = engine_probe.probe('claude', program=str(exe), workdir=tmp, offline=True)
        self.assertEqual(row['verdict'], 'not-run')
        self.assertFalse(row['ran'])
        self.assertIn('没真跑', engine_probe.summary(row))

    def test_qwen_is_left_to_its_own_adapter(self):
        row = engine_probe.probe('qwen')
        self.assertEqual(row['verdict'], 'handled-by-adapter')

    def codex_runner(self, help_text, reply):
        """造一支「codex 样子」的 CLI：答案写进 -o 指定的那份报告，标准输出是过程日志。"""

        def runner(argv, stdin='', timeout=180, cwd=None):
            if '--version' in argv:
                return 0, 'codex-cli 0.153.4\n', ''
            if '--help' in argv:
                return 0, help_text, ''
            if reply is not None:
                Path(argv[argv.index('-o') + 1]).write_text(reply, encoding='utf-8')
            return 0, '过程日志（不是 JSON）', ''

        return runner

    CODEX_HELP = ('Usage: codex exec [OPTIONS] [PROMPT]\n  --skip-git-repo-check\n'
                  '  -s, --sandbox <SANDBOX_MODE>\n  -C, --cd <DIR>\n  --add-dir <DIR>\n'
                  '  --color <COLOR>\n  -o, --output-last-message <FILE>\n')

    def test_codex_is_judged_by_the_report_it_writes(self):
        """真机实测：codex 的标准输出是过程日志、答案在 -o 那份报告里，不能按 JSON 判。"""
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / 'codex.exe'
            exe.write_bytes(b'MZ')
            row = engine_probe.probe('codex', program=str(exe), workdir=tmp,
                                     runner=self.codex_runner(self.CODEX_HELP, '收到'))
        self.assertEqual(row['verdict'], 'verified', engine_probe.summary(row))
        self.assertEqual(row['one_shot']['reply'], '收到')
        self.assertEqual(row['one_shot']['kind'], 'report')
        self.assertEqual(row['help_argv'], [str(exe), 'exec', '--help'], '问的是 exec 那一层')

    def test_an_empty_report_is_a_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / 'codex.exe'
            exe.write_bytes(b'MZ')
            row = engine_probe.probe('codex', program=str(exe), workdir=tmp,
                                     runner=self.codex_runner(self.CODEX_HELP, None))
        self.assertEqual(row['verdict'], 'installed-one-shot-failed')
        self.assertIn('报告里没有内容', row['one_shot']['note'])

    def test_the_real_process_path_runs(self):
        """真子进程那条路：拿本机解释器当一次「CLI」，走通 locate → --version → --help → -p。"""
        with tempfile.TemporaryDirectory() as tmp:
            row = engine_probe.probe('claude', program=sys.executable, workdir=tmp, timeout=120)
        self.assertTrue(row['ran'], engine_probe.summary(row))
        self.assertTrue(row['version'].lower().startswith('python'), row['version'])
        self.assertIn(row['verdict'],
                      ('installed-switches-missing', 'installed-one-shot-failed'),
                      '解释器不认 CLI 那串参数，正是这条路上该有的两种结论之一')


class SessionTests(unittest.TestCase):
    def test_a_persisted_session_is_found_under_the_cli_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            session = '11111111-2222-3333-4444-555555555555'
            self.assertFalse(engine_probe.persisted_session(session, home=home))
            folder = home / '.claude' / 'projects' / '-D-项目'
            folder.mkdir(parents=True)
            (folder / (session + '.jsonl')).write_text('{}', encoding='utf-8')
            self.assertTrue(engine_probe.persisted_session(session, home=home))

    def test_no_session_number_is_never_persisted(self):
        self.assertFalse(engine_probe.persisted_session('', home=Path(r'D:\home')))


class LedgerTests(unittest.TestCase):
    def test_the_ledger_keeps_one_row_per_engine_and_the_files_own_line_ending(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / '引擎真机验证.json'
            engine_probe.record({'engine': 'claude', 'at': '2026-09-24T00:00:00',
                                 'located': None, 'tried': ['PATH'], 'verdict': 'not-installed'}, path=target)
            engine_probe.record({'engine': 'codex', 'at': '2026-09-24T00:00:01',
                                 'located': r'C:\bin\codex.exe', 'tried': ['PATH'],
                                 'verdict': 'not-run'}, path=target)
            data = json.loads(target.read_text(encoding='utf-8-sig'))
            self.assertEqual(sorted(data['engines']), ['claude', 'codex'])
            self.assertEqual(data['engines']['claude']['verdict'], 'not-installed')
            self.assertEqual(data['updated'], '2026-09-24T00:00:01')
            self.assertEqual(data['engines']['claude']['tried'], ['PATH'], '同一支引擎覆盖上一次')
            self.assertFalse(target.read_bytes().startswith(b'\xef\xbb\xbf'), '不写 BOM')

    def test_the_ledger_lives_under_the_maintenance_folder(self):
        self.assertEqual(engine_probe.ledger_path(), Path(HERE) / '维护记录' / '引擎真机验证.json')


if __name__ == '__main__':
    unittest.main(verbosity=2)
