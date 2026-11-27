# -*- coding: utf-8 -*-
"""宠物贴片自检（核心生命周期、几何、接缝与桌面集成）：自原 test_pet_ui.py 按测试类拆分，断言与夹具原样保留。"""
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
if PROGRAM not in sys.path:
    sys.path.insert(0, PROGRAM)
os.chdir(PROGRAM)

from skip_reasons import PLATFORM_TKINTER
from pet_ui_test_support import (
    _Event,
    FakeDesktop,
    PetTestCase,
    make_project,
    SequenceRand,
)
import pet_bus
from ui import pet_cloud
import ui.pet_ui as pet_ui
import selftest_sandbox

selftest_sandbox.isolate(pet_ui)

class GeometryTests(PetTestCase):
    def show_at(self, width, height, x=20, y=20):
        self.win.geometry(f'{width}x{height}+{x}+{y}')
        self.win.deiconify()
        self.win.update_idletasks()
        self.win.update()

    def test_compact_avatar_paws_and_caption_fit_both_window_sizes(self):
        """第 R2946 期：三虎簇收成正方形——左列头像上小字下、右列猫爪对整组垂直居中。"""
        self.assertLess(pet_ui.SIZE, pet_ui.PET_LAYOUT['source_size'])
        for width, height in ((942, 1032), (800, 600)):
            with self.subTest(size=(width, height)):
                self.show_at(width, height)
                avatar, paws, caption = self.pet.canvas, self.pet.paws, self.pet.caption
                dock = self.fake.pet_dock
                layout = self.pet._cluster_layout()
                self.assertAlmostEqual(
                    avatar.winfo_rootx(), dock.winfo_rootx() + layout['avatar_x'], delta=2,
                    msg='头像在簇左列')
                self.assertAlmostEqual(
                    avatar.winfo_rooty(), dock.winfo_rooty() + layout['avatar_y'], delta=2,
                    msg='头像在簇区内垂直居中')
                # 猫爪列视觉右沿＝簇内容右缘内侧 DOCK_PAW_RIGHT（place 的 x 是相对右沿的偏移）。
                paw_right = layout['paw_x'] + dock.winfo_width()
                self.assertAlmostEqual(
                    paws.winfo_rootx() + paws.winfo_width(),
                    dock.winfo_rootx() + paw_right, delta=2,
                    msg='猫爪列右沿收在簇右缘内侧')
                # 猫爪列对「头像＋小字间距＋小字实高」整组垂直居中。
                caption_h = int(caption.winfo_reqheight())
                if caption_h <= 0:
                    caption_h = 2 * pet_ui.PET_LAYOUT['caption_height']
                group_h = pet_ui.SIZE + pet_ui.DOCK_CAPTION_GAP + caption_h
                group_cy = dock.winfo_rooty() + layout['avatar_y'] + group_h / 2.0
                self.assertAlmostEqual(
                    paws.winfo_rooty() + paws.winfo_height() / 2.0, group_cy, delta=2,
                    msg='猫爪列对头像＋小字整组垂直居中')
                self.assertAlmostEqual(
                    caption.winfo_rooty(),
                    avatar.winfo_rooty() + pet_ui.SIZE + pet_ui.DOCK_CAPTION_GAP, delta=2,
                    msg='小字在头像正下方')
                self.assertAlmostEqual(
                    caption.winfo_rootx(), avatar.winfo_rootx(), delta=2,
                    msg='小字左沿与头像左沿对齐')
                for widget in (avatar, paws, caption):
                    self.assertGreaterEqual(widget.winfo_rootx(), dock.winfo_rootx() - 2)
                    self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(),
                                         dock.winfo_rootx() + dock.winfo_width() + 2)
                    self.assertGreaterEqual(widget.winfo_rooty(), dock.winfo_rooty() - 2)
                    self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(),
                                         dock.winfo_rooty() + dock.winfo_height() + 2)

    def test_every_pose_is_scaled_into_the_avatar_hit_rectangle(self):
        for pose in pet_ui.POSES:
            for step in range(4):
                with self.subTest(pose=pose, step=step):
                    pet_ui.paint(self.pet.canvas, pose=pose, step=step)
                    left, top, right, bottom = self.pet.canvas.bbox('all')
                    self.assertGreaterEqual(left, -2)
                    self.assertGreaterEqual(top, -2)
                    self.assertLessEqual(right, pet_ui.SIZE + 2)
                    self.assertLessEqual(bottom, pet_ui.SIZE + 2)

    def test_paw_centres_keep_their_click_targets_after_shrinking(self):
        selected = []
        self.pet.set_paw_level = selected.append
        for index, level in enumerate(pet_ui.PAW_LEVELS):
            box = self.pet.paws.bbox('paw-' + level)
            y = (box[1] + box[3]) / 2
            self.assertEqual(self.pet.paw_at(y), index)
            self.pet.paw_click(SimpleNamespace(y=y))
        self.assertEqual(selected, list(pet_ui.PAW_LEVELS))

    def test_menu_and_cloud_follow_the_moved_and_resized_avatar(self):
        positions = []
        self.pet.menu.popup_at = lambda x, y: positions.append((x, y))
        cloud = self.pet.cloud()
        previous = None
        for width, height, x, y in ((942, 1032, 20, 20), (800, 600, 80, 100)):
            with self.subTest(size=(width, height), position=(x, y)):
                self.show_at(width, height, x, y)
                avatar = self.pet.canvas
                left, top = avatar.winfo_rootx(), avatar.winfo_rooty()
                aw, ah = avatar.winfo_width(), avatar.winfo_height()
                self.pet.popup_at()
                self.assertEqual(positions[-1], (left, top + ah))
                anchor = cloud._anchor()
                self.assertAlmostEqual(anchor[0], left + aw * pet_cloud.CHEEK_X, delta=2)
                self.assertAlmostEqual(anchor[1], top + ah * pet_cloud.CHEEK_Y, delta=2)
                if previous is not None:
                    self.assertNotEqual(anchor, previous)
                previous = anchor

    def test_host_pet_layer_keeps_control_of_its_height_and_propagation(self):
        layer = self.ttk.Frame(self.fake.body, height=pet_ui.DOCK_ROOM + 12)
        layer.pack(fill='x')
        layer.pack_propagate(False)
        self.fake.pet_layer = layer
        for widget in (self.pet.canvas, self.pet.paws, self.pet.caption):
            widget.destroy()
        self.pet._build_canvas()
        self.pet._build_paws()
        self.pet._reserve_room(layer, needed=False)
        self.assertEqual(self.pet.canvas.winfo_parent(), str(layer))
        self.assertEqual(self.pet.paws.winfo_parent(), str(layer))
        self.assertEqual(int(layer.cget('height')), pet_ui.DOCK_ROOM + 12)
        self.assertFalse(layer.pack_propagate())

    def test_pet_sits_inside_the_square_cluster(self):
        """第 R2946 期：簇区正方形——头像在左列、猫爪列右沿收在簇右缘内侧，坐标由 _cluster_layout 细算。"""
        layout = self.pet._cluster_layout()
        info = self.pet.canvas.place_info()
        self.assertEqual(info["anchor"], "nw")
        self.assertAlmostEqual(float(info["x"]), layout["avatar_x"], delta=1)
        self.assertAlmostEqual(float(info["y"]), layout["avatar_y"], delta=1)
        self.assertEqual(int(self.pet.canvas.cget("width")), pet_ui.SIZE)
        self.assertEqual(int(self.pet.canvas.cget("height")), pet_ui.SIZE)
        paws = self.pet.paws.place_info()
        self.assertEqual(float(paws['relx']), 1.0)
        self.assertEqual(paws['anchor'], 'ne')
        self.assertAlmostEqual(float(paws['x']), layout['paw_x'], delta=1)
        caption = self.pet.caption.place_info()
        self.assertAlmostEqual(float(caption['x']), layout['avatar_x'], delta=1)
        self.assertAlmostEqual(float(caption['y']), layout['caption_y'], delta=1)

    def test_pet_lives_inside_the_dock(self):
        self.assertEqual(str(self.pet.canvas.winfo_parent()), str(self.fake.pet_dock))
        self.assertIs(self.pet.canvas.winfo_toplevel(), self.win)

    def test_the_pet_cluster_left_the_header_row(self):
        """第 R2933 期：三虎簇搬进侧栏底栏，标题行文字不再需要给贴片让位。"""
        for widget in (self.pet.canvas, self.pet.paws, self.pet.caption):
            self.assertNotEqual(str(widget.winfo_parent()), str(self.fake.title_row))
        for widget in (self.fake.header_status, self.fake.header_model):
            self.assertEqual(str(widget.winfo_parent()), str(self.fake.title_row))


class MainWindowRestoreTests(PetTestCase):
    """任务栏最小化不能被 winfo_viewable 的 Windows 语义误判为可见。"""

    def test_iconic_window_is_not_treated_as_visible(self):
        original_state = self.win.state
        original_viewable = self.win.winfo_viewable
        self.win.state = lambda *args: 'iconic' if not args else None
        self.win.winfo_viewable = lambda: True
        self.addCleanup(setattr, self.win, 'state', original_state)
        self.addCleanup(setattr, self.win, 'winfo_viewable', original_viewable)
        self.assertFalse(self.pet.window_visible())

    def test_show_main_restores_iconic_window_before_showing_it(self):
        calls = []
        original_state = self.win.state
        original_viewable = self.win.winfo_viewable
        original_deiconify = self.win.deiconify
        original_update = self.win.update_idletasks
        original_lift = self.win.lift
        original_focus = self.win.focus_force
        original_attributes = self.win.attributes
        original_after_idle = self.win.after_idle
        self.win.state = lambda *args: calls.append(('state', args)) or ('iconic' if not args else None)
        self.win.winfo_viewable = lambda: True
        self.win.deiconify = lambda: calls.append(('deiconify',))
        self.win.update_idletasks = lambda: calls.append(('update_idletasks',))
        self.win.lift = lambda: calls.append(('lift',))
        self.win.focus_force = lambda: calls.append(('focus_force',))
        self.win.attributes = lambda *args: calls.append(('attributes', args))
        self.win.after_idle = lambda callback: calls.append(('after_idle',)) or callback()
        self.addCleanup(setattr, self.win, 'state', original_state)
        self.addCleanup(setattr, self.win, 'winfo_viewable', original_viewable)
        self.addCleanup(setattr, self.win, 'deiconify', original_deiconify)
        self.addCleanup(setattr, self.win, 'update_idletasks', original_update)
        self.addCleanup(setattr, self.win, 'lift', original_lift)
        self.addCleanup(setattr, self.win, 'focus_force', original_focus)
        self.addCleanup(setattr, self.win, 'attributes', original_attributes)
        self.addCleanup(setattr, self.win, 'after_idle', original_after_idle)
        self.assertTrue(self.pet.show_main())
        self.assertEqual(calls[:3], [('state', ()), ('deiconify',), ('state', ('normal',))])
        self.assertIn(('state', ('normal',)), calls)
        self.assertIn(('attributes', ('-topmost', True)), calls)
        self.assertIn(('attributes', ('-topmost', False)), calls)
        self.assertEqual(calls[-1], ('focus_force',))

    def test_show_main_keeps_restore_successful_when_focus_is_rejected(self):
        original_focus = self.win.focus_force
        self.win.focus_force = lambda: (_ for _ in ()).throw(RuntimeError('focus denied'))
        self.addCleanup(setattr, self.win, 'focus_force', original_focus)
        self.assertTrue(self.pet.show_main())
        self.assertTrue(any(name == 'show_main.focus' for name, _ in self.pet.errors))


class AnimationTests(PetTestCase):
    def test_animation_frames_do_not_close_open_chat(self):
        self.pet.open_chat()
        cloud = self.pet.cloud()
        for _ in range(12):
            self.pet.step()
            self.assertTrue(cloud.visible, '动画重排不能关闭刚打开的聊天框')

    def test_animation_frames_preserve_pending_single_click(self):
        self.pet.pet_click(_Event(widget=self.pet.canvas))
        pending = self.pet._click_at
        self.assertIsNotNone(pending)
        for _ in range(3):
            self.pet.step()
            self.assertEqual(self.pet._click_at, pending)
            self.assertIn(pending, self.win.tk.call('after', 'info'))

    def test_stop_still_closes_chat_and_cancels_pending_click(self):
        self.pet.open_chat()
        self.pet.pet_click(_Event(widget=self.pet.canvas))
        self.pet.step()
        self.pet.stop()
        self.assertFalse(self.pet.cloud().visible)
        self.assertIsNone(self.pet._click_at)
        self.assertIsNone(self.pet._timer)
        self.pet.stop()
        self.assertFalse(self.pet.cloud().visible)

    def test_frames_draw_eyes_and_blink(self):
        self.pet.draw(0)
        self.assertEqual(len(self.pet.canvas.find_withtag('eye-dot')), 2)
        self.pet.draw(3)
        self.assertEqual(len(self.pet.canvas.find_withtag('eye-line')), 2)
        self.assertEqual(len(self.pet.canvas.find_withtag('eye-dot')), 0)

    def test_step_advances_the_frame_and_keeps_a_timer(self):
        start = self.pet.frame
        self.pet.step()
        self.assertEqual(self.pet.frame, start + 1)
        self.assertIsNotNone(self.pet._timer)

    def test_rate_is_slow_when_idle_and_fast_while_working(self):
        for stage in pet_bus.STAGES:
            self.pet.machine.skip(stage)
        self.assertEqual(self.pet.mood(), 'idle')
        self.assertEqual(self.pet.interval(), pet_ui.IDLE_MS)
        self.pet.machine.start('script')
        self.assertEqual(self.pet.mood(), 'busy')
        self.assertEqual(self.pet.interval(), pet_ui.ACTIVE_MS)

    def test_paused_and_worried_moods(self):
        self.pet.agent.pause('配额用完')
        self.assertEqual(self.pet.mood(), 'paused')
        self.pet.agent.resume()
        self.pet.agent.fail('keyframe', '命中内容审核', attempt=4)
        self.assertEqual(self.pet.mood(), 'worry')

    def test_stop_cancels_the_timer(self):
        self.pet.step()
        self.pet.stop()
        self.assertIsNone(self.pet._timer)

    def test_step_never_stacks_two_timers(self):
        """build() 已经排了一个定时器，再手动 step()（自测与调试里都在用）不能叠出第二个。

        叠了就是双倍频，而且关窗时只取消得掉最后一个——剩下那个到期报 invalid command name "…step"。
        """
        win = self.tk.Tk()
        win.withdraw()
        destroyed = False

        def animation_jobs():
            # after info 返回 after#N；回调名称在每个任务的详细信息里。
            return {
                str(job) for job in win.tk.call('after', 'info')
                if str(win.tk.call('after', 'info', job)[0]).endswith('step')
            }

        try:
            fake = FakeDesktop(self.tk, self.ttk, win)
            fake.root = Path(self.tmp.name)
            pet = pet_ui.attach(fake, autostart=False)
            unrelated = win.after(60000, lambda: None)
            self.assertEqual(animation_jobs(), {pet._timer}, 'build 必须登记唯一动画任务')
            for _ in range(2):
                previous = pet._timer
                pet.step()
                self.assertEqual(animation_jobs(), {pet._timer}, '宠物定时器叠了第二个')
                self.assertNotIn(previous, win.tk.call('after', 'info'), '旧动画任务未撤销')
                self.assertIn(unrelated, win.tk.call('after', 'info'), '不应撤销其他任务')
            win.destroy()
            destroyed = True
            self.assertEqual(animation_jobs(), set(), '窗口销毁后还留着宠物定时器')
            self.assertIsNone(pet._timer, '销毁后应清除动画任务登记')
        finally:
            # 清理失败探针留下的任务，不捕获或替换测试断言。
            for job in win.tk.call('after', 'info'):
                win.tk.call('after', 'cancel', job)
            if not destroyed:
                win.destroy()


class SeamTests(PetTestCase):
    def test_stage_queue_reports_the_drain_and_forwards_it(self):
        seen = []
        box = pet_ui.StageQueue("keyframe", lambda stage, item: seen.append((stage, item)))
        item = (True, "自动补首帧完成：3 张")
        box.put(item)
        self.assertEqual(box.get_nowait(), item)
        self.assertEqual(seen, [("keyframe", item)])

    def test_stage_queue_forwards_the_rest_of_the_api(self):
        box = pet_ui.StageQueue("video")
        box.put((False, "失败"))
        self.assertFalse(box.empty())
        self.assertEqual(box.get(timeout=1), (False, "失败"))
        self.assertTrue(box.empty())
        self.assertEqual(box.qsize(), 0)

    def test_broken_sink_never_breaks_the_drain(self):
        def boom(stage, item):
            raise RuntimeError("sink 自己炸了")
        box = pet_ui.StageQueue("assets", boom)
        box.put((True, "自动补资产完成"))
        self.assertEqual(box.get_nowait(), (True, "自动补资产完成"))
        self.assertEqual(box.errors, [('sink', 'sink 自己炸了')],
                         '通知支线失败可降级，但必须留下可核原因')

    def test_status_var_keeps_the_original_text(self):
        var = pet_ui.watch_status(self.fake, self.pet)
        self.assertIs(var, self.fake.status)
        self.assertTrue(getattr(var, "_petWatched", False))
        var.set("已自动生成定稿。")
        self.assertEqual(var.get(), "已自动生成定稿。")
        self.assertEqual(self.pet.last_status, "已自动生成定稿。")
        var.set("已自动生成定稿。")
        self.assertEqual(len(self.pet.agent.notifier.pending), 1)

    def test_status_var_wraps_the_existing_variable_exactly_once(self):
        var = pet_ui.watch_status(self.fake, self.pet)
        self.assertIs(var, self.fake.status)
        self.assertIs(pet_ui.watch_status(self.fake, self.pet), var)
        var.set("只记一笔")
        var.set("只记一笔")
        self.assertEqual(len(self.pet.agent.notifier.pending), 1)

    def test_watch_status_without_a_status_var_is_a_noop(self):
        class Bare:
            pass
        self.assertIsNone(pet_ui.watch_status(Bare(), self.pet))

    def test_drain_success_without_an_artifact_stays_paused(self):
        self.pet.drain("keyframe", (True, "自动补首帧完成：3 张"))
        pet_ui.pump(self.fake)
        kinds = [(item["kind"], item["stage"]) for item in self.pet.bus.history]
        self.assertIn(("stage.paused", "keyframe"), kinds)
        self.assertNotIn(("stage.completed", "keyframe"), kinds)

    def test_report_done_without_an_artifact_cannot_complete_a_stage(self):
        self.pet.report_done("video", "自动补视频完成：1 个镜头")
        pet_ui.pump(self.fake)
        kinds = [(item["kind"], item["stage"]) for item in self.pet.bus.history]
        self.assertIn(("stage.paused", "video"), kinds)
        self.assertNotIn(("stage.completed", "video"), kinds)

    def test_drain_failure_goes_through_the_classifier(self):
        first = self.pet.drain("video", (False, "自动补视频未完成：HTTP 503 服务不可用"))
        self.assertEqual(first["category"], "server")
        self.assertTrue(first["allow"])
        self.assertEqual(self.pet.attempts["video"], 1)
        # 第 63 期任务 2.1～2.11：视频生成的重试上限是 2 次（与用户设的上限取小），
        # 第三次失败就等您确认，不再自动重来。
        second = self.pet.drain("video", (False, "自动补视频未完成：HTTP 503 服务不可用"))
        self.assertTrue(second["allow"])
        self.assertEqual(self.pet.attempts["video"], 2)
        last = self.pet.drain("video", (False, "自动补视频未完成：HTTP 503 服务不可用"))
        self.assertFalse(last["allow"])
        self.assertEqual(self.pet.attempts["video"], 0)
        self.assertEqual(len(self.pet.agent.failures), 1)
        self.assertEqual(self.pet.agent.failures[0]["policy"], "manual")   # 视频用尽后是「待您处理」
        self.pet.drain("video", (True, "自动补视频完成：1 个镜头"))
        self.assertEqual(self.pet.attempts["video"], 0)

    def test_tap_reports_after_the_original_action(self):
        order = []

        def action():
            order.append("action")
            return "结果"

        self.assertEqual(pet_ui.tap(self.fake, "导出交付", action), "结果")
        self.assertEqual(order, ["action"])
        pet_ui.pump(self.fake)
        item = [event for event in self.pet.bus.history if event["kind"] == "intent.command"][-1]
        self.assertEqual((item["text"], item["source"]), ("导出交付", "button"))

    def test_tap_keeps_the_error_for_the_caller(self):
        def boom():
            raise ValueError("按钮自己报错")
        with self.assertRaises(ValueError):
            pet_ui.tap(self.fake, "导出交付", boom)

    def test_pump_on_a_desktop_without_pet_is_a_noop(self):
        class Bare:
            pass
        self.assertEqual(pet_ui.pump(Bare()), 0)


class RemovedFeaturesTests(PetTestCase):
    """第 22 期：用户要的「删除独立小窗／自绘气泡」——两个功能连同它们的对象一起没有。"""

    def test_the_objects_and_the_methods_are_gone(self):
        for name in ('window', '_window', 'toast'):
            self.assertFalse(hasattr(self.pet, name), name + ' 还留在宠物身上')
        for name in ('open_window', 'close_window', 'toggle_window', 'open_toast',
                     'close_toast', 'toggle_toast', 'toast_action', 'notify'):
            self.assertFalse(hasattr(pet_ui.Pet, name), name + ' 还挂在宠物类上')
        # 第 44 期：quit_app 按用户附件回到功能栏最后一行（附件里那一项就是「退出」），
        # 所以它不再进这张「删过的清单」——它现在的判据在 MenuFeedbackTests／QuitTests 里。
        self.assertTrue(hasattr(pet_ui.Pet, 'quit_app'))

    def test_the_menu_has_no_entry_for_them(self):
        for name in ('window', 'toast'):
            self.assertNotIn(name, self.pet.menu_index, name + ' 还挂在功能栏上')

    def test_attach_no_longer_takes_the_two_switches(self):
        import inspect
        params = inspect.signature(pet_ui.attach).parameters
        self.assertNotIn('window', params)
        self.assertNotIn('toast', params)

    def test_closing_the_main_window_just_closes(self):
        """常驻模式没了：桌面问「要不要收进宠物窗」时一律答「不收」，关窗就是关程序。"""
        self.assertFalse(self.pet.hide_to_pet())


class DesktopSeamTests(unittest.TestCase):
    """真接缝：Desktop 上确实挂上了宠物，且 _tick_once 的收尾真的分发事件。"""

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def test_desktop_carries_the_pet_and_wrapped_seams(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        win = self.tk.Tk(); win.withdraw()
        try:
            from desktop import Desktop
            d = Desktop(win, root=PROGRAM)
            self.assertTrue(hasattr(d, "pet"))
            for name in ("final_queue", "edit_queue", "keyframe_queue",
                         "asset_queue", "video_queue", "handoff_queue"):
                with self.subTest(name=name):
                    box = getattr(d.auto, name)
                    self.assertIsInstance(box, pet_ui.StageQueue)
                    if name in ("keyframe_queue", "asset_queue"):
                        # 这两类任务必须由界面线程复核真实产物后才允许发送完成事件。
                        self.assertIsNone(box.sink)
                    else:
                        self.assertIs(box.sink.__self__, d.pet)
                        self.assertEqual(box.sink.__name__, "drain")
            self.assertIsInstance(d.status, self.tk.StringVar)
            self.assertTrue(getattr(d.status, "_petWatched", False))
            d.status.set("接缝自检：状态栏照旧")
            self.assertEqual(d.status.get(), "接缝自检：状态栏照旧")
            self.assertTrue(getattr(self.tk.Variable, "_dramaGuarded", False))
            self.assertIsNotNone(d.pet.canvas)
            # 第 R2933 期：三虎簇的真实宿主是侧栏底栏 pet_dock，不再是标题行。
            self.assertEqual(str(d.pet.canvas.winfo_parent()), str(d.pet_dock))
            stubs = [(box.stage, box) for box in (d.auto.final_queue, d.auto.edit_queue, d.auto.keyframe_queue,
                                                  d.auto.asset_queue, d.auto.video_queue, d.auto.handoff_queue)]
            self.assertEqual(sorted(stage for stage, _ in stubs),
                             sorted(["final", "edit", "keyframe", "assets", "video", "delivery"]))
        finally:
            win.destroy()

    def test_tk_gc_guard_skips_worker_threads(self):
        """非主线程回收 Tk 对象时不再调 Tcl——无人值守收尾阶段卡死的来源。

        tkinter 里只有 Variable、Image（PhotoImage）、font.Font 三个类型会在 __del__ 里调 Tcl；
        实机日志显示复选框图标（PhotoImage）被 worker 线程回收时刷出 32 条
        RuntimeError: main thread is not in main loop，这才是卡死链条上真正频繁的那一环。
        """
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import threading
        from tkinter import font as tkfont
        import desktop as desktop_module
        desktop_module.protect_tk_gc()
        win = self.tk.Tk(); win.withdraw()
        try:
            var = self.tk.StringVar(master=win, value="非主线程回收")
            image = self.tk.PhotoImage(master=win, width=1, height=1)
            lettering = tkfont.Font(root=win, family="TkDefaultFont", size=10)
            calls = [(self.tk.Variable.__del__, var), (self.tk.Image.__del__, image),
                     (tkfont.Font.__del__, lettering)]
            errors = []

            def worker():
                for function, target in calls:
                    try:
                        function(target)
                    except Exception as exc:
                        errors.append(repr(exc))

            thread = threading.Thread(target=worker)
            thread.start(); thread.join(20)
            self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])
            # 守卫直接放弃回收，Tcl 侧的东西仍然有效——证明这几次 __del__ 都没跨线程调 Tcl
            self.assertEqual(var.get(), "非主线程回收")
            self.assertEqual(image.width(), 1)
            for cls in (self.tk.Variable, self.tk.Image, tkfont.Font):
                self.assertTrue(getattr(cls, "_dramaGuarded", False))
            # 三个对象都被拦下来排队，等主线程释放：就地释放会把 Tkapp 一起在 worker 里析构。
            # 队列是进程级的：同进程先前用例在 worker 线程回收的 Tk 对象也可能还没排干，
            # 按对象身份断言本批三者都在队列里，不要求队列恰好只有它们。
            pending = desktop_module._PENDING_TK_GC
            for _function, target in calls:
                self.assertTrue(any(item is target for item in pending),
                                'worker 线程回收的 Tk 对象必须进排队等主线程释放')
            desktop_module.drain_tk_gc()
            self.assertEqual(desktop_module._PENDING_TK_GC, [])
        finally:
            win.destroy()

    def test_tick_once_drains_into_the_bus(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        win = self.tk.Tk(); win.withdraw()
        try:
            from desktop import Desktop
            d = Desktop(win, root=PROGRAM)
            d.auto.handoff_ticket += 1
            ticket = d.auto.handoff_tasks.submit(d.auto.handoff_ticket)
            d.auto.handoff_queue.put((ticket, True, "自动交接包已整理：exports/MASTER.mp4", "sig"))
            from unittest import mock
            from orchestrator import stage_completion_service
            with mock.patch.object(stage_completion_service, 'completion_evidence',
                                   return_value=(True, '')) as evidence:
                d._tick_once()
            evidence.assert_called_once_with(d.root, 'delivery', getattr(d.studio, 'auto_edit_ready', None))
            kinds = [(item["kind"], item.get("stage")) for item in d.pet.bus.history]
            # REQ-S13-54：此处显式注入产物核验通过，真实空项目拒绝完成另在下一用例验证。
            self.assertIn(("stage.completed", "delivery"), kinds)
            self.assertIn("自动交接包已整理：exports/MASTER.mp4", d.pet.last_status)
        finally:
            win.destroy()

    def test_handoff_success_text_without_artifacts_never_completes(self):
        """REQ/DES-S13-54：真实空项目入队成功文字仍须通过产物门禁。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from desktop import Desktop
        with tempfile.TemporaryDirectory() as folder:
            win = self.tk.Tk(); win.withdraw()
            try:
                d = Desktop(win, root=folder)
                d.auto.handoff_ticket += 1
                ticket = d.auto.handoff_tasks.submit(d.auto.handoff_ticket)
                d.auto.handoff_queue.put((ticket, True, "自动交接包已整理：exports/MASTER.mp4", "sig"))
                history_start = len(d.pet.bus.history)
                d._tick_once()
                events = d.pet.bus.history[history_start:]
                kinds = [(item['kind'], item.get('stage')) for item in events]
                self.assertIn(('stage.paused', 'delivery'), kinds)
                self.assertNotIn(('stage.completed', 'delivery'), kinds)
                paused = [item for item in events
                          if item['kind'] == 'stage.paused' and item.get('stage') == 'delivery']
                self.assertIn('待校验', paused[-1]['text'])
                self.assertIn('自动交接包已整理：exports/MASTER.mp4', d.pet.last_status)
            finally:
                win.destroy()

    def test_button_seam_reports_the_label(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        win = self.tk.Tk(); win.withdraw()
        try:
            from desktop import Desktop
            d = Desktop(win, root=PROGRAM)
            button = d.button(d.content, "导出交付", lambda: "ok")
            button.invoke()
            pet_ui.pump(d)
            item = [event for event in d.pet.bus.history if event["kind"] == "intent.command"][-1]
            self.assertEqual(item["text"], "导出交付")
        finally:
            win.destroy()


class FrameBatchSeamTests(unittest.TestCase):
    """真接缝：Desktop.pet_frame_batch 的每条出口都给人话，且从不碰付费通道。"""

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def setUp(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from desktop import Desktop
        self.win = self.tk.Tk()
        self.win.withdraw()
        self.addCleanup(self.win.destroy)
        self.d = Desktop(self.win, root=PROGRAM)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name) / "p"

    def project_with_a_gap(self):
        work = self.base / "storyboard" / "分镜拆分"
        work.mkdir(parents=True, exist_ok=True)
        source = work / "EP001_分镜.json"
        source.write_text(json.dumps({"episode_id": "EP001", "shots": [
            {"id": "SH001", "frame": "frames/SH001.png"},
            {"id": "SH002", "frame": "frames/SH002.png"}]}, ensure_ascii=False), encoding="utf-8")
        (self.base / "ui_settings.json").write_text(json.dumps(
            {"frame_json": "storyboard/分镜拆分/EP001_分镜.json"}, ensure_ascii=False), encoding="utf-8")
        self.d.root = self.base
        self.d.studio = object()
        return source

    def verified_frames(self, source):
        """写入真实可解码的首帧并登记来源证据，模拟已通过导入确认的成果。"""
        from tests.image_fixtures import png
        from keyframe_evidence import make_evidence
        frames = self.base / "storyboard" / "frames"
        frames.mkdir(parents=True, exist_ok=True)
        data = png((16, 9))
        episode = json.loads(source.read_text(encoding="utf-8"))
        for shot in episode["shots"]:
            path = frames / Path(shot["frame"]).name
            path.write_bytes(data)
            shot["frame_evidence"] = make_evidence(source, episode, shot, path)
        source.write_text(json.dumps(episode, ensure_ascii=False), encoding="utf-8")

    def test_it_says_nothing_without_a_project(self):
        self.assertEqual(self.d.pet_frame_batch(), "")
        self.assertEqual(self.d.pet.firstframe_batch(), "")

    def test_auto_keyframe_without_a_storyboard_finishes_as_failed(self):
        emitted = []
        self.d.pet._emit = lambda kind, **payload: emitted.append((kind, payload))
        text = self.d.pet_frame_batch(trigger='auto')
        self.assertIn('未找到可用分镜', text)
        self.assertEqual(emitted, [('stage.failed', {'stage': 'keyframe', 'error': text})])

    def test_it_says_nothing_when_there_is_no_gap(self):
        source = self.project_with_a_gap()
        self.verified_frames(source)
        self.assertEqual(self.d.pet_frame_batch(), "", "没有缺口就一个字都不说")

    def test_auto_keyframe_with_no_gap_finishes_as_completed(self):
        source = self.project_with_a_gap()
        self.verified_frames(source)
        emitted = []
        self.d.pet._emit = lambda kind, **payload: emitted.append((kind, payload))
        text = self.d.pet_frame_batch(trigger='auto')
        self.assertEqual(text, '首帧已齐全，无需制作')
        self.assertEqual(emitted, [('stage.completed', {'stage': 'keyframe', 'text': text})])

    def test_a_missing_asset_registry_is_reported_not_raised(self):
        self.project_with_a_gap()
        self.d.keyframe_settings = lambda: []
        self.assertIn("找不到资产清单", self.d.pet_frame_batch())
        self.assertFalse(self.d.auto.keyframe_busy)

    def test_it_names_the_missing_local_settings(self):
        self.project_with_a_gap()
        self.d.keyframe_settings = lambda: ["model"]
        text = self.d.pet_frame_batch()
        self.assertIn("还没配好", text)
        self.assertIn("model", text)
        self.assertFalse(self.d.auto.keyframe_busy)

    def test_it_names_the_blocked_shots(self):
        self.project_with_a_gap()
        self.d.keyframe_settings = lambda: []
        self.d.batch_blockers = lambda source, pending: [(shot["id"], "缺参考图") for shot in pending]
        text = self.d.pet_frame_batch()
        self.assertIn("2 镜都无法生成", text)
        self.assertIn("缺参考图", text)              # 原因与引擎逐镜跳过时同一句话
        self.assertFalse(self.d.auto.keyframe_busy)

    def test_the_unattended_path_skips_a_batch_it_already_handled(self):
        """无人值守先判重再派发：同一批（同一份分镜、同样缺几张参考图）只跑一次。

        批次还在跑的那几十秒里清单没变，判重必须发生在派发之前，否则同一批会被重复下单；
        用户按下的按钮不受这份记忆影响，显式操作永远照做。
        """
        self.project_with_a_gap()
        import infra.project_settings as project_settings
        project_settings.set_auto_keyframe(self.base, True)
        self.d.keyframe_settings = lambda: []
        self.d.batch_blockers = lambda source, pending: []
        self.d.keyframe_signature = lambda source, pending: ("签名", len(pending))
        self.d.auto.keyframe_signature = ("签名", 2)
        import keyframe_comfy
        original = keyframe_comfy.auto_batch
        started = []
        keyframe_comfy.auto_batch = lambda source, log, stop=None: started.append(1) or "批次结束"
        try:
            self.d.poll_auto_keyframe()
            self.assertEqual(started, [], "这一批已经在跑了，不能再下一单")
            self.assertFalse(self.d.auto.keyframe_busy)
            text = self.d.pet_frame_batch()          # 显式按下：同一批照样派发
            self.assertIn("已按分镜顺序派发 2 镜首帧", text)
            self.assertTrue(self.d.auto.keyframe_busy)
        finally:
            keyframe_comfy.auto_batch = original
            self.d.auto.keyframe_busy = False
            while not self.d.auto.keyframe_queue.empty():
                self.d.auto.keyframe_queue.get_nowait()

    def test_it_says_nothing_while_another_batch_runs(self):
        self.project_with_a_gap()
        self.d.auto.keyframe_busy = True
        try:
            self.assertIn("已有制作任务在跑", self.d.pet_frame_batch())
        finally:
            self.d.auto.keyframe_busy = False

    def test_auto_keyframe_while_busy_finishes_as_failed(self):
        self.project_with_a_gap()
        self.d.auto.keyframe_busy = True
        emitted = []
        self.d.pet._emit = lambda kind, **payload: emitted.append((kind, payload))
        try:
            text = self.d.pet_frame_batch(trigger='auto')
        finally:
            self.d.auto.keyframe_busy = False
        self.assertIn('已有制作任务在跑', text)
        self.assertEqual(emitted, [('stage.failed', {'stage': 'keyframe', 'error': text})])

    def test_it_dispatches_the_free_local_batch(self):
        self.project_with_a_gap()
        self.d.keyframe_settings = lambda: []
        self.d.batch_blockers = lambda source, pending: []
        self.d.keyframe_signature = lambda source, pending: ("签名", len(pending))
        import keyframe_comfy
        original = keyframe_comfy.auto_batch
        keyframe_comfy.auto_batch = lambda source, log, stop=None: "无人值守首帧批次结束：处理 2 镜"
        try:
            text = self.d.pet_frame_batch()
            self.assertIn("已按分镜顺序派发 2 镜首帧", text)
            self.assertTrue(self.d.auto.keyframe_busy)
            _ticket, ok, value, signature = self.d.auto.keyframe_queue.get(timeout=20)
            self.assertTrue(ok)
            self.assertIn("处理 2 镜", value)
            self.assertEqual(signature, ("签名", 2))
        finally:
            keyframe_comfy.auto_batch = original
            self.d.auto.keyframe_busy = False
            while not self.d.auto.keyframe_queue.empty():
                self.d.auto.keyframe_queue.get_nowait()

    def test_the_shared_signature_contains_the_missing_references(self):
        """无人值守与一键执行共用同一份指纹：两条路派发的批次不会互相再触发一次。"""
        source = self.project_with_a_gap()
        pending = [{"id": "SH001"}, {"id": "SH002"}]
        self.assertEqual(self.d.keyframe_signature(source, pending),
                         (str(source), (("SH001", 0), ("SH002", 0))))


class PetTextSeamTests(unittest.TestCase):
    """真接缝：宿主把宠物的「查看详情」接到全程序唯一的只读文本窗口上（不另造窗口）。"""

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def setUp(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        # 这一条只看「宠物的详情窗口」，与项目无关：把打开项目那一步挡住。
        # 不挡的话，win.update() 会真的去开本机项目、把无人值守资产那一批跑起来，
        # 状态栏就不再是这一个用例说了算（与本仓库另外 140 处同一条隔离）。
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        from desktop import Desktop
        self.win = self.tk.Tk()
        self.win.withdraw()
        self.addCleanup(self.win.destroy)
        self.d = Desktop(self.win, root=PROGRAM)
        self.addCleanup(self.d.cancel_timers)

    def popup(self):
        return [w for w in self.win.winfo_children() if isinstance(w, self.tk.Toplevel)][0]

    def buttons_of(self, win):
        from tkinter import ttk
        # BaseDialog 把正文与统一动作栏分层；宠物仍复用同一个提示窗，控件不再是
        # Toplevel 的直接子项。按窗口后代取控件，断言的是用户可见内容而非布局实现。
        found = []
        def walk(widget):
            for child in widget.winfo_children():
                if isinstance(child, ttk.Button):
                    found.append(child)
                walk(child)
        walk(win)
        return found

    def text_boxes_of(self, win):
        found = []
        def walk(widget):
            for child in widget.winfo_children():
                if isinstance(child, self.tk.Text):
                    found.append(child)
                walk(child)
        walk(win)
        return found

    def test_the_text_window_shows_what_it_was_given(self):
        self.d.pet_show_text("待确认详情", "第一行\n第二行", "已复制")
        self.win.update()
        popup = self.popup()
        boxes = self.text_boxes_of(popup)
        self.assertEqual(boxes[0].get("1.0", "end-1c"), "第一行\n第二行")
        self.assertEqual([str(button.cget("text")) for button in self.buttons_of(popup)], ["复制详情"])

    def test_the_copy_button_still_goes_through_the_shared_window(self):
        """复制仍然只有一处实现（prompt_window.copy_text）：按钮名字换了，行为没换。"""
        self.d.pet_show_text("待确认详情", "哨兵文字", "已复制")
        self.win.update()
        popup = self.popup()
        from infra import clipboard_lock
        with clipboard_lock.hold():
            self.buttons_of(popup)[0].invoke()
            self.win.update()
            self.assertEqual(self.win.clipboard_get(), "哨兵文字")
        self.assertFalse(popup.winfo_exists(), "复制成功后仍然关窗")
        self.assertEqual(self.d.status.get(), "已复制")


class DesktopPetSeamTests(unittest.TestCase):
    """第 23 期真接缝：Desktop.pet_goto（切页）与 Desktop.pet_advance（提前叫醒下一步）。"""

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def setUp(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from desktop import Desktop
        import entitlement_service
        from unittest.mock import patch
        # 本组只验切页与续跑接缝；会员闸门（真实账号状态）另有 test_account_* 覆盖，隔离后结果不随本机登录态变化。
        from orchestrator.account_controller import AccountController
        allowed = entitlement_service.Entitlement(entitlement_service.VALID, {'state': 'active'})
        self.enterContext(patch.object(AccountController, 'entitlement', return_value=allowed))
        self.win = self.tk.Tk()
        self.win.withdraw()
        self.addCleanup(self.win.destroy)
        self.d = Desktop(self.win, root=PROGRAM)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name) / "p"
        (self.base / "episode").mkdir(parents=True, exist_ok=True)
        (self.base / "episode" / "assets.json").write_text("{}", encoding="utf-8")

    # ── 切页 ────────────────────────────────────────────────────────────────
    def test_it_says_nothing_without_a_project(self):
        self.assertEqual(self.d.pet_goto("edit"), "")
        self.assertEqual(self.d.pet_advance("video"), "")
        self.assertEqual(self.d.pet_goto("不存在的步骤"), "")

    def test_it_hands_the_page_index_to_show(self):
        """页序号只认 pet_state.PAGE_OF 那一份，且真的落到 show() 上。"""
        from desktop import PAGES
        import infra.pet_state as pet_state
        self.d.root = self.base
        seen = []
        self.d.show = lambda index, video_mode=None: seen.append(index) or PAGES[index]
        self.assertEqual(self.d.pet_goto("edit"), PAGES[pet_state.PAGE_OF["edit"]])
        self.assertEqual(seen, [pet_state.PAGE_OF["edit"]])

    def test_a_broken_page_is_reported_not_raised(self):
        self.d.root = self.base
        self.d.studio = object()

        def boom(index, video_mode=None):
            raise RuntimeError("页面坏了")

        self.d.show = boom
        self.assertEqual(self.d.pet_goto("edit"), "")
        self.assertIn("切页失败", self.d.status.get())

    # ── 提前叫醒下一步 ──────────────────────────────────────────────────────
    def test_it_moves_only_the_due_time(self):
        self.d.root = self.base
        self.d.auto.video_due = 0
        self.assertIn("视频生成", self.d.pet_advance("video"))
        self.assertEqual(self.d.auto.video_due, 0)
        self.d.auto.video_due = time.monotonic() + 60      # 正常节流里还没到点的那一步
        self.assertIn("视频生成", self.d.pet_advance("video"))
        self.assertEqual(self.d.auto.video_due, 0, "把这一步的下一次轮询提前到现在")

    def test_a_step_in_backoff_is_left_alone(self):
        """失败后的 5 分钟退避不能被一次推进打乱（与 kick_unattended 同一条规矩）。"""
        from desktop import UNATTENDED_BACKOFF_FLOOR
        self.d.root = self.base
        far = time.monotonic() + UNATTENDED_BACKOFF_FLOOR + 60
        self.d.auto.keyframe_due = far
        self.assertEqual(self.d.pet_advance("keyframe"), "")
        self.assertEqual(self.d.auto.keyframe_due, far)

    def test_a_busy_step_is_left_alone(self):
        self.d.root = self.base
        self.d.auto.asset_busy = True
        self.assertEqual(self.d.pet_advance("assets"), "")
        self.d.auto.asset_busy = False

    def test_a_step_without_an_unattended_poll_says_nothing(self):
        self.d.root = self.base
        self.assertEqual(self.d.pet_advance("script"), "", "剧本没有无人值守轮询")
        self.assertEqual(self.d.pet_advance("audio"), "", "配音没有无人值守轮询")

    def test_the_desktop_hands_over_the_foreground_judge(self):
        """第 30 期第 3 条：真宿主把「前台窗口是不是本进程」挂到宠物上，假宿主不挂（＝不拦）。"""
        self.assertIs(self.d.pet.front, pet_ui.our_process_in_front)

    def test_the_table_covers_exactly_the_steps_that_have_a_poll(self):
        from desktop import PET_STAGE_POLL
        from orchestrator.desktop_auto_state import flow_slot
        import pet_bus
        for stage, name in PET_STAGE_POLL.items():
            self.assertIn(stage, pet_bus.STAGES)
            owner, prefix = flow_slot(self.d, name)
            self.assertTrue(hasattr(owner, prefix + "_due"), name + " 必须真的有这一步的轮询")

    # ── 自动开始某一步（第 67 期任务 5）─────────────────────────────────────
    def test_it_opens_the_unattended_switch_then_starts_the_step(self):
        import infra.project_settings as project_settings
        self.d.root = self.base
        self.d.auto.asset_due = 0
        self.assertIn("资产管理", self.d.pet_start("assets"))
        self.assertTrue(project_settings.auto_asset(self.base), "无人值守开关替用户打开")
        self.assertEqual(self.d.auto.asset_due, 0, "顺手把这一步提前叫醒一轮")

    def test_a_step_without_an_unattended_poll_starts_nothing(self):
        import stage_config
        self.d.root = self.base
        # R2862 契约：自动启动先过制作锁门禁；补齐剧本必填锁后才轮到「没有无人值守轮询」的判定。
        stage_config.put_production_locks(self.base, {'delivery_format': '两者都交付'})
        self.assertEqual(self.d.pet_start("script"), "", "剧本没有无人值守轮询")
        self.assertEqual(self.d.pet_start("audio"), "", "配音没有无人值守轮询")

    def test_auto_structure_without_source_emits_a_failure_instead_of_sticking_active(self):
        """自动链派到结构剧本却没有原稿时，必须收场为失败而非静默卡住。"""
        self.d.root = self.base
        emitted = []
        self.d.pet._emit = lambda kind, **payload: emitted.append((kind, payload))
        text = self.d.pet_script_structure_batch(trigger='auto')
        self.assertIn('未找到剧本准备阶段的剧本', text)
        self.assertEqual(emitted, [('stage.failed', {
            'stage': 'script_structure', 'error': text})])

    def test_stage_event_delivery_failure_is_not_silently_swallowed(self):
        """阶段权威通知坏了必须上抛，不能假装自动链已经收场。"""
        self.d.root = self.base

        def broken_emit(*_args, **_kwargs):
            raise RuntimeError('阶段事件总线不可用')

        self.d.pet._emit = broken_emit
        with self.assertRaisesRegex(RuntimeError, '阶段事件总线不可用'):
            self.d.pet_script_structure_batch(trigger='auto')

    def test_auto_structure_while_another_worker_is_busy_is_queued_once(self):
        """后台占用是暂态：自动链保留 active，收尾后会经 L3 重新派发。"""
        self.d.root = self.base
        self.d.worker = True
        emitted = []
        self.d.pet._emit = lambda kind, **payload: emitted.append((kind, payload))

        text = self.d.pet_script_structure_batch(trigger='auto')
        self.assertIn('当前后台任务完成后将自动制作结构剧本', text)
        self.assertTrue(self.d._auto_structure_retry)
        self.assertEqual(emitted, [])

    def test_auto_structure_sync_failure_stays_in_that_stage(self):
        """正稿没同步进分镜输入时，不能伪装结构阶段已完成后才让下游失败。"""
        import script_contract
        import stage_exec
        import storyboard_selection

        self.d.root = self.base
        source = self.base / 'writing' / 'script_raw.md'
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text('# 自然剧本', encoding='utf-8')
        output = script_contract.canonical_structured_script_path(self.base)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('# 结构化剧本', encoding='utf-8')
        emitted = []
        self.d.pet._emit = lambda kind, **payload: emitted.append((kind, payload))
        self.d.async_ = lambda work, received, **_kwargs: received(work())
        old_run, old_sync = stage_exec.run, storyboard_selection.sync_structured_script
        stage_exec.run = lambda *_args, **_kwargs: {'ok': True}
        storyboard_selection.sync_structured_script = lambda _project: []
        self.addCleanup(setattr, stage_exec, 'run', old_run)
        self.addCleanup(setattr, storyboard_selection, 'sync_structured_script', old_sync)

        self.assertIn('已自动开始', self.d.pet_script_structure_batch(trigger='auto'))
        self.assertEqual(emitted[0][0], 'stage.executing')
        self.assertEqual(emitted[1][0], 'stage.failed')
        self.assertEqual(emitted[1][1]['stage'], 'script_structure')
        self.assertIn('同步初步分镜失败', emitted[1][1]['error'])

    def test_auto_structure_bad_selection_settings_stays_in_that_stage(self):
        """损坏的分镜选择配置也必须收敛为当前阶段失败，而非漏出后台回调。"""
        import script_contract
        import stage_exec
        import storyboard_selection

        self.d.root = self.base
        source = self.base / 'writing' / 'script_raw.md'
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text('# 自然剧本', encoding='utf-8')
        output = script_contract.canonical_structured_script_path(self.base)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('# 结构化剧本', encoding='utf-8')
        emitted = []
        self.d.pet._emit = lambda kind, **payload: emitted.append((kind, payload))
        self.d.async_ = lambda work, received, **_kwargs: received(work())
        old_run, old_sync = stage_exec.run, storyboard_selection.sync_structured_script
        stage_exec.run = lambda *_args, **_kwargs: {'ok': True}
        storyboard_selection.sync_structured_script = lambda _project: (_ for _ in ()).throw(AttributeError('选择配置格式错误'))
        self.addCleanup(setattr, stage_exec, 'run', old_run)
        self.addCleanup(setattr, storyboard_selection, 'sync_structured_script', old_sync)

        self.d.pet_script_structure_batch(trigger='auto')
        self.assertEqual(emitted[-1][0], 'stage.failed')
        self.assertEqual(emitted[-1][1]['stage'], 'script_structure')
        self.assertIn('选择配置格式错误', emitted[-1][1]['error'])

    def test_auto_storyboard_without_input_emits_a_failure_instead_of_sticking_active(self):
        """自动链派到分镜却没有结构剧本输入时，必须收场为失败。"""
        self.d.root = self.base
        emitted = []
        self.d.pet._emit = lambda kind, **payload: emitted.append((kind, payload))
        text = self.d.pet_storyboard_batch(trigger='auto')
        self.assertIn('未选择结构剧本', text)
        self.assertEqual(emitted, [('stage.failed', {
            'stage': 'storyboard', 'error': text})])

    def test_auto_storyboard_bad_selection_state_emits_a_failure(self):
        """读取已选结构剧本异常也要收场，不能把自动链留在执行中。"""
        import storyboard_selection

        self.d.root = self.base
        emitted = []
        self.d.pet._emit = lambda kind, **payload: emitted.append((kind, payload))
        old_selected = storyboard_selection.selected_many
        storyboard_selection.selected_many = lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError('选择配置已损坏'))
        self.addCleanup(setattr, storyboard_selection, 'selected_many', old_selected)

        text = self.d.pet_storyboard_batch(trigger='auto')
        self.assertIn('读取结构剧本输入失败：选择配置已损坏', text)
        self.assertEqual(emitted, [('stage.failed', {
            'stage': 'storyboard', 'error': text})])

    def test_auto_storyboard_with_an_adopted_result_completes_instead_of_waiting_forever(self):
        """已生成且已采用的分镜是自动链的正常终态，不应再空转 auto_adopt。"""
        self.d.root = self.base
        script = self.base / 'writing' / '第01集.md'
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text('# 第01集', encoding='utf-8')
        board = self.base / 'storyboard' / '分镜拆分' / 'EP001_分镜.json'
        board.parent.mkdir(parents=True, exist_ok=True)
        board.write_text(json.dumps({'episode_id':'EP001','title':'测试','source_script':'writing/第01集.md',
                                     'shots':[{'id':'SH001','location':'LOC_001','title':'开场'}]},
                                    ensure_ascii=False), encoding='utf-8')
        (self.base / 'ui_settings.json').write_text(json.dumps({
            'storyboard_scripts':['writing/第01集.md'],
            'adopted_storyboards':['storyboard/分镜拆分/EP001_分镜.json']}, ensure_ascii=False), encoding='utf-8')
        self.d.pet.auto.active = 'storyboard'
        emitted = []
        self.d.pet._emit = lambda kind, **payload: emitted.append((kind, payload))
        text = self.d.pet_storyboard_batch(trigger='auto')
        self.assertIn('均已生成并采用', text)
        self.assertEqual(emitted, [('stage.completed', {'stage':'storyboard','text':text})])

    def test_the_switch_table_covers_exactly_the_steps_with_a_poll(self):
        from desktop import PET_STAGE_POLL, UNATTENDED_SWITCH
        import infra.project_settings as project_settings
        self.assertEqual(sorted(UNATTENDED_SWITCH), sorted(PET_STAGE_POLL.values()),
                         "每一个无人值守轮询都要配一把能打开它的开关")
        for name in UNATTENDED_SWITCH.values():
            self.assertTrue(callable(getattr(project_settings, name, None)), name + " 必须真的存在")


class ClickCancelTests(PetTestCase):
    """R3012：点击宠物后的待决单击随指针挪开取消——「点击后鼠标一动，云朵照样弹出」不再发生。"""

    def test_move_beyond_tolerance_cancels_pending_single_click(self):
        pet = self.pet
        pet._click_xy = (100, 100)
        pet._chat_interaction._pending = 'job-1'
        pet._pet_move(SimpleNamespace(x_root=130, y_root=100))
        self.assertIsNone(pet._chat_interaction._pending)

    def test_small_move_keeps_pending(self):
        pet = self.pet
        pet._click_xy = (100, 100)
        pet._chat_interaction._pending = 'job-1'
        pet._pet_move(SimpleNamespace(x_root=102, y_root=102))
        self.assertEqual(pet._chat_interaction._pending, 'job-1')
        pet._chat_interaction.cancel_pending()          # 清场

    def test_leave_cancels_pending_single_click(self):
        pet = self.pet
        pet._click_xy = (100, 100)
        pet._chat_interaction._pending = 'job-1'
        pet._pet_away()
        self.assertIsNone(pet._chat_interaction._pending)

    def test_pet_click_records_pointer_origin(self):
        pet = self.pet
        pet.pet_click(SimpleNamespace(x_root=45, y_root=60))
        self.assertEqual(pet._click_xy, (45, 60))
        pet._chat_interaction.cancel_pending()          # 清场


class PetBroadcastGetattrForwardTests(unittest.TestCase):
    """C04：转发属性真正缺失时，AttributeError 指明原对象与属性名。"""

    def _pet(self):
        from orchestrator.pet_broadcast_state import PetBroadcastAliasesMixin

        class _Pet(PetBroadcastAliasesMixin):
            pass
        return _Pet()

    def test_missing_forward_field_names_state_object(self):
        pet = self._pet()
        pet.bstate = SimpleNamespace()
        with self.assertRaises(AttributeError) as ctx:
            pet.notice
        self.assertIn('SimpleNamespace', str(ctx.exception))
        self.assertIn('notice', str(ctx.exception))

    def test_missing_plain_attribute_names_owner_and_attribute(self):
        pet = self._pet()
        with self.assertRaises(AttributeError) as ctx:
            pet.no_such_attr
        self.assertIn('_Pet', str(ctx.exception))
        self.assertIn('no_such_attr', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
