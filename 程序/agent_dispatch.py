"""Persist dispatch receipts so reopening an Agent does not resend a task."""
import hashlib,json,time
from pathlib import Path
from agent.core import read,save
import contract.stage_layout as stage_layout
from codex_tasks import task_lock

def signature(stage,prompt,followup,config,context):
    paths=set()
    def visit(value):
        if isinstance(value,dict):
            for key,item in value.items():
                if key in ('path','asset_manifest','image_registry') and isinstance(item,str):paths.add(item)
                else:visit(item)
        elif isinstance(value,list):
            for item in value:visit(item)
    visit(context)
    if config.get('skill'):paths.add(config['skill'])
    marks=[]
    for value in sorted(paths):
        path=Path(value)
        try:
            content=path.read_bytes();marks.append((value,len(content),hashlib.sha256(content).hexdigest()))
        except OSError:marks.append((value,None,None))
    payload=[stage,prompt,followup,config,marks]
    return hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True).encode('utf-8')).hexdigest()

def claim(project,key,title):
    file=stage_layout.workflow_dir(project,'Agent发送记录',f'{key}.json')
    with task_lock(Path(project)):
        previous=read(file) if file.is_file() else {}
        if not isinstance(previous,dict):previous={}
        if previous.get('state') in ('preparing','sent','uncertain'):
            return {'duplicate':True,'record':str(file),'state':previous['state']}
        save(file,{'state':'preparing','title':title,'created':time.time()})
    return {'duplicate':False,'record':str(file)}

def finish(receipt,state,reason='',**extra):
    file=Path(receipt['record']);data=read(file)
    if not isinstance(data,dict):data={}
    save(file,{**data,**extra,'state':state,'reason':reason,'updated':time.time()})

def outcome(receipt,result):
    state='sent' if result.get('ok') else ('uncertain' if result.get('send_dispatched') else 'failed')
    finish(receipt,state,result.get('reason',''))

def retryable(receipt,has_live_session):
    """只有没有存活窗口的「发送待核实」任务可由本次点击安全重试。"""
    return bool(receipt.get('duplicate') and receipt.get('state')=='uncertain' and not has_live_session)
