"""Local settings for the user's own Volcengine Seedream API account."""
import tkinter as tk
import webbrowser
from tkinter import ttk
import seedream_api as api
import tk_timers
from ui_widgets import (Card, DescriptionBlock, LineInput, PrimaryButton, ProgressLabel,
                        SecondaryButton, ask_confirmation, notify)
from ui_widgets import BaseDialog


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
    body=Card(win);body.pack(fill='both',expand=True,padx=16,pady=16);body.columnconfigure(1,weight=1)
    DescriptionBlock(body,text='使用您自己的火山方舟 API Key，费用计入火山账户，无需 Comfy 余额。',wraplength=690).grid(row=0,column=0,columnspan=3,sticky='w',pady=(0,12))
    values={key:tk.StringVar(value=value) for key,value in {'base_url':api.DEFAULT_URL,'model':'','api_key':''}.items()}
    current=['']
    def fill(profile_id=''):
        try:profile=api.load_profile(profile_id)
        except ValueError:return
        current[0]=profile['profile_id']
        for key,value in values.items():value.set(profile[key])
    fill()
    for row,key,label in [(1,'base_url','API 根地址'),(2,'model','模型 ID'),(3,'api_key','火山 API Key')]:
        ttk.Label(body,text=label).grid(row=row,column=0,sticky='w',padx=(0,12))
        LineInput(body,textvariable=values[key],show='•' if key=='api_key' else '').grid(row=row,column=1,columnspan=2,sticky='ew',pady=6)
    DescriptionBlock(body,text='模型 ID 填写火山控制台已开通的实际值，也支持推理接入点 ID。\n支持纯提示词或最多 10 张分类参考图；每项生成一张，批量顺序执行。',wraplength=690).grid(row=4,column=0,columnspan=3,sticky='w',pady=8)
    ttk.Label(body,text='已保存模型').grid(row=5,column=0,sticky='w')
    selected=tk.StringVar();choices={}
    dropdown=ttk.Combobox(body,textvariable=selected,state='readonly');dropdown.grid(row=5,column=1,sticky='ew',pady=6)
    def refresh():
        choices.clear()
        for key,value in api.read_settings().get('profiles',{}).items():
            if not value.get('retired'):choices[value['model']+' · '+key[:6]]=key
        dropdown.configure(values=list(choices))
        selected.set(next((label for label,key in choices.items() if key==current[0]),''))
    def choose(event=None):
        if selected.get() in choices:fill(choices[selected.get()])
    dropdown.bind('<<ComboboxSelected>>',choose);refresh()
    status=tk.StringVar(value='密钥加密保存到本机；保存配置不会发起付费生成。')
    ProgressLabel(body,textvariable=status,wraplength=690).grid(row=6,column=0,columnspan=3,sticky='w',pady=8)
    def remove():
        key=choices.get(selected.get())
        if not key:return
        data=api.read_settings();data['profiles'][key]['retired']=True
        if data.get('active')==key:data['active']=''
        api.write_settings(data);current[0]='';refresh()
        values['model'].set('');values['api_key'].set('');status.set('模型已从列表移除；进行中的任务仍使用原配置。')
    SecondaryButton(body,text='删除模型',command=remove).grid(row=5,column=2,padx=(8,0))
    row=ttk.Frame(body);row.grid(row=7,column=0,columnspan=3,sticky='ew',pady=(10,0))
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
        from api_endpoints import normalize_url, probe_endpoint
        try:url=normalize_url(values['base_url'].get())
        except ValueError as exc:status.set(str(exc));return
        status.set('正在测试连接…')
        import threading
        outcome=[]
        def run():
            # 工作线程只写普通列表：跨线程设置 Tk 变量会抛 RuntimeError，状态栏会一直停在「正在检测」。
            try:outcome.append(probe_endpoint(url))
            except Exception as exc:outcome.append({'reachable':False,'error':type(exc).__name__})
        def poll():
            if not win.winfo_exists():return
            if not outcome:return
            result=outcome[0]
            if result.get('reachable') and result.get('code') in (401,403,404):text='接口可达（HTTP %s，需密钥）'%result['code']
            elif result.get('reachable'):text='接口可达（HTTP %s）'%result['code']
            else:text='连接失败：'+str(result.get('error','未知错误'))
            status.set(text);stop()
        threading.Thread(target=run,daemon=True).start()
        stop=tk_timers.repeat(win,150,poll);poll()
    PrimaryButton(row,text='保存',command=commit).pack(side='left')
    SecondaryButton(row,text='检查配置',command=check).pack(side='left',padx=5)
    SecondaryButton(row,text='测试连接',command=probe).pack(side='left',padx=5)
    SecondaryButton(row,text='打开火山控制台',command=lambda:webbrowser.open('https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey')).pack(side='left',padx=5)
    SecondaryButton(row,text='取消',command=win.destroy).pack(side='right')
    win.update_idletasks();x=max(0,parent.winfo_rootx()+(parent.winfo_width()-win.winfo_width())//2);y=max(0,parent.winfo_rooty()+(parent.winfo_height()-win.winfo_height())//2)
    win.geometry(f'+{x}+{y}');win.deiconify()
