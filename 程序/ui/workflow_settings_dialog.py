"""工作流「调用设置」窗口：按项目、按流程编辑制作引擎、模型 ID、Skill 与补充要求。

只负责 Tk 控件与事件；配置的解析、校验与读写都经 ``workflow_settings``，保存走 ``save_flow``。
"""
import copy
import os
from pathlib import Path
from tkinter import ttk
import tkinter as tk

from orchestrator.workflow_settings import (ENGINES, FLOWS, FLOW_SKILLS, SKILL_DETAILS, SKILL_PRESETS, agent_label,
                               find_program, load, preset_folder, preset_skill, save_flow, set_skills,
                               skills_of, sync_qwen_model, validate_stage_profile)
from ui_dialogs import FileDialog
import ui_plugin_registry
from ui_widgets import BaseDialog, Card, PrimaryButton, SecondaryButton, Tooltip, notify
from ui_widgets import LineInput, TextArea
from ui_tokens import TEXT_ROWS, WRAPLENGTH, SPACING, ICON_MICROPHONE


def show_settings(desktop,project,on_saved=None,stage='previs',function=None):
    dialog_key=(str(Path(project).resolve()),stage)
    dialogs=getattr(desktop,'_flow_settings_dialogs',{})
    previous=dialogs.get(dialog_key)
    if previous is not None and previous.winfo_exists():
        previous.lift();previous.model_entry.focus_set();return previous
    saved=load(project,stage);draft=copy.deepcopy(saved)
    stage_presets=[(label,folder) for label,folder in SKILL_PRESETS if folder in FLOW_SKILLS[stage] and preset_skill(folder).is_file()]
    win=BaseDialog(desktop.win,FLOWS[stage]+' · 调用设置',geometry='800x610',minsize=(640,520),modal=False,chrome=False);win.attributes('-alpha',0)
    # The shared placement handler reveals the dialog after centering it.
    dialogs[dialog_key]=win;desktop._flow_settings_dialogs=dialogs
    footer=ttk.Frame(win,padding=(16,8));footer.pack(side='bottom',fill='x')
    body=Card(win);body.pack(fill='both',expand=True,padx=SPACING['lg'],pady=SPACING['lg']);body.columnconfigure(1,weight=1)
    ttk.Label(body,text='当前项目的本流程生效；保存后用于新任务，进行中的整批任务不变。',wraplength=WRAPLENGTH['lg']).grid(row=0,column=0,columnspan=3,sticky='w',pady=(SPACING['none'],SPACING['xs']))
    # 第 63 期任务 3.1／3.2：每一次打开阶段配置都能看见「本步怎么并行」和「门禁过没过」——
    # 口径只有 stage_parallel 一处（附件那张并行配置速查表）。
    from orchestrator.stage_parallel import page_lines
    ttk.Label(body,text='\n'.join(page_lines(project,stage)),justify='left',
              wraplength=WRAPLENGTH['lg'],style='Muted.TLabel').grid(row=0,column=0,columnspan=3,sticky='w',pady=(SPACING['none'],SPACING['md']))
    chosen=tk.StringVar(value=ENGINES[saved['engine']]);active=[saved['engine']]
    ttk.Label(body,text='制作引擎').grid(row=1,column=0,sticky='w',padx=(SPACING['none'],SPACING['md']))
    selector=ttk.Label(body,textvariable=chosen);selector.grid(row=1,column=1,sticky='ew',pady=SPACING['xs'])
    values={key:tk.StringVar() for key in ('program','model','skill')}
    custom=ttk.LabelFrame(body,text='自定义模型 / Skill / API',padding=10)
    custom.grid(row=3,column=0,columnspan=3,sticky='ew',pady=(SPACING['sm'],SPACING['xs']));custom.columnconfigure(1,weight=1)
    def browse(key):
        name=FileDialog(win).open_file(title='选择 '+('SKILL.md' if key=='skill' else ENGINES[active[0]]+' 命令行程序'),
            filetypes=[('Skill','SKILL.md')] if key=='skill' else [('命令行程序','*.exe')])
        if name:values[key].set(name)
    for row,key,label in [(1,'program','程序位置'),(0,'model','自定义模型 ID'),(3,'skill','Skill 文件')]:
        ttk.Label(custom,text=label).grid(row=row,column=0,sticky='w',padx=(SPACING['none'],SPACING['md']))
        entry=LineInput(custom,textvariable=values[key],state='normal');entry.grid(row=row,column=1,sticky='ew',pady=SPACING['xs'])
        if key=='model':win.model_entry=entry
        if key=='skill':skill_entry=entry
        if key!='model':SecondaryButton(custom,text='选择文件',command=lambda k=key:browse(k)).grid(row=row,column=2,padx=(SPACING['sm'],SPACING['none']))
    ttk.Label(custom,text='模型 ID 可直接填写；留空使用默认模型。保存后更新外面的 Agent 名称。',wraplength=WRAPLENGTH['lg'],style='Muted.TLabel').grid(row=4,column=0,columnspan=3,sticky='w',pady=SPACING['xs'])
    skill_details=tk.StringVar()
    def update_skill(*_):
        value=values['skill'].get()
        skill_details.set(SKILL_DETAILS.get(preset_folder(value),'自定义文件将随任务交给所选引擎读取。' if value else '仅使用本流程的内置要求。'))
    values['skill'].trace_add('write',update_skill)
    ttk.Label(custom,textvariable=skill_details,wraplength=WRAPLENGTH['lg']).grid(row=5,column=0,columnspan=3,sticky='w',pady=SPACING['xs'])
    ttk.Label(body,text='补充制作要求（可选）').grid(row=4,column=0,columnspan=2,sticky='w')
    notes=TextArea(body,height=TEXT_ROWS['sm'],wrap='word',undo=True);notes.grid(row=5,column=0,columnspan=3,sticky='nsew',pady=SPACING['xs']);body.rowconfigure(5,weight=1)
    feedback=tk.StringVar(value='模型与 Skill 在主页面切换；此处编辑当前配置，保存后自动关闭。')
    ttk.Label(body,textvariable=feedback,wraplength=WRAPLENGTH['lg']).grid(row=6,column=0,columnspan=3,sticky='w',pady=SPACING['xs'])
    # 语音输入离线化任务书轮 5：补充要求框复用共享听写组件（非 Windows 不显示麦克风）。
    # 经 ui_plugin_registry 延迟加载，避免 L4 页面散落动态 import（规则 18）。
    if os.name=='nt':
        mic=SecondaryButton(body,text=ICON_MICROPHONE,width=0,style='Tokens.Composer.Icon.TButton')
        mic.grid(row=4,column=2,sticky='e')
        mic.configure(command=lambda:voice_input.toggle())
        Tooltip(mic,'语音输入：点一下开始录音，再点一下结束并转成文字')
        voice_input=ui_plugin_registry.module('desktop_voice_input').VoiceInput(notes,mic,status=feedback,project=project)
    ttk.Label(body,text='当前 Agent').grid(row=2,column=0,sticky='w')
    agent_name=tk.StringVar()
    ttk.Label(body,textvariable=agent_name,wraplength=WRAPLENGTH['sm']).grid(row=2,column=1,columnspan=2,sticky='w',pady=SPACING['xs'])
    def update_agent_label(*_):
        agent_name.set(agent_label({k:v.get() for k,v in values.items()},stage,active[0],function))
    values['skill'].trace_add('write',update_agent_label)
    values['model'].trace_add('write',update_agent_label)
    def stash():
        profile={**{k:v.get().strip() for k,v in values.items()},'instructions':notes.get('1.0','end-1c').strip()}
        # 第 59 期第 5 条：这一格改的是这一档的第一份 SKILL，面板上勾的其余几份照旧留着。
        rest=skills_of(draft['profiles'][active[0]])[1:]
        set_skills(profile,([profile['skill']] if profile['skill'] else [])+rest)
        draft['profiles'][active[0]]=profile
    def populate():
        profile=draft['profiles'][active[0]]
        if active[0]=='qwen' and not profile['program']:
            try:profile['program']=find_program({'engine':'qwen','program':''})
            except ValueError:pass
        for key,var in values.items():var.set(profile[key])
        notes.delete('1.0','end');notes.insert('1.0',profile['instructions'])
        api_button.state(['!disabled'] if active[0]=='qwen' else ['disabled'])
        update_agent_label()
    def check():
        try:
            stash();cfg={'engine':active[0],**validate_stage_profile(draft['profiles'][active[0]],stage)}
            feedback.set('已找到程序：'+find_program(cfg)+'；登录和模型权限将在制作时验证。')
        except Exception as exc:feedback.set(str(exc))
    def commit():
        try:
            stash();save_flow(project,stage,draft,active[0])
            if on_saved:on_saved()
            win.destroy()
        except Exception as exc:notify(win, str(exc), level='error', title='调用设置', status=feedback)
    def api_saved():
        model=__import__('qwen_setup').load()['model']
        sync_qwen_model(project,model)
        draft['profiles']['qwen']['model']=model
        if active[0]=='qwen':values['model'].set(model)
        feedback.set('API 设置已保存，Qwen 模型已同步。')
    api_button=SecondaryButton(custom,text='自定义 API（Qwen）',command=lambda:__import__('ui.qwen_setup_dialog').show(win,on_saved=api_saved))
    api_button.grid(row=0,column=2,padx=(SPACING['sm'],SPACING['none']))
    row=ttk.Frame(footer);row.pack(side='right')
    SecondaryButton(row,text='检查配置',command=check).pack(side='left',padx=SPACING['xs'])
    PrimaryButton(row,text='保存',command=commit).pack(side='left',padx=SPACING['xs'])
    SecondaryButton(row,text='取消',command=win.destroy).pack(side='left')
    populate()
    def focus_model():
        if win.winfo_exists():win.lift();win.model_entry.focus_set()
    focus_timer=win.after_idle(focus_model)
    def disposed(event):
        if event.widget is win:
            try:win.after_cancel(focus_timer)
            except tk.TclError:pass
            if dialogs.get(dialog_key) is win:dialogs.pop(dialog_key,None)
    win.bind('<Destroy>',disposed,add='+')
    return win
