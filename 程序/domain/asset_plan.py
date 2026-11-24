"""Project asset requirements, independent of image registration."""
from pathlib import Path
import re
import logging
from functools import wraps
from agent.core import read
from contract.service_contract import SystemError, success


def _asset_plan_result(operation):
    """资产清单写入口只把实际存储故障转成可展示结果。"""
    @wraps(operation)
    def run(*args, **kwargs):
        try:
            return success(operation(*args, **kwargs))
        except OSError as exc:
            logging.getLogger('asset_plan').exception('资产清单写入失败')
            return SystemError('资产清单未能保存，请检查磁盘或文件占用后重试。',
                               data={'cause': str(exc), 'operation': operation.__name__})
    return run


def _publishers(gateway):
    """L2 只接受 L3 装配的发布能力，不自行决定正式落盘入口。"""
    gateway = gateway if isinstance(gateway, dict) else {}
    names = ('publish_json', 'publish_bytes', 'publish_text', 'remove_file')
    values = {name: gateway.get(name) for name in names}
    if not all(callable(value) for value in values.values()):
        raise RuntimeError('资产计划发布必须由 L3 注入')
    return values


def _bundle_is_current(folder, mappings, planned, source_info, progress_text):
    """四份发布文件都在，且解析后的内容与待发布的完全相同。

    无人值守轮询每个节拍都会重算清单，内容几乎总是没变；这时再走一遍「写四份＋fsync＋回读复核」
    只是白白磨盘。任何一份缺失、读不出或内容不同都按「不是最新」处理，仍整包重新发布。"""
    try:
        return (read(folder / '名称编号对照.json') == mappings
                and read(folder / 'assets.json') == planned
                and read(folder / '来源.json') == source_info
                and (folder / '导入进度.md').read_text(encoding='utf-8') == progress_text)
    except (OSError, ValueError):
        return False


def _publish_plan_bundle(folder, mappings, planned, source_info, progress_text, *, gateway=None):
    """发布同一资产清单的索引、正文、来源与进度；失败则恢复整个发布包。"""
    publishers = _publishers(gateway)
    folder = Path(folder)
    if not isinstance(mappings, dict) or not isinstance(planned, dict) or not isinstance(source_info, dict):
        raise ValueError('资产清单发布内容必须是对象')
    if not isinstance(progress_text, str):
        raise ValueError('资产清单进度必须是文本')
    targets = (
        (folder / '名称编号对照.json', publishers['publish_json'], mappings),
        (folder / 'assets.json', publishers['publish_json'], planned),
        (folder / '来源.json', publishers['publish_json'], source_info),
        (folder / '导入进度.md', publishers['publish_text'], progress_text),
    )
    if all(path.is_file() for path, _, _ in targets) and _bundle_is_current(
            folder, mappings, planned, source_info, progress_text):
        return
    previous = tuple((path, path.read_bytes() if path.is_file() else None) for path, _, _ in targets)
    try:
        for path, writer, content in targets:
            writer(path, content)
        if (read(folder / '名称编号对照.json') != mappings or read(folder / 'assets.json') != planned
                or read(folder / '来源.json') != source_info
                or (folder / '导入进度.md').read_text(encoding='utf-8') != progress_text):
            raise ValueError('资产清单发布后复核失败')
    except Exception:
        for path, raw in previous:
            if raw is not None:
                publishers['publish_bytes'](path, raw)
            elif path.is_file():
                publishers['remove_file'](path)
        raise


@_asset_plan_result
def publish_plan_bundle(folder, mappings, planned, source_info, progress_text, *, gateway=None):
    return _publish_plan_bundle(folder, mappings, planned, source_info, progress_text, gateway=gateway)

def _sync_plan(project,episode_dir,storyboard=None,*,scope='current',_adopting=False,gateway=None,context=None):
    if scope not in ('all','current','adopted'):raise ValueError('未知的资产显示范围')
    from domain.asset_context import library_dir,active_source,references
    project=Path(project).resolve();episode_dir=library_dir(project,episode_dir)
    folder=episode_dir/'assets'/'资产清单';folder.mkdir(parents=True,exist_ok=True)
    file=folder/'assets.json'
    planned=read(file) if file.exists() else {}
    if not isinstance(planned,dict):raise ValueError('资产清单 assets.json 应为以资产编号为键的对象')
    for aid,asset in planned.items():
        if not re.fullmatch(r'(CHAR|LOC|PROP)_\d{3,}',aid) or not isinstance(asset,dict):
            raise ValueError('资产清单编号或格式错误：'+str(aid))
    from domain.storyboard_catalog_service import resolve_source
    from contract.project_context import ProjectContext
    if not isinstance(context, ProjectContext):
        raise TypeError('资产计划需要由 L3 注入 ProjectContext。')
    if isinstance(storyboard,(list,tuple)):
        sources=list(dict.fromkeys(resolve_source(context,path) for path in storyboard))
    else:sources=[active_source(project,storyboard,episode_dir,context=context)]
    if not _adopting:
        from domain.storyboard_adoption_contract import adopted
        allowed=set(adopted(project))
        sources=[source for source in sources if source in allowed]
    episodes=[(source,read(source)) for source in sources]
    episode=episodes[-1][1] if episodes else {}
    source=sources[-1] if sources else None
    registry=read(episode_dir/'assets.json') if (episode_dir/'assets.json').exists() else {}
    for aid,asset in registry.items():
        planned.setdefault(aid,{k:v for k,v in asset.items() if k!='image'})
    from contract.prop_assets import normalize_shot,removed_ids,requires_asset
    aliases={}
    for aid,asset in planned.items():
        names=[asset.get('name',aid)]+asset.get('aliases',[])
        for name in names:
            if isinstance(name,str):aliases.setdefault((aid.split('_')[0],name.strip()),set()).add(aid)
    # Reserve every explicit ID before assigning names to avoid later collisions.
    if any(not isinstance(ep.get('shots',[]),list) for _,ep in episodes):raise ValueError('分镜 shots 应为镜头数组')
    shots=[shot for _,ep in episodes for shot in ep.get('shots',[])]
    if not all(isinstance(shot,dict) for shot in shots):raise ValueError('分镜中的镜头必须是对象')
    # 第 72 期（Round 3）：这一份「不建独立资产的编号」只跟清单有关，算一次，几百个镜头共用
    # （原来每个镜头都要把整份清单扫一遍，28 万次 requires_asset 就是这么来的）。
    removed=removed_ids(planned)
    shots=[normalize_shot(shot,planned,removed) for shot in shots]
    prop_details={}
    for shot in shots:
        for item in shot.get('props',[]):
            if isinstance(item,dict):
                key=item.get('id') or item.get('name')
                if key:prop_details[key]={k:v for k,v in item.items() if k in ('name','description','requires_asset','prop_importance','asset_reason','image_prompt','negative_prompt')}
    for shot in shots:
        for prefix,value in references(shot):
            if re.fullmatch(prefix+r'_\d{3,}',value):
                planned.setdefault(value,{'name':value,'description':'待补充名称和外观要求',**prop_details.get(value,{})})
    mappings={};current={}
    for shot in shots:
        for prefix,value in references(shot):
            if re.fullmatch(prefix+r'_\d{3,}',value):aid=value
            else:
                matches=aliases.get((prefix,value),set())
                if len(matches)>1:raise ValueError('资产名称对应多个编号，请在分镜中指定编号：'+value)
                if len(matches)==1:aid=next(iter(matches))
                else:
                    index=1
                    while f'{prefix}_{index:03}' in planned:index+=1
                    aid=f'{prefix}_{index:03}'
                    planned[aid]={'name':value,'description':'待确认外观要求','aliases':[value],**prop_details.get(value,{})}
                    aliases[(prefix,value)]={aid}
                mappings[prefix+':'+value]=aid
            used=current.setdefault(aid,[])
            if shot.get('id') and shot['id'] not in used:used.append(shot['id'])
            history=planned[aid].setdefault('used_in',[])
            if shot.get('id') and shot['id'] not in history:history.append(shot['id'])
    from domain.asset_reference_prompts import sync_reference_prompts,AUTO_FIELDS,discover as discover_reference_documents
    reference_documents={}
    for _,ep in episodes:
        # 上面这几步往清单里补过编号，这一份重新算一次；口径与 normalize_shot 内部一致。
        removed=removed_ids(planned)
        ids={value if re.fullmatch(prefix+r'_\d{3,}',value) else mappings.get(prefix+':'+value)
             for shot in ep.get('shots',[]) for prefix,value in references(normalize_shot(shot,planned,removed))}
        active={aid:planned[aid] for aid in ids if aid in planned}
        script=ep.get('source_script')
        # 已采用分镜多对同一份剧本时，逐集重复递归扫描 writing 只有重复成本。
        documents=reference_documents.get(script)
        if documents is None:
            documents=reference_documents[script]=discover_reference_documents(project,script)
        sync_reference_prompts(project,active,script,documents=documents)
    # 第 64 期任务 13：契约字段（正典板、锚点字符串、状态变体、锁定…）落到资产清单里。
    # 以前只在内存里被 normalize 补出来、从没落过盘，用户看到的就是「正典板和换状态面板两次
    # 新增都失败」。只补缺的键，已有的值一个都不动。
    from contract.asset_contract import normalize as _fill_contract
    for aid,asset in list(planned.items()):
        filled=_fill_contract(asset,aid)
        if filled!=asset:planned[aid]=filled
    rows={}
    for aid in sorted(current):
        asset=planned[aid]
        if not requires_asset(aid,asset):continue
        entry={**registry.get(aid,{}),**asset,'used_in':asset.get('used_in',[]) if scope=='all' else current[aid]}
        for field in AUTO_FIELDS:
            if field in asset:entry[field]=asset[field]
            elif registry.get(aid,{}).get('prompt_import_hash'):entry.pop(field,None)
        # Only registered images count as imported, never paths supplied by a plan.
        entry.pop('image',None)
        image=registry.get(aid,{}).get('image')
        if image:entry['image']=image
        path=(episode_dir/image).resolve() if image else None
        entry['status']='已导入' if path and path.is_relative_to(episode_dir) and path.is_file() else '待导入'
        rows[aid]=entry
    lines=['# 资产清单 · '+({'all':'全部资产','current':'当前分镜','adopted':'已采用分镜'}[scope]),'分镜来源：'+'、'.join(str(ep.get('episode_id','')) for _,ep in episodes),'', '| 编号 | 名称 | 状态 |','|---|---|---|']
    for aid,entry in sorted(rows.items()):
        name=str(entry.get('name',aid)).replace('|','／').replace('\n',' ')
        lines.append(f"| {aid} | {name} | {entry['status']} |")
    _publish_plan_bundle(folder, mappings, planned,
                         {'storyboard':str(source) if source else '', 'storyboards':[str(p) for p in sources],
                          'episode_id':episode.get('episode_id'),'episode_ids':[ep.get('episode_id') for _,ep in episodes],
                          'asset_ids':list(current)}, '\n'.join(lines)+'\n', gateway=gateway)
    return rows


@_asset_plan_result
def sync_plan(project,episode_dir,storyboard=None,*,scope='current',_adopting=False,gateway=None,context=None):
    return _sync_plan(project, episode_dir, storyboard, scope=scope, _adopting=_adopting, gateway=gateway, context=context)


def plan_file(project,episode_dir):
    """这一项的「人写的资产清单」落在哪：资产库/assets/资产清单/assets.json。"""
    from domain.asset_context import library_dir
    return library_dir(project,episode_dir)/'assets/资产清单/assets.json'


def _update_fields(project,episode_dir,aid,values,*,gateway=None):
    """把几项字段写进资产清单里那一条资产，返回写后的那一行（第 64 期任务 13）。

    正典板、锚点字符串、状态变体这些字段以前只在内存里被 asset_contract.normalize 补出来，
    从来没有落过盘——资产详情页读到的一直是空，用户看到的就是「正典板和换状态面板两次
    新增都失败」。这里补上唯一的落盘入口，界面与门禁都走它。
    """
    from domain.asset_context import library_dir
    return _update_planned(library_dir(project,episode_dir),aid,values,gateway=gateway)


@_asset_plan_result
def update_fields(project,episode_dir,aid,values,*,gateway=None):
    return _update_fields(project, episode_dir, aid, values, gateway=gateway)


def _apply_gate_choice(project, key, choice, episode_dir="", *, gateway=None):
    """将主观门禁的锚点／正典板选择写入资产清单。

    门禁契约只负责判断和记录确认；这项领域写入必须留在资产服务层，
    避免 L0 ``confirm_gates`` 反向依赖资产上下文。不支持的 key（如
    ``conflict:`` 裁决键）返回 ``None``：不落盘、不伪造已采用结果，
    调用方据此拒绝记成已确认。
    """
    head, _, asset_id = str(key or '').partition(':')
    if head not in ('anchor', 'canon') or not asset_id:
        return None
    value = str(choice or '').strip()
    values = ({'character_anchor': value, 'base_anchor': value}
              if head == 'anchor' else {'canonical_board': value})
    return _update_fields(project, episode_dir, asset_id, values, gateway=gateway)


@_asset_plan_result
def apply_gate_choice(project, key, choice, episode_dir="", *, gateway=None):
    return _apply_gate_choice(project, key, choice, episode_dir, gateway=gateway)


def _update_planned(episode_dir,aid,values,*,gateway=None):
    """按资产库目录直接落盘（第 64 期任务 13）。

    asset_batch.register_image 手上只有资产库目录、没有 project，走这一条同一个入口。
    """
    publishers = _publishers(gateway)
    aid=str(aid or '').strip()
    if not aid:raise ValueError('资产编号不能为空')
    if not isinstance(values,dict) or not values:raise ValueError('没有要写入的字段')
    file=Path(episode_dir)/'assets/资产清单/assets.json'
    planned=read(file) if file.is_file() else {}
    if not isinstance(planned,dict):raise ValueError('资产清单 assets.json 应以资产编号为键的对象')
    row=planned.get(aid)
    if not isinstance(row,dict):row={}
    row.update(values)
    planned[aid]=row
    publishers['publish_json'](file,planned)
    return row


@_asset_plan_result
def update_planned(episode_dir,aid,values,*,gateway=None):
    return _update_planned(episode_dir, aid, values, gateway=gateway)


def _adopted_storyboard_shots(project):
    """采用分镜里的 (episode_id, 分镜路径, 镜头)，读不动或没有采用就跳过。"""
    from infra.file_cache import read_json
    from domain.storyboard_adoption_contract import adopted
    rows = []
    for path in adopted(project):
        try:
            data = read_json(path)
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        episode = str(data.get('episode_id') or Path(path).stem)
        for shot in data.get('shots') or []:
            if isinstance(shot, dict):
                rows.append((episode, Path(path).resolve(), shot))
    return rows


def asset_impact(project, aid, *, episode_dir=''):
    """只读变更影响视图：一项资产的正典/变体、被哪些采用镜头引用、改了要复核什么、能否回收。

    依赖采用分镜与项目任务状态；不写盘、不改资产、不删文件。``orphan`` 为真表示当前没有
    采用镜头引用它（可回收），``protected`` 为真表示被采用镜头引用（改动需先核对）。
    """
    from domain.asset_context import referencing_shots
    from contract.asset_contract import state_variants
    from domain.storyboard_catalog_service import _generated_video_shots
    from contract.storyboard_paths import media_root
    project = Path(project).resolve()
    aid = str(aid or '').strip()
    if not re.fullmatch(r'(CHAR|LOC|PROP)_\d{3,}', aid):
        raise ValueError('资产编号不正确：' + (aid or '（空）'))
    file = plan_file(project, episode_dir)
    plan = read(file) if file.is_file() else {}
    entry = plan.get(aid) if isinstance(plan, dict) and isinstance(plan.get(aid), dict) else {}
    generated = _generated_video_shots(project)
    references, files, shots = [], [], set()
    for episode, path, shot in _adopted_storyboard_shots(project):
        rows = referencing_shots([shot], aid)
        if not rows:
            continue
        shots.add(rows[0]['id'])
        references.append({'episode': episode, 'shot': rows[0]['id'], 'fields': rows[0]['fields']})
        name = str(shot.get('frame') or '').strip()
        if name:
            try:
                frame = media_root(path) / name
            except OSError:
                frame = None
            if frame is not None and frame.is_file():
                files.append(str(frame))
    return {'aid': aid, 'in_plan': bool(entry), 'adopted': bool(references),
            'orphan': not references, 'protected': bool(references),
            'canon': {'board': str(entry.get('canonical_board') or '').strip(),
                      'anchor': str(entry.get('character_anchor') or entry.get('base_anchor') or '').strip()},
            'variants': [{'state_id': row['state_id'], 'name': row['name']} for row in state_variants(entry)],
            'references': references, 'files': sorted(set(files)),
            'videos': sorted(sid for sid in shots if sid in generated)}


def deletion_references(project, aid, *, episode_dir=''):
    """删除这一项资产前要看的引用清单：引用镜头、需复核文件、是否受保护。"""
    impact = asset_impact(project, aid, episode_dir=episode_dir)
    shots = [row['shot'] for row in impact['references']]
    if impact['protected']:
        head = '、'.join(shots[:6]) + ('…' if len(shots) > 6 else '')
        summary = '被 %d 个采用镜头引用（%s），删除前请先解除引用或改用替换。' % (len(shots), head)
    else:
        summary = '当前没有采用镜头引用，属可回收的孤立资产。'
    return {'aid': impact['aid'], 'protected': impact['protected'], 'shots': shots,
            'files': impact['files'], 'videos': impact['videos'], 'summary': summary}


def _usage_frame_status(path, shot, frame_problem_fn):
    """单镜首帧三档；异常由调用方吞掉并改 stale。"""
    from contract.storyboard_paths import media_root
    from infra.file_cache import read_json
    name = str(shot.get('frame') or '').strip()
    if not name:
        return 'missing', ''
    image = media_root(path) / name
    if not image.is_file():
        return 'missing', ''
    if frame_problem_fn is None:
        return 'stale', '未注入首帧校验'
    problem = frame_problem_fn(path, read_json(path), shot, image)
    if problem:
        return 'stale', str(problem)
    return 'latest', ''


def asset_usage(project, aid, *, episode_dir='', frame_problem_fn=None):
    """只读使用情况：逐镜首帧最新／过期／缺失与视频已生成／未生成（DES-S05-51）。

    不写盘。读分镜或校验抛错时该镜头按 ``stale`` 处理；本函数本身不向外抛。
    ``frame_problem_fn`` 由 L3 注入（避免同层未登记依赖 ``keyframe_evidence``）；
    未注入时有文件的首帧一律按 ``stale`` 并写明原因。
    """
    try:
        impact = asset_impact(project, aid, episode_dir=episode_dir)
    except Exception:
        return {'aid': str(aid or '').strip(), 'orphan': True, 'rows': [], 'videos': []}
    generated = set(impact.get('videos') or [])
    by_shot = {}
    for episode, path, shot in _adopted_storyboard_shots(project):
        sid = str(shot.get('id') or '')
        if sid:
            by_shot[(episode, sid)] = (path, shot)
    rows = []
    for ref in impact.get('references') or []:
        episode, sid = ref.get('episode'), ref.get('shot')
        video = 'generated' if sid in generated else 'none'
        try:
            path, shot = by_shot[(episode, sid)]
            frame_status, frame_reason = _usage_frame_status(path, shot, frame_problem_fn)
        except Exception as exc:
            frame_status, frame_reason = 'stale', str(exc) or '读不出分镜或校验失败'
        rows.append({'episode': episode, 'shot': sid, 'frame': frame_status,
                     'frame_reason': frame_reason, 'video': video})
    return {'aid': impact['aid'], 'orphan': bool(impact.get('orphan')),
            'rows': rows, 'videos': list(impact.get('videos') or [])}
