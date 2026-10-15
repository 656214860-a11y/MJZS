r"""分发副本自检：构建 → 校验 → 用副本自带的解释器导入主要入口模块。

只往系统临时目录写，结束即由 ``TemporaryDirectory`` 回收，不碰开发目录。随附 Python 是裁剪版，
这一步能在发布前发现“开发机能跑、副本缺文件／缺标准库”的问题。

用法（随附解释器）::

    python.exe -B scripts\distribution_selfcheck.py
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import distribution_build  # noqa: E402

ENTRY_MODULES = ('app_logging', 'diagnostic_capture', 'model_pool', 'desktop', 'app')


def run(root: Path | None = None) -> list[str]:
    """返回问题列表；空表示通过。"""
    root = Path(root or distribution_build.ROOT)
    problems: list[str] = []
    with tempfile.TemporaryDirectory(prefix='dist_selfcheck_') as tmp:
        destination = Path(tmp) / 'out'
        try:
            distribution_build.build(destination, root)
        except ValueError as exc:
            return ['构建失败：' + str(exc)]
        report = distribution_build.verify(destination)
        if not report.get('ok', False):
            problems.append('校验未通过：' + str({k: v for k, v in report.items() if k != 'files'})[:400])
        python = destination / '运行环境' / 'Python' / 'python.exe'
        program = destination / '程序'
        if not python.is_file():
            return problems + ['副本缺少随附解释器']
        code = ('import sys,os;os.chdir(sys.argv[1]);sys.path.insert(0,sys.argv[1]);'
                'import importlib;[importlib.import_module(n) for n in sys.argv[2:]];print("ok")')
        done = subprocess.run([str(python), '-I', '-B', '-c', code, str(program), *ENTRY_MODULES],
                              capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=180)
        if done.returncode != 0 or 'ok' not in done.stdout:
            problems.append('副本导入入口模块失败：' + (done.stderr or done.stdout)[-600:])
    return problems


def main() -> int:
    problems = run()
    for line in problems:
        print('[分发自检]', line)
    print('[分发自检]', '通过' if not problems else '未通过')
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main())
