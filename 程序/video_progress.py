"""Shared, read-only progress for local and cloud tasks of one storyboard."""
import time
from pathlib import Path
from file_cache import read_json_shared as read_cached
from video_task_state import ACTIVE,elapsed_text,provider_failure_reason,config_listing,resolved_path

LABELS={'submitting':'提交中','unknown':'待核实','queued':'排队中','running':'生成中',
        'succeeded':'下载中','downloaded':'已下载','failed':'失败','rejected':'被拒绝'}


def latest(path):
    try:
        state=read_cached(path)
    except (OSError,ValueError):  # 与原 read_json 一致：读不出来就当没有
        return {}
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
    source=resolved_path(source)
    skip={resolved_path(root) for root in skip_roots}
    for cfgfile in config_listing(resolved_path(project)/'cloud_video'):
        root=resolved_path(cfgfile.parent)
        if root in skip:continue
        try:
            cfg=read_cached(cfgfile)
            if not isinstance(cfg,dict) or not cfg.get('episode_file'):continue
            if resolved_path(cfg['episode_file'])!=source:continue
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

# O28：本地与云端任务共用一套可恢复状态名、错误分类与「下一步」。
# 只做只读翻译，不改判据——提交/查询/下载/重做是否允许仍由 video_task_state 与 engine 决定。
STATUS_LABELS={'submitting':'提交中','unknown':'结果不确定','queued':'排队中','running':'生成中',
               'downloading':'下载中','download_failed':'下载失败','qc_failed':'技术不合格',
               'review_pending':'待审核','adopted':'已采用','failed':'失败','rejected':'被拒绝',
               'missing_file':'视频文件缺失'}
STATUS_NEXT={'submitting':'继续查询，不要重投','unknown':'核对任务编号，不要重投',
             'queued':'继续查询','running':'继续查询','downloading':'继续查询并取回',
             'download_failed':'再次查询即可续取，不会重新生成','qc_failed':'检查设置后显式重做',
             'review_pending':'等您验收','adopted':'无需操作','failed':'看错误后显式重做',
             'rejected':'改参数或提示词后显式重做','missing_file':'重新取回或重新生成'}
# 错误只归到用户能行动的一类，不猜具体供应商文案。
ERROR_LABELS={'auth':'鉴权','quota':'限额','protocol':'模型协议','refused':'内容拒绝',
              'network':'网络','disk':'本机磁盘','unknown':'未分类'}
ERROR_NEXT={'auth':'补配置：检查密钥','quota':'补配置：充额度或等候','protocol':'显式重做：改参数或模型',
            'refused':'显式重做：改提示词','network':'查询：稍后再试，不会重投',
            'disk':'清理本机磁盘后重新取回','unknown':'看详情再定'}
_DISK_MARKS=('no space','errno 28','enospc','磁盘空间','空间不足','磁盘已满','写入失败','disk full')

def task_status(version):
    """把一条版本记录翻成统一状态码（O28 的八态＋失败/拒绝/缺文件）。"""
    v=version or {}
    state=v.get('state')
    if state=='downloaded':
        if not v.get('file'):return 'missing_file'
        if not v.get('qc_pass'):return 'qc_failed'
        return 'adopted' if v.get('review')=='pass' else 'review_pending'
    if state=='succeeded':
        return 'download_failed' if v.get('download_error') else 'downloading'
    if state in STATUS_LABELS:return state
    return '' if not v else 'unknown'

def status_label(version):
    if not version:return '未开始'
    key=task_status(version)
    return STATUS_LABELS.get(key,str((version or {}).get('state') or '未知'))

def status_next(version):
    if not version:return ''
    return STATUS_NEXT.get(task_status(version),'查看详情')

def error_kind(text):
    """错误分类：命中的第一类即结果；本机磁盘先判，再复用 pet_agent 的分级规则。"""
    hay=str(text or '').lower()
    if any(mark in hay for mark in _DISK_MARKS):return 'disk'
    if not hay.strip():return ''
    from pet_agent import classify
    category=classify(text)['category']
    return {'auth':'auth','quota':'quota','rate_limit':'quota','content':'refused',
            'params':'protocol','timeout':'network','server':'network'}.get(category,'unknown')

def status_detail(version):
    """一行状态：统一状态名＋下一步；失败/不确定再带上错误分类与可行动作。"""
    if not version:return '未开始；点击生成按钮才会提交'
    key=task_status(version)
    text=STATUS_LABELS.get(key,str((version or {}).get('state') or '未知'))
    step=STATUS_NEXT.get(key)
    if step:text+='（下一步：'+step+'）'
    if key in ('failed','rejected','unknown','download_failed','qc_failed'):
        kind=error_kind(version.get('error') or version.get('error_code'))
        if kind:text+=' · 错误分类：'+ERROR_LABELS[kind]+'，'+ERROR_NEXT[kind]
        if key == 'failed':
            reason = provider_failure_reason(version)
            if reason:text+=' · '+reason
    return text
