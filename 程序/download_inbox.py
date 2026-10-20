# -*- coding: utf-8 -*-
"""桌面 Agent 下载收件箱：任务书写明的目标文件只能在窗口里以「下载」交付时，按文件名收回。

Claude Desktop 等桌面应用读得到任务书，却常常不能直接写入本机路径，只在窗口里给出可下载
文件；用户点下载后文件落在「下载」文件夹，各阶段按目标路径找产物就会落空。这里只做纯计算：

- ``expected_targets()`` 从任务书正文里取出位于项目内、尚未存在的目标文件路径；
- ``match()`` 在下载文件夹里为待收回目标找同名（容许浏览器追加的「 (N)」）、派发后
  才下载的最新文件。

登记表读写与复制落盘由 L3 注入，本模块不读写项目数据。
"""
from __future__ import annotations

import re
from pathlib import Path

TARGET_SUFFIXES = ('md', 'json', 'png', 'jpg', 'jpeg', 'webp', 'mp4', 'mov', 'wav', 'mp3',
                   'srt', 'txt', 'blend', 'edl', 'fcpxml', 'csv')
PENDING_MAX_AGE = 3 * 24 * 3600     # 派发三天后仍没下载就不再等
# 路径必须有明确起点：盘符／根路径，或「01剧本准备」这类两位编号的阶段目录（相对项目根）。
# 目录名可含空格（如 Claude Desktop），因此不按空白切分，而是懒惰匹配到第一个目标扩展名。
_BODY = r'[^\n\r"\'`<>|*?，。；：、！？（）()【】「」《》]*?'
_PATH = re.compile(
    r'(?:[A-Za-z]:[\\/]|(?<![\w\\/])/|(?<![\w\\/.])\d{2}[^\x00-\x7f])' + _BODY
    + r'\.(?:' + '|'.join(TARGET_SUFFIXES) + r')(?![A-Za-z0-9_])', re.I)
_COPY_SUFFIX = re.compile(r'\s*\(\d+\)(?=\.[^.]+$)')


# 任务书也会引用输入素材；这些目录里的文件只读，不作为收回目标。
_INPUT_PARTS = frozenset(('输入', '工作流任务', '回收站'))


def expected_targets(root, text):
    """任务书里提到、位于项目目录内的目标文件（按出现顺序去重；输入与任务目录除外）。

    已存在的目标也登记：重新生成时下载件比现有文件新才会覆盖。"""
    base = Path(root).resolve()
    found = []
    for match in _PATH.finditer(str(text or '')):
        raw = match.group(0).replace('\\', '/')
        path = Path(raw)
        if re.match(r'[A-Za-z]:/', raw) and not path.is_absolute():
            continue                      # 盘符路径只在 Windows 上有意义，其他平台不当作相对路径
        target = path if path.is_absolute() else base / path
        try:
            target = target.resolve()
            target.relative_to(base)
        except (OSError, ValueError):
            continue
        if target in found or _INPUT_PARTS.intersection(target.relative_to(base).parts):
            continue
        found.append(target)
    return tuple(found)


_SEPARATOR_RUN = re.compile(r'[\s_]+')


def _plain_name(name):
    """把空格与下划线归一到同一形式再比较：桌面应用常把任务书里的 ``_`` 下成空格。"""
    return _SEPARATOR_RUN.sub(' ', _COPY_SUFFIX.sub('', name).strip()).casefold()


def match(downloads, pending, now):
    """返回 ``[(下载文件, 目标路径)]``：同名、派发后下载、比现有目标新的最新一份。

    同一文件名对应多个待收回目标时只认最近一次派发，避免把文件放错位置。
    """
    folder = Path(downloads)
    try:
        files = [path for path in folder.iterdir() if path.is_file()] if folder.is_dir() else []
    except OSError:
        files = []
    by_name = {}
    for entry in pending:
        try:
            target, since = Path(entry['target']), float(entry['since'])
        except (KeyError, TypeError, ValueError):
            continue
        if now - since > PENDING_MAX_AGE:
            continue
        key = _plain_name(target.name)
        if key not in by_name or since > by_name[key][1]:
            by_name[key] = (target, since)
    pairs = []
    for key, (target, since) in by_name.items():
        best = None
        for path in files:
            if _plain_name(path.name) != key:
                continue
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if mtime + 2 < since:
                continue
            if best is None or mtime > best[0]:
                best = (mtime, path)
        if best is None:
            continue
        try:
            if target.exists() and target.stat().st_mtime >= best[0]:
                continue
        except OSError:
            continue
        pairs.append((best[1], target))
    return pairs


def remaining(pending, done, now):
    """去掉已收回与过期的登记项。"""
    finished = {str(Path(target)) for target in done}
    kept = []
    for entry in pending:
        try:
            if str(Path(entry['target'])) in finished or now - float(entry['since']) > PENDING_MAX_AGE:
                continue
        except (KeyError, TypeError, ValueError):
            continue
        kept.append(entry)
    return kept
