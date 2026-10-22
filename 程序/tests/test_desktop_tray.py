# -*- coding: utf-8 -*-
"""桌面系统托盘（最小化到托盘 + 右键菜单）冒烟。"""
import os
import subprocess
import sys
import textwrap
import time
import unittest
from pathlib import Path

from skip_reasons import PLATFORM_NO_TRAY_HOST, PLATFORM_WINDOWS_ONLY

from desktop_tray import APP_ICON, LAUNCHER, PYTHONW, SUPPRESS_TRAY_ENV, TrayIcon, force_restart


def _on_tray_desktop():
    """本线程是否在默认交互桌面（Default）：隐藏测试桌面上没有任务栏，托盘图标加不上。"""
    import ctypes
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    user32.GetThreadDesktop.restype = ctypes.c_void_p
    desk = user32.GetThreadDesktop(ctypes.windll.kernel32.GetCurrentThreadId())
    buf = ctypes.create_unicode_buffer(256)
    needed = ctypes.c_ulong()
    if not desk or not user32.GetUserObjectInformationW(ctypes.c_void_p(desk), 2, buf,
                                                        ctypes.sizeof(buf), ctypes.byref(needed)):
        return True  # 读不到就照常跑，不靠猜测跳过
    return buf.value.lower() == 'default'


class TrayIconTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if sys.platform != 'win32':
            raise unittest.SkipTest(PLATFORM_WINDOWS_ONLY)
        if not _on_tray_desktop():
            raise unittest.SkipTest(PLATFORM_NO_TRAY_HOST)
        import tkinter as tk
        cls.win = tk.Tk()
        cls.win.withdraw()
        cls.win.update_idletasks()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.win.destroy()
        except Exception:
            pass

    def test_add_and_remove_tray_icon(self):
        tray = TrayIcon(
            self.win,
            on_restore=lambda: None,
            on_quit=lambda: None,
            on_force_restart=lambda: None,
        )
        tray.add()
        self.assertTrue(tray._active, 'Shell_NotifyIcon 添加成功')
        self.assertIsNotNone(tray._wndproc, 'WNDPROC 引用必须持有，防 GC 后回调段错误')
        self.assertNotEqual(tray._hwnd, int(self.win.winfo_id()),
                            '托盘必须挂在自己的隐藏窗口上，不能子类化 Tk 窗口（R1775 闪退根因）')
        tray.remove()
        self.assertFalse(tray._active)
        self.assertIsNone(tray._wndproc)
        self.assertIsNone(tray._thread, '移除后托盘线程已收摊')

    def test_two_trays_do_not_share_a_window_class(self):
        """同名窗口类会让后建的托盘沿用先建实例的 WNDPROC；先建的一收摊，回调被释放，
        后者再收到消息就以 0xC000041D 带崩整个进程（全量自检中的进程池中断）。"""
        import desktop_tray
        calls = []
        first = TrayIcon(self.win, on_restore=lambda: None, on_quit=lambda: None,
                         on_force_restart=lambda: None)
        second = TrayIcon(self.win, on_restore=lambda: calls.append('restore'), on_quit=lambda: None,
                          on_force_restart=lambda: None)
        self.assertNotEqual(first._class_name, second._class_name)
        first.add()
        second.add()
        try:
            first.remove()
            # 先建的已收摊：给后建的投一次左键单击，它自己的回调必须还活着。
            second._user32.PostMessageW(second._hwnd, desktop_tray.WM_TRAYICON, 1,
                                        desktop_tray.WM_LBUTTONUP)
            deadline = time.monotonic() + 3
            while not second._pending and time.monotonic() < deadline:
                time.sleep(0.02)
            second._drain()
            self.assertEqual(calls, ['restore'])
        finally:
            first.remove()
            second.remove()

    def test_restart_paths_are_resolved(self):
        self.assertTrue(PYTHONW.is_file(), '解释器路径存在')
        self.assertTrue(LAUNCHER.is_file(), '启动器路径存在')
        self.assertTrue(APP_ICON.is_file(), '托盘图标存在')
        # 强制重启用脱离的辅助进程稍候拉起，避开单实例互斥量竞态。
        self.assertTrue(callable(force_restart))

    def test_menu_commands_dispatch_to_callbacks(self):
        from unittest.mock import Mock
        tray = TrayIcon(self.win, on_restore=lambda: None, on_quit=lambda: None,
                        on_force_restart=lambda: None)
        tray._hwnd = int(self.win.winfo_id())
        calls = []
        tray.on_restore = lambda: calls.append('restore')
        tray.on_quit = lambda: calls.append('quit')
        tray.on_force_restart = lambda: calls.append('restart')
        user32 = Mock()
        user32.CreatePopupMenu.return_value = 1
        user32.AppendMenuW.return_value = True
        user32.SetForegroundWindow.return_value = True
        user32.DestroyMenu.return_value = True
        user32.TrackPopupMenu.side_effect = [1, 3]  # 恢复窗口、退出
        tray._user32 = user32
        tray._show_menu()
        tray._show_menu()
        # R1775 契约：菜单在托盘线程里只入队，命令由 Tk 主线程的 _drain 统一分发。
        tray._active = True
        try:
            tray._drain()
        finally:
            tray._cancel_drain()
            tray._active = False
        self.assertEqual(calls, ['restore', 'quit'])

    def test_a_failing_callback_does_not_drop_the_rest_of_the_batch(self):
        """R1777：恢复回调抛错时，同批的「退出」不能整批丢失。"""
        calls = []

        def broken_restore():
            raise RuntimeError('restore failed')

        tray = TrayIcon(self.win, on_restore=broken_restore, on_quit=lambda: calls.append('quit'),
                        on_force_restart=lambda: None)
        tray._active = True
        try:
            tray._enqueue(1)  # 恢复（回调会抛错）
            tray._enqueue(3)  # 退出
            tray._drain()
        finally:
            tray._cancel_drain()
            tray._active = False
        self.assertEqual(calls, ['quit'])

    def test_setup_tray_failure_does_not_block_startup(self):
        """R1777：托盘建不起来只记日志，不让 Desktop 构造失败。"""
        from unittest import mock
        import desktop_tray

        class Host(desktop_tray.TrayMixin):
            win = self.win

            def close(self):
                pass

        host = Host()
        # 自检器默认设了 DRAMA_SUPPRESS_TRAY=1（setup_tray 直接返回）；这条要走真实建托盘的失败分支，所以局部清掉。
        with mock.patch.dict(os.environ),                 mock.patch.object(desktop_tray.TrayIcon, 'add', side_effect=RuntimeError('托盘窗口创建超时')):
            os.environ.pop(SUPPRESS_TRAY_ENV, None)
            host.setup_tray()  # 不抛
        self.assertIsNone(host.tray_icon)


_CYCLE_SCRIPT = textwrap.dedent(r'''
    import ctypes, sys, time
    sys.path.insert(0, sys.argv[1])
    import tkinter as tk
    import desktop_tray as dt
    post = ctypes.windll.user32.PostMessageW
    class App(dt.TrayMixin):
        def __init__(self, win):
            self.win = win
        def close(self):
            pass
    win = tk.Tk(); win.geometry('200x120+50+50'); app = App(win); win.update()
    app.setup_tray(); tray = app.tray_icon
    def pump(ms):
        end = time.time() + ms / 1000
        while time.time() < end:
            win.update(); time.sleep(0.01)
    states = []
    for kind in (dt.WM_LBUTTONUP, dt.WM_LBUTTONDBLCLK, dt.WM_LBUTTONUP):
        win.iconify(); pump(250); states.append(win.state())
        post(tray._hwnd, dt.WM_TRAYICON, 1, kind); pump(350); states.append(win.state())
    app.close_tray(); win.destroy()
    print('STATES=' + ','.join(states))
''')


class TrayMinimizeCycleTests(unittest.TestCase):
    """R1775 回归：最小化进托盘、点托盘恢复，反复多次进程不得闪退。

    放子进程里跑：旧实现在这里直接 Fatal Python error（GIL 状态错乱），会带崩测试进程。
    """

    def test_minimize_and_click_tray_cycles_without_crash(self):
        if sys.platform != 'win32':
            self.skipTest(PLATFORM_WINDOWS_ONLY)
        if not _on_tray_desktop():
            self.skipTest(PLATFORM_NO_TRAY_HOST)
        program = Path(__file__).resolve().parents[1]
        env = {key: value for key, value in os.environ.items() if key != SUPPRESS_TRAY_ENV}
        result = subprocess.run(
            [sys.executable, '-I', '-c', _CYCLE_SCRIPT, str(program)],
            env=env, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        self.assertIn('STATES=withdrawn,normal,withdrawn,normal,withdrawn,normal', result.stdout)


if __name__ == '__main__':
    unittest.main()
