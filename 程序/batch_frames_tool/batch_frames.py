"""Serial local FLUX Klein reference-image generation; standard library only."""
import json,uuid,hashlib,time,struct
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from agent.core import save as atomic_save, save_bytes
from contract.storyboard_paths import media_root
from urllib.parse import urlencode
from infra.comfy_service import build_reference_graph
from infra.http_client import LocalComfyClient
import contract.pet_bus as pet_bus

def read(p):
    try:return json.loads(Path(p).read_text(encoding='utf-8-sig'))
    except json.JSONDecodeError as e:raise ValueError(f'JSON格式错误：{p}\n第{e.lineno}行，第{e.colno}列：{e.msg}') from None

def load_assets(source):
    """Keep output paths relative to the shot JSON, asset paths to its registry."""
    source=Path(source).resolve()
    from agent.shot_assets import asset_rows
    return asset_rows(source)

def save(p,data):
    """首帧任务记录和分镜 JSON 统一经原子写入服务落盘。"""
    return atomic_save(p,data)
def inside(base,relative):
    p=(base/relative).resolve()
    if not p.is_relative_to(base.resolve()):raise ValueError('图片路径越出JSON目录：'+str(relative))
    return p

def graph(prompt, images, cfg, seed):
    """批量首帧工具对外提供的参考图工作流入口。"""
    return build_reference_graph(prompt, images, cfg, seed)


class Client(LocalComfyClient):
    """批量首帧的提交回执恢复保留在批处理侧。"""

    def locate_prompt(self,client_id='',workflow=None,attempts=3,wait=1.0):
        """提交响应中断后，按本次 client_id（或完全相同的图）找回已进入 ComfyUI 的任务编号。

        只认本次提交，不会误挂到别的任务；找不到返回 None，调用方据此判定没有提交成功。
        """
        for index in range(max(1,attempts)):
            entries=[]
            for path in ('/queue','/history'):
                try:data=self.request(path)
                except Exception:continue
                if not isinstance(data,dict):continue
                if path=='/queue':
                    entries.extend(data.get('queue_running',[]) or [])
                    entries.extend(data.get('queue_pending',[]) or [])
                else:
                    entries.extend(entry.get('prompt') for entry in data.values() if isinstance(entry,dict))
            for entry in entries:
                if not (isinstance(entry,list) and len(entry)>3 and entry[1]):continue
                extra=entry[3] if isinstance(entry[3],dict) else {}
                if client_id and extra.get('client_id')==client_id:return entry[1]
                if workflow is not None and entry[2]==workflow:return entry[1]
            if index<attempts-1:time.sleep(wait)
        return None


def shot_inputs(shot,base,assets):
    from asset_context import references
    from contract.prop_assets import normalize_shot
    shot=normalize_shot(shot,assets)
    ids=[value for _,value in references(shot)]
    images=[];labels=[]
    for aid in ids:
        if isinstance(aid,dict):aid=aid.get('id') or aid.get('name')
        if not isinstance(aid,str):raise ValueError('资产编号格式不正确，请先在'+pet_bus.stage_step('final')+'刷新定稿JSON')
        entry=assets.get(aid,{})
        if not entry:
            matches=[v for v in assets.values() if v.get('name')==aid or aid in v.get('aliases',[])]
            if len(matches)>1:raise ValueError('资产名称重复，请使用资产编号：'+aid)
            if len(matches)==1:entry=matches[0]
        if not entry.get('image'):entry=shot.get('asset_bindings',{}).get(aid,{})
        if not entry.get('image'):raise ValueError('缺少资产图片：'+str(aid))
        asset_base=Path(entry['_registry_base']) if '_registry_base' in entry and any(entry is v for v in assets.values()) else base
        path=inside(asset_base,entry['image'])
        if not path.is_file():raise ValueError('图片不存在：'+str(path))
        if path not in images:images.append(path);labels.append(f'Image {len(images)}: {aid}, {entry.get("name",aid)}')
    if not images:raise ValueError('没有角色或场景参考图')
    if len(images)>4:raise ValueError('此低显存方案每镜最多4张参考图，请简化镜头或提高配置后再运行')
    from keyframe_batch import frame_prompt
    description=frame_prompt(shot)
    if not description.strip():raise ValueError('镜头缺少提示词')
    prompt='Create ONE coherent animation storyboard frame. Preserve each reference identity, costume and material. Use the reference scene. No collage, no panels, no contact sheet, no subtitles. Show only the START of the action.\n'+'\n'.join(labels)+'\n'+description
    return prompt,images

def attach_prompt(client,job,client_id=''):
    """提交结果不确定时找回任务编号：先按 client_id，再按记录里的工作流比对。

    找回则写入记录并返回 True；找不到返回 False，调用方据此提示人工核实。
    """
    prompt_id=client.locate_prompt(client_id,job.get('workflow'))
    if not prompt_id:return False
    job.update(state='queued',prompt_id=prompt_id)
    return True

def preflight(source,cfg):
    source=Path(source).resolve();ep=read(source);assets=load_assets(source)
    if 'shot_ids' in cfg:
        if not cfg['shot_ids']:raise ValueError('请先勾选待生成首帧的镜头')
        if set(cfg['shot_ids'])-{s['id'] for s in ep['shots']}:raise ValueError('勾选镜头已变化，请刷新列表')
    client=Client(cfg['url']);info=client.request('/object_info')
    sample=graph('check',['reference.png'],cfg,1)
    for node in sample.values():
        kind=node['class_type']
        if kind not in info:raise ValueError('缺少ComfyUI节点：'+kind+'，请更新ComfyUI')
    for kind,field,name in [('UNETLoader','unet_name',cfg['model']),('CLIPLoader','clip_name',cfg['text_encoder']),('VAELoader','vae_name',cfg['vae'])]:
        spec=info[kind]['input']['required'][field]
        options=spec[0] if isinstance(spec[0],list) else spec[1].get('options',[])
        if name not in options:raise ValueError('ComfyUI未发现模型：'+name)
    ready=[];skipped=[]
    for shot in ep['shots']:
        sid=shot['id']
        if not isinstance(sid,str) or not __import__('re').fullmatch(r'(?:EP\d+_)?SH\d+',sid):raise ValueError('镜头编号格式无效')
        if cfg.get('shot_id') and sid!=cfg['shot_id']:continue
        if 'shot_ids' in cfg and sid not in cfg['shot_ids']:continue
        if shot.get('frame_deleted'):skipped.append(sid+'：已删除，跳过');continue
        if inside(media_root(source),shot['frame']).is_file():skipped.append(sid+'：已有首帧，跳过');continue
        try:shot_inputs(shot,media_root(source),assets);ready.append(shot)
        except ValueError as e:skipped.append(sid+'：'+str(e))
    if len({s['id'] for s in ep['shots']})!=len(ep['shots']):raise ValueError('镜头编号重复')
    return source,client,assets,ready,skipped

def run(source,cfg,log,stop):
    import msvcrt
    source=Path(source).resolve()
    with (source.parent/'batch_frames.lock').open('a+b') as lock:
        if not lock.tell():lock.write(b'0');lock.flush()
        lock.seek(0)
        try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:raise ValueError('该分镜已有批量首帧任务在运行') from None
        try:_run(source,cfg,log,stop)
        finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)

def _failed(record,job,message):
    """确定的生成失败：把记录标记为 failed，下次运行会重新提交。

    否则记录一直停在 queued，重跑只会反复查询同一个任务、反复报同一个错，
    想重做就只能手动删除记录文件。
    """
    job.update(state='failed',error=str(message))
    save(record,job)
    raise ValueError(message)

def _run(source,cfg,log,stop):
    from keyframe_evidence import source_evidence, make_evidence
    failed=0
    source,client,assets,shots,skipped=preflight(source,cfg)
    for item in skipped:log(item)
    for shot in shots:
        if stop.is_set():log('已暂停；下次运行将查询已提交任务，不重复提交。');return
        try:
            prompt,images=shot_inputs(shot,media_root(source),assets)
            generation_config={k:v for k,v in cfg.items() if k!='shot_ids'}
            signature=hashlib.sha256(json.dumps([shot,prompt,generation_config,[hashlib.sha256(p.read_bytes()).hexdigest() for p in images]],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            folder=source.parent/'首帧任务';folder.mkdir(exist_ok=True)
            record=folder/(shot['id']+'_'+signature[:16]+'.json')
            job=read(record) if record.exists() else {}
            if job.get('state')=='failed':
                log(shot['id']+'：上次生成失败，本次重新提交（'+str(job.get('error',''))[:60]+'）');job={}
            if not job:
                frozen_source=source_evidence(source,read(source),shot)
                uploaded=[client.upload(p) for p in images]
                workflow=graph(prompt,uploaded,cfg,int(signature[:12],16))
                job={'state':'submitting','source':str(source),'shot':shot['id'],'signature':signature,'workflow':workflow,
                     'source_evidence':frozen_source}
                save(record,job)
                client_id=uuid.uuid4().hex
                try:
                    result=client.request('/prompt',{'prompt':workflow,'client_id':client_id})
                    if not result.get('prompt_id'):raise ValueError('未返回任务编号')
                    job.update(state='queued',prompt_id=result['prompt_id']);save(record,job)
                except Exception:
                    if not attach_prompt(client,job,client_id):
                        job['state']='unknown';save(record,job);raise
                    save(record,job);log(shot['id']+'：提交响应中断，已按 client_id 找回任务编号')
            if not job.get('prompt_id'):
                # 旧记录停在「结果不确定」：按记录里的工作流再比对一次，能找回就继续自动取回。
                if not attach_prompt(client,job):raise ValueError(shot['id']+'提交结果不确定，请在ComfyUI核实；不会自动重复提交。')
                save(record,job);log(shot['id']+'：已按记录里的工作流找回任务编号')
            log(shot['id']+'：生成中 / 查询已有任务…')
            while True:
                if stop.is_set():log('已暂停等待；ComfyUI可能仍在生成，下次继续查询。');return
                history=client.request('/history/'+job['prompt_id']).get(job['prompt_id'])
                if history:
                    if history.get('status',{}).get('status_str')=='error':_failed(record,job,shot['id']+'生成失败，请查看ComfyUI运行日志')
                    results=history.get('outputs',{}).get('14',{}).get('images',[])
                    if results:break
                stop.wait(2)
            if len(results)!=1 or results[0].get('type')!='output':_failed(record,job,'输出节点14应输出一张图片，请检查工作流（本次输出 '+str(len(results))+' 张）')
            item=results[0];raw=client.request('/view?'+urlencode({k:item.get(k,'') for k in ('filename','subfolder','type')}),raw=True)
            if not raw.startswith(b'\x89PNG\r\n\x1a\n') or len(raw)<24:_failed(record,job,'输出不是PNG图片')
            if struct.unpack('>II',raw[16:24])!=(cfg['width'],cfg['height']):_failed(record,job,'输出尺寸不符合设置，请检查工作流宽度/高度')
            from keyframe_evidence import image_facts
            try:
                image_facts(raw)
            except ValueError as exc:
                _failed(record,job,str(exc))
            frames=media_root(source)/'frames';frames.mkdir(exist_ok=True)
            dest=frames/(shot['id']+'.png')
            if dest.exists():dest=frames/(shot['id']+'_'+uuid.uuid4().hex[:8]+'.png')
            # ComfyUI 返回的 PNG 先完成原子替换，之后才允许更新镜头索引。
            # ``dest`` 已按 UUID 避开已有成果，避免覆盖用户现有首帧。
            from contract.platform_tools import execution_checkpoint
            execution_checkpoint()
            save_bytes(dest,raw)
            latest=read(source);current=next(s for s in latest['shots'] if s['id']==shot['id'])
            if current!=shot:raise ValueError('生成期间镜头JSON已变化，图片已保存但未覆盖关联：'+str(dest))
            if not isinstance(job.get('source_evidence'),dict):_failed(record,job,'旧首帧任务缺少来源版本，图片已保留，请重新生成或导入确认：'+str(dest))
            evidence=make_evidence(source,latest,current,raw,expected_size=(cfg['width'],cfg['height']),
                                   frozen_source=job['source_evidence'])
            current['frame']=dest.relative_to(media_root(source)).as_posix()
            current['frame_evidence']=evidence
            backup=folder/(source.stem+'_before_'+uuid.uuid4().hex[:8]+'.json');save_bytes(backup,source.read_bytes())
            execution_checkpoint()
            save(source,latest);job.update(state='downloaded',file=str(dest));save(record,job)
            log(shot['id']+'：已保存并关联 '+dest.name)
        except Exception as exc:
            failed+=1;log(shot['id']+'：失败：'+str(exc))
            continue
    log('批量任务结束；跳过项请补齐资产后再运行。'
        +('失败 '+str(failed)+' 镜，记录已标记 failed，可再次运行重新生成这些镜头。' if failed else ''))
