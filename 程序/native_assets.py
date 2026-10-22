"""Send asset data to the installed ComfyUI; import completed results by ID."""
import app_logging
import base64
import hashlib
import json
import logging
import os
import queue
import threading
import time
import uuid
from pathlib import Path
from file_cache import remove_temporary_file
from urllib.parse import urlencode
# 第 34 期第 9 条：`urllib.error` 连 http.client／ssl 一起加载（约 4.4 MB 常驻），
# 本模块只在真要连 ComfyUI 时用得到——改成函数内 import。
from agent.core import read, save, save_bytes
from comfy_service import Comfy
from cloud_assets import MODELS as CLOUD_MODELS
import tk_timers
from ui_tokens import SPACING


LOGGER = logging.getLogger(__name__)


LOCAL='FLUX.2 Klein（本地）'
# 第 65 期任务 3：助手直接给 ComfyUI 提交批次时补齐节点认的默认值（界面只存模型和画幅两项）。
BATCH_DEFAULTS={'model':LOCAL,'aspect_ratio':'1:1','quality':'medium','seed':42}
MODELS=[LOCAL,*CLOUD_MODELS]                    # 云模型清单只有 cloud_assets.MODELS 一份


def _seedream_payload(profile_model, prompt, aspect_ratio, ref_paths):
    """Compatibility facade for callers of the former window module API."""
    from native_asset_codec import seedream_payload
    return seedream_payload(profile_model, prompt, aspect_ratio, ref_paths)


def generated_plan(base):
    """生成目录对应的资产清单；缺失或格式不符时返回空表。"""
    from asset_generated_import_service import generated_plan as _generated_plan
    return _generated_plan(base)

def pending_generated_files(project, base, plan=None):
    """生成目录中尚未登记、可自动导入的 (目录, 文件, 资产编号) 列表；只扫描不写盘。"""
    from asset_generated_import_service import pending_generated_files as _pending_generated_files
    return _pending_generated_files(project, base, plan)

def pending_generated(project, base):
    """生成目录中尚未登记的资产编号；用于启动时轻量预检，不写盘。"""
    from asset_generated_import_service import pending_generated as _pending_generated
    return _pending_generated(project, base)

def _asset_batch_gateway():
    """L4 facade supplies the only L3 gateway accepted by the asset service."""
    from stage_execution_service import asset_batch_gateway
    return asset_batch_gateway()


def import_pending_generated(project, base, report=None):
    """扫描生成目录，把尚未登记的资产图片自动导入资产库（JPEG 自动转 PNG）。"""
    from asset_generated_import_service import import_pending_generated as _import_pending_generated
    return _import_pending_generated(project, base, report, gateway=_asset_batch_gateway())


def cleanup_batches(folder, days=7):
    """Compatibility facade for generated-asset batch cleanup."""
    from asset_generated_import_service import cleanup_batches as _cleanup_batches
    return _cleanup_batches(folder, days)


def _to_png(raw):
    from native_asset_codec import to_png
    return to_png(raw)


def seedream_cost_preview(project, base, items, options):
    """按当前资产与恢复记录预估新增请求，不把取回已有图片算作新生成。"""
    from seedream_api import UNSETTLED, load_profile
    from asset_context import generated_dir
    from asset_batch_service import image_ready
    from pet_llm import RequestLedger
    profile = load_profile(options.get('seedream_profile', ''))
    folder = generated_dir(base, create=False)
    count = 0
    for aid, _asset in items:
        if image_ready(base, aid):
            continue
        path = folder / ('seedream_' + aid + '.json')
        old = read(path) if path.is_file() else {}
        if old.get('state') == 'completed' or old.get('state') in UNSETTLED:
            continue
        if old.get('state') == 'failed' and any(folder.glob(aid + '_seedream*.png')):
            continue
        count += 1
    if not count:
        return '本批无新增 Seedream 请求；仅接续已有结果或提示待核实记录。'
    return f'本批至多新增 {count} 张；已有图片、待核实及可恢复结果不重复提交。\n' + RequestLedger(project).preview_text(
        profile['model'], 'images', {'images': count})


def _run_seedream_direct(project, base, items, options, report, stop=None):
    from seedream_api import UNSETTLED, load_profile, request_image
    from pet_llm import RequestLedger, BudgetRejected
    from uuid import uuid4
    from asset_reference_images import resolve, reference_instruction
    from asset_reference_prompts import display_prompt
    from asset_batch_service import register_image, image_ready
    from native_asset_codec import seedream_provenance
    gateway=_asset_batch_gateway()
    profile=load_profile(options.get('seedream_profile',''))
    report(seedream_cost_preview(project, base, items, options))
    from asset_context import generated_dir
    folder=generated_dir(base)
    aspect=options.get('aspect_ratio','1:1')
    total=len(items);done=[];failed=[];blocked=[]
    for index,(aid,asset) in enumerate(items,1):
        if stop is not None and stop.is_set():
            report('已停止 Seedream 制图');break
        if image_ready(base, aid):
            done.append(aid);report(aid+'：资产图片已就绪，跳过');continue
        report(f'{index}/{total} · {aid}：正在调用 Seedream API 生成…')
        prompt=display_prompt(asset)
        if not prompt.strip():raise ValueError(aid+' 缺少资产提示词')
        instruction=reference_instruction(asset)
        if instruction:prompt=prompt+'\n\n'+instruction
        refs=resolve(base,asset)
        if len(refs)>10:raise ValueError(aid+' 参考图超过 10 张，Seedream 每项最多 10 张')
        payload=_seedream_payload(profile['model'],prompt,aspect,refs)
        record=folder/('seedream_'+aid+'.json')
        trace={'model':profile['model'],'aid':aid,'provenance':seedream_provenance(payload)}
        dest=folder/(aid+'_seedream.png')
        old=read(record) if record.is_file() else {}
        if old.get('state')=='completed':
            done.append(aid);report(aid+'：已有 Seedream 结果，跳过');continue
        if old.get('state') in UNSETTLED:
            # 上次请求可能已经扣费：先到火山控制台核实，本次跳过该项，不再中断整批制图。
            blocked.append(aid+'（记录 '+record.name+'）')
            report(aid+'：上次 Seedream 请求结果不确定，未重复提交；请先核实记录 '+str(record));continue
        cands=sorted(folder.glob(aid+'_seedream*.png'))
        if old.get('state')=='failed' and cands:
            try:
                tmp=folder/(aid+'_recover.png');save_bytes(tmp,_to_png(cands[0].read_bytes()))
                result=register_image(base,aid,asset,tmp,gateway=gateway)
                remove_temporary_file(tmp)
                save(record,{'state':'completed','model':profile['model'],'aid':aid})
                done.append(aid);report(aid+'：'+result+'（已恢复，未重复扣费）');continue
            except Exception as exc:
                blocked.append(aid+'（已有图片恢复失败，请手动核实）')
                report(aid+'：上次图片无法恢复，保留原文件且不重复生成：'+str(exc));continue
        request_id = 'image:' + uuid4().hex
        save(record,{'request_id':request_id,'state':'sending',**trace})
        try:
            with RequestLedger(project).metered_units(request_id, profile['model'], 'assets', 'images', 1):
                raw = request_image(profile, payload)
        except BudgetRejected as exc:
            save(record, {'request_id': request_id, 'state': 'failed', **trace, 'not_submitted': True, 'error': str(exc)})
            failed.append(aid+'：'+str(exc)); report(aid+'：未发送，'+str(exc)); continue
        except Exception as exc:
            save(record,{'request_id':request_id,'state':'uncertain',**trace,'error':str(exc)})
            failed.append(aid+'：'+str(exc));report(aid+'：'+str(exc));continue
        try:
            raw=_to_png(raw);save_bytes(dest,raw)
        except Exception as exc:
            save(record,{'request_id':request_id,'state':'uncertain',**trace,'error':str(exc)})
            failed.append(aid+'：'+str(exc));report(aid+'：'+str(exc));continue
        try:
            result=register_image(base,aid,asset,dest,gateway=gateway)
        except (ValueError,OSError) as exc:
            save(record,{'request_id':request_id,'state':'failed',**trace,'error':str(exc)})
            failed.append(aid+'：'+str(exc));report(aid+'：'+str(exc));continue
        save(record,{'request_id':request_id,'state':'completed',**trace})
        done.append(aid);report(aid+'：'+result)
    message=f'Seedream 已生成并导入 {len(done)}/{total} 项。'
    if failed:message+=' 未完成：'+'；'.join(failed)
    if blocked:message+=' 未完成（结果待核实，未重复提交）：'+'；'.join(blocked)
    return message


def _submit_job(client, state, options, key, health):
    """把批次交给本地 ComfyUI 排队。

    第 65 期任务 3：新版节点在 /drama/assets/health 里声明 direct_submit，意思是「助手自己 POST /prompt，
    再把任务号告诉我」。用户机上原来的做法是调节点的 /drama/assets/dispatch——那个接口在把任务排进
    ComfyUI 队列之后还会抛异常，回一个英文的 500，助手照着就整批中断了，用户看到的现象正是
    「打开 ComfyUI 后无法开始执行任务」（弹窗只有一句 HTTP Error 500）。现在改成：能自己提交就自己提交，
    老节点没有这个能力才走 /dispatch，而且两条路失败都不甩英文栈，只给人话。
    """
    from urllib.error import HTTPError                              # 第 34 期第 9 条：HTTP 栈按需加载
    if health.get('direct_submit'):
        try:
            inputs={name:options.get(name,BATCH_DEFAULTS[name]) for name in BATCH_DEFAULTS}
            inputs['batch_id']=state['id']
            extra={'extra_pnginfo':{'workflow':{}}}
            if key and options['model'] not in (LOCAL,'Seedream 5.0 Pro'):extra['api_key_comfy_org']=key
            try:prompt_id=str(uuid.UUID(state['id']))                  # 节点记的批号就是标准 UUID
            except ValueError:prompt_id=uuid.uuid4().hex               # 万一不是，自己补一个不重号的
            result=client.request('/prompt',{'prompt':{'batch':{'class_type':'DramaAssistantBatch','inputs':inputs}},
                                             'prompt_id':prompt_id,'extra_data':extra})
            if not result.get('prompt_id'):raise ValueError('ComfyUI 没有返回任务编号')
            try:
                client.request('/drama/assets/ack',{'id':state['id'],'prompt_id':result['prompt_id']})
            except (HTTPError,OSError,ValueError) as exc:
                # 任务已由 /prompt 接收，不能因认领回执失败而重复提交；但也不能把这条
                # 网络失败伪装成正常排队，后续进度可能只能由输出目录对账。
                return {'state':'queued','prompt_id':result['prompt_id'],'error':'',
                        'ack_warning':'任务已排入 ComfyUI 队列，但进度认领未确认（'+str(exc)+'）。将继续按输出目录核对结果，不会重复提交。'}
            return {'state':'queued','prompt_id':result['prompt_id'],'error':'','ack_warning':''}
        except HTTPError as exc:
            return {'state':'uncertain','error':'ComfyUI 拒绝了这一批（HTTP '+str(exc.code)+'）。请检查模型与节点配置后重试。'}
        except (OSError,ValueError) as exc:
            return {'state':'uncertain','error':'提交没能确认（'+str(exc)+'）。任务已保留，不会重复提交。'}
    try:
        dispatched=client.request('/drama/assets/dispatch',{'id':state['id'],'options':options,'api_key':key})
    except HTTPError:
        # 老节点这个接口会在任务已经排进队列之后回一个英文 500；不能当成失败中断整批，接着取进度就好。
        return {'state':'queued','error':'',
                'ack_warning':'旧版节点提交接口返回异常；任务可能已排队，将继续核对进度与输出目录，不会重复提交。'}
    return {'state':dispatched['state'],'error':dispatched.get('error','')}

def run(project, base, items, url, report, timeout=7200, options=None, stop=None):
    from asset_batch_service import image_ready, register_image
    from asset_prompt_rules import issues
    from asset_reference_images import snapshot, resolve
    from asset_reference_prompts import display_prompt
    from batch_frames_tool.batch_frames import Client
    from native_apps import wait_comfy
    gateway=_asset_batch_gateway()
    project, base = Path(project), Path(base).resolve()
    items = [(aid, snapshot(base,asset)) for aid,asset in items if not image_ready(base,aid)]
    if not items:return '所选资产均已导入，无需重复生成。'
    for aid, asset in items:
        errors=issues(aid,asset)
        if errors:raise ValueError(aid+'：'+'、'.join(errors))
    options=options or {}
    if options.get('model')=='Seedream 5.0 Pro':
        return _run_seedream_direct(project, base, items, options, report, stop)
    wait_comfy(url,report,cancelled=stop.is_set if stop is not None else None)
    client=Comfy(url)
    from urllib.error import HTTPError                      # 第 34 期第 9 条：HTTP 栈按需加载
    try:health=client.request('/drama/assets/health')
    except HTTPError as exc:
        if exc.code==404:raise ValueError('ComfyUI 没装 drama 资产工作流（接口 404）。请装好后重启 ComfyUI 再试。') from None
        raise
    except OSError as exc:
        # 第 63 期：本地 ComfyUI 中途退出时，原来会把 WinError 10061 这种原文直接甩给用户；
        # 这里换成一句人话，并说清「任务已保留、不会重复扣费」。
        raise ValueError('本地 ComfyUI 没在运行（'+str(exc)+'）。请点“桌面打开 ComfyUI”重新启动后再点一次'
                         '“手动制作资产”；已提交的批次会接着上次的进度走，不会重复提交。') from None
    options=options or health['options']
    if options['model'] not in MODELS:raise ValueError('请选择支持的生图模型。')
    from asset_context import generated_dir
    # 生成图从第 48 期起统一进 generated_dir。
    gen=generated_dir(base)
    # 第 48 期第 3 条：这个目录名（Comfy 资产批次）已经落在用户盘上，改名会让旧项目里生成好的图失联，
    # 所以字面上不加空格，保持原样。
    # 第 63 期修 BUG：批次记录与断点续跑都指着这个目录，可上一轮改生成目录时只改了图片那一半，
    # 这里的 folder 没跟着定义——点「手动制作资产」会在 cleanup_batches(folder) 上直接 NameError。
    folder=project/'workflows/Comfy资产批次';folder.mkdir(parents=True,exist_ok=True)
    cleanup_batches(folder)
    identity=json.dumps([str(base),url,[(aid,asset.get('name'),display_prompt(asset),asset['_reference_signature']) for aid,asset in items]],ensure_ascii=False,sort_keys=True)
    signature=hashlib.sha256(identity.encode()).hexdigest()
    record=None
    for candidate in sorted(folder.glob('*.json'),key=lambda path:path.stat().st_mtime,reverse=True):
        old=read(candidate)
        unfinished=old.get('state') not in ('failed','completed')
        same_remaining=unfinished and all(aid in old.get('assets',{}) and all(asset.get(key)==old['assets'][aid].get(key) for key in ('name','image_prompt','positive_prompt','prompt','description','_reference_signature')) for aid,asset in items)
        if unfinished and (old.get('signature')==signature or same_remaining):
            record=candidate;state=old;break
        # Do not create overlapping batches just because the selection changed.
        if old.get('state') not in ('failed','completed') and set(old.get('assets',{})) & {aid for aid,_ in items}:
            prior=client.request('/drama/assets/job/'+old['id']) if old.get('id') else None
            if prior and prior['state']=='failed':old['state']='failed';save(candidate,old)
            else:raise ValueError('所选资产已有未结束批次，请保持原选择继续获取，或先在 ComfyUI 处理旧批次。')
    if record is None:
        request_id=uuid.uuid4().hex
        state={'id':request_id,'signature':signature,'state':'preparing','assets':dict(items),'imported':[],
               'request':{'request_id':request_id,'project':str(project),'items':[],'delivery':'direct','options':options}}
        record=folder/(request_id+'.json');save(record,state)
    options=state['request'].get('options',options)
    key=''
    if state['state'] in ('preparing','submitting','pending'):
        if options['model']=='Seedream 5.0 Pro':
            from seedream_api import load_profile
            profile=load_profile(options.get('seedream_profile',''))
            options={**options,'seedream_profile':profile['profile_id']}
            state['request']['options']=options;save(record,state)
        elif options['model']!=LOCAL:
            from cloud_assets import get_key
            key=get_key()
            if not key:raise ValueError('请先点击“云模型账号 / 密钥”，登录 Comfy 账户并保存 API Key。本地 FLUX 无需登录。')
    if state['state']=='preparing':
        uploads=Client(url);prepared=[]
        for aid, asset in items:
            report('正在传入 '+aid+' 的提示词和参考图…')
            refs=[]
            for path in resolve(base,asset):
                relative=path.relative_to(base).as_posix()
                refs.append({'image':uploads.upload(path),'role':asset.get('reference_roles',{}).get(relative,'综合参考')})
            prepared.append({'id':aid,'name':asset['name'],'prompt':display_prompt(asset),'references':refs})
        state['request']['items']=prepared;state['state']='submitting';save(record,state)
    if state['state']=='submitting':
        # request_id is saved first. A lost response can be retried without
        # creating another batch, even after the ComfyUI process restarts.
        result=client.request('/drama/assets/start',state['request'])
        state.update(id=result['id'],state=result['state']);save(record,state)
    if state['state']=='pending':
        report('正在直接提交到 ComfyUI：'+options['model'])
        state.update(_submit_job(client,state,options,key,health));save(record,state)
        if state.get('ack_warning'):
            report(state['ack_warning'])
    report('已提交本地 ComfyUI，正在获取生成进度…')
    started=time.monotonic();import_errors={};last_change=time.monotonic();last_key=None
    states={'pending':'等待本地 ComfyUI 接收','claimed':'正在载入工作流','dispatching':'正在提交到生成后端',
            'queued':'排队中','running':'生成中','uncertain':'提交未确认'}
    while time.monotonic()-started < timeout:
        if stop is not None and stop.is_set():
            return '已停止制图；任务已保留，可再次点击“手动制作资产”继续获取，不会重复提交。'
        job=client.request('/drama/assets/job/'+state['id'])
        for file in job.get('files',[]):
            aid=file['id']
            if aid in state['imported'] or aid not in state['assets']:continue
            if aid in import_errors:continue
            try:
                raw=client.request('/view?'+urlencode({k:file[k] for k in ('filename','subfolder','type')}),raw=True)
                dest=gen/(state['id']+'_'+aid+'.png');save_bytes(dest,raw)
                result=register_image(base,aid,state['assets'][aid],dest,gateway=gateway)
                state['imported'].append(aid);save(record,state);report(aid+'：'+result)
            except (ValueError,OSError) as exc:import_errors[aid]=str(exc)
        state.update(state='import_pending' if job['state']=='completed' and import_errors else job['state'],error=job.get('error',''));save(record,state)
        count=len(state['imported']);total=len(state['assets'])
        if job['state'] in ('completed','failed'):
            message=f'已自动导入 {count}/{total} 项。'
            if job['state']=='failed':message+='ComfyUI：'+job.get('error','生成未完成')
            if import_errors:message+=' 图片已保留，待处理：'+'；'.join(aid+' '+error for aid,error in import_errors.items())
            return message
        if job['state']=='uncertain':
            return f'已导入 {count}/{total} 项；'+job.get('error','提交状态待核实；未自动重复发送。')
        if job['state'] in ('pending','claimed') and time.monotonic()-started>90:
            return '任务已保存。请重启本地 ComfyUI 以加载接收功能，再点击“手动制作资产”继续获取；不会重复提交。'
        key=(job['state'],count,str(job.get('error',''))[:120])
        if key!=last_key:last_key=key;last_change=time.monotonic()
        if job['state'] not in ('queued','running') and time.monotonic()-last_change>180:
            return '任务停留在「'+str(job['state'])+'」状态超过 3 分钟，已停止等待。请检查 ComfyUI 界面与模型配置，必要时点击“强制关闭 ComfyUI”后重试；任务已保留，可再次点击“手动制作资产”继续。'
        report(f'已导入 {count}/{total} 项 · '+states.get(job['state'],job['state']))
        time.sleep(2)
    return '本批等待时间较长，任务已保留；再次点击“手动制作资产”将继续获取结果。'


def attach_controls(app, win, form, footer, project, base, selection, status, reload_rows, context_matches):
    return _AssetControls(app=app, win=win, form=form, footer=footer, project=project, base=base, selection=selection, status=status, reload_rows=reload_rows, context_matches=context_matches).build()


class _AssetControls:
    """制图窗口的模型、检测与制图控制区；闭包状态挂在实例上。"""
    def __init__(self, **context):
        self.__dict__.update(context)

    def build(self):
        import tkinter as tk
        from tkinter import ttk, messagebox
        from ui_widgets import BusyState, Card, SelectBox, PrimaryButton, ProgressLabel, SecondaryButton, notify
        self.notify = notify
        from responsive_ui import FlowBar
        self.progress_text=tk.StringVar()
        self.events=queue.Queue()
        self.prefsfile=self.project/'ui_settings.json'
        prefs=read(self.prefsfile) if self.prefsfile.is_file() else {}
        saved=prefs.get('asset_workflow',{})
        self.model=tk.StringVar(value=saved.get('model',LOCAL));self.aspect=tk.StringVar(value=saved.get('aspect_ratio','1:1'))
        config=Card(self.form);config.pack(fill='x',padx=14,pady=10)
        config.columnconfigure(1,weight=1)
        ttk.Label(config,text='生图模型').grid(row=0,column=0,columnspan=4,sticky='w')
        ttk.Label(config,text='模型').grid(row=1,column=0,sticky='w',padx=(0,SPACING['sm']))
        self.selector=SelectBox(config,textvariable=self.model,values=MODELS);self.selector.grid(row=1,column=1,sticky='ew',padx=SPACING['xs'])
        ttk.Label(config,text='画幅').grid(row=1,column=2,padx=(SPACING['md'],SPACING['xs']))
        self.shape=SelectBox(config,textvariable=self.aspect,values=['1:1','9:16','16:9']);self.shape.grid(row=1,column=3,padx=SPACING['xs'])
        self.hint=tk.StringVar();self.account_text=tk.StringVar(value='云模型账号 / 密钥')
        ProgressLabel(config,textvariable=self.hint,wraplength=730).grid(row=2,column=0,columnspan=4,sticky='w',pady=SPACING['sm'])
        self.selector.bind('<<ComboboxSelected>>',self.selected);self.shape.bind('<<ComboboxSelected>>',self.selected)
        SecondaryButton(config,textvariable=self.account_text,command=lambda:self.app.safe(self.account)).grid(row=3,column=0,columnspan=2,sticky='w')
        self.update_hint()
        self.check_stop=threading.Event()
        self.gen_stop=threading.Event()
        progress=ttk.Progressbar(self.form,mode='indeterminate');progress.pack(fill='x',padx=14,pady=6)
        ProgressLabel(self.form,textvariable=self.progress_text,wraplength=760,justify='left').pack(anchor='w',padx=14,pady=(0,4))
        self.busy=BusyState(self.progress_text,progress)
        tk_timers.repeat(self.win,250,self.poll)
        # 第 65 期任务 1：这一排只留「启动并检测」和「取消检测」。「手动制作资产」撤掉——检测通过就自动开跑
        # （见上面 done）；「桌面打开 ComfyUI」主界面已经有一颗；「强制关闭 ComfyUI」与「制作记录」搬到主界面
        # 「阶段配置」右边（desktop.asset_page）。同一件事只留一个入口。
        buttons=FlowBar(self.form);buttons.pack(fill='x',padx=14,pady=(2,8))
        self.check_button=PrimaryButton(buttons,text='启动并检测',command=lambda:self.app.safe(self.check));self.check_button.pack(side='left')
        SecondaryButton(buttons,text='预估费用',command=lambda:self.app.safe(self.preview_cost)).pack(side='left',padx=(6,0))
        self.cancel_button=SecondaryButton(buttons,text='取消检测',command=self.cancel,state='disabled');self.cancel_button.pack(side='left',padx=(6,0))
        tk_timers.repeat(self.win,250,self.update_buttons)
        tk_timers.repeat(self.win,250,self.poll)
        self.update_buttons()

    def update_hint(self):
        self.account_text.set('火山 API 设置' if self.model.get()=='Seedream 5.0 Pro' else '云模型账号 / 密钥')
        if self.model.get()=='Seedream 5.0 Pro':
            from seedream_api import public_profile
            try:detail='当前模型：'+public_profile()['model']
            except ValueError:detail='请保存实际模型 ID 和 API Key。'
            self.hint.set('使用自己的火山 API，费用计入火山账户。'+detail)
        else:self.hint.set('本地运行，无需登录。提示词与参考图直接提交 ComfyUI。' if self.model.get()==LOCAL else '使用 Comfy 账户余额；请在“云模型账号 / 密钥”登录并配置 Comfy API Key。')

    def selected(self, event=None):
        self.update_hint()
        prefs=read(self.prefsfile) if self.prefsfile.is_file() else {}
        prefs['asset_workflow']={'model':self.model.get(),'aspect_ratio':self.aspect.get(),'quality':'medium','seed':42};save(self.prefsfile,prefs)

    def account(self):
        if self.model.get()=='Seedream 5.0 Pro':
            from seedream_settings import show
            show(self.win,on_saved=self.update_hint)
        else:
            from cloud_assets import settings
            settings(self.win)

    def cancel(self):
        self.check_stop.set();self.gen_stop.set()

    def check(self):
        if self.app.worker:raise ValueError('请等待当前任务完成。')
        if not self.app.launch_comfy():return
        self.progress_text.set('正在检测本地 ComfyUI…（可取消）')
        url=self.app.settings.get('comfy_url','http://127.0.0.1:8188')
        self.check_stop.clear();self.busy.set_busy(True,progress_interval=15);self.cancel_button.configure(text='取消检测');self.cancel_button.state(['!disabled'])
        def probe():
            from comfy_service import Comfy
            from urllib.error import HTTPError                  # 第 34 期第 9 条：HTTP 栈按需加载
            try:
                client=Comfy(url)
            except Exception as exc:
                return 'ComfyUI 地址不可用：'+str(exc)
            deadline=time.monotonic()+75
            while not self.check_stop.is_set():
                try:
                    client.request('/system_stats',timeout=5)
                except Exception:
                    if time.monotonic()>=deadline:
                        return 'ComfyUI 未在 75 秒内就绪，请确认程序已打开、本机地址正确（'+url+'）。可点击“强制关闭 ComfyUI”后重新检测。'
                    time.sleep(1)
                    continue
                try:
                    client.request('/drama/assets/health',timeout=5)
                    return 'ComfyUI 已连接，检测通过。正在自动开始制图…'
                except HTTPError as exc:
                    if exc.code==404:
                        return 'ComfyUI 已启动，但缺少资产批量接收组件（/drama/assets/health 404）。请在 ComfyUI 安装/启用 drama 资产工作流组件后，点击“强制关闭 ComfyUI”重启再检测。'
                except Exception:
                    app_logging.swallowed()
                if time.monotonic()>=deadline:
                    return 'ComfyUI 已启动，但资产接收组件未就绪，请重启本地 ComfyUI 后再检测。'
                time.sleep(1)
            return '已取消检测'
        def done(result):
            self.busy.set_busy(False);self.cancel_button.state(['disabled']);self.cancel_button.configure(text='取消检测');self.progress_text.set(result)
            if result.startswith('ComfyUI 已连接'):
                self.app.safe(self.start)
        self.app.async_(probe,done,show_progress=False)

    def poll(self):
        if not self.win.winfo_exists():return
        try:
            while True:self.progress_text.set(self.events.get_nowait())
        except queue.Empty:pass

    def start(self):
        if self.app.worker:raise ValueError('当前任务正在处理，请等待完成。')
        if not self.context_matches():raise ValueError('项目或分镜范围已切换，请重新打开制图窗口。')
        self.reload_rows();items=self.selection()
        if not items:raise ValueError('请至少勾选一项待生成资产。')
        options={'model':self.model.get(),'aspect_ratio':self.aspect.get(),'quality':'medium','seed':42};self.selected()
        if options['model']=='Seedream 5.0 Pro':
            from seedream_api import load_profile
            try:options['seedream_profile']=load_profile()['profile_id']
            except ValueError as exc:
                self.progress_text.set(str(exc));self.account();return
            from seedream_settings import confirm_unsettled
            from asset_context import generated_dir
            confirm_unsettled(self.win,generated_dir(self.base),[aid for aid,_ in items],'资产')
            self.progress_text.set(seedream_cost_preview(self.project, self.base, items, options))
        elif options['model']!=LOCAL:
            from cloud_assets import get_key
            if not get_key():
                self.progress_text.set('请先保存 Comfy API Key，或切换到 Seedream 5.0 Pro（使用火山方舟 Seedream Key）。');self.account();return
        if options['model']!='Seedream 5.0 Pro':
            if not self.app.launch_comfy(silent=True):return             # 第 62 期任务 8：静默拉起，不弹选择框
        self.progress_text.set('正在启动制图：'+options['model']);self.busy.set_busy(True,controls=[self.selector,self.shape],progress_interval=15)
        self.gen_stop.clear();self.cancel_button.configure(text='停止制图');self.cancel_button.state(['!disabled'])
        url=self.app.settings.get('comfy_url','http://127.0.0.1:8188')
        def finished(result):
            self.app.status.set(result)
            try:
                if self.win.winfo_exists():
                    self.busy.set_busy(False)
                    self.cancel_button.state(['disabled']);self.cancel_button.configure(text='取消检测')
                    while not self.events.empty():self.events.get_nowait()
                    self.reload_rows();self.progress_text.set(result)
            except Exception:
                app_logging.swallowed()
            if self.app.root==self.project:self.app.show(2)
            try:
                if self.win.winfo_exists():
                    # 按资产库里的落盘结果判断，不靠返回文案里的关键字：取消、超时、
                    # 只导入一部分的批次都不算完成，不能弹「已自动保存」。
                    from asset_batch_service import batch_complete
                    if batch_complete(self.base,[aid for aid,_ in items]):
                        self.notify(self.win, result+'\n\n已自动保存到资产库。', title='制作完成', status=self.app.status)
                    else:
                        self.notify(self.win, result, level='warning', title='制图提示', status=self.app.status)
                    self.win.destroy()
            except Exception:
                app_logging.swallowed()
        def work():
            try:return run(self.project,self.base,items,url,self.events.put,options=options,stop=self.gen_stop)
            except Exception as exc:
                # 第 65 期任务 1：这里原来把异常原文直接拼给用户
                # （弹窗里那句英文「HTTP Error 500 ...」就是这么漏出来的）。
                # 现在只报一句人话，异常原文留在终端日志里方便排查。
                LOGGER.warning('制图未开始：%r', exc)
                return '制图没能开始，请点「启动并检测」重试'
        self.app.async_(work,finished,show_progress=False)

    def preview_cost(self):
        if not self.context_matches():raise ValueError('项目或分镜范围已切换，请重新打开制图窗口。')
        if self.model.get() != 'Seedream 5.0 Pro':raise ValueError('当前金额预估支持 Seedream 直连，请按实际供应商核对其他模型费用。')
        self.progress_text.set(seedream_cost_preview(self.project, self.base, self.selection(), {}))

    def update_buttons(self):
        if not self.win.winfo_exists():return
        self.check_button.state(['!disabled'] if (not self.app.worker and self.selection()) else ['disabled'])
