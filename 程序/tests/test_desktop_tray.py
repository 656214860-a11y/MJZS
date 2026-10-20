# -*- coding: utf-8 -*-
"""桌面系统托盘（最小化到托盘 + 右键菜单）冒烟。"""
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

from skip_reasons import PLATFORM_WINDOWS_ONLY

from desktop_tray import APP_ICON, LAUNCHER, PYTHONW, TrayIcon, force_restart


class TrayIconTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if sys.platform != 'win32':
            raise unittest.SkipTest(PLATFORM_WINDOWS_ONLY)
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
        program = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, '-I', '-c', _CYCLE_SCRIPT, str(program)],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        self.assertIn('STATES=withdrawn,normal,withdrawn,normal,withdrawn,normal', result.stdout)


if __name__ == '__main__':
    unittest.main()
