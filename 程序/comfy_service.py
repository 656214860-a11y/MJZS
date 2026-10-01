"""Local ComfyUI API workflow execution; no cloud video requests."""
import json, time, uuid
from pathlib import Path
from urllib.parse import urlparse, urlencode
# 第 34 期第 9 条：`urllib.request`／`urllib.error` 连 ssl 一起加载（约 4.4 MB 常驻），
# 本模块只在真要连本机 ComfyUI 时用得到——都改成函数内 import。
from agent.core import save, read, save_bytes

class ComfyGenerationFailed(ValueError):
    pass

class ComfySubmissionUncertain(RuntimeError):
    pass

def validate_safetensors(path):
    """校验 .safetensors 头部的张量表；LoRA 等模型文件送入 ComfyUI 之前先过这道关。"""
    with Path(path).open('rb') as f:
        size=int.from_bytes(f.read(8),'little')
        if not 2<=size<=16*1024**2:raise ValueError('不是有效safetensors文件，可能下载到了网页')
        header=json.loads(f.read(size));tensors=[v for k,v in header.items() if k!='__metadata__']
        if not tensors or not all(isinstance(v,dict) and 'data_offsets' in v for v in tensors):raise ValueError('文件缺少模型张量')

def locate_prompt(fetch,client_id='',workflow=None,attempts=3,wait=1.0):
    """提交响应中断后，按本次提交的 client_id（或完全相同的图）找回任务编号。

    fetch(path) 返回队列/历史接口的 JSON。只认本次提交的 client_id，或与本次完全相同的图，
    不会误挂到别的任务上；找不到返回 None，调用方据此判定本次确实没有提交成功。
    """
    for index in range(max(1,attempts)):
        entries=[]
        for path in ('/queue','/history'):
            try:data=fetch(path)
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

class Comfy:
    def __init__(self,url):
        self.url=url.rstrip('/');p=urlparse(self.url)
        if p.scheme!='http' or p.hostname not in ('localhost','127.0.0.1','::1'):raise ValueError('请输入本机ComfyUI地址，例如 http://127.0.0.1:8189')
    def request(self,path,data=None,raw=False,timeout=20):
        from urllib.request import Request, urlopen      # 第 34 期第 9 条：HTTP 栈按需加载
        body=None if data is None else json.dumps(data).encode()
        with urlopen(Request(self.url+path,data=body,headers={'Content-Type':'application/json'}),timeout=timeout) as r:b=r.read()
        return b if raw else json.loads(b)
    def models(self):
        info=self.request('/object_info/CheckpointLoaderSimple')
        node=info.get('CheckpointLoaderSimple',{})
        fields=node.get('input',{}).get('required',{})
        choices=fields.get('ckpt_name',[])
        return choices[0] if choices and isinstance(choices[0],list) else []
    def submit(self,root,kind,prompt,model,workflow=None,node='6',field='text',lora=None):
        if kind not in ('characters','scenes','props'):raise ValueError('无效资产类别')
        if not prompt.strip():raise ValueError('请填写图片提示词')
        if workflow:
            graph=read(workflow)
            if not graph or not all(isinstance(v,dict) and 'class_type' in v for v in graph.values()):raise ValueError('请选择API格式工作流，不能使用画布JSON')
            if node not in graph or field not in graph[node].get('inputs',{}):raise ValueError('提示词节点编号或字段不匹配')
            graph[node]['inputs'][field]=prompt
        else:
            if not model:raise ValueError('先检测连接并选择已安装模型，或选择API工作流')
            graph={'4':{'class_type':'CheckpointLoaderSimple','inputs':{'ckpt_name':model}},'5':{'class_type':'EmptyLatentImage','inputs':{'width':512 if kind=='characters' else 768,'height':512,'batch_size':1}},'6':{'class_type':'CLIPTextEncode','inputs':{'text':prompt,'clip':['4',1]}},'7':{'class_type':'CLIPTextEncode','inputs':{'text':'text, watermark, blurry','clip':['4',1]}},'3':{'class_type':'KSampler','inputs':{'seed':int(uuid.uuid4().hex[:8],16),'steps':20,'cfg':7,'sampler_name':'euler','scheduler':'normal','denoise':1,'model':['4',0],'positive':['6',0],'negative':['7',0],'latent_image':['5',0]}},'8':{'class_type':'VAEDecode','inputs':{'samples':['3',0],'vae':['4',2]}},'9':{'class_type':'SaveImage','inputs':{'images':['8',0],'filename_prefix':'DramaAssets'}}}
        if lora:
            if workflow:
                loaders=[v for v in graph.values() if 'lora_name' in v.get('inputs',{})]
                if len(loaders)!=1:raise ValueError('自定义工作流必须有且只有一个LoRA加载节点；请在ComfyUI调整后重试')
                loaders[0]['inputs']['lora_name']=lora
            else:
                graph['20']={'class_type':'LoraLoader','inputs':{'model':['4',0],'clip':['4',1],'lora_name':lora,'strength_model':0.8,'strength_clip':0.8}}
                graph['3']['inputs']['model']=['20',0]
                graph['6']['inputs']['clip']=['20',1];graph['7']['inputs']['clip']=['20',1]
        return self.submit_graph(root,kind,prompt,graph)

    def reference_config(self):
        from batch_frames_tool.batch_frames import graph
        cfg=read(Path(__file__).parent/'batch_frames_tool/config.json')
        cfg.update(width=768,height=768)
        info=self.request('/object_info')
        for item in graph('check',['reference.png'],cfg,1).values():
            if item['class_type'] not in info:raise ValueError('参考图工作流缺少节点：'+item['class_type'])
        for kind,field,key in [('UNETLoader','unet_name','model'),('CLIPLoader','clip_name','text_encoder'),('VAELoader','vae_name','vae')]:
            spec=info[kind]['input']['required'][field]
            choices=spec[0] if isinstance(spec[0],list) else spec[1].get('options',[])
            if cfg[key] not in choices:raise ValueError('参考图工作流缺少模型：'+cfg[key])
        return cfg

    def reference_graph(self,prompt,images,cfg):
        from batch_frames_tool.batch_frames import Client,graph
        upload=Client(self.url)
        names=[upload.upload(Path(path)) for path in images]
        task='按提示词中每张参考图的用途生成资产图；长相、服饰、画风、色调、氛围分别参考，不把风格参考中的人物身份或服装混入当前角色。\n'+prompt
        workflow=graph(task,names,cfg,int(uuid.uuid4().hex[:12],16))
        workflow['14']['inputs']['filename_prefix']='DramaAssets/reference_'+uuid.uuid4().hex[:10]
        return workflow

    def locate_prompt(self,client_id,attempts=3,wait=1.0):
        """提交响应中断后，按本次 client_id 在队列与历史里找回任务编号。"""
        return locate_prompt(lambda path:self.request(path,timeout=5),client_id,attempts=attempts,wait=wait)

    def submit_graph(self,root,kind,prompt,graph,extra_data=None):
        from urllib.error import HTTPError                # 第 34 期第 9 条：HTTP 栈按需加载
        if kind not in ('characters','scenes','props'):raise ValueError('无效资产类别')
        folder=Path(root)/'workflows';folder.mkdir(exist_ok=True)
        rec=folder/('comfy_'+uuid.uuid4().hex[:10]+'.json')
        job={'state':'submitting','kind':kind,'prompt':prompt,'workflow':graph};save(rec,job)
        client_id=uuid.uuid4().hex
        try:
            payload={'prompt':graph,'client_id':client_id}
            if extra_data:payload['extra_data']=extra_data
            result=self.request('/prompt',payload)
            if not result.get('prompt_id'):raise ValueError('ComfyUI没有返回任务编号')
            job.update(state='queued',prompt_id=result['prompt_id']);save(rec,job)
        except HTTPError as exc:
            # A definite HTTP rejection is safe to fix and resubmit. Network
            # timeouts remain unknown so they cannot trigger duplicate charges.
            job['state']='failed' if 400<=exc.code<500 else 'unknown';save(rec,job)
            if job['state']=='failed':raise ComfyGenerationFailed('ComfyUI 拒绝提交（HTTP '+str(exc.code)+'），请检查节点参数或账户配置') from None
            raise
        except Exception as exc:
            # 提交响应可能只是超时或断连，任务其实已经进了 ComfyUI：先按 client_id 找回，
            # 找回后照常排队生成；确认队列与历史里都没有本次任务，才判定提交结果不确定。
            prompt_id=self.locate_prompt(client_id)
            if prompt_id:
                job.update(state='queued',prompt_id=prompt_id,note='提交响应中断，已按 client_id 找回任务编号');save(rec,job)
                return rec
            job['state']='unknown';save(rec,job)
            error=ComfySubmissionUncertain('提交结果不确定，请在本地 ComfyUI 核实任务；未自动重复提交')
            error.record=str(rec)
            raise error from exc
        return rec
    def collect(self,root,record):
        if not Path(record).resolve().is_relative_to((Path(root)/'workflows').resolve()):raise ValueError('请选择当前项目内的ComfyUI任务')
        job=read(record)
        if job.get('kind') not in ('characters','scenes','props'):raise ValueError('无效资产类别')
        if job.get('state')=='downloaded':return job['files']
        if not job.get('prompt_id'):raise ValueError('提交结果不确定，请在ComfyUI核实任务；不会自动重新提交')
        h=self.request('/history/'+job['prompt_id']).get(job['prompt_id'])
        if not h:return '排队或生成中，稍后再获取'
        if h.get('status',{}).get('status_str')=='error':
            error='ComfyUI 生成失败，请打开本地 ComfyUI 查看详情'
            for kind,data in h.get('status',{}).get('messages',[]):
                if kind=='execution_error':error=str(data.get('exception_message',error))[:450]
            job.update(state='failed',error=error);save(record,job)
            raise ComfyGenerationFailed(error)
        # 第 64 期任务 1：取回的原始图落进 workflows/Comfy资产批次/ 这个暂存目录，不再直接写进
        # 资产库（episode/assets/<类别>）。登记（asset_batch.register_image）会把图复制进资产库并
        # 命名成「编号_名称_哈希.png」——原来留在资产库里的那份 comfy_xxx_1.png 就是用户报的重复项。
        files=[];out=Path(root)/'workflows/Comfy资产批次';out.mkdir(parents=True,exist_ok=True)
        for node,result in h.get('outputs',{}).items():
            for item in result.get('images',[]):
                if item.get('type')!='output':continue
                raw=self.request('/view?'+urlencode({k:item.get(k,'') for k in ('filename','subfolder','type')}),raw=True)
                if not raw.startswith(b'\x89PNG\r\n\x1a\n'):
                    # 任务已执行完但产出不可用：属确定的生成失败，标记记录失败以便重新提交；
                    # 否则记录一直停在 queued，每次取回都报同一个错、永远没有进展。
                    job.update(state='failed',error='工作流输出须为PNG图片');save(record,job)
                    raise ComfyGenerationFailed('工作流输出须为PNG图片')
                dest=out/(Path(record).stem+'_'+str(len(files)+1)+'.png');save_bytes(dest,raw);files.append(str(dest))
        if not files:
            job.update(state='failed',error='工作流没有输出图片，请检查SaveImage节点');save(record,job)
            raise ComfyGenerationFailed('工作流没有输出图片，请检查SaveImage节点')
        job.update(state='downloaded',files=files);save(record,job);return files
