"""轮次提交前的机械门禁；仅使用标准库，失败项以非零状态返回。

阈值取自 ``维护记录/测试分层基线.json``（只增不减），凭据扫描与定向测试读 ``round_evidence.py``
产出的 ``tasks_round/evidence/R<N>.json``，不再匹配结果文件里的措辞。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[2]
ROOT = PROGRAM.parent
BASELINE = PROGRAM / '维护记录' / '测试分层基线.json'
sys.path.insert(0, str(Path(__file__).resolve().parent))
import round_evidence  # noqa: E402


def git(*args):
    return subprocess.run(['git', '-C', str(ROOT), *args], text=True, capture_output=True,
                          check=False, encoding="utf-8", errors="replace")


def check(name, ok, detail):
    print(('GREEN' if ok else 'RED') + ' ' + name + ': ' + detail)
    return ok


def load_floors(path=BASELINE):
    """基线 JSON 里的门禁下界；缺字段按 0 处理，使门禁对缺失基线保持红色。"""
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        data = {}
    return {key: int(data.get(key, 0) or 0) for key in
            ('architecture_gate_files_min', 'skill_registry_count', 'smoke_checks_expected')}


def staging_forbidden(staged):
    """暂存区里不许出现的 tasks_round 文件；证据目录 ``tasks_round/evidence/`` 放行。"""
    return [name for name in staged if '/tasks_round/' in name.replace('\\', '/')
            and '/tasks_round/evidence/' not in name.replace('\\', '/')]


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('branch'); parser.add_argument('round', type=int)
    args = parser.parse_args(argv); all_ok = True
    floors = load_floors()
    all_ok &= check('branch', git('branch', '--show-current').stdout.strip() == args.branch, args.branch)
    sys.path.insert(0, str(PROGRAM))
    import smoke_test
    smoke_count = len(smoke_test.ROUND_CHECKS[smoke_test.ROUND])
    all_ok &= check('smoke', smoke_count == floors['smoke_checks_expected'] > 0,
                    '%d (基线 %d)' % (smoke_count, floors['smoke_checks_expected']))
    architecture = list((PROGRAM / 'tests' / 'architecture').glob('test_*.py'))
    all_ok &= check('architecture', len(architecture) >= floors['architecture_gate_files_min'] > 0,
                    '%d files (下界 %d)' % (len(architecture), floors['architecture_gate_files_min']))
    import skill_registry
    count = skill_registry.default_registry().count()
    all_ok &= check('registry', count == floors['skill_registry_count'] > 0,
                    '%d (基线 %d)' % (count, floors['skill_registry_count']))
    status = (PROGRAM / 'project_status.md').read_text(encoding='utf-8')
    match = re.search(r'当前轮次：(\d+)', status)
    all_ok &= check('round-continuity', bool(match) and int(match.group(1)) == args.round,
                    'status=' + (match.group(1) if match else 'missing'))
    result = PROGRAM / 'tasks_round' / f'tasks_round_{args.round}_result.md'
    all_ok &= check('result-present', result.exists(), str(result))
    scan_ok, tests_ok, detail = round_evidence.judge(args.round)
    all_ok &= check('credential-scan', scan_ok, detail)
    all_ok &= check('targeted-evidence', tests_ok, detail)
    staged = git('diff', '--cached', '--name-only').stdout.splitlines()
    forbidden = staging_forbidden(staged)
    all_ok &= check('staging-boundary', not forbidden,
                    'no staged tasks_round files' if not forbidden else ', '.join(forbidden))
    return 0 if all_ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
