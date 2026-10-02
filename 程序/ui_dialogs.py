"""文件与目录选择的 UI 入口；页面不直接调用 ``filedialog``。"""
from __future__ import annotations

from tkinter import TclError, filedialog


class FileDialog:
    """统一处理选择、取消和窗口打开失败的可见反馈。"""

    def __init__(self, parent, *, chooser=filedialog, notifier=None):
        self.parent = parent
        self.chooser = chooser
        self.notifier = notifier

    def open_files(self, **options):
        options.setdefault('parent', self.parent)
        try:
            paths = self.chooser.askopenfilenames(**options)
        except (OSError, TclError) as exc:
            self._report_error(exc)
            return ()
        return tuple(paths or ())

    def _report_error(self, exc):
        text = '无法打开文件选择窗口：%s' % exc
        reporter = getattr(self.notifier, 'error', None)
        if callable(reporter):
            reporter(text, title='选择文件')
        return text
