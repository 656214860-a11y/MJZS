"""One external Agent selector backed by the same profiles as its settings."""
from pathlib import Path
from weakref import WeakSet
from agent.core import read, save
from workflow_settings import (load, ENGINES, FLOWS, FLOW_SKILLS, SKILL_PRESETS, preset_skill, preset_label,
                                settings_path, set_skills, skills_of, agent_label)


def label(profile, stage, engine, function=None):
    return agent_label(profile,stage,engine,function)


def options(project,stage,function=None):
    cfg=load(project,stage);items={};selected=None
    for engine in ENGINES:
        profile=cfg['profiles'][engine]
        skills=[profile['skill'],*[str(preset_skill(folder)) for _,folder in SKILL_PRESETS if folder in FLOW_SKILLS[stage] and preset_skill(folder).is_file()]]
        for skill in dict.fromkeys(skills):
            name=label({**profile,'skill':skill},stage,engine,function)
            # A configured model can be available through multiple engines.
            if name in items:name=name.replace('.', '（'+ENGINES[engine]+'）.',1)
            items[name]=(engine,skill)
            if engine==cfg['engine'] and skill==profile['skill']:selected=name
    return items,selected


def choose(project,stage,pair):
    engine,skill=pair
    if engine not in ENGINES:raise ValueError('未知的 Agent 引擎')
    if skill and not Path(skill).is_file():raise ValueError('Skill 文件不存在，请重新选择')
    target=settings_path(project);data=read(target) if target.is_file() else {}
    cfg=load(project,stage);cfg['engine']=engine
    set_skills(cfg['profiles'][engine],[skill] if skill else [])   # 选中一个 Agent＝只挂这一份
    data.setdefault('flows',{})[stage]=cfg;save(target,data)


def refresh(desktop):
    for widget in list(getattr(desktop,'_agent_selectors',())):
        if widget.winfo_exists():widget.refresh_agent()


def selector(desktop,parent,stage,function=None):
    import tkinter as tk
    from tkinter import ttk
    project=desktop.root
    box=ttk.Frame(parent);box.pack(side='left',padx=(0,4))
    model=tk.StringVar();skill=tk.StringVar()
    ttk.Label(box,text='模型').pack(side='left',padx=(4,3))
    models=ttk.Combobox(box,textvariable=model,state='readonly',width=12);models.pack(side='left')
    ttk.Label(box,text='Skill').pack(side='left',padx=(7,3))
    skills=ttk.Combobox(box,textvariable=skill,state='readonly',width=9);skills.pack(side='left')
    model_choices={};skill_choices={}
    def update():
        nonlocal model_choices,skill_choices
        cfg=load(project,stage)
        model_choices={}
        for engine,engine_name in ENGINES.items():
            name=cfg['profiles'][engine].get('model','').strip() or engine_name
            while name in model_choices:name+=' · '+engine_name
            model_choices[name]=engine
        models.configure(values=list(model_choices))
        model.set(next(k for k,v in model_choices.items() if v==cfg['engine']))
        profile=cfg['profiles'][cfg['engine']]
        paths=[profile['skill'],'',*[str(preset_skill(folder)) for _,folder in SKILL_PRESETS if folder in FLOW_SKILLS[stage] and preset_skill(folder).is_file()]]
        skill_choices={}
        for path in dict.fromkeys(paths):
            name=preset_label(path) if path else '内置'
            if name=='自定义 Skill':name='自定义'
            while name in skill_choices:name+=' *'
            skill_choices[name]=path
        skills.configure(values=list(skill_choices));skill.set(next(k for k,v in skill_choices.items() if v==profile['skill']))
    def close_settings():
        key=(str(Path(project).resolve()),stage)
        dialog=getattr(desktop,'_flow_settings_dialogs',{}).get(key)
        if dialog is not None and dialog.winfo_exists():
            update();dialog.lift()
            raise ValueError('请先保存或关闭当前设置，再切换模型或 Skill')
    def apply_model():
        close_settings()
        cfg=load(project,stage);engine=model_choices[model.get()]
        choose(project,stage,(engine,cfg['profiles'][engine]['skill']));refresh(desktop)
        desktop.status.set('已切换模型：'+model.get())
    def apply_skill():
        close_settings()
        cfg=load(project,stage);choose(project,stage,(cfg['engine'],skill_choices[skill.get()]));refresh(desktop)
        desktop.status.set('已切换 Skill：'+skill.get())
    models.bind('<<ComboboxSelected>>',lambda e:desktop.safe(apply_model))
    skills.bind('<<ComboboxSelected>>',lambda e:desktop.safe(apply_skill))
    def state(spec=None):
        if spec is None:return models.state()
        models.state(spec);skills.state(spec)
    box.state=state;box.refresh_agent=update;box.model_combo=models;box.skill_combo=skills
    if not hasattr(desktop,'_agent_selectors'):desktop._agent_selectors=WeakSet()
    desktop._agent_selectors.add(box);update()
    return box
