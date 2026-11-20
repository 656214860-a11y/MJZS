"""Temporarily materialise skill submodules for local test runs (no network, no git changes)."""
import shutil
import sys
from pathlib import Path

MAIN = Path(r'D:\漫剧制作助手\程序\skills\01 剧本准备SKILL')
TARGET = Path(r'D:\漫剧制作助手\.agents\worktrees\foundation-c8-updater\程序\skills\01 剧本准备SKILL')
NAMES = ['剧本锻造', '编剧技能集']


def copy_in():
    for name in NAMES:
        src = MAIN / name
        dst = TARGET / name
        if dst.exists() and any(dst.iterdir()):
            print('exists', dst)
            continue
        if dst.exists():
            dst.rmdir()
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns('.git'))
        print('copied', dst)


def remove():
    for name in NAMES:
        dst = TARGET / name
        if dst.exists():
            shutil.rmtree(dst)
            print('removed', dst)


if __name__ == '__main__':
    if sys.argv[1:] == ['remove']:
        remove()
    else:
        copy_in()
