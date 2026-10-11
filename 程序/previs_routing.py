"""Route previs by motion complexity; the default inference remains overridable."""
import json,re
from datetime import datetime
from pathlib import Path
from agent.core import read
from project_context import ProjectContext

LEVELS={'simple':'简单／固定动作','medium':'中等动作','complex':'复杂动作'}
ROUTES={'simple':'无需白模','medium':'线上简单白模','complex':'Agent 自动制作'}


def classify(shot):
    if not isinstance(shot, dict):
        return 'medium', '分镜动作信息不足，先按中等处理，可手动调整复杂度'
    explicit=shot.get('action_complexity') or shot.get('previs_complexity')
    reason=shot.get('complexity_reason') or shot.get('previs_reason')
    if isinstance(explicit,dict):reason=explicit.get('reason') or reason;explicit=explicit.get('level')
    if not isinstance(explicit,str):explicit=None
    explicit={'简单':'simple','低':'simple','中等':'medium','复杂':'complex','高':'complex','low':'simple','moderate':'medium','high':'complex'}.get(explicit,explicit)
    if explicit in LEVELS:return explicit,str(reason or '采用分镜定稿标注的动作复杂度')
    action=str(shot.get('action') or shot.get('action_description') or '')
    if not action:action='；'.join(str(shot[k]) for k in ('action_start','action_end') if shot.get(k)) or str(shot.get('video_prompt',''))
    # Negated constraints are not motions to perform.
    action=re.sub(r'(?:禁止|不要|无需|没有)[^，。；;→]{0,14}', '', action)
    action=re.sub(r'(?:无|不)(?:追逐|打斗|跳跃|跑动|移动|转身|换手|抛接)', '', action)
    camera=str(shot.get('camera') or shot.get('camera_motion') or '')
    # 否定词同样适用于机位运动，避免把“不要环绕”误判为需要协同的复杂机位。
    camera=re.sub(r'(?:禁止|不要|无需|没有)[^，。；;→]{0,14}', '', camera)
    camera=re.sub(r'(?:无|不)(?:环绕|穿越|跟拍|绕行|推近|拉远|横移|跟随|摇镜|移镜)', '', camera)
    if re.search(r'追逐|打斗|搏斗|翻滚|腾空|跳跃|攀爬|摔倒|接住|抛接|抢夺|交接|换手|递给|递到|群舞|群体调度',action):
        return 'complex','涉及肢体互动、物件交接或快速运动，需要验证动作衔接'
    beats=len([p for p in re.split(r'→|然后|随后|接着|同时|再(?!次|见)',action) if p.strip()])
    if beats>=5:return 'complex','包含较长的连续动作链，需要验证动作起止和节奏'
    moving=bool(re.search(r'走|跑|挪|移动|伸手|拿起|放下|扶住|推|拉|蹲|起身|坐下|转身|弯腰',action))
    if moving and re.search(r'环绕|穿越|跟拍|绕行',camera):return 'complex','人物运动与摄像机运动需要协同'
    if moving or beats>=3:return 'medium','有少量走位或物件操作，适合线上简单白模'
    if re.search(r'静止|保持|站定|站着|站立|坐着|凝视|看|转头|点头|微笑|说|对白|对话|招呼|招手|整理衣|调整衣|眨眼|偏转|微偏|固定',action):
        return 'simple','固定站位或简单姿态、表情与对白，可直接进入视频制作'
    return 'medium','分镜动作信息不足，先按中等处理，可手动调整复杂度'


def _context(value):
    if not isinstance(value, ProjectContext):
        raise TypeError('白模分流项目路径需要由 L3 注入 ProjectContext。')
    return value


def overrides_file(context):return _context(context).root/'data/白模复杂度设置.json'


def entries(context,source):
    context=_context(context)
    ep=read(source)
    if not isinstance(ep,dict):return {}
    saved=read(overrides_file(context)) if overrides_file(context).is_file() else {}
    result={};prefix=str(ep.get('episode_id',''))+'|'
    shots=ep.get('shots',[])
    if not isinstance(shots, list):
        shots=[]
    if not isinstance(shots,list):shots=[]
    for shot in shots:
        if not isinstance(shot, dict) or not shot.get('id'):
            continue
        level,reason=classify(shot);choice=saved.get(prefix+shot['id'])
        if choice in LEVELS:level,reason=choice,'使用手动选择的复杂度'
        result[shot['id']]={'level':level,'reason':reason,'route':ROUTES[level],'override':choice or 'auto'}
    return result


def set_override(context,source,sid,value,*,publish):
    context=_context(context)
    if value not in ('auto',*LEVELS):raise ValueError('未知的动作复杂度')
    ep=read(source)
    if sid not in {s['id'] for s in ep['shots']}:raise ValueError('镜头不存在')
    file=overrides_file(context);data=read(file) if file.is_file() else {};key=str(ep.get('episode_id',''))+'|'+sid
    if value=='auto':data.pop(key,None)
    else:data[key]=value
    publish(file,data)


def partition(context,source,ids):
    context=_context(context)
    decisions=entries(context,source);groups={key:[] for key in LEVELS}
    if not ids or any(sid not in decisions for sid in ids):raise ValueError('请选择当前分镜中的镜头')
    for sid in dict.fromkeys(ids):groups[decisions[sid]['level']].append(sid)
    return groups,decisions


def decisions_for(context,source,shots):
    """页面、调度与阶段门禁共用的唯一有效决策：手工覆盖优先，读不到时退回自动分类。"""
    context=_context(context)
    saved=entries(context,source)
    result={}
    for shot in shots or []:
        if not isinstance(shot,dict) or not shot.get('id'):
            continue
        sid=shot['id'];item=saved.get(sid)
        if item is None:
            level,reason=classify(shot)
            item={'level':level,'reason':reason,'route':ROUTES[level],'override':'auto'}
        result[sid]=item
    return result


def ready(context,sid,source=None):
    context=_context(context)
    import white_model_service as wm
    try:
        value=wm.read_record(wm.shot_directory(context,sid,source=source)).get('preview')
    except (OSError,ValueError):
        return False
    path=Path(value) if value else None
    try:
        return bool(path and path.is_file() and path.stat().st_size and path.suffix.lower() in ('.mp4','.mov','.webm'))
    except OSError:
        return False


def automatic_candidates(context, source, shots, wait_for_frames=False, pending_frame_ids=None):
    """计算无人值守白模候选；不启动任务也不访问 UI。"""
    context=_context(context)
    ids = [shot['id'] for shot in shots if isinstance(shot, dict) and shot.get('id')]
    if not ids:
        return {'pending': [], 'medium': [], 'waiting': []}
    groups, _decisions = partition(context, source, ids)
    pending = [sid for sid in groups['complex'] if not ready(context, sid, source)]
    waiting = []
    if pending and wait_for_frames and callable(pending_frame_ids):
        without_frame = set(pending_frame_ids(shots))
        waiting = [sid for sid in pending if sid in without_frame]
        pending = [sid for sid in pending if sid not in without_frame]
    return {'pending': pending, 'medium': groups['medium'], 'waiting': waiting}


def automatic_notice(source, pending, medium, waiting):
    """返回无人值守白模的去重指纹及可展示提示项。"""
    notice = (str(source), tuple(pending), tuple(medium), len(waiting))
    notes = []
    if waiting:
        notes.append(str(len(waiting)) + ' 镜待首帧就绪后再建白模')
    if medium:
        notes.append(str(len(medium)) + ' 镜中等动作需用「线上白模入口」制作后导入')
    return notice, notes


def automatic_signature(source, pending):
    """返回自动白模派发批次的稳定去重键。"""
    return str(source), tuple(pending)


def automatic_engine(context, read_settings, engines):
    """从注入的设置读取器解析白模引擎，保留调用方的 UI/退避职责。"""
    settings = read_settings(_context(context).root, 'previs')
    return engines[settings['engine']]

def dispatch(context,source,ids,state,monitor=False,start_complex=None,*,publish):
    """Route selected shots; the caller owns the optional Agent executor.

    Keeping the executor injected prevents the routing policy from importing the
    automation runner, while retaining the old one-click behaviour in the UI.
    """
    context=_context(context)
    if state.get('busy'):raise ValueError('已有白模任务运行中')
    root=context.root
    groups,decisions=partition(context,source,ids)
    completed=[sid for sid in ids if ready(context,sid,source)]
    for level in groups:groups[level]=[sid for sid in groups[level] if sid not in completed]
    folder=root/'工作流任务/白模分流记录'/datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    publish(folder/'分流结果.json',{'source':str(source),'groups':groups,'ready_skipped':completed,'decisions':{sid:decisions[sid] for sid in ids}})
    state['routing_log_dir']=str(folder)
    for level in ('simple','medium'):
        for sid in groups[level]:
            key=str(root)+'|'+sid
            state.setdefault('status',{})[key]='无需白模，已跳过' if level=='simple' else '待线上制作／导入'
            state.setdefault('progress',{}).pop(key,None)
    state['summary']=f'已就绪 {len(completed)} 镜跳过；简单 {len(groups["simple"])} 镜跳过；中等 {len(groups["medium"])} 镜走线上；复杂 {len(groups["complex"])} 镜交给 Agent。'
    if groups['complex'] and start_complex:
        try:
            start_complex(root,source,groups['complex'],state,monitor=monitor)
        except Exception as exc:
            publish(folder/'启动错误.json',{'error':str(exc),'shot_ids':groups['complex']})
            for sid in groups['complex']:state.setdefault('status',{})[str(root)+'|'+sid]='失败：'+str(exc)
            state['summary']+=' Agent 尚未启动：'+str(exc)
    elif groups['complex']:
        state['summary']+=' Agent 尚未启动：未提供自动制作执行器。'
    return groups


def records_directory(context,state):
    root=_context(context).root
    candidates=[]
    for key in ('log_dir','routing_log_dir'):
        value=state.get(key)
        if value and Path(value).is_dir() and Path(value).resolve().is_relative_to(root.resolve()):candidates.append(Path(value))
    root=root/'工作流任务'
    for name in ('白模自动制作','白模批量任务','白模分流记录'):
        if (root/name).is_dir():candidates.extend(p for p in (root/name).iterdir() if p.is_dir())
    if candidates:return max(candidates,key=lambda p:p.stat().st_mtime_ns)
    folder=root/'白模分流记录';folder.mkdir(parents=True,exist_ok=True);return folder
