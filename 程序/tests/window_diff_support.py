"""窗口差分测试的公共件：旧函数源码原样内嵌，在模块命名空间副本里 exec 出旧实现；
同一份脚本分别驱动旧、新实现，逐步拍控件树快照对照（快照规则见 page_diff_support）。"""
import re
import tkinter as tk
from unittest import mock

from page_diff_support import pump, safe_call, snapshot as _snapshot


def snapshot(top, roots):
    """Tk 变量名（PY_VAR<n>）随进程里已建的变量数递增，与实现无关，统一抹掉。"""
    return re.sub(r'PY_VAR\d+', 'PY_VAR', repr(_snapshot(top, roots)))


def legacy(module, source, name):
    ns = dict(vars(module))
    exec(source, ns)
    return ns[name]


class FakeApp:
    """宿主替身：所有回调只记账，不真的跑后台任务。"""
    def __init__(self, root, log):
        self.worker = None
        self.settings = {}
        self.log = log
        self.status = tk.StringVar(root)
        self.root = None
        self.win = root

    def safe(self, function, *args):
        outcome = safe_call(function, *args)
        self.log.append(('safe', outcome))
        return outcome

    def async_(self, work, done, **kwargs):
        self.log.append(('async', getattr(work, '__name__', '?'), tuple(sorted(kwargs))))

    def launch_comfy(self, **kwargs):
        self.log.append(('launch_comfy', tuple(sorted(kwargs.items()))))
        return False

    def show(self, *args):
        self.log.append(('show', args))

    def __getattr__(self, name):
        if name.startswith('__'):
            raise AttributeError(name)
        return lambda *a, **k: self.log.append((name, len(a), tuple(sorted(k))))


def _plain(value):
    """替身对象的 repr 带内存地址（id='…'、at 0x…），抹掉后再比。"""
    return re.sub(r" id='\d+'| at 0x[0-9A-Fa-f]+", '', repr(value))


def clickable(widget):
    from page_diff_support import walk
    out = []
    for w in walk(widget):
        if w.winfo_class() in ('TButton', 'Button', 'TCheckbutton', 'Checkbutton'):
            try:
                out.append((str(w.cget('text')), w))
            except tk.TclError:
                continue
    return out


def drive(top, roots, log, skip=()):
    """初态快照，再逐个点按钮（跳过会弹模态窗或开外部程序的）；每步记快照与日志。"""
    steps = [('initial', snapshot(top, roots))]
    for text, button in clickable(top):
        if text in skip or not button.winfo_exists():
            continue
        with mock.patch('webbrowser.open'), mock.patch('tkinter.messagebox.showinfo'), mock.patch('tkinter.messagebox.showerror'), \
                mock.patch('tkinter.messagebox.showwarning'), mock.patch('tkinter.messagebox.askyesno', return_value=False):
            outcome = safe_call(button.invoke)
        pump(top)
        steps.append((text, _plain(outcome), _plain(log), snapshot(top, roots) if top.winfo_exists() else None))
    return steps
