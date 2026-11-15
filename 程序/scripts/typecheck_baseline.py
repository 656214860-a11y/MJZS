"""开发期类型检查基线（不进产品、不进发布包）：用 pyright 数每个模块的错误，错误数只许减少。

用法（程序目录下，需要 Node／npx 和联网；产品运行时与随附解释器不依赖它）::

    python -B scripts/typecheck_baseline.py --check     # 与 维护记录/类型检查基线.json 比较，任何模块变多即失败
    python -B scripts/typecheck_baseline.py --update    # 总数不增加时刷新基线（要放宽须加 --force 并说明理由）

口径固定为 pyright ``basic``、Python 3.13、缺失的第三方导入不报错；统计范围是 ``程序/`` 下除测试、技能、
维护记录、脚本等目录以外的生产模块。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
BASELINE = PROGRAM / '维护记录' / '类型检查基线.json'
PYRIGHT = 'pyright@1.1.414'
TOOL = 'pyright 1.1.414 basic python3.13'
EXCLUDE = ['**/tests', '**/skills', '**/维护记录', '**/tasks_round', '**/logs', '**/data', '**/__pycache__',
           '**/.wt', '**/scripts', '**/outputs', '**/附加工具', '**/private', '**/docs', '**/.selftmp']


SKIP_TOP = frozenset({'tests', 'skills', 'scripts', '维护记录', 'tasks_round', 'logs', 'data', 'outputs', '附加工具',
                      'private', 'docs', '.wt', '.selftmp', '__pycache__'})


def config_for(root, base):
    return {'include': [Path(os.path.relpath(root, base)).as_posix()], 'exclude': EXCLUDE,
            'typeCheckingMode': 'basic', 'pythonVersion': '3.13', 'reportMissingImports': 'none',
            'reportMissingModuleSource': 'none'}


def count_errors(report, root):
    """pyright ``--outputjson`` 报告 → ``{相对路径: 错误数}``；只数 error。"""
    counts = {}
    for item in report.get('generalDiagnostics', []):
        if item.get('severity') != 'error':
            continue
        name = Path(item['file']).resolve().relative_to(Path(root).resolve()).as_posix()
        if name.split('/')[0] in SKIP_TOP:
            continue
        counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items()))


def compare(baseline, current):
    """返回变差的模块：``{路径: (基线, 当前)}``；基线里没有的模块按 0 算。"""
    return {name: (baseline.get(name, 0), count) for name, count in current.items() if count > baseline.get(name, 0)}


def run_pyright(root=PROGRAM):
    with tempfile.TemporaryDirectory() as temporary:
        config = Path(temporary) / 'pyrightconfig.json'
        config.write_text(json.dumps(config_for(root, temporary)), encoding='utf-8')
        done = subprocess.run(['npx', '-y', PYRIGHT, '-p', str(config), '--outputjson'], capture_output=True,
                              text=True, encoding='utf-8', errors='replace', shell=(os.name == 'nt'))
    start = done.stdout.find('{')
    if start < 0:
        raise RuntimeError('pyright 没有输出报告：' + (done.stderr or done.stdout)[-300:])
    return count_errors(json.JSONDecoder().decode(done.stdout[start:]), root)


def document(counts):
    return {'tool': TOOL, 'total': sum(counts.values()), 'modules': counts}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check', action='store_true')
    group.add_argument('--update', action='store_true')
    parser.add_argument('--force', action='store_true', help='允许总数增加地刷新基线')
    args = parser.parse_args(argv)
    current = run_pyright()
    old = json.JSONDecoder().decode(BASELINE.read_text(encoding='utf-8')) if BASELINE.is_file() else {'modules': {}}
    worse = compare(old.get('modules', {}), current)
    if args.check:
        sys.stdout.write('类型错误总数 %d（基线 %d）\n' % (sum(current.values()), old.get('total', 0)))
        for name, (before, now) in sorted(worse.items()):
            sys.stdout.write('变差：%s %d → %d\n' % (name, before, now))
        return 1 if worse else 0
    if worse and not args.force and BASELINE.is_file():
        sys.stdout.write('拒绝刷新：以下模块错误变多（%s）；确需放宽加 --force\n' % ', '.join(sorted(worse)))
        return 1
    BASELINE.write_text(json.dumps(document(current), ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    sys.stdout.write('基线已刷新：%d 个模块，共 %d 处\n' % (len(current), sum(current.values())))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
