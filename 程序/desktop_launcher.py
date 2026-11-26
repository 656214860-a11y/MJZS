"""桌面应用唯一启动适配器。

将 Tk 根窗口的启动从各个 UI 页面模块中移出，页面模块可被嵌入或测试，
不会为 ``__main__`` 反向导入整个桌面壳。

轮 3B D3-i：``launch()`` 复用与 ``启动漫剧制作助手.pyw`` 同一个自检入口
（``infra.diagnostic_capture.run_startup_selfcheck``），不复制逻辑；
FATAL → MessageBoxW 后 ``SystemExit``，DEGRADED 暂存到窗口属性由桌面状态栏播报。
``desktop.py`` 的 ``__main__`` 直接构造 ``Desktop``、``app.py`` 的 ``__main__``
以 ``selfcheck=False`` 调本函数——两个调试入口都不跑自检（G4）。

REL-14：``enable_dpi_awareness()`` 必须在任何 Tk 窗口创建前调用（仓库根
``启动漫剧制作助手.pyw`` 与 ``launch()`` 都已接线）；``min_os_items()``
供启动器自检组装最低系统版本诊断（Windows 10 1809／build 17763 起）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import infra.app_logging as app_logging
import infra.hash_backend as hash_backend
hash_backend.install()
# REF-L5-1：tkinter 与 ui_widgets 不在顶层导入——DPI 声明、min_os_items、run_preflight
# 的预检段都不需要窗口；用到弹窗／主窗口的函数在用点内延迟导入，import 本模块保持轻量。


# ── REL-14：DPI 感知与最低系统版本 ─────────────────────────────────
# 进程级 DPI 感知声明必须早于任何 Tk 窗口创建；窗口级跨屏重排监听在
# responsive_ui.watch_dpi_change，由 desktop.py 接到既有 _layout_all 重排。

_DPI_CTX_PER_MONITOR_V2 = -4      # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
_SHCORE_PER_MONITOR = 2          # PROCESS_PER_MONITOR_DPI_AWARE
_SHCORE_SYSTEM = 1               # PROCESS_SYSTEM_DPI_AWARE

# 需求规格 §5.4 的最低系统版本：Windows 10 1809（build 17763）。
_MIN_OS_MAJOR = 10
_MIN_OS_BUILD = 17763

_dpi_awareness = {'done': False, 'level': None}


def enable_dpi_awareness():
    """声明进程 DPI 感知：per-monitor v2 优先，失败逐级降级，任何一步失败都不抛错。

    返回实际生效的级别名（``'per_monitor_v2'``／``'per_monitor'``／``'system'``）；
    全部失败返回 ``None``——此时 Windows 按系统 DPI 位图拉伸，应用照常启动。
    幂等：重复调用是空操作，直接返回首次结果；必须在任何 Tk 窗口创建前调用。
    """
    if _dpi_awareness['done']:
        return _dpi_awareness['level']
    _dpi_awareness['done'] = True
    level = None
    if os.name == 'nt':
        try:
            import ctypes
            from ctypes import wintypes
            # 第一级：SetProcessDpiAwarenessContext(PER_MONITOR_AWARE_V2)，Win10 1703+。
            try:
                context = ctypes.windll.user32.SetProcessDpiAwarenessContext
                context.restype = wintypes.BOOL
                if context(ctypes.c_void_p(_DPI_CTX_PER_MONITOR_V2)):
                    level = 'per_monitor_v2'
            except Exception:
                app_logging.swallowed()
            if level is None:
                # 第二级：shcore.SetProcessDpiAwareness——2＝per-monitor，1＝system（Win8.1+）。
                try:
                    aware = ctypes.windll.shcore.SetProcessDpiAwareness
                    aware.argtypes = [ctypes.c_int]
                    aware.restype = ctypes.c_long
                    if aware(_SHCORE_PER_MONITOR) == 0:
                        level = 'per_monitor'
                    if level is None and aware(_SHCORE_SYSTEM) == 0:
                        level = 'system'
                except Exception:
                    app_logging.swallowed()
            if level is None:
                # 第三级兜底：user32.SetProcessDPIAware（Vista+，等价 system 级感知）。
                try:
                    legacy = ctypes.windll.user32.SetProcessDPIAware
                    legacy.restype = wintypes.BOOL
                    if legacy():
                        level = 'system'
                except Exception:
                    app_logging.swallowed()
        except Exception:
            app_logging.swallowed()
    _dpi_awareness['level'] = level
    return level


def min_os_items():
    """最低系统版本自检：低于 Windows 10 1809（build 17763）返回一条 FATAL 诊断。

    非 Windows、版本读不出来或达到下限都返回空列表——自检组装不单独挡启动；
    返回的 FATAL 由启动器与其他 FATAL 同路走 ``notify_startup_fatal`` 后退出。
    """
    if os.name != 'nt':
        return []
    try:
        version = sys.getwindowsversion()
        major = int(getattr(version, 'major', 0) or 0)
        build = int(getattr(version, 'build', 0) or 0)
    except Exception:
        return []
    if (major, build) >= (_MIN_OS_MAJOR, _MIN_OS_BUILD):
        return []
    try:
        from contract.diagnostics import Diagnostic, Severity, StartupPhase
        return [Diagnostic(
            severity=Severity.FATAL,
            scope=StartupPhase.CONFIG.value,
            code='os-below-minimum',
            message='当前 Windows 版本（%d.%d build %d）低于最低要求 Windows 10 1809' % (
                major, int(getattr(version, 'minor', 0) or 0), build),
            remedy='请升级到 Windows 10 1809（build 17763）或更高版本（含 Windows 11）后再启动')]
    except Exception:
        return []


def entry_dialog(parent, title, text, primary='确定', secondary=None):
    """REQ-UI-L5-1：应用入口提示窗——单列说明文本＋一个强调色主按钮＋可选文字式次按钮。

    主按钮判「是」（返回 ``True``），次按钮／Esc／窗口 X 判「否」；
    ``secondary=None`` 时只摆主按钮（纯告知）。阻塞到用户选择或关窗。
    """
    from ui_widgets import (BaseDialog, DescriptionBlock, PrimaryButton,
                            SecondaryButton, DIALOG_ACTION_GAP, SPACING)
    win = BaseDialog(parent, str(title), modal=False)
    DescriptionBlock(win.content, text=str(text)).pack(fill='x')
    result = {'ok': False}

    def yes():
        result['ok'] = True
        win.close()

    def no():
        win.close()

    if secondary is not None:
        SecondaryButton(win.actions, text=str(secondary), command=no,
                        style='Tokens.Text.TButton').pack(
            side='right', padx=(DIALOG_ACTION_GAP, SPACING['none']))
    PrimaryButton(win.actions, text=str(primary), command=yes).pack(
        side='right', padx=(DIALOG_ACTION_GAP, SPACING['none']))
    win.bind('<Escape>', lambda _event: no())
    win.wait_window()
    return bool(result['ok'])


def entry_confirm(text, title, flags=0, parent=None):
    """``diagnostic_capture.confirm_safe_start`` 的 ask 实现：入口弹窗，按 Win32 结果码返回。

    主按钮（安全启动）→ ``_IDYES``；次按钮（正常启动）／Esc／关闭 → 0（按「否」处理）。
    ``flags`` 保留 ``MessageBoxW`` 调用形态，按钮与文案由本窗统一布局接管；
    ``parent=None`` 说明 Tk 尚未起，先开一扇隐藏根窗当宿主。
    """
    import tkinter as tk
    owner = parent
    if owner is None:
        owner = tk.Tk()
        owner.withdraw()
    try:
        ok = entry_dialog(owner, title, text, primary='安全启动', secondary='正常启动')
    finally:
        if parent is None:
            owner.destroy()
    # Win32 MessageBoxW 结果码：IDYES＝6（confirm_safe_start 只认这个值）。
    return 6 if ok else 0


def _entry_notify(items):
    """FATAL 自检的入口提示：同一路入口弹窗（单列诊断文本＋一个「退出」主按钮），建 Tk 之前可用。"""
    import tkinter as tk
    import infra.diagnostic_capture as diagnostic_capture
    from contract.app_metadata import APP_NAME
    root = tk.Tk()
    root.withdraw()
    try:
        entry_dialog(root, str(APP_NAME or '漫剧助手'),
                     diagnostic_capture.fatal_diagnostics_text(items), primary='退出')
    finally:
        root.destroy()


def run_preflight(program):
    """启动预检共用入口：``launch()`` 与仓库根 ``启动漫剧制作助手.pyw`` 同一路（REF-L5-1）。

    顺序：``run_startup_selfcheck`` → ``min_os_items``（有则补记 ``record_selfcheck``）
    → FATAL 走统一入口弹窗（文案首行 E-START-SELFCHECK）后 ``SystemExit(1)``
    → ``startup_gate(ask=entry_confirm)`` 崩溃预算二选一。
    返回 ``(degraded_items, safe_start)``：DEGRADED 项由调用方挂到窗口属性交状态栏播报。
    """
    import infra.diagnostic_capture as diagnostic_capture
    from contract.diagnostics import Severity
    items = diagnostic_capture.run_startup_selfcheck(Path(program))
    os_items = min_os_items()
    if os_items:
        items = list(items) + os_items
        diagnostic_capture.record_selfcheck(items)
    fatal_items = [item for item in items if item.severity is Severity.FATAL]
    degraded_items = [item for item in items if item.severity is not Severity.FATAL]
    if fatal_items:
        # fail-closed：给可操作诊断后退出；这不是崩溃，不写崩溃预算。
        # 入口弹窗走统一布局（REQ-UI-L5-1）；Tk 起不来时回退原来的 MessageBoxW。
        try:
            _entry_notify(fatal_items)
        except Exception:
            diagnostic_capture.notify_startup_fatal(fatal_items)
        raise SystemExit(1)
    return degraded_items, diagnostic_capture.startup_gate(ask=entry_confirm)


def launch(selfcheck=True):
    """启动桌面主窗口；``selfcheck=False`` 供调试 ``__main__`` 入口跳过启动自检与崩溃预算。"""
    import tkinter as tk
    enable_dpi_awareness()
    degraded_items = []
    safe_start = False
    if selfcheck:
        degraded_items, safe_start = run_preflight(Path(__file__).resolve().parent)
    # L5 组合根：把 L4 的 SKILL 工具适配器注入 L3；编排器本身不反向依赖 UI。
    import ui.skill_tools as skill_tools
    skill_tools.install_executor()
    from desktop import Desktop
    window = tk.Tk()
    window._selfcheck_degraded = degraded_items
    if safe_start:
        window._drama_safe_start = True
    def report_callback_exception(kind, value, trace):
        import infra.diagnostic_capture as diagnostic_capture
        from ui_widgets import notify
        try:
            diagnostic_capture.record_crash(value, trace)
        finally:
            try:
                window.after_idle(lambda: notify(window, '发生未处理错误，详情已写入 启动错误.log。', level='error', title='启动错误'))
            except tk.TclError:
                pass
    window.report_callback_exception = report_callback_exception
    Desktop(window, require_login=True)
    window.mainloop()
