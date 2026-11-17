"""Persistent ComfyUI video jobs, local loopback only; no cloud key or quota."""
import copy, json, time, uuid, math
from pathlib import Path
from api_endpoints import no_redirect
from file_cache import remove_temporary_file
# 第 34 期第 9 条：`urllib.request`／`urllib.error` 连 ssl 一起加载（约 4.4 MB 常驻），
# 本模块只在真要发本机 HTTP 时用得到——都改成函数内 import。
from urllib.parse import urlparse,urlencode,quote
from orchestrator.engine import Studio, REVIEW_PASS, AUTO_REVIEW_NOTE, auto_review_ready
from agent.core import read,save,file_hash,command,fingerprint,temporary_path,replace
from agent.media import check, png_size
import project_settings
from ui_tokens import CHAR_WIDTH, WRAPLENGTH, SPACING
from ui_widgets import BaseDialog, Card, LineInput, PrimaryButton, SecondaryButton
import contract.pet_bus as pet_bus

def model_name(cfg=None):
    """本地视频当前使用的模型：取已保存工作流的文件名，未配置时按默认 H3 显示。"""
    workflow=str((cfg or {}).get('local_video',{}).get('workflow','')).strip()
    return Path(workflow).stem if workflow else 'MiniMax H3'

class LocalAPI:
    def __init__(self,url):
        from urllib.request import build_opener,ProxyHandler   # 第 34 期第 9 条：HTTP 栈按需加载
        self.url=url.rstrip('/');p=urlparse(self.url)
        if p.scheme!='http' or p.hostname not in ('127.0.0.1','localhost','::1') or p.username or p.password or p.path or p.query:
            raise ValueError('本地视频只接受本机HTTP地址，例如 http://127.0.0.1:8189')
        self.opener=build_opener(ProxyHandler({}),no_redirect())
    def call(self,path,payload=None,body=None,content_type=None):
        from urllib.request import Request                     # 第 34 期第 9 条：HTTP 栈按需加载
        from contract.platform_tools import current_execution
        control = current_execution()
        timeout = control.remaining(30) if control is not None else 30
        data=json.dumps(payload).encode() if payload is not None else body
        req=Request(self.url+path,data=data,headers={'Content-Type':content_type or 'application/json'})
        with self.opener.open(req,timeout=timeout) as r:return json.load(r)
    def upload(self,frame, *, evidence=None):
        data=Path(frame).read_bytes()
        kind=('png','image/png') if data.startswith(b'\x89PNG\r\n\x1a\n') else ('jpg','image/jpeg') if data.startswith(b'\xff\xd8') else ('webp','image/webp') if data[:4]==b'RIFF' and data[8:12]==b'WEBP' else None
        if not kind or len(data)>20*1024**2:raise ValueError('参考图片必须是20MB以内的PNG、JPEG或WebP')
        boundary='drama'+uuid.uuid4().hex;name='drama_'+uuid.uuid4().hex+'.'+kind[0]
        body=(f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{name}"\r\nContent-Type: {kind[1]}\r\n\r\n'.encode()+data+f'\r\n--{boundary}--\r\n'.encode())
        result=self.call('/upload/image',body=body,content_type='multipart/form-data; boundary='+boundary)
        if evidence is not None:
            import hashlib
            evidence.update(path=str(Path(frame).resolve()), sha256=hashlib.sha256(data).hexdigest())
        return (result.get('subfolder','').strip('/')+'/' + result['name']).lstrip('/')
    def download(self,item,dest):
        from contract.platform_tools import current_execution, execution_checkpoint
        control = current_execution()
        timeout = control.remaining(90) if control is not None else 90
        query=urlencode({k:item.get(k,'') for k in ('filename','subfolder','type')})
        dest=Path(dest);dest.parent.mkdir(parents=True,exist_ok=True)
        temp=temporary_path(dest,'.partial.mp4');total=0
        try:
            with self.opener.open(self.url+'/view?'+query,timeout=timeout) as response,temp.open('wb') as out:
                while block:=response.read(1024**2):
                    execution_checkpoint()
                    total+=len(block)
                    if total>2*1024**3:raise ValueError('单镜超过2GB，已停止取回')
                    out.write(block)
            if not total:raise ValueError('视频文件为空')
            execution_checkpoint()
            replace(temp,dest)
        finally:
            if temp.exists():remove_temporary_file(temp)

    def locate_prompt(self,client_id='',workflow=None,attempts=3,wait=1.0):
        """提交响应中断后，按本次 client_id（或完全相同的图）找回已进入 ComfyUI 的任务编号。"""
        from comfy_service import locate_prompt
        return locate_prompt(lambda path:self.call(path),client_id,workflow=workflow,attempts=attempts,wait=wait)

def prepare_graph(root,cfg,shot):
    options=cfg.get('local_video',{});path=Path(options.get('workflow',str(Path(__file__).parent/'workflows/h3_i2v_api.json')))
    if not path.is_absolute():path=Path(root)/path
    if not path.is_file():raise ValueError('请在本地视频设置中选择API工作流')
    graph=copy.deepcopy(read(path))
    if not isinstance(graph,dict) or not graph or not all(isinstance(n,dict) and 'class_type' in n and 'inputs' in n for n in graph.values()):raise ValueError('请选择API格式工作流，不是ComfyUI画布JSON')
    def setvalue(binding,value):
        try:node,field=binding.split('.',1);inputs=graph[node]['inputs']
        except (ValueError,KeyError):raise ValueError('节点映射无效：'+binding)
        if field not in inputs or isinstance(inputs[field],list):raise ValueError('需要映射未连线的输入字段：'+binding)
        inputs[field]=value
    setvalue(options.get('prompt','104.prompt'),shot['video_prompt'])
    seconds=shot['duration'];mode=options.get('duration_mode','h3_frames')
    if mode=='h3_frames':
        if not 4<=seconds<=15:raise ValueError('H3单镜使用4–15秒，请调整镜头时长')
        count=round(seconds*24);duration=count+(5-count%17)%17
    elif mode=='seconds':duration=seconds
    else:raise ValueError('无效时长映射模式')
    setvalue(options.get('duration','104.length'),duration)
    if options.get('seed','15.noise_seed'):setvalue(options.get('seed','15.noise_seed'),int(uuid.uuid4().hex[:12],16))
    image=options.get('image','114.image');setvalue(image,'pending_upload.png')
    output=options.get('output','92')
    if output not in graph:raise ValueError('输出节点不存在')
    return graph,options

def preflight(api,graph):
    info=api.call('/object_info');missing=[]
    for node in graph.values():
        name=node['class_type']
        if name not in info:missing.append('节点 '+name);continue
        definition=info[name]
        if definition.get('api_node') or 'api node' in definition.get('category','').lower():raise ValueError('工作流包含云端API节点，不能作为本地方案')
        schema=definition.get('input',{}).get('required',{})
        for field,value in node['inputs'].items():
            spec=schema.get(field)
            choices=spec[0] if spec and isinstance(spec[0],list) else (spec[1].get('options') if spec and len(spec)>1 and isinstance(spec[1],dict) else None)
            if field in ('unet_name','clip_name','vae_name','lora_name') and choices is not None and value not in choices:missing.append('模型 '+str(value))
    if missing:raise ValueError('尚未准备好：\n'+'\n'.join(sorted(set(missing))))
    return '本地节点和模型名称检查通过（生成速度及显存仍需实测）'

class LocalStudio(Studio):
    def submit(self,sid,progress=None):
        from urllib.error import HTTPError                     # 第 34 期第 9 条：HTTP 栈按需加载
        report=progress or (lambda text:None)
        report("正在准备本地工作流…")
        from white_model import validate_video_submission
        validate_video_submission(self,sid)
        with self.lock():
            st=self.state();versions=st['shots'][sid];shot=self.shot(sid)
            from domain.video_task_state import submission_block_reason
            blocked=submission_block_reason(versions)
            if blocked:raise ValueError(blocked)
            graph,options=prepare_graph(self.root,self.cfg,shot);api=LocalAPI(options.get('url','http://127.0.0.1:8189'))
            frame=self.frame(shot)
            fw,fh=png_size(frame)
            ratio=fw/fh
            sizes=[]
            for node in graph.values():
                if node.get('class_type')=='MiniMaxH3ImageToVideo':
                    inputs=node['inputs'];budget=int(inputs.get('width',608))*int(inputs.get('height',352))
                    candidates=[(w,h) for w in range(128,2049,32) for h in range(128,2049,32) if w*h<=budget]
                    if not candidates:raise ValueError('工作流分辨率预算过小')
                    w,h=min(candidates,key=lambda size:(round(abs(math.log((size[0]/size[1])/ratio)),2),-size[0]*size[1]))
                    inputs.update(width=w,height=h);sizes.append((w,h))
                    inputs['prompt']+='\n画幅由首帧确定，保持人物原始身材比例，不拉伸人物。'
            has_audio=bool(shot.get('generate_audio',True))
            if not has_audio:
                for node in graph.values():
                    if node.get('class_type')=='CreateVideo':node['inputs'].pop('audio',None)
            report('首帧比例匹配：'+('、'.join(f'{w}×{h}' for w,h in sizes) or '沿用工作流')+'；'+('生成音轨' if has_audio else '无音轨'))
            from infra.h3_reference_adapter import attach
            references=attach(graph,options,self.episode_path,shot)
            if references:report('已接入 '+str(len(references))+' 张资产参考图；需要 Ref2VA 模型')
            from native_apps import open_comfy,wait_comfy
            open_comfy();wait_comfy(api.url,report)
            report('正在连接 ComfyUI 并检查节点：'+api.url);preflight(api,graph)
            report('正在检查视频处理工具…')
            command([self.cfg['ffmpeg'],'-version']);command([self.cfg['ffprobe'],'-version'])
            report('正在上传本镜首帧…')
            first_frame = {'category': 'image'}
            image=api.upload(frame, evidence=first_frame);node,field=options.get('image','114.image').split('.',1);graph[node]['inputs'][field]=image
            source_assets = []
            for asset in references:
                report('正在上传参考图：'+asset['id']+' '+asset['name'])
                receipt = {'id': asset['id'], 'name': asset['name']}
                graph[asset['node_id']]['inputs']['image']=api.upload(asset['path'], evidence=receipt)
                source_assets.append(receipt)
            if any(not item.get('path') or not item.get('sha256') for item in [first_frame, *source_assets]):
                raise ValueError('本地上传缺少素材来源回执，尚未提交生成')
            v={'version':len(versions)+1,'state':'submitting','seconds':shot['duration'],'charged':False,'backend':'comfy','endpoint':api.url,'output_node':options.get('output','92'),'review':'pending','created':time.time(),'signature':fingerprint(graph)}
            from contract.platform_tools import execution_metadata
            v['execution'] = execution_metadata('video', sid)
            v['retry_reason'] = 'explicit_after_' + str(versions[-1].get('state', 'unknown')) if versions else 'initial'
            v.update(generate_audio=has_audio,source_aspect=ratio,reference_assets=[{'id':a['id'],'name':a['name'],'picture':a['picture'],'path':a['path']} for a in references])
            folder=self.root/'data'/sid/f"v{v['version']:03}";folder.mkdir(parents=True,exist_ok=True);save(folder/'request.json',graph)
            save(folder/'assets_manifest.json', {'mode': 'local', 'assets': source_assets, 'first_frame': first_frame})
            client_id=uuid.uuid4().hex
            v['client_id']=client_id
            versions.append(v);save(self.db,st)
            def reattach():
                # 提交响应中断时任务往往已经排队：先按 client_id 在队列与历史里找回，绝不重复提交。
                try:prompt_id=api.locate_prompt(client_id,graph)
                except Exception:
                    v['state']='unknown';save(self.db,st)
                    raise RuntimeError('提交结果不确定且暂时无法查询；恢复连接后查询，不自动重发') from None
                if not prompt_id:return False
                v.update(task_id=prompt_id,state='queued',recovered_at=time.time());save(self.db,st)
                report('提交响应中断，已按 client_id 找回任务编号 '+prompt_id)
                return True
            try:
                report('正在向 ComfyUI 提交任务…')
                response=api.call('/prompt',{'prompt':graph,'client_id':client_id})
                if not response.get('prompt_id'):raise RuntimeError('未返回任务编号')
                v.update(task_id=response['prompt_id'],state='queued',submitted_at=time.time())
            except HTTPError as e:
                if e.code>=500 and reattach():return '提交响应中断，已按 client_id 找回任务编号；点击查询/下载取回。'
                v['state']='rejected' if 400<=e.code<500 else 'unknown';save(self.db,st);raise ValueError('ComfyUI拒绝请求或连接异常，请查看工作流：HTTP '+str(e.code)) from None
            except Exception:
                if reattach():return '提交响应中断，已按 client_id 找回任务编号；点击查询/下载取回。'
                v['state']='unknown';save(self.db,st);raise RuntimeError('提交结果不确定，请在ComfyUI核对任务编号，不自动重发') from None
            save(self.db,st);return '本地任务已提交；不使用云端额度。点击查询/下载取回。'
    def poll(self,sid):
        with self.lock():
            st=self.state();vs=st['shots'][sid]
            if not vs:raise ValueError('尚无任务')
            v=vs[-1]
            if v['state']=='downloaded':return '已下载，不重复取回'
            if v.get('backend')!='comfy':raise ValueError('这是历史云端任务，本地模式不会查询云端')
            api=LocalAPI(v['endpoint'])
            if not v.get('task_id'):
                # 旧记录可能停在「结果不确定」：按当初保存的工作流再比对一次，找回就继续自动取回。
                request=self.root/'data'/sid/f"v{v['version']:03}"/'request.json'
                prompt_id=api.locate_prompt(v.get('client_id',''),read(request) if request.is_file() else None)
                if not prompt_id:raise ValueError('请在ComfyUI核实任务编号，再使用恢复任务编号')
                v.update(task_id=prompt_id,state='queued',recovered_at=time.time());save(self.db,st)
            h=api.call('/history/'+quote(v['task_id'],safe='')).get(v['task_id'])
            if not h:return '本地排队或生成中；稍后再查询'
            if h.get('status',{}).get('status_str')=='error':
                v['state']='failed';save(self.db,st);return '本地生成失败，请在ComfyUI查看显存或节点错误'
            out=h.get('outputs',{}).get(v['output_node'],{});items=[]
            for value in out.values():
                if isinstance(value,list):items.extend(x for x in value if isinstance(x,dict) and x.get('type')=='output' and str(x.get('filename','')).lower().endswith('.mp4'))
            if len(items)!=1:
                # 任务已跑完但指定输出节点没有恰好一个MP4：属确定的失败，标记为 failed 让用户改正工作流后重做；
                # 否则版本一直停在 queued，而已完成的版本不允许重新提交，只能手改状态文件。
                v['state']='failed';save(self.db,st)
                raise ValueError('指定输出节点 '+str(v['output_node'])+' 没有输出一个MP4视频；已标记为失败，请改正工作流设置后重新提交')
            folder=self.root/'data'/sid/f"v{v['version']:03}";dest=folder/(sid+'.mp4');v['state']='succeeded';v['succeeded_observed_at']=time.time();v['download_started_at']=time.time();save(self.db,st)
            api.download(items[0],dest)
            v['download_completed_at']=time.time();save(self.db,st)
            try:
                report=check(dest,v['seconds'],{**self.cfg,'require_audio':v.get('generate_audio',True)})
                from agent.media import probe
                streams=probe(dest,self.cfg).get('streams',[])
                picture=next((x for x in streams if x.get('codec_type')=='video'),None)
                if picture and v.get('source_aspect') and abs((picture['width']/picture['height'])/v['source_aspect']-1)>0.04:report['errors'].append('视频比例与首帧不一致')
                command([self.cfg['ffmpeg'],'-v','error','-xerror','-i',dest,'-f','null','-'])
                if auto_review_ready(self.root,report):
                    v.update(review=REVIEW_PASS,review_by='auto',review_note=AUTO_REVIEW_NOTE)
            except Exception as exc:
                self.publish_downloaded_video(st,sid,v,dest,qc_error=exc)
                return '本地视频已取回；质检未完成，请检查FFmpeg设置后再验收'
            self.publish_downloaded_video(st,sid,v,dest,report)
            if report['errors']:return '本地视频已取回；QC未通过：'+'；'.join(report['errors'])
            return '本地视频已取回；'+('已按自动验收设置放行（未做内容审核）' if v.get('review')==REVIEW_PASS else '技术QC通过，待您验收')

    def note_failure(self,sid,error):
        """把无人值守提交失败记成一条失败版本：下一轮按失败跳过，不反复重提，等用户看报告处理。"""
        with self.lock():
            st=self.state();versions=st.setdefault('shots',{}).setdefault(sid,[])
            versions.append({'version':len(versions)+1,'state':'failed','error':str(error),'backend':'comfy',
                             'endpoint':(self.cfg.get('local_video') or {}).get('url','http://127.0.0.1:8189'),
                             'review':'pending','created':time.time(),'note':'无人值守自动提交失败'})
            save(self.db,st)


def _brief(ids):return '、'.join(ids[:5])+('…' if len(ids)>5 else '')


def skip_summary(skipped,limit=3):
    """把 [(镜头,原因)] 按原因归并成一句（无人值守的状态栏只有一行）。

    不同镜头被跳过的原因常常不同（缺首帧 / 上次生成未完成 / 已标记需修改），只报第一条会让人以为
    只有这一种问题：补齐首帧后仍然停着，也不知道还差什么。条数相同的按原因排序，同一状态稳定复现。
    """
    counts={}
    for _sid,why in skipped:counts[str(why)]=counts.get(str(why),0)+1
    ordered=sorted(counts.items(),key=lambda item:(-item[1],item[0]))
    parts=[why+' '+str(count)+' 镜' for why,count in ordered[:limit]]
    if len(ordered)>limit:parts.append('另有 '+str(len(ordered)-limit)+' 类原因')
    return '；'.join(parts)


def auto_skip_notice(source, skipped):
    """返回无人值守自动视频跳过提示的去重键和正文。"""
    return (str(source), tuple(skipped)), '无人值守自动补视频暂缓：'+str(len(skipped))+' 镜跳过：'+skip_summary(skipped)


def auto_poll_decision(source, submit, poll, skipped, previous_signature):
    """计算自动视频轮询应提示、跳过还是派发，不执行任何任务。"""
    if not submit and not poll:
        notice, message = auto_skip_notice(source, skipped)
        return {'action': 'notice' if skipped else 'idle', 'notice': notice, 'message': message}
    signature = tuple(submit)
    if not poll and signature == previous_signature:
        return {'action': 'skip', 'signature': signature}
    return {'action': 'dispatch', 'signature': signature}


def auto_plan(project,source,studio=None):
    """无人值守本地视频清单：把当前分镜的镜头分成「待提交」「待查询」，其余连同原因放进 skipped。

    只认本地 ComfyUI：线上视频按秒计费，无人值守绝不静默提交。已取回的镜头不重做；
    上次生成失败、被拒绝或没有任务编号的镜头只跳过并写明原因，等用户查看 ComfyUI 后手动处理。
    """
    from domain.video_task_state import ACTIVE
    project=Path(project);source=Path(source)
    studio=studio or open_studio(project,episode_file=source)
    if not isinstance(studio,LocalStudio):raise ValueError('无人值守自动补视频只支持本地 ComfyUI 后端；线上生成按次计费，请在视频页手动提交')
    st=studio.state();submit=[];poll=[];skipped=[]
    for shot in studio.episode.get('shots',[]):
        sid=shot['id'];versions=st.get('shots',{}).get(sid) or []
        if versions and versions[-1].get('state') in ACTIVE:poll.append(sid);continue
        if any(v.get('state')=='downloaded' for v in versions):
            if versions[-1].get('review')=='revise':skipped.append((sid,'已标记需修改，请手动重做'))
            continue
        if versions:
            last=versions[-1]
            if last.get('state') in ('failed','rejected'):
                skipped.append((sid,'上次本地生成未完成（'+str(last.get('state'))+'），请查看 ComfyUI 后手动重做'));continue
            skipped.append((sid,'上次任务状态异常（'+str(last.get('state') or '未知')+'），请先核实旧任务'));continue
        if shot.get('video_deleted'):skipped.append((sid,'镜头视频已删除，已跳过'));continue
        if not studio.frame(shot,required=False).is_file():skipped.append((sid,'尚无首帧，先在'+pet_bus.stage_step('keyframe')+'生成或导入'));continue
        submit.append(sid)
    return submit,poll,skipped


def auto_batch(project,source,log=None,stop=None,studio=None):
    """无人值守本地视频（免费后端）：一轮内提交缺视频的镜头，再把在跑的镜头查询取回。

    无人值守轮询会按清单变化反复调用，所以这里不阻塞等待生成；提交失败会留下失败版本记录，
    下一轮按失败跳过，不重复提交、不重复取回，也不消耗云端额度。
    """
    log=log or (lambda text:None)
    project=Path(project);source=Path(source)
    studio=studio or open_studio(project,episode_file=source)
    submit,poll,skipped=auto_plan(project,source,studio)
    if not submit and not poll:
        return '无人值守本地视频：没有需要提交或取回的镜头'+('；'+str(len(skipped))+' 镜跳过：'+skip_summary(skipped) if skipped else '')
    url=(studio.cfg.get('local_video') or {}).get('url','http://127.0.0.1:8189')
    from native_apps import open_comfy,wait_comfy
    try:wait_comfy(url,log,timeout=5,cancelled=stop.is_set if stop is not None else None)
    except ValueError:
        log('本地 ComfyUI 未运行，正在启动…');open_comfy()
        wait_comfy(url,log,timeout=120,cancelled=stop.is_set if stop is not None else None)
    done=[];fetched=[];waiting=[];failed=[]
    for sid in submit:
        if stop is not None and stop.is_set():break
        try:
            log(sid+'：提交本地生成');studio.submit(sid,log);done.append(sid)
        except Exception as exc:
            failed.append(sid)
            try:studio.note_failure(sid,exc)
            except (OSError,ValueError,KeyError) as record:log(sid+' 失败记录未写入：'+str(record))
            log(sid+' 提交未完成：'+str(exc))
    for sid in poll:
        if stop is not None and stop.is_set():break
        try:
            text=str(studio.poll(sid));log(sid+'：'+text)
            # 按落盘后的版本状态归类，不去猜中文提示文案：生成失败要如实报失败，
            # 否则界面会一直显示「仍在生成」，看不出任务已经死掉。
            versions=studio.state().get('shots',{}).get(sid) or []
            state=versions[-1].get('state') if versions and isinstance(versions[-1],dict) else None
            if state=='downloaded':fetched.append(sid)
            elif state in ('failed','rejected'):failed.append(sid)
            else:waiting.append(sid)
        except Exception as exc:
            failed.append(sid);log(sid+' 取回未完成：'+str(exc))
    parts=[]
    if done:parts.append('已提交 '+str(len(done))+' 镜：'+_brief(done))
    if fetched:parts.append('已取回 '+str(len(fetched))+' 镜')
    if waiting:parts.append('仍在生成 '+str(len(waiting))+' 镜')
    if failed:parts.append('未完成 '+str(len(failed))+' 镜：'+_brief(failed))
    if skipped:parts.append('跳过 '+str(len(skipped))+' 镜：'+skip_summary(skipped))
    summary='无人值守本地视频：'+('；'.join(parts) or '本轮没有变化')
    if failed and not done and not fetched:raise ValueError(summary)
    return summary


def open_studio(root,episode_file=None):
    try:
        cfg=read(Path(root)/'config.json')
    except (OSError,ValueError) as exc:
        raise ValueError('项目配置文件 config.json 无法读取：'+str(exc)) from None
    if not isinstance(cfg,dict):
        raise ValueError('项目配置文件 config.json 顶层必须为对象')
    if cfg.get('video_backend','comfy')=='comfy':return LocalStudio(root,episode_file=episode_file)
    if cfg.get('cloud_provider')=='openai':
        raise ValueError('此视频服务商已移除，请在视频生成设置中选择万相或Seedance')
    if cfg.get('cloud_provider')=='volcengine':
        from agent.volcengine import VolcengineAdapter
        return Studio(root,factory=VolcengineAdapter,episode_file=episode_file)
    return Studio(root,episode_file=episode_file)

def settings_window(app):
    import tkinter as tk
    from tkinter import ttk
    from ui_dialogs import FileDialog
    win=BaseDialog(app.window,'',modal=False,chrome=False);win.attributes('-alpha',0);win.title('本地ComfyUI视频设置 · MiniMax H3');win.geometry('850x610')
    body=Card(win,padding=SPACING['lg']);body.pack(fill='both',expand=True);body.columnconfigure(1,weight=1)
    defaults={'url':'http://127.0.0.1:8189','workflow':str(Path(__file__).parent/'workflows/h3_i2v_api.json'),'prompt':'104.prompt','image':'114.image','duration':'104.length','duration_mode':'h3_frames','seed':'15.noise_seed','output':'92'}
    defaults.update(app.studio.cfg.get('local_video',{}));entries={}
    labels={'url':'本地ComfyUI地址','workflow':'API工作流','prompt':'提示词节点.字段','image':'首帧节点.字段','duration':'时长节点.字段','duration_mode':'时长格式：h3_frames / seconds','seed':'随机种子节点.字段','output':'输出视频节点ID'}
    for row,(key,label) in enumerate(labels.items()):
        ttk.Label(body,text=label).grid(row=row,column=0,padx=SPACING['md'],pady=SPACING['sm'],sticky='w');e=LineInput(body,width=CHAR_WIDTH['field_md']);e.insert(0,defaults[key]);e.grid(row=row,column=1,padx=SPACING['sm']);entries[key]=e
    def browse():
        p=FileDialog(win).open_file(initialdir=app.root/'workflows',filetypes=[('ComfyUI API JSON','*.json')])
        if p:entries['workflow'].delete(0,'end');entries['workflow'].insert(0,p)
    SecondaryButton(body,text='选择工作流',command=browse).grid(row=8,column=1,sticky='w',pady=SPACING['sm'])
    def values():return {key:e.get().strip() for key,e in entries.items()}
    def inspect():
        cfg={**app.studio.cfg,'local_video':values()}
        graph,opt=prepare_graph(app.root,cfg,app.studio.episode['shots'][0]);api=LocalAPI(opt['url']);app.run(lambda:preflight(api,graph))
    def commit():
        opts=values();cfg={**app.studio.cfg,'local_video':opts,'video_backend':'comfy'}
        LocalAPI(opts['url']);prepare_graph(app.root,cfg,{**app.studio.episode['shots'][0],'duration':5})
        publisher=getattr(__import__('stage_execution_service'), 'publish_local_video_settings')
        app.studio.cfg=publisher(app.root, app.studio.cfg, opts);win.destroy();app.refresh()
    ttk.Label(body,text='只连接本机，不读取云端API Key。H3需完整模型；无音轨视频不会通过有声QC。',wraplength=WRAPLENGTH['xl']).grid(row=9,column=0,columnspan=2,pady=SPACING['md'])
    SecondaryButton(body,text='检测节点与模型',command=lambda:app.safe(inspect)).grid(row=10,column=0,pady=SPACING['sm'])
    PrimaryButton(body,text='保存设置',command=lambda:app.safe(commit)).grid(row=10,column=1,sticky='w',pady=SPACING['sm'])
