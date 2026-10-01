import os,sys,traceback
from pathlib import Path
root=Path(__file__).resolve().parent
os.chdir(root)
# 第 34 期第 10 条：hashlib 默认会连带 import _hashlib（OpenSSL），把 libcrypto-3.dll
# 常驻进内存（实测主界面工作集 +4 MB）。程序只用 sha256／sha1／md5，本版解释器有内置实现，
# 所以赶在下面那句 import hashlib 之前先切过去；切换失败会自动退回原样。
sys.path.insert(0,str(root/'程序'))
import hash_backend
hash_backend.install()
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
    import tkinter as tk
    from desktop import Desktop
    window=tk.Tk();Desktop(window,root=program)
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
    log=root/'启动错误.log';log.write_text(traceback.format_exc(),encoding='utf-8')
    import ctypes
    ctypes.windll.user32.MessageBoxW(0,'启动失败，详情已保存到：'+str(log),'漫剧制作助手',16)
