# -*- coding: utf-8 -*-
"""L1 资源感知（L1 任务书 I15／L1-Q12；依赖准入实测见当轮结果文件）。

- ``snapshot()``：内存、磁盘空间、磁盘读写计数、网络计数、可选显存。
  ``psutil`` 与 ``nvidia-ml-py`` 均**惰性导入**——本模块导入零成本，不在
  启动关键路径（I15-4）；任一采集失败该字段返回 ``'unavailable'``，不抛异常。
- ``ensure_free(path, nbytes)``：写前磁盘空间检查原语；空间不足抛
  ``contract.infra_errors.StorageError``（``E-IO-WRITE``），``detail`` 带
  ``required_bytes``／``available_bytes``。地基 C2 磁盘闸门由地基车道接线。
- 外部限额学习：``note_rate_limited(host, retry_after)`` 从 429＋
  ``Retry-After`` 推导每分钟上限（无 Retry-After 的裸 429 按当前值减半，
  下限 1）；``effective_rpm(host, configured)`` 与配置 rpm 取小。
  ``api_endpoints`` 的消费接线属后续轮，本轮只交付原语与测试。
"""
from __future__ import annotations

import shutil
import threading
import time
from datetime import datetime
from pathlib import Path

from contract.infra_errors import StorageError

__all__ = [
    'snapshot', 'ensure_free',
    'note_rate_limited', 'effective_rpm', 'learned_rpm',
]

PROGRAM = Path(__file__).resolve().parents[1]
_UNAVAILABLE = 'unavailable'
_LEARNED_TTL = 600.0
_DEFAULT_RPM = 60.0
_RATE_LOCK = threading.Lock()
_LEARNED = {}
_psutil_cache = []


def _psutil():
    """惰性导入 psutil；缺失或导入失败返回 None（字段降级 'unavailable'）。"""
    if _psutil_cache:
        return _psutil_cache[0]
    module = None
    try:
        import psutil as module  # noqa: F811
    except Exception:
        module = None
    _psutil_cache.append(module)
    return module


def _vram():
    """可选显存：nvidia-ml-py 惰性导入；无 NVIDIA 驱动／任何失败 → 'unavailable'。"""
    try:
        import pynvml
        pynvml.nvmlInit()
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        finally:
            # 关闭失败向上传播，由外层 except 统一降级 'unavailable'（不留痕吞异常）。
            pynvml.nvmlShutdown()
        mib = 1024 * 1024
        return {'total_mb': info.total // mib, 'used_mb': info.used // mib,
                'free_mb': info.free // mib}
    except Exception:
        return _UNAVAILABLE


def _memory(psutil):
    try:
        mem = psutil.virtual_memory()
        return {'total': mem.total, 'available': mem.available,
                'used': mem.used, 'percent': mem.percent}
    except Exception:
        return _UNAVAILABLE


def _disk_io(psutil):
    try:
        io = psutil.disk_io_counters()
        if io is None:
            return _UNAVAILABLE
        return {'read_count': io.read_count, 'write_count': io.write_count,
                'read_bytes': io.read_bytes, 'write_bytes': io.write_bytes}
    except Exception:
        return _UNAVAILABLE


def _network(psutil):
    try:
        net = psutil.net_io_counters()
        if net is None:
            return _UNAVAILABLE
        return {'bytes_sent': net.bytes_sent, 'bytes_recv': net.bytes_recv,
                'packets_sent': net.packets_sent, 'packets_recv': net.packets_recv}
    except Exception:
        return _UNAVAILABLE


def _probe_for(path):
    """取 path 所在卷的既有祖先用于 disk_usage；目标尚不存在时向上找。"""
    target = Path(path) if path is not None else PROGRAM
    try:
        target = target.resolve()
    except OSError:
        pass
    probe = target
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    return probe


def snapshot(path=None):
    """资源快照：内存、磁盘空间、磁盘读写、网络计数、可选显存。

    ``path`` 指定要量磁盘空间的目录（默认程序目录）；各字段采集失败返回
    ``'unavailable'``，调用方自行决定降级展示。
    """
    psutil = _psutil()
    probe = _probe_for(path)
    try:
        usage = shutil.disk_usage(probe)
        disk = {'path': str(probe), 'total': usage.total,
                'used': usage.used, 'free': usage.free}
    except OSError:
        disk = _UNAVAILABLE
    return {'collected_at': datetime.now().isoformat(timespec='seconds'),
            'memory': _memory(psutil) if psutil is not None else _UNAVAILABLE,
            'disk': disk,
            'disk_io': _disk_io(psutil) if psutil is not None else _UNAVAILABLE,
            'network': _network(psutil) if psutil is not None else _UNAVAILABLE,
            'vram': _vram()}


def ensure_free(path, nbytes):
    """写前磁盘空间检查：``path`` 所在卷可用空间须 ≥ ``nbytes``。

    返回 ``shutil.disk_usage`` 结果；不足抛 ``StorageError``（E-IO-WRITE），
    ``detail`` 含 ``required_bytes``／``available_bytes``／``probe``。
    """
    probe = _probe_for(path)
    usage = shutil.disk_usage(probe)
    needed = int(nbytes)
    if usage.free < needed:
        raise StorageError(
            '磁盘空间不足：需要 %d 字节，可用 %d 字节' % (needed, usage.free),
            code='E-IO-WRITE',
            detail={'required_bytes': needed, 'available_bytes': usage.free,
                    'probe': str(probe)})
    return usage


def _learned_entry(host, now):
    entry = _LEARNED.get(host)
    if entry is None:
        return None
    if now - entry['at'] > _LEARNED_TTL:
        _LEARNED.pop(host, None)
        return None
    return entry


def learned_rpm(host, *, now=None):
    """当前学习到的每分钟上限；无记录或已过期返回 None。"""
    host = str(host or '').strip().lower()
    if not host:
        return None
    with _RATE_LOCK:
        entry = _learned_entry(host, time.monotonic() if now is None else now)
        return entry['rpm'] if entry is not None else None


def note_rate_limited(host, retry_after=None, *, now=None):
    """记录一次 429：``retry_after``（秒）推导 rpm＝max(1, 60/秒)；
    无 Retry-After 的裸 429 把当前学习值减半（起点 60，下限 1）。

    同一主机在 TTL 内取更保守（更小）的值；不同主机互不影响。
    """
    host = str(host or '').strip().lower()
    if not host:
        return
    now = time.monotonic() if now is None else now
    with _RATE_LOCK:
        current = _learned_entry(host, now)
        current_rpm = current['rpm'] if current is not None else None
        try:
            seconds = float(retry_after)
        except (TypeError, ValueError):
            seconds = 0.0
        if seconds > 0:
            derived = max(1.0, 60.0 / seconds)
        else:
            derived = max(1.0, (current_rpm or _DEFAULT_RPM) / 2.0)
        rpm = derived if current_rpm is None else min(current_rpm, derived)
        _LEARNED[host] = {'rpm': rpm, 'at': now}


def effective_rpm(host, configured_rpm=None, *, now=None):
    """生效每分钟上限＝min(配置 rpm，学习 rpm)；两侧都无线率信息返回 None。"""
    host = str(host or '').strip().lower()
    if not host:
        return None
    try:
        configured = float(configured_rpm) if configured_rpm else None
    except (TypeError, ValueError):
        configured = None
    learned = learned_rpm(host, now=now)
    candidates = [value for value in (configured, learned)
                  if value is not None and value > 0]
    return min(candidates) if candidates else None
