"""测试搬家轮守卫（规则 16）：搬家只许移动测试文件和修 import，不许改测试逻辑、断言或 fixture。

对一次改动里每个测试文件做核对：
- 新增或删除测试文件＝双份或伪迁移，不通过；
- 重命名或修改的测试文件，新旧内容的差异只能出现在 ``import``／``from … import`` 行，其它任何一行不同都不通过。

用法（程序目录下）::

    python -B scripts/test_move_audit.py                 # 核对已暂存的改动（提交前）
    python -B scripts/test_move_audit.py --commit <sha>  # 核对某个提交

``dev.py commit`` 在提交信息首行以「R<n>: 测试搬家」开头时自动核对暂存区，不通过即拒绝提交。
"""
from __future__ import annotations

import argparse
import difflib
import re
import subprocess
import sys
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
IMPORT_LINE = re.compile(r'^\s*(?:import\s+\S|from\s+\S+\s+import\s)')
MARKER = '测试搬家'
MOVE_ROUND = re.compile(r'^R\d+(?:-FAIL)?: *' + MARKER)


def is_move_round(message):
    """提交信息首行以「R<n>: 测试搬家」开头才算测试搬家轮（正文里提到这个词不算）。"""
    return bool(MOVE_ROUND.match(str(message).lstrip()))


def _git(repo, *args):
    done = subprocess.run(['git', '-c', 'core.quotepath=false', '-C', str(repo), *args], capture_output=True,
                          text=True, encoding='utf-8', errors='replace')
    return done.returncode, done.stdout


def is_test_path(path):
    parts = path.replace('\\', '/').split('/')
    return parts[-1].endswith('.py') and ('tests' in parts or (
        parts[-1].startswith('test_') and not {'scripts', 'skills', '维护记录'} & set(parts)))


def logic_changes(old, new):
    """新旧文本差异里不是 import 行的变动行（空即只改了 import）。"""
    diff = difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm='', n=0)
    return [line for line in diff if line[:1] in '+-' and not line.startswith(('+++', '---'))
            and not IMPORT_LINE.match(line[1:])]


def audit(repo, diff_args, old_rev, new_rev):
    """返回问题列表。``new_rev`` 为空串表示暂存区（``git show :路径``）。"""
    _code, listing = _git(repo, 'diff', '-M', '--name-status', *diff_args)
    problems = []
    for row in listing.splitlines():
        fields = row.split('\t')
        status, paths = fields[0][:1], fields[1:]
        if not any(is_test_path(path) for path in paths):
            continue
        if status in 'AD':
            problems.append('%s：测试文件被%s，搬家轮不许新增或删除测试（会造成双份或伪迁移）' % (
                paths[-1], '新增' if status == 'A' else '删除'))
            continue
        old_path, new_path = paths[0], paths[-1]
        _c, old = _git(repo, 'show', '%s:%s' % (old_rev, old_path))
        _c, new = _git(repo, 'show', '%s:%s' % (new_rev, new_path))
        changed = logic_changes(old, new)
        if changed:
            problems.append('%s：除 import 外还有 %d 行变动（如 %s）' % (new_path, len(changed), changed[0].strip()[:60]))
    return problems


def audit_staged(repo=PROGRAM.parent):
    return audit(repo, ['--cached'], 'HEAD', '')


def audit_commit(repo, sha):
    return audit(repo, [sha + '^', sha], sha + '^', sha)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--commit', help='核对这个提交；省略则核对暂存区')
    parser.add_argument('--repo', default=str(PROGRAM.parent))
    args = parser.parse_args(argv)
    problems = audit_commit(args.repo, args.commit) if args.commit else audit_staged(args.repo)
    for line in problems:
        sys.stdout.write(line + '\n')
    sys.stdout.write('测试搬家核对：%d 个问题\n' % len(problems))
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main())
