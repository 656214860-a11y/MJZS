"""云朵气泡的计时方法与计时参数（从 pet_cloud.Cloud 原样迁出，R1621）。

方法体未改、self 语义不变，Cloud 通过继承 CloudTimingMixin 获得；自停／渐隐／读秒参数随方法迁出，
由 pet_cloud 按原名转回。仍与 Tk 控件紧耦合，故与 pet_cloud 同属 L4。
"""
import app_logging
from pet_cloud_shape import SHAPE_ROUND
from ui_tokens import PET_CLOUD_AUTO_CLOSE_MS


WATCH_RECHECK_MS = 2000           # 第 27 期第 2 条：指针停在云上（正在看）时，每隔这么久回头看一眼指针走了没
HOLD_MS = 9000                    # 一句话「最少」停留多久：给用户读完的时间以此为底
READ_MS_PER_CHAR = 110            # 第 24 期第 8 条：每个字留给用户读多久——话越长停得越久
READ_MAX_MS = 30000               # 再长也就停这么久：对话框不当路霸
ALPHA = 0.97                      # 整朵云的不透明度
FADE_MS = 16                      # 淡入的间隔
FADE_STEPS = (0.45, 0.70, 0.86, 1.0)   # 淡入的几档（乘在 ALPHA 上）：一露面是「浮」出来的
# 第 24 期：四种形状收场都走这条渐隐——用户要的「延时淡出」。档位多一点、间隔长一点，
# 淡下去看得见（原来三档 26ms 一共 78ms，比眨眼还快）。
FADE_OUT_STEPS = (0.82, 0.64, 0.46, 0.28, 0.12, 0.0)
FADE_OUT_MS = 60
GROW_STEPS = (0.45, 0.70, 0.88, 1.0)   # 气泡「长出来」的几档：从耳朵那头逐步到位
GROW_ROOM = 0.42                  # 起步时气泡偏向耳朵这么多比例


from ui_motion import reduce_motion

class CloudTimingMixin:
    def _fade_out(self):
        """渐隐：alpha 一档一档走到 0 再 withdraw（第 24 期：档数与间隔见 FADE_OUT_STEPS／FADE_OUT_MS）。

        定时器仍旧只有一个（self._fade），收窗／销毁都要收回来；返回值是 None——close() 的
        「空操作」语义不变。
        """
        if self.win is None:
            return self._hide_now()
        self.visible = False
        self.busy = False

        def step(index):
            if self.win is None:
                self._fade = None
                return None
            if index >= len(FADE_OUT_STEPS):
                self._fade = None
                return self._hide_now()
            try:
                self.win.attributes('-alpha', ALPHA * FADE_OUT_STEPS[index])
            except Exception:
                self._fade = None
                return self._hide_now()
            try:
                def next_step():
                    self._fade, self._fade_callback = None, None
                    return step(index + 1)
                self._fade_callback = next_step
                self._fade = self.win.after(FADE_OUT_MS, next_step)
            except Exception:
                self._fade = None
            return None

        step(len(FADE_OUT_STEPS) if reduce_motion() else 0)   # 减少动效：直接收起
        return None

    def read_hold(self, text=None):
        """读完这一句要留多久（毫秒）：按字数算，夹在 HOLD_MS 与 READ_MAX_MS 之间。

        第 24 期第 8 条（用户要的「为用户展示足够阅读的时间」）：原来不管话多长，播报一律 9 秒、
        对话一律 6 秒，长句子根本读不完。text 给 None 时按记录里最新那一条算。
        """
        text = self.lines[-1] if text is None and self.lines else text
        count = len(''.join(str(text or '').split()))
        return int(max(HOLD_MS, min(READ_MAX_MS, count * READ_MS_PER_CHAR)))

    def hold_for(self, text, floor):
        """这一句话该留多久：按字数算出来的阅读时间与这一形态的底线取大（第 24 期）。"""
        return max(int(floor), self.read_hold(text))

    def default_hold(self, text=None):
        """没人指定时该等多久：按最新那一条要读多久算。"""
        return self.read_hold(text)

    def _interaction_paused(self):
        try:
            focused = self.reply is not None and self.win.focus_get() is self.reply
        except Exception:
            focused = False
        return self._pointer_inside() or focused

    def _interaction_changed(self):
        """复用宠物心跳检查交互，不登记 Enter/Leave 或额外 Tcl 回调。"""
        if self.visible and (self.busy or self._interaction_paused()) != self._watching:
            self._arm_hold()

    def _arm_hold(self, hold=None):
        """空闲等完整十秒；交互中沿用原有 WATCH_RECHECK_MS 坐标复检。"""
        self._cancel_hold()
        self._watching = self.busy or self._interaction_paused()
        delay = WATCH_RECHECK_MS if self._watching else PET_CLOUD_AUTO_CLOSE_MS
        callback = self._recheck_hold if self._watching else self._expire
        try:
            self._hold = self.parent.after(delay, callback)
        except Exception as exc:
            self.errors.append(('after', str(exc)))
            self._hold = None
        return self._hold

    def _recheck_hold(self):
        """交互持续则继续复检，结束则重新登记完整十秒，不能直接收起。"""
        return self._arm_hold()

    def _cancel_position(self):
        """撤销父窗口上的定位重试；先清登记，取消失败后的迟到回调也不能继续定位。"""
        job, self._position_job = self._position_job, None
        self._position_callback = None
        if job is not None:
            try:
                self.parent.after_cancel(job)
            except Exception:
                # 父 Tcl 解释器已销毁时无可取消对象，关窗路径无需二次报错。
                app_logging.swallowed()
        return None

    def _cancel_hold(self):
        if self._hold is None:
            return None
        try:
            self.parent.after_cancel(self._hold)
        except Exception:
            app_logging.swallowed()
        self._hold = None
        return None

    def _cancel_fade(self):
        """收回淡入定时器：浮窗先一步没了的话，它在队列里到点就是一句 invalid command name。"""
        if self._fade is None:
            return None
        try:
            (self.win or self.parent).after_cancel(self._fade)
        except Exception:
            app_logging.swallowed()
        self._fade, self._fade_callback = None, None
        return None

    def _fade_in(self):
        """浮出：从淡到清楚地闪一下（第 16 期「交互时云朵框以浮出的形式出现」）。"""
        if self.win is None:
            return None
        self._cancel_fade()
        grow = self.shape == SHAPE_ROUND
        final = self._origin() if grow else None
        if grow and self.label is not None:
            try:
                self.label.place_forget()          # 长的那几拍先不摆字：字还不该露（露了就跑到圆外头了）
            except Exception as exc:
                self.errors.append(('grow', str(exc)))
        if grow and final is not None:
            self._grow_to(final, GROW_STEPS[0])
        try:
            self.win.attributes('-alpha', ALPHA * FADE_STEPS[0])
        except Exception:
            return None

        def bump(index):
            if self.win is None or not self.visible:
                return None
            try:
                self.win.attributes('-alpha', ALPHA * FADE_STEPS[min(index, len(FADE_STEPS) - 1)])
            except Exception:
                return None
            if grow and final is not None:
                self._grow_to(final, GROW_STEPS[min(index, len(GROW_STEPS) - 1)])
            if index + 1 < len(FADE_STEPS):
                try:
                    def next_bump():
                        self._fade, self._fade_callback = None, None
                        return bump(index + 1)
                    self._fade_callback = next_bump
                    self._fade = self.win.after(FADE_MS, next_bump)
                except Exception:
                    self._fade, self._fade_callback = None, None
            else:
                self._fade, self._fade_callback = None, None
                if grow:
                    self._place_label()            # 到位了才把字摆上去
                    self._place_window()
            return None

        try:
            def first_bump():
                self._fade, self._fade_callback = None, None
                return bump(len(FADE_STEPS) - 1 if reduce_motion() else 1)   # 减少动效：一步到位
            self._fade_callback = first_bump
            self._fade = self.win.after(FADE_MS, first_bump)
        except Exception:
            self._fade, self._fade_callback = None, None
        return self._fade

    def _grow_to(self, final, along):
        """圆气泡「长出来」的那几拍：从耳朵那头一档一档滑到最终落点。

        along＝0 贴着耳朵（1 — GROW_ROOM）、along＝1 就是该在的地方；只是位置在走，气泡本身的大小不变——
        “递进变大”看的就是它从耳朵那头一点点冒出来、越占越多地方。
        """
        try:
            ear_x, ear_y = self._ear()
            room = (1.0 - along) * GROW_ROOM
            left = final[0] + (ear_x - final[0]) * room
            top = final[1] + (ear_y - final[1]) * room
            self.win.geometry('+%d+%d' % (int(left), int(top)))
        except Exception as exc:
            self.errors.append(('grow', str(exc)))
        return None

    def _parent_gone(self, event=None):
        """父窗口被销毁：立刻收回定时器（子控件冒泡上来的 <Destroy> 不认领）。"""
        if event is not None and getattr(event, 'widget', None) is not self.parent:
            return None
        self.cancel_deferred_render()
        self._cancel_position()
        # 第 37 期第 4 条：滚动小字的表也挂在这个窗口上，一起收回来。
        self._hint_stop()
        return self._cancel_hold(), self._cancel_fade()

    def _window_gone(self, event=None):
        """浮窗自己被销毁：把引用与定时器一起收干净（子控件冒泡上来的 <Destroy> 不认领）。"""
        if event is not None and getattr(event, 'widget', None) is not self.win:
            return None
        self.cancel_deferred_render()
        self._cancel_hold()
        self._cancel_fade()
        self._hint_stop()
        self._cancel_position()
        self.win, self.canvas = None, None
        self.visible = False
        return None

    def _expire(self):
        """仅收起视图，保留历史、待决命令和后台状态。"""
        self._cancel_hold()
        if self.busy or self._interaction_paused():
            self._arm_hold()
            return False
        self.cancel_deferred_render()
        self._cancel_position()
        self._cancel_fade()
        self._hint_stop()
        busy = self.busy
        self._hide_now()
        self.busy = busy
        return True
