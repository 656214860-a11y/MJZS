"""统一文件选择入口的无 Tk 回归。"""
from __future__ import annotations

import unittest

from ui_dialogs import FileDialog


class _Chooser:
    def __init__(self, result=()):
        self.result = result
        self.calls = []

    def askopenfilenames(self, **options):
        self.calls.append(options)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    def askopenfilename(self, **options):
        self.calls.append(options)
        return self.result

    def asksaveasfilename(self, **options):
        self.calls.append(options)
        return self.result


class _Notifier:
    def __init__(self): self.calls = []
    def error(self, text, **options): self.calls.append((text, options))


class FileDialogTests(unittest.TestCase):
    def test_open_files_preserves_selection_and_uses_the_bound_parent(self):
        chooser, parent = _Chooser(('a.md', 'b.md')), object()
        dialog = FileDialog(parent, chooser=chooser)
        self.assertEqual(dialog.open_files(title='选择素材'), ('a.md', 'b.md'))
        self.assertEqual(chooser.calls, [{'parent': parent, 'title': '选择素材'}])

    def test_cancel_and_dialog_error_have_explicit_safe_results(self):
        self.assertEqual(FileDialog(object(), chooser=_Chooser()).open_files(), ())
        notifier = _Notifier()
        result = FileDialog(object(), chooser=_Chooser(OSError('窗口不可用')), notifier=notifier).open_files()
        self.assertEqual(result, ())
        self.assertEqual(notifier.calls[0][1]['title'], '选择文件')
        self.assertIn('窗口不可用', notifier.calls[0][0])

    def test_single_open_and_save_preserve_cancel_semantics(self):
        parent = object()
        chooser = _Chooser('frame.png')
        dialog = FileDialog(parent, chooser=chooser)
        self.assertEqual(dialog.open_file(title='选择首帧'), 'frame.png')
        self.assertEqual(dialog.save_file(title='导出'), 'frame.png')
        self.assertEqual(chooser.calls[0]['parent'], parent)
        self.assertEqual(FileDialog(parent, chooser=_Chooser('')).open_file(), '')
