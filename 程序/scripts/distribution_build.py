r"""按《分发清单》构建并校验可复制的正式分发副本。

声明来源是同目录上一级的 `distribution_manifest.md`（其中「必须保留」「必须排除」两张表，
表里只认反引号里的路径／模式）。本模块只从开发目录读、往新的输出目录写；
**绝不**在开发目录里删除、移动或重命名任何东西。

用法（用随附解释器）::

    python.exe -B scripts\distribution_build.py --plan
    python.exe -B scripts\distribution_build.py --build --destination D:\out\发行版
    python.exe -B scripts\distribution_build.py --verify --destination D:\out\发行版
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
PROGRAM = ROOT / '程序'
MANIFEST = PROGRAM / 'distribution_manifest.md'
DIGEST_NAME = '分发清单.json'

# 构建器安全兜底：不管清单怎么写，源控制元数据与字节码缓存都不进正式副本。
ALWAYS_EXCLUDE = ('.git', '.git/**', '**/.git/**', '__pycache__/**', '**/__pycache__/**',
                  '*.pyc', '**/*.pyc')
JINGJU_PACKAGE = '程序/skills/00全流程SKILL/jingju-skills'

_ROW = re.compile(r'^\|\s*(.+?)\s*\|')
_TOKEN = re.compile(r'`([^`]+)`')
_CACHE_DIRS = frozenset({'.git', '__pycache__'})


def pattern_regex(pattern: str):
    """把清单里的路径模式翻成正则：`**` 跨目录、`*` 不跨、目录以 `/` 结尾表示整棵子树。"""
    text = str(pattern or '').strip().replace('\\', '/')
    if not text:
        return None
    if text.endswith('/'):
        text += '**'
    parts, index = [], 0
    while index < len(text):
        if text.startswith('**', index):
            parts.append('.*')
            index += 2
        elif text[index] == '*':
            parts.append('[^/]*')
            index += 1
        elif text[index] == '?':
            parts.append('[^/]')
            index += 1
        else:
            parts.append(re.escape(text[index]))
            index += 1
    return re.compile('^' + ''.join(parts) + '$')


def parse_manifest(path=MANIFEST) -> dict:
    """从清单两张表里取模式；不认识的段落一律忽略。"""
    text = Path(path).read_text(encoding='utf-8')
    sections = {'keep': [], 'exclude': []}
    current = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith('#'):
            if '必须保留' in stripped:
                current = 'keep'
            elif '必须排除' in stripped:
                current = 'exclude'
            else:
                current = None
            continue
        if current is None:
            continue
        row = _ROW.match(stripped)
        if not row:
            continue
        for token in _TOKEN.findall(row.group(1)):
            token = token.strip()
            if token and token not in sections[current]:
                sections[current].append(token)
    return sections


def candidate_files(root) -> list:
    """列出 root 下的普通文件（相对路径、正斜杠）；不跟进符号链接，跳过 VCS 与字节码目录。"""
    base = Path(root)
    files, stack = [], [base]
    while stack:
        folder = stack.pop()
        try:
            entries = sorted(folder.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.is_symlink():
                continue
            if entry.is_dir():
                if entry.name not in _CACHE_DIRS:
                    stack.append(entry)
            elif entry.is_file():
                files.append(entry.relative_to(base).as_posix())
    return sorted(files)


def plan(root=ROOT, manifest=None) -> dict:
    """分三桶：清单要保留的、清单要排除的、以及清单没提、需要人工决定的。"""
    manifest = manifest or parse_manifest()
    keeps = [rx for rx in (pattern_regex(p) for p in manifest['keep']) if rx]
    drops = [rx for rx in (pattern_regex(p) for p in list(manifest['exclude'])
                           + list(ALWAYS_EXCLUDE)) if rx]
    buckets = {'keep': [], 'excluded': [], 'undecided': []}
    for relative in candidate_files(root):
        if any(rx.match(relative) for rx in drops):
            buckets['excluded'].append(relative)
        elif any(rx.match(relative) for rx in keeps):
            buckets['keep'].append(relative)
        else:
            buckets['undecided'].append(relative)
    return buckets


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def read_json_file(path, default=None):
    """经 `agent.core.read_json` 读 JSON：与产品同一条读取链，不在这里裸 `json.loads`。"""
    try:
        if str(PROGRAM) not in sys.path:
            sys.path.insert(0, str(PROGRAM))
        from agent.core import read_json
        return read_json(path, default=default)
    except Exception:
        return default


def _version() -> str:
    try:
        if str(PROGRAM) not in sys.path:
            sys.path.insert(0, str(PROGRAM))
        from app_metadata import VERSION
        return str(VERSION)
    except Exception:
        return ''


def build(destination, root=ROOT, manifest=None, allow_undecided=False) -> dict:
    """把清单内的文件复制到全新输出目录，并写版本与逐文件摘要；源目录一个字节都不改。"""
    manifest = manifest or parse_manifest()
    base = Path(root).resolve()
    if destination is None:
        raise ValueError('必须给出输出目录（--destination）')
    dest = Path(destination).resolve()
    if dest == base or base in dest.parents:
        raise ValueError('输出目录不能落在开发目录内部：' + str(dest))
    if dest.exists() and any(dest.iterdir()):
        raise ValueError('输出目录不是空的，拒绝覆盖：' + str(dest))
    buckets = plan(base, manifest)
    if buckets['undecided'] and not allow_undecided:
        raise ValueError('还有 %d 个文件不在清单里（未决定是否分发），前几个：%s；'
                         '请先补清单，或显式 --allow-undecided。'
                         % (len(buckets['undecided']), buckets['undecided'][:5]))
    selected = list(buckets['keep'])
    if allow_undecided:
        selected += buckets['undecided']
    entries = []
    for relative in selected:
        source = base / relative
        target = dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        entries.append({'path': relative, 'bytes': source.stat().st_size,
                        'sha256': _sha256(source)})
    report = {'version': _version(),
              'generated_at': datetime.now().isoformat(timespec='seconds'),
              'root': str(base), 'files': len(entries),
              'bytes': sum(item['bytes'] for item in entries),
              'keep_patterns': list(manifest['keep']),
              'exclude_patterns': list(manifest['exclude']) + list(ALWAYS_EXCLUDE),
              'entries': entries}
    (dest / DIGEST_NAME).write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                    encoding='utf-8')
    return report


def verify(destination, root=ROOT, manifest=None) -> dict:
    """校验一个已经建好的输出目录：不含排除项、入口齐全、摘要自洽、jingju 整包还在。"""
    manifest = manifest or parse_manifest()
    dest = Path(destination).resolve()
    present = candidate_files(dest)
    drops = [rx for rx in (pattern_regex(p) for p in manifest['exclude']) if rx]
    leaked = [rel for rel in present if any(rx.match(rel) for rx in drops)]
    missing = [pattern for pattern in manifest['keep']
               if not any(pattern_regex(pattern).match(rel) for rel in present)]
    digest_path = dest / DIGEST_NAME
    digest = {'ok': False, 'files': 0, 'mismatch': [], 'extra': []}
    if digest_path.is_file():
        saved = read_json_file(digest_path, default=None)
        if isinstance(saved, dict):
            entries = saved.get('entries') or []
            mismatch = [item['path'] for item in entries
                        if not (dest / item['path']).is_file()
                        or _sha256(dest / item['path']) != item.get('sha256')]
            listed = {item['path'] for item in entries}
            extra = [rel for rel in present if rel not in listed and rel != DIGEST_NAME]
            digest = {'ok': not mismatch and not extra, 'files': len(entries),
                      'mismatch': mismatch[:20], 'extra': extra[:20]}
    jingju = dest / JINGJU_PACKAGE / 'SKILL.md'
    checks = {
        'no_excluded': {'ok': not leaked, 'count': len(leaked), 'hits': leaked[:20]},
        'keep_present': {'ok': not missing, 'missing': missing},
        'digest': digest,
        'jingju_package': {'ok': jingju.is_file(), 'path': str(jingju)},
    }
    return {'ok': all(item['ok'] for item in checks.values()),
            'destination': str(dest), 'checks': checks}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='按《分发清单》构建并校验正式分发副本。')
    parser.add_argument('--root', default=str(ROOT))
    parser.add_argument('--destination', default='')
    parser.add_argument('--plan', action='store_true')
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--allow-undecided', action='store_true')
    args = parser.parse_args(argv)
    if args.verify:
        report = verify(args.destination, args.root)
    elif args.build:
        report = build(args.destination, args.root, allow_undecided=args.allow_undecided)
    else:
        buckets = plan(args.root)
        report = {'keep': len(buckets['keep']), 'excluded': len(buckets['excluded']),
                  'undecided': len(buckets['undecided']),
                  'undecided_sample': buckets['undecided'][:10],
                  'excluded_sample': buckets['excluded'][:10]}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.verify or args.build:
        return 0 if report.get('ok', True) else 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
