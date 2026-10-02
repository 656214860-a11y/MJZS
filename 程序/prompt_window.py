"""提示词复制窗口：首帧图片提示词与资产提示词共用同一套弹窗与复制行为。

两个入口（06 首帧管理的「查看首帧提示词」与资产管理页的「查看提示词」）以前各写一份弹窗，
复制成功后的行为因此容易走偏。这里只保留一份实现：复制成功即写剪贴板、写状态栏，然后关闭本窗口，
「复制提示词」在所有提示词窗口里表现一致。提示词为空时窗口保持打开、复制按钮禁用，
避免把「尚未填写」的说明当成提示词复制出去。
"""
import tkinter as tk
from tkinter import ttk,messagebox
import re

from clipboard_lock import hold as hold_clipboard
from ui_widgets import BaseDialog


_SECRET_VALUE = re.compile(r"(?i)(\b(?:api[_-]?key|secret|token|password)\s*[=:]\s*)([^\s,;]+)|\bsk-[A-Za-z0-9_-]{8,}")


def copy_preview(text, limit=40):
    """供状态栏使用的复制回执，绝不把疑似凭据回显到 UI。"""
    value = str(text or "").replace("\n", " ").strip()
    value = _SECRET_VALUE.sub(lambda match: (match.group(1) or "") + "***", value)
    return value[:max(0, int(limit))]


def copy_text(owner,text):
    """把文本写进系统剪贴板：成功返回空串，失败返回原因。

    全程序只有这一处写剪贴板（提示词窗口与 Codex 任务文本都走它）：复制行为不再各写一份，
    历史上正是各写一份才出现「一个窗口复制后关、另一个不关」以及「复制失败没人处理」。
    """
    with hold_clipboard() as acquired:
        if not acquired:
            return '剪贴板暂时被占用，请稍后重试'
        try:
            owner.clipboard_clear();owner.clipboard_append(str(text));owner.update_idletasks()
        except tk.TclError as exc:
            return str(exc)
    return ''


def show(parent,title,text,status=None,receipt='',empty_text='',empty_hint='',source='',geometry='800x460',scrollbar=False,button='复制提示词'):
    """弹出只读提示词窗口：复制成功写剪贴板并关窗；没有提示词时保持打开且禁用复制。"""
    win=BaseDialog(parent,title,geometry=geometry,modal=False)
    content=win.content
    if source:ttk.Label(content,text=source,wraplength=760).pack(anchor='w',padx=12,pady=(8,0))
    box=tk.Text(content,wrap="word",padx=12,pady=12)
    if scrollbar:
        bar=ttk.Scrollbar(content,orient="vertical",command=box.yview)
        box.configure(yscrollcommand=bar.set);bar.pack(side="right",fill="y")
    box.insert("1.0",text or empty_text);box.configure(state="disabled");box.pack(fill="both",expand=True)
    hint=ttk.Label(content,text=empty_hint if not text else '',style="Muted.TLabel")
    hint.pack(side="bottom",pady=(0,8))
    def copy():
        # 复制成功后关闭本窗口：与其他提示词复制窗口保持一致；剪贴板归主窗口所有，关窗不会丢内容。
        reason=copy_text(parent.winfo_toplevel(),text)
        if reason:
            messagebox.showerror("复制提示词","复制失败，请重试："+reason,parent=win);return
        if status is not None and receipt:status.set(receipt)
        win.destroy()
    action=ttk.Button(win.actions,text=button,command=copy)
    action.pack(side="right",pady=(8,2))
    if not text:action.configure(state="disabled")
    return win
