r"""升级前快照与回滚演练（U4／U8）。

``snapshot``：覆盖式升级之前，把当前开发目录按《分发清单》构建成一份完整副本，放进
开发目录同级的 ``<目录名>_升级快照/<版本>_<提交前8位>_<时间>``（构建器不许输出落在开发目录内），构建后立即校验；只保留最近 ``KEEP`` 份，更早的整份删除。
``drill``：在隔离的快照副本上做回滚演练——校验摘要，再用副本自带的解释器导入主要入口模块，
证明这一份真能拿来退回去。两者都不写开发目录里的任何程序文件。

用法（随附解释器）::

    python.exe -B scripts\release_snapshot.py --snapshot
    python.exe -B scripts\release_snapshot.py --drill 升级快照\<某一份>
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import distribution_build  # noqa: E402
from distribution_selfcheck import ENTRY_MODULES  # noqa: E402

KEEP = 3
SNAPSHOT_DIR = '升级快照'


def snapshot(root=None, destination_root=None, keep=KEEP, allow_undecided=False) -> dict:
    """构建并校验一份升级前快照；校验不过就删掉半成品并报错。返回含 path 的报告。"""
    root = Path(root or distribution_build.ROOT)
    folder = Path(destination_root or root.parent / (root.name + '_' + SNAPSHOT_DIR))
    label = distribution_build._git_binding(root)
    name = '%s_%s_%s' % (distribution_build._version() or 'unknown', (label['commit'] or 'nogit')[:8],
                         time.strftime('%Y%m%d_%H%M%S'))
    target = folder / name
    report = distribution_build.build(target, root, allow_undecided=allow_undecided)
    check = distribution_build.verify(target, root)
    if not check.get('ok'):
        shutil.rmtree(target, ignore_errors=True)
        raise ValueError('快照校验未通过，已删除半成品：' + str(target))
    for old in sorted(item for item in folder.iterdir() if item.is_dir())[:-keep]:
        shutil.rmtree(old, ignore_errors=True)
    return {'path': str(target), 'files': report['files'], 'commit': report.get('commit', ''),
            'round': report.get('round')}


def drill(snapshot_path, root=None) -> list[str]:
    """回滚演练：返回问题列表，空表示这份快照可用于回退。"""
    path = Path(snapshot_path)
    if not path.is_dir():
        return ['快照目录不存在：' + str(path)]
    problems: list[str] = []
    report = distribution_build.verify(path, root or distribution_build.ROOT)
    if not report.get('ok'):
        problems.append('快照校验未通过：' + str({k: v for k, v in report.items() if k != 'files'})[:400])
    python = path / '运行环境' / 'Python' / 'python.exe'
    if not python.is_file():
        return problems + ['快照缺少随附解释器']
    code = ('import sys,os;os.chdir(sys.argv[1]);sys.path.insert(0,sys.argv[1]);'
            'import importlib;[importlib.import_module(n) for n in sys.argv[2:]];print("ok")')
    done = subprocess.run([str(python), '-I', '-B', '-c', code, str(path / '程序'), *ENTRY_MODULES],
                          capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=180)
    if done.returncode != 0 or 'ok' not in done.stdout:
        problems.append('快照导入入口模块失败：' + (done.stderr or done.stdout)[-600:])
    return problems


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='升级前快照与回滚演练。')
    parser.add_argument('--snapshot', action='store_true')
    parser.add_argument('--drill', default='')
    parser.add_argument('--allow-undecided', action='store_true')
    args = parser.parse_args(argv)
    if args.drill:
        problems = drill(args.drill)
        for line in problems:
            print('[回滚演练]', line)
        print('[回滚演练]', '通过' if not problems else '未通过')
        return 1 if problems else 0
    if args.snapshot:
        print(json.dumps(snapshot(allow_undecided=args.allow_undecided), ensure_ascii=False, indent=2))
        return 0
    parser.print_help()
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
