"""Configure isolated cloud video task sessions without submitting on open."""
import time
import tkinter as tk
from tkinter import ttk,messagebox
import webbrowser
from pathlib import Path
from ui_tokens import WRAPLENGTH, SPACING
from ui_widgets import SelectBox, Card, BaseDialog, LineInput, PrimaryButton, ProgressLabel, SecondaryButton, ask_confirmation, notify
from agent.core import read
from contract.api_models import identity,cloud_removed

PROVIDERS={
    '阿里云百炼 · 万相':('wan','https://dashscope.aliyuncs.com/api/v1','wan2.6-i2v-flash','DASHSCOPE_API_KEY'),
    '火山引擎 · Seedance':('volcengine','https://ark.cn-beijing.volces.com/api/v3','doubao-seedance-1-5-pro-251215','ARK_API_KEY'),
}
PROVIDERS.update({'自定义 · 万相兼容':('wan','','','DASHSCOPE_API_KEY'),
                  '自定义 · Seedance兼容':('volcengine','','','ARK_API_KEY')})
KEY_REVEAL_MS=10_000

def provider_label(config):
    from cloud_video_service import provider_label as _provider_label
    return _provider_label(config,PROVIDERS)

def session_folder(project, kind, base, model, source):
    from stage_execution_service import cloud_video_session_folder
    return cloud_video_session_folder(project,kind,base,model,source)

def saved_provider_key(project,kind,remembered=None,base_url=None):
    from stage_execution_service import cloud_video_saved_provider_key
    return cloud_video_saved_provider_key(project,kind,PROVIDERS,remembered,base_url,__file__)

def settings_window(desktop):
    return _CloudSettingsWindow(desktop).build()


class _CloudSettingsWindow:
    """云端视频调用设置窗口；闭包状态挂在实例上。"""
    def __init__(self, desktop):
        self.desktop = desktop

    def build(self):
        previous=getattr(self.desktop,'cloud_settings_window',None)
        if previous is not None and previous.winfo_exists():previous.lift();return
        self.origin_video=self.desktop.video
        self.project=Path(self.desktop.root);self.source=self.desktop.current_frame_json();self.episode=self.source.parent
        self.prefs_path=self.project/'ui_settings.json';prefs=read(self.prefs_path) if self.prefs_path.is_file() else {}
        self.remembered={}
        if prefs.get('cloud_video_workspace'):
            folder=(self.project/prefs['cloud_video_workspace']).resolve()
            if folder.is_relative_to((self.project/'cloud_video').resolve()) and (folder/'config.json').is_file():
                self.remembered=read(folder/'config.json')
                if not isinstance(self.remembered,dict):self.remembered={}
        self.win=BaseDialog(self.desktop.win,'调用设置 · 云端视频 API',geometry='820x620',modal=False,chrome=False);self.win.attributes('-alpha',0)
        self.desktop.cloud_settings_window=self.win
        body=Card(self.win);body.pack(fill='both',expand=True,padx=SPACING['lg'],pady=SPACING['lg']);body.columnconfigure(1,weight=1)
        # 第 36 期第 2 条：下半截原来是一大段密排说明 ＋ 一列铺满整行的链接按钮，读起来费劲、
        # 也看不出哪个是主操作。现在窗口可放大（说明跟着换行），下面按「主操作 → 说明分条 →
        # 服务商控制台」三段排。
        self.win.resizable(True,True);self.win.minsize(700,560)
        if self.remembered and cloud_removed(self.project,self.remembered):self.remembered={**self.remembered,'model':''}
        selected_provider=provider_label(self.remembered)
        self.provider=tk.StringVar(value=selected_provider)
        ttk.Label(body,text='接口协议 / 服务商').grid(row=0,column=0,padx=SPACING['md'],pady=SPACING['md'],sticky='w')
        choice=SelectBox(body,textvariable=self.provider,values=list(PROVIDERS));choice.grid(row=0,column=1,sticky='ew',padx=SPACING['md'])
        self.entries={}
        for row,(key,label) in enumerate([('base','API根地址'),('model','模型ID'),('key','API Key（留空保留同地址密钥）'),('budget','本地累计调用上限（秒）')],1):
            ttk.Label(body,text=label).grid(row=row,column=0,padx=SPACING['md'],pady=SPACING['md'],sticky='w')
            field=SelectBox(body, state='normal') if key=='model' else LineInput(body)
            if key=='key':field.configure(show='•')
            field.grid(row=row,column=1,padx=SPACING['md'],sticky='ew');self.entries[key]=field
        self.entries['budget'].insert(0,'60')
        self.drafts={};self.active_choice=[None];self.initial_records={};self.reveal_timer=[None];self.revealed=[False]
        self.entries['key'].bind('<KeyPress>',lambda _event: self.revealed.__setitem__(0,False))
        self.win.bind('<Destroy>',self.on_window_destroy,add='+')
        for saved_path in sorted((self.project/'cloud_video').glob('*/config.json'),key=lambda p:p.stat().st_mtime):
            candidate=read(saved_path)
            if not isinstance(candidate,dict):continue
            if not cloud_removed(self.project,candidate):self.initial_records[provider_label(candidate)]=candidate
        if self.remembered:self.initial_records[selected_provider]=self.remembered
        SecondaryButton(body,text='删除模型',command=self.delete_model).grid(row=2,column=2,padx=(SPACING['none'],SPACING['md']))
        self.entries['base'].bind('<FocusOut>',self.refresh_models)
        choice.bind('<<ComboboxSelected>>',self.select);self.select()
        self.enabled=tk.BooleanVar(value=self.remembered.get('live_enabled',True))
        ttk.Checkbutton(body,text='允许联网调用（不会自动提交）',variable=self.enabled).grid(row=5,column=0,columnspan=2,padx=SPACING['md'],pady=(SPACING['md'],SPACING['xs']),sticky='w')
        self.probe_status=tk.StringVar(value='')
        # ① 主操作：保存设置摆在最前面并加粗（原来三样挤在一行、也没个主次）。
        row7=ttk.Frame(body);row7.grid(row=6,column=0,columnspan=2,sticky='ew',padx=SPACING['md'],pady=(SPACING['sm'],SPACING['md']))
        PrimaryButton(row7,text='保存设置',command=self.open_session).pack(side='left')
        SecondaryButton(row7,text='测试连接',command=self.probe_endpoint_now).pack(side='left',padx=SPACING['sm'])
        SecondaryButton(row7,text='显示已保存密钥（10 秒）',command=self.reveal_key).pack(side='left',padx=SPACING['sm'])
        ProgressLabel(row7,textvariable=self.probe_status).pack(side='left',padx=SPACING['sm'])
        # ② 说明分条：一条一行，跟着窗口宽度换行——原来是一整段四行密排，读起来串行。
        notes=ttk.LabelFrame(body,text='说明与限制',padding=(SPACING['md'],SPACING['sm']));notes.grid(row=7,column=0,columnspan=2,sticky='ew',padx=SPACING['md'])
        notes.columnconfigure(0,weight=1)
        for index,line in enumerate((
            '自定义地址需兼容所选万相或 Seedance API 协议；模型 ID 可手动填写，点「保存设置」后回填。',
            '全部资产上传：万相 2.7-r2v 支持首帧＋最多 5 张资产；Seedance 2.0 支持首帧构图参考＋最多 8 张资产（不严格锁定首帧）。',
            '需先在服务商开通对应模型；不会自动切换模型。1.0 无声音，1.5／万相 2.6 图生视频不支持此多资产流程。',
            '本地秒数预算不代表免费额度，调用前请核对费用。')):
            ttk.Label(notes,text='· '+line,wraplength=WRAPLENGTH['xl'],justify='left').grid(row=index,column=0,sticky='w')
        # ③ 服务商控制台：三个小按钮排一行（原来是一列铺满整行的按钮，看着像三件正经操作）。
        links=ttk.Frame(body);links.grid(row=8,column=0,columnspan=2,sticky='w',padx=SPACING['md'],pady=(SPACING['sm'],SPACING['md']))
        ttk.Label(links,text='服务商控制台',style='Muted.TLabel').pack(side='left',padx=(SPACING['none'],SPACING['sm']))
        for label,url in (
            ('阿里云：免费额度与用完即停','https://help.aliyun.com/zh/model-studio/new-free-quota'),
            ('火山引擎：模型控制台','https://console.volcengine.com/ark'),
            ('腾讯混元：免费额度说明（尚未接入）','https://cloud.tencent.com/document/product/1616/82562')):
            SecondaryButton(links,text=label,
                            command=lambda u=url:webbrowser.open(u)).pack(side='left',padx=(SPACING['none'],SPACING['sm']))

    def conceal_key(self):
        """结束临时查看时立即清空控件，避免已保存凭据停留在窗口内存/屏幕上。"""
        if self.reveal_timer[0] is not None:
            try:self.win.after_cancel(self.reveal_timer[0])
            except tk.TclError:pass
            self.reveal_timer[0]=None
        self.entries['key'].configure(show='•');self.entries['key'].delete(0,'end');self.revealed[0]=False

    def reveal_key(self):
        kind,base,_,_=PROVIDERS[self.provider.get()]
        key=saved_provider_key(self.project,kind,self.initial_records.get(self.provider.get(),{}),self.entries['base'].get().strip() or base)
        if not key:
            notify(self.win, '当前接口没有已保存的 API Key。', title='云端设置', status=self.desktop.status);return
        self.entries['key'].delete(0,'end');self.entries['key'].insert(0,key);self.entries['key'].configure(show='')
        self.revealed[0]=True;self.reveal_timer[0]=self.win.after(KEY_REVEAL_MS,self.conceal_key)

    def on_window_destroy(self, event):
        if event.widget is self.win and self.reveal_timer[0] is not None:
            try:self.win.after_cancel(self.reveal_timer[0])
            except tk.TclError:pass
            self.reveal_timer[0]=None

    def select(self, event=None):
        if self.active_choice[0]:
            self.drafts[self.active_choice[0]]={k:e.get().strip() for k,e in self.entries.items()}
            if self.revealed[0]:self.drafts[self.active_choice[0]]['key']=''
        self.conceal_key()
        label=self.provider.get();kind,base,model,_=PROVIDERS[label]
        record=self.initial_records.get(label,{})
        values=self.drafts.get(label,{'base':record.get('base_url',base),'model':record.get('model',model),
            'budget':str(record.get('budget_seconds',60)),'key':''})
        for key,value in values.items():self.entries[key].delete(0,'end');self.entries[key].insert(0,value)
        self.active_choice[0]=label
        self.refresh_models()

    def refresh_models(self, event=None):
        kind,_,_,_=PROVIDERS[self.provider.get()];base=self.entries['base'].get().strip().rstrip('/')
        pref=read(self.prefs_path) if self.prefs_path.is_file() else {};deleted=set(pref.get('cloud_deleted_models',[]))
        official=any(p==kind and u==base for p,u,_,_ in PROVIDERS.values() if u)
        values=({'wan':['wan2.7-r2v','wan2.7-r2v-2026-06-12','wan2.6-i2v-flash'],
                 'volcengine':['doubao-seedance-2-5-260628','doubao-seedance-2-0-260128','doubao-seedance-1-5-pro-251215']}[kind] if official else [])
        for saved_path in sorted((self.project/'cloud_video').glob('*/config.json')):
            cfg=read(saved_path)
            if not isinstance(cfg,dict):continue
            if cfg.get('cloud_provider')==kind and cfg.get('base_url','').rstrip('/')==base:values.append(cfg.get('model',''))
        self.entries['model'].configure(values=[m for m in dict.fromkeys(values) if m and identity(base,m,kind) not in deleted])
        if event is None and identity(base,self.entries['model'].get(),kind) in deleted:self.entries['model'].delete(0,'end')

    def delete_model(self):
        try:
            if self.desktop.root!=self.project:raise ValueError('项目已切换，请重新打开 API 设置')
            if self.desktop.worker or (self.desktop.video and self.desktop.video.busy):raise ValueError('请等待当前请求结束后删除模型')
            kind=PROVIDERS[self.provider.get()][0];base=self.entries['base'].get().strip().rstrip('/');model=self.entries['model'].get().strip()
            if not base or not model:raise ValueError('请先选择要删除的模型')
            if not ask_confirmation(self.win, '删除模型', f'删除模型 {model}？\n接口：{base}\n仅移除可选模型，已有视频和正在处理的任务保留。', dangerous=True):return
            key=identity(base,model,kind);updated=read(self.prefs_path) if self.prefs_path.is_file() else {}
            updated['cloud_deleted_models']=list(dict.fromkeys([*updated.get('cloud_deleted_models',[]),key]))
            active=updated.get('cloud_video_workspace')
            reset=False
            if active:
                cfgpath=(self.project/active/'config.json').resolve()
                if cfgpath.is_relative_to((self.project/'cloud_video').resolve()) and cfgpath.is_file():
                    cfg=read(cfgpath);reset=identity(cfg.get('base_url',''),cfg.get('model',''),cfg.get('cloud_provider','wan'))==key
                    if reset:updated.pop('cloud_video_workspace',None)
            from stage_execution_service import publish_cloud_video_workspace_preference
            publish_cloud_video_workspace_preference(self.prefs_path, updated)
            for value in self.drafts.values():
                if value.get('base','').rstrip('/')==base and value.get('model')==model:value['model']=''
            for value in self.initial_records.values():
                if identity(value.get('base_url',''),value.get('model',''),value.get('cloud_provider','wan'))==key:value['model']=''
            self.entries['model'].delete(0,'end');self.refresh_models()
            if reset and getattr(self.desktop,'page_index',None)==self.desktop.page_of('video'):
                self.desktop.show_stage('video',video_mode='cloud')
        except (ValueError,OSError) as exc:notify(self.win, str(exc), level='error', title='云端设置', status=self.desktop.status)

    def open_session(self):
        try:
            if self.desktop.root!=self.project:raise ValueError('当前项目已切换，请关闭设置后在对应项目重新打开')
            if self.desktop.worker or (self.desktop.video and self.desktop.video.busy):raise ValueError('当前任务尚未结束，请稍后保存')
            kind,expected,_,key_env=PROVIDERS[self.provider.get()]
            from api_endpoints import normalize_url
            base=normalize_url(self.entries['base'].get());model=self.entries['model'].get().strip()
            if not model:raise ValueError('请填写已开通的模型ID')
            limit=int(self.entries['budget'].get());key=self.entries['key'].get().strip() or saved_provider_key(self.project,kind,self.remembered,base)
            if self.enabled.get() and not key:raise ValueError('请填写当前接口对应的 API Key 后保存')
            if limit<0:raise ValueError('调用上限不能为负数')
            if any(c.isspace() for c in key) or (key and not key.isascii()):raise ValueError('API Key不能含空格或换行')
            if kind=='wan':
                from agent.wan import WanAdapter
                WanAdapter({'base_url':base})
            else:
                from agent.volcengine import VolcengineAdapter
                VolcengineAdapter({'base_url':base})
            folder=session_folder(self.project,kind,base,model,self.source);folder.mkdir(parents=True,exist_ok=True)
            config_path=folder/'config.json'
            cfg=read(config_path) if config_path.exists() else dict(self.desktop.studio.cfg)
            cfg.update(video_backend='cloud',cloud_provider=kind,base_url=base,model=model,key_env=key_env,
                episode_dir=str(self.episode),episode_file=str(self.source),resolution='720p' if kind=='volcengine' else '720P',
                budget_seconds=limit,reserve_seconds=0,live_enabled=self.enabled.get())
            # R505 P0：会话只标记统一模型池，密钥由当前用户的 DPAPI 存储读取。
            # 不在项目会话留下明文路径或密钥副本。
            import model_pool
            if key and not self.revealed[0]:model_pool.save_named_key(key_env,key)
            cfg['key_provider']='model_pool'
            cfg.pop('project_dir',None)
            saved_prefs=read(self.prefs_path) if self.prefs_path.is_file() else {}
            saved_prefs['cloud_deleted_models']=[k for k in saved_prefs.get('cloud_deleted_models',[]) if k!=identity(base,model,kind)]
            from stage_execution_service import publish_cloud_video_session_config
            publish_cloud_video_session_config(config_path, cfg, self.prefs_path, saved_prefs)
            if self.origin_video is not None and self.origin_video.root.resolve()==folder.resolve():
                self.origin_video.studio.cfg=cfg
                if self.desktop.video is self.origin_video:
                    self.origin_video.refresh();self.origin_video.update_progress()
                self.origin_video.write('设置已保存，继续当前镜头；未提交生成。')
                self.win.destroy()
            elif self.desktop.video is self.origin_video and getattr(self.desktop,'page_index',None)==self.desktop.page_of('video'):
                selected=self.origin_video.tree.selection() if self.origin_video else ()
                draft=self.origin_video.prompt.get('1.0','end').strip() if self.origin_video else None
                self.win.destroy()
                self.desktop.set_video_workspace(folder)
                current=self.desktop.video
                if current and selected and current.tree.exists(selected[0]):
                    current.tree.selection_set(selected[0]);current.select()
                    if draft is not None:
                        current.prompt.delete('1.0','end');current.prompt.insert('1.0',draft)
            else:
                self.desktop.set_video_workspace(folder,navigate=False)
                self.win.destroy()
        except (ValueError,OSError) as e:notify(self.win, str(e), level='error', title='云端设置', status=self.desktop.status)

    def probe_endpoint_now(self):
        from api_endpoints import normalize_url, probe_endpoint
        try:base=normalize_url(self.entries['base'].get())
        except ValueError as exc:self.probe_status.set(str(exc));return
        self.probe_status.set('检测中…')
        def work():
            result=probe_endpoint(base)
            if result.get('reachable') and result.get('code') in (401,403,404):return f'接口可达（HTTP {result["code"]}，需密钥）'
            if result.get('reachable'):return f'接口可达（HTTP {result["code"]}）'
            return '连接失败：'+str(result.get('error','未知错误'))
        # 只读、互不依赖的探测：后台正忙时排队，而不是用 async_ 顶掉正在进行的主动任务（代次覆盖会让其结果被丢弃）。
        self.desktop.async_queued(work,lambda text:self.probe_status.set(str(text)),label='测试云端连接',show_progress=False,retryable=True)

def align_source(desktop,folder):
    source=desktop.current_frame_json().resolve();cfg=read(folder/'config.json')
    if Path(cfg.get('episode_file',Path(cfg['episode_dir'])/'episode.json')).resolve()==source:return folder
    # Preserve old task IDs and history under their original source; never attach
    # another storyboard to an existing task ledger with the same shot numbers.
    target=session_folder(desktop.root,cfg.get('cloud_provider','wan'),cfg['base_url'],cfg['model'],source)
    target.mkdir(parents=True,exist_ok=True)
    if (target/'config.json').is_file():cfg=read(target/'config.json')
    cfg.update(episode_file=str(source),episode_dir=str(source.parent))
    prefs_path=desktop.root/'ui_settings.json';prefs=read(prefs_path) if prefs_path.is_file() else {}
    prefs['cloud_video_workspace']=target.relative_to(desktop.root).as_posix()
    from stage_execution_service import publish_cloud_video_session_config
    publish_cloud_video_session_config(target/'config.json', cfg, prefs_path, prefs)
    return target
