"""Small local-machine adapters with no workflow or UI dependency."""
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import webbrowser
import threading
import time
from contextlib import contextmanager
from urllib.parse import urlparse

_TOOL_CACHE = {}
# 随包二进制目录相对应用根（本文件在 程序/contract/ 下，上两级即分发根）。
# 运行环境/ 不入库，由分发构建从部署机复制；不存在时 _bundled_tool 返回 None。
_BUNDLED_BIN_DIR = Path(__file__).resolve().parents[2] / '运行环境' / 'ffmpeg' / 'bin'
_EXECUTION = threading.local()


class ExecutionStopped(RuntimeError):
    """Local stop, never proof that a provider or an in-flight thread stopped."""
    def __init__(self, reason, *, started=False):
        self.reason, self.started = reason, started
        super().__init__('执行已停止：%s；%s' % (reason, '在途结果待核对' if started else '未开始此单元'))


class ExecutionControl:
    def __init__(self, timeout=3600, *, observer=None):
        import math
        import uuid
        seconds = float(timeout)
        if not math.isfinite(seconds) or seconds <= 0:
            raise ValueError('执行期限必须是大于零的有限秒数')
        self.deadline = time.monotonic() + seconds
        self.stopped = threading.Event()
        self.observer = observer
        self.run_id = uuid.uuid4().hex

    def cancel(self):
        self.stopped.set()

    def checkpoint(self):
        if self.stopped.is_set():
            raise ExecutionStopped('cancelled')
        if time.monotonic() >= self.deadline:
            raise ExecutionStopped('deadline')

    def remaining(self, requested=None):
        self.checkpoint()
        remaining = max(.001, self.deadline - time.monotonic())
        return remaining if requested is None else min(float(requested), remaining)

    def report(self, **facts):
        if self.observer is not None:
            self.observer(facts)


def current_execution():
    return getattr(_EXECUTION, 'control', None)


def execution_metadata(stage, task, *, attempt=None):
    """Identity only: one supervised invocation is a run, each submission an attempt."""
    import uuid
    control = current_execution()
    return {'run_id': control.run_id if control is not None else uuid.uuid4().hex,
            'stage': str(stage), 'task_id': str(task),
            'attempt_id': str(attempt or uuid.uuid4().hex)}


@contextmanager
def execution_scope(control):
    previous = current_execution()
    _EXECUTION.control = control
    try:
        yield control
    finally:
        _EXECUTION.control = previous


def execution_checkpoint():
    control = current_execution()
    if control is not None:
        control.checkpoint()


def windows_registry():
    """返回 Windows 当前用户注册表模块；其他平台或精简运行时返回 ``None``。

    调用方只根据返回值决定功能是否可用，不能把 ``winreg`` 的可选导入散落到 UI、
    密钥或自启动逻辑里。这样 macOS/Linux 的降级语义一致，也便于测试替换宿主能力。
    """
    if os.name != 'nt':
        return None
    try:
        import winreg
    except ImportError:
        return None
    return winreg


_DOWNLOADS_FOLDER_ID = '{374DE290-123F-4565-9164-39C4925E467B}'


def downloads_directory():
    """当前用户的「下载」文件夹。

    Windows 读 User Shell Folders 里登记的下载位置（用户可能把它挪到别的盘）；
    读不到或不是目录时退回 ``~/Downloads``。只返回路径，不创建目录。
    """
    registry = windows_registry()
    if registry is not None:
        try:
            with registry.OpenKey(registry.HKEY_CURRENT_USER,
                                  r'Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders') as key:
                value, _kind = registry.QueryValueEx(key, _DOWNLOADS_FOLDER_ID)
            folder = Path(os.path.expandvars(str(value)))
            if folder.is_dir():
                return folder
        except OSError:
            pass
    return Path.home() / 'Downloads'


def hidden_console_flags():
    """Return the host-supported flag for background commands without a console window.

    Windows exposes ``CREATE_NO_WINDOW`` while other hosts have no equivalent;
    returning zero there keeps callers portable and removes magic constants from
    workflow, probe, and local-app adapters.
    """
    return getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0


def launch_background(command, *, cwd=None, stdin=None, stdout=None, stderr=None, env=None,
                      popen=None):
    """Start a host background process with the common silent-window policy.

    ``popen`` is an explicit injection seam for callers that must constrain a
    child environment and already expose a process-launch test hook.
    """
    execution_checkpoint()
    runner = popen or subprocess.Popen
    return runner(command, cwd=None if cwd is None else str(cwd),
                  creationflags=hidden_console_flags(),
                  stdin=stdin, stdout=stdout, stderr=stderr, env=env)


def launch_text_process(command, *, cwd=None, stdin=None, stdout=None, stderr=None, env=None):
    """Start a background process whose stdin/stdout use UTF-8 text mode (registered workflow engines)."""
    import functools
    return launch_background(command, cwd=cwd, stdin=stdin, stdout=stdout, stderr=stderr, env=env,
                             popen=functools.partial(subprocess.Popen, text=True, encoding='utf-8', errors='replace'))


def run_process(command, *, run=None, **kwargs):
    """Run a local host command with the shared hidden-console policy."""
    control = current_execution()
    if control is not None:
        kwargs['timeout'] = control.remaining(kwargs.get('timeout'))
    runner = run or subprocess.run
    if kwargs.get('cwd') is not None:
        kwargs['cwd'] = str(kwargs['cwd'])
    kwargs.setdefault('creationflags', hidden_console_flags())
    return runner(command, **kwargs)


def require_windows(feature):
    """Reject a Windows-only local integration with an actionable UI message."""
    if os.name != 'nt':
        raise ValueError(str(feature) + '仅支持 Windows；请在 Windows 设备上执行该本地操作。')


def terminate_process_tree(process, *, timeout=3):
    """结束已登记的后台进程；Windows 同时结束其子进程，其他宿主走标准终止。"""
    if os.name != 'nt':
        process.terminate()
        return True
    try:
        result = subprocess.run(
            ['taskkill', '/PID', str(process.pid), '/F', '/T'],
            capture_output=True, timeout=timeout, creationflags=hidden_console_flags())
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def communicate_or_kill(process, data, timeout, on_output=None):
    """喂完输入并等进程退出；超过 timeout 秒就结束整棵进程树，再抛 TimeoutExpired。

    ``on_output`` 可选：提供时，要求 ``process.stdout``／``process.stderr`` 是 PIPE，
    逐行读取并把每一行（含行尾换行符）回调为 ``on_output(line, stream)``，其中
    ``stream`` 是 ``'stdout'`` 或 ``'stderr'``，让调用方能区分日志与结构化响应；
    回调抛异常只吞掉并继续，不打断引擎运行。未提供时行为与原先一致（``communicate``）。
    """
    if on_output is None:
        try:
            return process.communicate(data, timeout=timeout)
        except subprocess.TimeoutExpired:
            terminate_process_tree(process)
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
            raise
    return _stream_communicate_or_kill(process, data, timeout, on_output)


def _stream_communicate_or_kill(process, data, timeout, on_output):
    """逐行读 PIPE 输出并回调 ``on_output(line, stream)``；读不到行或超时按超时处理。"""
    import threading

    def pump(stream, name):
        try:
            for line in stream or ():
                try:
                    on_output(line, name)
                except Exception:
                    # 回调抛异常只吞掉并继续，不让一次失败截断整路输出与回写日志。
                    pass
        except Exception:
            # 读流被打断（进程退出、PIPE 关闭）属预期。
            return

    out_thread = threading.Thread(target=pump, args=(process.stdout, 'stdout'), daemon=True)
    err_thread = threading.Thread(target=pump, args=(process.stderr, 'stderr'), daemon=True)
    out_thread.start()
    err_thread.start()
    try:
        process.stdin.write(data or '')
        process.stdin.flush()
        process.stdin.close()
    except (OSError, ValueError, AttributeError):
        # stdin 不是 PIPE（如某些调用方用文件对象）时，无法喂输入，忽略。
        pass
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        terminate_process_tree(process)
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
        raise
    finally:
        out_thread.join(timeout=3)
        err_thread.join(timeout=3)
    return process.returncode


def duration_text(seconds):
    """超时提示里的时长：满一分钟按分钟说，不满按秒说。"""
    seconds = int(seconds)
    return '%d 分钟' % (seconds // 60) if seconds >= 60 else '%d 秒' % seconds


def _bundled_tool(name):
    """随包版本（``运行环境/ffmpeg/bin/<name>.exe``）；不存在返回 None。

    只在文件真实存在时返回——失效的随包路径不能压过系统 PATH。
    """
    for candidate in (_BUNDLED_BIN_DIR / (name + '.exe'), _BUNDLED_BIN_DIR / name):
        try:
            if candidate.is_file():
                return str(candidate)
        except OSError:
            continue
    return None


def tool_path(name, fallback='', configured=''):
    """Return a cached executable path, falling back to an explicit setting.

    解析优先级（R3154，零依赖边界任务书 M1）：调用方传入的**显式且有效**
    的配置（``configured``）> 随包版本 > 系统 PATH > 调用方 ``fallback`` 原文。
    显式**路径**失效（文件不存在）时继续向下回退，不会压住随包/PATH；
    裸命令名（无路径分隔符，如 ``ffmpeg``／测试替身 ``stub``）无法按文件校验，
    原样下传、由 exec 时的 PATH 解析决定；``fallback`` 不查存在性，
    保持「兜底原文」语义。

    只缓存 `which` 的结果：未命中时不把 None 写进缓存，否则先发生的无兜底查询会让
    后续带兜底的调用拿不到明确路径（首帧解码就会把 None 交给 subprocess）。
    """
    configured = str(configured or '').strip()
    if configured:
        if '/' not in configured and '\\' not in configured:
            return configured
        try:
            if Path(configured).is_file():
                return configured
        except OSError:
            pass
    bundled = _bundled_tool(name)
    if bundled:
        return bundled
    if name not in _TOOL_CACHE:
        _TOOL_CACHE[name] = shutil.which(name) or None
    return _TOOL_CACHE[name] or fallback or None


def reveal_in_folder(path):
    """在系统文件管理器里定位这个文件（Windows 在资源管理器里选中它）。

    ``explorer /select`` 的退出码恒为 1，不是失败信号——拉起即返回，不读返回码。
    """
    target = Path(path)
    if not target.exists():
        raise ValueError('要定位的文件或目录不存在：' + str(target))
    if os.name == 'nt':
        subprocess.Popen(['explorer', '/select,', str(target.resolve())],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return str(target)
    if sys.platform == 'darwin':
        command = ['open', '-R', str(target)]
    else:
        command = ['xdg-open', str(target.parent if target.is_file() else target)]
    if shutil.which(command[0]) is None:
        raise ValueError('当前系统没有可用的文件管理器，请手动打开：' + str(target))
    try:
        subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as exc:
        raise ValueError('无法调用文件管理器：' + str(exc)) from exc
    return str(target)


def open_path(path):
    """用宿主系统默认程序打开一个已存在的文件或目录。

    UI 不应直接依赖 Windows 的 ``os.startfile``；本地缺少可用打开器时抛出可展示的
    ValueError，而不是让 AttributeError 穿透到通用“操作未完成”弹窗。
    """
    target = Path(path)
    if not target.exists():
        raise ValueError('要打开的文件或目录不存在：' + str(target))
    startfile = getattr(os, 'startfile', None)
    if callable(startfile):
        startfile(str(target))
        return str(target)
    command = ['open', str(target)] if sys.platform == 'darwin' else ['xdg-open', str(target)]
    if shutil.which(command[0]) is None:
        raise ValueError('当前系统没有可用的默认打开器，请在文件管理器中打开：' + str(target))
    try:
        subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as exc:
        raise ValueError('无法调用系统默认打开器：' + str(exc)) from exc
    return str(target)


def open_target(target):
    """打开本地路径、HTTP(S) 或白名单 Codex 深链，供 UI 取代 Windows ``startfile``。"""
    value = str(target or '').strip()
    # ``urlparse('C:\\foo')`` 会把 C 误判为 scheme；盘符路径必须优先按本地文件处理。
    if Path(value).drive:
        return open_path(value)
    parsed = urlparse(value)
    if parsed.scheme:
        if parsed.scheme in {'codex'}:
            message = '无法打开 codex:// 链接:请确认已安装并注册 ChatGPT/Codex 桌面协议。'
            startfile = getattr(os, 'startfile', None)
            if not callable(startfile):
                raise ValueError(message)
            try:
                startfile(value)
            except OSError as exc:
                raise ValueError(message) from exc
            return value
        if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
            raise ValueError('只允许打开有效的 HTTP(S) 链接：' + value)
        if not webbrowser.open(value):
            raise ValueError('无法调用默认浏览器打开链接：' + value)
        return value
    return open_path(value)


def open_directory(path):
    """确保目录存在再用宿主默认程序打开；UI 不该自己拼「建目录 + 打开」。"""
    target = Path(path)
    target.mkdir(exist_ok=True)
    return open_path(target)


_EDITOR_START_MENU = 'Microsoft/Windows/Start Menu/Programs'


def find_editor_shortcut(name='剪映专业版', *, skip=('卸载',)):
    """在开始菜单里找剪映专业版（或指定名）的快捷方式；跳过卸载项，找不到返回 None。

    原先这段扫描长在 desktop.py（L4）里，是纯本机适配逻辑，搬到 L0 便于单独测试与复用。
    """
    for base in (os.environ.get('APPDATA', ''), os.environ.get('PROGRAMDATA', '')):
        root = Path(base) / _EDITOR_START_MENU
        if not root.is_dir():
            continue
        for shortcut in root.glob('**/*%s*.lnk' % name):
            if not any(word in shortcut.name for word in skip):
                return shortcut
    return None


def tcp_listener(url, *, timeout=0.3):
    """Return whether a local TCP endpoint accepts a short connection.

    Local-process reachability belongs to this host adapter so Tk views do not
    open sockets themselves.  It deliberately sends no HTTP request.
    """
    parsed = urlparse(str(url or ''))
    host = parsed.hostname or '127.0.0.1'
    try:
        port = parsed.port or 8188
    except ValueError:
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def probe_http_endpoint(base_url, *, timeout=8):
    """Probe an HTTP(S) root without credentials or a request body.

    Network reachability is a host-adapter responsibility.  Keeping this small
    probe here gives configuration pages and future access gates one controlled
    outbound path while preserving their user-facing failure classification.
    """
    import urllib.request, urllib.error
    try:
        with urllib.request.urlopen(str(base_url).rstrip('/'), timeout=timeout) as response:
            return {'reachable': True, 'code': response.status}
    except urllib.error.HTTPError as exc:
        return {'reachable': True, 'code': exc.code}
    except Exception as exc:
        reason = getattr(exc, 'reason', None)
        detail = str(reason) if reason is not None else str(exc)
        low = detail.lower()
        if 'getaddrinfo' in low or 'name or service not known' in low or 'gaierror' in low:
            hint = '域名解析失败，请检查网络/DNS 或确认地址拼写正确'
        elif 'certificate' in low or 'ssl' in low:
            hint = 'HTTPS 证书校验失败，请检查系统时间、代理或防火墙'
        elif 'timed out' in low or 'timeout' in low:
            hint = '连接超时，请检查网络、防火墙或代理'
        elif 'refused' in low or '10061' in low:
            hint = '连接被拒绝，请确认地址与端口正确'
        else:
            hint = type(exc).__name__
        return {'reachable': False, 'code': None, 'error': f'{hint}（{detail[:160]}）'}


_CREDENTIAL_HEADERS = frozenset({'authorization', 'proxy-authorization', 'cookie'})
_HTTP_CACHE = {}


def _origin(url):
    parts = urlparse(url)
    scheme = parts.scheme.lower()
    return scheme, (parts.hostname or '').lower(), parts.port or {'http': 80, 'https': 443}.get(scheme)


def _same_origin(first, second):
    """协议、主机、端口都相同才算同一来源；端口写坏的地址按不同来源处理。"""
    try:
        return _origin(first) == _origin(second)
    except ValueError:
        return False


def _redirect_handler():
    """open_https 的重定向处理器：照常跟随，跳到另一来源时去掉凭据头（urllib 按需加载，类只建一次）。"""
    handler = _HTTP_CACHE.get('redirect')
    if handler is None:
        import urllib.request

        class CredentialSafeRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                forwarded = super().redirect_request(req, fp, code, msg, headers, newurl)
                if forwarded is not None and not _same_origin(req.full_url, forwarded.full_url):
                    for name in [key for key in forwarded.headers if key.lower() in _CREDENTIAL_HEADERS]:
                        forwarded.remove_header(name)
                return forwarded

        handler = _HTTP_CACHE['redirect'] = CredentialSafeRedirect
    return handler


def open_https(url, *, timeout=60, data=None, headers=None, method=None, context=None):
    """唯一出站 HTTP(S) 入口：返回已打开的响应，读取与错误分类留给调用方。

    与 ``run_process`` 同属宿主适配层——出站网络调用集中在此，便于统一超时、代理
    与后续访问闸门策略；``data`` 为 None 时是 GET，否则按请求体发送。``method``
    显式指定动词（如 DELETE）；``context`` 是调用方的 ``ssl.SSLContext``（如钉证书）。
    重定向照常跟随，但跳到另一来源（协议、主机、端口任一不同，含 https→http）时不再带
    Authorization／Proxy-Authorization／Cookie，令牌不会被转给跳转目标。
    """
    import urllib.request
    control = current_execution()
    if control is not None:
        timeout = control.remaining(timeout)
    request = urllib.request.Request(str(url), data=data, headers=dict(headers or {}), method=method)
    if context is not None:
        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context), _redirect_handler())
    else:
        # 同 urlopen 的全局 opener 一样复用：每建一个都要重新装一遍系统根证书（本机实测约 20 ms）。
        opener = _HTTP_CACHE.get('opener')
        if opener is None:
            opener = _HTTP_CACHE['opener'] = urllib.request.build_opener(_redirect_handler())
    return opener.open(request, timeout=timeout)


def _requests_failure(error):
    """Expose only safe transport messages; callers retain the original cause."""
    import requests
    import urllib.error
    from urllib3.exceptions import TimeoutError as ReadTimeout
    if isinstance(error, (requests.exceptions.Timeout, ReadTimeout, TimeoutError)):
        return TimeoutError('network request timed out')
    return urllib.error.URLError('network request failed')


class _RequestsJsonResponse:
    """Bounded decoded reads and one owner for the response/session lifetime."""
    def __init__(self, response, session):
        self.response, self.session = response, session
        self.status, self.headers = response.status_code, response.headers

    def read(self, size=-1):
        import requests
        from urllib3.exceptions import HTTPError
        try:
            return self.response.raw.read(size, decode_content=True)
        except (requests.exceptions.RequestException, HTTPError, OSError) as error:
            self.close()
            raise _requests_failure(error) from error

    def close(self):
        session, self.session = self.session, None
        if session is not None:
            try:
                self.response.close()
            finally:
                session.close()

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()


def _requests_tls_adapter(verify):
    """Default trust is system + certifi; an explicit CA path replaces both."""
    import certifi
    import ssl
    from requests.adapters import HTTPAdapter

    if verify is True:
        context = ssl.create_default_context()
        context.load_verify_locations(certifi.where())
    else:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        locations = {'capath' if os.path.isdir(verify) else 'cafile': verify}
        context.load_verify_locations(**locations)

    class VerifiedAdapter(HTTPAdapter):
        def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
            pool_kwargs['ssl_context'] = context
            return super().init_poolmanager(connections, maxsize, block=block, **pool_kwargs)

        def proxy_manager_for(self, proxy, **proxy_kwargs):
            proxy_kwargs.update(ssl_context=context, proxy_ssl_context=context)
            return super().proxy_manager_for(proxy, **proxy_kwargs)

        def build_connection_pool_key_attributes(self, request, verify, cert=None):
            # requests >= 2.32 otherwise replaces the manager's context with certifi-only trust.
            host, pool = super().build_connection_pool_key_attributes(request, verify, cert)
            pool['ssl_context'] = context
            return host, pool

    return VerifiedAdapter(max_retries=0)


class RequestsJsonOpener:
    """urllib Request/.open adapter; retries and redirects stay in the caller."""
    def open(self, request, timeout=None):
        import urllib.error
        if os.environ.get('DRAMA_SUPPRESS_NETWORK') == '1':
            raise urllib.error.URLError('network suppressed')
        import requests
        session, response = requests.Session(), None
        try:
            # Empty auth tuples are falsy and still permit netrc to replace Authorization.
            session.auth = lambda prepared: prepared
            prepared = session.prepare_request(requests.Request(
                request.get_method(), request.full_url, data=request.data, headers=dict(request.header_items())))
            settings = session.merge_environment_settings(prepared.url, {}, True, True, None)
            adapter = _requests_tls_adapter(settings['verify'])
            for scheme in ('http://', 'https://'):
                session.mount(scheme, adapter)
            # Session.send builds _next even with redirects disabled, consuming redirect bodies.
            response = session.get_adapter(prepared.url).send(prepared, timeout=timeout, **settings)
        except BaseException as error:
            try:
                if response is not None:
                    response.close()
            finally:
                session.close()
            if isinstance(error, (requests.exceptions.RequestException, OSError)):
                raise _requests_failure(error) from error
            raise
        result = _RequestsJsonResponse(response, session)
        if not 200 <= response.status_code < 300:
            raise urllib.error.HTTPError(request.full_url, response.status_code, response.reason, response.headers, result)
        return result


class WebSocketRefused(OSError):
    """握手没拿到 101：``status`` 是服务端返回的 HTTP 状态码。"""
    def __init__(self, status):
        super().__init__('WebSocket 握手被拒绝（HTTP %d）' % status)
        self.status = status


def _apply_mask(payload, mask):
    """RFC 6455 掩码：按 4 字节循环异或，整段一次算完。"""
    size = len(payload)
    if not size:
        return b''
    key = (mask * (size // 4 + 1))[:size]
    return (int.from_bytes(payload, 'little') ^ int.from_bytes(key, 'little')).to_bytes(size, 'little')


class WebSocket:
    """最小 WebSocket 客户端（RFC 6455，零第三方依赖）：只收发文本帧，自动回 pong。

    由 ``open_websocket`` 建立；``send_text`` 可在任意线程调用（内部加锁），``recv_text``
    只应由一个读线程调用，对端关闭时返回 None。``close()`` 可从别的线程打断阻塞中的读。
    """
    def __init__(self, sock, pending=b''):
        self.sock, self.buffer, self.lock = sock, bytearray(pending), threading.Lock()

    def _frame(self, opcode, payload):
        import struct
        size, mask = len(payload), os.urandom(4)
        if size < 126:
            head = struct.pack('!BB', 0x80 | opcode, 0x80 | size)
        elif size < 65536:
            head = struct.pack('!BBH', 0x80 | opcode, 0x80 | 126, size)
        else:
            head = struct.pack('!BBQ', 0x80 | opcode, 0x80 | 127, size)
        masked = _apply_mask(payload, mask)
        with self.lock:
            self.sock.sendall(head + mask + masked)

    def send_text(self, text):
        self._frame(0x1, str(text).encode('utf-8'))

    def _read(self, count):
        while len(self.buffer) < count:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError('WebSocket 连接被对端断开')
            self.buffer += chunk
        data = bytes(self.buffer[:count])
        del self.buffer[:count]
        return data

    def recv_text(self):
        import struct
        parts = []
        while True:
            first, second = self._read(2)
            size = second & 0x7F
            if size == 126:
                size = struct.unpack('!H', self._read(2))[0]
            elif size == 127:
                size = struct.unpack('!Q', self._read(8))[0]
            mask = self._read(4) if second & 0x80 else b''
            payload = self._read(size)
            if mask:
                payload = _apply_mask(payload, mask)
            opcode = first & 0x0F
            if opcode == 0x8:
                self.close()
                return None
            if opcode == 0x9:
                self._frame(0xA, payload)
                continue
            if opcode in (0x0, 0x1, 0x2):
                parts.append(payload)
                if first & 0x80:
                    return b''.join(parts).decode('utf-8', 'replace')

    def close(self):
        try:
            self._frame(0x8, b'')
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass


def open_websocket(url, *, headers=None, timeout=15, context=None):
    """唯一出站 WebSocket 入口（与 ``open_https`` 同属宿主适配层）：握手成功返回 ``WebSocket``。

    ``wss://`` 走 TLS 并校验证书；握手阶段受 ``timeout`` 约束，建立后读操作不再超时
    （长连接里对端可能很久不发消息），由调用方 ``close()`` 结束。
    """
    import base64
    import hashlib
    import socket
    import ssl
    from urllib.parse import urlsplit
    parts = urlsplit(str(url))
    if parts.scheme not in ('ws', 'wss') or not parts.hostname:
        raise ValueError('WebSocket 地址必须以 ws:// 或 wss:// 开头')
    control = current_execution()
    if control is not None:
        timeout = control.remaining(timeout)
    port = parts.port or (443 if parts.scheme == 'wss' else 80)
    sock = socket.create_connection((parts.hostname, port), timeout=timeout)
    try:
        if parts.scheme == 'wss':
            sock = (context or ssl.create_default_context()).wrap_socket(sock, server_hostname=parts.hostname)
        key = base64.b64encode(os.urandom(16)).decode('ascii')
        target = (parts.path or '/') + ('?' + parts.query if parts.query else '')
        host = parts.hostname if parts.port is None else '%s:%d' % (parts.hostname, parts.port)
        lines = ['GET %s HTTP/1.1' % target, 'Host: ' + host, 'Upgrade: websocket', 'Connection: Upgrade',
                 'Sec-WebSocket-Key: ' + key, 'Sec-WebSocket-Version: 13']
        lines += ['%s: %s' % item for item in dict(headers or {}).items()]
        sock.sendall(('\r\n'.join(lines) + '\r\n\r\n').encode('utf-8'))
        response = b''
        while b'\r\n\r\n' not in response:
            chunk = sock.recv(4096)
            if not chunk or len(response) > 65536:
                raise ConnectionError('WebSocket 握手没有完成')
            response += chunk
        head, pending = response.split(b'\r\n\r\n', 1)
        status_line, *header_lines = head.decode('latin-1').split('\r\n')
        code = (status_line.split() + ['', ''])[1]
        if code != '101':
            raise WebSocketRefused(int(code) if code.isdigit() else 0)
        fields = {name.strip().lower(): value.strip() for name, _, value in (line.partition(':') for line in header_lines)}
        expected = base64.b64encode(hashlib.sha1((key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode('ascii')).digest())
        if fields.get('sec-websocket-accept', '').encode('ascii') != expected:
            raise ConnectionError('WebSocket 握手校验失败')
        sock.settimeout(None)
        return WebSocket(sock, pending)
    except BaseException:
        sock.close()
        raise


def launch_windows_app(executable, feature, *, args=None, cwd=None, env=None, creationflags=0):
    """启动已定位的 Windows 本地程序，并把宿主失败转成可展示提示。

    ``args`` 让本地 CLI 也复用同一个 Windows 宿主边界；未提供时仍只启动
    可执行文件本身，保持桌面应用入口的原有行为。
    """
    execution_checkpoint()
    require_windows(feature)
    executable = Path(executable)
    if not executable.is_file():
        raise ValueError(str(feature) + '程序不存在：' + str(executable))
    command = [str(executable)] if args is None else [str(item) for item in args]
    if not command or command[0] != str(executable):
        raise ValueError(str(feature) + '启动命令必须以已定位的程序开头：' + str(executable))
    try:
        return subprocess.Popen(command, cwd=str(cwd or executable.parent), env=env,
                                creationflags=creationflags)
    except OSError as exc:
        raise ValueError('无法启动' + str(feature) + '：' + str(exc)) from exc


def work_area():
    """主显示器去掉任务栏后的可用区域 ``(left, top, right, bottom)``；取不到返回 ``None``。"""
    if os.name != 'nt':
        return None
    try:
        import ctypes
        from ctypes import wintypes
        rect = wintypes.RECT()
        if not ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(rect), 0):
            return None
    except (OSError, AttributeError, ValueError):
        return None
    return (rect.left, rect.top, rect.right, rect.bottom)


# REQ-S01-71：麦克风录音（仿桌面微信：先录音，再交云端识别）。R2112 的 System.Speech 离线听写中文识别率低，已撤下。
# 用 winmm 的 waveIn*（ctypes，零依赖）录默认麦克风：16 kHz、单声道、16 位，正是云端识别要的格式。
RECORD_RATE = 16000
_RECORD_CHUNK_BYTES = RECORD_RATE // 10 * 2      # 每块缓冲 0.1 秒
_RECORD_BUFFERS = 8
_WHDR_DONE = 0x1
_WAVE_MAPPER = 0xFFFFFFFF


def wav_bytes(pcm, rate=RECORD_RATE):
    """16 位单声道 PCM 包成 WAV 文件字节。"""
    import struct
    data = bytes(pcm)
    # 随附运行环境裁掉了标准库 wave，这里直接写 44 字节 RIFF 头。
    return (struct.pack('<4sI4s4sIHHIIHH4sI', b'RIFF', 36 + len(data), b'WAVE', b'fmt ', 16, 1, 1,
                        rate, rate * 2, 2, 16, b'data', len(data)) + data)


def _peak(chunk):
    import array
    samples = array.array('h', bytes(chunk[:len(chunk) // 2 * 2]))
    return max((abs(value) for value in samples), default=0)


def _wave_types():
    import ctypes
    from ctypes import wintypes

    class WaveFormat(ctypes.Structure):
        _fields_ = [('wFormatTag', wintypes.WORD), ('nChannels', wintypes.WORD),
                    ('nSamplesPerSec', wintypes.DWORD), ('nAvgBytesPerSec', wintypes.DWORD),
                    ('nBlockAlign', wintypes.WORD), ('wBitsPerSample', wintypes.WORD), ('cbSize', wintypes.WORD)]

    class WaveHeader(ctypes.Structure):
        _fields_ = [('lpData', ctypes.c_void_p), ('dwBufferLength', wintypes.DWORD),
                    ('dwBytesRecorded', wintypes.DWORD), ('dwUser', ctypes.c_void_p),
                    ('dwFlags', wintypes.DWORD), ('dwLoops', wintypes.DWORD),
                    ('lpNext', ctypes.c_void_p), ('reserved', ctypes.c_void_p)]
    return WaveFormat, WaveHeader


class MicrophoneRecorder:
    """录音会话：start() 打开默认麦克风，后台线程收 PCM；stop() 收尾并返回 ``(wav 字节, 全程峰值)``。

    ``level``（0–1，最近 0.1 秒的峰值）与 ``seconds`` 供界面显示；录满 ``max_seconds``
    或设备出错时 ``finished`` 变真，界面据此自动收尾。给了 ``on_chunk`` 时每 0.1 秒把这一块
    PCM 交给它（在录音线程里调用），不再攒整段，stop() 返回的 WAV 为空。``winmm`` 是测试注入点。
    """
    def __init__(self, *, max_seconds=180, winmm=None, on_chunk=None):
        self.max_seconds, self.winmm, self.on_chunk = max_seconds, winmm, on_chunk
        self.pcm, self.recorded, self.peak, self.level, self.error = bytearray(), 0, 0, 0.0, ''
        self.handle, self.thread = None, None
        self.halt = threading.Event()

    @property
    def seconds(self):
        return self.recorded / (RECORD_RATE * 2)

    @property
    def finished(self):
        return self.thread is not None and not self.thread.is_alive()

    def start(self):
        """成功返回空串，失败返回原因。"""
        import ctypes
        if os.name != 'nt' and self.winmm is None:
            return '当前系统不支持录音'
        winmm = self.winmm or ctypes.windll.winmm
        if not winmm.waveInGetNumDevs():
            return '没有找到麦克风'
        WaveFormat, WaveHeader = _wave_types()
        fmt = WaveFormat(1, 1, RECORD_RATE, RECORD_RATE * 2, 2, 16, 0)
        handle = ctypes.c_void_p()
        code = winmm.waveInOpen(ctypes.byref(handle), ctypes.c_uint(_WAVE_MAPPER), ctypes.byref(fmt), None, None, 0)
        if code:
            return '麦克风打不开（错误码 %d，可能被其他程序独占）' % code
        self.handle = handle
        buffers = [ctypes.create_string_buffer(_RECORD_CHUNK_BYTES) for _ in range(_RECORD_BUFFERS)]
        headers = [WaveHeader(ctypes.cast(buffer, ctypes.c_void_p), _RECORD_CHUNK_BYTES) for buffer in buffers]
        for header in headers:
            winmm.waveInPrepareHeader(handle, ctypes.byref(header), ctypes.sizeof(header))
            winmm.waveInAddBuffer(handle, ctypes.byref(header), ctypes.sizeof(header))
        winmm.waveInStart(handle)
        self.thread = threading.Thread(target=self._collect, args=(winmm, handle, buffers, headers),
                                       name='voice-record', daemon=True)
        self.thread.start()
        return ''

    def _take(self, buffer, header):
        chunk = buffer.raw[:header.dwBytesRecorded]
        peak = _peak(chunk)
        self.recorded += len(chunk)
        if self.on_chunk is None:
            self.pcm += chunk
        elif chunk:
            self.on_chunk(chunk)
        self.peak, self.level = max(self.peak, peak), peak / 32768
        header.dwFlags &= ~_WHDR_DONE

    def _collect(self, winmm, handle, buffers, headers):
        import ctypes
        try:
            while not self.halt.is_set() and self.seconds < self.max_seconds:
                for buffer, header in zip(buffers, headers):
                    if header.dwFlags & _WHDR_DONE:
                        self._take(buffer, header)
                        winmm.waveInAddBuffer(handle, ctypes.byref(header), ctypes.sizeof(header))
                time.sleep(0.02)
            winmm.waveInReset(handle)          # 交回所有缓冲，已录的那部分也收进来
            for buffer, header in zip(buffers, headers):
                if header.dwFlags & _WHDR_DONE and header.dwBytesRecorded:
                    self._take(buffer, header)
                winmm.waveInUnprepareHeader(handle, ctypes.byref(header), ctypes.sizeof(header))
        except OSError as error:
            self.error = str(error) or '录音中断'
        finally:
            winmm.waveInClose(handle)

    def stop(self):
        self.halt.set()
        if self.thread is not None:
            self.thread.join(timeout=2)
        return wav_bytes(self.pcm), self.peak
