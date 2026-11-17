"""Save a complete final bundle, then retire its original working JSON."""
import app_logging
from pathlib import Path
from contract.storyboard_paths import media_root, is_final_dir
import copy, shutil, re, uuid, hashlib, json
from agent.core import read
from domain.asset_plan import _sync_plan
from domain.project_naming import dated_path
from contract.file_naming import generate_existing
from orchestrator.project_context_factory import project_context


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
        from contract.artifact_lineage import record
        record(project, episodefile, lineage_source, 'final_storyboard')

def _batch_plan_markdown(episode):
    """批次划分说明（人读）：只从定稿镜头派生，不含时间戳。"""
    from contract.shot_batches import BATCH_MAX_SHOTS, BATCH_SECONDS, batches, duration
    shots = episode.get('shots') if isinstance(episode, dict) else None
    shots = shots if isinstance(shots, list) else []
    grouped = batches(shots)
    lines = ['# 批次划分说明', '',
             '- 集号：' + str(episode.get('episode_id') or ''),
             '- 镜头数：%d' % len(shots),
             '- 批次：%d' % len(grouped),
             '- 切批依据：按三元组（scene_id、character_ids、costume_id）划分；'
             '三元组变化、单批满 %d 镜或累计超过 %d 秒即切新批。'
             % (BATCH_MAX_SHOTS, BATCH_SECONDS), '']
    for name, items in grouped.items():
        seconds = sum(duration(item) for item in items)
        ids = '、'.join(str(item.get('shot_id') or item.get('id') or '') for item in items)
        first = items[0] if items else {}
        chars = '、'.join(str(value) for value in (first.get('character_ids') or []))
        lines += ['## ' + name, '',
                  '- 镜头：%s（%d 镜）' % (ids, len(items)),
                  '- 合计时长：%d 秒' % seconds,
                  '- 三元组：场景 %s／角色 %s／状态变体 %s'
                  % (str(first.get('scene_id') or '（未指定）'), chars or '（无）',
                     str(first.get('costume_id') or '（未指定）')), '']
    return '\n'.join(lines).rstrip('\n') + '\n'


def _shot_table_markdown(episode):
    """一镜一行的镜头表（人读）：只从定稿镜头派生，不含时间戳。"""
    from contract.shot_batches import duration
    shots = episode.get('shots') if isinstance(episode, dict) else None
    shots = shots if isinstance(shots, list) else []
    lines = ['# 镜头表', '',
             '| 镜头号 | 批次 | 场景 | 角色 | 时长（秒） |',
             '| --- | --- | --- | --- | --- |']
    for shot in shots:
        if not isinstance(shot, dict):
            continue
        chars = '、'.join(str(value) for value in (shot.get('character_ids') or []))
        cells = (str(shot.get('shot_id') or shot.get('id') or ''),
                 str(shot.get('batch_id') or ''),
                 str(shot.get('scene_id') or ''),
                 chars,
                 str(duration(shot)))
        lines.append('| ' + ' | '.join(cell.replace('|', '／') for cell in cells) + ' |')
    return '\n'.join(lines) + '\n'


def _publish_final_docs(project, episode):
    """在定稿写出成功后，按 stage_layout 声明的 docs/ 派生两份人读 Markdown。

    路径来自 L0 权威（dirname_of＋paths），发布沿用 finalize 写 episode.json 的同一
    L3 入口 ``publish_stage_text``；不直接 save_text。切批失败等路径不会走到这里。
    """
    from contract.stage_layout import dirname_of, paths
    docs = paths(project, dirname_of('final'))['docs']
    from stage_execution_service import publish_stage_text
    for name, text in (('batch_plan.md', _batch_plan_markdown(episode)),
                       ('shot_table.md', _shot_table_markdown(episode))):
        publish_stage_text(docs / name, text,
                           lambda value: bool(str(value).strip()), lambda _target: None)


def finalize(project,episode_dir,source,retire_working=None,*,gateway=None):
    from domain.asset_context import library_dir,references
    from stage_execution_service import storyboard_resolve_source as resolve_source
    from domain.storyboard_lifecycle import signature
    project=Path(project).resolve();base=library_dir(project,episode_dir)
    source=resolve_source(project,source);original=source.read_bytes()
    original_hash=hashlib.sha256(original).hexdigest()
    frame_base=media_root(source)
    rows=_sync_plan(project,base,source,gateway=gateway,context=project_context(project))
    mapping=read(base/'assets/资产清单/名称编号对照.json')
    if not isinstance(mapping,dict):mapping={}
    episode=copy.deepcopy(read(source));missing=[];used=set()
    if not isinstance(episode,dict) or not isinstance(episode.get('shots'),list):raise ValueError('分镜JSON格式错误：顶层须为对象且 shots 为数组')
    from contract.prop_assets import normalize_shot
    planned=read(base/'assets/资产清单/assets.json')
    if not isinstance(planned,dict):planned={}
    episode['shots']=[normalize_shot(shot,planned) for shot in episode['shots']];from infra.continuity_ledger import require_final_ready;require_final_ready(project,episode['shots'])
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
        from contract.shot_batches import assign
        episode['shots']=list(assign(episode['shots']))
    except Exception as exc:
        app_logging.swallowed()
        raise ValueError('批次划分失败，已中止定稿：'+str(exc)) from exc
    episode['missing_assets']=sorted(set(missing))
    episode['assets_ready']=not missing
    from domain.writing import validate_episode
    assets={aid:{k:v for k,v in rows[aid].items() if k!='status'} for aid in used}
    validate_episode(episode,frame_base,assets)
    wanted=signature(episode,assets,base)
    from contract.project_stages import stage
    # 定稿的唯一写入目录。此前读取 ``分镜拆分``、写入 ``分镜``，下一次定稿扫不到上次
    # 产物而重复创建；旧目录仅兼容读取历史项目。
    finals_root=stage(project, 'final')/'分镜'
    existing_files=[]
    from contract.stage_path_service import read_dirs
    for root in (folder / name for folder in read_dirs(project,'final') for name in ('分镜','分镜拆分')):
        if root.is_dir():
            existing_files.extend(p for p in root.glob('*/episode.json') if is_final_dir(p.parent.name))
    for existing in sorted(existing_files,key=lambda p:p.stat().st_mtime,reverse=True):
        try:matches=bool(wanted and signature(read(existing),read(existing.with_name('assets.json')),existing.parent)==wanted)
        except (OSError,ValueError,KeyError):continue
        if matches:
            from stage_execution_service import storyboard_working_source as is_working_source
            _record_lineage(project, existing, source)
            if is_working_source(project,source):
                if not callable(retire_working):raise TypeError('定稿退役需要 L3 编排入口。')
                retire_working(project,source,existing,original_hash)
            return existing.parent
    dest=dated_path(stage(project,'final')/'分镜',generate_existing('storyboard_final', episode_id=episode['episode_id']))
    # A final is a single maintained document, including later asset updates.
    if source.name=='episode.json' and is_final_dir(source.parent.name) and source.is_relative_to(finals_root):
        dest=source.parent
    else:
        from domain.storyboard_storage import ALIAS_FILE
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
            target=target.with_name(generate_existing('collision', stem=target.stem,
                                    token=hashlib.sha256((base/rel).read_bytes()).hexdigest()[:12], suffix=target.suffix))
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
                    target=target.with_name(generate_existing('collision', stem=target.stem,
                                            token=uuid.uuid4().hex[:8], suffix=target.suffix))
                    shot['frame']=target.relative_to(output_base).as_posix()
                if not target.exists():shutil.copy2(frame,target)
    if hashlib.sha256(source.read_bytes()).hexdigest()!=original_hash:
        raise ValueError('分镜在同步期间已修改，请重新生成；原JSON未改动')
    validate_episode(episode,output_base,assets)
    episodefile=dest/'episode.json';assetfile=dest/'assets.json'
    from stage_execution_service import publish_final_storyboard_bundle
    from stage_execution_service import publish_stage_text
    def validate_episode_text(value):
        validate_episode(json.loads(value), output_base, assets)
        return True
    publish_stage_text(
        episodefile, json.dumps(episode, ensure_ascii=False, indent=2), validate_episode_text,
        lambda _published: publish_final_storyboard_bundle(
            episodefile, assetfile, episode, assets,
            lambda saved_episode, saved_assets: validate_episode(saved_episode, output_base, saved_assets)),
    )
    _record_lineage(project, episodefile, source)
    _publish_final_docs(project, episode)
    from stage_execution_service import storyboard_working_source as is_working_source
    if is_working_source(project,source):
        if not callable(retire_working):raise TypeError('定稿退役需要 L3 编排入口。')
        retire_working(project,source,dest/'episode.json',original_hash)
    return dest
