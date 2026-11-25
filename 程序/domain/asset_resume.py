# -*- coding: utf-8 -*-
"""资产中断的跨重启续跑台账（第 6 轮）。

进程内的退避重试（60 秒 × 次数，到 `desktop.ASSET_RETRY_LIMIT` 停）只活在内存里：助手一
关，`auto_asset_attempt` 与「下次几秒后再试」全没了，下次打开项目又从第 1 次开始——同一批
做不出图的资产被反复重排，用户既看不到「已经试过几次」，也等不到那句「已停下等您处理」。

这一份把「每个编号试过几次、下次从什么时候接着退避」写进项目自己的
`workflows/资产续跑台账.json`，进程重启后原样读回来。三件事：

* `note_round(project, ids)`：一轮跑完还有缺图时记账——只留还在等图的编号，逐个「次数＋1」，
  并写下下次该重试的**挂钟时刻**（`time.time()`；`time.monotonic()` 的起点每趟进程都不一样，
  跨重启不能用它）；到 `limit` 次的那一项标成 stopped，重启后照样是「停下等人工处理」。
* `delay(project)`：离最早那一项该重试还差几秒；没有等待中的项返回 None。
* `clear(project)`：缺图补齐了、或用户亲手关掉这一档，就把台账整份删掉，不留下「历史账」。

台账是辅助：读不出来一律当没记过（`agent.core.read_json` 自己吞掉坏文件），绝不因此把
「打开项目」拦下来。
"""
import time
import sqlite3
from pathlib import Path
from functools import wraps
import logging

from agent.core import read_json
from agent.publication import access
from contract.service_contract import SystemError, success

FILE_NAME = '资产续跑台账.json'
STEP = 60                      # 每多试一次，退避多等这么些秒（与进程内那份 60×次数 一致）


def _ledger_result(function):
    @wraps(function)
    def run(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except OSError:
            logging.getLogger('asset_resume').exception('资产续跑台账更新失败')
            return SystemError('资产续跑台账更新失败，请检查文件权限和磁盘空间。')
    return run


def path(project):
    """台账落在项目自己的 workflows 目录（与「资产批量记录.json」同层）。"""
    return Path(project) / 'workflows' / FILE_NAME


def _number(value):
    """挂钟时刻：读得出来就是 float，其余（缺字段、写坏了）当没记过。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load(project):
    """读台账：文件不在、读不动、格式坏都当空台账，顺手把看不懂的条目滤掉。"""
    data = read_json(path(project), None)
    if not isinstance(data, dict):
        return {}
    clean = {}
    for aid, entry in data.items():
        if not isinstance(entry, dict):
            continue
        try:
            attempts = int(entry.get('attempts') or 0)
        except (TypeError, ValueError):
            attempts = 0
        if attempts <= 0:
            continue
        clean[str(aid)] = {'attempts': attempts,
                           'state': 'stopped' if entry.get('state') == 'stopped' else 'waiting',
                           'last_try': _number(entry.get('last_try')),
                           'next_try': _number(entry.get('next_try'))}
    return clean


def attempts(project, ids=None):
    """这一批编号里「试过几次」的最大值（决定重启后接着第几次退避、要不要停下等人）。"""
    data = load(project)
    picked = data.values() if ids is None else [data[str(aid)] for aid in ids if str(aid) in data]
    return max([entry['attempts'] for entry in picked], default=0)


@_ledger_result
@access()
def note_round(project, ids, limit=None, now=None, *, publish=None):
    """一轮跑完还有缺图：只留还在等图的编号，逐个「次数＋1」并写下下次退避的挂钟时刻。

    出图了的编号不在 `ids` 里，跟着就从台账上摘掉——台账始终只记「眼下还缺、还在退避」的那些。
    到 `limit` 次的那一项标成 stopped、不再排下一次（与 desktop 的 ASSET_RETRY_LIMIT 对齐）。
    """
    if not callable(publish):
        raise RuntimeError('资产续跑台账发布必须由 L3 注入')
    ids = [str(aid) for aid in ids]
    if not ids:
        result = clear(project)
        return success({}) if result.ok else result
    now = time.time() if now is None else float(now)
    counted = load(project)
    data = {}
    for aid in ids:
        tries = int((counted.get(aid) or {}).get('attempts') or 0) + 1
        data[aid] = {'attempts': tries, 'last_try': now, 'next_try': now + STEP * tries,
                     'state': 'waiting'}
        if limit is not None and tries >= limit:
            data[aid]['state'] = 'stopped'
            data[aid]['next_try'] = None
    publish(path(project), data)
    _dual_write(project, data)
    return success(data)


def _dual_write(project, data):
    """I19 试点：把台账镜像进通用作业库；旧台账仍是读取权威，双写失败不阻断本轮。"""
    try:
        from infra.job_store import open_store
        with open_store(project) as store:
            store.sync_mirror('asset_resume', {
                aid: dict(entry, state='retrying' if entry['state'] == 'waiting' else 'stopped')
                for aid, entry in data.items()})
    except (OSError, sqlite3.Error):
        logging.getLogger('asset_resume').exception('作业库双写失败（旧台账不受影响）')


@access()
def consistency_report(project):
    """I19-2 一致性检查：旧台账与作业库的差异报告（missing/field_diffs）。"""
    from infra.job_store import open_store
    ledger = load(project)
    mapped = {aid: {'attempts': entry.get('attempts'),
                    'next_try': entry.get('next_try'),
                    'state': entry.get('state')}
              for aid, entry in ledger.items()}
    with open_store(project) as store:
        return store.reconcile(
            mapped, kind='asset_resume', state_map={'waiting': 'retrying', 'stopped': 'stopped'})


def delay(project, now=None):
    """离最早那一项该重试还差几秒；没有任何等待中的项（都停了、或没记过）返回 None。"""
    now = time.time() if now is None else float(now)
    stamps = [entry['next_try'] for entry in load(project).values()
              if entry['state'] == 'waiting' and entry['next_try'] is not None]
    if not stamps:
        return None
    return max(0.0, min(stamps) - now)


@_ledger_result
@access()
def clear(project):
    """受控清除台账；底层拒绝或删除失败必须返回失败，不再静默丢弃。"""
    from infra.storage_maintenance import clear_generated_workflow_state

    if not clear_generated_workflow_state(project, path(project), FILE_NAME):
        logging.getLogger('asset_resume').error('资产续跑台账清除被拒绝或失败')
        return SystemError('资产续跑台账未清除，请检查文件权限和目录边界后重试。')
    _dual_write(project, {})
    return success()
