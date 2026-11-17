"""单框查找替换条（REQ-S02-36／R2）。

``FindBar`` 只作用于一个正文 ``tk.Text``：关键字、上一个／下一个循环、
单个替换与替换全部、命中计数、``Esc`` 关闭。命中位置由纯函数
``_search_positions`` 给出（字符偏移、不重叠），UI 层只负责换算成
Tk 行列索引、``tag_add('sel')`` 高亮与 ``see()`` 跳转。

替换要求文本框处于 ``state='normal'``（编辑态）；只读态下 ``delete``／
``insert`` 不会真正改文本，因此直接拒绝并提示。替换产生的 ``<<Modified>>``
事件仍走 ``ScriptStructureEditController`` 的既有撤销／保存链路。
"""
import re
import tkinter as tk
from tkinter import ttk

from ui_tokens import CHAR_WIDTH, SPACING
from ui_widgets import LineInput, SecondaryButton

# 计数标签样式与正文区一致的弱化色。
_COUNT_STYLE = "Muted.TLabel"


def _search_positions(text, pattern, nocase=False):
    """返回 ``[(start, end)]`` 字符偏移（左闭右开、按出现顺序、不重叠）。

    纯函数、不依赖 Tk：``nocase=True`` 时按 Unicode 简单忽略大小写匹配；
    空文本或空关键字返回 ``[]``。
    """
    value = str(text or "")
    needle = str(pattern or "")
    if not value or not needle:
        return []
    flags = re.IGNORECASE if nocase else 0
    return [(match.start(), match.end())
            for match in re.finditer(re.escape(needle), value, flags)]


def _offset_index(text, offset):
    """字符偏移 → Tk ``'行.列'`` 索引（行 1 起、列 0 起）。"""
    line = text.count("\n", 0, offset) + 1
    return "%d.%d" % (line, offset - (text.rfind("\n", 0, offset) + 1))


class FindBar(ttk.Frame):
    """查找替换条：默认 ``grid_remove`` 隐藏，由页面 ``show()``/``hide()`` 开合。"""

    def __init__(self, master, text_widget, *, on_changed=None, notify=None, run=None):
        super().__init__(master, padding=(SPACING["xs"], SPACING["xs"], SPACING["xs"], SPACING["none"]))
        self._text = text_widget
        self._on_changed = on_changed or (lambda: None)
        self._notify = notify or (lambda _message: None)
        self._run = run or (lambda fn: fn())
        self._sel = None          # 当前高亮命中 (start, end) 字符偏移
        self._shown = False

        self.sensitive = tk.BooleanVar(value=False)   # 勾选＝区分大小写（默认不敏感）
        self.keyword = LineInput(self, width=CHAR_WIDTH["3xl"], placeholder="查找")
        self.keyword.pack(side="left")
        ttk.Checkbutton(self, text="Aa", variable=self.sensitive,
                        style="TCheckbutton").pack(
            side="left", padx=(SPACING["xs"], SPACING["none"]))
        self._button("上一个", self.find_prev).pack(side="left", padx=(SPACING["sm"], SPACING["none"]))
        self._button("下一个", self.find_next).pack(side="left", padx=(SPACING["xs"], SPACING["none"]))
        self.replacement = LineInput(self, width=CHAR_WIDTH["2xl"], placeholder="替换为")
        self.replacement.pack(side="left", padx=(SPACING["md"], SPACING["xs"]))
        self._button("替换", self.replace_one).pack(side="left")
        self._button("替换全部", self.replace_all).pack(side="left", padx=(SPACING["xs"], SPACING["none"]))
        self.count_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.count_var, style=_COUNT_STYLE).pack(side="left", padx=(SPACING["sm"], SPACING["none"]))
        self._button("关闭", self.hide).pack(side="left")

        self.keyword.bind("<Return>", lambda _e: self.find_next(), add="+")
        self.keyword.bind("<Shift-Return>", lambda _e: self.find_prev(), add="+")
        self.replacement.bind("<Return>", lambda _e: self.replace_one(), add="+")
        for entry in (self.keyword, self.replacement):
            entry.bind("<Escape>", lambda _e: self.hide(), add="+")

    # ---- 显隐 ---------------------------------------------------------

    @property
    def visible(self):
        return self._shown

    def show(self):
        """显示查找条并聚焦关键字框；重复调用幂等。"""
        if not self._shown:
            self.grid()
            self._shown = True
        self.keyword.focus_set()
        self.keyword.selection_range(0, "end")

    def hide(self):
        self.grid_remove()
        self._shown = False

    def reset(self):
        """内容整体变化后清空命中状态与计数；不隐藏查找条。"""
        self._sel = None
        self.count_var.set("")

    # ---- 查找 ---------------------------------------------------------

    def _content(self):
        return self._text.get("1.0", "end-1c")

    def _positions(self):
        return _search_positions(self._content(), self.keyword.get(),
                                 nocase=not bool(self.sensitive.get()))

    def _needle_matches(self, fragment):
        needle = self.keyword.get()
        if bool(self.sensitive.get()):
            return fragment == needle
        return fragment.casefold() == needle.casefold()

    def _set_count(self, index, total):
        self.count_var.set("第 %d/%d 个" % (index, total) if total else "未找到")

    def _highlight(self, match, text):
        start, end = match
        self._text.tag_remove("sel", "1.0", "end")
        self._text.tag_add("sel", _offset_index(text, start), _offset_index(text, end))
        self._text.see(_offset_index(text, start))

    def find_next(self):
        positions = self._positions()
        if not positions:
            self._sel = None
            self._set_count(0, 0)
            self._notify("未找到“%s”。" % self.keyword.get())
            return False
        sel = self._sel
        if sel is None:
            match = positions[0]
        else:
            after = [pos for pos in positions if pos[0] >= sel[1]]
            match = after[0] if after else positions[0]
        self._sel = match
        text = self._content()
        self._highlight(match, text)
        self._set_count(positions.index(match) + 1, len(positions))
        return True

    def find_prev(self):
        positions = self._positions()
        if not positions:
            self._sel = None
            self._set_count(0, 0)
            self._notify("未找到“%s”。" % self.keyword.get())
            return False
        sel = self._sel
        if sel is None:
            match = positions[-1]
        else:
            before = [pos for pos in positions if pos[1] <= sel[0]]
            match = before[-1] if before else positions[-1]
        self._sel = match
        text = self._content()
        self._highlight(match, text)
        self._set_count(positions.index(match) + 1, len(positions))
        return True

    # ---- 替换 ---------------------------------------------------------

    def _editable(self):
        return str(self._text.cget("state")) == "normal"

    def _require_editable(self):
        if not self._editable():
            self._notify("请先点击“编辑”，再替换。")
            return False
        return True

    def replace_one(self):
        """替换当前命中（无命中时先找下一个）；返回替换次数。"""
        if not self._require_editable():
            return 0
        if self._sel is None and not self.find_next():
            return 0
        text = self._content()
        start, end = self._sel
        if not self._needle_matches(text[start:end]):
            # 文本在两次查找之间被改过：重新定位一次，仍不匹配则放弃。
            self._sel = None
            if not self.find_next():
                return 0
            text = self._content()
            start, end = self._sel
        replacement = self.replacement.get()
        self._text.delete(_offset_index(text, start), _offset_index(text, end))
        self._text.insert(_offset_index(text, start), replacement)
        # 续位到替换文本末尾，避免把替换结果自身当成下一处命中。
        self._sel = (start + len(replacement), start + len(replacement))
        self._changed()
        self.find_next()
        return 1

    def replace_all(self):
        """替换全部命中并返回处数；从后往前改，前面偏移不受影响。"""
        if not self._require_editable():
            return 0
        text = self._content()
        positions = _search_positions(text, self.keyword.get(),
                                      nocase=not bool(self.sensitive.get()))
        if not positions:
            self._notify("未找到“%s”。" % self.keyword.get())
            return 0
        replacement = self.replacement.get()
        for start, end in reversed(positions):
            index = _offset_index(text, start)
            self._text.delete(index, _offset_index(text, end))
            self._text.insert(index, replacement)
        count = len(positions)
        self._sel = None
        self._changed()
        self._notify("已替换 %d 处。" % count)
        self.find_next()
        return count

    def _changed(self):
        self._on_changed()

    # ---- 控件 ---------------------------------------------------------

    def _button(self, text, command):
        return SecondaryButton(self, text=text,
                               command=lambda: self._run(command))
