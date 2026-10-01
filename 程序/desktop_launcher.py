"""桌面应用唯一启动适配器。

将 Tk 根窗口的启动从各个 UI 页面模块中移出，页面模块可被嵌入或测试，
不会为 ``__main__`` 反向导入整个桌面壳。
"""
from __future__ import annotations

import hash_backend
hash_backend.install()
import tkinter as tk


def launch():
    from desktop import Desktop
    window = tk.Tk()
    Desktop(window)
    window.mainloop()
