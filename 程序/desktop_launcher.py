"""桌面应用唯一启动适配器。

将 Tk 根窗口的启动从各个 UI 页面模块中移出，页面模块可被嵌入或测试，
不会为 ``__main__`` 反向导入整个桌面壳。
"""
from __future__ import annotations

import hash_backend
hash_backend.install()
import tkinter as tk
from ui_widgets import notify


def launch():
    from desktop import Desktop
    window = tk.Tk()
    def report_callback_exception(kind, value, trace):
        import diagnostic_capture
        try:
            diagnostic_capture.record_crash(value, trace)
        finally:
            try:
                window.after_idle(lambda: notify(window, '发生未处理错误，详情已写入 启动错误.log。', level='error', title='启动错误'))
            except tk.TclError:
                pass
    window.report_callback_exception = report_callback_exception
    Desktop(window)
    window.mainloop()
