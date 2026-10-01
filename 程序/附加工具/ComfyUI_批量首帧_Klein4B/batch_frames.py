"""Serial local FLUX Klein reference-image generation; standard library only."""
import json,os,uuid,hashlib,struct
from pathlib import Path
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.parse import urlparse,urlencode

def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def _temporary_path(p):
    p=Path(p)
    return p.with_name('.'+p.name+'.'+uuid.uuid4().hex+'.tmp')
def save(p,data):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    temp=_temporary_path(p)
    try:
        payload=json.dumps(data,ensure_ascii=False,indent=2)
        json.loads(payload)
        temp.write_text(payload,encoding='utf-8')
        read(temp)
        temp.replace(p)
    finally:
        temp.unlink(missing_ok=True)
def save_bytes(p,payload):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    temp=_temporary_path(p);payload=bytes(payload)
    try:
        temp.write_bytes(payload)
        if temp.stat().st_size!=len(payload):raise OSError('临时备份文件写入不完整')
        temp.replace(p)
    finally:
        temp.unlink(missing_ok=True)
def save_bytes_new(p,payload):
    """发布新 PNG；同名文件存在时安全失败，不能覆盖既有用户首帧。"""
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    temp=_temporary_path(p);payload=bytes(payload)
    try:
        temp.write_bytes(payload)
        if temp.stat().st_size!=len(payload):raise OSError('临时图片写入不完整')
        os.link(temp,p)
    finally:
        temp.unlink(missing_ok=True)
def inside(base,relative):
    p=(base/relative).resolve()
    if not p.is_relative_to(base.resolve()):raise ValueError('图片路径越出JSON目录：'+str(relative))
    return p

def graph(prompt,images,cfg,seed):
    g={}
    def node(i,kind,**inputs):g[str(i)]={'class_type':kind,'inputs':inputs};return [str(i),0]
    model=node(1,'UNETLoader',unet_name=cfg['model'],weight_dtype='default')
    clip=node(2,'CLIPLoader',clip_name=cfg['text_encoder'],type='flux2',device='default')
    vae=node(3,'VAELoader',vae_name=cfg['vae'])
    positive=node(4,'CLIPTextEncode',clip=clip,text=prompt)
    negative=node(5,'ConditioningZeroOut',conditioning=positive)
    for index,name in enumerate(images):
        i=100+index*5
        image=node(i,'LoadImage',image=name)
        image=node(i+1,'ImageScaleToTotalPixels',image=image,upscale_method='area',megapixels=.5,resolution_steps=16)
        latent=node(i+2,'VAEEncode',pixels=image,vae=vae)
        positive=node(i+3,'ReferenceLatent',conditioning=positive,latent=latent)
        negative=node(i+4,'ReferenceLatent',conditioning=negative,latent=latent)
    latent=node(6,'EmptyFlux2LatentImage',width=cfg['width'],height=cfg['height'],batch_size=1)
    guider=node(7,'CFGGuider',model=model,positive=positive,negative=negative,cfg=1.0)
    noise=node(8,'RandomNoise',noise_seed=seed)
    sampler=node(10,'KSamplerSelect',sampler_name='euler')
    sigmas=node(11,'Flux2Scheduler',steps=4,width=cfg['width'],height=cfg['height'])
    samples=node(12,'SamplerCustomAdvanced',noise=noise,guider=guider,sampler=sampler,sigmas=sigmas,latent_image=latent)
    image=node(13,'VAEDecode',samples=samples,vae=vae)
    node(14,'SaveImage',images=image,filename_prefix='DramaFrames/'+str(seed))
    return g

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError('拒绝接口跳转')

class Client:
    def __init__(self,url):
        p=urlparse(url)
        if p.scheme!='http' or p.hostname not in ('127.0.0.1','localhost','::1') or p.username or p.password:raise ValueError('仅支持本机ComfyUI地址')
        self.url=url.rstrip('/');self.opener=build_opener(NoRedirect)
    def request(self,path,data=None,raw=False,content_type='application/json'):
        if isinstance(data,dict):data=json.dumps(data).encode()
        with self.opener.open(Request(self.url+path,data=data,headers={'Content-Type':content_type}),timeout=30) as r:
            body=r.read(64*1024*1024+1)
        if len(body)>64*1024*1024:raise ValueError('返回文件超过64MB')
        return body if raw else json.loads(body)
    def upload(self,path):
        content=path.read_bytes()
        if len(content)>20*1024*1024:raise ValueError('参考图超过20MB：'+path.name)
        boundary=uuid.uuid4().hex;name='drama_'+uuid.uuid4().hex+path.suffix.lower()
        body=(f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{name}"\r\nContent-Type: application/octet-stream\r\n\r\n').encode()+content+f'\r\n--{boundary}--\r\n'.encode()
        result=self.request('/upload/image',body,content_type='multipart/form-data; boundary='+boundary)
        return '/'.join(x for x in (result.get('subfolder'),result['name']) if x)

def shot_inputs(shot,base,assets):
    ids=list(shot.get('characters',[]))+([shot['location']] if shot.get('location') else [])+list(shot.get('props',[]))
    images=[];labels=[]
    for aid in ids:
        entry=assets.get(aid,{})
        if not entry.get('image'):entry=shot.get('asset_bindings',{}).get(aid,{})
        if not entry.get('image'):raise ValueError('缺少资产图片：'+str(aid))
        path=inside(base,entry['image'])
        if not path.is_file():raise ValueError('图片不存在：'+str(path))
        if path not in images:images.append(path);labels.append(f'Image {len(images)}: {aid}, {entry.get("name",aid)}')
    if not images:raise ValueError('没有角色或场景参考图')
    if len(images)>4:raise ValueError('此低显存方案每镜最多4张参考图，请简化镜头或提高配置后再运行')
    description=shot.get('keyframe_prompt') or shot.get('video_prompt','')
    if not description.strip():raise ValueError('镜头缺少提示词')
    prompt='Create ONE coherent animation storyboard frame. Preserve each reference identity, costume and material. Use the reference scene. No collage, no panels, no contact sheet, no subtitles. Show only the START of the action.\n'+'\n'.join(labels)+'\n'+description
    return prompt,images

def preflight(source,cfg):
    source=Path(source).resolve();ep=read(source);assets=read(source.parent/'assets.json')
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
        if shot.get('frame_deleted'):skipped.append(sid+'：已删除，跳过');continue
        if inside(source.parent,shot['frame']).is_file():skipped.append(sid+'：已有首帧，跳过');continue
        try:shot_inputs(shot,source.parent,assets);ready.append(shot)
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

def _run(source,cfg,log,stop):
    source,client,assets,shots,skipped=preflight(source,cfg)
    for item in skipped:log(item)
    for shot in shots:
        if stop.is_set():log('已暂停；下次运行将查询已提交任务，不重复提交。');return
        prompt,images=shot_inputs(shot,source.parent,assets)
        signature=hashlib.sha256(json.dumps([shot,prompt,cfg,[hashlib.sha256(p.read_bytes()).hexdigest() for p in images]],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        folder=source.parent/'首帧任务';folder.mkdir(exist_ok=True)
        record=folder/(shot['id']+'_'+signature[:16]+'.json')
        job=read(record) if record.exists() else {}
        if not job:
            uploaded=[client.upload(p) for p in images]
            workflow=graph(prompt,uploaded,cfg,int(signature[:12],16))
            job={'state':'submitting','source':str(source),'shot':shot['id'],'signature':signature,'workflow':workflow}
            save(record,job)
            try:
                result=client.request('/prompt',{'prompt':workflow,'client_id':uuid.uuid4().hex})
                if not result.get('prompt_id'):raise ValueError('未返回任务编号')
                job.update(state='queued',prompt_id=result['prompt_id']);save(record,job)
            except Exception:
                job['state']='unknown';save(record,job);raise
        if not job.get('prompt_id'):raise ValueError(shot['id']+'提交结果不确定，请在ComfyUI核实；不会自动重复提交。')
        log(shot['id']+'：生成中 / 查询已有任务…')
        while True:
            if stop.is_set():log('已暂停等待；ComfyUI可能仍在生成，下次继续查询。');return
            history=client.request('/history/'+job['prompt_id']).get(job['prompt_id'])
            if history:
                if history.get('status',{}).get('status_str')=='error':raise ValueError(shot['id']+'生成失败，请查看ComfyUI；不会自动重做')
                results=history.get('outputs',{}).get('14',{}).get('images',[])
                if results:break
            stop.wait(2)
        if len(results)!=1 or results[0].get('type')!='output':raise ValueError('预期一张输出图片')
        item=results[0];raw=client.request('/view?'+urlencode({k:item.get(k,'') for k in ('filename','subfolder','type')}),raw=True)
        if not raw.startswith(b'\x89PNG\r\n\x1a\n') or len(raw)<24:raise ValueError('输出不是PNG')
        if struct.unpack('>II',raw[16:24])!=(cfg['width'],cfg['height']):raise ValueError('输出尺寸不符合设置')
        frames=source.parent/'frames';frames.mkdir(exist_ok=True)
        dest=frames/(shot['id']+'.png')
        if dest.exists():dest=frames/(shot['id']+'_'+uuid.uuid4().hex[:8]+'.png')
        save_bytes_new(dest,raw)
        latest=read(source);current=next(s for s in latest['shots'] if s['id']==shot['id'])
        if current!=shot:raise ValueError('生成期间镜头JSON已变化，图片已保存但未覆盖关联：'+str(dest))
        current['frame']=dest.relative_to(source.parent).as_posix()
        backup=folder/(source.stem+'_before_'+uuid.uuid4().hex[:8]+'.json');save_bytes(backup,source.read_bytes())
        save(source,latest);job.update(state='downloaded',file=str(dest));save(record,job)
        log(shot['id']+'：已保存并关联 '+dest.name)
    log('批量任务结束；跳过项请补齐资产后再运行。')
