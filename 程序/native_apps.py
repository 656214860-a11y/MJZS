"""Open the user's installed media apps; never replace them with browser tabs."""
import csv
import io
import json
import os
import subprocess
import threading
import time
from pathlib import Path
from contract.platform_tools import hidden_console_flags, launch_windows_app, require_windows

_launch_lock = threading.Lock()
_blender_process = None


def open_comfy(settings=None):
    from comfy_runtime import open_comfy as launch
    return launch(settings)


def comfy_server_pids():
    """跑着 ComfyUI 服务的那几个 python 进程号。

    第 65 期任务 1：Comfy Desktop 起来的服务其实是 `.venv/Scripts/python.exe -s ComfyUI/main.py`，
    「Comfy Desktop.exe／ComfyUI.exe」这两颗镜像一个都盖不到它——用户按「强制关闭 ComfyUI」
    却关不掉，正是这个原因。这里按命令行认人（既要含 ComfyUI 又要含 main.py），
    绝不按「凡是 python 就杀」（助手自己也是 python）。
    """
    require_windows('ComfyUI 进程检测')
    script=('Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and '
            '$_.CommandLine -match "ComfyUI" -and $_.CommandLine -match "main[.]py" } | '
            'ForEach-Object { $_.ProcessId }')
    try:
        result=subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',script],
                              capture_output=True,timeout=20,creationflags=hidden_console_flags())
    except (OSError,subprocess.SubprocessError):
        return []
    pids=[]
    for token in result.stdout.decode('utf-8','replace').split():
        if token.strip().isdigit():pids.append(int(token))
    mine=os.getpid()
    return [pid for pid in pids if pid!=mine]


def force_close_comfy(settings=None):
    require_windows('强制关闭 ComfyUI')
    from integrations import comfy_executable
    exe = comfy_executable(settings or {})
    images = []
    if exe is not None:
        images.append(exe.name)
    for name in ('Comfy Desktop.exe', 'ComfyUI.exe'):
        if name not in images:
            images.append(name)
    killed = []
    for image in images:
        result = subprocess.run(
            ['taskkill', '/IM', image, '/F', '/T'],
            capture_output=True, timeout=10, creationflags=hidden_console_flags())
        if result.returncode == 0:
            killed.append(image)
    for pid in comfy_server_pids():
        result = subprocess.run(
            ['taskkill', '/PID', str(pid), '/F', '/T'],
            capture_output=True, timeout=10, creationflags=hidden_console_flags())
        if result.returncode == 0:
            killed.append('ComfyUI 服务进程 '+str(pid))
    if not killed:
        raise ValueError('未发现正在运行的 ComfyUI 进程（'+'、'.join(images)+'）。请先点击“桌面打开 ComfyUI”启动程序。')
    return '已强制关闭 ComfyUI：'+'、'.join(killed)


def _blender_window_running():
    require_windows('Blender 窗口检测')
    result = subprocess.run(
        ['tasklist', '/FI', 'IMAGENAME eq blender.exe', '/V', '/FO', 'CSV', '/NH'],
        capture_output=True, timeout=5, creationflags=hidden_console_flags())
    if result.returncode:
        return False
    for row in csv.reader(io.StringIO(result.stdout.decode('mbcs', errors='replace'))):
        if row and row[0].lower() == 'blender.exe' and len(row) >= 9:
            title = row[-1].strip().casefold()
            if title and title not in ('n/a', '暂缺', '不适用', '无'):
                return True
    return False


def open_blender(project_file=None):
    from ui.white_model import find_blender
    # 每次点击都重新检测：用户可能在程序启动后才安装 Blender（扫描一次约 12 毫秒）。
    exe = find_blender(refresh=True)
    if exe is None:
        raise ValueError('未找到本地 Blender，请检查 Blender 程序位置')
    project_file = Path(project_file).resolve() if project_file else None
    if project_file and (project_file.suffix.lower() != '.blend' or not project_file.is_file()):
        raise ValueError('Blender 工程不存在，请先完成工程制作')
    global _blender_process
    with _launch_lock:
        if project_file is None:
            if _blender_process is not None and _blender_process.poll() is None:
                return exe
            try:
                if _blender_window_running():
                    return exe
            except (OSError, subprocess.TimeoutExpired):
                pass
        args = [str(exe)] + ([str(project_file)] if project_file else [])
        # Intentionally visible: the user wants to inspect and edit the scene.
        _blender_process = launch_windows_app(exe, 'Blender', args=args, cwd=exe.parent)
    return exe


def wait_comfy(url,report=None,timeout=90,cancelled=None):
    from comfy_runtime import wait_comfy as wait
    return wait(url, report, timeout, cancelled)
