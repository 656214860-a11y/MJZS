"""校验 git bundle 备份：对目录下 ``*.bundle`` 逐个 ``git bundle verify`` 并汇总。

T1 远端备份链路的本机侧校验入口：服务器 ``/srv/git/ci/weekly_bundle.sh`` 每周一
04:00 产出 ``manju-<日期>.bundle``（只留最近 4 份），本脚本核对目录里的 bundle
能否被 git 完整读回，防「文件在但已损坏」的静默备份失效。

用法（随附解释器）::

    python -B scripts/backup_verify.py                    # 默认 /srv/git/backups
    python -B scripts/backup_verify.py D:\\backups         # 指定 bundle 目录
    python -B scripts/backup_verify.py --repo /srv/git/manju-assistant.git

bundle 校验需要仓库上下文（``git bundle verify`` 在非仓库目录报
``need a repository to verify a bundle``）；``--all`` 产出的 bundle 是完整历史，
但 verify 仍要有仓库解析引用。默认在 ``<目录>/../manju-assistant.git`` 找到
服务器 bare 仓库自动带上；也可用 ``--repo`` 显式指定，或在任一 git 仓库里运行。

退出码：0 全部通过；1 存在校验失败或目录下没有 bundle；2 参数/环境错误。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

DEFAULT_DIR = '/srv/git/backups'
DEFAULT_KEEP = 4
GIT_TIMEOUT = 120


def verify_bundle(path: Path, repo: str | None = None) -> tuple[bool, str]:
    """跑 ``git bundle verify``，返回 (是否通过, 说明)。"""
    command = ['git']
    if repo:
        command += ['-C', repo]
    command += ['bundle', 'verify', str(path)]
    try:
        done = subprocess.run(command, capture_output=True, text=True,
                              encoding='utf-8', errors='replace', timeout=GIT_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, 'git 调用失败：%s' % exc
    tail = (done.stderr or done.stdout or '').strip().splitlines()
    detail = tail[-1] if tail else ('退出码 %d' % done.returncode)
    return done.returncode == 0 and 'okay' in (done.stdout + done.stderr), detail


def collect_bundles(directory: Path) -> list[Path]:
    return sorted((p for p in directory.glob('*.bundle') if p.is_file()), key=lambda p: p.name)


def guess_repo(directory: Path) -> str | None:
    """服务器布局 ``/srv/git/backups`` 的同级 bare 仓库 ``/srv/git/manju-assistant.git``。"""
    candidate = directory.parent / 'manju-assistant.git'
    return str(candidate) if candidate.is_dir() else None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='校验 git bundle 备份目录')
    parser.add_argument('directory', nargs='?', default=None,
                        help='bundle 目录（默认 %s 或环境变量 MANJU_BUNDLE_DIR）' % DEFAULT_DIR)
    parser.add_argument('--repo', default=None,
                        help='带前提 bundle 校验时使用的仓库路径（git -C）')
    parser.add_argument('--keep', type=int, default=DEFAULT_KEEP,
                        help='预期保留份数，只做提示不判负（默认 %d）' % DEFAULT_KEEP)
    args = parser.parse_args(argv)

    raw = args.directory or os.environ.get('MANJU_BUNDLE_DIR') or DEFAULT_DIR
    directory = Path(raw)
    if not directory.is_dir():
        print('[backup_verify] 目录不存在：%s' % directory)
        return 2
    bundles = collect_bundles(directory)
    if not bundles:
        print('[backup_verify] %s 下没有 *.bundle' % directory)
        return 1

    repo = args.repo or guess_repo(directory)
    failures = []
    for bundle in bundles:
        ok, detail = verify_bundle(bundle, repo)
        mark = 'OK ' if ok else 'FAIL'
        print('[backup_verify] %s %s（%d 字节）%s' % (mark, bundle.name,
              bundle.stat().st_size, '' if ok else ' — ' + detail))
        if not ok:
            failures.append(bundle.name)

    newest = max(bundles, key=lambda p: p.stat().st_mtime)
    print('[backup_verify] 共 %d 份，最新 %s；预期保留 %d 份'
          % (len(bundles), newest.name, args.keep))
    if len(bundles) > args.keep:
        print('[backup_verify] 提示：份数超过保留上限 %d，weekly_bundle.sh 应已裁剪' % args.keep)
    if failures:
        print('[backup_verify] 失败 %d 份：%s' % (len(failures), '、'.join(failures)))
        return 1
    print('[backup_verify] 全部通过')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
