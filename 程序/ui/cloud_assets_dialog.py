"""云图片模型「Comfy 账户」设置窗口（L4）；密钥读写与校验在 ``cloud_assets``。"""
from infra.cloud_assets import get_key, redact, save_key
from ui_tokens import CHAR_WIDTH, WRAPLENGTH, SPACING


def settings(parent):
    import tkinter as tk
    import webbrowser
    from tkinter import ttk
    from account_inputs import PasswordInput
    from ui_widgets import (Card, DescriptionBlock, FormDialog, PrimaryButton,
                            ProgressLabel, SecondaryButton, notify)
    win = FormDialog(parent, '云图片模型 · Comfy 账户', modal=False, chrome=False)
    win.withdraw();win.transient(parent)
    body = Card(win, padding=16);body.pack(fill='both', expand=True)
    DescriptionBlock(body, text='Seedream 5.0 Pro / Nano Banana Pro / GPT Image 2', wraplength=WRAPLENGTH['md']).pack(anchor='w')
    DescriptionBlock(body, text='使用 ComfyUI 账户余额；本地 FLUX 无需此密钥。', wraplength=WRAPLENGTH['md']).pack(anchor='w', pady=SPACING['xs'])
    DescriptionBlock(body,text='1. 打开 Comfy 账户并登录或注册。\n2. 在 API Keys 页面创建密钥，复制到下方并保存。\n3. 确认账户有可用余额，再返回手动制作资产。',wraplength=WRAPLENGTH['md']).pack(anchor='w',pady=SPACING['xs'])
    ttk.Label(body, text='Comfy API Key（统一保存到 程序目录/private/.env，不写入工作流）').pack(anchor='w')
    saved = get_key()
    token = tk.StringVar(value=saved)
    PasswordInput(body, textvariable=token, width=CHAR_WIDTH['field_md']).pack(fill='x', pady=SPACING['xs'])
    status = tk.StringVar(value='已保存密钥（%s）' % redact(saved) if saved
                           else '尚未配置，暂不能从助手批量调用云模型')
    ProgressLabel(body, textvariable=status, wraplength=WRAPLENGTH['md']).pack(anchor='w')
    row = ttk.Frame(body);row.pack(fill='x', pady=(SPACING['md'], SPACING['none']))
    def save():
        try:save_key(token.get());win.destroy()
        except Exception as exc:notify(win, str(exc), level='error', title='保存失败', status=status)
    PrimaryButton(row, text='保存', command=save).pack(side='left')
    SecondaryButton(row, text='打开 Comfy 账户', command=lambda:webbrowser.open('https://platform.comfy.org/')).pack(side='left', padx=SPACING['xs'])
    SecondaryButton(row, text='获取 API Key', command=lambda:webbrowser.open('https://platform.comfy.org/profile/api-keys')).pack(side='left', padx=SPACING['xs'])
    win.update_idletasks()
    x = max(0, parent.winfo_rootx() + (parent.winfo_width()-win.winfo_reqwidth())//2)
    y = max(0, parent.winfo_rooty() + (parent.winfo_height()-win.winfo_reqheight())//2)
    win.geometry(f'+{x}+{y}');win.deiconify()
