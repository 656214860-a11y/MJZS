"""Sequential local asset generation with ID-based registration and resumable jobs."""
import json, os, re, uuid, threading, queue
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from agent.core import read
from infra.comfy_service import Comfy
from stage_execution_service import remove_asset_batch_model as remove_model, save_asset_batch_settings as save_settings
import infra.tk_timers as tk_timers
import infra.ui_plugin_registry as ui_plugin_registry
from infra.pet_state import PAGE_OF
import orchestrator.stage_models as stage_models
from responsive_ui import FlowBar, scroll_form
from contract.platform_tools import open_target
from ui_tokens import TEXT_ROWS, WRAPLENGTH, COLORS, SPACING
from ui.ui_dialogs import FileDialog
from ui_widgets import SelectBox, BaseDialog, Card, DataTable, DescriptionBlock, LineInput, PrimaryButton, ProgressLabel, SecondaryButton, ask_confirmation
from domain.asset_batch_service import (
    KINDS, asset_prompt as _asset_prompt, register_image as _register_image,
    image_ready as _image_ready, batch_complete as _batch_complete,
    automatic_plan as _automatic_plan, auto_settings as _auto_settings,
    current_model as _current_model, unattended_plan as _unattended_plan,
)
from orchestrator.asset_auto_batch_service import auto_batch as _auto_batch
from domain.asset_batch_state_service import ledger_path, uncertain_assets, prune_raw_outputs, ready_asset_ids
from domain.asset_batch_selection_service import all_selected, scope_label, set_selection, toggle_excluded
from orchestrator.asset_batch_controller import AssetBatchController, WORKFLOW_MODEL


def release_uncertain(project, ids):
    """兼容旧入口；L4 只经 L3 放开已核实的未知提交记录。"""
    from stage_execution_service import release_uncertain_asset_batch
    return release_uncertain_asset_batch(project, ids)


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
    from infra.project_settings import read_prefs
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
    from orchestrator.asset_batch_execution import run_batch as execute_batch
    return execute_batch(project,base,items,options,events,stop,client_factory)

def auto_settings(project):
    """无人值守批量资产复用的设置：批量窗口保存过的 asset_batch（连接、模型与各类别勾选）。"""
    return _auto_settings(project)


def current_model(project):
    """「资产图片制作」窗口当前的生图模型（第 46 期第 8 条）。

    模型只有一个入口——底部共享输入框的模型下拉框（写在项目自己的 skill_config.json 里，阶段 id＝assets），
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


def show(app, engine='comfy', selected_ids=None):
    return _AssetBatchWindow(app, engine, selected_ids).build()


class _AssetBatchWindow:
    """批量资产窗口：引擎设置表单、资产勾选列表与生产按钮。"""
    def __init__(self, app, engine='comfy', selected_ids=None):
        self.app = app
        self.engine = engine
        self.selected_ids = selected_ids

    def build(self):
        self.skill_mode=self.engine=="skill"
        self.qwen_images=self.skill_mode and _is_skill_api_engine(self.app.root)
        self.project=Path(self.app.root);self.base=self.app.asset_base();self.source=self.app.current_frame_json();self.scope=self.app.asset_scope();self.sources=self.app.asset_sources()
        self.prefsfile=self.project/'ui_settings.json';prefs=_prefs(self.prefsfile);saved=prefs.get('asset_batch',{})
        from stage_execution_service import sync_asset_plan
        self.controller=AssetBatchController(self.project,self.base,self.sources,self.scope,self.engine,self.selected_ids,saved,sync_asset_plan)
        self.base=self.app.asset_base();self.controller.base=self.base
        scope_text=scope_label(self.scope,self.sources,read(self.source).get('episode_id',''))
        self.win=BaseDialog(self.app.win,'',modal=False,chrome=False);self.win.withdraw();self.win.title(('资产图片制作' if self.skill_mode or self.engine=='workflow' else 'ComfyUI')+' · 批量资产 · '+scope_text);self.win.geometry('850x640');self.win.minsize(700,480);self.win.transient(self.app.win)
        self.win.protocol('WM_DELETE_WINDOW',self.win.destroy)
        # Keep production buttons visible while the long API form scrolls above them.
        footer=ttk.Frame(self.win);footer.pack(side='bottom',fill='x')
        viewport=ttk.Frame(self.win);viewport.pack(side='top',fill='both',expand=True)
        view=scroll_form(viewport,bg=COLORS['background_primary']);form=view.form     # 滚动表单区与首帧制作共用一份实现
        ttk.Label(form,text='选择资产类别 → 开始批量生成 → 按编号和名称自动导入',style='Tokens.Title.TLabel').pack(anchor='w',padx=SPACING['lg'],pady=SPACING['md'])
        DescriptionBlock(form,text='生成范围：'+scope_text+'；道具仅制作关键道具，普通道具随画面生成；已导入图片自动跳过。').pack(anchor='w',padx=SPACING['lg'])
        if self.qwen_images:DescriptionBlock(form,text='由 Qwen 按所选 Skill 核对提示词和参考图，再调用本机 ComfyUI 生图并自动导入。').pack(anchor='w',padx=SPACING['lg'],pady=SPACING['xs'])
        types=ttk.Frame(form);types.pack(fill='x',padx=SPACING['lg'],pady=SPACING['sm']);self.checks={}
        for prefix,(_,label) in KINDS.items():
            default_checked=self.controller.category_defaults(KINDS, self.app.asset_kind)[prefix]
            self.checks[prefix]=tk.BooleanVar(value=default_checked)
            ttk.Checkbutton(types,text=label,style='TCheckbutton',variable=self.checks[prefix],command=lambda p=prefix:self.toggle_category(p)).pack(side='left',padx=(SPACING['none'],SPACING['md']))
        self.table_shell=DataTable(form,columns=[('name','名称',135),('references','参考图',65),
                                            ('prompt','生图提示词',450)],show='tree headings',
                              height=TEXT_ROWS['lg'],selectmode='extended',empty_text='暂无可生成资产')
        self.table=self.table_shell.tree
        for key,label,width in [('#0','',120),('name','名称',135),('references','参考图',65),('prompt','生图提示词',450)]:self.table.heading(key,text=label);self.table.column(key,width=width,minwidth=36,stretch=False)
        self.table.bind('<Configure>',lambda event:self.fit_columns(event.width),add='+')
        self.table.column('#0',anchor='w')
        self.table_shell.pack(fill='x',padx=SPACING['lg'])
        self.status=tk.StringVar();ProgressLabel(form,textvariable=self.status,wraplength=WRAPLENGTH['xl'],justify='left').pack(anchor='w',padx=SPACING['lg'],pady=SPACING['sm'])
        self.table.heading('#0',command=self.toggle_all)
        self.table.bind('<Button-1>',self.click_check);self.table.bind('<space>',self.space_check)
        if self.engine=='workflow':
            def reload_rows():
                self.controller.reload_rows();self.refresh()
            def context_matches():
                return self.app.root==self.project and self.app.current_frame_json()==self.source and self.app.asset_scope()==self.scope and self.app.asset_sources()==self.sources
            _attach_native_controls(self.app,self.win,form,footer,self.project,self.base,self.pending,self.status,reload_rows,context_matches)
            self.refresh();view.bind_wheel();self.win.update_idletasks()
            self.win.geometry(f'+{self.app.win.winfo_rootx()+40}+{self.app.win.winfo_rooty()+40}');self.win.deiconify()
            return
        from infra.cloud_assets import LOCAL,MODELS
        from ui.cloud_assets_dialog import settings as cloud_settings
        self.LOCAL = LOCAL; self.MODELS = MODELS; self.cloud_settings = cloud_settings
        self.chooser=FlowBar(form);self.chooser.pack(fill='x',padx=SPACING['lg'],pady=SPACING['sm'])
        # 第 46 期第 8 条：这一格原来是一个「生图模型」下拉框（与统一模型下拉框重复）。
        # R2942：只剩一行只读的当前模型，右边一颗「模型」就地弹开共享输入框的模型下拉框。
        workflow_default=str(Path(__file__).resolve().parents[1]/'flux2_klein_asset_text_api.json')
        defaults, aspect_default, quality_default, backend_default=self.controller.form_defaults(workflow_default,current_model(self.project))
        self.backend=tk.StringVar(value=backend_default)
        self.aspect=tk.StringVar(value=aspect_default)
        self.quality=tk.StringVar(value=quality_default)
        ttk.Label(self.chooser,text='生图模型').pack(side='left')
        ttk.Label(self.chooser,textvariable=self.backend).pack(side='left',padx=SPACING['xs'])
        SecondaryButton(self.chooser,text='模型',
                        command=lambda:self.app.safe(lambda:stage_models.open_model_dropdown(self.app))).pack(side='left',padx=SPACING['xs'])
        ttk.Label(self.chooser,text='云模型画幅').pack(side='left',padx=(SPACING['sm'],SPACING['none']))
        SelectBox(self.chooser,textvariable=self.aspect,values=['1:1','9:16','16:9']).pack(side='left',padx=SPACING['xs'])
        SecondaryButton(self.chooser,text='云模型设置',command=lambda:self.app.safe(lambda:self.cloud_settings(self.win))).pack(side='left',padx=SPACING['xs'])
        SecondaryButton(self.chooser,text='Midjourney（手动）',command=self.open_midjourney).pack(side='left',padx=SPACING['xs'])
        self.config=Card(form,padding=SPACING['sm']);self.config.pack(fill='x',padx=SPACING['lg'],pady=SPACING['sm']);self.config.columnconfigure(1,weight=1)
        ttk.Label(self.config,text='ComfyUI 连接与本地工作流').grid(row=0,column=0,columnspan=2,sticky='w',pady=(SPACING['none'],SPACING['xs']))
        self.values={key:tk.StringVar(value=value) for key,value in defaults.items()}
        for i,(key,label) in enumerate([('url','本机地址'),('model','基础模型'),('workflow','API 工作流（可选）'),('node','提示词节点编号'),('field','提示词字段')], start=1):
            ttk.Label(self.config,text=label).grid(row=i,column=0,sticky='w',padx=SPACING['xs'],pady=SPACING['xs'])
            field=SelectBox(self.config,textvariable=self.values[key], state='normal') if key=='model' else LineInput(self.config,textvariable=self.values[key])
            field.grid(row=i,column=1,sticky='ew',padx=SPACING['xs'])
            if key=='model':self.modelbox=field
        SecondaryButton(self.config,text='删除模型',command=lambda:self.app.safe(self.delete_model)).grid(row=3,column=2,padx=SPACING['xs'])
        SecondaryButton(self.config,text='启动并检测',command=lambda:self.app.safe(self.detect)).grid(row=1,column=2,padx=SPACING['xs'])
        SecondaryButton(self.config,text='选择文件',command=lambda:self.values['workflow'].set(FileDialog(self.win).open_file(filetypes=[('ComfyUI API 工作流','*.json')]) or self.values['workflow'].get())).grid(row=2,column=2,padx=SPACING['xs'])
        SecondaryButton(self.config,text='保存设置',command=lambda:self.app.safe(self.save_api)).grid(row=0,column=2,padx=SPACING['xs'])
        self.show_backend()
        DescriptionBlock(form,text='参考图可选：有图时按长相、服饰、画风等用途结合提示词生成；无图时只使用提示词。',wraplength=WRAPLENGTH['2xl']).pack(anchor='w',padx=SPACING['lg'],pady=SPACING['xs'])
        self.events=queue.Queue();self.stop=threading.Event()
        tk_timers.repeat(self.win,250,self.poll)
        buttons=FlowBar(footer);buttons.pack(fill='x',padx=SPACING['lg'],pady=SPACING['sm'])
        PrimaryButton(buttons,text='开始资产图片制作' if self.skill_mode else '开始批量生成并导入',command=lambda:self.app.safe(self.start)).pack(side='left')
        if not self.skill_mode:SecondaryButton(buttons,text='停止后续资产',command=lambda:self.stop.set()).pack(side='left',padx=SPACING['xs'])
        SecondaryButton(buttons,text='生成记录',command=self.records).pack(side='left',padx=SPACING['xs'])
        self.refresh();view.bind_wheel();self.win.update_idletasks();self.win.geometry(f'+{self.app.win.winfo_rootx()+40}+{self.app.win.winfo_rooty()+40}');self.win.deiconify();self.poll()

    def fit_columns(self, width=None):
        from tkinter import font as tkfont
        body_font=tkfont.Font(root=self.win,font=ttk.Style(self.win).lookup('Treeview','font') or 'TkDefaultFont')
        heading_font=tkfont.Font(root=self.win,font=ttk.Style(self.win).lookup('Treeview.Heading','font') or 'TkHeadingFont')
        headings={'name':'名称','references':'参考图'}
        widths={}
        for key in ('name','references'):
            widest=max([heading_font.measure(headings[key]),
                        *(body_font.measure(str(self.table.set(item,key))) for item in self.table.get_children())])
            widths[key]=min({'name':220,'references':105}[key],max({'name':70,'references':65}[key],widest+20))
        available=max(1,(width or self.table.winfo_width())-4)
        for key,size in widths.items():self.table.column(key,width=size)
        self.table.column('prompt',width=max(160,available-sum(widths.values())))

    def toggle_category(self, prefix):
        if self.checks[prefix].get():
            self.controller.toggle_category(prefix, True)
        self.refresh()

    def enabled(self): return {kind for kind, value in self.checks.items() if value.get()}

    def available(self): return self.controller.available(self.enabled())

    def pending(self): return self.controller.pending(self.enabled())

    def refresh(self):
        selected=self.table.selection();focused=self.table.focus();position=self.table.yview()[0]
        self.table.delete(*self.table.get_children())
        for aid,a in self.available():self.table.insert('','end',iid=aid,text=aid,image=self.app.win._tick_images[0 if aid in self.controller.excluded else 1],values=(a.get('name',aid),str(len(a.get('reference_images',[])))+' 张',a.get('image_prompt') or a.get('prompt') or a.get('description','')))
        self.table_shell.refresh_empty_state()
        ids=[aid for aid,_ in self.available()]
        self.table.heading('#0',image=self.app.win._tick_images[1 if ids and all(aid not in self.controller.excluded for aid in ids) else 0])
        self.table.selection_set([aid for aid in selected if self.table.exists(aid)])
        if self.table.exists(focused):self.table.focus(focused)
        self.table.yview_moveto(position)
        self.table.configure(height=max(2,min(8,len(self.available()))))
        self.fit_columns()
        from infra.asset_prompt_rules import issues
        missing=sum(bool(issues(aid,asset)) for aid,asset in self.pending())
        self.status.set(f'已勾选 {len(self.pending())} / {len(self.available())} 项；其中 {missing} 项需补齐名称或提示词。取消勾选的不生成，已导入自动跳过。')

    def toggle(self, aids):
        self.controller.excluded=toggle_excluded(self.controller.excluded,aids)
        self.refresh()

    def click_check(self, event):
        aid=self.table.identify_row(event.y)
        if aid and self.table.identify_region(event.x,event.y) in ('tree','cell'):
            self.table.selection_set(aid);self.table.focus(aid);self.toggle([aid]);return 'break'

    def space_check(self, event):
        self.toggle(self.table.selection());return 'break'

    def select_checks(self, value):
        ids={aid for aid,_ in self.available()}
        self.controller.excluded=set_selection(self.controller.excluded,ids,value)
        self.refresh()

    def toggle_all(self):
        ids={aid for aid,_ in self.available()}
        if not ids:return
        self.select_checks(not all_selected(ids,self.controller.excluded))

    def open_midjourney(self):
        open_target('https://www.midjourney.com/create')
        self.status.set('Midjourney 为手动制作入口；生成后使用“导入资产图片”导入，当前不提供官方公开 API。')

    def work_options(self):
        return self.controller.options({key:value.get() for key,value in self.values.items()}, current_model(self.project), self.aspect.get(), self.quality.get())

    def model_key(self):
        from contract.api_models import identity
        return identity(self.values['url'].get(),self.values['model'].get())

    def delete_model(self):
        if self.app.worker:raise ValueError('请等待本批生成完成后删除模型配置')
        if self.app.root!=self.project:raise ValueError('项目已切换，请重新打开资产设置')
        model=self.work_options()['model']
        if not model:raise ValueError('请先选择要删除的模型')
        if not ask_confirmation(self.win, '删除模型', f'删除模型配置 {model}？\n只从助手列表移除，ComfyUI 里的模型文件不动。', dangerous=True):return
        result=remove_model(self.project, self.values['url'].get(), model, self.model_key())
        if not result.ok:
            self.status.set(result.reason)
            return
        self.values['model'].set('');self.modelbox.configure(values=[m for m in self.modelbox['values'] if m!=model])
        self.status.set('模型配置已删除并保存，ComfyUI 模型文件保留。')

    def detect(self):
        url=self.values['url'].get();client=Comfy(url)
        if not self.app.launch_comfy():return
        def load():
            from contract.api_models import identity
            current=_prefs(self.prefsfile)
            deleted=current.get('asset_batch',{}).get('deleted_models',[])
            return self.controller.detect(client.models, url, deleted, identity)
        def done(models):
            self.modelbox.configure(values=models)
            if len(models)==1:self.values['model'].set(models[0])
            elif not models and self.values['workflow'].get().strip():self.values['model'].set(WORKFLOW_MODEL)
            self.status.set(f'检测到 {len(models)} 个基础模型，请选择。' if models else 'ComfyUI 已连接；未发现传统基础模型，可使用已选择的 API 工作流。')
        self.app.async_(load,done)

    def save_api(self):
        options=self.work_options();Comfy(options['url'])
        if self.backend.get()==self.LOCAL and options['workflow'] and not Path(options['workflow']).is_file():raise ValueError('API 工作流文件不存在')
        result=save_settings(self.project, options, {k:v.get() for k,v in self.checks.items()}, self.model_key())
        if not result.ok:
            self.status.set(result.reason)
            return
        self.status.set('ComfyUI API 设置已保存，下次打开自动回填。')

    def show_backend(self):
        if self.skill_mode and not self.qwen_images and self.backend.get()==self.LOCAL:self.config.pack_forget()
        elif not self.config.winfo_manager():self.config.pack(fill='x',padx=SPACING['lg'],pady=SPACING['sm'],after=self.chooser)

    def poll(self):
        if not self.win.winfo_exists():return
        try:
            while True:self.status.set(self.events.get_nowait())
        except queue.Empty:pass

    def start(self):
        from infra.asset_prompt_rules import issues
        from stage_execution_service import require_formal_asset_generation
        options=self.work_options()
        require_formal_asset_generation(self.project, online_model=self.backend.get() in self.MODELS)
        decision=self.controller.start_decision(
            self.app.root==self.project and self.app.current_frame_json()==self.source and self.app.asset_scope()==self.scope and self.app.asset_sources()==self.sources,
            self.enabled(), issues, options, self.backend.get(), None if self.skill_mode else self.LOCAL, uncertain_assets(self.project))
        items=decision.items;self.refresh()
        def done(result):
            try:
                while True:self.events.get_nowait()
            except queue.Empty:pass
            self.controller.reload_rows();self.refresh();self.status.set(result);self.app.status.set(result)
            if self.app.root==self.project and getattr(self.app,'page_index',None)==PAGE_OF['assets']:self.app.show(PAGE_OF['assets'])    # REQ-S05-24：人不在资产管理页就不翻页，状态栏照常更新
            # 第 47 期第 5 条：完成消息由宿主上报三虎；批量页不反向依赖宠物 UI。
            reporter=getattr(self.app, 'pet_report', None)
            if callable(reporter):
                reporter('assets', result)
        if self.skill_mode:
            if self.qwen_images or self.backend.get() in self.MODELS:
                Comfy(options['url'])
                if self.backend.get()==self.LOCAL and any(not a.get('reference_images') for _,a in items) and not options['workflow'] and not options['model']:raise ValueError('请先选择图像模型或 ComfyUI API 工作流')
                if self.backend.get() in self.MODELS:
                    from infra.cloud_assets import get_key
                    if not get_key():raise ValueError('请先在“云模型设置”保存 Comfy API Key，再启动 Qwen 批量生图')
                result=save_settings(self.project, options)
                if not result.ok:
                    self.status.set(result.reason)
                    return
                if _launch_skill_batch(self.app,self.project,self.base,items):self.win.destroy()
                else:self.status.set(self.app.status.get())
                return
            if _launch_skill_batch(self.app,self.project,self.base,items):self.win.destroy()
            else:self.status.set(self.app.status.get())
            return
        blocked=decision.uncertain_ids
        if blocked:
            if ask_confirmation(self.win, '提交结果无法确认',
                    '以下资产上次提交时连接中断，无法确认是否已经生成：\n'+'、'.join(blocked)+
                    '\n\n请先在 ComfyUI 或云端控制台核对它们的生成情况。\n'
                    '点“确认”：确认没有生成成功，本次重新生成；使用云端模型时会再次计费。\n'
                    '点“取消”：本次先跳过这些资产，其余资产照常生成。',dangerous=True):
                self.status.set('已按核实结果放开重新生成：'+'、'.join(release_uncertain(self.project,blocked)))
            else:
                skip=set(blocked);items=[(aid,asset) for aid,asset in items if aid not in skip]
                self.status.set('已跳过提交结果无法确认的资产：'+'、'.join(blocked))
        Comfy(options['url'])
        for aid,a in items:asset_prompt(a,KINDS[aid.split('_')[0]][0])
        result=save_settings(self.project, options, {k:v.get() for k,v in self.checks.items()}, self.model_key())
        if not result.ok:
            self.status.set(result.reason)
            return
        if not self.app.launch_comfy(silent=True):return                 # 第 62 期任务 8：静默拉起，不弹选择框
        self.stop.clear()
        self.app.async_(lambda:run_batch(self.project,self.base,items,options,self.events,self.stop),done)

    def records(self):
        from contract.platform_tools import open_path
        folder=self.project/'workflows';folder.mkdir(exist_ok=True);open_path(folder)
