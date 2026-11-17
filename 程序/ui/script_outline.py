"""剧本大纲（REQ-S02-36／R3）：集数／场次与标题层级的行号跳转面板。

``outline_entries`` 是纯函数：复用 ``script_view_style.spans`` 的标签
（natural 取 ``script_episode``／``script_scene``，structured 取
``script_heading*``），按行号升序去重并把该行原文清洗成标题。
``OutlinePanel`` 只做展示与跳转：点击条目 ``see()`` 到正文对应行，
并在该行打 ``script_outline_hit`` 临时高亮（下一次跳转或内容刷新时清除）。
"""
import re
import tkinter as tk
from tkinter import ttk

import ui.script_view_style as script_view_style
from ui_tokens import COLORS, SPACING, SCRIPT_VIEW_FONT, TEXT_ROWS

_TITLE_MAX = 40       # 大纲条目标题截断长度（字符）
_LIST_WIDTH = 30      # Listbox 宽度（字符）：容下一条截断标题
_HIT_TAG = "script_outline_hit"
_EMPTY_TEXT = "无集数／场次标题"

_STRUCTURED_TAGS = frozenset(script_view_style.HEADING_TAGS.values())
_NATURAL_TAGS = frozenset({script_view_style.EPISODE, script_view_style.SCENE})


def _clean_title(line):
    """去掉 Markdown 标题井号与首尾空白，截断到 ``_TITLE_MAX`` 字。"""
    title = re.sub(r"^\s*#+\s*", "", str(line or "")).strip()
    if len(title) > _TITLE_MAX:
        title = title[: _TITLE_MAX - 1] + "…"
    return title


def outline_entries(text, kind="natural"):
    """返回 ``[(行号, 标题)]``，行号升序、按行去重；无匹配返回 ``[]``。"""
    value = str(text or "")
    if not value:
        return []
    wanted = _STRUCTURED_TAGS if kind == "structured" else _NATURAL_TAGS
    lines = value.split("\n")
    found = {}
    for start_line, _sc, _el, _ec, tag in script_view_style.spans(value, kind):
        if tag not in wanted or start_line in found:
            continue
        index = start_line - 1
        title = _clean_title(lines[index] if index < len(lines) else "")
        if title:
            found[start_line] = title
    return sorted(found.items())


class OutlinePanel(ttk.Frame):
    """侧边大纲列表；点击条目 ``see()`` 到正文对应行并高亮。"""

    def __init__(self, master, text_widget, **kwargs):
        super().__init__(master, **kwargs)
        self._text = text_widget
        self._entries = []
        text_widget.tag_configure(_HIT_TAG, background=COLORS["selection_bg"])

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        self._empty = ttk.Label(body, text=_EMPTY_TEXT, style="Muted.TLabel")
        self._list = tk.Listbox(
            body,
            font=SCRIPT_VIEW_FONT,
            bg=COLORS["background_card"],
            fg=COLORS["text_primary"],
            selectbackground=COLORS["primary"],
            selectforeground=COLORS["background_card"],
            highlightthickness=0,
            bd=0,
            width=_LIST_WIDTH,
            height=TEXT_ROWS["lg"],
            activestyle="none",
        )
        self._scroll = ttk.Scrollbar(body, orient="vertical", command=self._list.yview)
        self._list.configure(yscrollcommand=self._scroll.set)
        self._list.bind("<<ListboxSelect>>", self._on_select)
        self.set_entries(())

    # ---- 数据 ---------------------------------------------------------

    def set_entries(self, entries):
        """整体替换大纲条目；空列表时显示空态文案。"""
        self._entries = list(entries)
        self._list.delete(0, "end")
        for _line, title in self._entries:
            self._list.insert("end", title)
        self._text.tag_remove(_HIT_TAG, "1.0", "end")
        has_entries = bool(self._entries)
        if has_entries:
            self._empty.pack_forget()
            self._list.pack(side="left", fill="both", expand=True)
            self._scroll.pack(side="right", fill="y")
        else:
            self._scroll.pack_forget()
            self._list.pack_forget()
            self._empty.pack(fill="both", expand=True)

    # ---- 跳转 ---------------------------------------------------------

    def _on_select(self, _event=None):
        selection = self._list.curselection()
        if not selection:
            return
        index = selection[0]
        if index >= len(self._entries):
            return
        line, _title = self._entries[index]
        start = "%d.0" % line
        try:
            end = self._text.index("%s lineend" % start)
        except tk.TclError:
            end = start
        self._text.tag_remove(_HIT_TAG, "1.0", "end")
        self._text.tag_add(_HIT_TAG, start, end)
        self._text.see(start)
