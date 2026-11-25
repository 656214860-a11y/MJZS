# -*- coding: utf-8 -*-
"""用户级项目 zip 备份导出与校验导入还原（REL-06B）。

纯 L2 业务模块：不 import tkinter，打包／清点／校验解包全走标准库 ``zipfile``。
包格式 ``ARCHIVE_FORMAT``：zip 根放 ``manifest.json``（app_version、original_root、
file_count、逐文件 size/sha256/mtime、脱敏与跳过记录），项目文件统一放在 ``project/`` 前缀下。
``config.json``／``cloud_video/*/config.json``／``projects.json`` 中命中密钥
字段的非空字符串写成 ``<已移除>`` 脱敏副本，命中记入 ``manifest.redacted``。
"""
import hashlib
import json
import os
import re
import shutil
import stat
import time
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

from agent.core import replace
from contract.app_metadata import VERSION
from infra import file_cache

ARCHIVE_FORMAT = 'manju-project-archive/1'
_ARCHIVE_FAMILY = ARCHIVE_FORMAT.rsplit('/', 1)[0]
_ARCHIVE_MAJOR = int(ARCHIVE_FORMAT.rsplit('/', 1)[1])
MAX_FILE_BYTES = 4 * 1024 ** 3
REDACTED = '<已移除>'
_SECRET_KEY = re.compile(r'(?i)(api[_-]?key|secret|token|password)')
_EXCLUDED_NAMES = frozenset({'__pycache__', '.thumbs', 'thumbs', '缩略图'})
_EXCLUDED_SUFFIXES = frozenset({'.lock', '.pyc', '.tmp', '.part'})
_PAYLOAD_PREFIX = 'project/'


def _slug(path):
    """目录名片段：去掉日期／序号尾巴，与 ``projects._slug`` 同规则。"""
    return re.sub(r'_\d{8}(?:_\d+)?$', '', Path(path).name)


def _project_dir_openable(path):
    """能打开的登记目录：是目录且内含 config.json（同 projects.project_dir_openable 判据）。"""
    if not str(path or ''):
        return False
    root = Path(path)
    return root.is_dir() and (root / 'config.json').is_file()


def _excluded(name):
    return (name in _EXCLUDED_NAMES
            or PurePosixPath(name).suffix.lower() in _EXCLUDED_SUFFIXES)


def _is_link(path):
    return os.path.islink(path) or os.path.isjunction(path)


def _secret_target(rel):
    parts = rel.split('/')
    return rel in ('config.json', 'projects.json') or (
        len(parts) == 3 and parts[0] == 'cloud_video' and parts[2] == 'config.json')


def _zip_time(path):
    return time.localtime(path.stat().st_mtime)[:6]


def _walk_project(root, notes):
    """收集待打包的普通文件与目录；排除锁文件、缓存目录与链接（含 junction）。"""
    files, dirs = [], []
    for folder, dir_names, file_names in os.walk(root):
        keep = []
        for name in dir_names:
            full = os.path.join(folder, name)
            if _is_link(full):
                notes.append('跳过链接目录：' + Path(full).relative_to(root).as_posix())
            elif _excluded(name):
                notes.append('排除目录：' + Path(full).relative_to(root).as_posix())
            else:
                keep.append(name)
        dir_names[:] = keep
        if folder != str(root):
            dirs.append(folder)
        for name in file_names:
            full = os.path.join(folder, name)
            if _is_link(full):
                notes.append('跳过链接文件：' + Path(full).relative_to(root).as_posix())
            elif _excluded(name):
                notes.append('排除文件：' + Path(full).relative_to(root).as_posix())
            else:
                files.append(Path(full))
    files.sort(key=lambda item: item.relative_to(root).as_posix())
    dirs.sort()
    return files, dirs


def _redact_value(value, hits, prefix=''):
    if isinstance(value, dict):
        out = {}
        for key, val in value.items():
            if isinstance(val, str) and val and _SECRET_KEY.search(str(key)):
                hits.append(prefix + str(key))
                out[key] = REDACTED
            else:
                out[key] = _redact_value(val, hits, prefix + str(key) + '.')
        return out
    if isinstance(value, list):
        return [_redact_value(item, hits, prefix) for item in value]
    return value


def _redact_file(path, rel, manifest):
    """密钥防线：命中字段的值替换成脱敏副本；解析不了的文件按原样打包并记录。"""
    raw = path.read_bytes()
    try:
        data = file_cache.read_json(path)
    except (OSError, ValueError):
        manifest['notes'].append('密钥字段未能解析，按原样打包：' + rel)
        return raw
    if not isinstance(data, dict):
        return raw
    hits = []
    redacted = _redact_value(data, hits)
    manifest['redacted'].extend(rel + '#' + key for key in hits)
    return json.dumps(redacted, ensure_ascii=False, indent=2).encode('utf-8')


def _verify_zip(path, manifest):
    """写完的包整体读回，逐文件复核 sha256 后才允许原子改名。"""
    try:
        with zipfile.ZipFile(path) as zf:
            for row in manifest['files']:
                digest = hashlib.sha256()
                with zf.open(_PAYLOAD_PREFIX + row['path']) as src:
                    for chunk in iter(lambda: src.read(1024 * 1024), b''):
                        digest.update(chunk)
                if digest.hexdigest() != row['sha256']:
                    raise ValueError('备份包校验失败：' + row['path'])
    except BaseException:
        file_cache.remove_temporary_file(path)
        raise


def _pack_member(zf, root, full, rel, manifest):
    """把单个项目文件写进包并登记 manifest 行；密钥目标先过脱敏副本。"""
    info = zipfile.ZipInfo(_PAYLOAD_PREFIX + rel, _zip_time(full))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o600 << 16
    if _secret_target(rel):
        data = _redact_file(full, rel, manifest)
        zf.writestr(info, data)
        digest = hashlib.sha256(data).hexdigest()
        size = len(data)
    else:
        digest = hashlib.sha256()
        with full.open('rb') as src, zf.open(info, 'w', force_zip64=True) as out:
            for chunk in iter(lambda: src.read(1024 * 1024), b''):
                digest.update(chunk)
                out.write(chunk)
        digest = digest.hexdigest()
        size = full.stat().st_size
    manifest['files'].append({'path': rel, 'size': size, 'sha256': digest,
                              'mtime': full.stat().st_mtime})
    manifest['total_bytes'] += size


def export_project(projects, path, *, dest_dir=None):
    """把已登记的项目目录打成 zip 备份包，返回包路径。

    命名 ``<slug>_<YYYYMMDD-HHMMSS>.zip``（重名补 ``_2`` 等序号）。单文件
    大于 4GB、或项目总量超过目标盘可用空间一半时拒绝；链接与缓存目录不打
    入包，全部记入 ``manifest.notes``。
    """
    root = Path(path)
    if root not in {Path(item.get('path', '')) for item in
                    getattr(projects, 'info', {}).get('projects', [])}:
        raise ValueError('项目未登记，不能导出备份包：' + str(root))
    if not _project_dir_openable(root):
        raise ValueError('项目目录不可打开（缺 config.json）：' + str(root))
    dest = Path(dest_dir) if dest_dir is not None else Path(projects.downloads)
    dest.mkdir(parents=True, exist_ok=True)
    notes = []
    files, dirs = _walk_project(root, notes)
    total = 0
    for item in files:
        size = item.stat().st_size
        if size > MAX_FILE_BYTES:
            raise ValueError('单个文件超过 4GB，不能打包：' + item.name)
        total += size
    if total > shutil.disk_usage(dest).free // 2:
        raise ValueError('目标盘剩余空间不足项目内容的一半，拒绝导出备份包。')
    item = next((row for row in projects.info['projects']
                 if Path(row.get('path', '')) == root), {})
    name = str(item.get('name') or _slug(root))
    slug = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)[:50].rstrip('. ') or '项目'
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    final = dest / (slug + '_' + stamp + '.zip')
    serial = 2
    while final.exists():
        final = dest / (slug + '_' + stamp + '_' + str(serial) + '.zip')
        serial += 1
    part = final.with_name(final.name + '.part')
    manifest = {'format': ARCHIVE_FORMAT, 'app_version': VERSION, 'name': name,
                'original_root': str(root), 'exported_at': datetime.now().isoformat(timespec='seconds'),
                'files': [], 'dirs': [], 'redacted': [], 'notes': notes, 'total_bytes': 0}
    try:
        with zipfile.ZipFile(part, 'w', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
            for folder in dirs:
                manifest['dirs'].append(Path(folder).relative_to(root).as_posix())
            for full in files:
                _pack_member(zf, root, full, full.relative_to(root).as_posix(), manifest)
            manifest['file_count'] = len(manifest['files'])
            zf.writestr('manifest.json',
                        json.dumps(manifest, ensure_ascii=False, indent=1).encode('utf-8'))
    except BaseException:
        file_cache.remove_temporary_file(part)
        raise
    _verify_zip(part, manifest)
    replace(part, final)
    return final


def _format_major(fmt):
    """``manju-project-archive/<N>`` 的主版本号；不属于本格式族时返回 None。"""
    if not isinstance(fmt, str):
        return None
    head, _, tail = fmt.rpartition('/')
    if head != _ARCHIVE_FAMILY or not re.fullmatch(r'[0-9]+', tail):
        return None
    return int(tail)


def inspect_archive(zip_path):
    """读取备份包 ``manifest.json`` 并核对格式；非本格式族或主版本号高于当前时拒绝。"""
    path = Path(zip_path)
    try:
        with zipfile.ZipFile(path) as zf:
            try:
                raw = zf.read('manifest.json')
            except KeyError:
                raise ValueError('不是漫剧项目备份包（缺少 manifest.json）：' + path.name)
    except zipfile.BadZipFile:
        raise ValueError('不是有效的 zip 备份包：' + path.name)
    try:
        manifest = json.JSONDecoder().decode(raw.decode('utf-8'))
    except (UnicodeDecodeError, ValueError):
        raise ValueError('备份包清单损坏：' + path.name)
    if not isinstance(manifest, dict):
        raise ValueError('不是漫剧项目备份包（format 不符）：' + path.name)
    major = _format_major(manifest.get('format'))
    if major is None:
        raise ValueError('不是漫剧项目备份包（format 不符）：' + path.name)
    if major > _ARCHIVE_MAJOR:
        raise ValueError('备份包格式版本高于本应用支持的 %s：%s' % (ARCHIVE_FORMAT, path.name))
    return manifest


def _safe_member(rel):
    """manifest 里的相对路径必须是 posix 风格、不含 ``..``、盘符与反斜杠。"""
    if not isinstance(rel, str) or not rel or '\\' in rel or rel.startswith('/'):
        return None
    if any(part in ('', '.', '..') for part in rel.split('/')):
        return None
    if re.match(r'(?i)^[a-z]:', rel):
        return None
    return rel


def _member_target(dest, rel):
    target = dest.joinpath(*rel.split('/'))
    if not target.resolve().is_relative_to(dest.resolve()):
        raise ValueError('备份包含越界路径：' + rel)
    return target


def _zip_is_link(info):
    return stat.S_ISLNK(info.external_attr >> 16)


def remove_scratch_dir(path):
    """清理本轮导入自己的 ``._import_`` 临时解包目录；项目层源码不含永久删除原语。"""
    file_cache.remove_temporary_tree(path)


def extract_archive(zip_path, dest_dir):
    """校验并解包到 ``dest_dir``；目标已存在即拒绝，任一文件 sha256 对不上就删掉 ``dest_dir`` 并拒绝。"""
    manifest = inspect_archive(zip_path)
    dest = Path(dest_dir)
    if dest.exists():
        raise ValueError('目标目录已存在，拒绝覆盖：' + str(dest))
    dest.mkdir(parents=True)
    try:
        with zipfile.ZipFile(zip_path) as zf:
            members = {info.filename: info for info in zf.infolist()}
            for rel_dir in manifest.get('dirs') or []:
                safe = _safe_member(rel_dir)
                if safe is None:
                    raise ValueError('备份包含非法路径：' + str(rel_dir))
                _member_target(dest, safe).mkdir(parents=True, exist_ok=True)
            for row in manifest.get('files') or []:
                rel = row.get('path') if isinstance(row, dict) else None
                safe = _safe_member(rel)
                if safe is None:
                    raise ValueError('备份包含非法路径：' + str(rel))
                info = members.get(_PAYLOAD_PREFIX + safe)
                if info is None or info.is_dir() or _zip_is_link(info):
                    raise ValueError('备份包校验失败：' + safe)
                target = _member_target(dest, safe)
                target.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                with zf.open(info) as src, target.open('wb') as out:
                    for chunk in iter(lambda: src.read(1024 * 1024), b''):
                        digest.update(chunk)
                        out.write(chunk)
                if digest.hexdigest() != row.get('sha256'):
                    raise ValueError('备份包校验失败：' + safe)
                if isinstance(row.get('mtime'), (int, float)):
                    os.utime(target, (row['mtime'], row['mtime']))
    except BaseException:
        file_cache.remove_temporary_tree(dest)
        raise
    return dest
