"""Import only complete, manifest-bound first frames into the matching shots."""
from pathlib import Path
import hashlib, json, re, time, uuid, shutil
from datetime import datetime
import tk_timers
from agent.core import read,save,save_bytes_new
from agent.media import png_complete
from file_cache import read_json
from contract.storyboard_paths import media_root

def fingerprint(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()

def pending_tasks(project,source):
    """未导入的首帧任务：镜头编号 -> 批次清单。用于判断能否重新提交。"""
    source=Path(source).resolve();pending={}
    for manifest in (Path(project)/'workflows/首帧批次').glob('*/批次.json'):
        try:data=read(manifest)
        except (OSError,ValueError):continue
        if not isinstance(data,dict) or not data.get('source'):continue
        if Path(str(data['source'])).resolve()!=source:continue
        items=data.get('items')
        if not isinstance(items,list):continue
        for item in items:
            if isinstance(item,dict) and item.get('state')=='pending' and item.get('shot_id'):pending[item['shot_id']]=manifest
    return pending

def abandon_tasks(pending):
    """放弃指定镜头的未完成任务，让它们可以重新提交；批次文件保留为记录。"""
    changed=set()
    for manifest in {manifest for manifest in pending.values()}:
        try:data=read(manifest)
        except (OSError,ValueError):continue
        items=data.get('items') if isinstance(data,dict) else None
        if not isinstance(items,list):continue
        dirty=False
        for item in items:
            if not isinstance(item,dict) or item.get('state')!='pending':continue
            if item.get('shot_id') not in pending or pending[item['shot_id']]!=manifest:continue
            item.update(state='cancelled',cancelled_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'));dirty=True
        if dirty:save(manifest,data);changed.add(manifest)
    return changed

def publish_frame_reference(source,base,item,dest):
    """为已独占发布的首帧原子更新分镜关联；失败时保留新图供用户恢复。"""
    source=Path(source).resolve();base=Path(base).resolve();dest=Path(dest).resolve()
    sid=item['shot_id']
    if not dest.is_relative_to(base) or not dest.is_file():raise ValueError('首帧尚未安全发布')
    latest=read(source);current=next((s for s in latest['shots'] if s['id']==sid),None)
    if not current or fingerprint(current)!=item['shot_signature']:raise ValueError('镜头刚被修改，生成图已保留，未更新关联')
    from domain.keyframe_evidence import make_evidence
    if not isinstance(item.get('source_evidence'), dict):
        raise ValueError('旧首帧任务缺少来源版本，生成图已保留，请通过导入首帧确认')
    evidence=make_evidence(source,latest,current,dest,frozen_source=item['source_evidence'],
                           expected_size=item.get('expected_size'),aspect_ratio=item.get('aspect_ratio'))
    history=source.parent/'历史版本/首帧导入'
    if not history.resolve().is_relative_to(source.parent):raise ValueError('备份路径越出当前分镜目录')
    history.mkdir(parents=True,exist_ok=True);shutil.copy2(source,history/(source.stem+'_'+uuid.uuid4().hex[:8]+'.json'))
    current['frame']=dest.relative_to(base).as_posix();current['frame_evidence']=evidence;save(source,latest)
    return dest

def register(source,item,image):
    source=Path(source).resolve();base=media_root(source).resolve();episode=read(source)
    sid=item['shot_id']
    if not re.fullmatch(r'(?:EP\d+_)?SH\d+',sid):raise ValueError('镜头编号格式无效')
    matches=[shot for shot in episode['shots'] if shot['id']==sid]
    if len(matches)!=1:raise ValueError('镜头已删除或编号重复，生成图已保留')
    shot=matches[0]
    if fingerprint(shot)!=item['shot_signature']:raise ValueError('生成期间镜头已修改，生成图已保留，未覆盖首帧关联')
    target=(base/shot['frame']).resolve()
    if not target.is_relative_to(base):raise ValueError('首帧路径越出素材目录')
    if shot.get('frame_deleted') or target.is_file():raise ValueError('此镜头已删除或已有首帧，生成图已保留，未覆盖')
    raw=Path(image).read_bytes()
    if len(raw)<33 or not raw.startswith(b'\x89PNG\r\n\x1a\n') or raw[12:16]!=b'IHDR' or raw[-8:-4]!=b'IEND':raise ValueError('PNG首帧尚未保存完整')
    from domain.keyframe_evidence import make_evidence
    make_evidence(source,episode,shot,raw,frozen_source=item.get('source_evidence'),
                  expected_size=item.get('expected_size'),aspect_ratio=item.get('aspect_ratio'))
    folder=base/'frames'
    if not folder.resolve().is_relative_to(base):raise ValueError('首帧目录越出素材目录')
    folder.mkdir(exist_ok=True)
    from contract.file_naming import generate_existing
    dest=folder/generate_existing('keyframe', episode_id=episode.get('episode_id', ''),
                                  shot_id=sid, token=uuid.uuid4().hex[:8], suffix='.png')
    # Unique filenames also isolate episodes that reuse SH001 etc.; the final
    # publish remains exclusive so a collision can never overwrite a frame.
    save_bytes_new(dest,raw)
    return publish_frame_reference(source,base,item,dest)

def stale_tasks(project,source,agent_running=False,limit=300):
    """可以自动放弃的未完成首帧任务：没有执行记录、没有产出、Agent 也没在跑，且已超过等待时间。

    有执行记录（Agent 真跑过）或已经产出图片的批次必须保留：前者可能仍在生成，后者正等自动导入。
    """
    from domain.asset_batch_lifecycle import status as lifecycle
    from stage_execution_service import asset_batch_gateway
    gateway=asset_batch_gateway()
    now=time.time();stale={}
    for sid,manifest in pending_tasks(project,source).items():
        try:data=read(manifest);info=lifecycle(manifest,gateway=gateway)
        except (OSError,ValueError):continue
        if agent_running:continue
        items=data.get('items') if isinstance(data,dict) else None
        if not isinstance(items,list):continue
        if any((manifest.parent/item['output']).is_file() for item in items
               if isinstance(item,dict) and item.get('state')=='pending' and item.get('output')):continue
        state=info.get('state')
        if state=='failed' or (state=='legacy' and now-info.get('created',now)>limit):stale[sid]=manifest
    return stale

def clear_stale_tasks(app,project,source,blocked,waiting):
    """自动放弃没有执行记录的旧任务，返回仍需用户确认的镜头编号。"""
    if not blocked:return []
    sessions=getattr(app,'flow_processes',{})
    agent_running=any(key[:2]==(str(project),'assets') and process.poll() is None for key,process in sessions.items())
    stale=stale_tasks(project,source,agent_running=agent_running)
    auto=[sid for sid in blocked if sid in stale]
    if auto:
        abandon_tasks({sid:waiting[sid] for sid in auto})
        status=getattr(app,'status',None)
        if status is not None:status.set('已自动放弃没有执行记录的首帧任务：'+'、'.join(auto)+'；本次重新提交这些镜头。')
    return [sid for sid in blocked if sid not in stale]

def launch(app,source,shot_id=None,shot_ids=None):
    from domain.keyframe_batch import candidates,frame_prompt
    from stage_execution_service import keyframe_image_prompt
    from orchestrator.workflow_settings import current
    source=Path(source).resolve();project=Path(app.root).resolve()
    if not source.is_relative_to(project):raise ValueError('请选择当前项目的镜头JSON')
    shots=candidates(source,shot_id,shot_ids)
    waiting=pending_tasks(project,source)
    blocked=sorted(shot['id'] for shot in shots if shot['id'] in waiting)
    blocked=clear_stale_tasks(app,project,source,blocked,waiting)
    if blocked:
        from ui_widgets import ask_confirmation
        if not ask_confirmation(app.win, '已有未完成的首帧任务',
                '这些镜头还有上次未完成的首帧任务：\n'+'、'.join(blocked)+'\n\n'
                '如果上次的 Agent 窗口已经关闭、不再继续，可以放弃旧任务并重新提交。\n'
                '点“确认”放弃旧任务并重新提交；点“取消”保留旧任务，等待自动导入。',dangerous=True):
            app.status.set('已保留上次未完成的首帧任务；需要重做时再点一次并选择“放弃旧任务”。')
            return False
        abandon_tasks({sid:waiting[sid] for sid in blocked})
    shot_ids=[shot['id'] for shot in shots]
    if shot_id and not frame_prompt(shots[0]):raise ValueError('当前镜头缺少首帧图片提示词，请先在分镜JSON中补齐frame_prompt')
    if current(app.root,'assets')['engine']=='qwen':
        if not app.launch_comfy(silent=True):return                 # 第 62 期任务 8：静默拉起，不弹选择框
    folder=project/'workflows/首帧批次'/uuid.uuid4().hex[:12];folder.mkdir(parents=True)
    from domain.keyframe_evidence import source_evidence
    episode=read(source)
    items=[{'shot_id':shot['id'],'shot_signature':fingerprint(shot),'output':shot['id']+'.png','state':'pending',
            'source_evidence':source_evidence(source,episode,shot)} for shot in shots]
    # Validate IDs before constructing any output path.
    if any(not re.fullmatch(r'(?:EP\d+_)?SH\d+',item['shot_id']) for item in items):raise ValueError('镜头编号格式无效')
    manifest=folder/'批次.json';save(manifest,{'source':str(source),'items':items})
    outputs={item['shot_id']:folder/item['output'] for item in items}
    task=keyframe_image_prompt(project,source,shot_id,outputs,shot_ids=shot_ids)
    if current(app.root,'assets')['engine']=='qwen':
        from image_agent_runner import task_instruction
        config_file=Path(__file__).parent/'batch_frames_tool/config.json'
        cfg=read(config_file)
        if not cfg.get('api_settings_saved'):cfg['url']=app.settings.get('comfy_url',cfg['url'])
        payload=read(manifest);payload['comfy_config']=cfg;save(manifest,payload)
        task+='\n'+task_instruction(project,manifest)
    if current(app.root,'assets')['engine']=='qwen':app.open_direct_flow_agent('assets','资产管理',task,{'image':manifest})   # REQ-S08-52
    else:app.open_flow_agent('assets','资产管理',task)
    watch(app,manifest)
    return True

def watch(app,manifest):
    manifest=Path(manifest);watched=getattr(app,'keyframe_import_watchers',set());key=str(manifest)
    if key in watched:return
    watched.add(key);app.keyframe_import_watchers=watched;stable={}
    def tick():
        try:
            data=read(manifest)
            if not isinstance(data,dict) or not isinstance(data.get('items'),list):stop();return
            items=data['items'];dirty=False
            for item in items:
                if item['state']!='pending':continue
                image=(manifest.parent/item['output']).resolve()
                if image.parent!=manifest.parent.resolve() or not image.is_file():continue
                mark=(image.stat().st_size,image.stat().st_mtime_ns)
                if stable.get(item['shot_id'])!=mark:stable[item['shot_id']]=mark;continue
                # An unfinished file can pause for a while; retry until PNG is complete.
                # 只读头尾判断：这个循环每 1.5 秒检查一次，整图读进来既慢又占内存。
                if not png_complete(image):continue
                try:
                    dest=register(data['source'],item,image);item.update(state='imported',file=str(dest));dirty=True
                    app.status.set(item['shot_id']+' 首帧已自动导入')
                except (OSError,ValueError,KeyError) as exc:item.update(state='failed',error=str(exc));dirty=True
            if dirty:save(manifest,data)
            if not any(item['state']=='pending' for item in items):watched.discard(key);stop();return
        except (OSError,ValueError,KeyError):pass
    # 定时器随主窗口销毁一起取消：残留的 after 回调会在退出后报 invalid command name。
    stop=tk_timers.repeat(app.win,1500,tick)

def resume(app):
    for manifest in (Path(app.root)/'workflows/首帧批次').glob('*/批次.json'):
        try:
            data=read(manifest)
            if isinstance(data,dict) and any(item.get('state')=='pending' for item in data.get('items',[]) if isinstance(item,dict)):watch(app,manifest)
        except (OSError,ValueError,KeyError):continue

def watch_list(owner,source,refresh,interval=1500):
    """Refresh on JSON or image completion for both Agent and ComfyUI outputs."""
    source=Path(source);base=media_root(source)
    def snapshot():
        stat=source.stat();result=[(str(source),stat.st_mtime_ns,stat.st_size)]
        for shot in read_json(source).get('shots',[]):
            file=(base/shot['frame']).resolve()
            if file.is_relative_to(base) and file.is_file():
                stat=file.stat();result.append((str(file),stat.st_mtime_ns,stat.st_size))
        return tuple(result)
    return tk_timers.watch_changes(owner,snapshot,refresh,interval)
