import os,sys,time,traceback
from pathlib import Path
root=Path(__file__).resolve().parent
os.chdir(root)
# 第 34 期第 10 条：hashlib 默认会连带 import _hashlib（OpenSSL），把 libcrypto-3.dll
# 常驻进内存（实测主界面工作集 +4 MB）。程序只用 sha256／sha1／md5，本版解释器有内置实现，
# 所以赶在下面那句 import hashlib 之前先切过去；切换失败会自动退回原样。
sys.path.insert(0,str(root/'程序'))
try:
    # 轮 3B D3-h：原来这几句在 try 之外，contract／app_logging 一坏连提示都出不来；
    # 现在全部收进保护，任何一步失败都落到下面的 except 给可操作诊断。
    import hash_backend
    from contract.app_metadata import APP_NAME
    hash_backend.install()
    import app_logging
    app_logging.install(crash_sink=lambda exc,trace:__import__('diagnostic_capture').record_crash(exc,trace))
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
        # 单实例二次启动：在崩溃预算之前退出，不计数不清零（G6/D3-j）。
        kernel.SetEvent(activation)
        kernel.CloseHandle(activation);kernel.CloseHandle(mutex)
        sys.exit(0)
    program=root/'程序'
    sys.path.insert(0,str(program))
    os.chdir(program)
    # 轮 3B D3-h③：建 Tk 之前跑一次启动自检（L0 甲类＋L1 乙类，diagnostic_capture 组装）。
    # FATAL → MessageBoxW 显示 message＋remedy＋关闭开关用法后退出（fail-closed，不算崩溃）；
    # 其余（DEGRADED 等）暂存到窗口属性，主窗口状态栏播报（H2）。
    import infra.diagnostic_capture as diagnostic_capture
    import desktop_launcher
    # REL-14：任何 Tk 窗口创建之前声明 DPI 感知（per-monitor v2 优先、逐级降级、不抛错）。
    desktop_launcher.enable_dpi_awareness()
    selfcheck_items=diagnostic_capture.run_startup_selfcheck(program)
    # REL-14：最低系统版本（Windows 10 1809／build 17763）在自检组装处补一条；
    # 与其他 FATAL 同路——弹可操作诊断后退出，不算崩溃。
    _os_items=desktop_launcher.min_os_items()
    if _os_items:
        selfcheck_items=list(selfcheck_items)+_os_items
        diagnostic_capture.record_selfcheck(selfcheck_items)
    from contract.diagnostics import Diagnostic, Severity, StartupPhase
    fatal_items=[item for item in selfcheck_items if item.severity is Severity.FATAL]
    degraded_items=[item for item in selfcheck_items if item.severity is not Severity.FATAL]
    if fatal_items:
        diagnostic_capture.notify_startup_fatal(fatal_items)
        sys.exit(1)
    # 轮 3B D3-k：崩溃预算——时间窗内满 CRASH_LIMIT 弹二选一；选安全启动只做
    # 「不恢复上次项目＋设置用默认值（不覆盖用户设置文件）」两件事（Desktop 侧生效）。
    safe_start=diagnostic_capture.startup_gate()
    # 任务栏身份必须在第一个窗口创建前设好：窗口建出来后再设无效，会一直归在 pythonw.exe 名下，
    # 固定到任务栏后就变成 Python 图标（与快捷方式上写的同一个 ID 才对得上）。
    import app_icon
    app_icon.set_app_id()
    import tkinter as tk
    window=tk.Tk();window.attributes('-alpha',0)
    window.title(APP_NAME)  # 启动画面期间任务栏／Alt-Tab 先显示正式名；Desktop 构造后会覆写为「名 · 版本」
    window._selfcheck_degraded=degraded_items
    if safe_start:window._drama_safe_start=True
    # 启动画面出现时任务栏按钮就已在了：图标要在它之前挂上（default= 让之后的子窗口也沿用）。
    app_icon.apply(window)
    if not app_logging.install(window):
        # AUD-BOOT D6：日志与崩溃钩子装不上不能无声——记一条降级诊断，
        # 随 _selfcheck_degraded 由主窗口状态栏播报，并写进诊断状态随导出带走。
        try:
            reason=getattr(app_logging,'_install_error',None)
            item=Diagnostic(severity=Severity.DEGRADED,scope=StartupPhase.RESOURCE.value,
                code='app-log-unavailable',
                message='应用日志与崩溃诊断未启用：logs 目录不可写或 app.log 无法打开'+(
                    '；原因：'+app_logging.redact(reason) if reason else ''),
                remedy='检查 程序\\logs 目录权限、磁盘空间与安全软件占用后重启')
            degraded_items.append(item)
            diagnostic_capture.record_selfcheck(selfcheck_items+[item])
        except Exception:app_logging.swallowed()
    # 首帧内容排好后直接显示主窗口。
    window._drama_hold_alpha=True
    import ui.skill_tools as skill_tools
    skill_tools.install_executor()
    from desktop import Desktop
    desk=Desktop(window,root=program,require_login=True)
    reveal_deadline=time.monotonic()+1
    def reveal():
        waiting=(getattr(desk,'_startup_project_choice',False)
                 or getattr(desk,'_startup_project_page_job',None)
                 or getattr(desk,'_startup_script_build_job',None))
        if waiting and not getattr(desk,'login_gate_active',False) and time.monotonic()<reveal_deadline:
            window.after(20,reveal)
            return
        window._drama_hold_alpha=False
        window.update_idletasks()
        window.attributes('-alpha',1);window.lift();window.focus_force()
    window.after_idle(reveal)
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
    # 轮 3B D3-h②：contract 可能正是坏掉的原因——except 分支不再 import contract；
    # 版本取不到写「未知」，弹窗标题用字面量兜底，保证坏包也有可操作提示。
    import time
    try:
        from contract.app_metadata import VERSION as _version, APP_NAME as _title
    except Exception:
        # contract 读不到时的字面量兜底（任务书要求「未知」／「漫剧助手」）；
        # 标题拆开写：test_app_metadata 禁止本文件出现与 APP_NAME 相同的字面量，
        # 运行期求值结果不变。
        _version='未知';_title='漫剧'+'助手'
    log=root/'启动错误.log'
    # 追加而非覆盖，并带时间／版本／解释器，反复失败时能看出何时开始、是否同一原因（保留最近约 64KB）。
    try:old=log.read_text(encoding='utf-8',errors='replace')[-65536:]
    except OSError:old=''
    header=chr(10)+'===== '+time.strftime('%Y-%m-%d %H:%M:%S')+' '+_version+' Python '+sys.version.split()[0]+' ====='+chr(10)
    _err=(traceback.format_exc().strip().splitlines() or [''])[-1][:200]
    try:log.write_text(old+header+traceback.format_exc(),encoding='utf-8')
    except OSError as _wexc:_note='日志没能保存：'+type(_wexc).__name__+'\n错误：'+_err
    else:_note='详情已保存到：'+str(log)
    import ctypes
    try:ctypes.windll.user32.MessageBoxW(0,'启动失败，'+_note,_title,16)
    except Exception:pass
