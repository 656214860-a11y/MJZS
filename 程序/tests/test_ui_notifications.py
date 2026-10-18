"""统一通知分发器的无 Tk 行为回归。"""
from __future__ import annotations

import unittest

from ui_widgets import BusyState, ContextMenu, NotificationDispatcher


class _Status:
    def __init__(self):
        self.values = []

    def set(self, value):
        self.values.append(value)


class _Dialogs:
    def __init__(self):
        self.calls = []

    def showerror(self, title, text, parent=None):
        self.calls.append(("error", title, text, parent))

    def showwarning(self, title, text, parent=None):
        self.calls.append(("warning", title, text, parent))

    def showinfo(self, title, text, parent=None):
        self.calls.append(("info", title, text, parent))


class _Progress:
    def __init__(self): self.calls = []
    def start(self, interval): self.calls.append(("start", interval))
    def stop(self): self.calls.append(("stop",))


class _Control:
    def __init__(self): self.calls = []
    def state(self, value): self.calls.append(tuple(value))


class _Menu:
    def __init__(self, owner, tearoff=False): self.calls = [("init", owner, tearoff)]
    def add_command(self, **kwargs): self.calls.append(("command", kwargs["label"]))
    def add_separator(self): self.calls.append(("separator",))
    def tk_popup(self, x, y): self.calls.append(("popup", x, y))
    def grab_release(self): self.calls.append(("release",))


class NotificationDispatcherTests(unittest.TestCase):
    def test_error_updates_status_and_reuses_error_dialog_when_modal(self):
        status, dialogs, parent = _Status(), _Dialogs(), object()
        notifier = NotificationDispatcher(status, parent=parent, dialogs=dialogs)

        self.assertEqual(notifier.error("  保存失败\n请重试  ", modal=True), "保存失败 请重试")
        self.assertEqual(status.values, ["保存失败 请重试"])
        self.assertEqual(dialogs.calls, [("error", "操作提示", "保存失败 请重试", parent)])

    def test_non_modal_warning_and_success_do_not_open_a_dialog(self):
        status, dialogs = _Status(), _Dialogs()
        notifier = NotificationDispatcher(status, dialogs=dialogs)

        notifier.warning("请检查设置")
        notifier.success("已保存")
        self.assertEqual(status.values, ["请检查设置", "已保存"])
        self.assertEqual(dialogs.calls, [])

    def test_unknown_level_and_empty_message_are_explicit(self):
        notifier = NotificationDispatcher(_Status(), dialogs=_Dialogs())
        self.assertEqual(notifier.notify("", level="info"), "")
        with self.assertRaises(ValueError):
            notifier.notify("内容", level="other")

    def test_busy_state_pairs_progress_status_and_control_recovery(self):
        status, progress, control = _Status(), _Progress(), _Control()
        busy = BusyState(status, progress)
        self.assertTrue(busy.set_busy(True, message="正在读取", controls=(control,)))
        self.assertTrue(busy.busy)
        self.assertEqual(status.values, ["正在读取"])
        self.assertEqual(progress.calls, [("start", 15)])
        self.assertEqual(control.calls, [("disabled",)])
        self.assertFalse(busy.set_busy(False))
        self.assertFalse(busy.busy)
        self.assertEqual(progress.calls[-1], ("stop",))
        self.assertEqual(control.calls[-1], ("!disabled",))

    def test_context_menu_builds_and_releases_grab_after_popup(self):
        event = type("Event", (), {"x_root": 12, "y_root": 34})()
        menu = ContextMenu("owner", menu_factory=_Menu).command("复制", lambda: None).separator()
        self.assertEqual(menu.popup(event), "break")
        self.assertEqual(menu.menu.calls, [("init", "owner", False), ("command", "复制"),
                                            ("separator",), ("popup", 12, 34), ("release",)])
