# -*- coding: utf-8 -*-
"""窗口定时器回归：关窗后不能留下 after 定时器。

Tkinter 销毁窗口时会删除 after 回调对应的 Tcl 命令，却不取消已登记的定时器：
残留定时器到期后执行已删除的命令，控制台就出现
invalid command name "…poll" ("after" script)。
运行：python test_timers.py
"""
from skip_reasons import (
    MISSING_NODE,
    PLATFORM_DIRECTORY_LINK,
    PLATFORM_TKINTER,
    PLATFORM_TK_DISPLAY,
    PLATFORM_WORKING_SET,
    REQUIRES_BUNDLED_SKILL,
)
import json, os, sys, tempfile, time, unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import tk_timers

FFMPEG = r"D:/Tools/ffmpeg/bin/ffmpeg.exe"
FFPROBE = r"D:/Tools/ffmpeg/bin/ffprobe.exe"


def make_minimal_project(td):
    proj = Path(td) / "p"
    (proj / "episode" / "frames").mkdir(parents=True)
    (proj / "episode" / "assets.json").write_text("{}", encoding="utf-8")
    (proj / "episode" / "episode.json").write_text(json.dumps({"episode_id": "EP001", "title": "T", "shots": [
        {"id": "SH001", "title": "镜头", "duration": 5, "characters": ["CHAR_001"], "location": "LOC_001",
         "frame": "frames/SH001.png", "video_prompt": "画面", "frame_prompt": "窗边的猫", "dialogue": []}]}, ensure_ascii=False), encoding="utf-8")
    (proj / "config.json").write_text(json.dumps({
        "episode_dir": str(proj / "episode"), "episode_file": str(proj / "episode" / "episode.json"),
        "budget_seconds": 0, "reserve_seconds": 0, "live_enabled": False,
        "ffmpeg": FFMPEG, "ffprobe": FFPROBE}), encoding="utf-8")
    return proj


class WindowTimerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def root(self):
        win = self.tk.Tk(); win.withdraw()
        def quiet_destroy():
            try:
                win.destroy()
            except Exception:
                pass
        self.addCleanup(quiet_destroy)
        return win

    def test_stop_removes_pending_timer(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        win = self.root()
        popup = self.tk.Toplevel(win)
        stop = tk_timers.repeat(popup, 5000, lambda: None)
        registered = set(win.tk.call("after", "info"))
        self.assertTrue(registered)
        stop()
        self.assertEqual(set(win.tk.call("after", "info")) & registered, set())

    def test_repeat_keeps_firing_until_window_destroyed(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        win = self.root()
        popup = self.tk.Toplevel(win)
        hits = []
        tk_timers.repeat(popup, 20, lambda: hits.append(1))
        for _ in range(25):
            win.update()
            if len(hits) >= 2:
                break
            time.sleep(0.01)
        self.assertGreaterEqual(len(hits), 2)
        popup.destroy(); win.update()
        count = len(hits)
        for _ in range(15):
            win.update(); time.sleep(0.01)
        self.assertEqual(len(hits), count)

    def test_batch_window_cancels_its_timer_on_close(self):
        """资产批量窗口关掉后，它的 250 毫秒轮询定时器必须一起取消。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        import asset_batch
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            win = self.root()
            from desktop import Desktop
            from local_video import open_studio
            d = Desktop(win, root=HERE)
            d.root = proj
            d.studio = open_studio(proj)
            # 先停掉主窗口自己的刷新循环，下面只观察这个批量窗口的定时器。
            d.cancel_timers()
            # 托盘的 120ms 排空定时器（R1775）也挂在主窗口上，与批量窗口无关；先关掉免得算进「窗口销毁后残留」。
            d.close_tray()
            registered = []
            original_repeat = tk_timers.repeat
            tk_timers.repeat = lambda widget, interval, callback: (
                registered.append((widget, interval)), original_repeat(widget, interval, callback))[1]
            self.addCleanup(setattr, tk_timers, "repeat", original_repeat)
            # R4424 起主窗口共享输入框挂了一条常驻 tk_timers.repeat（400ms 状态同步）：
            # 它随宿主控件 <Destroy> 自取消、不属 cancel_timers 管辖，且每次重排换新
            # after id，「after info 全空」的旧口径因此不再成立。按控件归属核对同一
            # 不变式：记录每个 widget 排过的 after id，关窗后批量窗口自己的必须全消失。
            scheduled = []
            original_after = self.tk.Misc.after

            def record_after(widget, ms, func=None, *args):
                after_id = original_after(widget, ms, func, *args)
                if func is not None:
                    scheduled.append((widget, str(after_id)))
                return after_id

            self.tk.Misc.after = record_after
            self.addCleanup(setattr, self.tk.Misc, "after", original_after)
            asset_batch.show(d, "workflow", selected_ids=["CHAR_001"])
            win.update()
            popup = [w for w in win.winfo_children() if isinstance(w, self.tk.Toplevel)][-1]
            # 批量窗口的刷新循环必须走会随窗口销毁一起取消的 tk_timers.repeat，不能自己再 after 一次。
            intervals = [interval for widget, interval in registered if widget is popup]
            self.assertTrue(intervals, "资产批量窗口没有登记刷新循环")
            self.assertEqual(set(intervals), {250})
            popup.destroy(); win.update()
            popup_jobs = {job for widget, job in scheduled if widget is popup}
            remaining = set(win.tk.call("after", "info")) & popup_jobs
            self.assertEqual(remaining, set())

    def test_window_placement_idle_job_is_cancelled_on_close(self):
        """install_window_placement 在主窗口排了一次 after_idle(place)；窗口在 idle 到期前被销毁时
        必须一起取消，否则控制台报 invalid command name "…<lambda>" ("after" script)。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import ui_theme
        win = self.root()
        ui_theme.install_window_placement(win)
        self.assertTrue(set(win.tk.call("after", "info")), "没有登记 after_idle")
        win.destroy()
        self.assertEqual(set(win.tk.call("after", "info")), set())

    def test_desktop_cancels_pending_content_fit_job(self):
        """关闭发生在首帧布局前时，Desktop 自己登记的 after_idle 必须可取消。"""
        from types import SimpleNamespace
        from desktop import Desktop

        class Window:
            def __init__(self):
                self.idle = None
                self.cancelled = []
            def after_idle(self, callback):
                self.idle = callback
                return 'content-fit-idle'
            def after_cancel(self, timer):
                self.cancelled.append(timer)

        win=Window(); subject=Desktop.__new__(Desktop)
        subject.win=win; subject._fit_pending=False; subject._fit_again=False
        subject._fit_content_now=lambda:(800, 900, 900)
        subject.restore_scroll=lambda offset:None
        subject.idea_chat_controller=SimpleNamespace(cancel_request=lambda:None)
        subject.pet=None; subject.startup_controller=None; subject.automation_scheduler=None
        subject.fit_content()
        self.assertEqual(subject._fit_job, 'content-fit-idle')
        subject.cancel_timers()
        self.assertEqual(win.cancelled, ['content-fit-idle'])
        self.assertIsNone(subject._fit_job)


class ChangeWatcherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def root(self):
        win = self.tk.Tk(); win.withdraw()
        self.addCleanup(lambda: win.winfo_exists() and win.destroy())
        return win

    def pump(self, win, times=40, delay=0.01):
        for _ in range(times):
            win.update(); time.sleep(delay)

    def test_refreshes_after_two_equal_observations(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        win = self.root(); popup = self.tk.Toplevel(win)
        state = {"value": 1}; hits = []
        tk_timers.watch_changes(popup, lambda: state["value"], lambda: hits.append(state["value"]), interval=20)
        self.pump(win, 20)
        self.assertEqual(hits, [])          # 快照没变，不刷新
        state["value"] = 2
        self.pump(win, 30)
        self.assertEqual(hits, [2])         # 连续两次相同后只刷新一次
        self.pump(win, 20)
        self.assertEqual(hits, [2])         # 稳定后不再重复刷新

    def test_declined_refresh_keeps_retrying(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        win = self.root(); popup = self.tk.Toplevel(win)
        state = {"value": 1}; calls = []

        def refresh():
            calls.append(state["value"]); return False

        tk_timers.watch_changes(popup, lambda: state["value"], refresh, interval=20)
        state["value"] = 2
        self.pump(win, 40)
        self.assertGreaterEqual(len(calls), 2)          # 返回 False 表示没处理，会继续重试
        self.assertTrue(all(value == 2 for value in calls))

    def test_stops_when_window_destroyed(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        win = self.root(); popup = self.tk.Toplevel(win)
        state = {"value": 1}; hits = []
        tk_timers.watch_changes(popup, lambda: state["value"], lambda: hits.append(1), interval=20)
        state["value"] = 2
        self.pump(win, 20)
        popup.destroy(); win.update()
        count = len(hits)
        self.assertGreaterEqual(count, 1)
        state["value"] = 3
        self.pump(win, 20)
        self.assertEqual(len(hits), count)              # 窗口销毁后定时器一起下线

    def test_page_watchers_delegate_to_shared_helper(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import keyframe_import, storyboard_files
        seen = []
        original_sync = tk_timers.watch_changes
        original_async = tk_timers.watch_changes_async
        tk_timers.watch_changes = lambda *args, **kwargs: (seen.append(args[1]), original_sync(*args, **kwargs))[1]
        tk_timers.watch_changes_async = lambda *args, **kwargs: (seen.append(args[1]), original_async(*args, **kwargs))[1]
        self.addCleanup(setattr, tk_timers, "watch_changes", original_sync)
        self.addCleanup(setattr, tk_timers, "watch_changes_async", original_async)
        win = self.root(); holder = self.tk.Frame(win); holder.pack()
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            storyboard_files.watch_files(holder, proj, lambda: None, interval=99999)
            keyframe_import.watch_list(holder, proj / "episode" / "episode.json", lambda: None, interval=99999)
        self.assertEqual(len(seen), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
