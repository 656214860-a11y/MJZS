# -*- coding: utf-8 -*-
"""REL-14：DPI 感知声明、最低系统版本自检、跨屏 DPI 重排监听与窄宽布局下限。

覆盖：
- ``desktop_launcher.enable_dpi_awareness``：per-monitor v2 优先、逐级降级、
  全失败不抛错、幂等（重复调用只生效一次）、无 Tk 时可调用；
- ``desktop_launcher.min_os_items``：低于 Windows 10 1809（build 17763）返回
  FATAL 诊断，达到下限或版本读不出返回空列表；
- 根 ``启动漫剧制作助手.pyw``：``desktop_launcher.enable_dpi_awareness()``
  调用行号早于第一处 ``tk.Tk()``（AST 断言，不起子进程）；
- ``responsive_ui.watch_dpi_change``：``<Configure>`` 上按实测 DPI 变化触发重排；
- ``desktop.py``：DPI 变化接到既有 ``_layout_all`` 重排（源码接线断言）；
- 1366×768 级窄宽下 FlowBar 换行不裁切（真 Tk，隐藏桌面运行器）与窗口尺寸 token 回归。
"""
from __future__ import annotations

import ast
import ctypes
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import desktop_launcher
import responsive_ui
from contract.diagnostics import Severity
from ui_tokens import DESKTOP_LAYOUT, SPACING

HERE = Path(__file__).resolve().parent.parent          # 程序/
REPO = HERE.parent                                     # 仓库根（启动漫剧制作助手.pyw 所在）
LAUNCHER = REPO / '启动漫剧制作助手.pyw'


# ---------------------------------------------------------------------------
# enable_dpi_awareness：级别优先级、逐级降级、幂等与不抛错（桩断言，不碰真实 user32/shcore）
# ---------------------------------------------------------------------------

def _fake_windll(*, context=None, per_monitor=1, system=1, legacy=None,
                 shcore=True, legacy_api=True, context_api=True):
    """组装 ctypes.windll 替身；返回值 None 表示该 API 不存在（AttributeError 路径）。"""
    calls = {'context': [], 'aware': [], 'legacy': []}
    user32 = SimpleNamespace()
    if context_api:
        def _context(value):
            calls['context'].append(value)
            return context
        user32.SetProcessDpiAwarenessContext = _context
    if legacy_api:
        def _legacy():
            calls['legacy'].append(True)
            return legacy
        user32.SetProcessDPIAware = _legacy
    windll = SimpleNamespace(user32=user32)
    if shcore:
        def _aware(value):
            calls['aware'].append(value)
            return per_monitor if value == 2 else system
        windll.shcore = SimpleNamespace(SetProcessDpiAwareness=_aware)
    windll._calls = calls
    return windll


class EnableDpiAwarenessTests(unittest.TestCase):
    """进程级 DPI 感知：v2 → per-monitor → system → 兜底，任何失败不抛错。"""

    def setUp(self):
        desktop_launcher._dpi_awareness.update({'done': False, 'level': None})

    def tearDown(self):
        desktop_launcher._dpi_awareness.update({'done': False, 'level': None})

    def _enable(self, windll):
        with mock.patch.object(ctypes, 'windll', windll):
            return desktop_launcher.enable_dpi_awareness()

    def test_per_monitor_v2_is_preferred_and_stops_there(self):
        windll = _fake_windll(context=True, per_monitor=0, system=0, legacy=True)
        self.assertEqual(self._enable(windll), 'per_monitor_v2')
        self.assertEqual(len(windll._calls['context']), 1)
        self.assertEqual(windll._calls['aware'], [])       # 不再降级
        self.assertEqual(windll._calls['legacy'], [])

    def test_context_failure_falls_back_to_per_monitor(self):
        windll = _fake_windll(context=False, per_monitor=0, system=1, legacy=True)
        self.assertEqual(self._enable(windll), 'per_monitor')
        self.assertEqual(windll._calls['aware'], [2])
        self.assertEqual(windll._calls['legacy'], [])

    def test_per_monitor_failure_falls_back_to_system(self):
        windll = _fake_windll(context=False, per_monitor=1, system=0, legacy=True)
        self.assertEqual(self._enable(windll), 'system')
        self.assertEqual(windll._calls['aware'], [2, 1])
        self.assertEqual(windll._calls['legacy'], [])

    def test_missing_shcore_falls_back_to_legacy_api(self):
        windll = _fake_windll(context=False, shcore=False, legacy=True)
        self.assertEqual(self._enable(windll), 'system')
        self.assertEqual(windll._calls['legacy'], [True])

    def test_shcore_error_falls_back_to_legacy_api(self):
        windll = _fake_windll(context=False, per_monitor=1, system=1, legacy=True)
        windll.shcore.SetProcessDpiAwareness = mock.Mock(side_effect=OSError('no shcore'))
        self.assertEqual(self._enable(windll), 'system')
        self.assertEqual(windll._calls['legacy'], [True])

    def test_all_failures_return_none_without_raising(self):
        windll = _fake_windll(context=False, per_monitor=1, system=1,
                             legacy=False, shcore=False)
        self.assertIsNone(self._enable(windll))

    def test_missing_apis_return_none_without_raising(self):
        windll = _fake_windll(context_api=False, legacy_api=False, shcore=False)
        self.assertIsNone(self._enable(windll))

    def test_windll_failure_returns_none_without_raising(self):
        class _Boom:
            @property
            def user32(self):
                raise OSError('user32 gone')
        with mock.patch.object(ctypes, 'windll', _Boom()):
            self.assertIsNone(desktop_launcher.enable_dpi_awareness())

    def test_non_windows_returns_none(self):
        with mock.patch('os.name', 'posix'):
            self.assertIsNone(desktop_launcher.enable_dpi_awareness())

    def test_repeat_call_is_noop_and_returns_first_result(self):
        """幂等：重复调用不再触碰 ctypes 三个入口，直接返回首次结果。"""
        windll = _fake_windll(context=True, per_monitor=0, system=0, legacy=True)
        with mock.patch.object(ctypes, 'windll', windll):
            self.assertEqual(desktop_launcher.enable_dpi_awareness(), 'per_monitor_v2')
            self.assertEqual(desktop_launcher.enable_dpi_awareness(), 'per_monitor_v2')
            self.assertEqual(desktop_launcher.enable_dpi_awareness(), 'per_monitor_v2')
        self.assertEqual(len(windll._calls['context']), 1)
        self.assertEqual(windll._calls['aware'], [])
        self.assertEqual(windll._calls['legacy'], [])

    def test_failed_attempt_is_not_retried(self):
        """首次全失败后重复调用仍是空操作，不重试三级入口。"""
        windll = _fake_windll(context=False, per_monitor=1, system=1,
                             legacy=False, shcore=False)
        with mock.patch.object(ctypes, 'windll', windll):
            self.assertIsNone(desktop_launcher.enable_dpi_awareness())
            self.assertIsNone(desktop_launcher.enable_dpi_awareness())
        self.assertEqual(len(windll._calls['context']), 1)

    def test_enable_dpi_awareness_runs_without_tk_window(self):
        """无 Tk 窗口时即可调用：本用例不创建任何 Tk 实例。"""
        import tkinter
        self.assertIsNone(getattr(tkinter, '_default_root', None))
        windll = _fake_windll(context=True)
        with mock.patch.object(ctypes, 'windll', windll):
            self.assertEqual(desktop_launcher.enable_dpi_awareness(), 'per_monitor_v2')
        self.assertIsNone(getattr(tkinter, '_default_root', None))


# ---------------------------------------------------------------------------
# min_os_items：低于 Windows 10 1809（build 17763）给 FATAL，达到下限放行
# ---------------------------------------------------------------------------

class MinOsItemsTests(unittest.TestCase):
    def _run(self, major=10, minor=0, build=17763):
        version = SimpleNamespace(major=major, minor=minor, build=build)
        with mock.patch.object(sys, 'getwindowsversion', return_value=version):
            return desktop_launcher.min_os_items()

    def test_below_windows_10_1809_returns_fatal_diagnostic(self):
        for major, build in ((6, 7601), (6, 9600), (10, 17134), (10, 17762)):
            with self.subTest(major=major, build=build):
                items = self._run(major=major, build=build)
                self.assertEqual(len(items), 1)
                item = items[0]
                self.assertIs(item.severity, Severity.FATAL)
                self.assertEqual(item.code, 'os-below-minimum')
                self.assertEqual(item.scope, 'config')
                self.assertIn('1809', item.message)
                self.assertTrue(item.remedy)

    def test_windows_10_1809_and_later_returns_empty(self):
        for major, build in ((10, 17763), (10, 19045), (10, 22631), (11, 22000)):
            with self.subTest(major=major, build=build):
                self.assertEqual(self._run(major=major, build=build), [])

    def test_version_unreadable_returns_empty(self):
        with mock.patch.object(sys, 'getwindowsversion', side_effect=OSError('no version')):
            self.assertEqual(desktop_launcher.min_os_items(), [])

    def test_non_windows_returns_empty(self):
        with mock.patch('os.name', 'posix'):
            self.assertEqual(desktop_launcher.min_os_items(), [])


# ---------------------------------------------------------------------------
# watch_dpi_change：<Configure> 上按实测 DPI 变化触发重排回调
# ---------------------------------------------------------------------------

class _FakeWidget:
    """只实现 watch_dpi_change 用到的两个 Tk 面：bind／winfo_fpixels。"""

    def __init__(self, scale=96.0, fail=False):
        self.scale = scale
        self.fail = fail
        self.bindings = []

    def bind(self, sequence, callback, add=None):
        self.bindings.append((sequence, callback))

    def winfo_fpixels(self, spec):
        if self.fail:
            raise RuntimeError('no window')
        return self.scale


class WatchDpiChangeTests(unittest.TestCase):
    def test_binds_configure_and_fires_only_on_real_scale_change(self):
        widget = _FakeWidget(96.0)
        fired = []
        check = responsive_ui.watch_dpi_change(widget, lambda: fired.append(1))
        self.assertIn(('<Configure>', check), widget.bindings)
        check()                                    # 同值：不触发
        check()
        self.assertEqual(fired, [])
        widget.scale = 144.0                       # 100% → 150%：触发一次
        check()
        check()                                    # 同值不重复触发
        self.assertEqual(len(fired), 1)
        widget.scale = 192.0                       # → 200%：再触发
        check()
        self.assertEqual(len(fired), 2)
        widget.scale = 96.0                        # 移回原屏：仍是真变化
        check()
        self.assertEqual(len(fired), 3)

    def test_unmeasurable_scale_is_ignored_without_raising(self):
        widget = _FakeWidget(fail=True)
        fired = []
        check = responsive_ui.watch_dpi_change(widget, lambda: fired.append(1))
        check()
        self.assertEqual(fired, [])
        widget.fail = False
        widget.scale = 96.0                        # 首个可测值建立基线并触发一次重排
        check()
        self.assertEqual(len(fired), 1)
        check()
        self.assertEqual(len(fired), 1)

    def test_initial_scale_is_the_baseline(self):
        widget = _FakeWidget(144.0)
        fired = []
        check = responsive_ui.watch_dpi_change(widget, lambda: fired.append(1))
        check()
        self.assertEqual(fired, [])


# ---------------------------------------------------------------------------
# 启动器接线（AST）：DPI 声明先于第一处 tk.Tk()
# ---------------------------------------------------------------------------

class LauncherDpiOrderTests(unittest.TestCase):
    """根 启动漫剧制作助手.pyw：enable_dpi_awareness 调用必须早于任何 Tk 窗口创建。"""

    def test_dpi_call_precedes_first_tk_window(self):
        self.assertTrue(LAUNCHER.is_file(), '仓库根缺少 启动漫剧制作助手.pyw')
        tree = ast.parse(LAUNCHER.read_text(encoding='utf-8'))
        imported = {alias.name for node in ast.walk(tree)
                    if isinstance(node, ast.Import) for alias in node.names}
        self.assertIn('desktop_launcher', imported)
        dpi_lines = [node.lineno for node in ast.walk(tree)
                     if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Attribute)
                     and node.func.attr == 'enable_dpi_awareness'
                     and isinstance(node.func.value, ast.Name)
                     and node.func.value.id == 'desktop_launcher']
        tk_lines = [node.lineno for node in ast.walk(tree)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == 'Tk'
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == 'tk']
        self.assertTrue(dpi_lines, '根启动器缺少 desktop_launcher.enable_dpi_awareness() 调用')
        self.assertTrue(tk_lines, '根启动器找不到 tk.Tk()')
        self.assertLess(min(dpi_lines), min(tk_lines),
                        'DPI 感知必须在建 Tk 窗口之前声明')


class DeferredImportTests(unittest.TestCase):
    """REF-L5-1：``import desktop_launcher`` 不在模块顶层拉起 tkinter／ui_widgets。

    顶层提前导入会让 DPI 声明与启动自检为不需要窗口的路径白付冷导入开销；
    弹窗与 ``launch()`` 在用点函数内延迟导入。真子进程核验 ``sys.modules``。
    """

    def test_import_does_not_load_tkinter_or_ui_widgets(self):
        code = ('import sys\n'
                'sys.path.insert(0, %r)\n'
                'import desktop_launcher\n'
                'bad = sorted(m for m in ("tkinter", "tkinter.ttk", "ui_widgets")\n'
                '             if m in sys.modules)\n'
                'raise SystemExit("desktop_launcher 顶层提前导入：%%r" %% bad if bad else 0)\n'
                % str(HERE))
        done = subprocess.run([sys.executable, '-B', '-c', code],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0,
                         'stdout=%r stderr=%r' % (done.stdout[-400:], done.stderr[-800:]))


class DesktopDpiWiringTests(unittest.TestCase):
    """desktop.py 必须把 DPI 变化接到既有整页重排入口（不新建布局体系、不重建窗口）。"""

    def test_watch_dpi_change_is_wired_to_full_relayout(self):
        source = (HERE / 'desktop.py').read_text(encoding='utf-8')
        self.assertIn('watch_dpi_change', source)
        self.assertIn('watch_dpi_change(win,self._layout_all)', source)
        self.assertLess(source.index('watch_window_resize(win)'),
                        source.index('watch_dpi_change(win,self._layout_all)'))


# ---------------------------------------------------------------------------
# 1366×768 级窄宽布局：FlowBar 换行不裁切（真 Tk，隐藏桌面运行器）
# ---------------------------------------------------------------------------

class FlowBarNarrowWidthTests(unittest.TestCase):
    """窄宽下操作栏换行增高，按钮不被左右裁掉（沿用 responsive_ui 既有做法）。"""

    def test_buttons_wrap_within_bar_instead_of_clipping(self):
        import tkinter as tk
        from tkinter import ttk
        root = tk.Tk()
        self.addCleanup(root.destroy)
        root.geometry('480x360')
        bar = responsive_ui.FlowBar(root)
        bar.pack(fill='x', padx=8)
        for index in range(6):
            ttk.Button(bar, text='操作按钮 %d' % index, command=lambda: None).pack(side='left', padx=2)
        root.update()
        root.update()
        width = bar.winfo_width()
        self.assertGreater(width, 100)
        placed = 0
        for child in bar.winfo_children():
            info = child.place_info()
            x = int(info.get('x', 0) or 0)
            w = int(info.get('width', 0) or 0)
            self.assertLessEqual(x + w, width + 1,
                                 '%s 伸出操作栏右缘被裁切' % child)
            self.assertTrue(child.winfo_ismapped(), '%s 未显示' % child)
            placed += 1
        self.assertEqual(placed, 6)
        # 换行后栏高超过单行：SPACING['sm']*5 是 FlowBar 的初始单行高度。
        self.assertGreater(int(bar.cget('height')), SPACING['sm'] * 5)


class SmallScreenLayoutContractTests(unittest.TestCase):
    """1366×768 约束：最小尺寸与默认窗口都必须落在可用区内（token 级回归守卫）。"""

    def test_minimum_window_fits_1366x768(self):
        self.assertLessEqual(DESKTOP_LAYOUT['min_width'], 1366)
        self.assertLessEqual(DESKTOP_LAYOUT['min_height'], 768)
        self.assertLessEqual(DESKTOP_LAYOUT['min_width'] + 2 * DESKTOP_LAYOUT['window_margin_x'], 1366)
        self.assertLessEqual(DESKTOP_LAYOUT['min_height'] + 2 * DESKTOP_LAYOUT['window_margin_y'], 768)

    def test_default_window_is_clamped_into_1366x768(self):
        # 与 desktop.py 启动几何同一公式：min(默认, 屏幕可用区)。
        width = min(DESKTOP_LAYOUT['default_width'],
                    1366 - DESKTOP_LAYOUT['window_margin_x'])
        height = min(DESKTOP_LAYOUT['default_height'],
                     768 - DESKTOP_LAYOUT['window_margin_y'])
        self.assertLessEqual(width, 1366 - DESKTOP_LAYOUT['window_margin_x'])
        self.assertLessEqual(height, 768 - DESKTOP_LAYOUT['window_margin_y'])
        self.assertGreater(width, DESKTOP_LAYOUT['min_width'])
        self.assertGreater(height, DESKTOP_LAYOUT['min_height'])


if __name__ == '__main__':
    unittest.main()
