# -*- coding: utf-8 -*-
"""L1-H3 结构化指标：``counter``／``observe``／``query``，JSON 行原始流水 ＋ sqlite3 日汇总。

- **维度白名单**（任务书 L1-H3）：``kind``、``stage``、``provider``（主机名）、
  ``model``、``project``、``outcome``、``error_code``。``project`` 一律存项目根
  路径的 sha256 前 16 位、不存路径本体；其余维度值只收 ``[A-Za-z0-9_.-]`` 安全
  形态，路径样值（含分隔符／盘符／空白）哈希处理，白名单外维度名整条丢弃并计数。
- **落盘**：原始事件按天追加 ``data/metrics/raw-YYYYMMDD.jsonl``；日汇总写
  ``data/metrics/summary.sqlite``（WAL，``daily(day,name,dims,count,total,vmin,vmax)``）。
- **热路径开销**（I14-4／A6）：``counter``/``observe`` 只做一次加锁 ``deque.append``
  与节流检查；缓冲默认 60 秒或 512 条由专用守护线程批量落盘，退出时
  ``atexit`` 同步补刷。实测开销记录在 R3623 结果文件；若超 1% 退路为纯内存聚合。
- **零项目内依赖**：本模块不 import 任何 ``infra``/``agent``/``contract`` 成员——
  ``workflow_process_registry``→``metrics``→``executors``→``app_logging``→
  ``agent.core``→``workflow_process_registry`` 会形成新的静态导入环
  （``test_no_circular_import`` 棘轮只降不升）；落盘调度用模块自带守护线程，
  内部异常只进 ``faults`` 计数、不进 ``app.log``。
- **保留期**：原始 JSON 行 14 天、日汇总 180 天；清理在后台落盘时顺带执行，
  不在启动路径上（规则 33）。
- **查询**：``query`` 读原始行算精确 count/p50/p95，并合并内存缓冲；原始行已过
  保留期的日期回落 sqlite 日汇总（只有次数与极值，无分位）。
- ``export_snapshot`` 供 ``diagnostic_capture.export`` 打包；维度已经白名单与
  哈希处理，不含路径与密钥。
"""
from __future__ import annotations

import atexit
import hashlib
import json
import re
import sqlite3
import threading
import time
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path

__all__ = ['counter', 'observe', 'query', 'flush', 'export_snapshot', 'dropped_counts']

PROGRAM = Path(__file__).resolve().parents[1]
DIR = PROGRAM / 'data' / 'metrics'

_DIM_WHITELIST = frozenset({'kind', 'stage', 'provider', 'model', 'project', 'outcome', 'error_code'})
_SAFE_VALUE = re.compile(r'[A-Za-z0-9_.\-]{1,96}')
_NAME = re.compile(r'[a-z0-9][a-z0-9_.\-]{0,63}')
_HASH_LEN = 16
_RAW_KEEP_DAYS = 14
_SUMMARY_KEEP_DAYS = 180
_FLUSH_SECONDS = 60.0
_FLUSH_BATCH = 512
_BUF_MAX = 20000

_buf = deque()
_buf_lock = threading.Lock()
_last_flush = [0.0]
_flush_pending = [False]
_last_cleanup_day = ['']
_dropped = {'name': 0, 'dim': 0, 'overflow': 0}
_faults = {}
_flush_thread = None
_flush_cv = threading.Condition()


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()[:_HASH_LEN]


def _clean_dims(dims) -> dict:
    out = {}
    for key, value in (dims or {}).items():
        name = str(key)
        if name not in _DIM_WHITELIST:
            with _buf_lock:
                _dropped['dim'] += 1
            continue
        text = str(value)
        if not text:
            continue
        if name == 'project':
            out[name] = _hash(text)
        elif _SAFE_VALUE.fullmatch(text):
            out[name] = text
        else:
            out[name] = _hash(text)
    return out


def _note_drop(kind: str) -> None:
    with _buf_lock:
        _dropped[kind] = _dropped.get(kind, 0) + 1


def dropped_counts() -> dict:
    """被丢弃的维度名／指标名／溢出事件计数（验收与观测用）。"""
    with _buf_lock:
        return dict(_dropped)


def _note_fault(site: str) -> None:
    """内部故障计数：指标模块自身任何异常都只计数，绝不影响调用方。"""
    with _buf_lock:
        _faults[site] = _faults.get(site, 0) + 1


def _record(kind: str, name, value, dims) -> None:
    """唯一入口：校验 → 入内存缓冲 → 节流触发后台落盘。任何异常都吞掉。"""
    try:
        metric = str(name)
        if not _NAME.fullmatch(metric):
            _note_drop('name')
            return
        event = {'t': time.time(), 'n': metric, 'k': kind, 'd': _clean_dims(dims)}
        if kind == 'o':
            try:
                event['v'] = float(value)
            except (TypeError, ValueError):
                _note_drop('value')
                return
        with _buf_lock:
            if len(_buf) >= _BUF_MAX:
                _dropped['overflow'] += 1
                return
            _buf.append(event)
        _maybe_flush()
    except Exception:
        _note_fault('emit')


def counter(name, **dims) -> None:
    """计数一次指标事件；``dims`` 只收 L1-H3 白名单维度。"""
    _record('c', name, None, dims)


def observe(name, value, **dims) -> None:
    """记录一次数值观测（耗时毫秒、字节数等）；``dims`` 同 ``counter``。"""
    _record('o', name, value, dims)


def _maybe_flush(now: float | None = None) -> None:
    now = time.monotonic() if now is None else now
    with _buf_lock:
        due = (now - _last_flush[0] >= _FLUSH_SECONDS) or len(_buf) >= _FLUSH_BATCH
        if due and not _flush_pending[0]:
            _flush_pending[0] = True
            _last_flush[0] = now
        else:
            due = False
    if not due:
        return
    try:
        _ensure_flush_thread()
        with _flush_cv:
            _flush_cv.notify()
    except Exception:
        with _buf_lock:
            _flush_pending[0] = False
        _note_fault('wake')


def _flush_loop() -> None:
    """守护落盘线程：每 ``_FLUSH_SECONDS`` 唤醒一次，或被 ``_maybe_flush`` 提前唤醒。"""
    while True:
        with _flush_cv:
            _flush_cv.wait(timeout=_FLUSH_SECONDS)
        try:
            _flush_buffer()
        except Exception:
            _note_fault('loop')


def _ensure_flush_thread() -> None:
    global _flush_thread
    if _flush_thread is not None and _flush_thread.is_alive():
        return
    with _flush_cv:
        if _flush_thread is None or not _flush_thread.is_alive():
            _flush_thread = threading.Thread(target=_flush_loop,
                                             name='metrics-flush', daemon=True)
            _flush_thread.start()


def _flush_buffer() -> None:
    """把缓冲批量落盘（raw JSONL ＋ sqlite 日汇总）并顺带清理过期数据。

    由守护线程、``flush()`` 或 ``atexit`` 调用；自身异常吞掉不影响业务。
    """
    try:
        with _buf_lock:
            batch = list(_buf)
            _buf.clear()
        if batch:
            _append_raw(batch)
            _upsert_daily(batch)
        _cleanup_expired()
    except Exception:
        _note_fault('flush')
    finally:
        with _buf_lock:
            _flush_pending[0] = False


def flush() -> None:
    """同步落盘（导出、测试用）；不经过执行器。"""
    _flush_buffer()


def _day_stamp(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime('%Y%m%d')


def _day_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime('%Y-%m-%d')


def _append_raw(batch) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    by_day = {}
    for event in batch:
        by_day.setdefault(_day_stamp(event['t']), []).append(event)
    for day, events in by_day.items():
        path = DIR / ('raw-%s.jsonl' % day)
        with path.open('a', encoding='utf-8') as handle:
            for event in events:
                handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + '\n')


def _connect_db():
    DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DIR / 'summary.sqlite'), timeout=5)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('''CREATE TABLE IF NOT EXISTS daily(
        day TEXT NOT NULL, name TEXT NOT NULL, dims TEXT NOT NULL,
        count INTEGER NOT NULL, total REAL NOT NULL,
        vmin REAL, vmax REAL,
        PRIMARY KEY(day, name, dims))''')
    return db


def _upsert_daily(batch) -> None:
    agg = {}
    for event in batch:
        key = (_day_iso(event['t']), event['n'],
               json.dumps(event.get('d') or {}, sort_keys=True, ensure_ascii=False))
        slot = agg.get(key)
        if slot is None:
            slot = agg[key] = [0, 0.0, None, None]
        slot[0] += 1
        value = event.get('v')
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            number = float(value)
            slot[1] += number
            slot[2] = number if slot[2] is None else min(slot[2], number)
            slot[3] = number if slot[3] is None else max(slot[3], number)
    if not agg:
        return
    db = _connect_db()
    try:
        for (day, name, dims), (count, total, vmin, vmax) in agg.items():
            db.execute('''INSERT INTO daily(day,name,dims,count,total,vmin,vmax)
                VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(day,name,dims) DO UPDATE SET
                count=count+excluded.count, total=total+excluded.total,
                vmin=MIN(COALESCE(vmin,excluded.vmin),COALESCE(excluded.vmin,vmin)),
                vmax=MAX(COALESCE(vmax,excluded.vmax),COALESCE(excluded.vmax,vmax))''',
                (day, name, dims, count, total, vmin, vmax))
        db.commit()
    finally:
        db.close()


def _cleanup_expired() -> None:
    """过期原始 JSONL（>14 天）与日汇总行（>180 天）清理；每日至多一次。"""
    today = datetime.now().strftime('%Y%m%d')
    if _last_cleanup_day[0] == today:
        return
    _last_cleanup_day[0] = today
    try:
        cutoff = (datetime.now() - timedelta(days=_RAW_KEEP_DAYS)).strftime('%Y%m%d')
        for path in DIR.glob('raw-*.jsonl'):
            stamp = path.name[len('raw-'):-len('.jsonl')]
            if stamp.isdigit() and stamp < cutoff:
                try:
                    path.unlink()
                except OSError:
                    _note_fault('cleanup-unlink')
        day_cut = (datetime.now() - timedelta(days=_SUMMARY_KEEP_DAYS)).strftime('%Y-%m-%d')
        if (DIR / 'summary.sqlite').is_file():
            db = sqlite3.connect(str(DIR / 'summary.sqlite'), timeout=5)
            try:
                db.execute('DELETE FROM daily WHERE day < ?', (day_cut,))
                db.commit()
            finally:
                db.close()
    except Exception:
        _note_fault('cleanup')


def _iter_raw_events(name: str, since_ts: float | None):
    if not DIR.is_dir():
        return
    for path in sorted(DIR.glob('raw-*.jsonl')):
        stamp = path.name[len('raw-'):-len('.jsonl')]
        if not stamp.isdigit():
            continue
        # 文件名日期整体早于 since 当天时整份跳过（文件内事件仍按 t 过滤）
        if since_ts is not None:
            file_day = datetime.strptime(stamp, '%Y%m%d')
            if file_day.date() < datetime.fromtimestamp(since_ts).date():
                continue
        try:
            with path.open('r', encoding='utf-8') as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    if event.get('n') != name:
                        continue
                    if since_ts is not None and float(event.get('t') or 0) < since_ts:
                        continue
                    yield event
        except OSError:
            _note_fault('query-read')


def _raw_days_present() -> set:
    days = set()
    if DIR.is_dir():
        for path in DIR.glob('raw-*.jsonl'):
            stamp = path.name[len('raw-'):-len('.jsonl')]
            if stamp.isdigit():
                days.add(stamp)
    return days


def _merge_summary_rows(name: str, group_by, since_ts, groups) -> None:
    """原始行已过期的日期回落 sqlite 日汇总（只补次数，无分位）。"""
    db_path = DIR / 'summary.sqlite'
    if not db_path.is_file():
        return
    since_day = _day_iso(since_ts) if since_ts is not None else None
    try:
        db = sqlite3.connect(str(db_path), timeout=5)
        try:
            rows = db.execute(
                'SELECT day,dims,count FROM daily WHERE name=?', (name,)).fetchall()
        finally:
            db.close()
    except (OSError, sqlite3.Error):
        return
    present = _raw_days_present()
    for day, dims_json, count in rows:
        if day.replace('-', '') in present:
            continue  # 该日原始行仍在，已由 raw 计入
        if since_day and day < since_day:
            continue
        try:
            dims = json.loads(dims_json)
        except ValueError:
            continue
        key = tuple(str(dims.get(g, '')) for g in group_by)
        slot = groups.get(key)
        if slot is None:
            slot = groups[key] = {'count': 0, 'values': []}
        slot['count'] += int(count or 0)


def _since_ts(since) -> float | None:
    if since is None:
        return None
    if isinstance(since, (int, float)):
        return float(since)
    text = str(since).strip()
    try:
        return datetime.strptime(text[:10], '%Y-%m-%d').timestamp()
    except ValueError:
        return None


def _percentile(sorted_values, q: float):
    if not sorted_values:
        return None
    pos = (q / 100.0) * (len(sorted_values) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = pos - lo
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * frac


def query(name, group_by=(), since=None):
    """按 ``group_by`` 维度聚合 ``name``：返回
    ``[{'group': {dim: value}, 'count': n, 'observed': m, 'total': Σ,
    'min':…, 'max':…, 'p50':…, 'p95':…}]``，按 count 降序。

    ``count`` 含 counter 与 observe 事件数；分位与极值只对 observe 的 ``v`` 计算。
    ``since`` 接受 ``'YYYY-MM-DD'``、epoch 秒或 None。原始行过期的日期回落
    sqlite 日汇总（仅次数）。
    """
    group_by = tuple(group_by or ())
    since_ts = _since_ts(since)
    groups = {}
    for event in _iter_raw_events(str(name), since_ts):
        dims = event.get('d') or {}
        key = tuple(str(dims.get(g, '')) for g in group_by)
        slot = groups.get(key)
        if slot is None:
            slot = groups[key] = {'count': 0, 'values': []}
        slot['count'] += 1
        value = event.get('v')
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            slot['values'].append(float(value))
    with _buf_lock:
        pending = list(_buf)
    for event in pending:
        if event.get('n') != str(name):
            continue
        if since_ts is not None and float(event.get('t') or 0) < since_ts:
            continue
        dims = event.get('d') or {}
        key = tuple(str(dims.get(g, '')) for g in group_by)
        slot = groups.get(key)
        if slot is None:
            slot = groups[key] = {'count': 0, 'values': []}
        slot['count'] += 1
        value = event.get('v')
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            slot['values'].append(float(value))
    _merge_summary_rows(str(name), group_by, since_ts, groups)
    out = []
    for key, slot in groups.items():
        values = sorted(slot['values'])
        row = {'group': {dim: key[i] for i, dim in enumerate(group_by)},
               'count': slot['count'], 'observed': len(values)}
        if values:
            row.update(total=round(sum(values), 3), min=round(values[0], 3),
                       max=round(values[-1], 3),
                       p50=round(_percentile(values, 50), 3),
                       p95=round(_percentile(values, 95), 3))
        else:
            row.update(total=0.0, min=None, max=None, p50=None, p95=None)
        out.append(row)
    out.sort(key=lambda row: (-row['count'], json.dumps(row['group'], sort_keys=True)))
    return out


def export_snapshot() -> dict:
    """诊断导出用的指标快照：先同步落盘缓冲，再汇总 sqlite 日表。

    只含白名单维度名与已哈希值，不含路径与密钥；供
    ``diagnostic_capture.export`` 写入 ``logs/metrics_summary.json``。
    """
    try:
        _flush_buffer()
    except Exception:
        _note_fault('snapshot-flush')
    totals = {}
    partial = False
    try:
        db = sqlite3.connect(str(DIR / 'summary.sqlite'), timeout=5)
        try:
            for name, count in db.execute('SELECT name, SUM(count) FROM daily GROUP BY name'):
                totals[str(name)] = int(count or 0)
        finally:
            db.close()
    except (OSError, sqlite3.Error):
        partial = True
    with _buf_lock:
        buffered = len(_buf)
    with _buf_lock:
        faults = dict(_faults)
    return {'generated_at': datetime.now().isoformat(timespec='seconds'),
            'totals': totals, 'buffered_events': buffered, 'partial': partial,
            'faults': faults,
            'retention': {'raw_days': _RAW_KEEP_DAYS, 'summary_days': _SUMMARY_KEEP_DAYS},
            'dimensions': sorted(_DIM_WHITELIST)}


atexit.register(_flush_buffer)
