"""Open the user's installed media apps; never replace them with browser tabs."""
import csv
import io
import os
import subprocess
import threading
from pathlib import Path
from contract.platform_tools import hidden_console_flags, launch_windows_app, require_windows

_launch_lock = threading.Lock()
_blender_process = None
# I3b（L1 任务书）：L1 不得反向依赖 L4 ui.white_model；Blender 查找器由
# L4/L5 组装点经 register_blender_finder 注入（ui.white_model 导入时自登记）。
# 未注入时 open_blender 返回明确的「未配置」错误，不抛 AttributeError。
_blender_finder = None


def register_blender_finder(finder):
    """登记 Blender 可执行文件查找器，签名同 ui.white_model.find_blender(refresh=...)。"""
    global _blender_finder
    _blender_finder = finder


def open_comfy(settings=None):
    from infra.comfy_runtime import open_comfy as launch
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
    """强制关闭 ComfyUI：只按登记过的进程号与 comfy_server_pids() 认人，不按映像名杀。

    用户自己启动的 Comfy Desktop 窗口、以及 os.startfile 打开的程序都不在登记表里，
    一律不碰；找不到登记进程时提示手动关闭，不猜测映像名批量结束。
    """
    require_windows('强制关闭 ComfyUI')
    from infra import workflow_process_registry
    pids = []
    for pid in comfy_server_pids():
        if pid not in pids:
            pids.append(pid)
    for process in workflow_process_registry.all_processes():
        pid = getattr(process, 'pid', None)
        try:
            pid = int(pid)
        except (TypeError, ValueError):
            continue
        if pid > 0 and pid != os.getpid() and pid not in pids:
            pids.append(pid)
    killed = []
    for pid in pids:
        result = subprocess.run(
            ['taskkill', '/PID', str(pid), '/F', '/T'],
            capture_output=True, timeout=10, creationflags=hidden_console_flags())
        if result.returncode == 0:
            killed.append('进程 ' + str(pid))
    if not killed:
        return '未发现登记在册的 ComfyUI 相关进程；若 Comfy Desktop 窗口仍在，请手动关闭它。'
    return '已强制关闭 ComfyUI：' + '、'.join(killed)


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
    finder = _blender_finder
    if finder is None:
        # 注入点：ui.white_model.find_blender（L4/L5 组装）
        raise ValueError('Blender 查找器未配置：需 L4/L5 组装点注入')
    # 每次点击都重新检测：用户可能在程序启动后才安装 Blender（扫描一次约 12 毫秒）。
    exe = finder(refresh=True)
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
    from infra.comfy_runtime import wait_comfy as wait
    return wait(url, report, timeout, cancelled)
