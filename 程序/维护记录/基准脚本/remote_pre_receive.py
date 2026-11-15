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

stdin 协议：每行 ``<old> <new> <ref>``；``new`` 为全零是删分支，跳过。
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


def git(*args):
    return subprocess.run(['git', '-c', 'core.quotepath=false', *args], capture_output=True, text=True,
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


def main() -> int:
    updates = [line.split() for line in sys.stdin if line.strip()]
    problems = []
    for old, new, ref in updates:
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
