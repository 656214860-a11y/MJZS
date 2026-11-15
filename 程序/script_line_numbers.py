"""剧本阅读框左侧行号槽（REQ-S02-36／R1）。

``LineNumberGutter`` 是只读 ``tk.Canvas``：按正文 ``tk.Text`` 当前可见的
**逻辑行**画行号。刷新时机只有三类——正文 ``yscrollcommand`` 包装回调、
文本框与自身的 ``<Configure>``、以及 ``set_font``（R4 缩放）；内容增减由
页面在装载／编辑边界显式调 ``refresh()``。软换行折出的多条显示行共用同一
个逻辑行号，不重复编号。
"""
import tkinter as tk
import tkinter.font as tkfont

from ui_tokens import COLORS, SCRIPT_GUTTER_WIDTH, SCRIPT_VIEW_FONT, SPACING

# 行号与槽右缘、以及与槽左缘的留白（像素）。
_GUTTER_PAD = SPACING["xs"]


def _spec_weight(font):
    """Tk 字体描述 ``(族, 字号[, 'bold'])`` → 'bold'/'normal'，供测量字体用。"""
    return "bold" if "bold" in tuple(font)[2:] else "normal"


class LineNumberGutter(tk.Canvas):
    """正文左侧行号槽：只读、只画行号，随 text 滚动与配置刷新。"""

    def __init__(self, master, text_widget, font=None, **kwargs):
        self._text = text_widget
        self._font_spec = tuple(font) if font else SCRIPT_VIEW_FONT
        kwargs.setdefault("width", SCRIPT_GUTTER_WIDTH)
        kwargs.setdefault("highlightthickness", 0)
        kwargs.setdefault("bd", 0)
        super().__init__(master, bg=COLORS["background_card"], **kwargs)
        self._measure = tkfont.Font(root=self)
        self._apply_font()
        text_widget.bind("<Configure>", self._on_text_configure, add="+")
        self.bind("<Configure>", self._redraw, add="+")

    # ---- 对外接口 -----------------------------------------------------

    def set_font(self, font):
        """R4：正文缩放时同步行号字号；``font`` 为 ``(族, 字号[, 字重])``。"""
        self._font_spec = tuple(font)
        self._apply_font()
        self._redraw()

    def refresh(self):
        """内容增减后由页面调用；滚动与尺寸变化已自动触发。"""
        self._redraw()

    # ---- 内部 ---------------------------------------------------------

    def _apply_font(self):
        spec = self._font_spec
        self._measure.configure(
            family=spec[0],
            size=spec[1],
            weight=_spec_weight(spec),
        )

    def _on_text_configure(self, _event=None):
        self._redraw()

    def _visible_range(self):
        """返回 (首可见逻辑行, 末可见逻辑行)；窗口未映射时退化为第 1 行。"""
        text = self._text
        try:
            first = int(str(text.index("@0,0")).split(".")[0])
            bottom = max(1, self.winfo_height())
            last = int(str(text.index("@0,%d" % bottom)).split(".")[0])
        except (tk.TclError, ValueError):
            return 1, 1
        return first, max(first, last)

    def _needed_width(self, line_count):
        """按最大行号位数量宽，不小于 token 下限。"""
        needed = self._measure.measure(str(max(1, line_count))) + _GUTTER_PAD * 2
        return max(SCRIPT_GUTTER_WIDTH, int(needed) + 1)

    def _redraw(self, _event=None):
        self.delete("all")
        text = self._text
        if not text.winfo_exists():
            return
        try:
            line_count = int(str(text.index("end-1c")).split(".")[0])
        except (tk.TclError, ValueError):
            line_count = 1
        width = self._needed_width(line_count)
        if int(float(self.cget("width"))) != width:
            self.configure(width=width)
        first, last = self._visible_range()
        right = width - _GUTTER_PAD
        for line in range(first, last + 1):
            info = text.dlineinfo("%d.0" % line)
            if not info:
                continue
            # dlineinfo 返回 (x, y, w, h[, 基线])；取 y 与高度让行号垂直居中于首行。
            self.create_text(
                right, info[1] + info[3] / 2.0,
                text=str(line), anchor="e",
                font=self._font_spec, fill=COLORS["text_muted"],
            )
