"""Small local-machine adapters with no workflow or UI dependency."""
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import webbrowser
from urllib.parse import urlparse

_TOOL_CACHE = {}


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
    runner = popen or subprocess.Popen
    return runner(command, cwd=None if cwd is None else str(cwd),
                  creationflags=hidden_console_flags(),
                  stdin=stdin, stdout=stdout, stderr=stderr, env=env)


def run_process(command, *, run=None, **kwargs):
    """Run a local host command with the shared hidden-console policy."""
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


def tool_path(name, fallback=''):
    """Return a cached executable path, falling back to an explicit setting.

    只缓存 `which` 的结果：未命中时不把 None 写进缓存，否则先发生的无兜底查询会让
    后续带兜底的调用拿不到明确路径（首帧解码就会把 None 交给 subprocess）。
    """
    if name not in _TOOL_CACHE:
        _TOOL_CACHE[name] = shutil.which(name) or None
    return _TOOL_CACHE[name] or fallback or None


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


def open_https(url, *, timeout=60, data=None, headers=None):
    """唯一出站 HTTP(S) 入口：返回已打开的响应，读取与错误分类留给调用方。

    与 ``run_process`` 同属宿主适配层——出站网络调用集中在此，便于统一超时、代理
    与后续访问闸门策略；``data`` 为 None 时是 GET，否则按请求体发送。
    """
    import urllib.request
    request = urllib.request.Request(str(url), data=data, headers=dict(headers or {}))
    return urllib.request.urlopen(request, timeout=timeout)


def launch_windows_app(executable, feature, *, args=None, cwd=None, env=None, creationflags=0):
    """启动已定位的 Windows 本地程序，并把宿主失败转成可展示提示。

    ``args`` 让本地 CLI 也复用同一个 Windows 宿主边界；未提供时仍只启动
    可执行文件本身，保持桌面应用入口的原有行为。
    """
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
