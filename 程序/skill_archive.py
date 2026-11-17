# -*- coding: utf-8 -*-
"""SKILL 压缩包（ZIP）导入的安全解包与候选装配（L4 服务，无 Tk）。

与 ``skill_import_service.import_from_repo`` 共用同一条「候选扫描→阶段判定→
``plan_import`` 预检→确认→``perform_import`` 换入→试冻结→台账登记」管线；
本模块只负责把 ``.zip`` 安全落到暂存目录，并把暂存目录交给该管线。

安全口径（``master_skill_update`` 已随 R2862 总控下线，无现存共享实现，
按任务书「复制改名」精神在此自含）：

- 条目数上限 ``ARCHIVE_MAX_ENTRIES``（与 ``PACKAGE_MAX_FILES`` 同量级另设常量）；
- 解压后总体积上限复用 ``PACKAGE_MAX_BYTES``；
- 拒绝绝对路径、盘符（``C:``／``C:\\``）、UNC、``..`` 穿越与控制字符条目；
- 只写普通文件，不解符号链接语义（zipfile 本就不落链接）；
- 加密条目直接拒绝（本应用不需要解密包）。
"""
from __future__ import annotations

import re
import shutil
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import NamedTuple

import skill_import_service
import skill_registry
from storage_maintenance import recycle_paths

ARCHIVE_STAGING_PREFIX = '.压缩包解压-'
# ZIP 条目数上限：与包文件数护栏同量级，单独成常量便于按压缩包口径调整。
ARCHIVE_MAX_ENTRIES = 2000
_ENCRYPTED_FLAG = 0x1
_CHUNK = 1024 * 1024


def _unsafe(message, name):
    return skill_import_service.ImportBlocked('压缩包条目不安全：「%s」（%s）' % (name, message))


def _member_relpath(name):
    """把 ZIP 条目名规范成安全相对路径；目录条目返回 None，不安全抛 ImportBlocked。"""
    text = str(name or '').replace('\\', '/')
    if not text or text.endswith('/'):
        return None
    if text.startswith('/') or text.startswith('~') or re.match(r'^[A-Za-z]:', text):
        raise _unsafe('绝对路径或盘符', name)
    parts = PurePosixPath(text).parts
    if '..' in parts or not parts:
        raise _unsafe('路径穿越', name)
    if any('\x00' <= ch <= '\x1f' or ch == ':' for part in parts for ch in part):
        raise _unsafe('非法字符', name)
    return parts


def _check_members(archive):
    """条目数、加密标记与解压后总体积护栏；返回可落盘的 (info, parts) 列表。"""
    infos = archive.infolist()
    if len(infos) > ARCHIVE_MAX_ENTRIES:
        raise skill_import_service.ImportBlocked(
            '压缩包含超过 %d 个条目上限' % ARCHIVE_MAX_ENTRIES)
    total = 0
    members = []
    for info in infos:
        if info.flag_bits & _ENCRYPTED_FLAG:
            raise skill_import_service.ImportBlocked(
                '压缩包含加密条目「%s」，本应用不解密导入' % info.filename)
        parts = _member_relpath(info.filename)
        total += int(info.file_size or 0)
        if total > skill_import_service.PACKAGE_MAX_BYTES:
            raise skill_import_service.ImportBlocked(
                '压缩包解压后总体积超过 %d MB 上限'
                % (skill_import_service.PACKAGE_MAX_BYTES // 1024 // 1024))
        members.append((info, parts))
    return members


def _extract(zip_path, dest):
    """把 ZIP 安全解到 ``dest``；任何一步失败抛 ImportBlocked，调用方负责回收暂存。"""
    zip_path = Path(zip_path)
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    try:
        archive = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile as exc:
        raise skill_import_service.ImportBlocked('不是有效的 ZIP 压缩包（%s）' % exc) from exc
    except OSError as exc:
        raise skill_import_service.ImportBlocked('读不出压缩包（%s）' % exc) from exc
    with archive:
        members = _check_members(archive)
        for info, parts in members:
            if parts is None:
                continue
            target = dest.joinpath(*parts)
            try:
                resolved = target.resolve()
                if not resolved.is_relative_to(dest.resolve()):
                    raise skill_import_service.ImportBlocked(
                        '压缩包含不安全路径「%s」' % info.filename)
            except OSError as exc:
                raise skill_import_service.ImportBlocked(
                    '压缩包路径无法解析（%s）' % exc) from exc
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                with archive.open(info) as src, open(target, 'wb') as out:
                    shutil.copyfileobj(src, out, _CHUNK)
            except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
                raise skill_import_service.ImportBlocked(
                    '解压条目「%s」失败（%s）' % (info.filename, exc)) from exc


def _staging_name(zip_path):
    """解压容器名取压缩包文件名主干，去掉 Windows 非法字符；根级 SKILL.md 包以此命名。"""
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', Path(zip_path).stem).strip(' .')
    return (stem or '压缩包')[:80]


def _scope_root(root, scope):
    """ZIP 内子目录作用域（远程 GitHub ``/tree/<ref>/<子目录>`` 用）：必须是解压根内的目录。"""
    parts = [part for part in str(scope).replace('\\', '/').split('/') if part]
    if not parts or any(part in ('.', '..') for part in parts):
        raise skill_import_service.ImportBlocked('压缩包子目录路径不安全：「%s」' % scope)
    target = Path(root).joinpath(*parts)
    resolved = target.resolve()
    if not resolved.is_relative_to(Path(root).resolve()):
        raise skill_import_service.ImportBlocked('压缩包子目录越界：「%s」' % scope)
    if not resolved.is_dir():
        raise skill_import_service.ImportBlocked('压缩包中没有目录「%s」' % scope)
    return resolved


class ArchiveOptions(NamedTuple):
    """``import_archive`` 的可选参数包：``install_source`` 覆盖台账来源，
    ``scope`` 限定包内子目录（如 GitHub ``/tree/<ref>/<子目录>``），
    ``layer`` 是安装目标层（``'user'``／``'project'``）。"""
    install_source: object = None
    scope: str = ''
    layer: str = 'user'


def import_archive(zip_path, program, registry, stage_hint='', confirm=None, *,
                   options=None):
    """ZIP 导入主入口：安全解包 → 候选扫描 → 与仓库导入同一条安装管线。

    返回 ``{'label', 'installed', 'failed', 'skipped', 'candidates'}``，
    结构与 ``skill_import_service.import_from_repo`` 一致；台账 ``source``
    记压缩包绝对路径、``source_kind`` 记 ``archive``。

    ``options.install_source``：远程链接导入（``skill_remote_service``）传入的
    :class:`skill_import_service._InstallSource`，覆盖台账来源与 ``source_url``／
    ``source_ref``。
    """
    program = Path(program)
    zip_path = Path(zip_path)
    options = options or ArchiveOptions()
    staging = (skill_registry.default_user_root(program)
               / (ARCHIVE_STAGING_PREFIX + uuid.uuid4().hex[:8]))
    root = staging / _staging_name(zip_path)
    try:
        _extract(zip_path, root)
        if options.scope:
            root = _scope_root(root, options.scope)
        candidates = skill_import_service._repo_candidates(root)
        if not candidates:
            raise skill_import_service.ImportBlocked(
                '压缩包中没有找到 SKILL.md 或 *.skill.md')
        plans, problems, errors = skill_import_service._candidate_plans(
            candidates, root, registry, stage_hint, layer=options.layer)
        source = options.install_source or skill_import_service._InstallSource(
            ledger_source=str(zip_path.resolve()), label=zip_path.name,
            source_kind='archive', origin='压缩包')
        return skill_import_service._install_candidate_plans(
            plans, problems, errors, program, confirm, source)
    finally:
        if staging.exists():
            recycle_paths(program, [staging], 'SKILL 压缩包解压暂存收尾')


def archive_entry_digests(zip_path, program, registry, scope='', layer='user'):
    """ZIP → ``{台账键: 内容摘要}``：安全解包到暂存（用后回收）→ 候选扫描 → 逐候选摘要。

    更新检测专用：只读不安装；``scope`` 与 ``import_archive`` 同义（包内子目录），
    ``layer`` 是台账行所在层（``'user'``／``'project'``），决定候选键的口径。
    """
    program = Path(program)
    zip_path = Path(zip_path)
    staging = (skill_registry.default_user_root(program)
               / (ARCHIVE_STAGING_PREFIX + uuid.uuid4().hex[:8]))
    root = staging / _staging_name(zip_path)
    try:
        _extract(zip_path, root)
        if scope:
            root = _scope_root(root, scope)
        return skill_import_service._entry_digests(root, registry, layer)
    finally:
        if staging.exists():
            recycle_paths(program, [staging], 'SKILL 更新检测解包暂存收尾')


def probe_row(key, row, program, registry):
    """本地 ZIP 台账行的更新探测：``source_kind=='archive'`` 且无 ``source_url`` 才接管。

    返回 ``'unchanged'|'source-newer'|'source-missing'``；不接管的行返回 ``None``
    （交给 ``skill_import_service`` 的默认判定或远程探针）。
    """
    if str(row.get('source_kind') or '') != 'archive' or row.get('source_url'):
        return None
    source = str(row.get('source') or '')
    if not source or not Path(source).is_file():
        return 'source-missing'
    try:
        digests = archive_entry_digests(
            source, program,
            skill_import_service.registry_for_ledger_row(program, row, registry),
            layer=skill_import_service._row_layer(row))
    except (skill_import_service.ImportBlocked, OSError):
        return 'source-missing'
    return skill_import_service._entry_status(key, row, digests)
