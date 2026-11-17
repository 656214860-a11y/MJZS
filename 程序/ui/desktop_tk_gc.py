"""Tk 对象的回收护栏（从 desktop 原样迁出，R1622）。

组合框只读保护、Tcl async handler 的解释器句柄保留、worker 线程里被回收的 Tk 对象排队到主线程释放。
模块级状态 _PENDING_TK_GC／_KEEP_APPS 随迁，desktop 按原名转回（同一对象，不复制）。
"""
import infra.app_logging as app_logging
import threading
import tkinter as tk


_PENDING_TK_GC = []        # worker 线程里被回收的 Tk 对象，等主线程释放

_KEEP_APPS = []            # 解释器句柄：Tcl 的 async handler 只能在主线程析构（否则进程直接中止）


def protect_readonly_combobox(win):
    """只读下拉框不再被滚轮改选。

    Tk 8.6 的 TCombobox <MouseWheel> 绑定会调用 ttk::combobox::Scroll 直接换选项；
    落在只读下拉框上时表现为「滚轮滑过选择分镜，文件被切换，整页重建抖动」。
    这里给 ttk::combobox::Scroll 加一层只读／禁用判断，全局生效，可编辑下拉框不受影响。
    """
    try:
        # 注意：Tcl 的 0/1 是字符串，'0' 在 Python 里为真，必须显式比较。
        if win.tk.eval('info exists ::dramaComboWheelGuard')=='1':return
        if not win.tk.eval('info commands ::ttk::combobox::Scroll'):return
        # 改名必须留在同一命名空间：原过程内部调用 SelectEntry 等非限定名命令。
        win.tk.eval('rename ::ttk::combobox::Scroll ::ttk::combobox::ScrollOriginal')
        # Tk 8.6 调 Scroll cb dir，Tk 9 调 Scroll cb dir factor；用可变参数原样转发，两个版本都认。
        win.tk.eval('proc ::ttk::combobox::Scroll {cb args} {'
                    ' if {[$cb instate readonly] || [$cb instate disabled]} { return };'
                    ' ::ttk::combobox::ScrollOriginal $cb {*}$args }')
        win.tk.eval('set ::dramaComboWheelGuard 1')
    except Exception:app_logging.swallowed()


def _pin_tk_app():
    """把每个 Tk 解释器都留在进程里。

    Tcl 的 async handler 只能在创建它的线程里析构，否则 Tcl 直接 Tcl_Panic 中止整个进程
    （Tcl_AsyncDelete: async handler deleted by the wrong thread）。解释器句柄是 C 层对象，
    按引用计数析构，加不了 __del__ 守卫；worker 线程里的一次 GC 就可能把「主线程建的窗口对象环」
    连同解释器一起回收掉，唯一的办法是自己拿住引用。
    """
    try:
        import _tkinter
        if getattr(_tkinter,'_dramaPinned',False):return
        original=_tkinter.create
        def create(*args,**kwargs):
            app=original(*args,**kwargs)
            _KEEP_APPS.append(app)
            return app
        _tkinter.create=create
        _tkinter._dramaPinned=True
    except Exception:app_logging.swallowed()


def protect_tk_gc(win=None):
    """Tk 对象只在界面线程里释放。

    tkinter 里只有三个类型会在 __del__ 里调 Tcl 释放自己的资源：Variable、Image（PhotoImage）、
    font.Font。对象若在 worker 线程被 GC 回收，这次 Tcl 调用就跨线程跑，轻则刷
    RuntimeError: main thread is not in main loop，重则与正在 update() 的界面线程互相等待而卡死
    （实测：无人值守收尾阶段在 worker 里分配对象时，复选框图标与字体对象都会被回收）。

    所以这里做四件事：
    1) 给这三个 __del__ 加线程守卫：非主线程不调 Tcl；
    2) 被拦下的对象交给 _PENDING_TK_GC 暂存、由主线程的 drain_tk_gc() 真正释放——顺带让它所在的
       对象环整体活到主线程。若就地释放，环里的 Tkapp 会在 worker 里析构，Tcl 直接
       Tcl_AsyncDelete 中止整个进程；
    3) 记下解释器句柄：Tkapp 的析构只能在主线程发生；
    4) 把所有 Tk 解释器都留在进程里（见 _pin_tk_app）——否则 worker 里的一次 GC 就足以中止进程。
    幂等（各类上的 _dramaGuarded、模块上的 _dramaPinned）。
    """
    _pin_tk_app()
    try:
        import threading
        import tkinter as tk
        from tkinter import font as tkfont
        if win is not None and getattr(win,'tk',None) is not None:
            _KEEP_APPS.append(win.tk)
        for cls in (tk.Variable,tk.Image,tkfont.Font):
            if getattr(cls,'_dramaGuarded',False):continue
            original=getattr(cls,'__del__',None)
            if original is None:continue
            def guarded(self,_original=original):
                if threading.current_thread() is not threading.main_thread():
                    app=getattr(self,'tk',None) or getattr(self,'_tk',None)
                    if app is not None and not any(item is app for item in _KEEP_APPS):
                        _KEEP_APPS.append(app)
                    _PENDING_TK_GC.append(self)
                    return
                _original(self)
            cls.__del__=guarded
            cls._dramaGuarded=True
    except Exception:app_logging.swallowed()


def drain_tk_gc(limit=64):
    """主线程心跳里调用：释放 worker 线程回收到的 Tk 对象（每轮最多 64 个，不拖慢界面）。"""
    try:
        for _ in range(limit):
            if not _PENDING_TK_GC:break
            _PENDING_TK_GC.pop()
    except Exception:app_logging.swallowed()
