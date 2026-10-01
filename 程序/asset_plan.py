"""Project asset requirements, independent of image registration."""
from pathlib import Path
import re
from agent.core import read, save, save_bytes, save_text


def publish_plan_bundle(folder, mappings, planned, source_info, progress_text):
    """发布同一资产清单的索引、正文、来源与进度；失败则恢复整个发布包。"""
    folder = Path(folder)
    if not isinstance(mappings, dict) or not isinstance(planned, dict) or not isinstance(source_info, dict):
        raise ValueError('资产清单发布内容必须是对象')
    if not isinstance(progress_text, str):
        raise ValueError('资产清单进度必须是文本')
    targets = (
        (folder / '名称编号对照.json', save, mappings),
        (folder / 'assets.json', save, planned),
        (folder / '来源.json', save, source_info),
        (folder / '导入进度.md', save_text, progress_text),
    )
    previous = tuple((path, path.read_bytes() if path.is_file() else None) for path, _, _ in targets)
    try:
        for path, writer, content in targets:
            writer(path, content)
        if (read(folder / '名称编号对照.json') != mappings or read(folder / 'assets.json') != planned
                or read(folder / '来源.json') != source_info
                or (folder / '导入进度.md').read_text(encoding='utf-8') != progress_text):
            raise ValueError('资产清单发布后复核失败')
    except Exception:
        from file_cache import remove_temporary_file
        for path, raw in previous:
            if raw is not None:
                save_bytes(path, raw)
            elif path.is_file():
                remove_temporary_file(path)
        raise

def sync_plan(project,episode_dir,storyboard=None,*,scope='current',_adopting=False):
    if scope not in ('all','current','adopted'):raise ValueError('未知的资产显示范围')
    from asset_context import library_dir,active_source,references
    project=Path(project).resolve();episode_dir=library_dir(project,episode_dir)
    folder=episode_dir/'assets'/'资产清单';folder.mkdir(parents=True,exist_ok=True)
    file=folder/'assets.json'
    planned=read(file) if file.exists() else {}
    if not isinstance(planned,dict):raise ValueError('资产清单 assets.json 应为以资产编号为键的对象')
    for aid,asset in planned.items():
        if not re.fullmatch(r'(CHAR|LOC|PROP)_\d{3,}',aid) or not isinstance(asset,dict):
            raise ValueError('资产清单编号或格式错误：'+str(aid))
    from storyboard_catalog_service import resolve_source
    if isinstance(storyboard,(list,tuple)):
        sources=list(dict.fromkeys(resolve_source(project,path) for path in storyboard))
    else:sources=[active_source(project,storyboard,episode_dir)]
    if not _adopting:
        from storyboard_adoption_contract import adopted
        allowed=set(adopted(project))
        sources=[source for source in sources if source in allowed]
    episodes=[(source,read(source)) for source in sources]
    episode=episodes[-1][1] if episodes else {}
    source=sources[-1] if sources else None
    registry=read(episode_dir/'assets.json') if (episode_dir/'assets.json').exists() else {}
    for aid,asset in registry.items():
        planned.setdefault(aid,{k:v for k,v in asset.items() if k!='image'})
    from prop_assets import normalize_shot,removed_ids,requires_asset
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
    from asset_reference_prompts import sync_reference_prompts,AUTO_FIELDS
    for _,ep in episodes:
        # 上面这几步往清单里补过编号，这一份重新算一次；口径与 normalize_shot 内部一致。
        removed=removed_ids(planned)
        ids={value if re.fullmatch(prefix+r'_\d{3,}',value) else mappings.get(prefix+':'+value)
             for shot in ep.get('shots',[]) for prefix,value in references(normalize_shot(shot,planned,removed))}
        active={aid:planned[aid] for aid in ids if aid in planned}
        sync_reference_prompts(project,active,ep.get('source_script'))
    # 第 64 期任务 13：契约字段（正典板、锚点字符串、状态变体、锁定…）落到资产清单里。
    # 以前只在内存里被 normalize 补出来、从没落过盘，用户看到的就是「正典板和换状态面板两次
    # 新增都失败」。只补缺的键，已有的值一个都不动。
    from asset_contract import normalize as _fill_contract
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
    publish_plan_bundle(folder, mappings, planned,
                        {'storyboard':str(source) if source else '', 'storyboards':[str(p) for p in sources],
                         'episode_id':episode.get('episode_id'),'episode_ids':[ep.get('episode_id') for _,ep in episodes],
                         'asset_ids':list(current)}, '\n'.join(lines)+'\n')
    return rows


def plan_file(project,episode_dir):
    """这一项的「人写的资产清单」落在哪：资产库/assets/资产清单/assets.json。"""
    from asset_context import library_dir
    return library_dir(project,episode_dir)/'assets/资产清单/assets.json'


def update_fields(project,episode_dir,aid,values):
    """把几项字段写进资产清单里那一条资产，返回写后的那一行（第 64 期任务 13）。

    正典板、锚点字符串、状态变体这些字段以前只在内存里被 asset_contract.normalize 补出来，
    从来没有落过盘——资产详情页读到的一直是空，用户看到的就是「正典板和换状态面板两次
    新增都失败」。这里补上唯一的落盘入口，界面与门禁都走它。
    """
    from asset_context import library_dir
    return update_planned(library_dir(project,episode_dir),aid,values)


def apply_gate_choice(project, key, choice, episode_dir=""):
    """将主观门禁的锚点／正典板选择写入资产清单。

    门禁契约只负责判断和记录确认；这项领域写入必须留在资产服务层，
    避免 L0 ``confirm_gates`` 反向依赖资产上下文。
    """
    head, _, asset_id = str(key or '').partition(':')
    if head not in ('anchor', 'canon') or not asset_id:
        return None
    value = str(choice or '').strip()
    values = ({'character_anchor': value, 'base_anchor': value}
              if head == 'anchor' else {'canonical_board': value})
    return update_fields(project, episode_dir, asset_id, values)


def update_planned(episode_dir,aid,values):
    """按资产库目录直接落盘（第 64 期任务 13）。

    asset_batch.register_image 手上只有资产库目录、没有 project，走这一条同一个入口。
    """
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
    save(file,planned)
    return row


