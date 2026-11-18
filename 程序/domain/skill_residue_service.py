"""非阶段 SKILL 包的懒发现与回收；阶段／包口径和写发布器由 L3 注入。"""
import os
from pathlib import Path

from contract.service_contract import SystemError, UserError, success


def _linked(path):
    return any(part.is_symlink() or part.is_junction() for part in (path, *path.parents))


def _package_stats(package):
    size, count = 0, 0
    for folder, directories, files in os.walk(package, followlinks=False):
        base = Path(folder)
        directories[:] = [name for name in directories if not _linked(base / name)]
        for name in files:
            path = base / name
            if _linked(path) or not path.is_file():
                continue
            size += path.stat().st_size
            if path != package / 'SKILL.md' and (name == 'SKILL.md' or name.endswith('.skill.md')):
                count += 1
    return size, count


def scan_residue(program, *, stage_from_path, package_source):
    """只枚举根部非阶段包，00 容器按下一层整包展示；不触碰阶段注册表。"""
    program = Path(program).absolute()
    root = program / 'skills'
    if _linked(root) or not root.is_dir():
        return []
    rows = []
    for directory in sorted(root.iterdir(), key=lambda p: p.name):
        if (directory.name.startswith('.') or not directory.is_dir() or _linked(directory)
                or stage_from_path(directory / '__stage_probe__')):
            continue
        candidates = sorted(directory.iterdir(), key=lambda p: p.name) if directory.name == '00全流程SKILL' else [directory]
        for package in candidates:
            if not package.is_dir() or package.name.startswith('.') or _linked(package):
                continue
            source = package_source(package)
            size, count = _package_stats(package)
            rows.append({'name': package.name, 'path': str(package), 'kind': 'package',
                         'size': size, 'sub_skill_count': count,
                         'description': source.name if source else '无包说明',
                         'relative_path': package.relative_to(root).as_posix()})
    return rows


def dispose_residue(program, names, *, stage_from_path, package_source, publisher):
    """先校验整批唯一包目标，再经 recycle_paths 的原子批次回收并返回真实凭据。"""
    names = [names] if isinstance(names, str) else names
    if not isinstance(names, (list, tuple)) or not names or any(
            not isinstance(name, str) or not name.strip() for name in names):
        return UserError('请选择要回收的残留包')
    try:
        rows = scan_residue(program, stage_from_path=stage_from_path, package_source=package_source)
        targets = []
        root = Path(program).absolute()
        for name in names:
            matches = [row for row in rows if name in (row['name'], row['relative_path'])]
            if len(matches) != 1:
                return UserError('残留包不存在或名称不唯一，请刷新列表后重试')
            target = Path(matches[0]['path'])
            if _linked(target) or not target.resolve().is_relative_to((root / 'skills').resolve()):
                return UserError('残留包路径不安全，请刷新列表后重试')
            if target not in targets:
                targets.append(target)
        record = publisher(root.resolve(), targets, 'SKILL 管理：回收非阶段残留包')
        if not record:
            return UserError('残留包已不存在，请刷新列表后重试')
        return success({'records': record, 'paths': [str(path) for path in targets]}, '残留包已移入回收站')
    except ValueError as exc:
        return UserError(str(exc))
    except OSError as exc:
        return SystemError('残留包回收失败：%s' % exc)
