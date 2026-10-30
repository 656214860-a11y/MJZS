# -*- coding: utf-8 -*-
"""桌面 Agent 下载收件箱：任务书写明的目标文件只能在窗口里以「下载」交付时，按文件名收回。

Claude Desktop 等桌面应用读得到任务书，却常常不能直接写入本机路径，只在窗口里给出可下载
文件；用户点下载后文件落在「下载」文件夹，各阶段按目标路径找产物就会落空。这里只做纯计算：

- ``expected_targets()`` 从任务书正文里取出位于项目内、尚未存在的目标文件路径；
- ``match_registered()`` 在下载文件夹里为待收回目标找同名（容许浏览器追加的「 (N)」）、派发后
  才下载的最新文件；没有同名件时，四段式文件名只差日期段且下载件日期更新的，另存到
  新日期的文件与「创意_日期」批次，旧日期版本保留。

登记表读写与复制落盘由 L3 注入，本模块不读写项目数据。
"""
from __future__ import annotations

import re
from datetime import datetime
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


_DATED_NAME = re.compile(r'^(.+)[ _](\d{8})(\.[^.]+)$')


def _dated(name):
    """归一后的四段式文件名拆成 ``(去掉日期的名字, 日期)``；末段不是合法日期返回 ``None``。"""
    found = _DATED_NAME.match(name)
    if not found:
        return None
    try:
        datetime.strptime(found.group(2), '%Y%m%d')
    except ValueError:
        return None
    return found.group(1) + found.group(3), found.group(2)


def filename_day(name):
    """文件名末尾的合法日期段（容许副本后缀「 (N)」，空格与下划线都认）；没有返回空串。"""
    found = _dated(_plain_name(name))
    return found[1] if found else ''


def dated_target(target, day):
    """把目标文件名的日期段换成 ``day``；所在批次目录是「创意_旧日期」时一并换成新日期。"""
    target = Path(target)
    found = _DATED_NAME.match(target.name)
    if not found:
        return target
    name = target.name[:found.start(2)] + day + target.name[found.end(2):]
    batch = target.parent.parent
    if batch.name == '创意_' + found.group(2):
        return batch.parent / ('创意_' + day) / target.parent.name / name
    return target.with_name(name)


def _newest(files, since, accept):
    best = None
    for path in files:
        if not accept(path):
            continue
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if mtime + 2 < since:
            continue
        if best is None or mtime > best[0]:
            best = (mtime, path)
    return best


def match_registered(downloads, pending, now):
    """返回 ``[(下载文件, 写入路径, (登记目标, …))]``：同名、派发后下载、比现有目标新的最新一份。

    同一份下载可能同时对上几次派发的登记（如换了模型名、同名件与只差日期的旧目标），
    只写到最近一次派发的那个位置；其余登记随之销账，不再另存副本。"""
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
    claims = {}
    for key, (target, since) in by_name.items():
        written = target
        best = _newest(files, since, lambda path: _plain_name(path.name) == key)
        dated = _dated(key) if best is None else None
        if dated is not None:
            # 桌面应用常按当天日期给文件命名，不照任务书里沿用的旧日期：只差日期且更新的另存新批次。
            stem, day = dated
            def newer(path):
                other = _dated(_plain_name(path.name))
                return other is not None and other[0] == stem and other[1] > day
            best = _newest(files, since, newer)
            if best is not None:
                written = dated_target(target, _dated(_plain_name(best[1].name))[1])
        if best is not None:
            claims.setdefault(best[1], []).append((since, dated is None, best[0], written, target))
    found = []
    for source, rows in claims.items():
        rows.sort(key=lambda row: row[:2], reverse=True)   # 最近一次派发优先，同一次派发同名件优先
        _since, _exact, mtime, written, target = rows[0]
        try:
            if written.exists() and written.stat().st_mtime >= mtime:
                continue
        except OSError:
            continue
        found.append((source, written, tuple(row[4] for row in rows)))
    return found


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
