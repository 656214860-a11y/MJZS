# -*- coding: utf-8 -*-
"""在隐藏的 Windows 桌面上运行命令：Tk 窗口出现在不可见的桌面里，不会弹到用户屏幕上，也不抢焦点。

用法（用仓库自带解释器启动本脚本）：
  python gui_hidden.py <输出文件> <工作目录> -- <命令> [参数…]
  python gui_hidden.py --probe     # 秒级自检：能否创建隐藏桌面（0=可以，3=不行）

输出（stdout＋stderr）写入输出文件，退出码即被运行命令的退出码；超时用 GUI_HIDDEN_TIMEOUT 秒（默认 3600）。
实现：CreateDesktopW 建一个临时桌面，CreateProcessW 的 STARTUPINFO.lpDesktop 指向它，
子进程继承本进程的环境变量（PYTHONPATH 等照常有效）。几何测量不受影响：窗口是真实映射的，只是不在用户可见的桌面上。

退出码：0=子命令退出码透传；2=参数错误；3=CreateDesktop 失败；4=CreateProcess 失败；124=超时。

R3039 起入库（scripts/），任何工作树/干净检出都随 git 可用；`run_selftests.py`／`smoke_test.py` 自包装
与 `scripts/auto_full_safe.py` 只引用本文件。主工作区旧副本 `工作流任务/gui_hidden.py` 保留作历史，不再被引用。
"""
import ctypes
import msvcrt
import os
import subprocess
import sys
import uuid
from ctypes import wintypes

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
u32 = ctypes.WinDLL("user32", use_last_error=True)

STARTF_USESTDHANDLES = 0x100
CREATE_UNICODE_ENVIRONMENT = 0x400
HANDLE_FLAG_INHERIT = 1
GENERIC_ALL = 0x10000000
INFINITE = 0xFFFFFFFF
WAIT_TIMEOUT = 0x102


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR), ("lpDesktop", wintypes.LPWSTR),
                ("lpTitle", wintypes.LPWSTR), ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD),
                ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD), ("dwXCountChars", wintypes.DWORD),
                ("dwYCountChars", wintypes.DWORD), ("dwFillAttribute", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD), ("lpReserved2", ctypes.c_void_p),
                ("hStdInput", wintypes.HANDLE), ("hStdOutput", wintypes.HANDLE), ("hStdError", wintypes.HANDLE)]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE),
                ("dwProcessId", wintypes.DWORD), ("dwThreadId", wintypes.DWORD)]


u32.CreateDesktopW.restype = wintypes.HANDLE
u32.CreateDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                               wintypes.DWORD, ctypes.c_void_p]
u32.CloseDesktop.argtypes = [wintypes.HANDLE]
k32.CreateProcessW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p, ctypes.c_void_p, wintypes.BOOL,
                               wintypes.DWORD, ctypes.c_void_p, wintypes.LPCWSTR, ctypes.POINTER(STARTUPINFOW),
                               ctypes.POINTER(PROCESS_INFORMATION)]
k32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
k32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
k32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
k32.CloseHandle.argtypes = [wintypes.HANDLE]
k32.SetHandleInformation.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD]


def _configure_stdio_utf8():
    for stream in (sys.stdout, sys.stderr):
        if stream is None:
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError, TypeError):
            pass


def main(argv):
    _configure_stdio_utf8()
    if argv[1:2] == ['--probe']:
        name = "manju_probe_" + uuid.uuid4().hex[:8]
        desktop = u32.CreateDesktopW(name, None, None, 0, GENERIC_ALL, None)
        if not desktop:
            print("CreateDesktop 失败", ctypes.get_last_error())
            return 3
        u32.CloseDesktop(desktop)
        print("隐藏桌面探测 OK")
        return 0
    if "--" not in argv or len(argv) < 5:
        print(__doc__)
        return 2
    sep = argv.index("--")
    out_path, cwd, cmd = argv[1], argv[2], argv[sep + 1:]
    timeout = int(os.environ.get("GUI_HIDDEN_TIMEOUT", "3600")) * 1000
    name = "manju_hidden_" + uuid.uuid4().hex[:8]
    desktop = u32.CreateDesktopW(name, None, None, 0, GENERIC_ALL, None)
    if not desktop:
        print("CreateDesktop 失败", ctypes.get_last_error())
        return 3
    out = open(out_path, "wb")
    handle = msvcrt.get_osfhandle(out.fileno())
    k32.SetHandleInformation(handle, HANDLE_FLAG_INHERIT, HANDLE_FLAG_INHERIT)
    nul = open(os.devnull, "rb")
    nul_handle = msvcrt.get_osfhandle(nul.fileno())
    k32.SetHandleInformation(nul_handle, HANDLE_FLAG_INHERIT, HANDLE_FLAG_INHERIT)
    si = STARTUPINFOW()
    si.cb = ctypes.sizeof(si)
    si.lpDesktop = "WinSta0\\" + name
    si.dwFlags = STARTF_USESTDHANDLES
    si.hStdInput, si.hStdOutput, si.hStdError = nul_handle, handle, handle
    pi = PROCESS_INFORMATION()
    cmdline = ctypes.create_unicode_buffer(subprocess.list2cmdline(cmd))
    prev_io = os.environ.get("PYTHONIOENCODING")
    prev_utf8 = os.environ.get("PYTHONUTF8")
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PYTHONUTF8"] = "1"
    try:
        ok = k32.CreateProcessW(None, cmdline, None, None, True, CREATE_UNICODE_ENVIRONMENT, None, cwd,
                                ctypes.byref(si), ctypes.byref(pi))
    finally:
        if prev_io is None:
            os.environ.pop("PYTHONIOENCODING", None)
        else:
            os.environ["PYTHONIOENCODING"] = prev_io
        if prev_utf8 is None:
            os.environ.pop("PYTHONUTF8", None)
        else:
            os.environ["PYTHONUTF8"] = prev_utf8
    if not ok:
        print("CreateProcess 失败", ctypes.get_last_error())
        u32.CloseDesktop(desktop)
        return 4
    code = 124
    if k32.WaitForSingleObject(pi.hProcess, timeout) == WAIT_TIMEOUT:
        k32.TerminateProcess(pi.hProcess, 124)
    else:
        c = wintypes.DWORD()
        k32.GetExitCodeProcess(pi.hProcess, ctypes.byref(c))
        code = c.value
    k32.CloseHandle(pi.hProcess)
    k32.CloseHandle(pi.hThread)
    out.close()
    nul.close()
    u32.CloseDesktop(desktop)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
