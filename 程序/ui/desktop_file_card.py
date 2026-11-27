# -*- coding: utf-8 -*-
"""文件表悬停预览卡片：列窄截断文件名时，悬停读到磁盘上的完整文件名（R1964）。"""
import tkinter as tk
from pathlib import Path

from ui_tokens import (COLORS, FONTS, SPACING, TOOLTIP_BACKGROUND, TOOLTIP_BORDER_WIDTH, TOOLTIP_FONT,
                       TOOLTIP_FOREGROUND, TOOLTIP_PADDING, TOOLTIP_WRAPLENGTH)
from ui_widgets import TreeRowTooltip


class TreeRowCard(TreeRowTooltip):
    """树表逐行预览卡片：文本首行是标题（如完整文件名，粗体折行），其余行是说明。

    数据由调用方预先提供，悬停不读磁盘。
    """

    def _populate(self, tip):
        title, _sep, detail = self.text.partition("\n")
        kwargs = dict(bg=TOOLTIP_BACKGROUND, padx=TOOLTIP_PADDING[0], justify="left",
                      anchor="w", wraplength=TOOLTIP_WRAPLENGTH)
        tk.Label(tip, text=title, font=FONTS["body_bold"], fg=TOOLTIP_FOREGROUND,
                 pady=TOOLTIP_PADDING[1], **kwargs).pack(
            fill="x", padx=TOOLTIP_BORDER_WIDTH, pady=(TOOLTIP_BORDER_WIDTH, SPACING["none"]))
        if detail:
            tk.Label(tip, text=detail, font=TOOLTIP_FONT, fg=COLORS["text_secondary"],
                     pady=TOOLTIP_PADDING[1], **kwargs).pack(
                fill="x", padx=TOOLTIP_BORDER_WIDTH, pady=(SPACING["none"], TOOLTIP_BORDER_WIDTH))


def script_row_card(row, label, modified, project_root):
    """卡片文本：首行是磁盘上的完整文件名，其余为说明；全部取自已加载的行数据，不读磁盘。"""
    path = Path(row.item_id)
    lines = [path.name]
    if row.name != path.name:
        lines.append('列表显示：' + row.name)
    if label:
        lines.append('状态：' + label)
    lines.append('修改时间：' + modified)
    try:
        folder = path.parent.relative_to(project_root).as_posix()
    except ValueError:
        folder = str(path.parent)
    lines.append('位置：' + folder)
    return '\n'.join(lines)


def pack_entry_buttons(panel):
    """「项目文件」与正下方「导入文件到当前阶段目录」一起挂进最右外轨。"""
    if not panel.button.winfo_manager():
        panel.button.pack(side='top', fill='x', padx=SPACING['none'],
                           pady=(SPACING['sm'], SPACING['xs']))
    imp = getattr(panel, 'import_button', None)
    if imp is not None and not imp.winfo_manager():
        imp.pack(side='top', fill='x', padx=SPACING['none'],
                 pady=(SPACING['none'], SPACING['xs']))

