# -*- coding: utf-8 -*-
"""事务原语：把「登记路径 → 写盘 → 失败恢复」收成 begin/commit/rollback 三件套（L1 基础设施）。

现状 ``domain/`` 里 7 处各写一遍「暂存→校验→替换→失败恢复」，其中 4 处回滚不完整，
且全部只在 ``except Exception`` 内生效——取消与进程中断不回滚。本模块是唯一实现：

- ``begin(paths)``：登记一组目标路径，把每个已存在文件的原内容备份进磁盘 journal
  （``outputs/unit-of-work-transactions/<uuid>/``，程序私有运行数据、非项目产物），
  manifest 逐条记录 ``existed`` 与备份名；原本不存在的路径记为「原本不存在」。
  返回不透明令牌，此后调用方可自由写这些路径。
- ``commit(token)``：先把 manifest 原子改写为 ``state='committed'``（提交点——
  此后 journal 即使残留，自动恢复也只清目录、绝不回滚目标），再尽力清理
  journal 与锁文件，令牌作废。
- ``rollback(token)``：逆序逐个恢复——有备份的经 ``agent.core.save_file`` 原子写回，
  「原本不存在」的经 ``agent.core.restore_bytes(path, None)`` 删除（仓库既有回滚权威
  原语，与 ``video_prompt_publication`` 等处 writers 同口径；``storage_maintenance.
  recycle_paths`` 需要项目根且对越界路径静默跳过，不适用于任意路径的 L1 原语；
  删除后以 ``lexists`` 复核，删不掉记为恢复失败而不是静默放过）。
  恢复失败**不吞调用方正在处理的原异常**：尽力恢复完所有路径后抛
  ``RollbackFailedError``（原异常经 ``__context__`` 链仍可见），journal 保留供重试
  与自动恢复；每条失败同时记 ``logging``（只记序号与异常类型，不落盘符）。

取消与进程中断（任务书轮 5 硬要求）：

- **取消路径**：``rollback`` 不检查异常类型，``except BaseException``／``finally``
  里调用同样生效；对已 ``commit``／已 ``rollback`` 的令牌是安全空操作，保证取消
  异常传播不会被二次操作顶掉。
- **进程中断路径**：journal 与逐路径备份都在盘上。每个事务另有 ``<uuid>.lock``
  字节锁文件，令牌存活期间持有；进程死亡锁随句柄释放。``begin`` 与公开的
  ``recover_pending()`` 会扫描 journal 根，对「锁可拿到＝属主已死」的 journal 按
  ``state='pending'`` 恢复、按 ``committed``／``rolled_back`` 或 manifest 缺失／
  损坏只清目录；
  本进程活跃事务与锁仍被持有的 journal 一律跳过。令牌被 GC 而未收尾时同样释放
  锁，journal 留给下次恢复——放弃的事务不会成为永久悬挂。

状态机：``active → committed｜rolled_back``。重复 ``commit`` 幂等；``rollback``
对 ``committed``／``rolled_back`` 幂等空操作（已提交没有可恢复状态，且绝不能
回滚已提交内容）；``commit`` 打在 ``rolled_back`` 上抛 ``ValueError``；非
``begin`` 产物的令牌抛 ``TypeError``。同一令牌的并发操作经令牌内 ``RLock`` 串行；
不同令牌互不影响；跨进程由锁文件活性＋扫描协调。

只登记普通文件：符号链接／联接点等重解析点与目录在 ``begin`` 即拒绝。
"""
from __future__ import annotations

import json
import logging
import os
import stat
import threading
import time
import uuid
import weakref
from collections import abc
from pathlib import Path

import infra.app_logging as app_logging
from agent.core import restore_bytes, save_file, save_text
from infra.file_cache import published, read_json, remove_temporary_file, remove_temporary_tree

# journal 根：程序私有运行数据（与 agent/publication 的 transactions 同区性质），
# 测试可 patch 本常量隔离到临时目录。
JOURNAL_ROOT = Path(__file__).resolve().parents[1] / 'outputs' / 'unit-of-work-transactions'

_MANIFEST = 'manifest.json'
_HEX32 = frozenset('0123456789abcdef')
_REPARSE_POINT = 0x400  # FILE_ATTRIBUTE_REPARSE_POINT（Windows）

_LOCK = threading.RLock()          # 保护 _ACTIVE 与恢复扫描
_ACTIVE = set()                    # 本进程持有的 journal 目录（str），扫描时跳过
_logger = logging.getLogger(__name__)


class RollbackFailedError(RuntimeError):
    """``rollback`` 未能恢复全部登记路径。

    ``failures`` 是 ``(路径, 异常)`` 列表；journal 与令牌保持 ``active``，
    调用方可修复现场后重试 ``rollback(token)``，或交给下次 ``begin`` 的自动恢复。
    """

    def __init__(self, message, failures=()):
        super().__init__(message)
        self.failures = list(failures)


class _Token:
    """``begin()`` 返回的不透明令牌：journal 目录、锁文件句柄与状态机。"""

    __slots__ = ('journal', 'lock_path', 'stream', 'key', 'state', '_mutex', '_finalizer', '__weakref__')

    def __init__(self, journal, lock_path, stream):
        self.journal = journal
        self.lock_path = lock_path
        self.stream = stream
        self.key = str(journal)
        self.state = 'active'                    # active → committed｜rolled_back
        self._mutex = threading.RLock()
        with _LOCK:
            _ACTIVE.add(self.key)
        self._finalizer = weakref.finalize(self, _abandon, stream, self.key)


def _abandon(stream, key):
    """令牌被 GC 而未 commit/rollback：释放锁、移出活跃集。

    留下的 ``pending`` journal 由下次 ``begin``／``recover_pending`` 按中断恢复，
    放弃的事务不会成永久悬挂。
    """
    try:
        stream.close()
    except Exception:
        app_logging.swallowed('unit_of_work.abandon')
    with _LOCK:
        _ACTIVE.discard(key)


def _locking():
    """返回 ``msvcrt``；非 Windows 运行环境在 ``begin``／``recover_pending`` 入口即拒绝。

    与 ``agent.publication.access`` 同口径：先按 ``os.name`` 拒绝再裸导入，
    不设 ``ImportError`` 容错——平台边界统一登记在 ``platform_tools`` 一类模块，
    本模块只做硬性前置检查（``test_import_error_boundaries`` 门禁）。
    """
    if os.name != 'nt':
        raise RuntimeError('unit_of_work 事务锁仅支持随附 Windows 运行环境')
    import msvcrt
    return msvcrt


def _lock_path_for(journal_dir):
    return Path(journal_dir).parent / (Path(journal_dir).name + '.lock')


def _acquire_new_lock(path):
    """``begin`` 用：创建（或打开）锁文件并非阻塞加锁 1 字节。

    锁文件先于 journal 目录出现——扫描方只认「目录存在且锁可拿到＝属主已死」，
    因此任何可见的 journal 目录都已被某个存活或刚死的属主持锁过。
    """
    stream = open(path, 'a+b')
    try:
        if os.fstat(stream.fileno()).st_size == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        msvcrt = _locking()
        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
    except Exception:
        stream.close()
        raise
    return stream


def _try_lock_existing(path):
    """对已存在锁文件尝试非阻塞加锁；返回已锁句柄（调用方负责关闭），否则 ``None``。

    绝不创建文件：``r+b`` 打不开就当「无法证明属主已死」，跳过不恢复。
    """
    try:
        if not path.is_file():
            return None
        stream = open(path, 'r+b')
    except OSError:
        return None
    try:
        stream.seek(0)
        msvcrt = _locking()
        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        stream.close()
        return None
    return stream


def _read_manifest(journal_dir):
    """读 journal manifest；缺失／损坏／版本不符一律返回 ``None``（视为无恢复依据）。

    走 ``file_cache.read_json`` 唯一 JSON 读入口（带发布锁与签名缓存；
    ``save_text`` 写盘经 ``replace`` 已自动 ``published`` 失效，口径一致）。
    """
    try:
        data = read_json(Path(journal_dir) / _MANIFEST)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('entries'), list):
        return None
    return data


def _write_manifest(journal_dir, manifest):
    save_text(Path(journal_dir) / _MANIFEST,
              json.dumps(manifest, ensure_ascii=False, indent=1))


def _mark_rolled_back(journal_dir, manifest):
    """恢复完成后把 journal 状态改写为 ``rolled_back``：残留目录此后只被清理、不再回滚。"""
    try:
        marked = dict(manifest)
        marked['state'] = 'rolled_back'
        _write_manifest(journal_dir, marked)
    except Exception:
        app_logging.swallowed('unit_of_work.mark_rolled_back')


def _check_supported(path):
    """只接受「不存在」或「普通文件」；符号链接／联接点等重解析点与目录一律拒绝。"""
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return
    if stat.S_ISLNK(info.st_mode):
        raise ValueError('事务原语不支持符号链接：' + path.name)
    if getattr(info, 'st_file_attributes', 0) & _REPARSE_POINT:
        raise ValueError('事务原语不支持联接点／重解析点：' + path.name)
    if stat.S_ISDIR(info.st_mode):
        raise ValueError('事务原语只登记文件，不登记目录：' + path.name)
    if not stat.S_ISREG(info.st_mode):
        raise ValueError('事务原语只支持普通文件：' + path.name)


def _prepare_paths(paths):
    """规范化、去重、校验登记路径；返回解析后的绝对 ``Path`` 列表（保持首次出现顺序）。"""
    targets = []
    seen = set()
    for raw in paths:
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        path = path.resolve()
        key = os.path.normcase(str(path))
        if key in seen:
            continue
        seen.add(key)
        _check_supported(path)
        targets.append(path)
    return targets


def _check_token(token):
    if not isinstance(token, _Token):
        raise TypeError('unit_of_work 令牌必须来自 begin()')


def _release_files(token):
    """关闭锁句柄、移出活跃集并尽力清理 journal 与锁文件；清理失败只记不抛。

    残留 journal 已带 ``rolled_back`` 状态或已无 manifest，下次扫描只会清目录。
    """
    try:
        token.stream.close()
    except Exception:
        app_logging.swallowed('unit_of_work.release')
    token.stream = None
    with _LOCK:
        _ACTIVE.discard(token.key)
    remove_temporary_tree(token.journal)
    remove_temporary_file(token.lock_path)


def _restore_entry(journal_dir, entry):
    """恢复单个登记路径：有备份→原子写回原内容；原本不存在→删除。"""
    raw = entry.get('path')
    candidate = Path(raw) if isinstance(raw, str) else None
    if candidate is None or not candidate.is_absolute():
        raise ValueError('journal 登记路径无效')
    # 不再 resolve()：begin 时登记的已是解析后绝对路径；此处若跟随符号链接，
    # 事务窗口内被换成链接的路径会把恢复写到链接目标、越出登记范围。
    target = candidate
    if entry.get('existed'):
        backup = entry.get('backup')
        if not isinstance(backup, str):
            raise ValueError('journal 备份名无效')
        source = Path(journal_dir) / backup
        if source.parent != Path(journal_dir) or not source.is_file():
            raise ValueError('journal 备份缺失或越界')
        save_file(target, source)
    else:
        restore_bytes(target, None)
        if os.path.lexists(target):
            # remove_temporary_file 对 OSError 静默返回 False；删不掉必须如实记失败，
            # 否则「原本不存在」的路径会带着事务产物被当成已恢复、journal 还被清掉。
            raise OSError('原本不存在的登记路径删除失败')
    published(target)


def _restore_entries(journal_dir, manifest):
    """按 manifest 逆序恢复全部登记路径；返回 ``(路径, 异常)`` 失败列表并逐条记日志。

    日志只记条目序号与异常类型：路径可能含用户项目内容，按硬约束不落日志。
    """
    failures = []
    entries = manifest.get('entries') or []
    for position in range(len(entries) - 1, -1, -1):
        entry = entries[position]
        try:
            _restore_entry(journal_dir, entry)
        except Exception as exc:
            failures.append((entry.get('path'), exc))
            _logger.error('unit_of_work 恢复失败（第 %d 项）：%s', position, type(exc).__name__)
    return failures


def _recover_journal(journal_dir):
    """处理一个确认属主已死的 journal；返回 ``True``＝目录确已清走可删锁文件。

    ``pending``→尽力恢复（有失败则保留 journal 与锁文件待下次重试）；
    ``committed``／``rolled_back``／manifest 缺失或损坏→只清目录不动目标文件。
    """
    manifest = _read_manifest(journal_dir)
    if manifest is not None and manifest.get('state') == 'pending':
        failures = _restore_entries(journal_dir, manifest)
        if failures:
            return False                        # 保留 journal，下次扫描重试
        _mark_rolled_back(journal_dir, manifest)
    # rolled_back／manifest 缺失或损坏：journal 不是有效恢复依据，只清理目录。
    remove_temporary_tree(journal_dir)
    return not Path(journal_dir).exists()


def _recover_one(entry):
    """扫描单个 journal 根条目：活跃事务与无法证明属主已死的一律跳过。"""
    root = JOURNAL_ROOT
    name = entry.name
    if entry.is_dir() and len(name) == 32 and all(char in _HEX32 for char in name):
        journal = Path(entry)
        with _LOCK:
            if os.path.normcase(str(journal)) in _ACTIVE:
                return                           # 本进程活事务，绝不动
        stream = _try_lock_existing(_lock_path_for(journal))
        if stream is None:
            return                               # 属主活着或锁文件缺失：跳过
        try:
            done = _recover_journal(journal)
        finally:
            stream.close()                       # 关闭即释放字节锁
        if done:
            # 目录确已清走才删锁文件；目录残留则留锁给下次扫描继续清理，
            # 避免留下「无锁目录」被扫描方永远跳过的死角。
            remove_temporary_file(_lock_path_for(journal))
    elif entry.is_file() and name.endswith('.lock'):
        # 孤儿锁文件（journal 目录已不在）：能拿到锁说明属主已死，清掉。
        if (root / name[:-5]).exists():
            return
        stream = _try_lock_existing(Path(entry))
        if stream is None:
            return
        stream.close()                           # 先放锁再删文件（Windows 不能删开着的文件）
        remove_temporary_file(Path(entry))


def recover_pending():
    """清扫 journal 根下属主已消亡的陈旧事务；由 ``begin`` 自动调用，也可显式触发。

    尽力而为：单个 journal 的任何意外只记日志，不影响其余 journal 与新事务。
    """
    _locking()
    root = JOURNAL_ROOT
    try:
        entries = sorted(root.iterdir()) if root.is_dir() else []
    except OSError:
        return
    for entry in entries:
        try:
            _recover_one(entry)
        except Exception:
            app_logging.swallowed('unit_of_work.recover_pending')


def begin(paths: abc.Iterable[Path]) -> object:
    """登记 ``paths`` 的原内容备份并返回事务令牌；语义见模块 docstring。"""
    _locking()
    recover_pending()                        # 先清扫上次中断留下的 journal
    targets = _prepare_paths(paths)
    JOURNAL_ROOT.mkdir(parents=True, exist_ok=True)
    journal = JOURNAL_ROOT / uuid.uuid4().hex
    stream = _acquire_new_lock(_lock_path_for(journal))
    try:
        journal.mkdir()
        entries = []
        for index, target in enumerate(targets):
            entry = {'path': str(target), 'existed': target.is_file()}
            if entry['existed']:
                backup = 'b%d' % index
                save_file(journal / backup, target)
                entry['backup'] = backup
            entries.append(entry)
        _write_manifest(journal, {
            'version': 1, 'state': 'pending', 'pid': os.getpid(),
            'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'entries': entries})
    except BaseException:
        # begin 自身失败：自己建的 journal 与锁必须收走，不给自动恢复留误伤面。
        try:
            stream.close()
        except Exception:
            app_logging.swallowed('unit_of_work.begin.close')
        with _LOCK:
            _ACTIVE.discard(str(journal))
        remove_temporary_tree(journal)
        remove_temporary_file(_lock_path_for(journal))
        raise
    return _Token(journal, _lock_path_for(journal), stream)


def commit(token: object) -> None:
    """提交事务：manifest 改写 ``committed`` 即提交点，随后尽力清理 journal，令牌作废。

    重复 ``commit`` 幂等；``commit`` 打在已 ``rollback`` 的令牌上抛 ``ValueError``；
    非 ``begin`` 产物抛 ``TypeError``。
    """
    _check_token(token)
    with token._mutex:
        if token.state == 'committed':
            return
        if token.state == 'rolled_back':
            raise ValueError('事务已回滚，不能再提交')
        # 提交点：manifest 改写为 committed——此后 journal 即使残留，自动恢复
        # 也只清目录、绝不回滚目标。用原子写而非删文件：写失败抛出时 manifest
        # 仍是 pending，令牌保持 active 可回滚；物理删除统一走 file_cache。
        manifest = _read_manifest(token.journal)
        if manifest is not None:
            committed = dict(manifest)
            committed['state'] = 'committed'
            _write_manifest(token.journal, committed)
        token.state = 'committed'
        _release_files(token)


def rollback(token: object) -> None:
    """回滚事务：逆序逐个恢复 ``begin`` 时的内容，不吞调用方原异常。

    恢复失败抛 ``RollbackFailedError``（原异常经 ``__context__`` 链可见），
    journal 保留可重试；对 ``committed``／``rolled_back`` 令牌是安全空操作；
    非 ``begin`` 产物抛 ``TypeError``。
    """
    _check_token(token)
    with token._mutex:
        if token.state != 'active':
            return                                # committed／rolled_back：幂等空操作
        journal = token.journal
        manifest = _read_manifest(journal)
        if manifest is None or manifest.get('state') != 'pending':
            # journal 已失效（manifest 缺失／被清）：没有可恢复内容，直接收尾。
            token.state = 'rolled_back'
            _release_files(token)
            return
        failures = _restore_entries(journal, manifest)
        if failures:
            raise RollbackFailedError(
                'unit_of_work 回滚 %d 个路径失败，journal 已保留可重试' % len(failures),
                failures=failures)
        _mark_rolled_back(journal, manifest)
        token.state = 'rolled_back'
        _release_files(token)
