r"""升级前快照与回滚演练（U4／U8）。

``snapshot``：覆盖式升级之前，把当前开发目录按《分发清单》构建成一份完整副本，放进
开发目录同级的 ``<目录名>_升级快照/<版本>_<提交前8位>_<时间>``（构建器不许输出落在开发目录内），构建后立即校验；只保留最近 ``KEEP`` 份，更早的整份删除。
``drill``：在隔离的快照副本上做回滚演练——校验摘要，再用副本自带的解释器导入主要入口模块，
证明这一份真能拿来退回去。``check_upgrade``：覆盖式升级之后，对照分发副本的
``分发清单.json`` 逐文件核对安装目录；不一致即混合态，从升级前快照整份恢复。
三者都不写开发目录里的任何程序文件。

用法（随附解释器）::

    python.exe -B scripts\release_snapshot.py --snapshot
    python.exe -B scripts\release_snapshot.py --drill 升级快照\<某一份>
    python.exe -B scripts\release_snapshot.py --check-upgrade <安装目录> --package <分发副本>
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


def check_upgrade(package, install) -> dict:
    """升级后核对：安装目录里每个包内清单条目必须与新副本逐字节一致。

    覆盖式升级只写 ``分发清单.json`` 列出的程序文件；config.json、projects.json、
    desktop_settings.json、private、data 运行数据与用户项目不在包内，本函数不核对
    也不触碰。``ok=False`` 表示安装目录处于混合态或未拷全，应按发布检查单从升级前
    快照整份恢复。
    """
    package, install = Path(package), Path(install)
    digest_path = package / distribution_build.DIGEST_NAME
    saved = (distribution_build.read_json_file(digest_path, default=None)
             if digest_path.is_file() else None)
    if not isinstance(saved, dict):
        return {'ok': False, 'checked': 0, 'missing': [], 'mismatch': [],
                'error': '分发清单缺失或无法解析：' + str(digest_path)}
    entries = saved.get('entries') or []
    missing, mismatch = [], []
    for item in entries:
        target = install / item['path']
        if not target.is_file():
            missing.append(item['path'])
        elif distribution_build._sha256(target) != item.get('sha256'):
            mismatch.append(item['path'])
    return {'ok': not missing and not mismatch, 'checked': len(entries),
            'missing': missing[:20], 'mismatch': mismatch[:20]}


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
    parser.add_argument('--check-upgrade', default='', metavar='安装目录')
    parser.add_argument('--package', default='', metavar='分发副本')
    parser.add_argument('--allow-undecided', action='store_true')
    args = parser.parse_args(argv)
    if args.check_upgrade:
        report = check_upgrade(args.package, args.check_upgrade)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report['ok'] else 1
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
