"""轮次证据：凭据扫描与定向测试由门禁自己执行并落成机器可读文件，不靠结果文件里的文字自述。

用法（程序目录下）::

    python -B 维护记录/基准脚本/round_evidence.py <轮次号> [-k 模块关键词 ...]

产出 ``tasks_round/evidence/R<N>.json``；``round_gate.py`` 读取它判定，不再匹配结果文件措辞。
扫描只看已暂存改动的新增行；命中只记录「文件:行:规则名」，不保存任何命中的取值。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[2]
ROOT = PROGRAM.parent
EVIDENCE_DIR = PROGRAM / 'tasks_round' / 'evidence'
SECRET_PATTERNS = (
    ('private-key', re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----')),
    ('openai-style-key', re.compile(r'\bsk-[A-Za-z0-9_-]{20,}')),
    ('aws-access-key', re.compile(r'\bAKIA[0-9A-Z]{16}\b')),
    ('assigned-secret', re.compile(r'(?i)\b(?:api[_-]?key|secret|token|password)\b\s*[:=]\s*[\'"][A-Za-z0-9_\-/+=]{24,}[\'"]')),
)
EVIDENCE_REQUIRED_FROM = 2527
ALLOWED_SKIPS = ('docs-only', 'merge-ci-exit')
PASSED_RE = re.compile(r'共 (\d+) 条用例')
RED_RE = re.compile(r'(\d+) 个文件有红')


def _git(*args, cwd=ROOT):
    return subprocess.run(['git', '-c', 'core.quotepath=false', *args], cwd=cwd, capture_output=True,
                          text=True, encoding='utf-8', errors='replace')


def scan_lines(path, lines):
    """返回 ``path:行号:规则名`` 列表；不含命中的取值。"""
    return ['%s:%d:%s' % (path, number, name) for number, line in lines
            for name, pattern in SECRET_PATTERNS if pattern.search(line)]


def staged_added_lines(root=ROOT):
    """已暂存改动的新增行：``[(path, [(行号, 文本)])]``。"""
    out = _git('diff', '--cached', '-U0', '--no-color', cwd=root).stdout
    result, path, number = {}, None, 0
    for raw in out.splitlines():
        if raw.startswith('+++ '):
            path = raw[6:] if raw.startswith('+++ b/') else None
        elif raw.startswith('@@'):
            matched = re.search(r'\+(\d+)', raw)
            number = int(matched.group(1)) if matched else 0
        elif raw.startswith('+') and path:
            result.setdefault(path, []).append((number, raw[1:]))
            number += 1
    return list(result.items())


def credential_scan(root=ROOT):
    hits = []
    for path, lines in staged_added_lines(root):
        if path.replace('\\', '/').startswith('程序/tasks_round/evidence/'):
            continue
        hits += scan_lines(path, lines)
    return {'ran': True, 'hits': hits}


def targeted_tests(keywords, python=sys.executable, cwd=PROGRAM):
    """跑 ``run_selftests.py -k 关键词``；返回命令、退出码、用例数与红文件数。"""
    command = [python, '-B', 'run_selftests.py', '-k', *keywords]
    done = subprocess.run(command, cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    text = done.stdout + done.stderr
    total, red = PASSED_RE.search(text), RED_RE.search(text)
    return {'cmd': ' '.join(['run_selftests.py', '-k', *keywords]), 'exit': done.returncode,
            'passed': int(total.group(1)) if total else 0,
            'failed': int(red.group(1)) if red else (0 if 'ALL TESTS PASSED' in text else -1)}


def evidence_path(number, directory=EVIDENCE_DIR):
    return Path(directory) / ('R%d.json' % number)


def staged_code_changed(root=ROOT):
    """已暂存改动里是否含 ``程序/`` 下的 .py（决定是否必须有定向测试证据）。"""
    names = _git('diff', '--cached', '--name-only', cwd=root).stdout.splitlines()
    return any(name.startswith('程序/') and name.endswith('.py') for name in names)


def write_evidence(number, keywords, directory=EVIDENCE_DIR, root=ROOT, run_tests=targeted_tests, skip=None):
    base = _git('rev-parse', '--short', 'HEAD', cwd=root).stdout.strip()
    if skip:
        targeted = {'cmd': '', 'exit': 0, 'passed': 0, 'failed': 0, 'skipped': skip}
    elif keywords:
        targeted = run_tests(keywords)
    elif staged_code_changed(root):
        targeted = {'cmd': '', 'exit': -1, 'passed': 0, 'failed': -1}
    else:
        targeted = {'cmd': '', 'exit': 0, 'passed': 0, 'failed': 0, 'skipped': 'docs-only'}
    document = {'round': number, 'commit_base': base, 'credential_scan': credential_scan(root),
                'targeted': targeted, 'generated_at': datetime.now().isoformat(timespec='seconds')}
    target = evidence_path(number, directory)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return target


def judge(number, directory=EVIDENCE_DIR):
    """``(凭据扫描是否通过, 定向测试是否通过, 说明)``；证据缺失、未执行或有命中即不通过。"""
    if number < EVIDENCE_REQUIRED_FROM:
        return True, True, 'R%d 早于证据文件制度（R%d 起），豁免' % (number, EVIDENCE_REQUIRED_FROM)
    target = evidence_path(number, directory)
    if not target.is_file():
        return False, False, '缺少 %s' % target.name
    try:
        data = json.loads(target.read_text(encoding='utf-8'))
    except ValueError:
        return False, False, '%s 不是合法 JSON' % target.name
    scan, tests = data.get('credential_scan') or {}, data.get('targeted') or {}
    scan_ok = scan.get('ran') is True and not scan.get('hits')
    tests_ok = tests.get('skipped') in ALLOWED_SKIPS and tests.get('exit') == 0 or (
        tests.get('exit') == 0 and tests.get('failed') == 0 and tests.get('passed', 0) > 0)
    return scan_ok, tests_ok, 'scan hits=%s, tests exit=%s failed=%s' % (
        len(scan.get('hits') or []), tests.get('exit'), tests.get('failed'))


HEADER_PREFIX = '<!-- round-evidence: '
HEADER_RE = re.compile(r'^<!-- round-evidence: .* -->$', re.M)


def result_header(number, directory=EVIDENCE_DIR):
    """结果文件头里的机器可读一行：类型、命令、退出码、通过／失败数、证据文件摘要与基线提交。"""
    target = evidence_path(number, directory)
    raw = target.read_bytes()
    data = json.JSONDecoder().decode(raw.decode('utf-8'))
    tests = data.get('targeted') or {}
    summary = {'round': number, 'commit_base': data.get('commit_base', ''),
               'tests': tests.get('skipped') or tests.get('cmd', ''), 'exit': tests.get('exit'),
               'passed': tests.get('passed'), 'failed': tests.get('failed'),
               'credential_hits': len((data.get('credential_scan') or {}).get('hits') or []),
               'evidence_sha256': hashlib.sha256(raw).hexdigest()[:16]}
    return HEADER_PREFIX + json.dumps(summary, ensure_ascii=False, sort_keys=True) + ' -->'


def stamp_result(result, number, directory=EVIDENCE_DIR):
    """把机器头写进结果文件标题行之后（已有则替换）；文件不存在返回 False。"""
    result = Path(result)
    if not result.is_file():
        return False
    header = result_header(number, directory)
    text = result.read_text(encoding='utf-8')
    if HEADER_RE.search(text):
        text = HEADER_RE.sub(lambda _match: header, text, count=1)
    else:
        first, _, rest = text.partition('\n')
        text = first + '\n' + header + '\n' + rest
    result.write_text(text, encoding='utf-8', newline='\n')
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('round', type=int)
    parser.add_argument('-k', '--keywords', nargs='*', default=[], help='定向测试的模块关键词')
    args = parser.parse_args(argv)
    target = write_evidence(args.round, args.keywords)
    scan_ok, tests_ok, detail = judge(args.round)
    print('%s: %s' % (target, detail))
    return 0 if scan_ok and tests_ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
