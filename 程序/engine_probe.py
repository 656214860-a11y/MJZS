# -*- coding: utf-8 -*-
"""引擎真机验证：拿本机真装的那支 CLI，把「程序真会传的那串参数」跑一遍，结论落台账。

为什么单独有这么一份：`workflow_engines` 给 CLI 拼的是一串命令行开关——
    claude -p --output-format json --permission-mode auto --add-dir <目录> [--model <模型>]
交互那条路还要 --session-id／--resume／--name。CLI 换版本时这些开关会改名或换取值，
光读代码看不出「本机这一支认不认」。这一份做的事就是：按程序真正会用的那串参数在本机
跑一遍，把「装了没／版本／哪个开关不在 --help 里／-p 那一次返回的 JSON 字段齐不齐」记进
`维护记录\引擎真机验证.json`，并在屏幕上说一句人话。

四种结论（`verdict`）：
    verified                    装了、开关都在、-p 那一次的 JSON 字段也齐
    installed-switches-missing  装了，但 --help 里找不到程序要传的某个开关（契约漂了）
    installed-one-shot-failed   装了，但 -p 那一次没跑成、或返回的字段不齐
    not-installed               本机没装这支 CLI（真实制作仍未验证，**不是**「已通过」）

开关的核对口径：`--help` 问的是**程序真会用的那一层**（`codex exec` 就查 `codex exec --help`），
免得把子命令的开关误报成「漂了」。`-p` 那一次的判据也按引擎分——claude 看标准输出那份 JSON，
codex 看 `-o` 写出的报告（真机实测：codex 的标准输出是过程日志，不是 JSON）。

跑法（在程序根目录）：
    python engine_probe.py                    # 验 Claude Code，并落台账
    python engine_probe.py --engine codex
    python engine_probe.py --dry-run          # 只报「装在哪／参数长什么样」，不真跑
    python engine_probe.py --program <某个 .exe>
    python engine_probe.py --json             # 顺带把整条记录打到屏幕上
"""
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from file_cache import read_json

ENGINES = {'codex': 'ChatGPT / Codex', 'qwen': 'Qwen Code（阿里云）', 'claude': 'Claude Code'}
# -p 那一次的判据按引擎分（见 workflow_engines.run_background 的两支）：
#   claude：标准输出就是一份 JSON，程序读 result／is_error／permission_denials 三个字段；
#   codex ：标准输出是过程日志（真机实测不是 JSON），答案落在 -o 写出的那份报告里。
ONE_SHOT_KEYS = ('result', 'is_error', 'permission_denials')
ONE_SHOT_KIND = {'claude': 'json', 'codex': 'report'}
# 交互那条路的开关：写在一处，字面量就是 workflow_engines.launch_interactive 里那几个；
# 自检会去那份源码里逐个核对，改了一边不改这边就会红。
SESSION_SWITCHES = {'claude': ('--session-id', '--resume', '--name')}
ONE_SHOT_PROMPT = '只回复两个字：收到。'
LEDGER = Path('维护记录') / '引擎真机验证.json'


# ── 找程序 ────────────────────────────────────────────────────────────────────
def locate(engine, program='', which=None, home=None):
    """找**程序真会用的那一支** CLI，返回 (路径 or None, 试过的地方)。

    与 `workflow_settings.find_program` 同一套口径、同一个先后：先 PATH，再引擎自己的位置。
    这里多回来一份「试过哪些地方」——没装时台账要能说清去哪找过。
    """
    which = which or shutil.which
    home = Path(home) if home else Path.home()
    tried = []
    if program:
        spot = Path(program).expanduser()
        tried.append(str(spot))
        return (str(spot) if spot.is_file() else None), tried
    if engine == 'qwen':
        tried.append('Qwen 走 qwen_adapter 自己的解析（这一份不代跑）')
        return None, tried
    tried.append('PATH 上的 ' + engine + '.exe')
    found = which(engine + '.exe')
    if found:
        return found, tried
    if engine == 'codex':
        local = os.environ.get('LOCALAPPDATA', '')
        if local:
            tried.append(str(Path(local) / 'OpenAI' / 'Codex' / 'bin' / '*' / 'codex.exe'))
            choices = list((Path(local) / 'OpenAI' / 'Codex' / 'bin').glob('*/codex.exe'))
            if choices:
                return str(max(choices, key=lambda spot: spot.stat().st_mtime)), tried
    else:
        native = home / '.local' / 'bin' / 'claude.exe'
        tried.append(str(native))
        if native.is_file():
            return str(native), tried
    return None, tried


# ── 程序会传的那串参数 ────────────────────────────────────────────────────────
def app_argv(engine, exe, project, output, report, model=''):
    """程序真会拼的那串参数：**向 workflow_engines 要**，不在这儿另抄一份。

    第一条换成我们要跑的那支 CLI（`find_program` 见到 program 就原样返回，不校验存在）。
    """
    import workflow_engines
    config = {'engine': engine, 'program': str(exe), 'model': model}
    argv = workflow_engines.background_command(config, Path(project), Path(output), Path(report))
    return [str(item) for item in argv], config


def help_argv(located, argv):
    """要「程序真会用的那一层」的帮助：argv 里有子命令（`exec`）就查子命令的。

    `codex --help` 只列顶层开关，程序传给 `exec` 的 `--skip-git-repo-check`／`--color`
    在 `codex exec --help` 里（本机实测）；问错一层就会把好好的契约误报成「漂了」。
    """
    command = []
    for item in [str(part) for part in argv][1:]:
        if item.startswith('-'):
            break
        command.append(item)
    return [str(located), *command, '--help']


def switches(argv):
    """从这串参数里挑出开关（`-x`／`--xxx`）；开关后面跟的值不算。"""
    found = []
    for item in argv[1:]:
        if item.startswith('-') and len(item) > 1 and not item[1:2].isdigit():
            found.append(item)
    return found


def run(argv, stdin='', timeout=180, cwd=None):
    """真跑一次（不弹控制台窗）。返回 (退出码, 标准输出, 标准错误)。"""
    import subprocess
    from platform_tools import hidden_console_flags
    done = subprocess.run(argv, input=stdin, capture_output=True, text=True, encoding='utf-8',
                          errors='replace', timeout=timeout, cwd=cwd, creationflags=hidden_console_flags())
    return done.returncode, done.stdout or '', done.stderr or ''


def one_shot(argv, runner, folder, timeout=180, kind='json', report=None):
    """按程序的方式跑一次（提示词从标准输入喂进去），再看这一次的成色。

    kind='json'：标准输出得是一份 JSON，三个字段（ONE_SHOT_KEYS）要齐；
    kind='report'：答案在 `-o` 写出的那份报告里，报告有内容且退出码为 0 才算成。
    """
    outcome = {'ok': False, 'code': None, 'kind': kind, 'keys': [], 'missing': [], 'note': ''}
    try:
        code, out, err = runner(argv, ONE_SHOT_PROMPT, timeout, str(folder))
    except Exception as exc:
        outcome['note'] = '%s: %s' % (type(exc).__name__, exc)
        return outcome
    outcome['code'] = code
    if kind == 'report':
        spot = Path(report) if report else None
        try:
            body = spot.read_text(encoding='utf-8', errors='replace').strip() if spot and spot.is_file() else ''
        except OSError as exc:
            body = ''
            outcome['note'] = '报告读不动：%s' % exc
        outcome['reply'] = body[:200]
        outcome['missing'] = [] if body else ['report']
        outcome['ok'] = bool(body) and code == 0
        if not outcome['ok'] and not outcome['note']:
            outcome['note'] = ('退出码 %s，报告里是：%s' % (code, body[:120])) if body else '报告里没有内容（-o 那份）'
        return outcome
    outcome['missing'] = list(ONE_SHOT_KEYS)
    body = (out or '').strip()
    if not body:
        outcome['note'] = ('没有输出' if not (err or '').strip() else (err or '').strip()[:300])
        return outcome
    try:
        data = json.loads(body)
    except ValueError as exc:
        outcome['note'] = '返回的不是 JSON（%s）：%s' % (type(exc).__name__, body[:200])
        return outcome
    if not isinstance(data, dict):
        outcome['note'] = '返回的 JSON 不是对象：%s' % body[:200]
        return outcome
    outcome['keys'] = sorted(str(key) for key in data)
    outcome['missing'] = [key for key in ONE_SHOT_KEYS if key not in data]
    outcome['is_error'] = bool(data.get('is_error'))
    outcome['reply'] = str(data.get('result', ''))[:200]
    outcome['ok'] = not outcome['missing'] and not outcome['is_error']
    if not outcome['ok']:
        outcome['note'] = ('缺字段：' + '、'.join(outcome['missing'])) if outcome['missing'] \
            else ('这一次 is_error 为真：' + outcome['reply'])
    return outcome


def persisted_session(session, home=None):
    """这一支 CLI 的会话落盘了没：`~/.claude/projects/*/<会话号>.jsonl`（launch_interactive 的判据）。"""
    if not session:
        return False
    home = Path(home) if home else Path.home()
    return any((home / '.claude' / 'projects').glob('*/' + str(session) + '.jsonl'))


# ── 验一支引擎 ────────────────────────────────────────────────────────────────
def verdict_of(row):
    if row.get('verdict_override'):
        return row['verdict_override']
    if not row.get('located'):
        return 'not-installed'
    if row.get('missing'):
        return 'installed-switches-missing'
    if not row.get('one_shot', {}).get('ok'):
        return 'installed-one-shot-failed'
    return 'verified'


def probe(engine='claude', program='', runner=run, which=None, home=None, model='',
          workdir=None, timeout=180, offline=False, now=None):
    """验一支引擎：找程序 → --version → --help 里核对开关 → 真跑一次 -p → 出结论。

    `runner`／`which`／`home` 都能换（自检拿假的进来）；`offline=True` 就只做静态那几步
    （不真跑 CLI，屏幕与台账上直接标明「没真跑」）。
    """
    home = Path(home) if home else Path.home()
    folder = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix='engine_probe_'))
    folder.mkdir(parents=True, exist_ok=True)
    stamp = now or datetime.now().isoformat(timespec='seconds')
    located, tried = locate(engine, program, which=which, home=home)
    row = {'engine': engine, 'at': stamp, 'located': located, 'tried': list(tried),
           'version': None, 'help_code': None, 'flags': {}, 'missing': [],
           'session_switches': list(SESSION_SWITCHES.get(engine, ())), 'one_shot': {},
           'ran': False, 'switches': [], 'model': model}
    if engine == 'qwen':
        row['verdict_override'] = 'handled-by-adapter'
        row['verdict'] = verdict_of(row)
        return row
    argv, _config = app_argv(engine, located or (engine + '.exe'), folder, folder, folder / 'report.md', model=model)
    row['switches'] = switches(argv)
    row['argv'] = argv
    if not located:
        row['verdict'] = verdict_of(row)
        return row
    if offline:
        row['verdict_override'] = 'not-run'
        row['verdict'] = verdict_of(row)
        return row
    row['help_argv'] = help_argv(located, argv)
    try:
        code, out, err = runner([located, '--version'], '', timeout, str(folder))
        first = (out or err or '').strip().splitlines()
        row['version'] = first[0] if first else ''
        code, out, err = runner(row['help_argv'], '', timeout, str(folder))
        row['help_code'] = code
        text = (out or '') + '\n' + (err or '')
        row['flags'] = {flag: (flag in text) for flag in [*row['switches'], *row['session_switches']]}
        row['missing'] = sorted(flag for flag, known in row['flags'].items() if not known)
    except Exception as exc:
        row['note'] = '%s: %s' % (type(exc).__name__, exc)
        row['verdict'] = verdict_of(row)
        return row
    row['ran'] = True
    if row['missing']:
        row['one_shot'] = {'ok': False, 'code': None, 'kind': ONE_SHOT_KIND.get(engine, 'report'),
                           'keys': [], 'missing': list(ONE_SHOT_KEYS),
                           'note': '开关对不上，没真跑那一次（免得白花一次调用）'}
    else:
        row['one_shot'] = one_shot(argv, runner, folder, timeout,
                                   kind=ONE_SHOT_KIND.get(engine, 'report'),
                                   report=folder / 'report.md')
    row['verdict'] = verdict_of(row)
    return row


# ── 台账与人话 ────────────────────────────────────────────────────────────────
def ledger_path(program=None):
    return (Path(program) if program else Path(__file__).resolve().parent) / LEDGER


def record(row, path=None):
    """把这一条并进台账（同一支引擎覆盖上一次），回写走 line_endings.write_text。"""
    import line_endings
    target = Path(path) if path else ledger_path()
    data = {}
    if target.is_file():
        try:
            loaded = read_json(target)
        except (OSError, ValueError):
            loaded = {}
        if isinstance(loaded, dict):
            data = loaded
    engines = data.get('engines')
    if not isinstance(engines, dict):
        engines = {}
    engines[row['engine']] = row
    data.update(schema=1, updated=row['at'], engines=engines)
    line_endings.write_text(target, json.dumps(data, ensure_ascii=False, indent=2))
    return target


def summary(row):
    """一句话说清这一次验到哪了（屏幕与维护记录都用它）。"""
    label = ENGINES.get(row['engine'], row['engine'])
    verdict = row.get('verdict')
    if verdict == 'not-installed':
        return '%s：本机没装（找过：%s）——真实制作仍未验证' % (label, '、'.join(row['tried']))
    if verdict == 'handled-by-adapter':
        return '%s：由 qwen_adapter 自己解析，这一份不代跑' % label
    if verdict == 'not-run':
        return '%s：只做了静态核对（没真跑）：%s' % (label, row.get('version') or '版本未知')
    head = '%s：%s（%s）' % (label, row.get('version') or '版本未知', row['located'])
    if verdict == 'verified':
        return head + '；程序要传的开关都在 --help 里，-p 那一次返回的字段也齐——真机验证通过'
    if verdict == 'installed-switches-missing':
        return head + '；这些开关不在 --help 里（契约漂了，要改 workflow_engines）：' + '、'.join(row['missing'])
    return head + '；-p 那一次没验过：' + str(row.get('one_shot', {}).get('note', row.get('note', '')))


# ── 入口 ──────────────────────────────────────────────────────────────────────
USAGE = '''用法：python engine_probe.py [选项]

  --engine <codex|claude|qwen>  验哪一支（默认 claude）
  --program <路径>               指定 CLI 的 .exe（默认按程序同一套口径去找）
  --model <模型 ID>              顺带验「程序带 --model 时那串参数」
  --dry-run                      不真跑：只报装在哪、参数长什么样
  --no-record                    不写台账（只打在屏幕上）
  --json                         把整条记录打到屏幕上
'''


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    engine, program, model, dry, write, show = 'claude', '', '', False, True, False
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == '--dry-run':
            dry = True
        elif arg == '--no-record':
            write = False
        elif arg == '--json':
            show = True
        elif arg in ('--engine', '--program', '--model'):
            index += 1
            if index >= len(args):
                print('%s 后面要跟一个值' % arg)
                return 2
            value = args[index]
            if arg == '--engine':
                if value not in ENGINES:
                    print('不认识的引擎：%s（可选的：%s）' % (value, '、'.join(ENGINES)))
                    return 2
                engine = value
            elif arg == '--program':
                program = value
            else:
                model = value
        elif arg in ('-h', '--help'):
            print(USAGE)
            return 0
        else:
            print('不认识的参数：%s\n\n%s' % (arg, USAGE))
            return 2
        index += 1
    print('引擎真机验证 · %s' % ENGINES[engine])
    folder = Path(tempfile.mkdtemp(prefix='engine_probe_'))
    try:
        row = probe(engine, program=program, model=model, offline=dry, workdir=folder)
    finally:
        from file_cache import remove_temporary_tree
        remove_temporary_tree(folder)
    print('  ' + summary(row))
    for flag, known in sorted(row.get('flags', {}).items()):
        print('    %s %s' % ('✅' if known else '❌', flag))
    if write and not dry:
        print('  台账：%s' % record(row))
    if show:
        print(json.dumps(row, ensure_ascii=False, indent=2))
    return 1 if row['verdict'] in ('installed-switches-missing', 'installed-one-shot-failed') else 0


if __name__ == '__main__':
    sys.exit(main())
