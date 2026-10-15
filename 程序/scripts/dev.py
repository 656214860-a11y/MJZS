r"""开发者统一入口：一个命令名对应一个既有实现，不另写第二套逻辑。

用法（随附解释器，在 程序\ 下）::

    python.exe -B scripts\dev.py            # 列出子命令
    python.exe -B scripts\dev.py smoke      # 默认冒烟
    python.exe -B scripts\dev.py arch       # 全部架构门禁
    python.exe -B scripts\dev.py full       # 安全全量自检
    python.exe -B scripts\dev.py debt       # 全量欠账与后台补跑状态
    python.exe -B scripts\dev.py ci         # 本地 CI（冒烟 + 安全全量，日志写 logs/ci_最近.log）
    python.exe -B scripts\dev.py dist       # 分发副本自检（构建 → 校验 → 导入入口）
    python.exe -B scripts\dev.py health     # 仓库健康检查
    python.exe -B scripts\dev.py logs       # 日志维护（--dry-run 可预览）
    python.exe -B scripts\dev.py claim      # 领取下一个轮次号
子命令后面的参数原样传给底层脚本。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
COMMANDS = {
    'smoke': (['smoke_test.py'], '默认冒烟'),
    'arch': (['smoke_test.py', '--architecture'], '全部架构门禁'),
    'full': (['run_selftests.py', '--all', '--safe'], '安全全量自检'),
    'debt': (['scripts/auto_full_safe.py', '--status'], '全量欠账与后台补跑状态'),
    'ci': (['scripts/local_ci.py'], '本地 CI'),
    'dist': (['scripts/distribution_selfcheck.py'], '分发副本自检'),
    'health': (['scripts/repo_health.py'], '仓库健康检查'),
    'logs': (['scripts/maintain_logs.py'], '日志维护'),
    'claim': (['维护记录/基准脚本/round_claim.py', 'next'], '领取下一个轮次号'),
}


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in COMMANDS:
        print('用法：dev.py <子命令> [参数]')
        for name, (_, note) in COMMANDS.items():
            print(f'  {name:7s}{note}')
        return 0 if not argv else 2
    target, _ = COMMANDS[argv[0]]
    return subprocess.call([sys.executable, '-B', str(PROGRAM / target[0]), *target[1:], *argv[1:]], cwd=str(PROGRAM))


if __name__ == '__main__':
    raise SystemExit(main())
