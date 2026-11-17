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
        return self._choose('askopenfilenames', (), **options)

    def open_file(self, **options):
        """选择单个文件；取消统一返回空字符串。"""
        return self._choose('askopenfilename', '', **options)

    def save_file(self, **options):
        """选择保存目标；取消统一返回空字符串。"""
        return self._choose('asksaveasfilename', '', **options)

    def directory(self, **options):
        """选择目录；取消统一返回空字符串。"""
        return self._choose('askdirectory', '', **options)

    def _choose(self, method, empty, **options):
        options.setdefault('parent', self.parent)
        try:
            result = getattr(self.chooser, method)(**options)
        except (OSError, TclError) as exc:
            self._report_error(exc)
            return empty
        if method == 'askopenfilenames':
            return tuple(result or ())
        return result or empty

    def _report_error(self, exc):
        text = '无法打开文件选择窗口：%s' % exc
        reporter = getattr(self.notifier, 'error', None)
        if callable(reporter):
            reporter(text, title='选择文件')
        return text
