"""轮次提交前的机械门禁；仅使用标准库，失败项以非零状态返回。"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[2]
ROOT = PROGRAM.parent


def git(*args):
    return subprocess.run(['git', '-C', str(ROOT), *args], text=True, capture_output=True, check=False)


def check(name, ok, detail):
    print(('GREEN' if ok else 'RED') + ' ' + name + ': ' + detail)
    return ok


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('branch'); parser.add_argument('round', type=int)
    args = parser.parse_args(argv); all_ok = True
    all_ok &= check('branch', git('branch','--show-current').stdout.strip() == args.branch, args.branch)
    sys.path.insert(0, str(PROGRAM))
    import smoke_test
    smoke_count = len(smoke_test.ROUND_CHECKS[smoke_test.ROUND])
    all_ok &= check('smoke-8', smoke_count == 8, str(smoke_count))
    architecture = list((PROGRAM/'tests'/'architecture').glob('test_*.py'))
    all_ok &= check('architecture', len(architecture) >= 14, str(len(architecture)) + ' files')
    import skill_registry
    all_ok &= check('registry-73', skill_registry.default_registry().count() == 73,
                    str(skill_registry.default_registry().count()))
    status = (PROGRAM/'project_status.md').read_text(encoding='utf-8')
    match = re.search(r'当前轮次：(\d+)', status)
    all_ok &= check('round-continuity', bool(match) and int(match.group(1)) == args.round,
                    'status=' + (match.group(1) if match else 'missing'))
    result = PROGRAM/'tasks_round'/f'tasks_round_{args.round}_result.md'
    result_text = result.read_text(encoding='utf-8') if result.exists() else ''
    all_ok &= check('result-present', result.exists(), str(result))
    all_ok &= check('targeted-evidence', bool(re.search(r'(?:定向|affected).*(?:0\s*红|PASSED)', result_text, re.I)),
                    'result scan')
    all_ok &= check('credential-scan', '凭据扫描' in result_text or '密钥扫描' in result_text, 'result scan')
    staged = git('diff','--cached','--name-only').stdout.splitlines()
    forbidden = [name for name in staged if '/tasks_round/' in name.replace('\\','/')]
    all_ok &= check('staging-boundary', not forbidden, 'no staged tasks_round files' if not forbidden else ', '.join(forbidden))
    return 0 if all_ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
