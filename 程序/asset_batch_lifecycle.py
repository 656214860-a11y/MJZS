"""Track Agent dispatch separately from image output; recover unsubmitted legacy batches."""
import time
from pathlib import Path
from agent.core import read,save


def status(manifest):
    manifest=Path(manifest)
    execution=manifest.parent/'执行状态.json'
    if execution.is_file():
        data=read(execution)
        return data if isinstance(data,dict) else {'state':'legacy','created':manifest.stat().st_mtime}
    dispatch=manifest.parent/'派发状态.json'
    if dispatch.is_file():
        data=read(dispatch)
        if not isinstance(data,dict):return {'state':'legacy','created':manifest.stat().st_mtime}
        receipt=Path(data['receipt']) if data.get('receipt') else None
        if receipt and receipt.is_file():
            result=read(receipt)
            return {'state':result.get('state','preparing'),'message':result.get('reason','')}
        if data.get('state')=='preparing' and time.time()-data.get('created',time.time())>300:
            return {'state':'failed','message':'Agent 派发未完成，可重新启动本批次。'}
        return data
    return {'state':'legacy','created':manifest.stat().st_mtime}


def prepare(manifest):
    save(Path(manifest).parent/'派发状态.json',{'state':'preparing','created':time.time()})


def attach(manifest,receipt):
    save(Path(manifest).parent/'派发状态.json',{'state':'preparing','receipt':receipt['record'],'created':time.time()})


def fail(manifest,message):
    save(Path(manifest).parent/'执行状态.json',{'state':'failed','message':str(message),'updated':time.time()})


def reconcile(project,base,selected,agent_running=False):
    """Return only batches with output or evidence of a real dispatch/submission."""
    project=Path(project);base=Path(base).resolve();selected=set(selected)
    ledger=project/'workflows/资产批量记录.json'
    jobs=read(ledger) if ledger.is_file() else {}
    if not isinstance(jobs,dict):jobs={}
    pending={}
    for manifest in (project/'workflows/Imagen资产批次').glob('*/批次.json'):
        data=read(manifest)
        if not isinstance(data,dict):continue
        if Path(data.get('base','')).resolve()!=base:continue
        state=status(manifest);changed=False
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
        if changed:save(manifest,data)
    return pending
