"""桌面应用唯一启动适配器。

将 Tk 根窗口的启动从各个 UI 页面模块中移出，页面模块可被嵌入或测试，
不会为 ``__main__`` 反向导入整个桌面壳。

轮 3B D3-i：``launch()`` 复用与 ``启动漫剧制作助手.pyw`` 同一个自检入口
（``infra.diagnostic_capture.run_startup_selfcheck``），不复制逻辑；
FATAL → MessageBoxW 后 ``SystemExit``，DEGRADED 暂存到窗口属性由桌面状态栏播报。
``desktop.py`` 的 ``__main__`` 直接构造 ``Desktop``、``app.py`` 的 ``__main__``
以 ``selfcheck=False`` 调本函数——两个调试入口都不跑自检（G4）。
"""
from __future__ import annotations

from pathlib import Path

import infra.hash_backend as hash_backend
hash_backend.install()
import tkinter as tk
from ui_widgets import notify


def launch(selfcheck=True):
    """启动桌面主窗口；``selfcheck=False`` 供调试 ``__main__`` 入口跳过启动自检与崩溃预算。"""
    degraded_items = []
    safe_start = False
    if selfcheck:
        import infra.diagnostic_capture as diagnostic_capture
        from contract.diagnostics import Severity
        program = Path(__file__).resolve().parent
        items = diagnostic_capture.run_startup_selfcheck(program)
        fatal_items = [item for item in items if item.severity is Severity.FATAL]
        degraded_items = [item for item in items if item.severity is not Severity.FATAL]
        if fatal_items:
            # fail-closed：给可操作诊断后退出；这不是崩溃，不写崩溃预算。
            diagnostic_capture.notify_startup_fatal(fatal_items)
            raise SystemExit(1)
        safe_start = diagnostic_capture.startup_gate()
    from desktop import Desktop
    window = tk.Tk()
    window._selfcheck_degraded = degraded_items
    if safe_start:
        window._drama_safe_start = True
    def report_callback_exception(kind, value, trace):
        import infra.diagnostic_capture as diagnostic_capture
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
