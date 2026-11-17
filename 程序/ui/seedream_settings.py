"""Local settings for the user's own Volcengine Seedream API account."""
import tkinter as tk
import webbrowser
from tkinter import ttk
import seedream_api as api
import tk_timers
from ui_widgets import (SelectBox, Card, DescriptionBlock, LineInput, PrimaryButton, ProgressLabel,
                        SecondaryButton, ask_confirmation, notify)
from ui_widgets import BaseDialog
from account_inputs import PasswordInput
from ui_tokens import BUTTON_GAP, WRAPLENGTH, SPACING


def confirm_unsettled(parent,folder,values,what='镜头'):
    """上次 Seedream 请求没拿到结果时，先让用户核实，再决定是否重新生成。

    确认后把记录降级为 failed（允许本次重新提交）；未确认的编号会被跳过，不会重复扣费。
    返回用户确认可以重新生成的编号。
    """
    blocked=api.unsettled(folder,values)
    if not blocked:return []
    shown='、'.join(blocked[:8])+('…' if len(blocked)>8 else '')
    if not ask_confirmation(parent, 'Seedream 请求结果不确定',
            '有 '+str(len(blocked))+' 个'+what+'上次的 Seedream 请求没有拿到结果，可能已经扣费：\n'+shown+
            '\n\n请先在火山控制台核实这些请求；确认没有生成，再选择“是”重新生成。\n其余'+what+'照常制作，不会重复扣费。',
            dangerous=True):
        return []
    return api.release(folder,blocked)


def show(parent,on_saved=None):
    win=BaseDialog(parent,'Seedream 5.0 Pro · 火山 API',geometry='760x420',minsize=(620,390),modal=False,chrome=False);win.withdraw()
    body=Card(win);body.pack(fill='both',expand=True,padx=SPACING['lg'],pady=SPACING['lg']);body.columnconfigure(1,weight=1)
    DescriptionBlock(body,text='使用您自己的火山方舟 API Key，费用计入火山账户，无需 Comfy 余额。',wraplength=WRAPLENGTH['lg']).grid(row=0,column=0,columnspan=3,sticky='w',pady=(SPACING['none'],SPACING['md']))
    values={key:tk.StringVar(value=value) for key,value in {'base_url':api.DEFAULT_URL,'model':'','api_key':''}.items()}
    current=['']
    def fill(profile_id=''):
        try:profile=api.load_profile(profile_id)
        except ValueError:return
        current[0]=profile['profile_id']
        for key,value in values.items():value.set(profile[key])
    fill()
    for row,key,label in [(1,'base_url','API 根地址'),(2,'model','模型 ID'),(3,'api_key','火山 API Key')]:
        ttk.Label(body,text=label).grid(row=row,column=0,sticky='w',padx=(SPACING['none'],SPACING['md']))
        (PasswordInput if key=='api_key' else LineInput)(body,textvariable=values[key]).grid(row=row,column=1,columnspan=2,sticky='ew',pady=SPACING['xs'])
    DescriptionBlock(body,text='模型 ID 填写火山控制台已开通的实际值，也支持推理接入点 ID。\n支持纯提示词或最多 10 张分类参考图；每项生成一张，批量顺序执行。',wraplength=WRAPLENGTH['lg']).grid(row=4,column=0,columnspan=3,sticky='w',pady=SPACING['sm'])
    ttk.Label(body,text='已保存模型').grid(row=5,column=0,sticky='w')
    selected=tk.StringVar();choices={}
    dropdown=SelectBox(body,textvariable=selected);dropdown.grid(row=5,column=1,sticky='ew',pady=SPACING['xs'])
    def refresh():
        choices.clear()
        for key,value in api.read_settings().get('profiles',{}).items():
            if not value.get('retired'):choices[value['model']+' · '+key[:6]]=key
        dropdown.set_values(list(choices))
        selected.set(next((label for label,key in choices.items() if key==current[0]),''))
    def choose(event=None):
        if selected.get() in choices:fill(choices[selected.get()])
    dropdown.bind('<<ComboboxSelected>>',choose);refresh()
    status=tk.StringVar(value='密钥加密保存到本机；保存配置不会发起付费生成。')
    ProgressLabel(body,textvariable=status,wraplength=WRAPLENGTH['lg']).grid(row=6,column=0,columnspan=3,sticky='w',pady=SPACING['sm'])
    def remove():
        key=choices.get(selected.get())
        if not key:return
        data=api.read_settings();data['profiles'][key]['retired']=True
        if data.get('active')==key:data['active']=''
        api.write_settings(data);current[0]='';refresh()
        values['model'].set('');values['api_key'].set('');status.set('模型已从列表移除；进行中的任务仍使用原配置。')
    SecondaryButton(body,text='删除模型',command=remove).grid(row=5,column=2,padx=(SPACING['sm'],SPACING['none']))
    row=ttk.Frame(body);row.grid(row=7,column=0,columnspan=3,sticky='ew',pady=(SPACING['sm'],SPACING['none']))
    def commit():
        try:
            api.save_profile(values['base_url'].get(),values['model'].get(),values['api_key'].get(), profile_id=current[0] or None)
            if on_saved:on_saved()
            win.destroy()
        except (ValueError,OSError) as exc:notify(win, str(exc), level='error', title='保存失败', status=status)
    def check():
        try:
            api.validate(values['base_url'].get(),values['model'].get(),values['api_key'].get())
            status.set('填写格式正确；实际模型权限和余额将在正式制图时验证。')
        except ValueError as exc:status.set(str(exc))
    def probe():
        from api_endpoints import normalize_url, probe_message
        try:url=normalize_url(values['base_url'].get())
        except ValueError as exc:status.set(str(exc));return
        status.set('正在测试连接…')
        tk_timers.run_in_background(win,lambda:probe_message(url),status.set,lambda exc:status.set('连接失败：'+type(exc).__name__))
    SecondaryButton(row,text='检查配置',command=check).pack(side='left')
    SecondaryButton(row,text='测试连接',command=probe).pack(side='left',padx=(BUTTON_GAP,SPACING['none']))
    SecondaryButton(row,text='打开火山控制台',command=lambda:webbrowser.open('https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey')).pack(side='left',padx=(BUTTON_GAP,SPACING['none']))
    PrimaryButton(row,text='保存',command=commit).pack(side='right')
    SecondaryButton(row,text='取消',command=win.destroy).pack(side='right',padx=(SPACING['none'],BUTTON_GAP))
    win.update_idletasks();x=max(0,parent.winfo_rootx()+(parent.winfo_width()-win.winfo_width())//2);y=max(0,parent.winfo_rooty()+(parent.winfo_height()-win.winfo_height())//2)
    win.geometry(f'+{x}+{y}');win.deiconify()
