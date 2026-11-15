"""外部工具哈希锁：核对随附解释器与已登记工具的完整性（开发期检查，不进分发副本）。

用法（程序目录下）::

    python -B scripts/tools_lock.py --check    # 核对 external_tools.lock.json，失配退出 1
    python -B scripts/tools_lock.py --update   # 重新生成锁文件（解释器升级后执行）

锁文件只登记仓库自带、可复现的二进制（``运行环境/Python/python.exe``）；
ffmpeg 等用户自配路径不锁——它们由 config.json 指向，属用户环境。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
ROOT = PROGRAM.parent
LOCK = PROGRAM / 'external_tools.lock.json'


def _bundled_interpreter() -> Path:
    """随附解释器在主检出（运行环境不随工作树复制）；工作树里没有时回落到主工作区。"""
    local = ROOT / '运行环境' / 'Python' / 'python.exe'
    if local.is_file():
        return local
    try:
        out = subprocess.run(['git', 'rev-parse', '--git-common-dir'], cwd=str(ROOT),
                             capture_output=True, text=True, timeout=15)
        common = Path(out.stdout.strip())
        if not common.is_absolute():
            common = (ROOT / common).resolve()
        main_root = common.parent
        candidate = main_root / '运行环境' / 'Python' / 'python.exe'
        if candidate.is_file():
            return candidate
    except (OSError, subprocess.SubprocessError):
        pass
    return local


BUNDLED = _bundled_interpreter()
CHUNK = 1 << 20


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(CHUNK), b''):
            digest.update(block)
    return digest.hexdigest()


def _version(path: Path) -> str:
    try:
        out = subprocess.run([str(path), '--version'], capture_output=True, text=True,
                             timeout=15, encoding='utf-8', errors='replace')
        return (out.stdout or out.stderr).strip().splitlines()[0] if (out.stdout or out.stderr).strip() else ''
    except (OSError, subprocess.SubprocessError):
        return ''


TOOL_NAME = '运行环境/Python/python.exe'


def _resolve(name: str) -> Path:
    """锁内相对路径 → 实际文件：本树没有时回落主工作区（运行环境不随工作树复制）。"""
    local = ROOT / name
    if local.is_file():
        return local
    try:
        out = subprocess.run(['git', 'rev-parse', '--git-common-dir'], cwd=str(ROOT),
                             capture_output=True, text=True, timeout=15)
        common = Path(out.stdout.strip())
        if not common.is_absolute():
            common = (ROOT / common).resolve()
        candidate = common.parent / name
        if candidate.is_file():
            return candidate
    except (OSError, subprocess.SubprocessError):
        pass
    return local


def build() -> dict:
    entry = {'sha256': _sha256(BUNDLED), 'bytes': BUNDLED.stat().st_size,
             'version': _version(BUNDLED)}
    return {'version': 1, 'note': '随附解释器与受控工具的完整性锁；--update 重新生成',
            'tools': {TOOL_NAME: entry}}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--update', action='store_true')
    args = parser.parse_args(argv)
    if not BUNDLED.is_file():
        print('随附解释器不存在：%s（跳过核对）' % BUNDLED)
        return 0
    if args.update or not LOCK.is_file():
        LOCK.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('已写入 %s' % LOCK.name)
        return 0
    lock = json.loads(LOCK.read_text(encoding='utf-8'))
    problems = []
    for name, meta in lock.get('tools', {}).items():
        path = _resolve(name)
        if not path.is_file():
            problems.append('%s：文件缺失' % name)
            continue
        actual = _sha256(path)
        if actual != meta.get('sha256'):
            problems.append('%s：sha256 不符（锁 %s… 实际 %s…）'
                            % (name, str(meta.get('sha256'))[:12], actual[:12]))
    for problem in problems:
        print('失配：' + problem, file=sys.stderr)
    if problems:
        return 1
    print('工具哈希核对通过：%d 项' % len(lock.get('tools', {})))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
