"""Persist model choices separately from generated media and task ledgers."""
import json

FIELDS=('base_url','model','api_key')


def identity(base_url,model,provider=''):
    return json.dumps([provider,str(base_url).strip().rstrip('/'),str(model).strip()],ensure_ascii=False)


def records(config):
    if not isinstance(config, dict):
        return []
    # Once migrated, the model list is authoritative: legacy fields must not
    # bring deleted models back on the next launch.
    if 'model_profiles' in config:
        candidates=config['model_profiles']
    else:
        candidates=[*config.get('profiles',{}).values(),config]
    result={};removed=set(config.get('deleted_models',[]))
    for value in candidates:
        if not isinstance(value,dict):continue
        record={key:str(value.get(key,'')) for key in FIELDS}
        record['base_url']=record['base_url'].strip().rstrip('/')
        record['model']=record['model'].strip()
        key=identity(record['base_url'],record['model'])
        if record['base_url'] and record['model'] and key not in removed:result[key]=record
    return list(result.values())


def with_records(config,values):
    result=dict(config);result['model_profiles']=list(values)
    result['profiles']={record['base_url']:dict(record) for record in values}
    return result


def remember(config,value):
    record={key:str(value.get(key,'')) for key in FIELDS}
    record['base_url']=record['base_url'].strip().rstrip('/')
    record['model']=record['model'].strip()
    key=identity(record['base_url'],record['model'])
    values=[r for r in records(config) if identity(r['base_url'],r['model'])!=key]
    result=with_records({**config,**value},[*values,record])
    result['deleted_models']=[k for k in config.get('deleted_models',[]) if k!=key]
    return result


def remove(config,base_url,model):
    key=identity(base_url,model)
    values=[r for r in records(config) if identity(r['base_url'],r['model'])!=key]
    result=with_records(config,values)
    result['deleted_models']=list(dict.fromkeys([*config.get('deleted_models',[]),key]))
    if identity(config.get('base_url',''),config.get('model',''))==key:result['model']=''
    return result


def label(record):return record['model']+' · '+record['base_url']


def cloud_removed(project,config):
    from pathlib import Path
    from agent.core import read
    if not isinstance(config, dict):
        return False
    path=Path(project)/'ui_settings.json'
    prefs=read(path) if path.is_file() else {}
    if not isinstance(prefs, dict):
        prefs={}
    deleted=prefs.get('cloud_deleted_models',[])
    if not isinstance(deleted, list):
        deleted=[]
    return identity(config.get('base_url',''),config.get('model',''),config.get('cloud_provider','wan')) in deleted


def ensure_cloud_model(root,config):
    from pathlib import Path
    from storyboard_paths import is_cloud_workspace
    root=Path(root)
    if is_cloud_workspace(root) and cloud_removed(root.parent.parent,config):
        raise ValueError('此 API 模型已删除，请重新选择并保存模型后生成。历史任务仍可查询。')
