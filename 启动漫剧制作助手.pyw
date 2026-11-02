import os,sys,traceback
from pathlib import Path
root=Path(__file__).resolve().parent
os.chdir(root)
# 第 34 期第 10 条：hashlib 默认会连带 import _hashlib（OpenSSL），把 libcrypto-3.dll
# 常驻进内存（实测主界面工作集 +4 MB）。程序只用 sha256／sha1／md5，本版解释器有内置实现，
# 所以赶在下面那句 import hashlib 之前先切过去；切换失败会自动退回原样。
sys.path.insert(0,str(root/'程序'))
import hash_backend
from app_metadata import APP_NAME
hash_backend.install()
import app_logging
app_logging.install(crash_sink=lambda exc,trace:__import__('diagnostic_capture').record_crash(exc,trace))
try:
    import ctypes
    import hashlib
    from ctypes import wintypes
    mutex_name='Local\\DramaStudio_'+hashlib.sha256(str(root).encode()).hexdigest()[:16]
    kernel=ctypes.windll.kernel32
    kernel.CreateMutexW.argtypes=[ctypes.c_void_p,wintypes.BOOL,wintypes.LPCWSTR]
    kernel.CreateMutexW.restype=ctypes.c_void_p
    kernel.CreateEventW.argtypes=[ctypes.c_void_p,wintypes.BOOL,wintypes.BOOL,wintypes.LPCWSTR]
    kernel.CreateEventW.restype=ctypes.c_void_p
    kernel.SetEvent.argtypes=[wintypes.HANDLE]
    kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    mutex=kernel.CreateMutexW(None,False,mutex_name)
    existing=kernel.GetLastError()==183
    activation=kernel.CreateEventW(None,False,False,mutex_name+'_activate')
    if not mutex or not activation:raise ctypes.WinError()
    if existing:
        kernel.SetEvent(activation)
        kernel.CloseHandle(activation);kernel.CloseHandle(mutex)
        sys.exit(0)
    program=root/'程序'
    sys.path.insert(0,str(program))
    os.chdir(program)
    # 任务栏身份必须在第一个窗口创建前设好：窗口建出来后再设无效，会一直归在 pythonw.exe 名下，
    # 固定到任务栏后就变成 Python 图标（与快捷方式上写的同一个 ID 才对得上）。
    import app_icon
    app_icon.set_app_id()
    import tkinter as tk
    window=tk.Tk();window.attributes('-alpha',0)
    # 启动画面出现时任务栏按钮就已在了：图标要在它之前挂上（default= 让之后的子窗口也沿用）。
    app_icon.apply(window)
    app_logging.install(window)
    # 主窗口在加载完成前一直透明（ui_theme 摆位置时也不显形），由启动画面整块盖住。
    window._drama_hold_alpha=True
    import platform_tools
    def expected_rect():
        # 直接复用 ui_theme 首次摆放主窗口的尺寸规则并居中；改默认尺寸时启动画面跟着变，不会揭开前突然放大。
        from ui_theme import main_window_size
        area=platform_tools.work_area() or (0,0,window.winfo_screenwidth(),window.winfo_screenheight())
        left,top,right,bottom=area
        width,height=main_window_size(right-left,bottom-top)
        x,y=left+(right-left-width)//2,top+(bottom-top-height)//2
        # Tk 的 +x+y 定的是外框左上角，只有宽高要加上标题栏与边框。
        _,_,outer_w,outer_h=platform_tools.outer_rect_for_client(x,y,width,height)
        return (x,y,outer_w,outer_h)
    try:
        from ui_widgets import Splash
        splash=Splash(window,expected_rect())
        def record_splash(marks):
            import diagnostic_capture
            for key in ('ready','total'):
                if key in marks:diagnostic_capture.record_startup_timing('splash_'+key,marks[key])
        splash.on_finish=record_splash
    except Exception:
        splash=None
    def step(index):
        if splash:splash.step(index)
    from desktop import Desktop
    step(1)
    desk=Desktop(window,root=program,require_login=True)
    step(2)
    def reveal():
        window._drama_hold_alpha=False
        # 揭开前把挂起的布局和重绘一次做完，避免透明转不透明的瞬间露出空白底色。
        window.update_idletasks()
        window.attributes('-alpha',1);window.lift();window.focus_force()
    def loaded():
        # 未登录时登录闸已盖满主窗口，首帧启动要等登录后才开始：直接揭开，让用户看到登录页。
        if getattr(desk,'login_gate_active',False):return True
        # 首帧完成、今日项目页与剧本准备整页都在启动画面后建好才揭开（R1413 先揭外壳的做法会白屏）。
        if not getattr(window,'_desktop_first_paint_complete',False):return False
        if getattr(window,'_desktop_loading_project',False):return False
        # 剧本准备整页在启动画面后面建完才揭开；只等外壳会让用户看到白屏。
        return (getattr(desk,'_startup_project_page_job',None) is None
                and getattr(desk,'_startup_script_build_job',None) is None)
    def track():
        try:return platform_tools.window_outer_rect(int(window.wm_frame(),16))
        except (tk.TclError,ValueError):return None
    if splash:splash.wait(loaded,reveal,track=track)
    else:reveal()
    def activate_existing():
        if kernel.WaitForSingleObject(activation,0)==0:
            window.deiconify();window.attributes('-alpha',1);window.lift()
            modal=window.grab_current()
            target=modal.winfo_toplevel() if modal else window
            target.deiconify();target.attributes('-alpha',1);target.lift()
            target.attributes('-topmost',True);target.focus_force()
            def release_topmost():
                if target.winfo_exists():target.attributes('-topmost',False)
            window.after(250,release_topmost)
        window.after(200,activate_existing)
    window.after(200,activate_existing)
    try:window.mainloop()
    finally:
        kernel.CloseHandle(activation);kernel.CloseHandle(mutex)
except Exception:
    import time;from app_metadata import VERSION
    log=root/'启动错误.log'
    # 追加而非覆盖，并带时间／版本／解释器，反复失败时能看出何时开始、是否同一原因（保留最近约 64KB）。
    try:old=log.read_text(encoding='utf-8',errors='replace')[-65536:]
    except OSError:old=''
    header=chr(10)+'===== '+time.strftime('%Y-%m-%d %H:%M:%S')+' '+VERSION+' Python '+sys.version.split()[0]+' ====='+chr(10)
    log.write_text(old+header+traceback.format_exc(),encoding='utf-8')
    import ctypes
    ctypes.windll.user32.MessageBoxW(0,'启动失败，详情已保存到：'+str(log),APP_NAME,16)
