# -*- coding: utf-8 -*-
"""RESIZE 任务书：主窗口连续拖动改大小时合并整页重排，静默后补做一次完整重排。

运行：python tests/test_window_resize_coalescing.py

真 Tk 构造主窗口；连续尺寸变化由一个空闲回调按 STEP_PAUSE_MS 的节奏发出（远小于静默时长），
模拟 Windows 拖动时连续送 WM_SIZE。「光标捏在边框上」由测试翻动合并器的真实探测结果，
不碰系统设置，也不需要真的拖动鼠标。
"""
from skip_reasons import PLATFORM_TK_DISPLAY
import os
import sys
import tempfile
import threading
import time
import tkinter as tk
from tkinter import ttk
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, PROGRAM)
sys.path.insert(0, HERE)
os.chdir(PROGRAM)

from desktop import Desktop
from ui_tokens import DESKTOP_LAYOUT
import test_desktop_startup_perf as startup_fixtures

DRAG_STEPS = 30
STEP_PAUSE_MS = 4


class WindowResizeCoalescingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.win = tk.Tk()
        except tk.TclError as exc:
            raise unittest.SkipTest(PLATFORM_TK_DISPLAY + ': ' + str(exc))
        cls.temp = tempfile.TemporaryDirectory(prefix='resize-coalesce-')
        app, _project = startup_fixtures.DesktopStartupPerfTests._startup_app(
            cls.temp.name, remembered=True)
        cls.desktop = Desktop(cls.win, root=app)
        cls.win.update()
        cls.pump(.3)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.desktop.cancel_timers()
        except Exception:
            pass
        try:
            cls.win.destroy()
        except tk.TclError:
            pass
        cls.temp.cleanup()

    @classmethod
    def pump(cls, seconds=.2):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            cls.win.update()
            time.sleep(.005)

    def setUp(self):
        self.calls = 0
        self.trace = []
        self.original = self.desktop._fit_content_now

        def counted(from_drag=False):
            self.calls += 1
            self.trace.append(self.calls)
            self.marks.append((from_drag, self.calls))
            if from_drag:
                self.drag_calls += 1
            return self.original()
        self.desktop._fit_content_now = counted
        self.addCleanup(setattr, self.desktop, '_fit_content_now', self.original)
        self.held = False
        self.trace = []
        self.marks = []
        self.drag_calls = 0

        def dragging():
            return True if self.held else False
        self.desktop.resize_scheduler.__dict__['drag_active'] = dragging
        self.addCleanup(self._restore)

    def _restore(self):
        self.desktop.resize_scheduler.flush()
        try:
            del self.desktop.resize_scheduler.drag_active
        except AttributeError:
            pass

    def wait_for(self, predicate, seconds=3.0):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.win.update()
            if predicate():
                return True
            time.sleep(.005)
        return False

    def drag(self, start, sizes):
        """按拖动节奏连续发出尺寸变化；结束后（可选）松手。返回实际发出的次数。"""
        self.win.geometry('%dx%d' % start)
        self.assertTrue(self.wait_for(
            lambda: (self.win.winfo_width(), self.win.winfo_height()) == start))
        self.pump(.15)
        self.calls = 0
        self.held = True
        pending = list(sizes)
        fired = []

        def step():
            if not pending:
                return
            self.win.geometry('%dx%d' % pending[0])
            fired.append(pending.pop(0))
            if pending:
                self.win.after(STEP_PAUSE_MS, step)
        self.win.after(STEP_PAUSE_MS, step)
        self.assertTrue(self.wait_for(lambda: not pending, seconds=10.0))
        return fired

    def layout_snapshot(self):
        d = self.desktop
        return (self.win.winfo_width(), self.win.winfo_height(),
                d.canvas.itemcget(d.content_id, 'width'),
                d.canvas.cget('scrollregion'),
                str(d.sidebar_canvas.cget('scrollregion')),
                len(getattr(d, '_picker_items', ())),
                int(d.status_bar.winfo_height()))

    def test_continuous_drag_coalesces_until_quiet(self):
        """拖动期间完整重排 ≤2 次；松手静默后补做，最终布局与直接设同尺寸一致。"""
        sizes = [(1000 + 4 * index, 760 + 2 * index) for index in range(DRAG_STEPS)]
        fired = self.drag((1000, 760), sizes)
        self.assertEqual(len(fired), DRAG_STEPS)
        self.assertEqual((self.win.winfo_width(), self.win.winfo_height()), sizes[-1])
        during = self.calls
        self.assertLessEqual(during, 2, '拖动期间执行了 %d 次完整重排' % during)
        self.held = False
        self.assertTrue(self.wait_for(lambda: self.calls >= 1, seconds=3.0),
                        '松手静默后没有补做完整重排')
        self.pump(.3)
        coalesced = self.layout_snapshot()
        self.assertEqual(coalesced[:2], sizes[-1])
        # 对照：同一尺寸走非拖动路径再排一次，布局结果必须与合并路径一致。
        self.win.geometry('%dx%d' % (sizes[-1][0] - 40, sizes[-1][1]))
        self.pump(.25)
        self.win.geometry('%dx%d' % sizes[-1])
        self.pump(.3)
        self.assertEqual(coalesced, self.layout_snapshot())

    def test_drag_without_release_still_defers_until_quiet(self):
        """仍捏着边框但已静止：静默到点也不重排（等松手补做）。"""
        sizes = [(980 + 3 * index, 740 + 2 * index) for index in range(DRAG_STEPS)]
        self.drag(sizes[0], sizes[1:])
        during = self.calls
        self.pump(DESKTOP_LAYOUT['resize_quiet_ms'] / 1000.0 + .3)
        self.assertLessEqual(self.calls, 2)
        self.assertEqual(during, self.calls)
        self.held = False
        self.assertTrue(self.wait_for(lambda: self.calls >= 1, seconds=3.0))
        self.assertTrue(self.wait_for(lambda: not self.desktop.resize_scheduler.is_waiting(),
                                      seconds=2.0))

    def test_quit_event_during_drag_is_not_deferred(self):
        """事件循环要空了（用户退出拖动）但还没松手：仍要补做，不能挂到下次尺寸变化。"""
        sizes = [(1000, 760), (1004, 762), (1008, 764), (1012, 766), (1016, 768)]
        self.win.geometry('%dx%d' % sizes[0])
        self.assertTrue(self.wait_for(
            lambda: (self.win.winfo_width(), self.win.winfo_height()) == sizes[0]))
        self.pump(.15)
        self.calls = 0
        self.held = True
        for size in sizes[1:]:
            self.win.geometry('%dx%d' % size)
            self.win.update()
            time.sleep(STEP_PAUSE_MS / 1000.0)
        n = self.calls
        self.assertLessEqual(n, 2)
        self.held = False
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and self.calls == n:
            self.win.tk.call('update')  # Tk 只在事件队列耗尽时发 <<Quit>>
        self.assertTrue(self.wait_for(lambda: self.calls > n, seconds=2.0),
                        '没有新的尺寸变化，补做重排丢了')
        self.assertEqual((self.win.winfo_width(), self.win.winfo_height()), sizes[-1])

    def settle(self):
        """等到拖动补做／稳定性补算都落定，返回此刻的调用序号。"""
        self.pump(DESKTOP_LAYOUT['resize_quiet_ms'] / 1000.0 + .3)
        end = time.monotonic() + 5.0
        stable = 0
        while time.monotonic() < end:
            before = self.calls
            self.win.update()
            time.sleep(.01)
            stable = stable + 1 if self.calls == before else 0
            if stable >= 3:
                break
        return len(self.trace)

    def test_direct_fit_content_is_immediate(self):
        """非拖动场景不被延迟：主动调用 fit_content 仍立即执行，不等静默。"""
        self.calls = 0
        self.held = True
        self.marks.append((self.held, len(self.trace)))
        self.desktop.fit_content()
        end = time.monotonic() + .5
        while time.monotonic() < end and self.calls == 0:
            self.win.update()
            time.sleep(.005)
        # 光标仍捏在边框上，主动 fit_content 也已经排过（标记时 held 仍为真）；拖动的补做不会再来。
        self.assertTrue(self.trace)
        self.assertTrue(self.marks[0][0])
        self.assertEqual(self.drag_calls, 0, '拖动补做重复排了一次整页')
        self.held = False

    def test_layout_does_not_feed_on_its_own_content_resize(self):
        """布局自己把内容框撑到目标尺寸后，那次 <Configure> 不能再排一次整页重排。

        页面里的自动定高区域在内容框变高后会请求更高；若布局写出的尺寸又被当成
        一次「外部变化」，两者互相喂养，空闲队列永远排不空（窗口卡死、update() 不返回）。
        """
        d = self.desktop
        self.held = False
        d.fit_content()
        self.pump(.3)
        size = (int(float(d.canvas.itemcget(d.content_id, 'width'))),
                int(float(d.canvas.itemcget(d.content_id, 'height'))))
        self.calls = 0
        # 布局刚刚把内容框设成这个尺寸；Tk 随后送来的同尺寸 <Configure> 不是外部变化。
        event = types.SimpleNamespace(widget=d.content, width=size[0], height=size[1])
        d._on_resize_configure(event)
        self.pump(.3)
        self.assertEqual(self.calls, 0,
                         '布局自己写出的内容框尺寸又被当成外部变化，重排了 %d 次' % self.calls)

    def test_descendant_configure_does_not_trigger_page_relayout(self):
        """子控件尺寸变化不是页面尺寸变化：绑定在顶层窗口上的 <Configure>
        会经 bindtags 收到所有后代控件的事件，不能把每次子控件变化都当成整页重排。

        整页重排会改子控件尺寸，若后代事件也触发重排就会自我喂养，update() 永远不返回。
        （刻意不写需求编号：本次依据是真实环境证据与本确定性用例，不冒认既有需求锚点。）
        """
        d = self.desktop
        self.held = False
        d.fit_content()
        self.pump(.3)
        self.calls = 0
        descendant = ttk.Label(d.content, text='后代控件')
        self.addCleanup(lambda: descendant.destroy() if descendant.winfo_exists() else None)
        d._on_resize_configure(types.SimpleNamespace(
            widget=descendant,
            width=descendant.winfo_reqwidth(), height=descendant.winfo_reqheight()))
        self.pump(.3)
        self.assertEqual(self.calls, 0,
                         '后代子控件 %s 的 <Configure> 触发了整页重排 %d 次'
                         % (descendant, self.calls))
        # 正向：来自主窗口且宽高真的变了（各变 1 像素即可离开上一次记录），仍要重排。
        width, height = self.win.winfo_width(), self.win.winfo_height()
        d._on_resize_configure(types.SimpleNamespace(
            widget=self.win, width=width + 1, height=height + 1))
        self.assertTrue(self.wait_for(lambda: self.calls >= 1, seconds=3.0),
                        '主窗口宽高变化没有触发整页重排')

    def test_quiet_and_edge_are_tokens(self):
        """静默时长与命中圈取自 ui_tokens 既有常量表，不写魔法数字。"""
        self.assertIn('resize_quiet_ms', DESKTOP_LAYOUT)
        self.assertIn('resize_edge_px', DESKTOP_LAYOUT)
        self.assertGreater(DESKTOP_LAYOUT['resize_quiet_ms'], 0)
        self.assertGreater(DESKTOP_LAYOUT['resize_edge_px'], 0)
        self.assertLess(STEP_PAUSE_MS / 1000.0, DESKTOP_LAYOUT['resize_quiet_ms'] / 4000.0)


class LayoutConvergenceTests(unittest.TestCase):
    """画布宽度不变时，新控件及逐层请求几何仍须收敛。"""

    def setUp(self):
        from desktop_layout import LayoutMixin
        self.win = tk.Tk()
        self.addCleanup(self.win.destroy)
        self.win.geometry('800x500')
        canvas = tk.Canvas(self.win, highlightthickness=0)
        canvas.pack(fill='both', expand=True)
        content = ttk.Frame(canvas)
        window = canvas.create_window(0, 0, window=content, anchor='nw')

        class Layout(LayoutMixin):
            def align_header(self):
                pass

        self.layout = Layout()
        self.layout.win = self.win
        self.layout.canvas = canvas
        self.layout.content = content
        self.layout.content_id = window
        self.layout.page_index = 0
        self.win.update()

    def test_new_label_wraps_at_unchanged_canvas_width(self):
        d = self.layout
        d.fit_content(); self.win.update()
        label = ttk.Label(d.content, text='同宽重建的长说明' * 60, wraplength=200)
        label.pack()
        d.fit_content(); self.win.update()
        self.assertEqual(int(label.cget('wraplength')), d.canvas.winfo_width() - 28)

    def test_descendant_requests_settle_before_scroll_boundary(self):
        d = self.layout
        parent = d.content
        for _ in range(6):
            parent = ttk.Frame(parent)
            parent.pack()
        label = ttk.Label(parent, text='逐层传播的长说明' * 100, wraplength=200)
        label.pack()
        d.fit_content(); self.win.update()
        region = [int(v) for v in d.canvas.cget('scrollregion').split()]
        self.assertEqual(region[3], max(d.canvas.winfo_height(), d.content.winfo_reqheight()))
        self.assertIsNone(d._fit_job)
        self.assertFalse(d._fit_pending)

    def test_fit_signature_uses_direct_children_not_full_tree(self):
        """C01：_fit_request_signature 的测量节点数等于直接子级数，不递归全树。

        先红：当前实现把整棵子树所有控件都加入签名；修复后只量直接子级。
        签名第 4 分量 tuple(measured) 的长度应等于 content.winfo_children() 数量。
        """
        d = self.layout
        # 建两层：直接子级 2 个 Frame，各含 3 个 Label，共 8 个控件（深度 2）。
        for _ in range(2):
            frame = ttk.Frame(d.content)
            frame.pack()
            for _ in range(3):
                ttk.Label(frame, text='签名深度测试').pack()
        self.win.update()
        d.fit_content()
        self.win.update()
        sig = getattr(d, '_fit_request_signature', None)
        self.assertIsNotNone(sig, '_fit_request_signature 未设置')
        # sig = (width, req, target, tuple(measured))
        measured = sig[3]
        direct_count = len(d.content.winfo_children())
        self.assertEqual(
            len(measured), direct_count,
            '_fit_request_signature 包含 %d 个节点，应只含 %d 个直接子级（不递归）'
            % (len(measured), direct_count),
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)
