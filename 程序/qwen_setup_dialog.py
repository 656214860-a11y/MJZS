"""Qwen Code「API 设置」窗口：编辑根地址、默认模型与 API Key，管理已保存模型并测试连接。

只负责 Tk 控件与事件；连接设置的读取、校验与密钥读写都经 ``qwen_setup``。
"""
import json,threading
# 第 34 期第 9 条：`urllib.request` 连 ssl 一起加载（约 4.4 MB 常驻），验证连接时才 import。
import tkinter as tk
from tkinter import ttk
from api_models import records,remember,remove,label,identity
from agent.core import save
from qwen_setup import load,save_key,settings_path,unified_key,validate
import tk_timers
from ui_tokens import WRAPLENGTH, SPACING
from ui_widgets import (SelectBox, Card, DescriptionBlock, FormDialog, LineInput, PrimaryButton,
                        ProgressLabel, SecondaryButton, ask_confirmation, notify)

def show(parent,on_saved=None):
    win=FormDialog(parent,'Qwen Code · API 设置',geometry='780x480',modal=False,chrome=False)
    body=Card(win);body.pack(fill='both',expand=True,padx=SPACING['lg'],pady=SPACING['lg']);body.columnconfigure(1,weight=1)
    DescriptionBlock(body,text='支持阿里云百炼或自定义 OpenAI 兼容接口；填写后点击保存设置。').grid(row=0,column=0,columnspan=2,sticky='w',pady=(SPACING['none'],SPACING['md']))
    vars={k:tk.StringVar(value=v) for k,v in load().items() if k in ('base_url','model','api_key')}
    for row,(key,title) in enumerate([('base_url','API 根地址'),('model','默认模型'),('api_key','API Key')],1):
        ttk.Label(body,text=title).grid(row=row,column=0,sticky='w',padx=(SPACING['none'],SPACING['md']))
        LineInput(body,textvariable=vars[key]).grid(row=row,column=1,sticky='ew',pady=SPACING['sm'])
    DescriptionBlock(body,text='自动批量制作请使用百炼按量付费通用 API；Token Plan 个人版和 Coding Plan 不适用于非交互式批量调用。\n文本和任务执行使用 Qwen；资产与首帧图片交给现有 ComfyUI 工作流。',wraplength=WRAPLENGTH['lg']).grid(row=4,column=0,columnspan=2,sticky='w',pady=SPACING['sm'])
    status=tk.StringVar(value='尚未配置时，可继续选择 ChatGPT/Codex。')
    ProgressLabel(body,textvariable=status,wraplength=WRAPLENGTH['lg']).grid(row=5,column=0,columnspan=2,sticky='w',pady=SPACING['sm'])
    cfg=load()
    ttk.Label(body,text='已保存模型').grid(row=6,column=0,sticky='w',pady=SPACING['sm'])
    preset=tk.StringVar()
    chooser=SelectBox(body,textvariable=preset)
    chooser.grid(row=6,column=1,sticky='ew')
    def refresh_models():
        chooser.set_values([label(r) for r in records(cfg)])
        selected=next((r for r in records(cfg) if identity(r['base_url'],r['model'])==identity(vars['base_url'].get(),vars['model'].get())),None)
        preset.set(label(selected) if selected else '')
    def choose(event=None):
        record=next((r for r in records(cfg) if label(r)==preset.get()),None)
        if record:
            # 第 65 期任务 1：密钥不再随记录存，挑了老记录就把统一那份 .env 里的钥匙补回框里。
            for key,var in vars.items():var.set(record.get(key,'') or (unified_key() if key=='api_key' else ''))
    chooser.bind('<<ComboboxSelected>>',choose);refresh_models()
    def values():return validate({k:v.get() for k,v in vars.items()})
    def commit():
        nonlocal cfg
        try:
            value=values()
            save_key(value['api_key'])                 # 第 65 期任务 1：密钥只进统一那份 .env
            updated=remember(load(),{**value,'api_key':''});save(settings_path(),updated);cfg=updated
            if on_saved:on_saved()
            win.destroy()
        except Exception as exc:notify(win, str(exc), level='error', title='Qwen 设置', status=status)
    def delete_model():
        nonlocal cfg
        try:
            base=vars['base_url'].get().strip().rstrip('/');model=vars['model'].get().strip()
            if not base or not model:raise ValueError('请先选择要删除的模型')
            if not ask_confirmation(win, '删除模型', f'删除模型 {model}？\n接口：{base}\n删除后立即保存，正在执行的任务保持不变。', dangerous=True):return
            updated=remove({**load(),'api_key':''},base,model);save(settings_path(),updated);cfg=updated
            vars['model'].set('');refresh_models()
            status.set('模型已删除并保存。请选择其他模型，或填写新模型后保存。')
            if on_saved:on_saved()
        except (ValueError,OSError) as exc:notify(win, str(exc), level='error', title='Qwen 设置', status=status)
    def check():
        try:cfg=values()
        except ValueError as exc:status.set(str(exc));return
        status.set('正在验证连接…')
        result=[]
        def run():
            from urllib.request import Request,urlopen           # 第 34 期第 9 条：HTTP 栈按需加载
            try:
                request=Request(cfg['base_url']+'/models',headers={'Authorization':'Bearer '+cfg['api_key']})
                with urlopen(request,timeout=15) as response:data=json.load(response)
                models=[str(m.get('id')) for m in data.get('data',[])]
                result.append('API 已连接；模型在返回列表中。' if cfg['model'] in models else 'API 已连接；请确认填写的模型已开通权限。')
            except Exception as exc:
                code=getattr(exc,'code',None)
                result.append('连接失败'+('（HTTP '+str(code)+'）' if code else '')+'，请检查网络、根地址和 API Key。')
        def poll():
            if not win.winfo_exists():return
            if not result:return
            status.set(result[0]);stop()
        threading.Thread(target=run,daemon=True).start()
        stop=tk_timers.repeat(win,250,poll);poll()
    row=ttk.Frame(body);row.grid(row=7,column=0,columnspan=2,sticky='w',pady=SPACING['sm'])
    PrimaryButton(row,text='保存设置',command=commit).pack(side='left')
    SecondaryButton(row,text='删除模型',command=delete_model).pack(side='left',padx=SPACING['sm'])
    SecondaryButton(row,text='测试连接',command=check).pack(side='left',padx=SPACING['sm'])
    SecondaryButton(row,text='打开阿里云百炼',command=lambda:__import__('webbrowser').open('https://bailian.console.aliyun.com/')).pack(side='left')
    return win
