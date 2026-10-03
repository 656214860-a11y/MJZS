"""Configure isolated cloud video task sessions without submitting on open."""
import re
import time
import tkinter as tk
from tkinter import ttk,messagebox
import webbrowser
from pathlib import Path
from ui_tokens import SPACING
from ui_widgets import Card, BaseDialog, LineInput, PrimaryButton, ProgressLabel, SecondaryButton, ask_confirmation, notify
from agent.core import read
from api_models import identity,cloud_removed
from project_naming import dated_path

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
def _legacy_provider_label(config):
    kind=config.get('cloud_provider','wan');url=config.get('base_url','').rstrip('/')
    for label,(provider,base,_,_) in PROVIDERS.items():
        if provider==kind and base and url==base:return label
    if not url:return '阿里云百炼 · 万相'
    return '自定义 · 万相兼容' if kind=='wan' else '自定义 · Seedance兼容'

def session_folder(project, kind, base, model, source):
    from cloud_video_service import session_folder as _session_folder
    return _session_folder(project,kind,base,model,source)
def _legacy_session_folder(project, kind, base, model, source):
    # Find an existing ledger, or choose a readable name for a new one.
    parent=Path(project)/'cloud_video';parent.mkdir(exist_ok=True)
    source=Path(source).resolve()
    for candidate in parent.iterdir():
        config=candidate/'config.json'
        if not candidate.is_dir() or not config.is_file():continue
        saved=read(config)
        if not isinstance(saved,dict):continue
        if (saved.get('cloud_provider')==kind and saved.get('base_url','').rstrip('/')==base.rstrip('/')
                and saved.get('model')==model and Path(saved.get('episode_file','')).resolve()==source):
            return candidate
    provider='火山引擎' if kind=='volcengine' else '阿里云'
    model_name=re.sub(r'[^A-Za-z0-9_-]+','-',model).strip('-_')[:55] or '视频模型'
    return dated_path(parent,provider+'_'+model_name)

def saved_provider_key(project,kind,remembered=None,base_url=None):
    from cloud_video_service import saved_provider_key as _saved_provider_key
    return _saved_provider_key(project,kind,PROVIDERS,remembered,base_url,__file__)
def _legacy_saved_provider_key(project,kind,remembered=None,base_url=None):
    key_name='ARK_API_KEY' if kind=='volcengine' else 'DASHSCOPE_API_KEY'
    configs=[]
    if remembered and remembered.get('cloud_provider')==kind:configs.append(remembered)
    for path in sorted((Path(project)/'cloud_video').glob('*/config.json'),key=lambda p:p.stat().st_mtime,reverse=True):
        cfg=read(path)
        if not isinstance(cfg,dict):continue
        if cfg.get('cloud_provider')==kind:configs.append(cfg)
    expected=(base_url or next(spec[1] for spec in PROVIDERS.values() if spec[0]==kind and spec[1])).rstrip('/')
    paths=[Path(c['project_dir'])/'.env' for c in configs if c.get('project_dir') and c.get('base_url','').rstrip('/')==expected]
    if expected in [spec[1] for spec in PROVIDERS.values() if spec[0]==kind and spec[1]]:
        paths.append(Path(__file__).resolve().parent/'private/.env')
    for path in paths:
        if not path.is_file():continue
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if line.lstrip().startswith('#') or '=' not in line:continue
            name,value=line.split('=',1);value=value.strip().strip(chr(34)).strip(chr(39))
            if name.strip()==key_name and value and value not in ('replace_me','<YOUR_API_KEY>'):return value
    return ''

def settings_window(desktop):
    previous=getattr(desktop,'cloud_settings_window',None)
    if previous is not None and previous.winfo_exists():previous.lift();return
    origin_video=desktop.video
    project=Path(desktop.root);source=desktop.current_frame_json();episode=source.parent
    prefs_path=project/'ui_settings.json';prefs=read(prefs_path) if prefs_path.is_file() else {}
    remembered={}
    if prefs.get('cloud_video_workspace'):
        folder=(project/prefs['cloud_video_workspace']).resolve()
        if folder.is_relative_to((project/'cloud_video').resolve()) and (folder/'config.json').is_file():
            remembered=read(folder/'config.json')
            if not isinstance(remembered,dict):remembered={}
    win=BaseDialog(desktop.win,'调用设置 · 云端视频 API',geometry='820x620',modal=False,chrome=False);win.attributes('-alpha',0)
    desktop.cloud_settings_window=win
    body=Card(win);body.pack(fill='both',expand=True,padx=SPACING['lg'],pady=SPACING['lg']);body.columnconfigure(1,weight=1)
    # 第 36 期第 2 条：下半截原来是一大段密排说明 ＋ 一列铺满整行的链接按钮，读起来费劲、
    # 也看不出哪个是主操作。现在窗口可放大（说明跟着换行），下面按「主操作 → 说明分条 →
    # 服务商控制台」三段排。
    win.resizable(True,True);win.minsize(700,560)
    if remembered and cloud_removed(project,remembered):remembered={**remembered,'model':''}
    selected_provider=provider_label(remembered)
    provider=tk.StringVar(value=selected_provider)
    ttk.Label(body,text='接口协议 / 服务商').grid(row=0,column=0,padx=SPACING['md'],pady=SPACING['md'],sticky='w')
    choice=ttk.Combobox(body,textvariable=provider,values=list(PROVIDERS),state='readonly');choice.grid(row=0,column=1,sticky='ew',padx=SPACING['md'])
    entries={}
    for row,(key,label) in enumerate([('base','API根地址'),('model','模型ID'),('key','API Key（留空保留同地址密钥）'),('budget','本地累计调用上限（秒）')],1):
        ttk.Label(body,text=label).grid(row=row,column=0,padx=SPACING['md'],pady=SPACING['md'],sticky='w')
        field=ttk.Combobox(body) if key=='model' else LineInput(body)
        if key=='key':field.configure(show='•')
        field.grid(row=row,column=1,padx=SPACING['md'],sticky='ew');entries[key]=field
    entries['budget'].insert(0,'60')
    drafts={};active_choice=[None];initial_records={};reveal_timer=[None];revealed=[False]
    def conceal_key():
        """结束临时查看时立即清空控件，避免已保存凭据停留在窗口内存/屏幕上。"""
        if reveal_timer[0] is not None:
            try:win.after_cancel(reveal_timer[0])
            except tk.TclError:pass
            reveal_timer[0]=None
        entries['key'].configure(show='•');entries['key'].delete(0,'end');revealed[0]=False
    def reveal_key():
        kind,base,_,_=PROVIDERS[provider.get()]
        key=saved_provider_key(project,kind,initial_records.get(provider.get(),{}),entries['base'].get().strip() or base)
        if not key:
            notify(win, '当前接口没有已保存的 API Key。', title='云端设置', status=desktop.status);return
        entries['key'].delete(0,'end');entries['key'].insert(0,key);entries['key'].configure(show='')
        revealed[0]=True;reveal_timer[0]=win.after(KEY_REVEAL_MS,conceal_key)
    entries['key'].bind('<KeyPress>',lambda _event: revealed.__setitem__(0,False))
    def on_window_destroy(event):
        if event.widget is win and reveal_timer[0] is not None:
            try:win.after_cancel(reveal_timer[0])
            except tk.TclError:pass
            reveal_timer[0]=None
    win.bind('<Destroy>',on_window_destroy,add='+')
    for saved_path in sorted((project/'cloud_video').glob('*/config.json'),key=lambda p:p.stat().st_mtime):
        candidate=read(saved_path)
        if not isinstance(candidate,dict):continue
        if not cloud_removed(project,candidate):initial_records[provider_label(candidate)]=candidate
    if remembered:initial_records[selected_provider]=remembered
    def select(event=None):
        if active_choice[0]:
            drafts[active_choice[0]]={k:e.get().strip() for k,e in entries.items()}
            if revealed[0]:drafts[active_choice[0]]['key']=''
        conceal_key()
        label=provider.get();kind,base,model,_=PROVIDERS[label]
        record=initial_records.get(label,{})
        values=drafts.get(label,{'base':record.get('base_url',base),'model':record.get('model',model),
            'budget':str(record.get('budget_seconds',60)),'key':''})
        for key,value in values.items():entries[key].delete(0,'end');entries[key].insert(0,value)
        active_choice[0]=label
        refresh_models()
    def refresh_models(event=None):
        kind,_,_,_=PROVIDERS[provider.get()];base=entries['base'].get().strip().rstrip('/')
        pref=read(prefs_path) if prefs_path.is_file() else {};deleted=set(pref.get('cloud_deleted_models',[]))
        official=any(p==kind and u==base for p,u,_,_ in PROVIDERS.values() if u)
        values=({'wan':['wan2.7-r2v','wan2.7-r2v-2026-06-12','wan2.6-i2v-flash'],
                 'volcengine':['doubao-seedance-2-5-260628','doubao-seedance-2-0-260128','doubao-seedance-1-5-pro-251215']}[kind] if official else [])
        for saved_path in sorted((project/'cloud_video').glob('*/config.json')):
            cfg=read(saved_path)
            if not isinstance(cfg,dict):continue
            if cfg.get('cloud_provider')==kind and cfg.get('base_url','').rstrip('/')==base:values.append(cfg.get('model',''))
        entries['model'].configure(values=[m for m in dict.fromkeys(values) if m and identity(base,m,kind) not in deleted])
        if event is None and identity(base,entries['model'].get(),kind) in deleted:entries['model'].delete(0,'end')
    def delete_model():
        try:
            if desktop.root!=project:raise ValueError('项目已切换，请重新打开 API 设置')
            if desktop.worker or (desktop.video and desktop.video.busy):raise ValueError('请等待当前请求结束后删除模型')
            kind=PROVIDERS[provider.get()][0];base=entries['base'].get().strip().rstrip('/');model=entries['model'].get().strip()
            if not base or not model:raise ValueError('请先选择要删除的模型')
            if not ask_confirmation(win, '删除模型', f'删除模型 {model}？\n接口：{base}\n仅移除可选模型，已有视频和正在处理的任务保留。', dangerous=True):return
            key=identity(base,model,kind);updated=read(prefs_path) if prefs_path.is_file() else {}
            updated['cloud_deleted_models']=list(dict.fromkeys([*updated.get('cloud_deleted_models',[]),key]))
            active=updated.get('cloud_video_workspace')
            reset=False
            if active:
                cfgpath=(project/active/'config.json').resolve()
                if cfgpath.is_relative_to((project/'cloud_video').resolve()) and cfgpath.is_file():
                    cfg=read(cfgpath);reset=identity(cfg.get('base_url',''),cfg.get('model',''),cfg.get('cloud_provider','wan'))==key
                    if reset:updated.pop('cloud_video_workspace',None)
            from stage_execution_service import publish_cloud_video_workspace_preference
            publish_cloud_video_workspace_preference(prefs_path, updated)
            for value in drafts.values():
                if value.get('base','').rstrip('/')==base and value.get('model')==model:value['model']=''
            for value in initial_records.values():
                if identity(value.get('base_url',''),value.get('model',''),value.get('cloud_provider','wan'))==key:value['model']=''
            entries['model'].delete(0,'end');refresh_models()
            if reset and getattr(desktop,'page_index',None)==desktop.page_of('video'):
                desktop.show_stage('video',video_mode='cloud')
        except (ValueError,OSError) as exc:notify(win, str(exc), level='error', title='云端设置', status=desktop.status)
    SecondaryButton(body,text='删除模型',command=delete_model).grid(row=2,column=2,padx=(SPACING['none'],SPACING['md']))
    entries['base'].bind('<FocusOut>',refresh_models)
    choice.bind('<<ComboboxSelected>>',select);select()
    enabled=tk.BooleanVar(value=remembered.get('live_enabled',True))
    ttk.Checkbutton(body,text='允许联网调用（不会自动提交）',variable=enabled).grid(row=5,column=0,columnspan=2,padx=SPACING['md'],pady=(SPACING['md'],SPACING['xs']),sticky='w')
    def open_session():
        try:
            if desktop.root!=project:raise ValueError('当前项目已切换，请关闭设置后在对应项目重新打开')
            if desktop.worker or (desktop.video and desktop.video.busy):raise ValueError('当前任务尚未结束，请稍后保存')
            kind,expected,_,key_env=PROVIDERS[provider.get()]
            from api_endpoints import normalize_url
            base=normalize_url(entries['base'].get());model=entries['model'].get().strip()
            if not model:raise ValueError('请填写已开通的模型ID')
            limit=int(entries['budget'].get());key=entries['key'].get().strip() or saved_provider_key(project,kind,remembered,base)
            if enabled.get() and not key:raise ValueError('请填写当前接口对应的 API Key 后保存')
            if limit<0:raise ValueError('调用上限不能为负数')
            if any(c.isspace() for c in key) or (key and not key.isascii()):raise ValueError('API Key不能含空格或换行')
            if kind=='wan':
                from agent.wan import WanAdapter
                WanAdapter({'base_url':base})
            else:
                from agent.volcengine import VolcengineAdapter
                VolcengineAdapter({'base_url':base})
            folder=session_folder(project,kind,base,model,source);folder.mkdir(parents=True,exist_ok=True)
            config_path=folder/'config.json'
            cfg=read(config_path) if config_path.exists() else dict(desktop.studio.cfg)
            cfg.update(video_backend='cloud',cloud_provider=kind,base_url=base,model=model,key_env=key_env,
                episode_dir=str(episode),episode_file=str(source),resolution='720p' if kind=='volcengine' else '720P',
                budget_seconds=limit,reserve_seconds=0,live_enabled=enabled.get())
            # R505 P0：会话只标记统一模型池，密钥由当前用户的 DPAPI 存储读取。
            # 不在项目会话留下明文路径或密钥副本。
            import model_pool
            if key and not revealed[0]:model_pool.save_named_key(key_env,key)
            cfg['key_provider']='model_pool'
            cfg.pop('project_dir',None)
            saved_prefs=read(prefs_path) if prefs_path.is_file() else {}
            saved_prefs['cloud_deleted_models']=[k for k in saved_prefs.get('cloud_deleted_models',[]) if k!=identity(base,model,kind)]
            from stage_execution_service import publish_cloud_video_session_config
            publish_cloud_video_session_config(config_path, cfg, prefs_path, saved_prefs)
            if origin_video is not None and origin_video.root.resolve()==folder.resolve():
                origin_video.studio.cfg=cfg
                if desktop.video is origin_video:
                    origin_video.refresh();origin_video.update_progress()
                origin_video.write('设置已保存，继续当前镜头；未提交生成。')
                win.destroy()
            elif desktop.video is origin_video and getattr(desktop,'page_index',None)==desktop.page_of('video'):
                selected=origin_video.tree.selection() if origin_video else ()
                draft=origin_video.prompt.get('1.0','end').strip() if origin_video else None
                win.destroy()
                desktop.set_video_workspace(folder)
                current=desktop.video
                if current and selected and current.tree.exists(selected[0]):
                    current.tree.selection_set(selected[0]);current.select()
                    if draft is not None:
                        current.prompt.delete('1.0','end');current.prompt.insert('1.0',draft)
            else:
                desktop.set_video_workspace(folder,navigate=False)
                win.destroy()
        except (ValueError,OSError) as e:notify(win, str(e), level='error', title='云端设置', status=desktop.status)
    probe_status=tk.StringVar(value='')
    def probe_endpoint_now():
        from api_endpoints import normalize_url, probe_endpoint
        try:base=normalize_url(entries['base'].get())
        except ValueError as exc:probe_status.set(str(exc));return
        probe_status.set('检测中…')
        def work():
            result=probe_endpoint(base)
            if result.get('reachable') and result.get('code') in (401,403,404):return f'接口可达（HTTP {result["code"]}，需密钥）'
            if result.get('reachable'):return f'接口可达（HTTP {result["code"]}）'
            return '连接失败：'+str(result.get('error','未知错误'))
        desktop.async_(work,lambda text:probe_status.set(str(text)),show_progress=False)
    # ① 主操作：保存设置摆在最前面并加粗（原来三样挤在一行、也没个主次）。
    row7=ttk.Frame(body);row7.grid(row=6,column=0,columnspan=2,sticky='ew',padx=SPACING['md'],pady=(SPACING['sm'],SPACING['md']))
    PrimaryButton(row7,text='保存设置',command=open_session).pack(side='left')
    SecondaryButton(row7,text='测试连接',command=probe_endpoint_now).pack(side='left',padx=SPACING['sm'])
    SecondaryButton(row7,text='显示已保存密钥（10 秒）',command=reveal_key).pack(side='left',padx=SPACING['sm'])
    ProgressLabel(row7,textvariable=probe_status).pack(side='left',padx=SPACING['sm'])
    # ② 说明分条：一条一行，跟着窗口宽度换行——原来是一整段四行密排，读起来串行。
    notes=ttk.LabelFrame(body,text='说明与限制',padding=(SPACING['md'],SPACING['sm']));notes.grid(row=7,column=0,columnspan=2,sticky='ew',padx=SPACING['md'])
    notes.columnconfigure(0,weight=1)
    for index,line in enumerate((
        '自定义地址需兼容所选万相或 Seedance API 协议；模型 ID 可手动填写，点「保存设置」后回填。',
        '全部资产上传：万相 2.7-r2v 支持首帧＋最多 5 张资产；Seedance 2.0 支持首帧构图参考＋最多 8 张资产（不严格锁定首帧）。',
        '需先在服务商开通对应模型；不会自动切换模型。1.0 无声音，1.5／万相 2.6 图生视频不支持此多资产流程。',
        '本地秒数预算不代表免费额度，调用前请核对费用。')):
        ttk.Label(notes,text='· '+line,wraplength=740,justify='left').grid(row=index,column=0,sticky='w')
    # ③ 服务商控制台：三个小按钮排一行（原来是一列铺满整行的按钮，看着像三件正经操作）。
    links=ttk.Frame(body);links.grid(row=8,column=0,columnspan=2,sticky='w',padx=SPACING['md'],pady=(SPACING['sm'],SPACING['md']))
    ttk.Label(links,text='服务商控制台',style='Muted.TLabel').pack(side='left',padx=(SPACING['none'],SPACING['sm']))
    for label,url in (
        ('阿里云：免费额度与用完即停','https://help.aliyun.com/zh/model-studio/new-free-quota'),
        ('火山引擎：模型控制台','https://console.volcengine.com/ark'),
        ('腾讯混元：免费额度说明（尚未接入）','https://cloud.tencent.com/document/product/1616/82562')):
        SecondaryButton(links,text=label,
                        command=lambda u=url:webbrowser.open(u)).pack(side='left',padx=(SPACING['none'],SPACING['sm']))

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
