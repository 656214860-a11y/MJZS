"""Shared, read-only progress for local and cloud tasks of one storyboard."""
import time
from pathlib import Path
from agent.core import read,read_json
from video_task_state import ACTIVE,elapsed_text

LABELS={'submitting':'提交中','unknown':'待核实','queued':'排队中','running':'生成中',
        'succeeded':'下载中','downloaded':'已下载','failed':'失败','rejected':'被拒绝'}


def latest(path):
    state=read_json(path)
    if not isinstance(state,dict):
        return {}
    shots=state.get('shots',{})
    if not isinstance(shots,dict):
        return {}
    return {sid:versions[-1] for sid,versions in shots.items() if isinstance(versions,list) and versions}


def workspaces(project,source,skip_roots=()):
    """本分镜对应的云端工作集 (目录, 配置)。

    某个工作集里的 config.json 可能被别的工具写坏、编码不符，或字段类型不对：
    跳过它即可。一个坏文件不能让 07 页的进度显示和无人值守的云端轮询一起失效
    ——轮询每轮都会调到这里，抛异常就等于线上任务再也没人查询、成片不会被自动下载。
    """
    source=Path(source).resolve()
    skip={Path(root).resolve() for root in skip_roots}
    for cfgfile in (Path(project).resolve()/'cloud_video').glob('*/config.json'):
        root=cfgfile.parent.resolve()
        if root in skip:continue
        try:
            cfg=read(cfgfile)
            if not isinstance(cfg,dict) or not cfg.get('episode_file'):continue
            if Path(cfg['episode_file']).resolve()!=source:continue
        except (OSError,ValueError,TypeError):
            continue
        yield root,cfg


def snapshot(project,source):
    project=Path(project).resolve()
    local=latest(project/'data/state.json')
    cloud={}
    for root,cfg in workspaces(project,source):
        for sid,version in latest(root/'data/state.json').items():
            old=cloud.get(sid)
            if old is None or version.get('created',0)>old.get('created',0):
                cloud[sid]=version
    return local,cloud


def unwatched_pending(project,source,watched_roots):
    result=[]
    for root,cfg in workspaces(project,source,watched_roots):
        if not cfg.get('live_enabled'):continue
        for sid,version in latest(root/'data/state.json').items():
            if version.get('state') in ACTIVE and version.get('task_id'):result.append((root,sid))
    return result


def display(version,now=None):
    if not version:return '未开始'
    state=version.get('state','unknown')
    text=LABELS.get(state,state)
    if state in ACTIVE:text+=elapsed_text(version,now or time.time())
    return text


def summary(local,cloud,side=None):
    """第 38 期第 1 条：进度只报「这一份工作台自己」那一侧。

    本地生成页原来顶着一句「线上：0 进行中 / 0 已下载」，线上页反过来，两边都没意义。
    side='local' 只报本地，side='cloud' 只报线上；不传时两侧都报（老调用方保持原样）。
    """
    def count(rows):
        active=sum(v.get('state') in ACTIVE for v in rows.values())
        done=sum(v.get('state')=='downloaded' for v in rows.values())
        return f'{active} 进行中 / {done} 已下载'
    if side=='local':return f'本地：{count(local)}'
    if side=='cloud':return f'线上：{count(cloud)}'
    return f'本地：{count(local)}    线上：{count(cloud)}'
