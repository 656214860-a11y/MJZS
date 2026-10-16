"""Thread-safe registry of child workflow processes, independent of adapters."""
import threading

_running = {}
_lock = threading.Lock()
_slots = {}
_queued = []
_queue_counter = 0


def _reap_exited_processes():
    """申请容量前回收已退出的自有进程；活进程及未绑定进程的预留不动。"""
    with _lock:
        snapshot = [(project, process) for project, items in _running.items() for process in items]
    for project, process in snapshot:
        try:
            exited = process.poll() is not None
        except (OSError, ValueError):
            continue
        if exited:
            forget_process(project, process)


def reserve_process_slot(project, stage, stage_limit=1, global_limit=8, stage_name=None):
    """按调用方给定的容量预留槽位；本注册表不依赖阶段业务配置。"""
    _reap_exited_processes()
    key = str(stage or '')
    name = stage_name or key
    with _lock:
        total = sum(len(items) for items in _slots.values())
        stage_total = len(_slots.get(key, ()))
        limit = int(stage_limit)
        if total >= int(global_limit):
            raise ValueError(f'当前已有 {total} 个模型请求在执行，达到全局并发上限 {global_limit}；请等待已有请求结束后再试。')
        if stage_total >= limit:
            raise ValueError(f'{name}已有 {stage_total} 个模型请求，达到阶段并发上限 {limit}；请等待已有请求结束后再试。')
        token = object()
        _slots.setdefault(key, set()).add(token)
        return token


def request_process_slot(project, stage, stage_limit=1, global_limit=8, stage_name=None):
    """非阻塞地申请模型槽位；满额时登记队列而不是占住调用线程。"""
    global _queue_counter
    _reap_exited_processes()
    key = str(stage or '')
    name = stage_name or key
    with _lock:
        total = sum(len(items) for items in _slots.values())
        if total < int(global_limit) and len(_slots.get(key, ())) < int(stage_limit):
            token = object()
            _slots.setdefault(key, set()).add(token)
            return {'state': 'granted', 'slot': token, 'position': 0, 'reason': ''}
        _queue_counter += 1
        ticket = {'id': _queue_counter, 'project': str(project), 'stage': key,
                  'stage_limit': int(stage_limit), 'global_limit': int(global_limit),
                  'stage_name': name}
        _queued.append(ticket)
        return {'state': 'queued', 'ticket': ticket, 'position': len(_queued),
                'reason': '模型请求正在排队，等待可用并发槽位'}


def claim_process_slot(ticket):
    """轮询一个排队申请；仅在其成为最早可运行请求时分配槽位。"""
    _reap_exited_processes()
    if not isinstance(ticket, dict):
        return {'state': 'cancelled', 'reason': '排队请求已取消'}
    with _lock:
        try:
            index = _queued.index(ticket)
        except ValueError:
            return {'state': 'cancelled', 'reason': '排队请求已取消'}
        total = sum(len(items) for items in _slots.values())
        eligible = next((item for item in _queued
                         if total < item['global_limit']
                         and len(_slots.get(item['stage'], ())) < item['stage_limit']), None)
        if eligible is ticket:
            _queued.pop(index)
            token = object()
            _slots.setdefault(ticket['stage'], set()).add(token)
            return {'state': 'granted', 'slot': token, 'position': 0, 'reason': ''}
        return {'state': 'queued', 'position': index + 1,
                'reason': '模型请求正在排队，等待可用并发槽位'}




def cancel_slot_request(ticket):
    """撤销单个尚未启动的申请，不影响同项目的其他请求。"""
    with _lock:
        for index, item in enumerate(_queued):
            if item is ticket:
                _queued.pop(index)
                return True
    return False


def cancel_project_slot_requests(project):
    """停止项目时撤销其所有未启动的模型请求。"""
    key = str(project)
    with _lock:
        before = len(_queued)
        _queued[:] = [ticket for ticket in _queued if ticket['project'] != key]
        return before - len(_queued)


def release_process_slot(token):
    """释放已预留的槽位；重复释放安全，便于异常与停止路径共用。"""
    if token is None:
        return
    with _lock:
        for key, items in list(_slots.items()):
            if token in items:
                items.remove(token)
                if not items:
                    _slots.pop(key, None)
                return

def register_process(project, process):
    with _lock:
        _running.setdefault(str(project), []).append(process)

def forget_process(project, process):
    with _lock:
        items = _running.get(str(project))
        if items and process in items:
            items.remove(process)
        if items is not None and not items:
            _running.pop(str(project), None)
    release_process_slot(getattr(process, 'workflow_process_slot', None))

def processes(project):
    with _lock:
        return list(_running.get(str(project), []))
