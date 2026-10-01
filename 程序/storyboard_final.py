"""Save a complete final bundle, then retire its original working JSON."""
from pathlib import Path
from storyboard_paths import media_root, is_final_dir
from datetime import datetime
import copy, shutil, re, uuid, hashlib, json
from agent.core import read
from asset_plan import sync_plan
from project_naming import dated_path


def _lineage_source(project, source):
    """定稿追溯到稳定的结构剧本，而非会被归档的分镜工作 JSON。"""
    project, source = Path(project).resolve(), Path(source).resolve()
    if source.name == 'episode.json' and is_final_dir(source.parent.name):
        return None
    try:
        data = read(source)
        linked = str(data.get('source_script') or '').strip() if isinstance(data, dict) else ''
        candidate = Path(linked)
        if linked:
            candidate = candidate.resolve() if candidate.is_absolute() else (project / candidate).resolve()
            if candidate.is_relative_to(project) and candidate.is_file():
                return candidate
    except (OSError, ValueError):
        pass
    return source


def _record_lineage(project, episodefile, source):
    lineage_source = _lineage_source(project, source)
    if lineage_source is not None:
        from artifact_lineage import record
        record(project, episodefile, lineage_source, 'final_storyboard')

def finalize(project,episode_dir,source):
    from asset_context import library_dir,references
    from storyboard_catalog_service import resolve_source
    from storyboard_lifecycle import signature,retire
    project=Path(project).resolve();base=library_dir(project,episode_dir)
    source=resolve_source(project,source);original=source.read_bytes()
    original_hash=hashlib.sha256(original).hexdigest()
    frame_base=media_root(source)
    rows=sync_plan(project,base,source)
    mapping=read(base/'assets/资产清单/名称编号对照.json')
    if not isinstance(mapping,dict):mapping={}
    episode=copy.deepcopy(read(source));missing=[];used=set()
    if not isinstance(episode,dict) or not isinstance(episode.get('shots'),list):raise ValueError('分镜JSON格式错误：顶层须为对象且 shots 为数组')
    from prop_assets import normalize_shot
    planned=read(base/'assets/资产清单/assets.json')
    if not isinstance(planned,dict):planned={}
    episode['shots']=[normalize_shot(shot,planned) for shot in episode['shots']]
    for shot in episode['shots']:
        refs=[];bindings={}
        for prefix,key,many in [('CHAR','characters',True),('LOC','location',False),('PROP','props',True)]:
            values=shot.get(key,[] if many else None)
            values=values if isinstance(values,list) else [values] if values else []
            resolved=[]
            for value in values:
                if isinstance(value,dict):value=value.get('id') or value.get('name')
                aid=value if isinstance(value,str) and re.fullmatch(prefix+r'_\d{3,}',value) else mapping.get(prefix+':'+str(value))
                if not aid or aid not in rows:raise ValueError('无法匹配资产编号：'+str(value))
                resolved.append(aid);used.add(aid)
                bindings[aid]={'name':rows[aid].get('name',aid),'image':rows[aid].get('image') if rows[aid]['status']=='已导入' else None,'status':rows[aid]['status']}
                if rows[aid]['status']!='已导入':missing.append(aid)
                elif rows[aid]['image'] not in refs:refs.append(rows[aid]['image'])
            shot[key]=resolved if many else (resolved[0] if resolved else '')
        for prefix,value in references(shot):
            aid=value if value in rows else mapping.get(prefix+':'+value)
            if not aid or aid not in rows:raise ValueError('无法匹配资产编号：'+value)
            if aid in bindings:continue
            used.add(aid)
            bindings[aid]={'name':rows[aid].get('name',aid),'image':rows[aid].get('image') if rows[aid]['status']=='已导入' else None,'status':rows[aid]['status']}
            if rows[aid]['status']!='已导入':missing.append(aid)
            elif rows[aid]['image'] not in refs:refs.append(rows[aid]['image'])
        for line in shot.get('dialogue',[]):
            if not isinstance(line,dict):continue
            speaker=line.get('speaker')
            line['speaker']=mapping.get('CHAR:'+str(speaker),speaker)
        shot['reference_images']=refs;shot['asset_bindings']=bindings
        shot['asset_status']='待补齐资产' if any(a['status']!='已导入' for a in bindings.values()) else '已匹配资产'
    # 第 61 期 v0.8 任务 10：按三元组切批次并回填 batch_id（B01…），顺手补齐那九个必填字段。
    # 只增不改——老的 id／characters／location／duration 一个都不动，validate_episode 照旧过。
    try:
        from shot_batches import assign
        episode['shots']=list(assign(episode['shots']))
    except Exception:
        pass
    episode['missing_assets']=sorted(set(missing))
    episode['assets_ready']=not missing
    from writing import validate_episode
    assets={aid:{k:v for k,v in rows[aid].items() if k!='status'} for aid in used}
    validate_episode(episode,frame_base,assets)
    wanted=signature(episode,assets,base)
    from project_stages import stage
    # 定稿的唯一写入目录。此前读取 ``分镜拆分``、写入 ``分镜``，下一次定稿扫不到上次
    # 产物而重复创建；旧目录仅兼容读取历史项目。
    finals_root=stage(project, 'final')/'分镜'
    legacy_finals_root=stage(project, 'final')/'分镜拆分'
    existing_files=[]
    for root in (finals_root,legacy_finals_root):
        if root.is_dir():
            existing_files.extend(p for p in root.glob('*/episode.json') if is_final_dir(p.parent.name))
    for existing in sorted(existing_files,key=lambda p:p.stat().st_mtime,reverse=True):
        try:matches=bool(wanted and signature(read(existing),read(existing.with_name('assets.json')),existing.parent)==wanted)
        except (OSError,ValueError,KeyError):continue
        if matches:
            from storyboard_lifecycle import is_working_source
            _record_lineage(project, existing, source)
            if is_working_source(project,source):
                retire(project,source,existing,original_hash)
            return existing.parent
    dest=dated_path(stage(project,'final')/'分镜',re.sub(r'[^A-Za-z0-9_-]','_',episode['episode_id'])+'_分镜定稿')
    # A final is a single maintained document, including later asset updates.
    if source.name=='episode.json' and is_final_dir(source.parent.name):
        dest=source.parent
    else:
        from storyboard_storage import ALIAS_FILE
        aliasfile=finals_root/ALIAS_FILE
        aliases=read(aliasfile) if aliasfile.is_file() else {}
        if not isinstance(aliases,dict):aliases={}
        relative=source.relative_to(project).as_posix() if source.is_relative_to(project) else ''
        previous=(project/aliases[relative]).resolve() if relative in aliases else None
        if previous and previous.is_relative_to(finals_root) and is_final_dir(previous.parent.name) and previous.is_file():
            if read(previous).get('episode_id')==episode.get('episode_id'):dest=previous.parent
    dest.mkdir(parents=True,exist_ok=True)
    image_rewrites={}
    for aid,asset in assets.items():
        if aid in missing:
            asset.pop('image',None);continue
        rel=Path(asset['image']);target=dest/rel;target.parent.mkdir(parents=True,exist_ok=True)
        if target.is_file() and target.read_bytes()!=(base/rel).read_bytes():
            target=target.with_name(target.stem+'_'+hashlib.sha256((base/rel).read_bytes()).hexdigest()[:12]+target.suffix)
            image_rewrites[rel.as_posix()]=target.relative_to(dest).as_posix()
            asset['image']=target.relative_to(dest).as_posix()
        if (base/rel).resolve()!=target.resolve():shutil.copy2(base/rel,target)
    for shot in episode['shots']:
        shot['reference_images']=[image_rewrites.get(value,value) for value in shot['reference_images']]
        for binding in shot['asset_bindings'].values():
            if binding.get('image'):binding['image']=image_rewrites.get(binding['image'],binding['image'])
    output_base=media_root(dest/'episode.json')
    (output_base/'frames').mkdir(exist_ok=True)
    for shot in episode['shots']:
        frame=(frame_base/shot['frame']).resolve()
        if frame.is_relative_to(frame_base) and frame.is_file():
            target=output_base/shot['frame'];target.parent.mkdir(parents=True,exist_ok=True)
            if frame.resolve()!=target.resolve():
                if target.exists() and frame.read_bytes()!=target.read_bytes():
                    target=target.with_name(target.stem+'_'+uuid.uuid4().hex[:8]+target.suffix)
                    shot['frame']=target.relative_to(output_base).as_posix()
                if not target.exists():shutil.copy2(frame,target)
    if hashlib.sha256(source.read_bytes()).hexdigest()!=original_hash:
        raise ValueError('分镜在同步期间已修改，请重新生成；原JSON未改动')
    validate_episode(episode,output_base,assets)
    episodefile=dest/'episode.json';assetfile=dest/'assets.json'
    try:
        from storyboard_storage import publish_final_bundle
        from stage_execution_service import publish_stage_text
        def validate_episode_text(value):
            validate_episode(json.loads(value), output_base, assets)
            return True
        publish_stage_text(
            episodefile, json.dumps(episode, ensure_ascii=False, indent=2), validate_episode_text,
            lambda _published: publish_final_bundle(
                episodefile, assetfile, episode, assets,
                lambda saved_episode, saved_assets: validate_episode(saved_episode, output_base, saved_assets)),
        )
        _record_lineage(project, episodefile, source)
    except Exception: raise
    from storyboard_lifecycle import is_working_source
    if is_working_source(project,source):
        retire(project,source,dest/'episode.json',original_hash)
    return dest
