"""将版本受控的协作 Git hooks 安装到当前仓库的共享 hooks 目录。"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


PROGRAM = Path(__file__).resolve().parents[2]
ROOT = PROGRAM.parent
SOURCE = Path(__file__).resolve().parent / "hooks"
HOOKS = ("commit-msg", "pre-commit")


def git_common_dir(root: Path = ROOT) -> Path:
    result = subprocess.run(["git", "-C", str(root), "rev-parse", "--git-common-dir"],
                            text=True, capture_output=True, check=True)
    path = Path(result.stdout.strip())
    return path if path.is_absolute() else (root / path).resolve()


def install(common_dir: Path | None = None) -> list[Path]:
    target = (common_dir or git_common_dir()) / "hooks"
    target.mkdir(parents=True, exist_ok=True)
    installed = []
    for name in HOOKS:
        destination = target / name
        shutil.copyfile(SOURCE / name, destination)
        destination.chmod(destination.stat().st_mode | 0o111)
        installed.append(destination)
    return installed


if __name__ == "__main__":
    for path in install():
        print(path)
