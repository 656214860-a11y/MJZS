#!/usr/bin/env python3
"""私有服务器 pre-receive 门禁：推送到 bare 仓库时做 Linux 可判定的静态检查。

部署：复制本文件到 ``<bare>.git/hooks/pre-receive`` 并 ``chmod +x``。
本脚本不依赖 Tk、不依赖项目解释器，只用 python3 标准库，推送方不需要 Windows 环境。

检查项（任一命中即拒绝整个 push，消息走 stderr）：

1. ``程序/`` 下新增/修改的 ``.py`` 逐个 ``compile()``：语法错误与无效转义
   （``SyntaxWarning`` 按错误处理）直接拒绝——对应本机 ``test_static_hygiene`` 的
   轻量子集；完整架构门禁仍在 Windows 本机跑。
2. 新增行里的高置信凭据形态（与 ``round_evidence.SECRET_PATTERNS`` 同族）。
3. 装了 gitleaks 时对推送提交区间跑全树密钥扫描（``GITLEAKS_BIN`` 指定二进制，
   默认 ``/srv/git/ci/bin/gitleaks``；配置取推送版的 ``程序/.gitleaks.toml``，
   缺失退回 ``GITLEAKS_CONFIG`` 部署副本）。gitleaks 未安装或自身报错不阻断，
   由第 2 项形态扫描兜底。
4. 推到 ``master``/``main`` 的 R2527 及以后轮次提交必须带同一提交里的绿色证据
   ``程序/tasks_round/evidence/R<n>.json``（凭据扫描已跑且无命中、定向测试退出码
   0 且无红；文档轮／合并轮按证据里的 skipped 记录放行），删除 master/main 一律
   拒绝。判据与 ``server_hooks/pre-receive``、``round_evidence.judge`` 同口径，
   其它分支不受此限。

stdin 协议：每行 ``<old> <new> <ref>``；``new`` 为全零是删分支，跳过静态检查，
但删除 ``master``/``main`` 会被第 4 项拒绝。
新分支的 old 用空树 ``4b825dc642cb6eb9a060e54bf8d69288fbee4904`` 做 diff 基线。
退出码：0 放行，1 拒绝。
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path

EMPTY_TREE = '4b825dc642cb6eb9a060e54bf8d69288fbee4904'
PROGRAM_PREFIX = '程序/'
GITLEAKS_BIN = os.environ.get('GITLEAKS_BIN', '/srv/git/ci/bin/gitleaks')
GITLEAKS_CONFIG = os.environ.get('GITLEAKS_CONFIG', '/srv/git/ci/.gitleaks.toml')
SECRET_PATTERNS = (
    ('private-key', re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----')),
    ('openai-style-key', re.compile(r'\bsk-[A-Za-z0-9_-]{20,}')),
    ('aws-access-key', re.compile(r'\bAKIA[0-9A-Z]{16}\b')),
    ('github-token', re.compile(r'\b(?:ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{22,}|gho_[A-Za-z0-9]{36}|ghu_[A-Za-z0-9]{36}|ghs_[A-Za-z0-9]{36}|ghr_[A-Za-z0-9]{36})\b')),
    ('slack-token', re.compile(r'\bxox[baprs]-[A-Za-z0-9-]{10,}\b')),
    ('google-api-key', re.compile(r'\bAIza[0-9A-Za-z_-]{35}\b')),
    ('assigned-secret', re.compile(r'(?i)\b(?:api[_-]?key|secret|token|password)\b\s*[:=]\s*[\'"][A-Za-z0-9_\-/+=]{24,}[\'"]')),
)


EVIDENCE_FROM = 2527
PROTECTED_REFS = ('refs/heads/master', 'refs/heads/main')
ZERO = '0' * 40
ALLOWED_SKIPS = ('docs-only', 'merge-ci-exit')
EVIDENCE_PATH = '程序/tasks_round/evidence/R%d.json'


def git(*args, repo=None):
    command = ['git', '-c', 'core.quotepath=false']
    if repo:
        command += ['--git-dir', str(repo)]
    command += list(args)
    return subprocess.run(command, capture_output=True, text=True,
                          encoding='utf-8', errors='replace')


def compile_check(rev, path):
    """返回错误描述或 None；SyntaxWarning 视为错误（与静态卫生门禁同口径）。"""
    shown = git('show', '%s:%s' % (rev, path))
    if shown.returncode:
        return None  # 二进制或读取失败不判，交给本机门禁
    source = shown.stdout
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', SyntaxWarning)
            compile(source, path, 'exec')
    except SyntaxError as exc:
        return '语法错误 %s:%s %s' % (path, exc.lineno, exc.msg)
    except SyntaxWarning as exc:
        return '无效转义 %s:%s %s' % (path, exc.lineno, exc.msg)
    return None


def _gitleaks_config(new):
    """优先用推送提交里的 程序/.gitleaks.toml，缺失退回 CI 部署副本。"""
    shown = git('show', '%s:%s' % (new, PROGRAM_PREFIX + '.gitleaks.toml'))
    if shown.returncode or not shown.stdout.strip():
        return GITLEAKS_CONFIG, None
    fd, path = tempfile.mkstemp(prefix='gitleaks-', suffix='.toml')
    with os.fdopen(fd, 'w', encoding='utf-8') as handle:
        handle.write(shown.stdout)
    return path, path


def gitleaks_scan(base, new):
    """装了 gitleaks 时对 ``base..new`` 提交区间做全树密钥扫描，返回命中描述。

    未装二进制或扫描器自身异常（非 1 退出码、超时、报告不可读）都返回 []——
    第 2 项形态扫描是硬门禁，gitleaks 是增强层，不能把故障升级为阻断。
    """
    if not (os.path.isfile(GITLEAKS_BIN) and os.access(GITLEAKS_BIN, os.X_OK)):
        return []
    config, temporary = _gitleaks_config(new)
    fd, report = tempfile.mkstemp(prefix='gitleaks-report-', suffix='.json')
    os.close(fd)
    try:
        done = subprocess.run(
            [GITLEAKS_BIN, 'git', '--log-opts', '%s..%s' % (base, new), '--redact',
             '--config', config, '--report-format', 'json', '--report-path', report, '.'],
            capture_output=True, text=True, timeout=300)
        if done.returncode != 1:
            return []
        findings = json.loads(Path(report).read_text(encoding='utf-8') or '[]')
        return ['gitleaks:%s %s:%s' % (item.get('RuleID', '?'), item.get('File', '?'),
                                     item.get('StartLine', '?')) for item in findings][:20]
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return []
    finally:
        for path in [report] + ([temporary] if temporary else []):
            try:
                os.unlink(path)
            except OSError:
                pass


def scan_added_lines(diff_text):
    """diff 输出里新增行的凭据命中：返回 ['path:line:rule']。"""
    hits = []
    path, number = None, 0
    for raw in diff_text.splitlines():
        if raw.startswith('+++ '):
            path = raw[6:] if raw.startswith('+++ b/') else None
        elif raw.startswith('@@'):
            matched = re.search(r'\+(\d+)', raw)
            number = int(matched.group(1)) if matched else 0
        elif raw.startswith('+') and path:
            for name, pattern in SECRET_PATTERNS:
                if pattern.search(raw[1:]):
                    hits.append('%s:%d:%s' % (path, number, name))
            number += 1
    return hits


def round_of(subject):
    """``R<n>: …`` 返回 n；``R<n>-FAIL: …`` 与其它标题返回 None。"""
    head = subject.split(':', 1)[0].strip()
    if head.startswith('R') and head[1:].isdigit() and ':' in subject:
        return int(head[1:])
    return None


def evidence_problem(raw):
    """证据文本不合格返回原因，合格返回空串（与 round_evidence.judge 同口径）。"""
    try:
        data = json.loads(raw)
    except ValueError:
        return '证据文件不是合法 JSON'
    scan, tests = data.get('credential_scan') or {}, data.get('targeted') or {}
    if scan.get('ran') is not True or scan.get('hits'):
        return '凭据扫描未执行或有命中'
    skipped_ok = tests.get('skipped') in ALLOWED_SKIPS and tests.get('exit') == 0
    if not (skipped_ok or (tests.get('exit') == 0 and tests.get('failed') == 0 and tests.get('passed', 0) > 0)):
        return '定向测试未通过或未执行'
    return ''


def commit_problems(sha, repo=None):
    subject = git('log', '-1', '--format=%s', sha, repo=repo).stdout.strip()
    number = round_of(subject)
    if number is None or number < EVIDENCE_FROM:
        return []
    parents = git('log', '-1', '--format=%P', sha, repo=repo).stdout
    names = git('show', '--name-only', '--format=', '-m', '--first-parent', sha,
                repo=repo).stdout
    needs = len(parents.split()) > 1 or any(n.startswith(PROGRAM_PREFIX) and n.endswith('.py')
                                           for n in names.splitlines())
    if not needs:
        return []
    shown = git('show', '%s:%s' % (sha, EVIDENCE_PATH % number), repo=repo)
    if shown.returncode:
        return ['%s R%d：缺少 %s' % (sha[:10], number, EVIDENCE_PATH % number)]
    reason = evidence_problem(shown.stdout)
    return ['%s R%d：%s' % (sha[:10], number, reason)] if reason else []


def check_push(old, new, ref, repo=None):
    """返回拒绝原因列表（空即放行）；只管 master/main，其它 ref 恒为空。"""
    if ref not in PROTECTED_REFS:
        return []
    if new == ZERO:
        return ['不允许删除 %s' % ref]
    if old == ZERO:
        return []
    listing = git('rev-list', '%s..%s' % (old, new), repo=repo).stdout
    problems = []
    for sha in listing.split():
        problems += commit_problems(sha, repo)
    return problems


def main() -> int:
    updates = [line.split() for line in sys.stdin if line.strip()]
    problems = []
    for old, new, ref in updates:
        problems.extend(check_push(old, new, ref))
        if set(new) == {'0'}:
            continue
        base = old if set(old) != {'0'} else EMPTY_TREE
        names = git('diff', '--name-only', '--diff-filter=ACMR', base, new, '--', PROGRAM_PREFIX).stdout.split()
        py_files = [n for n in names if n.endswith('.py')]
        for path in py_files:
            problem = compile_check(new, path)
            if problem:
                problems.append(problem)
        diff = git('diff', '-U0', '--no-color', base, new, '--', PROGRAM_PREFIX).stdout
        problems.extend(scan_added_lines(diff))
        problems.extend(gitleaks_scan(base, new))
    if problems:
        sys.stderr.write('pre-receive 拒绝：\n' + '\n'.join('  ' + p for p in problems[:50]) + '\n')
        if len(problems) > 50:
            sys.stderr.write('  …共 %d 项\n' % len(problems))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
