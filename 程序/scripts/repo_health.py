# -*- coding: utf-8 -*-
"""开发侧仓库体检：计划预览（默认）与执行（--run）。

三段仓库卫生复用产品模块 ``workspace_maintenance`` 的谓词与统计，不复制逻辑；
本脚本额外承担产品退出链里绝不做的高成本动作：``git gc --auto`` 与
``git worktree prune`` 的即时回收。开发机手工跑或每轮收尾跑：

    运行环境\\Python\\python.exe -B scripts\\repo_health.py            # 只看计划
    运行环境\\Python\\python.exe -B scripts\\repo_health.py --run      # 真正执行

git 调用走 subprocess（开发脚本先例：维护记录/基准脚本/round_gate.py），
不在产品分层扫描范围；执行前逐项打印 kept 原因，工作树永不 --force。
"""
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

PROGRAM = Path(__file__).resolve().parents[1]
DIST_ROOT = PROGRAM.parent
sys.path.insert(0, str(PROGRAM))

from infra import workspace_maintenance as wm


def git(args):
    return subprocess.run(['git', '-c', 'core.quotepath=off', '-C', str(DIST_ROOT), *args],
                          capture_output=True, text=True, encoding='utf-8', errors='replace')


def repo_size():
    result = git(['count-objects', '-vH'])
    return (result.stdout or '').strip() if result.returncode == 0 else '不可用'


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    dry_run = '--run' not in argv
    print('== 仓库卫生（%s） ==' % ('预览，不改动' if dry_run else '执行'))
    summary = wm.maintain_repository(program=PROGRAM, dist_root=DIST_ROOT, dry_run=dry_run)
    for key in ('pycache', 'selftmp'):
        part = summary[key]
        print(f"{key}: 移除 {part['removed_entries']} 项 / {part['removed_bytes'] / 1048576:.2f} MiB，错误 {part['errors']}")
    worktrees = summary['worktrees']
    print(f"worktrees: git={worktrees['git']}")
    for item in worktrees['removed']:
        print(f"  移除 {item['name']} @ {item['head'][:12]}（{item['bytes'] / 1048576:.1f} MiB，{item['files']} 文件）")
    for name, reason in worktrees['kept']:
        print(f"  保留 {name}: {reason}")
    print(f"合计释放：{summary['released_bytes'] / 1048576:.2f} MiB{'（计划）' if dry_run else ''}")
    if dry_run:
        print('执行请加 --run；git gc / stash 报告仅在 --run 时输出。')
        return 0
    print('== git 维护（仅开发脚本，产品退出链绝不执行） ==')
    before = repo_size()
    result = git(['gc', '--auto', '--quiet'])
    if result.returncode != 0:
        print('gc 失败：', (result.stderr or '').strip())
    git(['worktree', 'prune'])
    stash = git(['stash', 'list'])
    stash_lines = [line for line in (stash.stdout or '').splitlines() if line.strip()]
    print(f"stash：{len(stash_lines)} 条（仅报告，不删除）")
    for line in stash_lines:
        print(' ', line)
    print('gc 前对象库：', before.splitlines()[-1] if before else '不可用')
    print('gc 后对象库：', repo_size().splitlines()[-1] if repo_size() else '不可用')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
