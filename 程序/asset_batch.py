"""Sequential local asset generation with ID-based registration and resumable jobs."""
import json,os,re,uuid,threading,queue
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from agent.core import read
from comfy_service import Comfy
from stage_execution_service import remove_asset_batch_model as remove_model, save_asset_batch_settings as save_settings
import tk_timers
import ui_plugin_registry
from responsive_ui import FlowBar, scroll_form
from platform_tools import open_target
from ui_tokens import COLORS, FONTS, SPACING
from ui_dialogs import FileDialog
from ui_widgets import SelectBox, BaseDialog, DataTable, DescriptionBlock, LineInput, PrimaryButton, ProgressLabel, SecondaryButton, ask_confirmation
from asset_batch_service import (
    KINDS, asset_prompt as _asset_prompt, register_image as _register_image,
    image_ready as _image_ready, batch_complete as _batch_complete,
    automatic_plan as _automatic_plan, auto_settings as _auto_settings,
    current_model as _current_model, unattended_plan as _unattended_plan,
)
from asset_auto_batch_service import auto_batch as _auto_batch
from asset_batch_state_service import ledger_path, uncertain_assets, prune_raw_outputs, ready_asset_ids
from asset_batch_selection_service import all_selected, scope_label, set_selection, toggle_excluded
from stage_execution_service import remove_asset_batch_model as remove_model, save_asset_batch_settings as save_settings


def release_uncertain(project, ids):
    """兼容旧入口；L4 只经 L3 放开已核实的未知提交记录。"""
    from stage_execution_service import release_uncertain_asset_batch
    return release_uncertain_asset_batch(project, ids)
from asset_batch_controller import AssetBatchController, WORKFLOW_MODEL



def _launch_skill_batch(app, project, base, items):
    """Invoke the optional skill-runner from the UI boundary.

    The runner is loaded only for the user-triggered skill path, preventing
    the asset window module from becoming a static dependency of orchestration
    services during ordinary asset browsing.
    """
    return ui_plugin_registry.module('asset_skill_batch').launch(app, project, base, items)


def _attach_native_controls(*args, **kwargs):
    """Load native-generation controls only for the dedicated UI mode."""
    return ui_plugin_registry.module('native_assets').attach_controls(*args, **kwargs)


def _is_skill_api_engine(project):
    """Read the selected asset workflow engine at the interactive UI edge."""
    return ui_plugin_registry.module('workflow_settings').current(project, 'assets')['engine'] == 'qwen'


def _prefs(path):
    """读 ui_settings.json：与桌面页共用同一个入口（损坏时报同一句可操作的中文提示）。

    这里故意用不缓存的读法：调用方会就地改这份字典再写回，共享缓存对象一旦被就地改，
    同一轮里其他读者就会看到还没保存的值。
    """
    from project_settings import read_prefs
    return read_prefs(path)


class AssetSubmissionUncertain(ValueError):
    """批量提交结果无法确认：只跳过并提示，绝不自动重提，避免重复生成或重复扣费。"""


def asset_prompt(asset,kind):
    return _asset_prompt(asset,kind)


def register_image(base,aid,asset,image):
    from stage_execution_service import asset_batch_gateway
    return _register_image(base,aid,asset,image,gateway=asset_batch_gateway())

def image_ready(base,aid,registry=None):
    return _image_ready(base,aid,registry)


def batch_complete(base,aids):
    """所选资产是否都已落盘进资产库：只看结果，不看生成流程返回的中文文案。

    批量返回的消息里既有「已停止」「等待时间较长」这类没做完的，也有失败汇总；
    靠关键字判断会把没做完的批次当成成功弹「已自动保存」。
    """
    return _batch_complete(base,aids)


def run_batch(project,base,items,options,events,stop,client_factory=Comfy):
    """Compatibility entry point; UI code delegates to the headless executor."""
    from asset_batch_execution import run_batch as execute_batch
    return execute_batch(project,base,items,options,events,stop,client_factory)

def auto_settings(project):
    """无人值守批量资产复用的设置：批量窗口保存过的 asset_batch（连接、模型与各类别勾选）。"""
    return _auto_settings(project)


def current_model(project):
    """「资产图片制作」窗口当前的生图模型（第 46 期第 8 条）。

    模型只有一个入口——「阶段配置 → 模型」（写在项目自己的 skill_config.json 里，阶段 id＝assets），
    这里只是把它翻成一行只读文字。升级上来的老项目里 ui_settings.json 存过的那一档仍然兜底：
    阶段配置还没挑过生产模型时按它显示，看到的还是原来那个模型；挑过就以阶段配置为准。
    """
    return _current_model(project)


def auto_plan(project,base,sources,scope='adopted'):
    """无人值守资产清单：勾选类别里缺图、且清单已补齐的资产；其余连同原因放进 skipped。

    用的模型与「资产图片制作」窗口当前保存的生图模型一致：本地模型照常排队，云端模型按次计费，
    所以状态栏和勾选框都会写明当前模型，用户随时能停掉或换成便宜的后端。
    """
    from stage_execution_service import plan_unattended_assets
    return plan_unattended_assets(project,base,sources,scope)


def auto_batch(project,base,sources,scope='adopted',log=None,stop=None,client_factory=Comfy):
    """Compatibility facade for the headless unattended batch service."""
    from stage_execution_service import asset_plan_gateway
    return _auto_batch(project,base,sources,scope,log,stop,client_factory,gateway=asset_plan_gateway())


def show(app,engine="comfy",selected_ids=None):
    skill_mode=engine=="skill"
    qwen_images=skill_mode and _is_skill_api_engine(app.root)
    project=Path(app.root);base=app.asset_base();source=app.current_frame_json();scope=app.asset_scope();sources=app.asset_sources()
    prefsfile=project/'ui_settings.json';prefs=_prefs(prefsfile);saved=prefs.get('asset_batch',{})
    from stage_execution_service import sync_asset_plan
    controller=AssetBatchController(project,base,sources,scope,engine,selected_ids,saved,sync_asset_plan)
    base=app.asset_base();controller.base=base
    scope_text=scope_label(scope,sources,read(source).get('episode_id',''))
    win=BaseDialog(app.win,'',modal=False,chrome=False);win.withdraw();win.title(('资产图片制作' if skill_mode or engine=='workflow' else 'ComfyUI')+' · 批量资产 · '+scope_text);win.geometry('850x640');win.minsize(700,480);win.transient(app.win)
    win.protocol('WM_DELETE_WINDOW',win.destroy)
    # Keep production buttons visible while the long API form scrolls above them.
    footer=ttk.Frame(win);footer.pack(side='bottom',fill='x')
    viewport=ttk.Frame(win);viewport.pack(side='top',fill='both',expand=True)
    view=scroll_form(viewport,bg=COLORS['background_primary']);form=view.form     # 滚动表单区与首帧制作共用一份实现
    ttk.Label(form,text='选择资产类别 → 开始批量生成 → 按编号和名称自动导入',font=FONTS['title']).pack(anchor='w',padx=SPACING['lg'],pady=SPACING['md'])
    DescriptionBlock(form,text='生成范围：'+scope_text+'；道具仅制作关键道具，普通道具随画面生成；已导入图片自动跳过。').pack(anchor='w',padx=SPACING['lg'])
    if qwen_images:DescriptionBlock(form,text='由 Qwen 按所选 Skill 核对提示词和参考图，再调用本机 ComfyUI 生图并自动导入。').pack(anchor='w',padx=SPACING['lg'],pady=SPACING['xs'])
    types=ttk.Frame(form);types.pack(fill='x',padx=SPACING['lg'],pady=SPACING['sm']);checks={}
    for prefix,(_,label) in KINDS.items():
        default_checked=controller.category_defaults(KINDS, app.asset_kind)[prefix]
        checks[prefix]=tk.BooleanVar(value=default_checked)
        ttk.Checkbutton(types,text=label,style='TCheckbutton',variable=checks[prefix],command=lambda p=prefix:toggle_category(p)).pack(side='left',padx=(SPACING['none'],SPACING['md']))
    table_shell=DataTable(form,columns=[('name','名称',135),('references','参考图',65),
                                        ('prompt','生图提示词',450)],show='tree headings',
                          height=8,selectmode='extended',empty_text='暂无可生成资产')
    table=table_shell.tree
    for key,label,width in [('#0','',120),('name','名称',135),('references','参考图',65),('prompt','生图提示词',450)]:table.heading(key,text=label);table.column(key,width=width,minwidth=36,stretch=False)
    def fit_columns(width=None):
        from tkinter import font as tkfont
        body_font=tkfont.Font(root=win,font=ttk.Style(win).lookup('Treeview','font') or 'TkDefaultFont')
        heading_font=tkfont.Font(root=win,font=ttk.Style(win).lookup('Treeview.Heading','font') or 'TkHeadingFont')
        headings={'name':'名称','references':'参考图'}
        widths={}
        for key in ('name','references'):
            widest=max([heading_font.measure(headings[key]),
                        *(body_font.measure(str(table.set(item,key))) for item in table.get_children())])
            widths[key]=min({'name':220,'references':105}[key],max({'name':70,'references':65}[key],widest+20))
        available=max(1,(width or table.winfo_width())-4)
        for key,size in widths.items():table.column(key,width=size)
        table.column('prompt',width=max(160,available-sum(widths.values())))
    table.bind('<Configure>',lambda event:fit_columns(event.width),add='+')
    table.column('#0',anchor='w')
    table_shell.pack(fill='x',padx=SPACING['lg'])
    status=tk.StringVar();ProgressLabel(form,textvariable=status,wraplength=760,justify='left').pack(anchor='w',padx=SPACING['lg'],pady=SPACING['sm'])
    def toggle_category(prefix):
        if checks[prefix].get():
            controller.toggle_category(prefix, True)
        refresh()
    def enabled(): return {kind for kind, value in checks.items() if value.get()}
    def available(): return controller.available(enabled())
    def pending(): return controller.pending(enabled())
    def refresh():
        selected=table.selection();focused=table.focus();position=table.yview()[0]
        table.delete(*table.get_children())
        for aid,a in available():table.insert('','end',iid=aid,text=aid,image=app.win._tick_images[0 if aid in controller.excluded else 1],values=(a.get('name',aid),str(len(a.get('reference_images',[])))+' 张',a.get('image_prompt') or a.get('prompt') or a.get('description','')))
        table_shell.refresh_empty_state()
        ids=[aid for aid,_ in available()]
        table.heading('#0',image=app.win._tick_images[1 if ids and all(aid not in controller.excluded for aid in ids) else 0])
        table.selection_set([aid for aid in selected if table.exists(aid)])
        if table.exists(focused):table.focus(focused)
        table.yview_moveto(position)
        table.configure(height=max(2,min(8,len(available()))))
        fit_columns()
        from asset_prompt_rules import issues
        missing=sum(bool(issues(aid,asset)) for aid,asset in pending())
        status.set(f'已勾选 {len(pending())} / {len(available())} 项；其中 {missing} 项需补齐名称或提示词。取消勾选的不生成，已导入自动跳过。')
    def toggle(aids):
        controller.excluded=toggle_excluded(controller.excluded,aids)
        refresh()
    def click_check(event):
        aid=table.identify_row(event.y)
        if aid and table.identify_region(event.x,event.y) in ('tree','cell'):
            table.selection_set(aid);table.focus(aid);toggle([aid]);return 'break'
    def space_check(event):
        toggle(table.selection());return 'break'
    def select_checks(value):
        ids={aid for aid,_ in available()}
        controller.excluded=set_selection(controller.excluded,ids,value)
        refresh()
    def toggle_all():
        ids={aid for aid,_ in available()}
        if not ids:return
        select_checks(not all_selected(ids,controller.excluded))
    table.heading('#0',command=toggle_all)
    table.bind('<Button-1>',click_check);table.bind('<space>',space_check)
    if engine=='workflow':
        def reload_rows():
            controller.reload_rows();refresh()
        def context_matches():
            return app.root==project and app.current_frame_json()==source and app.asset_scope()==scope and app.asset_sources()==sources
        _attach_native_controls(app,win,form,footer,project,base,pending,status,reload_rows,context_matches)
        refresh();view.bind_wheel();win.update_idletasks()
        win.geometry(f'+{app.win.winfo_rootx()+40}+{app.win.winfo_rooty()+40}');win.deiconify()
        return
    from cloud_assets import LOCAL,MODELS,settings as cloud_settings
    chooser=FlowBar(form);chooser.pack(fill='x',padx=SPACING['lg'],pady=SPACING['sm'])
    # 第 46 期第 8 条：这一格原来是一个「生图模型」下拉框（本地 ComfyUI／云端生图都摆在这儿，
    # 与「阶段配置 → 模型」重复）。现在只剩一行只读的当前模型，右边留一颗「阶段配置」就地打开
    # 唯一能挑模型的那一处。
    workflow_default=str(Path(__file__).with_name('flux2_klein_asset_text_api.json'))
    defaults, aspect_default, quality_default, backend_default=controller.form_defaults(workflow_default,current_model(project))
    backend=tk.StringVar(value=backend_default)
    aspect=tk.StringVar(value=aspect_default)
    quality=tk.StringVar(value=quality_default)
    ttk.Label(chooser,text='生图模型').pack(side='left')
    ttk.Label(chooser,textvariable=backend).pack(side='left',padx=SPACING['xs'])
    SecondaryButton(chooser,text='阶段配置',
                    command=lambda:app.safe(lambda:ui_plugin_registry.module('skill_panel').show(app,'assets'))).pack(side='left',padx=SPACING['xs'])
    ttk.Label(chooser,text='云模型画幅').pack(side='left',padx=(SPACING['sm'],SPACING['none']))
    SelectBox(chooser,textvariable=aspect,values=['1:1','9:16','16:9']).pack(side='left',padx=SPACING['xs'])
    SecondaryButton(chooser,text='云模型设置',command=lambda:app.safe(lambda:cloud_settings(win))).pack(side='left',padx=SPACING['xs'])
    def open_midjourney():
        open_target('https://www.midjourney.com/create')
        status.set('Midjourney 为手动制作入口；生成后使用“导入资产图片”导入，当前不提供官方公开 API。')
    SecondaryButton(chooser,text='Midjourney（手动）',command=open_midjourney).pack(side='left',padx=SPACING['xs'])
    config=ttk.LabelFrame(form,text='ComfyUI 连接与本地工作流',padding=SPACING['sm']);config.pack(fill='x',padx=SPACING['lg'],pady=SPACING['sm']);config.columnconfigure(1,weight=1)
    values={key:tk.StringVar(value=value) for key,value in defaults.items()}
    def work_options():
        return controller.options({key:value.get() for key,value in values.items()}, current_model(project), aspect.get(), quality.get())
    for i,(key,label) in enumerate([('url','本机地址'),('model','基础模型'),('workflow','API 工作流（可选）'),('node','提示词节点编号'),('field','提示词字段')]):
        ttk.Label(config,text=label).grid(row=i,column=0,sticky='w',padx=SPACING['xs'],pady=SPACING['xs'])
        field=SelectBox(config,textvariable=values[key], state='normal') if key=='model' else LineInput(config,textvariable=values[key])
        field.grid(row=i,column=1,sticky='ew',padx=SPACING['xs'])
        if key=='model':modelbox=field
    def model_key():
        from api_models import identity
        return identity(values['url'].get(),values['model'].get())
    def delete_model():
        if app.worker:raise ValueError('请等待本批生成完成后删除模型配置')
        if app.root!=project:raise ValueError('项目已切换，请重新打开资产设置')
        model=work_options()['model']
        if not model:raise ValueError('请先选择要删除的模型')
        if not ask_confirmation(win, '删除模型', f'删除模型配置 {model}？\n只从助手列表移除，ComfyUI 里的模型文件不动。', dangerous=True):return
        result=remove_model(project, values['url'].get(), model, model_key())
        if not result.ok:
            status.set(result.reason)
            return
        values['model'].set('');modelbox.configure(values=[m for m in modelbox['values'] if m!=model])
        status.set('模型配置已删除并保存，ComfyUI 模型文件保留。')
    SecondaryButton(config,text='删除模型',command=lambda:app.safe(delete_model)).grid(row=3,column=2,padx=SPACING['xs'])
    def detect():
        url=values['url'].get();client=Comfy(url)
        if not app.launch_comfy():return
        def load():
            from api_models import identity
            current=_prefs(prefsfile)
            deleted=current.get('asset_batch',{}).get('deleted_models',[])
            return controller.detect(client.models, url, deleted, identity)
        def done(models):
            modelbox.configure(values=models)
            if len(models)==1:values['model'].set(models[0])
            elif not models and values['workflow'].get().strip():values['model'].set(WORKFLOW_MODEL)
            status.set(f'检测到 {len(models)} 个基础模型，请选择。' if models else 'ComfyUI 已连接；未发现传统基础模型，可使用已选择的 API 工作流。')
        app.async_(load,done)
    SecondaryButton(config,text='启动并检测',command=lambda:app.safe(detect)).grid(row=1,column=2,padx=SPACING['xs'])
    SecondaryButton(config,text='选择文件',command=lambda:values['workflow'].set(FileDialog(win).open_file(filetypes=[('ComfyUI API 工作流','*.json')]) or values['workflow'].get())).grid(row=2,column=2,padx=SPACING['xs'])
    def save_api():
        options=work_options();Comfy(options['url'])
        if backend.get()==LOCAL and options['workflow'] and not Path(options['workflow']).is_file():raise ValueError('API 工作流文件不存在')
        result=save_settings(project, options, {k:v.get() for k,v in checks.items()}, model_key())
        if not result.ok:
            status.set(result.reason)
            return
        status.set('ComfyUI API 设置已保存，下次打开自动回填。')
    SecondaryButton(config,text='保存设置',command=lambda:app.safe(save_api)).grid(row=0,column=2,padx=SPACING['xs'])
    def show_backend():
        if skill_mode and not qwen_images and backend.get()==LOCAL:config.pack_forget()
        elif not config.winfo_manager():config.pack(fill='x',padx=SPACING['lg'],pady=SPACING['sm'],after=chooser)
    show_backend()
    DescriptionBlock(form,text='参考图可选：有图时按长相、服饰、画风等用途结合提示词生成；无图时只使用提示词。',wraplength=800).pack(anchor='w',padx=SPACING['lg'],pady=SPACING['xs'])
    events=queue.Queue();stop=threading.Event()
    def poll():
        if not win.winfo_exists():return
        try:
            while True:status.set(events.get_nowait())
        except queue.Empty:pass
    tk_timers.repeat(win,250,poll)
    def start():
        from asset_prompt_rules import issues
        from stage_execution_service import require_formal_asset_generation
        options=work_options()
        require_formal_asset_generation(project, online_model=backend.get() in MODELS)
        decision=controller.start_decision(
            app.root==project and app.current_frame_json()==source and app.asset_scope()==scope and app.asset_sources()==sources,
            enabled(), issues, options, backend.get(), None if skill_mode else LOCAL, uncertain_assets(project))
        items=decision.items;refresh()
        def done(result):
            try:
                while True:events.get_nowait()
            except queue.Empty:pass
            controller.reload_rows();refresh();status.set(result);app.status.set(result)
            if app.root==project:app.show(2)
            # 第 47 期第 5 条：完成消息由宿主上报三虎；批量页不反向依赖宠物 UI。
            reporter=getattr(app, 'pet_report', None)
            if callable(reporter):
                reporter('assets', result)
        if skill_mode:
            if qwen_images or backend.get() in MODELS:
                Comfy(options['url'])
                if backend.get()==LOCAL and any(not a.get('reference_images') for _,a in items) and not options['workflow'] and not options['model']:raise ValueError('请先选择图像模型或 ComfyUI API 工作流')
                if backend.get() in MODELS:
                    from cloud_assets import get_key
                    if not get_key():raise ValueError('请先在“云模型设置”保存 Comfy API Key，再启动 Qwen 批量生图')
                result=save_settings(project, options)
                if not result.ok:
                    status.set(result.reason)
                    return
                if _launch_skill_batch(app,project,base,items):win.destroy()
                else:status.set(app.status.get())
                return
            if _launch_skill_batch(app,project,base,items):win.destroy()
            else:status.set(app.status.get())
            return
        blocked=decision.uncertain_ids
        if blocked:
            if ask_confirmation(win, '提交结果无法确认',
                    '以下资产上次提交时连接中断，无法确认是否已经生成：\n'+'、'.join(blocked)+
                    '\n\n请先在 ComfyUI 或云端控制台核对它们的生成情况。\n'
                    '点“确认”：确认没有生成成功，本次重新生成；使用云端模型时会再次计费。\n'
                    '点“取消”：本次先跳过这些资产，其余资产照常生成。',dangerous=True):
                status.set('已按核实结果放开重新生成：'+'、'.join(release_uncertain(project,blocked)))
            else:
                skip=set(blocked);items=[(aid,asset) for aid,asset in items if aid not in skip]
                status.set('已跳过提交结果无法确认的资产：'+'、'.join(blocked))
        Comfy(options['url'])
        for aid,a in items:asset_prompt(a,KINDS[aid.split('_')[0]][0])
        result=save_settings(project, options, {k:v.get() for k,v in checks.items()}, model_key())
        if not result.ok:
            status.set(result.reason)
            return
        if not app.launch_comfy(silent=True):return                 # 第 62 期任务 8：静默拉起，不弹选择框
        stop.clear()
        app.async_(lambda:run_batch(project,base,items,options,events,stop),done)
    buttons=FlowBar(footer);buttons.pack(fill='x',padx=SPACING['lg'],pady=SPACING['sm'])
    PrimaryButton(buttons,text='开始资产图片制作' if skill_mode else '开始批量生成并导入',command=lambda:app.safe(start)).pack(side='left')
    if not skill_mode:SecondaryButton(buttons,text='停止后续资产',command=lambda:stop.set()).pack(side='left',padx=SPACING['xs'])
    def records():
        from platform_tools import open_path
        folder=project/'workflows';folder.mkdir(exist_ok=True);open_path(folder)
    SecondaryButton(buttons,text='生成记录',command=records).pack(side='left',padx=SPACING['xs'])
    refresh();view.bind_wheel();win.update_idletasks();win.geometry(f'+{app.win.winfo_rootx()+40}+{app.win.winfo_rooty()+40}');win.deiconify();poll()
