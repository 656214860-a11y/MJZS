"""REQ-S01-71 离线后端：``voice_engine/offline_asr_server.py`` 子进程客户端（L2）。

引擎进程模块级单例常驻（模型常驻内存，跨听写会话复用）；一次听写只是一次
``start``/``stop``（或 ``cancel``）周期。stdout 事件转成与 ``speech_api.RealtimeSession``
相同的统一接口 ``('partial'|'final'|'error'|'closed'|'log', item, text)``——离线没有
partial，每句 VAD 定稿即 final。子进程崩溃、未安装、超时都转成中文 error/closed 事件，
绝不把异常穿透到界面线程；``fallback`` 注入时启动失败自动降级云端会话。

只依赖标准库与 ``contract.platform_tools``；引擎侧第三方依赖全部隔离在独立 venv。
"""
import atexit
import base64
import json
import os
import queue
import subprocess
import threading
import time
from json import loads as _json_loads
from pathlib import Path

import infra.app_logging as app_logging
import contract.platform_tools as platform_tools

PROGRAM = Path(__file__).resolve().parents[1]
SERVER_SCRIPT = PROGRAM / 'voice_engine' / 'offline_asr_server.py'
VENV_DIR = PROGRAM / 'data' / 'voice_asr_venv'
SAMPLE_RATE = 16000
_ACQUIRE_POLL = 0.1
_MISSING = object()


PROTOCOL_VERSION = 1
MAX_LINE_BYTES = 8 * 1024 * 1024  # 与独立引擎一致，含行结束符


class EngineUnavailable(RuntimeError):
    """引擎不可用（环境缺失/启动失败/进程死亡），``args[0]`` 是中文原因。"""


class EngineBusy(RuntimeError):
    """引擎正被另一个听写会话占用。"""


class EngineCancelled(RuntimeError):
    """等待引擎就绪期间会话被取消。"""


def venv_python(venv_dir):
    """venv 内解释器路径（与 ``voice_engine/bootstrap.py`` 同口径）。"""
    if os.name == 'nt':
        return Path(venv_dir) / 'Scripts' / 'python.exe'
    return Path(venv_dir) / 'bin' / 'python'


def resolve_python(settings):
    """离线引擎解释器：设置优先，否则自动探测 ``data/voice_asr_venv``。"""
    offline = (settings or {}).get('offline') or {}
    explicit = str(offline.get('python') or '').strip()
    if explicit:
        return explicit
    return str(venv_python(VENV_DIR))


def environment_problem(settings):
    """引擎环境体检：返回空串可用，否则一句中文原因（不触发子进程）。"""
    if not SERVER_SCRIPT.is_file():
        return '离线识别引擎文件缺失：%s' % SERVER_SCRIPT
    python = resolve_python(settings)
    if not Path(python).is_file():
        offline = (settings or {}).get('offline') or {}
        explicit = str(offline.get('python') or '').strip()
        if explicit:
            # 用户显式指定的解释器失效：点名设置值本身，便于对照修正。
            return ('离线识别环境未安装（设置的解释器不存在：%s）：请在「模型管理 › '
                    '语音识别…」修正或清空该路径后重试' % python)
        # 任务书 M6：默认 venv 缺失给可执行引导——不贴内部路径、不说「缺少
        # python.exe」；没有云端密钥的新用户按指引任选一条路走通。
        return ('离线语音包未安装：请在「模型管理 › 语音识别…」下载离线语音包，'
                '或为语音识别配置云端密钥')
    return ''


def missing_reason(settings=None):
    """与 ``speech_api.missing_reason`` 同口径：能开离线识别返回空串。"""
    return environment_problem(settings or {})


def _offline_settings(settings):
    return (settings or {}).get('offline') or {}


def _emit_safe(callback, message):
    try:
        callback(message)
    except Exception:  # noqa: BLE001 —— 进度回调失败不影响引擎
        app_logging.swallowed()


class EngineHost:
    """引擎子进程宿主：spawn/读写/看门狗/回收。整台机器同时只允许一个听写会话。"""

    def __init__(self):
        self.lock = threading.Lock()
        self.state = 'idle'          # idle | starting | ready | dead
        self.process = None
        self.session = None          # 当前占用的 OfflineAsrSession
        self.dead_reason = ''
        self.pending_error = ''
        self.protocol_version = None
        self.session_started = False
        self.session_id = 0
        self.stderr_tail = []
        self.log_sinks = []          # 等待就绪期间的进度接收者
        self.write_lock = threading.Lock()

    # ---- 生命周期 ----
    def spawn(self, settings):
        """仅在 idle/dead 时拉起新进程；返回是否真的发起了启动。"""
        offline = _offline_settings(settings)
        env = dict(os.environ)
        cache_dir = str(offline.get('cache_dir') or '').strip()
        if cache_dir:
            env['VOICE_ASR_MODEL_CACHE'] = cache_dir
        threads = str(offline.get('threads') or '').strip()
        if threads:
            env['OMP_NUM_THREADS'] = threads
        command = [resolve_python(settings), str(SERVER_SCRIPT)]
        with self.lock:
            if self.state not in ('idle', 'dead'):
                return False
            self.state = 'starting'
            self.dead_reason = self.pending_error = ''
            self.protocol_version = None
            self.stderr_tail = []
            try:
                self.process = platform_tools.launch_text_process(
                    command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, env=env)
            except Exception as error:  # noqa: BLE001
                self.state = 'dead'
                self.dead_reason = '离线识别引擎启动失败：%s' % str(error)[:160]
                raise EngineUnavailable(self.dead_reason)
            process = self.process
        threading.Thread(target=self._read_stdout, args=(process,),
                         name='voice-asr-reader', daemon=True).start()
        threading.Thread(target=self._drain_stderr, args=(process,),
                         name='voice-asr-stderr', daemon=True).start()
        return True

    def _read_stdout(self, process):
        try:
            stream = process.stdout.buffer
            while line := stream.readline(MAX_LINE_BYTES + 1):
                if len(line) > MAX_LINE_BYTES:
                    self.kill('离线识别响应超出字节上限', expected_process=process)
                    return
                if not line.endswith(b'\n'):
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    message = _json_loads(line.decode('utf-8'))
                except (ValueError, RecursionError):
                    continue
                if isinstance(message, dict):
                    self._dispatch(message, process)
        except (OSError, ValueError):
            app_logging.swallowed()
        self._on_exit(process)

    def _drain_stderr(self, process):
        try:
            for line in process.stderr:
                text = line.strip()
                if text:
                    self.stderr_tail.append(text)
                    del self.stderr_tail[:-20]
        except (OSError, ValueError):
            pass

    def _dispatch(self, message, process):
        kind = message.get('type')
        with self.lock:
            if self.process is not process or self.state == 'dead':
                return
            session = self.session
            if kind == 'ready' and self.state == 'starting':
                version = message.get('protocol_version')
                if 'protocol_version' not in message or (
                    type(version) is int and version == PROTOCOL_VERSION
                ):
                    self.protocol_version = version
                    self.state = 'ready'
                    return
            elif kind == 'log':
                sinks = list(self.log_sinks)
                if session is not None and message.get('started_session_id') == self.session_id:
                    self.session_started = True
            elif kind == 'error' and self.state == 'starting':
                self.pending_error = str(message.get('message') or '')[:200]
            if kind in ('sentence', 'done') and not self.session_started:
                return
            if kind == 'error' and not self.session_started and (
                message.get('start_error_session_id') != self.session_id
            ):
                return
        if kind == 'ready':
            if self.state == 'starting':
                self.kill('离线识别引擎协议版本不受支持', expected_process=process)
            return
        if kind == 'log':
            text = str(message.get('message') or '')
            if session is not None:
                session._engine_log(text)
            for sink in sinks:
                _emit_safe(sink, text)
            return
        if kind in ('error', 'sentence', 'done') and session is not None:
            session._engine_message(message)

    def _on_exit(self, process):
        """stdout EOF：只有当前登记的进程退出才算数（旧 reader 不干扰新进程）。"""
        with self.lock:
            if self.process is not process or self.state == 'dead':
                return
            try:
                code = process.poll()
            except (OSError, ValueError):
                code = None
            if self.state == 'starting' and self.pending_error:
                reason = self.pending_error
            else:
                reason = self._exit_reason(code)
            self.state = 'dead'
            self.dead_reason = reason
            session = self.session
            self.session = None
        if session is not None:
            session._engine_dead(reason)

    def _exit_reason(self, code):
        tail = '；'.join(self.stderr_tail[-3:])[:200]
        suffix = ('：' + tail) if tail else ''
        if code == 2:
            return self.pending_error or '离线识别模型不可用，请检查模型缓存或网络'
        if code not in (None, 0):
            return '离线识别进程意外退出（退出码 %s）%s' % (code, suffix)
        return '离线识别进程已退出%s' % suffix

    # ---- 会话占用 ----
    def attach(self, session):
        with self.lock:
            if self.state != 'ready':
                raise EngineUnavailable(self.dead_reason or '离线识别引擎未就绪')
            if self.session is not None:
                raise EngineBusy('离线识别正在输出上一句，请稍候再试')
            self.session = session
            self.session_id += 1
            self.session_started = self.protocol_version is None

    def detach(self, session):
        with self.lock:
            if self.session is session:
                self.session = None

    # ---- 命令通道 ----
    def command(self, message):
        """向引擎写一行 JSON；进程死亡抛 EngineUnavailable。"""
        with self.write_lock:
            process = self.process
            dead = self.state == 'dead' or process is None
            if not dead:
                try:
                    dead = process.poll() is not None
                except (OSError, ValueError):
                    dead = True
            if dead:
                self._mark_dead('离线识别进程已退出')
                raise EngineUnavailable(self.dead_reason)
            try:
                self._write_command(process, message)
            except (OSError, ValueError) as error:
                self._mark_dead('离线识别进程通信中断：%s' % str(error)[:120])
                raise EngineUnavailable(self.dead_reason)

    def feed(self, pcm):
        self.command({'cmd': 'audio',
                      'data': base64.b64encode(bytes(pcm)).decode('ascii')})

    def _write_command(self, process, message):
        if self.protocol_version is not None:
            message = dict(message, protocol_version=self.protocol_version)
            if message.get('cmd') == 'start':
                message['session_id'] = self.session_id
        process.stdin.write(json.dumps(message, ensure_ascii=False) + '\n')
        process.stdin.flush()

    def _mark_dead(self, reason):
        with self.lock:
            if self.state == 'dead':
                return
            self.state = 'dead'
            self.dead_reason = reason or '离线识别进程已退出'
            session = self.session
            self.session = None
        if session is not None:
            session._engine_dead(self.dead_reason)

    def kill(self, reason, *, expected_process=None):
        """强制结束引擎进程（看门狗用）；下一会话重新拉起。"""
        with self.lock:
            process = self.process
            if self.state == 'dead' or (
                expected_process is not None and self.process is not expected_process
            ):
                return
            self.state = 'dead'
            self.dead_reason = reason
            self.process = None
            session = self.session
            self.session = None
        if session is not None:
            session._engine_dead(reason)
        if process is not None:
            try:
                platform_tools.terminate_process_tree(process)
                process.wait(timeout=3)
            except Exception:  # noqa: BLE001 —— 清理失败不阻塞主程序
                try:
                    process.kill()
                except Exception:  # noqa: BLE001
                    app_logging.swallowed()

    def shutdown(self):
        """退出前收尾：请引擎自尽，超时强杀。"""
        with self.write_lock:
            process = self.process
            if process is not None and self.state != 'dead':
                try:
                    self._write_command(process, {'cmd': 'shutdown'})
                    process.wait(timeout=5)
                except Exception:  # noqa: BLE001
                    app_logging.swallowed()
        self.kill('应用退出')


_HOST = None
_HOST_LOCK = threading.Lock()


def _host():
    global _HOST
    with _HOST_LOCK:
        if _HOST is None:
            _HOST = EngineHost()
        return _HOST


def _shutdown_host():
    host = _HOST
    if host is not None:
        try:
            host.shutdown()
        except Exception:  # noqa: BLE001 —— 退出路径不抛
            app_logging.swallowed()


atexit.register(_shutdown_host)


def acquire(settings, *, log_sink=None, is_cancelled=None):
    """取一个就绪的引擎宿主：没有就拉起并等 ``ready``；失败抛 ``EngineUnavailable``。

    ``log_sink(message)`` 收模型加载/下载进度；``is_cancelled()`` 为真时抛
    ``EngineCancelled``（引擎继续后台就绪，下次复用）。进程死亡后下一次
    ``acquire`` 自动重拉。
    """
    host = _host()
    if log_sink is not None:
        with host.lock:
            host.log_sinks.append(log_sink)
    retried = False
    try:
        while True:
            with host.lock:
                state = host.state
            if state == 'ready':
                return host
            if state == 'dead':
                if retried:
                    raise EngineUnavailable(host.dead_reason or '离线识别引擎不可用')
                retried = True
            if state in ('idle', 'dead'):
                problem = environment_problem(settings)
                if problem:
                    raise EngineUnavailable(problem)
                host.spawn(settings)
                continue
            if is_cancelled is not None and is_cancelled():
                raise EngineCancelled()
            time.sleep(_ACQUIRE_POLL)
    finally:
        if log_sink is not None:
            with host.lock:
                if log_sink in host.log_sinks:
                    host.log_sinks.remove(log_sink)


class OfflineAsrSession:
    """一次听写会话：与 ``RealtimeSession`` 同一接口（start/send/finish/cancel/events）。

    ``fallback(settings) -> 会话`` 为可选降级工厂：引擎在音频流动前不可用时改走
    云端会话并先发一条 ``('log', '', 原因)`` 通知；会话中途崩溃只报 error 不降级。
    ``host`` 为测试注入点（实现 ``attach/detach/command/feed/kill``）。
    """

    def __init__(self, settings, *, fallback=None, host=None):
        self.settings = settings or {}
        self.fallback = fallback
        self.host = host
        self.events = queue.Queue()
        self.audio = queue.Queue()
        self.cancelled = False
        self.thread = None
        self._delegate = None
        self._finished = threading.Event()
        self._closed = False
        self._failed = False
        self._seq = 0

    # ---- 与 RealtimeSession 一致的外部接口 ----
    def start(self):
        self.thread = threading.Thread(target=self._run, name='voice-offline-asr', daemon=True)
        self.thread.start()

    def send(self, pcm):
        self.audio.put(bytes(pcm))

    def finish(self):
        self.audio.put(None)

    def cancel(self):
        self.cancelled = True
        self.audio.put(None)
        delegate = self._delegate
        if delegate is not None:
            delegate.cancel()

    # ---- 事件出口（供 EngineHost/测试驱动） ----
    def _push(self, kind, item, text):
        self.events.put((kind, item, text))

    def _log_event(self, message):
        self._push('log', '', str(message))

    def _fail(self, reason):
        if not self._failed:
            self._failed = True
            self._push('error', '', str(reason))

    def _emit_closed(self):
        if not self._closed:
            self._closed = True
            self._finished.set()
            self._push('closed', '', '')

    def _engine_log(self, message):
        self._log_event(message)

    def _engine_message(self, message):
        if self.cancelled or self._closed:
            return
        kind = message.get('type')
        if kind == 'sentence':
            self._seq += 1
            self._push('final', 's%d' % self._seq, str(message.get('text') or ''))
        elif kind == 'done':
            self._emit_closed()
        elif kind == 'error':
            self._fail(str(message.get('message') or '离线识别引擎报错'))

    def _engine_dead(self, reason):
        """引擎进程死亡/被杀：唤醒消费线程并按失败收尾。"""
        self.audio.put(None)
        if self.cancelled or self._closed:
            return
        self._fail(reason or '离线识别进程意外退出')
        self._finished.set()
        self._emit_closed()

    # ---- 会话主流程 ----
    def _run(self):
        host = None
        try:
            host = self._acquire()
            self._run_offline(host)
        except EngineCancelled:
            pass
        except (EngineUnavailable, EngineBusy) as error:
            self._degrade_or_fail(error)
        finally:
            if host is not None:
                try:
                    host.detach(self)
                except Exception:  # noqa: BLE001
                    app_logging.swallowed()
            self._emit_closed()

    def _acquire(self):
        if self.host is not None:
            return self.host
        return acquire(self.settings, log_sink=self._log_event,
                       is_cancelled=lambda: self.cancelled)

    def _degrade_or_fail(self, reason):
        text = str(reason)
        if self.fallback is not None:
            self._run_delegate(text)
        else:
            self._fail(text)

    def _start_command(self):
        command = {'cmd': 'start', 'sample_rate': SAMPLE_RATE}
        offline = _offline_settings(self.settings)
        hotword = str(offline.get('hotword') or '').strip()
        if hotword:
            command['hotword'] = hotword
        try:
            trailing = int(offline.get('vad_trailing_ms'))
        except (TypeError, ValueError):
            trailing = 0
        if trailing > 0:
            command['vad'] = {'trailing_ms': trailing}
        return command

    def _run_offline(self, host):
        host.attach(self)
        try:
            host.command(self._start_command())
        except EngineUnavailable:
            raise   # 音频未流动，交给 _run 决定是否降级
        while True:
            pcm = self.audio.get()
            if pcm is None or self.cancelled:
                break
            try:
                host.feed(pcm)
            except EngineUnavailable as error:
                self._fail(str(error))
                return
        if self.cancelled:
            try:
                host.command({'cmd': 'cancel'})
            except EngineUnavailable:
                pass
            return
        try:
            host.command({'cmd': 'stop'})
        except EngineUnavailable as error:
            self._fail(str(error))
            return
        try:
            timeout = float(self.settings.get('timeout', 15))
        except (TypeError, ValueError):
            timeout = 15.0
        if not self._finished.wait(max(1.0, timeout)):
            reason = '离线识别收尾超时（%d 秒），已断开引擎' % int(timeout)
            self._fail(reason)
            self._finished.set()
            host.kill(reason)

    def _run_delegate(self, reason):
        """引擎不可用且配置了云端后端：降级 ``fallback`` 会话并转发事件。"""
        self._log_event('离线识别不可用（%s），本次改用云端识别。' % reason)
        try:
            delegate = self.fallback(self.settings)
        except Exception as error:  # noqa: BLE001
            self._fail('离线与云端识别都不可用：%s' % str(error)[:120])
            return
        self._delegate = delegate
        delegate.start()
        while True:
            try:
                pcm = self.audio.get_nowait()
            except queue.Empty:
                pcm = _MISSING
            if pcm is not _MISSING:
                if pcm is None:
                    delegate.cancel() if self.cancelled else delegate.finish()
                else:
                    delegate.send(pcm)
                continue
            try:
                kind, item, text = delegate.events.get(timeout=0.05)
            except queue.Empty:
                continue
            if kind == 'closed':
                self._closed = True
                self._finished.set()
            self._push(kind, item, text)
            if kind == 'closed':
                break
        self._delegate = None
