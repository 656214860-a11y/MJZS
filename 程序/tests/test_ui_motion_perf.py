"""性能/资源轮：平滑滚动、按钮悬停渐变、拖窗口时只画外层框架（冻结／解冻）。

真 Tk（withdraw）；时间相关断言只用「不晚于」的宽松上限，帧由测试自己泵事件循环推进。
"""
import time
import tkinter as tk
import unittest
from tkinter import ttk
from types import SimpleNamespace

import ui_hover_fade
import ui_scroll
from desktop_layout import LayoutMixin
from desktop_layout_resize import ResizeCoalescer
from ui_rounded import button_specs
from ui_tokens import (HOVER_FADE_MS, HOVER_FADE_STEPS, SCROLL_FRAME_MS, SCROLL_SNAP_PX)
from ui_widgets import setup_styles


class TkCase(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(str(exc))
        self.root.geometry('+40+40')

    def tearDown(self):
        if hasattr(self, 'root'):
            self.root.destroy()

    def pump(self, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.root.update()
            time.sleep(.002)

    def pending_after(self):
        return len(self.root.tk.splitlist(self.root.tk.call('after', 'info')))


class EasedScrollTests(TkCase):
    def make_canvas(self, region_height=2000):
        canvas = tk.Canvas(self.root, width=200, height=200, highlightthickness=0,
                           scrollregion=(0, 0, 200, region_height))
        canvas.pack()
        self.root.update()
        return canvas

    def top_px(self, canvas, total=2000):
        return canvas.yview()[0] * total

    def test_first_step_is_synchronous_and_distance_matches_native_unit(self):
        canvas = self.make_canvas()
        reference = self.make_canvas()
        reference.yview_scroll(1, 'units')
        native = self.top_px(reference)
        ui_scroll.eased_scroll(canvas, 1)
        first = self.top_px(canvas)
        self.assertGreater(first, 0, '滚轮事件里就要有位移，不能等下一帧')
        self.assertLess(first, native, '缓动：第一步只走一部分')
        self.pump(.3)
        self.assertAlmostEqual(self.top_px(canvas), native, delta=SCROLL_SNAP_PX + 1)

    def test_motion_is_monotonic_ease_out_and_ends_idle(self):
        canvas = self.make_canvas()
        ui_scroll.eased_scroll(canvas, 3)
        positions = [self.top_px(canvas)]
        for _ in range(12):
            self.pump(SCROLL_FRAME_MS / 1000 + .004)
            positions.append(self.top_px(canvas))
        self.assertEqual(positions, sorted(positions))
        steps = [b - a for a, b in zip(positions, positions[1:]) if b > a]
        self.assertGreater(len(steps), 2, '要分多帧走完，而不是一步跳')
        self.assertGreaterEqual(steps[0], steps[-1], '缓出：越走越慢')
        self.assertFalse(canvas._eased_scroll.running)

    def test_consecutive_wheel_events_accumulate(self):
        canvas = self.make_canvas()
        reference = self.make_canvas()
        reference.yview_scroll(6, 'units')
        for _ in range(3):
            ui_scroll.eased_scroll(canvas, 2)
        self.pump(.4)
        self.assertAlmostEqual(self.top_px(canvas), self.top_px(reference), delta=SCROLL_SNAP_PX + 2)

    def test_clamped_at_both_ends_and_reverse_returns(self):
        canvas = self.make_canvas()
        ui_scroll.eased_scroll(canvas, 1000)
        self.pump(.6)
        self.assertAlmostEqual(canvas.yview()[1], 1.0, places=3)
        ui_scroll.eased_scroll(canvas, -1000)
        self.pump(.6)
        self.assertAlmostEqual(canvas.yview()[0], 0.0, places=3)

    def test_other_code_moving_the_canvas_cancels_the_animation(self):
        canvas = self.make_canvas()
        ui_scroll.eased_scroll(canvas, 8)
        canvas.yview_moveto(.5)  # 翻页键、拖滚动条、代码直接定位
        self.pump(.3)
        self.assertAlmostEqual(canvas.yview()[0], .5, places=2)
        self.assertFalse(canvas._eased_scroll.running)

    def test_non_scrollable_or_fixed_increment_canvas_falls_back_to_native(self):
        short = self.make_canvas(region_height=100)
        ui_scroll.eased_scroll(short, 3)
        self.assertEqual(short.yview(), (0.0, 1.0))
        fixed = self.make_canvas()
        fixed.configure(yscrollincrement=10)
        ui_scroll.eased_scroll(fixed, 2)
        self.assertAlmostEqual(self.top_px(fixed), 20, delta=1)
        self.assertFalse(fixed._eased_scroll.running)

    def test_destroy_cancels_pending_frames(self):
        canvas = self.make_canvas()
        before = self.pending_after()
        ui_scroll.eased_scroll(canvas, 5)
        self.assertGreater(self.pending_after(), before)
        canvas.destroy()
        self.pump(.1)
        self.assertEqual(self.pending_after(), before)

    def test_scroll_form_wheel_uses_easing(self):
        from responsive_ui import ScrollForm
        holder = ttk.Frame(self.root, width=300, height=200)
        holder.pack()
        form = ScrollForm(holder)
        ttk.Label(form.form, text='x', padding=(0, 600)).pack()
        self.root.update()
        before = form.canvas.yview()[0]
        form.wheel(SimpleNamespace(delta=-120))
        mid = form.canvas.yview()[0]
        self.assertGreater(mid, before)
        self.pump(.3)
        self.assertGreater(form.canvas.yview()[0], mid)


class HoverFadeTests(TkCase):
    def setUp(self):
        super().setUp()
        setup_styles(self.root)
        self.button = ttk.Button(self.root, text='发送', style='Primary.TButton')
        self.button.pack(padx=20, pady=20)
        self.root.update()

    def styles_seen(self, seconds):
        seen = []
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.root.update()
            name = str(self.button.cget('style'))
            if not seen or seen[-1] != name:
                seen.append(name)
            time.sleep(.002)
        return seen

    def test_enter_fades_through_intermediate_levels_then_restores_base(self):
        self.button.event_generate('<Enter>')
        seen = self.styles_seen((HOVER_FADE_MS + 120) / 1000)
        self.assertEqual(seen[0], 'Fade0.Primary.TButton', '进入的第一帧就切到常态色，避免瞬间翻成悬停色')
        levels = [int(name.split('.')[0][4:]) for name in seen if name.startswith('Fade')]
        self.assertEqual(levels, list(range(HOVER_FADE_STEPS)))
        self.assertEqual(seen[-1], 'Primary.TButton')

    def test_leave_fades_back_down_and_restores_base(self):
        self.button.event_generate('<Enter>')
        self.styles_seen(.3)
        self.button.event_generate('<Leave>')
        seen = self.styles_seen(.3)
        levels = [int(name.split('.')[0][4:]) for name in seen if name.startswith('Fade')]
        self.assertEqual(levels, list(range(HOVER_FADE_STEPS, 0, -1)))
        self.assertEqual(seen[-1], 'Primary.TButton')

    def test_total_duration_is_bounded_by_the_token(self):
        self.button.event_generate('<Enter>')
        start = time.monotonic()
        while str(self.button.cget('style')) != 'Primary.TButton' or time.monotonic() - start < .01:
            self.root.update()
            time.sleep(.002)
            self.assertLess(time.monotonic() - start, HOVER_FADE_MS / 1000 + .15)

    def test_reversal_midway_continues_from_current_level(self):
        self.button.event_generate('<Enter>')
        self.pump((HOVER_FADE_MS / HOVER_FADE_STEPS) * 2 / 1000 + .01)
        self.button.event_generate('<Leave>')
        seen = self.styles_seen(.3)
        self.assertEqual(seen[-1], 'Primary.TButton')
        levels = [int(name.split('.')[0][4:]) for name in seen if name.startswith('Fade')]
        self.assertEqual(levels, sorted(levels, reverse=True), '反向后只降不升')
        self.assertLess(levels[-1], HOVER_FADE_STEPS - 1)

    def test_style_changed_elsewhere_is_never_overwritten(self):
        self.button.event_generate('<Enter>')
        self.pump(.01)
        self.button.configure(style='Secondary.TButton')
        self.pump(.3)
        self.assertEqual(str(self.button.cget('style')), 'Secondary.TButton')

    def test_disabled_button_does_not_fade(self):
        self.button.state(['disabled'])
        self.button.event_generate('<Enter>')
        self.pump(.05)
        self.assertEqual(str(self.button.cget('style')), 'Primary.TButton')

    def test_unregistered_style_is_left_alone(self):
        plain = ttk.Button(self.root, text='x', style='Totally.Unknown.TButton')
        plain.pack()
        self.root.update()
        plain.event_generate('<Enter>')
        self.pump(.05)
        self.assertEqual(str(plain.cget('style')), 'Totally.Unknown.TButton')

    def test_destroy_during_fade_cancels_timer(self):
        before = self.pending_after()
        self.button.event_generate('<Enter>')
        self.assertGreater(self.pending_after(), before)
        self.button.destroy()
        self.pump(.05)
        self.assertEqual(self.pending_after(), before)

    def test_intermediate_images_are_lazy_cached_and_pressed_state_survives(self):
        root = self.root
        names_before = set(ttk.Style(root).element_names())
        self.assertFalse([n for n in names_before if n.startswith('Drama.RoundedFade')],
                         '混色底图按需生成，安装样式时不预建')
        self.button.event_generate('<Enter>')
        self.styles_seen(.2)
        first = {n for n in ttk.Style(root).element_names() if n.startswith('Drama.RoundedFade')}
        self.assertEqual(len(first), HOVER_FADE_STEPS)
        self.button.event_generate('<Leave>')
        self.styles_seen(.2)
        self.button.event_generate('<Enter>')
        self.styles_seen(.2)
        again = {n for n in ttk.Style(root).element_names() if n.startswith('Drama.RoundedFade')}
        self.assertEqual(first | {n for n in again if n.endswith('Primary_TButton')}, again)
        spec = button_specs(root)['Primary.TButton']
        self.assertEqual(set(spec['images']), {'normal', 'active', 'pressed', 'disabled'})

    def test_every_rounded_button_style_is_registered_for_fade(self):
        registered = set(button_specs(self.root))
        for name in ('TButton', 'Primary.TButton', 'Tokens.Primary.TButton', 'Secondary.TButton',
                     'Nav.TButton', 'Selected.Nav.TButton', 'Tokens.Danger.TButton'):
            self.assertIn(name, registered)

    def test_install_is_idempotent(self):
        ui_hover_fade.install_hover_fade(self.root)
        ui_hover_fade.install_hover_fade(self.root)
        script = str(self.root.tk.call('bind', 'TButton', '<Enter>'))
        self.assertEqual(script.count('_enter'), 1)


class FreezeThawTests(TkCase):
    def make(self):
        events = []
        coalescer = ResizeCoalescer(self.root, quiet_ms=30,
                                    freeze=lambda: events.append('freeze'),
                                    thaw=lambda: events.append('thaw'))
        return coalescer, events

    def test_freeze_once_when_drag_confirmed_and_thaw_before_pending_runs(self):
        coalescer, events = self.make()
        coalescer.drag_active = lambda: True
        done = []
        apply = lambda: events.append('apply')
        for _ in range(5):
            self.assertTrue(coalescer.schedule(apply, event=object()))
        self.assertEqual(events, ['freeze'], '连续尺寸变化只冻结一次')
        coalescer.drag_active = lambda: False
        self.pump(.15)
        self.assertEqual(events, ['freeze', 'thaw', 'apply'], '先放回内容，再补做整页重排')
        self.assertFalse(done)

    def test_unknown_probe_defers_without_freezing(self):
        coalescer, events = self.make()
        coalescer.drag_active = lambda: None
        self.assertTrue(coalescer.schedule(lambda: events.append('apply'), event=object()))
        self.pump(.12)
        self.assertEqual(events, ['apply'], '探测不到时只合并，不收起画面')

    def test_not_dragging_never_freezes(self):
        coalescer, events = self.make()
        coalescer.drag_active = lambda: False
        self.assertFalse(coalescer.schedule(lambda: None, event=object()))
        self.assertEqual(events, [])

    def test_flush_and_cancel_thaw_immediately(self):
        for finish in ('flush', 'cancel'):
            coalescer, events = self.make()
            coalescer.drag_active = lambda: True
            coalescer.schedule(lambda: None, event=object())
            getattr(coalescer, finish)()
            self.assertEqual(events, ['freeze', 'thaw'], finish)
            getattr(coalescer, finish)()
            self.assertEqual(events, ['freeze', 'thaw'], finish + ' 重复调用不再解冻')

    def test_still_held_keeps_frozen_until_release(self):
        coalescer, events = self.make()
        coalescer.drag_active = lambda: True
        coalescer.schedule(lambda: events.append('apply'), event=object())
        self.pump(.12)
        self.assertEqual(events, ['freeze'])
        coalescer.drag_active = lambda: False
        self.pump(.12)
        self.assertEqual(events, ['freeze', 'thaw', 'apply'])

    def test_freeze_failure_is_swallowed_and_not_stuck(self):
        def boom():
            raise RuntimeError('x')
        coalescer = ResizeCoalescer(self.root, quiet_ms=20, freeze=boom, thaw=lambda: None)
        coalescer.drag_active = lambda: True
        self.assertTrue(coalescer.schedule(lambda: None, event=object()))
        coalescer.drag_active = lambda: False
        self.pump(.1)
        self.assertFalse(coalescer.is_waiting())

    def test_desktop_freeze_hides_page_and_sidebar_content_only(self):
        from responsive_ui import ScrollForm
        canvas = tk.Canvas(self.root)
        content = ttk.Frame(canvas)
        content_id = canvas.create_window(0, 0, window=content, anchor='nw')
        holder = ttk.Frame(self.root)
        side = ScrollForm(holder)
        fake = SimpleNamespace(canvas=canvas, content_id=content_id, sidebar_scroll=side)
        LayoutMixin._freeze_content(fake)
        self.assertEqual(canvas.itemcget(content_id, 'state'), 'hidden')
        self.assertEqual(side.canvas.itemcget(side.window_id, 'state'), 'hidden')
        LayoutMixin._thaw_content(fake)
        self.assertEqual(canvas.itemcget(content_id, 'state'), 'normal')
        self.assertEqual(side.canvas.itemcget(side.window_id, 'state'), 'normal')


if __name__ == '__main__':
    unittest.main()
