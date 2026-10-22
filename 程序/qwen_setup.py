"""Local Alibaba connection settings, kept out of project task files and logs."""
import json,os,re,threading
from pathlib import Path
from urllib.parse import urlparse
# 第 34 期第 9 条：`urllib.request` 连 ssl 一起加载（约 4.4 MB 常驻），验证连接时才 import。
import tkinter as tk
from tkinter import ttk
from api_models import records,remember,remove,label,identity
from agent.core import save
import tk_timers
from ui_tokens import WRAPLENGTH, SPACING
from ui_widgets import (SelectBox, Card, DescriptionBlock, FormDialog, LineInput, PrimaryButton,
                        ProgressLabel, SecondaryButton, ask_confirmation, notify)

def settings_path():return Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'漫剧制作助手'/'qwen-api.json'

# 第 65 期任务 1：密钥统一存进「程序目录/private/.env」，qwen-api.json 里不再留明文。
KEY_ENV='DASHSCOPE_API_KEY'


def child_environment():
    """给 Qwen CLI 的最小 Windows 运行环境，不转交父进程中的其它密钥。"""
    allowed = ('APPDATA', 'COMSPEC', 'HOMEDRIVE', 'HOMEPATH', 'LOCALAPPDATA',
               'NUMBER_OF_PROCESSORS', 'OS', 'PATH', 'PATHEXT', 'PROCESSOR_ARCHITECTURE',
               'PROCESSOR_IDENTIFIER', 'SYSTEMROOT', 'TEMP', 'TMP', 'USERNAME', 'WINDIR')
    return {name: os.environ[name] for name in allowed if os.environ.get(name)}


def unified_key():
    """统一那份 .env 里的密钥；没有就是空串。"""
    try:
        import model_pool
        return model_pool.named_key(KEY_ENV)
    except Exception:
        return ''


def save_key(value):
    """把密钥写进统一那份 .env（界面点「保存设置」时走这里）。"""
    import model_pool
    return model_pool.save_named_key(KEY_ENV,value)


def load():
    path=settings_path()
    value={}
    if path.is_file():
        try:
            data=json.loads(path.read_text(encoding='utf-8-sig'))
            if isinstance(data,dict):
                value=data
        except (OSError,ValueError):
            pass
    merged={'base_url':'https://dashscope.aliyuncs.com/compatible-mode/v1','model':'qwen3.7-plus','api_key':'',**value}
    if not merged['api_key']:
        merged['api_key']=unified_key()          # 密钥不再存在这份 json 里，从统一那份补回来
    return merged

def validate(value):
    value={k:str(value.get(k,'')).strip() for k in ('base_url','model','api_key')}
    from api_endpoints import normalize_url
    value['base_url']=normalize_url(value['base_url'])
    url=urlparse(value['base_url'])
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}',value['model']):raise ValueError('请填写有效的模型 ID')
    if not value['api_key'] and url.hostname in ('localhost','127.0.0.1','::1'):value['api_key']='local'
    if not value['api_key'] or any(c.isspace() for c in value['api_key']):raise ValueError('请填写当前接口对应的 API Key')
    value['base_url']=value['base_url'].rstrip('/')
    return value

def api_credential(api):
    """这一条模型的密钥：只有 model_pool 一处判据（.env／private/.env／环境变量／本机加密）。

    第 62 期任务 3：阶段配置挑的模型自带接口，密钥也照它自己的密钥名去取；不另写一遍读取
    逻辑——界面上说这条能用，这里就得找得到同一把钥匙。
    """
    name=str((api or {}).get('key_env') or '').strip()
    if not name:return ''
    try:
        import model_pool
        return model_pool.key_of({'key_env':name})
    except Exception:
        return ''


def environment(model='',api=None):
    """这一趟要交给 Qwen Code 的运行环境。

    第 62 期任务 3：`api` 是阶段配置里选中那一条模型的接口（根地址／密钥名），给了就用它，
    不再无条件打到 Qwen 的默认地址上——用户在那里选了 deepseek，就不该再调用 qwen3.7-plus。
    """
    cfg=load()
    if not cfg['api_key'] and cfg['base_url'].rstrip('/')=='https://dashscope.aliyuncs.com/compatible-mode/v1':
        cfg['api_key']=os.environ.get('DASHSCOPE_API_KEY','')
    if api:
        cfg['base_url']=str(api.get('base_url') or cfg['base_url'])
        cfg['api_key']=api_credential(api) or cfg['api_key']
    cfg=validate(cfg);env=child_environment()
    env.update(OPENAI_API_KEY=cfg['api_key'],OPENAI_BASE_URL=cfg['base_url'],OPENAI_MODEL=model or cfg['model'])
    return env

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
