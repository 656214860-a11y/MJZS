"""Thread-safe registry of child workflow processes, independent of adapters."""
import logging
import os
import threading

_LOG = logging.getLogger('workflow_process_registry')

_running = {}
_supervised = {}
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


def _is_direct_child(pid):
    """``pid`` 是否为本进程直接子进程（Toolhelp32 快照核对父进程号）。

    Job Object 是「关闭即结束」的杀伤面：只允许本进程真实派生的子进程入列，
    自身、父进程或任意 pid 绝不可挂入，否则宿主退出时会误杀无关进程。
    """
    if os.name != 'nt' or not isinstance(pid, int) or pid <= 0:
        return False
    try:
        import ctypes
        from ctypes import wintypes

        class _ProcessEntry(ctypes.Structure):
            _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD),
                        ('th32ProcessID', wintypes.DWORD),
                        ('th32DefaultHeapID', ctypes.c_size_t),
                        ('th32ModuleID', wintypes.DWORD),
                        ('cntThreads', wintypes.DWORD),
                        ('th32ParentProcessID', wintypes.DWORD),
                        ('pcPriClassBase', ctypes.c_long),
                        ('dwFlags', wintypes.DWORD),
                        ('szExeFile', wintypes.WCHAR * 260)]

        kernel32 = ctypes.windll.kernel32
        kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ProcessEntry)]
        kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ProcessEntry)]
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        snap = kernel32.CreateToolhelp32Snapshot(2, 0)  # TH32CS_SNAPPROCESS
        if not snap or snap == ctypes.c_void_p(-1).value:
            return False
        try:
            entry = _ProcessEntry()
            entry.dwSize = ctypes.sizeof(entry)
            ok = kernel32.Process32FirstW(snap, ctypes.byref(entry))
            me = os.getpid()
            while ok:
                if entry.th32ProcessID == pid:
                    return entry.th32ParentProcessID == me
                ok = kernel32.Process32NextW(snap, ctypes.byref(entry))
            return False
        finally:
            kernel32.CloseHandle(snap)
    except Exception:
        return False


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
        kernel32.GetProcessId.argtypes = [wintypes.HANDLE]
        kernel32.GetProcessId.restype = wintypes.DWORD
        kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        handle = getattr(process, '_handle', None)
        close_handle = False
        pid = getattr(process, 'pid', None)
        if not isinstance(handle, int) or handle <= 0:
            handle = None
        if not handle:
            if isinstance(pid, int) and pid > 0:
                handle = kernel32.OpenProcess(_PROCESS_SET_QUOTA_TERMINATE, False, pid)
                close_handle = bool(handle)
        if handle:
            # 只允许本进程直接子进程入列：_handle 伪造或 pid 指向自身/他人时跳过。
            if _is_direct_child(kernel32.GetProcessId(handle)):
                try:
                    kernel32.AssignProcessToJobObject(job, handle)
                finally:
                    if close_handle:
                        kernel32.CloseHandle(handle)
            elif close_handle:
                kernel32.CloseHandle(handle)
    except Exception:
        _LOG.debug('Job Object 分配失败，进程仅登记不挂 Job', exc_info=True)


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

def register_process(project, process, *, job=True):
    """登记子进程；``job=False`` 时只登记不挂 Job Object（``detached`` 种类专用）。"""
    with _lock:
        _running.setdefault(_key(project), []).append(process)
    if job:
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
        _supervised.pop(id(process), None)
    release_process_slot(getattr(process, 'workflow_process_slot', None))


def register_supervised(process, *, kind, stage, project, in_job):
    """登记监督器元数据（kind/stage/project/job 归属），供按项目或阶段取消与计量。"""
    with _lock:
        _supervised[id(process)] = {'kind': kind, 'stage': stage,
                                    'project': str(project), 'in_job': bool(in_job)}


def supervised_info(process):
    """返回登记的监督器元数据；未登记返回空 dict。"""
    with _lock:
        info = _supervised.get(id(process))
        return dict(info) if info else {}

def cancel_supervised(project, *, stage=None, kind=None):
    """按项目结束登记过的受监督进程；给 ``stage``/``kind`` 时再收窄。

    只动 ``spawn`` 登记的进程（``_supervised`` 有元数据）；返回结束数。
    """
    from contract.platform_tools import terminate_process_tree
    key = _key(project)
    with _lock:
        items = [process for process in _running.get(key, ())
                 if id(process) in _supervised
                 and (stage is None or _supervised[id(process)].get('stage') == stage)
                 and (kind is None or _supervised[id(process)].get('kind') == kind)]
    killed = 0
    for process in items:
        try:
            terminate_process_tree(process)
            process.wait(timeout=3)
        except Exception:
            try:
                process.kill()
            except Exception:
                _LOG.debug('cancel_supervised 兜底 kill 失败', exc_info=True)
        forget_process(project, process)
        killed += 1
    return killed


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


# ── I8 进程监督器：L1-H9 种类登记与 spawn ──────────────────────────────
# 每个种类登记默认超时（沿用各调用方现值）与 Job Object 归属；
# ``detached`` 是唯一不进 Job 的种类——需要在应用退出后继续运行的进程
# （用户请求打开的外部应用、自重启 helper）登记此类，不被「关闭即结束」误杀。

PROCESS_KINDS = {
    'engine_cli':  {'timeout': 7200, 'job': True},
    'comfy':       {'timeout': 90,   'job': True},
    'ffmpeg':      {'timeout': 120,  'job': True},
    'asr':         {'timeout': 15,   'job': True},
    'blender':     {'timeout': 1800, 'job': True},
    'optimizer':   {'timeout': 125,  'job': True},
    'test_runner': {'timeout': 300,  'job': True},
    'detached':    {'timeout': None, 'job': False},
}

_STDERR_TAIL_LINES = 200


class SupervisedProcess:
    """``spawn`` 返回的受监督进程句柄：登记、Job 归属、超时与错误分类集中于此。"""

    def __init__(self, kind, project, stage, timeout, health, process, in_job):
        self.kind = kind
        self.project = project
        self.stage = stage
        self.timeout = timeout
        self.health = health
        self.process = process
        self.in_job = in_job
        from collections import deque
        self._stderr_tail = deque(maxlen=_STDERR_TAIL_LINES)
        self._stderr_lock = threading.Lock()
        self._pump_started = False

    def start_pump(self):
        """启动 stderr 尾部泵线程（幂等）。``communicate`` 会自行排干 stderr，
        调用方随后走 communicate 时由 ``spawn(pump_stderr=False)`` 关闭本泵。"""
        if self._pump_started:
            return
        self._pump_started = True
        stream = getattr(self.process, 'stderr', None)
        if stream is not None:
            threading.Thread(target=self._pump_stderr, args=(stream,),
                             daemon=True, name='supervised-stderr').start()

    def _pump_stderr(self, stream):
        try:
            while True:
                line = stream.readline()
                if line in (b'', ''):
                    break
                with self._stderr_lock:
                    self._stderr_tail.append(line)
            try:
                stream.close()
            except Exception:
                _LOG.debug('stderr 泵关闭管道失败', exc_info=True)
        except Exception:
            _LOG.debug('stderr 泵读取中断', exc_info=True)

    @property
    def pid(self):
        return self.process.pid

    def poll(self):
        return self.process.poll()

    def wait(self, timeout=None):
        """等待退出；缺省用登记超时，超时返回 ``None``（由调用方经 ``error_code`` 归类）。"""
        import subprocess
        try:
            return self.process.wait(timeout=self.timeout if timeout is None else timeout)
        except subprocess.TimeoutExpired:
            return None

    def terminate(self):
        self.process.terminate()

    def kill(self):
        self.process.kill()

    def stderr_tail(self):
        """stderr 尾部若干行（UTF-8 尽力解码），供错误分类与日志取证。"""
        with self._stderr_lock:
            lines = list(self._stderr_tail)
        return ''.join(line.decode('utf-8', errors='replace')
                       if isinstance(line, bytes) else str(line)
                       for line in lines)

    def error_code(self, timed_out=False):
        """当前退出状态归类为 ``error_codes`` 码；仍在运行返回空串。"""
        return classify_exit(self.process.poll(), timed_out=timed_out,
                             stderr_tail=self.stderr_tail())

    def communicate(self, input=None, timeout=None):
        """同步等待并回收输出；结束（含超时被杀）后自动从进程表注销。

        与 ``subprocess.run(timeout=...)`` 同约定：超时或被打断先结束进程树，
        再从登记表移除，避免活进程脱离「强制停止」可见范围。
        """
        try:
            result = self.process.communicate(
                input=input,
                timeout=self.timeout if timeout is None else timeout)
        except BaseException:
            try:
                from contract.platform_tools import terminate_process_tree
                terminate_process_tree(self.process)
                self.process.wait(timeout=3)
            except Exception:
                _LOG.debug('communicate 清理失败', exc_info=True)
            forget_process(self.project, self.process)
            raise
        forget_process(self.project, self.process)
        return result


def classify_exit(returncode, *, timed_out=False, stderr_tail=''):
    """把退出码与 stderr 尾部归类为 ``error_codes`` 码；成功返回空串。

    - 超时 → ``E-TOOL-TIMEOUT``；
    - 找不到可执行文件 → ``E-TOOL-MISSING``（stderr 命中系统「无此命令」措辞）；
    - 其余非零退出 → ``E-TOOL-FAILED``；零退出 → 空串。
    """
    if timed_out:
        return 'E-TOOL-TIMEOUT'
    if returncode is None:
        return ''
    if returncode == 0:
        return ''
    text = (stderr_tail or '').lower()
    if ('not recognized' in text or '不是内部或外部命令' in text
            or 'no such file or directory' in text):
        return 'E-TOOL-MISSING'
    return 'E-TOOL-FAILED'


def spawn(kind, command, *, project, stage, timeout=None, health=None,
          **popen_kwargs):
    """监督器启动入口（I8）：登记进程、挂 Job Object（``detached`` 除外）、留 stderr 尾部。

    ``timeout`` 必须显式给出——各进程种类的默认值登记在 ``PROCESS_KINDS`` 供调用方
    取值，``spawn`` 本身不带默认；缺省或非法值抛 ``ConfigError``，未登记 ``kind``
    同样抛 ``ConfigError``。找不到可执行文件抛 ``ProcessError``（``E-TOOL-MISSING``）。
    返回 ``SupervisedProcess``；``detached`` 种类登记但不进 Job Object。
    其余关键字原样透传给 ``subprocess.Popen``（``env``/``cwd``/``stdin``/``stdout``/
    ``stderr`` 等）；``stderr`` 缺省接管为 ``PIPE`` 供尾部留存，``cwd`` 缺省为项目目录。
    ``popen``（经 ``popen_kwargs`` 透传，不占签名参数位）是显式注入缝（与
    ``platform_tools.launch_background`` 同约定），生产路径不传，测试用它约束
    子进程替身。``pump_stderr=False`` 同理透传——用于调用方随后走 ``communicate``
    的场景：stderr 交给 communicate 一次性排干，不再并发泵读。
    """
    import math
    import subprocess
    from contract.infra_errors import ConfigError, ProcessError
    from contract.platform_tools import hidden_console_flags

    spec = PROCESS_KINDS.get(kind)
    if spec is None:
        raise ConfigError('未登记的进程种类：%r（可选：%s）'
                          % (kind, '、'.join(sorted(PROCESS_KINDS))))
    if timeout is None:
        raise ConfigError('spawn 必须显式给出 timeout；%s 的登记默认值为 %s'
                          % (kind, spec['timeout']))
    try:
        seconds = float(timeout)
    except (TypeError, ValueError):
        raise ConfigError('timeout 必须是正数秒数') from None
    if isinstance(timeout, bool) or not math.isfinite(seconds) or seconds <= 0:
        raise ConfigError('timeout 必须是正数秒数')

    popen = popen_kwargs.pop('popen', None)
    pump_stderr = popen_kwargs.pop('pump_stderr', True)
    popen_kwargs.setdefault('stderr', subprocess.PIPE)
    if popen_kwargs.get('cwd') is None:
        popen_kwargs['cwd'] = str(project)
    popen_kwargs.setdefault('creationflags', hidden_console_flags())
    runner = popen or subprocess.Popen
    try:
        process = runner(command, **popen_kwargs)
    except FileNotFoundError as exc:
        raise ProcessError('找不到可执行文件：%s' % (command[0] if isinstance(command, (list, tuple)) else command),
                           code='E-TOOL-MISSING', detail={'command': str(command)}) from exc
    except OSError as exc:
        raise ProcessError('无法启动进程：%s' % exc, code='E-TOOL-FAILED',
                           detail={'command': str(command), 'errno': exc.errno}) from exc

    register_process(project, process, job=bool(spec['job']))
    register_supervised(process, kind=kind, stage=stage, project=project,
                        in_job=bool(spec['job']))
    sup = SupervisedProcess(kind, project, stage, seconds, health, process,
                            in_job=bool(spec['job']))
    if pump_stderr:
        sup.start_pump()
    return sup
