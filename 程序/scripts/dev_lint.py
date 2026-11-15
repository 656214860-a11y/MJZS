r"""开发期静态分析：ruff（真缺陷规则）+ mypy（契约层），配置见 程序/pyproject.toml。

工具用系统 Python 安装（见 dev-requirements.txt），不进 运行环境\Python，也不进分发副本；
任一工具缺失即报错退出，不静默跳过。
"""
import shutil
import subprocess
import sys
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]


def main() -> int:
    ruff = shutil.which('ruff')
    if not ruff:
        print('未找到 ruff：pip install -r dev-requirements.txt', file=sys.stderr)
        return 2
    steps = [[ruff, 'check', '--no-cache', '.'], ['python', '-m', 'mypy']]
    if shutil.which('python') is None:
        steps[1][0] = sys.executable
    code = 0
    for cmd in steps:
        code |= subprocess.call(cmd, cwd=str(PROGRAM)) != 0
    return int(code)


if __name__ == '__main__':
    raise SystemExit(main())
