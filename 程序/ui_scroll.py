"""L4 平滑滚动：给 ``tk.Canvas`` 的滚轮滚动加缓出（ease-out）动画，纯 ``after`` 循环。

滚轮每推一次只是把「目标位置」往前推一段（连续滚轮累加），每帧走剩余距离的
``SCROLL_EASE`` 比例；第一步在滚轮事件里同步走完，所以滚轮后画布立刻有位移。
别处（翻页键、拖滚动条、代码里的 ``yview_*``）移动了画布，下一帧发现位置对不上就放弃剩余动画，
不会和它们抢。动画只在画布还活着时排帧，销毁即取消；静止时不占事件循环。
参数全部来自 ``ui_tokens``（SCROLL_*）。
"""
import tkinter as tk

from ui_tokens import SCROLL_EASE, SCROLL_FRAME_MS, SCROLL_SNAP_PX

#: 画布当前位置与上一帧自己写下的位置差超过这么多像素，就认为被别处移动过。
_EXTERNAL_MOVE_PX = 1.5
_TK_UNIT_DIVISOR = 10  # yscrollincrement=0 时，Tk 一个「单位」是可视高度的 1/10


class EasedScroll:
    def __init__(self, canvas):
        self.canvas = canvas
        self._target = None
        self._expected = None
        self._job = None
        canvas.bind('<Destroy>', self._destroyed, add='+')

    @property
    def running(self):
        return self._job is not None

    def _geometry(self):
        """(滚动区总高, 可视高, 当前顶端像素)；区域未定或无可滚内容返回 None。"""
        region = str(self.canvas.cget('scrollregion')).split()
        if len(region) != 4:
            return None
        total = float(region[3]) - float(region[1])
        view = float(self.canvas.winfo_height())
        if total <= view or total <= 0:
            return None
        return total, view, self.canvas.yview()[0] * total

    def _unit_px(self, view):
        increment = float(self.canvas.winfo_fpixels(self.canvas.cget('yscrollincrement') or 0))
        return increment if increment > 0 else max(1.0, view / _TK_UNIT_DIVISOR)

    def scroll(self, steps):
        """按 Tk「单位」滚 steps 格（负数向上）；能缓动就缓动，否则退回原生滚动。"""
        if not steps:
            return
        geometry = self._geometry()
        if geometry is None or float(self.canvas.winfo_fpixels(self.canvas.cget('yscrollincrement') or 0)) > 0:
            self.cancel()
            self.canvas.yview_scroll(steps, 'units')
            return
        total, view, top = geometry
        idle = self._target is None or self._expected is None
        if idle or abs(top - self._expected) > _EXTERNAL_MOVE_PX:
            self._target = top
        self._target = min(max(self._target + steps * self._unit_px(view), 0.0), total - view)
        self._cancel_job()
        self._step()

    def _step(self):
        self._job = None
        try:
            geometry = self._geometry()
        except tk.TclError:
            self._reset()
            return
        if geometry is None:
            self._reset()
            return
        total, _view, top = geometry
        if self._expected is not None and abs(top - self._expected) > _EXTERNAL_MOVE_PX:
            self._reset()  # 别处动过画布：放弃剩余动画
            return
        remaining = self._target - top
        if abs(remaining) <= SCROLL_SNAP_PX:
            new, done = self._target, True
        else:
            new, done = top + remaining * SCROLL_EASE, False
        try:
            self.canvas.yview_moveto(new / total)
            if done:
                self._reset()
            else:
                self._expected = new
                self._job = self.canvas.after(SCROLL_FRAME_MS, self._step)
        except tk.TclError:
            self._reset()

    def _cancel_job(self):
        job, self._job = self._job, None
        if job is not None:
            try:
                self.canvas.after_cancel(job)
            except tk.TclError:
                pass

    def _reset(self):
        self._target = None
        self._expected = None

    def cancel(self):
        self._cancel_job()
        self._reset()

    def _destroyed(self, event):
        if event.widget is self.canvas:
            self.cancel()


def eased_scroll(canvas, steps):
    """页面／侧栏滚轮的统一入口：每块画布一个 EasedScroll，按需创建。"""
    scroller = getattr(canvas, '_eased_scroll', None)
    if scroller is None:
        scroller = canvas._eased_scroll = EasedScroll(canvas)
    scroller.scroll(steps)
