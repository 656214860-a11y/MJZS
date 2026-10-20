# -*- coding: utf-8 -*-
"""桌面系统托盘（最小化到托盘 + 右键菜单）冒烟。"""
import sys
import unittest

from desktop_tray import APP_ICON, LAUNCHER, PYTHONW, TrayIcon, force_restart


class TrayIconTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if sys.platform != 'win32':
            raise unittest.SkipTest('托盘仅 Windows')
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
        self.assertIsNotNone(tray._original_wndproc)
        tray.remove()
        self.assertFalse(tray._active)
        self.assertIsNone(tray._wndproc)

    def test_restart_paths_are_resolved(self):
        self.assertTrue(PYTHONW.is_file(), '解释器路径存在')
        self.assertTrue(LAUNCHER.is_file(), '启动器路径存在')
        self.assertTrue(APP_ICON.is_file(), '托盘图标存在')
        # 强制重启用脱离的辅助进程稍候拉起，避开单实例互斥量竞态。
        self.assertTrue(callable(force_restart))


if __name__ == '__main__':
    unittest.main()
