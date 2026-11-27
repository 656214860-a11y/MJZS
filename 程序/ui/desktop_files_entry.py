# -*- coding: utf-8 -*-
"""项目文件入口钮的外轨排布（从面板模块拆出，避免单文件超过 1000 行）。"""
from ui_tokens import SPACING


def pack_entry_buttons(panel):
    """「项目文件」与正下方「导入文件到当前阶段目录」一起挂进最右外轨。"""
    if not panel.button.winfo_manager():
        panel.button.pack(side='top', fill='x', padx=SPACING['none'],
                           pady=(SPACING['sm'], SPACING['xs']))
    imp = getattr(panel, 'import_button', None)
    if imp is not None and not imp.winfo_manager():
        imp.pack(side='top', fill='x', padx=SPACING['none'],
                 pady=(SPACING['none'], SPACING['xs']))
