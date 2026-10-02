"""Track Agent dispatch separately from image output; recover unsubmitted legacy batches."""
import time
from pathlib import Path
def _require_gateway(gateway):
    """Batch dispatch records are formal project data and require L3 I/O."""
    required = ('read_json', 'publish_json')
    if not isinstance(gateway, dict) or any(not callable(gateway.get(name)) for name in required):
        raise TypeError('资产批次状态读写需要由 L3 注入发布与读取网关。')
    return gateway


def status(manifest, *, gateway=None):
    gateway = _require_gateway(gateway)
    manifest=Path(manifest)
    execution=manifest.parent/'执行状态.json'
    if execution.is_file():
        data=gateway['read_json'](execution)
        return data if isinstance(data,dict) else {'state':'legacy','created':manifest.stat().st_mtime}
    dispatch=manifest.parent/'派发状态.json'
    if dispatch.is_file():
        data=gateway['read_json'](dispatch)
        if not isinstance(data,dict):return {'state':'legacy','created':manifest.stat().st_mtime}
        receipt=Path(data['receipt']) if data.get('receipt') else None
        if receipt and receipt.is_file():
            result=gateway['read_json'](receipt)
            return {'state':result.get('state','preparing'),'message':result.get('reason','')}
        if data.get('state')=='preparing' and time.time()-data.get('created',time.time())>300:
            return {'state':'failed','message':'Agent 派发未完成，可重新启动本批次。'}
        return data
    return {'state':'legacy','created':manifest.stat().st_mtime}


def prepare(manifest, *, gateway=None):
    gateway = _require_gateway(gateway)
    gateway['publish_json'](Path(manifest).parent/'派发状态.json',{'state':'preparing','created':time.time()})


def attach(manifest,receipt, *, gateway=None):
    gateway = _require_gateway(gateway)
    gateway['publish_json'](Path(manifest).parent/'派发状态.json',{'state':'preparing','receipt':receipt['record'],'created':time.time()})


def fail(manifest,message, *, gateway=None):
    gateway = _require_gateway(gateway)
    gateway['publish_json'](Path(manifest).parent/'执行状态.json',{'state':'failed','message':str(message),'updated':time.time()})


def reconcile(project,base,selected,agent_running=False, *, gateway=None):
    """Return only batches with output or evidence of a real dispatch/submission."""
    gateway = _require_gateway(gateway)
    project=Path(project);base=Path(base).resolve();selected=set(selected)
    ledger=project/'workflows/资产批量记录.json'
    jobs=gateway['read_json'](ledger) if ledger.is_file() else {}
    if not isinstance(jobs,dict):jobs={}
    pending={}
    for manifest in (project/'workflows/Imagen资产批次').glob('*/批次.json'):
        data=gateway['read_json'](manifest)
        if not isinstance(data,dict):continue
        if Path(data.get('base','')).resolve()!=base:continue
        state=status(manifest, gateway=gateway);changed=False
        items=data.get('assets',[])
        if not isinstance(items,list):items=[]
        for item in items:
            aid=item['id']
            if aid not in selected or item.get('state')!='pending':continue
            output=manifest.parent/item['output']
            if output.is_file():pending[aid]=manifest;continue
            job=jobs.get(aid,{})
            submitted=bool(job.get('record') or job.get('state') in ('submitting','queued'))
            stale=(state['state']=='legacy' and time.time()-state['created']>300 and not agent_running and not submitted)
            if state['state']=='failed' or stale:
                item.update(state='failed',error=state.get('message') or '旧批次未记录 Agent 派发或 ComfyUI 提交，可重新派发。')
                changed=True
            else:pending[aid]=manifest
        if changed:gateway['publish_json'](manifest,data)
    return pending
