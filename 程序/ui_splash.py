"""启动画面 Splash（L4，自 ui_widgets 拆出；``ui_widgets`` 仍转出同名符号）。"""
import app_logging
import time as _time
import tkinter as tk
import ui_tokens as T
from app_metadata import APP_NAME


# 进度按真实启动阶段推进：每段有目标百分比，段内匀速爬向下一段，爬到头就停等。
SPLASH_STAGES = (('正在加载组件…', 0.15), ('正在构建工作台…', 0.45), ('正在打开项目…', 0.75),
                 ('正在渲染页面…', 0.92), ('准备就绪', 1.0))


class Splash:
    """启动画面：整块盖住主窗口所在位置，加载完、进度条走满的那一刻才揭开主窗口。

    主线程被搭建工作占住时画面会停，所以 step() 都主动推一帧；空闲时由 wait() 轮询就绪。"""

    def __init__(self, master, rect):
        self.win = tk.Toplevel(master)
        self.win.overrideredirect(True)
        self.win.attributes('-topmost', True)
        self.win.configure(bg=T.SPLASH_BACKGROUND)
        self.canvas = tk.Canvas(self.win, bg=T.SPLASH_BACKGROUND, highlightthickness=0, bd=0)
        self.canvas.pack(fill='both', expand=True)
        self.start = _time.perf_counter()
        self.stage = 0
        self.progress = 0.0
        self._job = None
        self._size = None
        # 各段与收尾的耗时（毫秒，距 Splash 创建）；收起时交给 on_finish，由调用方决定落到哪。
        self.marks = {}
        self.on_finish = None
        self.cover(rect)
        self._tick()
        self.win.update()

    def cover(self, rect):
        """把画面挪到 rect=(x, y, w, h)，尺寸变了就按新尺寸重画。"""
        x, y, width, height = (int(v) for v in rect)
        self.win.geometry(f'{width}x{height}+{x}+{y}')
        if self._size != (width, height):
            self._size = (width, height)
            self._draw(width, height)

    def _draw(self, w, h):
        c = self.canvas
        c.delete('all')
        cx, cy = w // 2, h // 2 - T.SPACING['2xl']
        r = T.SPACING['2xl'] + T.SPACING['sm']
        self.ring = c.create_arc(cx - r, cy - r, cx + r, cy + r, start=90, extent=300,
                                 style='arc', outline=T.SPLASH_ACCENT, width=3)
        tri = r // 2
        c.create_polygon(cx - tri // 2, cy - tri, cx - tri // 2, cy + tri, cx + tri, cy,
                         fill=T.SPLASH_ACCENT_ALT, outline='')
        title_y = cy + r + T.SPACING['2xl']
        c.create_text(cx, title_y, text=APP_NAME, fill=T.SPLASH_TITLE, font=T.SPLASH_TITLE_FONT)
        c.create_text(cx, title_y + T.SPACING['2xl'] + T.SPACING['xs'], text='AI 漫剧 · 从剧本到成片',
                      fill=T.SPLASH_SUBTITLE, font=T.SPLASH_SUBTITLE_FONT)
        half = min(w // 3, T.SPLASH_BAR_HALF)
        bar_y = title_y + T.SPACING['2xl'] * 3
        self.bar_box = (cx - half, bar_y, cx + half)
        c.create_line(cx - half, bar_y, cx + half, bar_y, fill=T.SPLASH_FILM, width=3, capstyle='round')
        self.bar = c.create_line(cx - half, bar_y, cx - half, bar_y, fill=T.SPLASH_ACCENT, width=3,
                                 capstyle='round')
        self.status = c.create_text(cx, bar_y + T.SPACING['lg'] + T.SPACING['xs'],
                                    text=SPLASH_STAGES[self.stage][0],
                                    fill=T.SPLASH_SUBTITLE, font=T.SPLASH_SUBTITLE_FONT)
        self._paint()

    def _paint(self):
        c = self.canvas
        c.itemconfigure(self.ring, start=(90 - (_time.perf_counter() - self.start) * 240) % 360)
        left, y, right = self.bar_box
        c.coords(self.bar, left, y, left + (right - left) * min(1.0, self.progress), y)

    def _advance(self, dt):
        floor = SPLASH_STAGES[self.stage - 1][1] if self.stage else 0.0
        ceiling = SPLASH_STAGES[self.stage][1]
        # 段内爬到上限的 95% 就停等，不让进度条在没加载完时假装走满。
        self.progress = max(self.progress, floor)
        self.progress = min(ceiling - (ceiling - floor) * 0.05, self.progress + dt * T.SPLASH_CREEP)

    def _tick(self):
        if not self.win.winfo_exists():
            return
        self._advance(T.SPLASH_FRAME_MS / 1000)
        self._paint()
        self._job = self.win.after(T.SPLASH_FRAME_MS, self._tick)

    def _mark(self, name):
        self.marks.setdefault(name, round((_time.perf_counter() - self.start) * 1000, 1))

    def _report(self):
        callback, self.on_finish = self.on_finish, None
        if callback is None:
            return
        try:
            callback(dict(self.marks))
        except Exception:   # 计时只是诊断，绝不能挡住揭开主窗口
            app_logging.swallowed()

    def step(self, index):
        """进入第 index 段（0 起），并立刻刷一帧。"""
        if not self.win.winfo_exists():
            return
        self.stage = max(self.stage, min(index, len(SPLASH_STAGES) - 1))
        self._mark('stage_%d' % self.stage)
        self.progress = max(self.progress, SPLASH_STAGES[self.stage - 1][1] if self.stage else 0.0)
        self.canvas.itemconfigure(self.status, text=SPLASH_STAGES[self.stage][0])
        self._paint()
        # 只刷布局与重绘，不能用 update()：它会把已到期的 after 任务（项目加载、建页）整队排空，
        # 全吞进这一次调用里，Splash 的动画帧就没机会执行，进度条冻结。加载交给主循环按拍推进。
        self.win.update_idletasks()

    def wait(self, ready, done, track=None, timeout=T.SPLASH_MAX_SECONDS):
        """轮询 ready()；连续两拍就绪（或超时）后把进度条走满，再调 done() 并收起画面。

        track() 返回主窗口当前外框时，画面跟着它挪，保证始终整块盖住。"""
        deadline = _time.perf_counter() + timeout
        hits = [0]

        def finish(start, begin):
            if not self.win.winfo_exists():
                return done()
            t = min(1.0, (_time.perf_counter() - start) / (T.SPLASH_FINISH_MS / 1000))
            self.progress = begin + (1.0 - begin) * t
            self._paint()
            if t < 1.0:
                self.win.after(T.SPLASH_FRAME_MS, finish, start, begin)
                return
            self._mark('total')
            try:
                done()
            finally:
                self.close()
                self._report()

        def poll():
            if not self.win.winfo_exists():
                return done()
            if track is not None:
                rect = track()
                if rect:
                    self.cover(rect)
            hits[0] = hits[0] + 1 if ready() else 0
            if hits[0] >= 2 or _time.perf_counter() > deadline:
                self.stage = len(SPLASH_STAGES) - 1
                self._mark('ready')
                # 收尾动画自己推进度，停掉逐帧爬升，免得两边抢着改进度条往回跳。
                if self._job is not None:
                    self.win.after_cancel(self._job)
                    self._job = None
                self.canvas.itemconfigure(self.status, text=SPLASH_STAGES[-1][0])
                finish(_time.perf_counter(), self.progress)
                return
            self.win.after(T.SPLASH_POLL_MS, poll)

        self.win.after(T.SPLASH_POLL_MS, poll)

    def close(self):
        if self._job is not None:
            try:
                self.win.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None
        try:
            self.win.destroy()
        except tk.TclError:
            pass
