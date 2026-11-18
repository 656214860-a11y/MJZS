"""命名有界执行器（L1-H8）：io/cpu/network/gpu 四个命名池＋按供应商并发闸门。

- 队列有界（``QUEUE_LIMIT``=256），满时 ``submit`` 抛 ``QuotaError``，不静默丢弃。
- ``network`` 池的真实并发由供应商闸门决定：``submit(..., vendor=...)`` 的任务
  在 worker 内先占住该供应商的槽位再执行；``set_vendor_limit`` 可热调上限
  （I21 自适应并发在此基础上做 AIMD）。
- 取消：``cancel`` 传 ``threading.Event``、``CancelFlag`` 或带 ``is_set()``/
  ``cancelled()`` 的对象；任务出队时已取消则不执行（Future 置 cancelled），
  执行中由任务自身读同一标记。K12 落地 L0 ``CancelToken`` 后本封装可整体替换。
- ``shutdown(wait=5)`` 有序收尾：停止接收、取消未开始任务、worker 按期限退出，
  超时任务记诊断日志，不阻塞退出（线程为 daemon）。
"""
import logging
import os
import queue
import threading
import time
from concurrent.futures import Future

import infra.app_logging as app_logging
from contract.infra_errors import ConfigError, QuotaError

_LOG = logging.getLogger('executors')

QUEUE_LIMIT = 256
SHUTDOWN_WAIT = 5.0
# network 池 worker 数下限；有效并发由供应商闸门收紧，worker 数随闸门上限总和扩容。
_NETWORK_MIN_WORKERS = 2
_GATE_POLL = 0.05

_POOLS = {}
_POOLS_LOCK = threading.Lock()

# 供应商并发闸门：vendor -> _VendorGate
_VENDOR_GATES = {}
_VENDOR_LOCK = threading.Lock()


class CancelFlag:
    """``threading.Event`` 的薄封装：K12 落地 L0 ``CancelToken`` 后只换本类内部。"""

    def __init__(self):
        self._event = threading.Event()

    def cancel(self):
        self._event.set()

    def cancelled(self):
        return self._event.is_set()

    def is_set(self):
        return self._event.is_set()

    @property
    def event(self):
        return self._event


def _cancelled(flag):
    """取消标记判定：Event/CancelFlag 的 is_set()、cancelled()，或裸真值。"""
    if flag is None:
        return False
    for probe in ('is_set', 'cancelled'):
        method = getattr(flag, probe, None)
        if callable(method):
            try:
                return bool(method())
            except Exception:
                return False
    return bool(flag)


class _VendorGate:
    """单个供应商的并发槽位闸门；``limit<=0`` 表示未设闸（不限）。

    用 Condition 而非 Semaphore：上限可被 ``set_limit`` 热调，等待方能被唤醒重估。
    """

    def __init__(self, limit):
        self.limit = max(0, int(limit))
        self.in_flight = 0
        self._cond = threading.Condition(threading.Lock())

    def set_limit(self, limit):
        with self._cond:
            self.limit = max(0, int(limit))
            self._cond.notify_all()

    def acquire(self, cancel=None):
        """占槽；``limit<=0`` 直接放行；cancel 置位时放弃返回 False。"""
        with self._cond:
            if self.limit <= 0:
                self.in_flight += 1
                return True
            while self.in_flight >= self.limit:
                if _cancelled(cancel):
                    return False
                self._cond.wait(timeout=_GATE_POLL)
            self.in_flight += 1
            return True

    def release(self):
        with self._cond:
            self.in_flight = max(0, self.in_flight - 1)
            self._cond.notify()


def set_vendor_limit(vendor, limit):
    """设置供应商并发上限；``limit<=0`` 移除闸门（不限）。返回生效上限。"""
    name = str(vendor or '').strip()
    if not name:
        raise ConfigError('供应商名不能为空')
    try:
        value = int(limit)
    except (TypeError, ValueError):
        raise ConfigError('供应商并发上限必须是整数') from None
    with _VENDOR_LOCK:
        if value <= 0:
            _VENDOR_GATES.pop(name, None)
            effective = 0
        else:
            gate = _VENDOR_GATES.get(name)
            if gate is None:
                gate = _VENDOR_GATES[name] = _VendorGate(value)
            else:
                gate.set_limit(value)
            effective = gate.limit
    _ensure_network_workers()
    return effective


def vendor_status():
    """诊断快照：各供应商闸门的上限与在飞数（I21 AIMD 与门禁测试用）。"""
    with _VENDOR_LOCK:
        return {name: {'limit': gate.limit, 'in_flight': gate.in_flight}
                for name, gate in _VENDOR_GATES.items()}


def _pool_sizes():
    return {'io': 8, 'cpu': max(2, (os.cpu_count() or 4) // 2), 'gpu': 1}


def _vendor_gate(vendor):
    if not vendor:
        return None
    with _VENDOR_LOCK:
        return _VENDOR_GATES.get(str(vendor).strip())


def _ensure_network_workers():
    """network 池 worker 数 = 供应商上限总和（下限 _NETWORK_MIN_WORKERS），只增不减。"""
    with _VENDOR_LOCK:
        want = max(_NETWORK_MIN_WORKERS,
                   sum(gate.limit for gate in _VENDOR_GATES.values()
                       if gate.limit > 0))
    pool = _POOLS.get('network')
    if pool is not None:
        pool.add_workers(want - len(pool._workers))
    else:
        _pool('network', want)


class _Pool:
    def __init__(self, name, workers):
        self.name = name
        self._queue = queue.Queue(maxsize=QUEUE_LIMIT)
        self._workers = []
        self._lock = threading.Lock()
        self._closing = False
        self._deadline = None
        for _ in range(max(1, int(workers))):
            self._spawn_worker()

    def _spawn_worker(self):
        thread = threading.Thread(target=self._work, name='executor-%s' % self.name,
                                  daemon=True)
        thread.start()
        self._workers.append(thread)

    def add_workers(self, count):
        for _ in range(max(0, int(count))):
            self._spawn_worker()

    def submit(self, item):
        with self._lock:
            if self._closing:
                raise QuotaError('执行器已关闭：%s' % self.name)
        try:
            self._queue.put_nowait(item)
        except queue.Full:
            raise QuotaError('执行器队列已满（%d）：%s' % (QUEUE_LIMIT, self.name)) from None

    def _work(self):
        while True:
            if self._deadline is not None and time.monotonic() >= self._deadline:
                break
            try:
                item = self._queue.get(timeout=_GATE_POLL)
            except queue.Empty:
                if self._closing and self._queue.empty():
                    break
                continue
            fn, cancel, _label, vendor, future = item
            try:
                if future.cancelled() or _cancelled(cancel):
                    future.cancel()
                    continue
                if not future.set_running_or_notify_cancel():
                    continue
                gate = _vendor_gate(vendor)
                if gate is not None and not gate.acquire(cancel):
                    future.cancel()
                    continue
                try:
                    future.set_result(fn())
                finally:
                    if gate is not None:
                        gate.release()
            except BaseException as exc:  # noqa: BLE001 —— 结果一律回传 Future
                try:
                    future.set_exception(exc)
                except Exception:
                    _LOG.debug('future 回填异常失败', exc_info=True)
            finally:
                self._queue.task_done()

    def shutdown(self, wait):
        with self._lock:
            self._closing = True
        self._deadline = time.monotonic() + max(0.0, wait)
        # 取消尚未开始的排队任务；worker 取到空队列＋closing 即退出。
        while True:
            try:
                _fn, _c, _l, _v, fut = self._queue.get_nowait()
            except queue.Empty:
                break
            try:
                fut.cancel()
            except Exception:
                app_logging.swallowed('executors.shutdown fut.cancel')
            self._queue.task_done()
        for thread in self._workers:
            remain = max(0.0, self._deadline - time.monotonic())
            thread.join(timeout=remain)
        if any(t.is_alive() for t in self._workers):
            _LOG.warning('执行器 %s 关闭超时：仍有任务在运行（等待 %.1f 秒）',
                         self.name, wait)


def _pool(name, workers=None):
    with _POOLS_LOCK:
        pool = _POOLS.get(name)
        if pool is None:
            if name == 'network':
                count = workers if workers is not None else _NETWORK_MIN_WORKERS
            else:
                count = _pool_sizes().get(name)
            if count is None:
                raise ConfigError('未知执行器池：%r（可用：io/cpu/network/gpu）' % name)
            pool = _POOLS[name] = _Pool(name, count)
        return pool


def submit(pool, fn, *, cancel=None, label='', vendor=None):
    """向命名池提交任务，返回 ``concurrent.futures.Future``。

    - ``pool``：``io``/``cpu``/``network``/``gpu``。
    - ``cancel``：``CancelFlag``/``threading.Event`` 或 ``cancelled()``/``is_set()`` 对象；
      出队时已置位则任务不执行。
    - ``vendor``：供应商桶名；配合 ``set_vendor_limit`` 的并发闸门（network 池建议携带）。
    - 队列满抛 ``QuotaError``；池已关闭同样抛 ``QuotaError``（RuntimeError 兼容）。
    """
    if not callable(fn):
        raise ConfigError('submit 的 fn 必须可调用')
    target = _pool(str(pool or '').strip())
    if target.name == 'network' and vendor:
        _ensure_network_workers()
    future = Future()
    target.submit((fn, cancel, str(label or ''), vendor, future))
    return future


def pool_status():
    """诊断快照：各池 worker 数、排队深度与关闭状态。"""
    with _POOLS_LOCK:
        return {name: {'workers': len(pool._workers),
                       'queued': pool._queue.qsize(),
                       'closing': pool._closing}
                for name, pool in _POOLS.items()}


def shutdown(wait=SHUTDOWN_WAIT):
    """有序关闭全部池：停止接收、取消未开始任务、最多等 ``wait`` 秒收尾。

    超时仍在运行的任务只记诊断日志，不阻塞调用方（线程为 daemon）。
    """
    with _POOLS_LOCK:
        pools = list(_POOLS.values())
    for pool in pools:
        pool.shutdown(wait)


__all__ = ['CancelFlag', 'QUEUE_LIMIT', 'SHUTDOWN_WAIT',
           'pool_status', 'set_vendor_limit', 'shutdown', 'submit',
           'vendor_status']
