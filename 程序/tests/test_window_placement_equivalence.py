"""ui_theme.install_window_placement 把不依赖闭包的辅助函数提到模块级：HEAD 旧实现原样内嵌。
它会改写全进程的 tk.Toplevel.__init__，新旧实现不能同进程对照，所以各开一个子进程，
跑同一段脚本（主窗、弹窗、带子控件的弹窗、隐藏再显示、定位前就销毁），对照逐步记录与 stderr。"""
import subprocess
import sys
import unittest
from pathlib import Path

from skip_reasons import PLATFORM_TKINTER

LEGACY = 'def install_window_placement(root):\n\n    """Center each window once; leave subsequent user moves alone."""\n\n    import tkinter as tk\n\n    if getattr(root,\'_drama_place_enabled\',False):return\n\n    root._drama_place_enabled=True\n    # Hide new application windows before their first native Map event.\n\n    if not getattr(tk.Toplevel,\'_drama_hidden_init\',False):\n\n        original_init=tk.Toplevel.__init__\n\n        def grab_popup(event,window):\n            # <Map> 会沿 bindtags 冒泡：子 Label／Frame 映射时也会送到\n            # Toplevel 的绑定。只能由窗口自身取得 grab，绝不能让子控件\n            # 把整个应用的输入锁走。\n            if getattr(event,\'widget\',None) is not window:\n                return\n            try:window.grab_set()\n            except tk.TclError:pass\n\n        def release_popup_on_unmap(event,window):\n            # 隐藏以复用的窗口不应继续持有输入；同样只响应自身事件，避免\n            # 子控件卸载时误释放仍可见窗口的 grab。\n            if getattr(event,\'widget\',None) is not window:\n                return\n            try:window.grab_release()\n            except tk.TclError:pass\n\n        def hidden_init(window,*args,**kwargs):\n\n            original_init(window,*args,**kwargs)\n\n            try:rt=window._root()\n\n            except Exception:rt=window.master\n\n            if getattr(rt,\'_drama_place_enabled\',False):\n\n                window.attributes(\'-alpha\',0)\n\n                # patched ``hidden_init`` retains callbacks for the app lifetime;\n                # a one-off lambda can be deleted before a queued Map event runs.\n                def grab_on_own_map(event,w=window):\n                    grab_popup(event,w)\n                def release_on_own_unmap(event,w=window):\n                    release_popup_on_unmap(event,w)\n                window._drama_grab_popup_callback=grab_on_own_map\n                window._drama_release_popup_callback=release_on_own_unmap\n                window.bind(\'<Map>\',grab_on_own_map,add=\'+\')\n                window.bind(\'<Unmap>\',release_on_own_unmap,add=\'+\')\n\n                # 第 8 轮（收口）：弹窗右上角那两颗「最小化 / 最大化」删掉了（用户点名要删）。\n                # 第 65 期任务 5 曾在这一处给每个弹窗长出它们（全程序只此一处接线），第 67 期\n                # 任务 1 又把三虎的云朵框单独摘过；现在这里什么都不长，弹窗只剩系统那颗 ×。\n\n        tk.Toplevel.__init__=hidden_init\n\n        tk.Toplevel._drama_hidden_init=True\n\n    root.attributes(\'-alpha\',0)\n\n    def focus_popup(window):\n\n        """弹窗摆好之后把它点活（第 59 期第 13 条）。\n\n        这些弹窗都是「置顶 ＋ 抓到手里」的（见上面的 grab_popup）：置顶窗在 Windows 上\n\n        不会自动成为活动窗，用户的第一下点击只会被系统当成「点活这扇窗」——按钮于是要\n\n        点两次才生效（用户报的「关闭按钮要点两次」就是这个）。三虎的云朵框早就单独补过\n\n        这一下（pet_cloud 的 show → focus_force），这里把同一件事做给所有居中弹出的窗口。\n\n        """\n\n        try:window.focus_force()\n\n        except Exception:app_logging.swallowed()\n\n    def work_area(window):\n\n        try:\n\n            import ctypes\n\n            from ctypes import wintypes\n\n            class MONITORINFO(ctypes.Structure):\n\n                _fields_=[(\'cbSize\',wintypes.DWORD),(\'rcMonitor\',wintypes.RECT),(\'rcWork\',wintypes.RECT),(\'dwFlags\',wintypes.DWORD)]\n\n            api=ctypes.windll.user32\n\n            api.MonitorFromWindow.argtypes=[wintypes.HWND,wintypes.DWORD]\n\n            api.MonitorFromWindow.restype=wintypes.HANDLE\n\n            api.GetMonitorInfoW.argtypes=[wintypes.HANDLE,ctypes.POINTER(MONITORINFO)]\n\n            info=MONITORINFO();info.cbSize=ctypes.sizeof(info)\n\n            monitor=api.MonitorFromWindow(window.winfo_id(),2)\n\n            if api.GetMonitorInfoW(monitor,ctypes.byref(info)):\n\n                r=info.rcWork;return r.left,r.top,r.right,r.bottom\n\n        except (AttributeError,OSError):pass\n\n        return 0,0,root.winfo_screenwidth(),root.winfo_screenheight()\n\n    def place(window,parent=None):\n\n        if not window.winfo_exists():return\n\n        # 主窗口的宽高由下面的工作区规则直接给出，不必先量自然尺寸；整壳布局只算一遍。\n        if parent is not None:window.update_idletasks()\n\n        left,top,right,bottom=work_area(parent or window)\n\n        width=min(window.winfo_width(),right-left-24)\n\n        height=min(window.winfo_height(),bottom-top-48)\n\n        if parent and not window.overrideredirect():\n            window.transient(parent)\n            # 主窗口仅约束首次尺寸；之后由用户自由缩放，不沿用业务页的固定尺寸。\n            width=min(width,parent.winfo_width())\n            height=min(height,parent.winfo_height())\n            window.resizable(True,True)\n            # 弹窗不再被压到 1×1：未声明也至少保留 240×160 的内容下限。\n            window.minsize(DIALOG_MIN_WIDTH,DIALOG_MIN_HEIGHT)\n            window.maxsize(window.winfo_vrootwidth(),window.winfo_vrootheight())\n\n        if parent is None:\n\n            window.state(\'normal\')\n\n            width,height=main_window_size(right-left,bottom-top)\n\n            minw,minh=window.minsize();window.minsize(min(minw,width),min(minh,height))\n\n        if parent:\n\n            x=parent.winfo_rootx()+(parent.winfo_width()-width)//2\n\n            y=parent.winfo_rooty()+(parent.winfo_height()-height)//2\n\n            if window.overrideredirect():window.transient(parent)\n\n        else:x=left+(right-left-width)//2;y=top+(bottom-top-height)//2\n\n        x=max(left,min(x,right-width));y=max(top,min(y,bottom-height))\n\n        window.geometry(f\'{width}x{height}+{x}+{y}\');window.update_idletasks()\n\n        # 启动画面盖着主窗口时由启动器决定何时显形，这里只摆位置。\n        if not getattr(window,\'_drama_hold_alpha\',False):window.attributes(\'-alpha\',1);window.lift()\n\n        if parent:focus_popup(window)      # 第 59 期第 13 条：弹窗摆好就点活，不留一下“白点”给用户\n\n    def cancel_position_job(window,event=None):\n        """取消该窗口尚未执行的定位回调。\n\n        ``after`` 挂在 Tcl 解释器上而不是控件上；窗口先销毁时，若 Python 闭包没有持有\n        回调 id，Tcl 到时仍会尝试执行已被删除的命令并污染 stderr。回调 id 因此归窗口\n        所有，且只绑定一次自身的 ``<Destroy>``，避免子控件销毁误取消定位。\n        """\n        if event is not None and getattr(event,\'widget\',None) is not window:\n            return\n        job=getattr(window,\'_drama_place_job\',None)\n        if job is not None:\n            try:window.after_cancel(job)\n            except Exception:app_logging.swallowed()\n        window._drama_place_job=None\n\n    def schedule_place(window,parent=None):\n        cancel_position_job(window)\n        if not getattr(window,\'_drama_place_cancel_bound\',False):\n            # Keep the callback on the widget.  Tcl may dispatch a queued Destroy\n            # event after this helper has returned; an unreferenced lambda would\n            # then have been deleted from Tcl before the event is handled.\n            def cancel_position_on_destroy(event, w=window):\n                cancel_position_job(w,event)\n            window._drama_place_destroy_callback=cancel_position_on_destroy\n            window.bind(\'<Destroy>\',cancel_position_on_destroy,add=\'+\')\n            window._drama_place_cancel_bound=True\n\n        def ready():\n            window._drama_place_job=None\n            try:\n                if window.winfo_exists():\n                    place(window,parent)\n            except Exception as exc:\n                # 已在 Map 时隐藏并取得输入的窗口，定位失败也必须恢复为\n                # 可见且无 grab；否则会留下“看不见但点不动”的全局输入锁。\n                try:window.attributes(\'-alpha\',1)\n                except tk.TclError:pass\n                try:window.grab_release()\n                except tk.TclError:pass\n                notice=getattr(root,\'_drama_place_notice\',None)\n                if callable(notice):\n                    try:notice(\'窗口定位失败，已恢复交互：%s\'% (str(exc) or \'未知错误\'))\n                    except Exception:app_logging.swallowed()\n\n        window._drama_place_job=window.after_idle(ready)\n\n    def mapped(event):\n\n        window=event.widget\n\n        if not isinstance(window,tk.Toplevel) or getattr(window,\'_positioned_once\',False):return\n\n        window._positioned_once=True\n\n        schedule_place(window,root)\n\n    root.bind_all(\'<Map>\',mapped,add=\'+\')\n\n    schedule_place(root)\n'

DRIVER = r'''
import sys, time, tkinter as tk
sys.path.insert(0, sys.argv[2])
import ui_theme
fn = ui_theme.install_window_placement
if sys.argv[1] == 'legacy':
    ns = dict(vars(ui_theme)); exec(sys.argv[3], ns); fn = ns['install_window_placement']
try:
    root = tk.Tk()
except tk.TclError:
    print('NO_TK'); raise SystemExit
root.geometry('900x700+10+10')
notices = []
root._drama_place_notice = notices.append
out = []
def pump(seconds=0.25):
    end = time.time() + seconds
    while time.time() < end:
        root.update(); time.sleep(0.01)
def state(w, tag):
    out.append((tag, w.winfo_exists() and w.winfo_ismapped(), w.geometry(), w.attributes('-alpha'),
                str(w.grab_current()), w.minsize(), w.resizable(), str(w.transient() or ''),
                getattr(w, '_positioned_once', None), getattr(w, '_drama_place_job', 'unset'),
                sorted(w.bind())))
fn(root); fn(root)
pump(); state(root, 'root')
top = tk.Toplevel(root); tk.Label(top, text='child').pack(); top.geometry('300x200')
pump(); state(top, 'popup')
top.withdraw(); pump(); state(top, 'withdrawn')
top.deiconify(); pump(); state(top, 'shown again')
top.destroy(); pump()
gone = tk.Toplevel(root); gone.destroy(); pump(); out.append(('destroyed early', str(root.grab_current())))
odd = tk.Toplevel(root); odd.overrideredirect(True); pump(); state(odd, 'override'); odd.destroy(); pump()
out.append(('notices', notices))
print(repr(out))
root.destroy()
'''


def _run(mode):
    program = str(Path(__file__).resolve().parents[1])
    done = subprocess.run([sys.executable, '-B', '-c', DRIVER, mode, program, LEGACY],
                          capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
    return done.returncode, done.stdout, done.stderr


class WindowPlacementEquivalence(unittest.TestCase):
    def test_matches_legacy(self):
        old = _run('legacy')
        if 'NO_TK' in old[1]:
            self.skipTest(PLATFORM_TKINTER)
        new = _run('new')
        self.assertEqual(new, old)
        self.assertIn("'popup', 1, '", old[1])   # 对照不能是空对空：弹窗真的显示出来了


if __name__ == '__main__':
    unittest.main()
