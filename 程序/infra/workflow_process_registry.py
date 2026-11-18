"""Thread-safe registry of child workflow processes, independent of adapters."""
import os
import threading

_running = {}
_lock = threading.Lock()
_slots = {}
_queued = []
_queue_counter = 0

_JOB = None
_JOB_LOCK = threading.Lock()
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
_PROCESS_SET_QUOTA_TERMINATE = 0x0100 | 0x0001


def _job_object():
    """本进程私有的 Job Object（KILL_ON_JOB_CLOSE）：最后一个句柄关闭即结束全部登记子进程。

    只在 Windows 上懒建；建不出来（权限、旧系统、嵌套 Job 限制）返回 None，
    调用方照常登记进程、不影响启动——Job 只是兜底，不是前置条件。
    """
    global _JOB
    if os.name != 'nt':
        return None
    with _JOB_LOCK:
        if _JOB is not None:
            return _JOB
        try:
            import ctypes
            from ctypes import wintypes

            class _BasicLimit(ctypes.Structure):
                _fields_ = [('PerProcessUserTimeLimit', ctypes.c_int64),
                            ('PerJobUserTimeLimit', ctypes.c_int64),
                            ('LimitFlags', wintypes.DWORD),
                            ('MinimumWorkingSetSize', ctypes.c_size_t),
                            ('MaximumWorkingSetSize', ctypes.c_size_t),
                            ('ActiveProcessLimit', wintypes.DWORD),
                            ('Affinity', ctypes.c_size_t),
                            ('PriorityClass', wintypes.DWORD),
                            ('SchedulingClass', wintypes.DWORD)]

            class _IoCounters(ctypes.Structure):
                _fields_ = [(name, ctypes.c_uint64) for name in (
                    'ReadOperationCount', 'WriteOperationCount', 'OtherOperationCount',
                    'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]

            class _ExtendedLimit(ctypes.Structure):
                _fields_ = [('BasicLimitInformation', _BasicLimit),
                            ('IoInfo', _IoCounters),
                            ('ProcessMemoryLimit', ctypes.c_size_t),
                            ('JobMemoryLimit', ctypes.c_size_t),
                            ('PeakProcessMemoryUsed', ctypes.c_size_t),
                            ('PeakJobMemoryUsed', ctypes.c_size_t)]

            kernel32 = ctypes.windll.kernel32
            kernel32.CreateJobObjectW.restype = wintypes.HANDLE
            kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
            kernel32.SetInformationJobObject.argtypes = [
                wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
            kernel32.SetInformationJobObject.restype = wintypes.BOOL
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL
            job = kernel32.CreateJobObjectW(None, None)
            if not job:
                return None
            info = _ExtendedLimit()
            info.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            ok = kernel32.SetInformationJobObject(
                job, _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                ctypes.byref(info), ctypes.sizeof(info))
            if not ok:
                kernel32.CloseHandle(job)
                return None
            _JOB = job
            return _JOB
        except Exception:
            return None


def _assign_to_job(process):
    """把登记过的子进程挂进本进程的 Job Object；失败只跳过，不影响启动结果。"""
    if os.name != 'nt':
        return
    job = _job_object()
    if not job:
        return
    try:
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.windll.kernel32
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        handle = getattr(process, '_handle', None)
        close_handle = False
        if not isinstance(handle, int) or handle <= 0:
            handle = None
        if not handle:
            pid = getattr(process, 'pid', None)
            if isinstance(pid, int) and pid > 0:
                handle = kernel32.OpenProcess(_PROCESS_SET_QUOTA_TERMINATE, False, pid)
                close_handle = bool(handle)
        if handle:
            try:
                kernel32.AssignProcessToJobObject(job, handle)
            finally:
                if close_handle:
                    kernel32.CloseHandle(handle)
    except Exception:
        import infra.app_logging as app_logging
        app_logging.swallowed('workflow_process_registry._assign_to_job')


def _key(project):
    """同一个项目文件夹无论写成 Path、正斜杠还是大小写不同，都落到同一个登记键。"""
    return os.path.normcase(os.path.abspath(str(project)))


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
        ticket = {'id': _queue_counter, 'project': _key(project), 'stage': key,
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
    key = _key(project)
    with _lock:
        before = len(_queued)
        _queued[:] = [ticket for ticket in _queued if ticket['project'] != key]
        return before - len(_queued)


_requests = {}


def register_request(project, handle):
    """登记项目里一个可取消的直连 API 请求（handle.cancel() 中断它）；同一项目只许一个。"""
    key = _key(project)
    with _lock:
        if key in _requests:
            return False
        _requests[key] = handle
        return True


def forget_request(project, handle):
    key = _key(project)
    with _lock:
        if _requests.get(key) is handle:
            del _requests[key]


def cancel_project_requests(project):
    """停止项目时中断其直连 API 请求；返回被中断的个数。"""
    with _lock:
        handle = _requests.get(_key(project))
    if handle is None:
        return 0
    handle.cancel()
    return 1


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
        _running.setdefault(_key(project), []).append(process)
    _assign_to_job(process)


def all_processes():
    """所有项目登记过的存活句柄快照（跨项目），供「按登记进程号结束」使用。"""
    with _lock:
        return [process for items in _running.values() for process in items]

def forget_process(project, process):
    with _lock:
        items = _running.get(_key(project))
        if items and process in items:
            items.remove(process)
        if items is not None and not items:
            _running.pop(_key(project), None)
    release_process_slot(getattr(process, 'workflow_process_slot', None))

def processes(project):
    with _lock:
        return list(_running.get(_key(project), []))


def run_registered(args, project, prompt, streams, timeout, *, timeout_label, options=None):
    """启动子进程并登记（唯一实现，R2178 J14）：只有登记过的进程才会被「强制停止制作」结束。

    超时或被异常（含 Ctrl+C）打断时先结束进程树再注销，否则它脱离登记表后「强制停止」找不到。

    ``options`` 可选字典，收拢可选关键字：``env``（子进程环境）与 ``on_output``（流式回调
    ``on_output(line, stream)``，提供时把 stdout/stderr 改为 PIPE 逐行读取，每行既写回
    ``streams`` 里对应的文件对象，又回调出去）。未提供时行为与原先一致。
    """
    import subprocess
    from contract.platform_tools import communicate_or_kill, duration_text, launch_text_process, terminate_process_tree
    options = options or {}
    env = options.get('env')
    on_output = options.get('on_output')
    stdout, stderr = streams
    pipe_out = subprocess.PIPE if on_output is not None else stdout
    pipe_err = subprocess.PIPE if on_output is not None else stderr
    process = launch_text_process(args, cwd=project, stdin=subprocess.PIPE, stdout=pipe_out, stderr=pipe_err, env=env)
    register_process(project, process)
    try:
        if on_output is None:
            communicate_or_kill(process, prompt, timeout)
        else:
            def forward(line, stream):
                # 逐行写回调用方给的对应文件对象（若有），再交回调；stream 区分 stdout/stderr。
                target = stdout if stream == 'stdout' else stderr
                if hasattr(target, 'write'):
                    try:
                        target.write(line)
                        target.flush()
                    except (OSError, ValueError):
                        pass
                on_output(line, stream)
            communicate_or_kill(process, prompt, timeout, on_output=forward)
    except subprocess.TimeoutExpired:
        raise ValueError('%s（%s 仍未结束），已强制结束；请查看运行日志后重试' % (timeout_label, duration_text(timeout))) from None
    except BaseException:
        terminate_process_tree(process)
        raise
    finally:
        forget_process(project, process)
    return process.returncode
