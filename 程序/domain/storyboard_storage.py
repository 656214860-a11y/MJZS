"""Normalize working storyboard filenames and coalesce only equal JSON documents."""
import hashlib,json,os,re,time
from pathlib import Path
import logging
from functools import wraps
from agent.core import read
from infra.file_cache import read_stable_json_snapshot
from contract.project_stages import storyboard
from infra.storage_maintenance import recycle_paths

ALIAS_FILE='文件路径映射.json'


def _storage_result(operation):
    @wraps(operation)
    def run(*args, **kwargs):
        try:
            from contract.service_contract import SystemError, success
            return success(operation(*args, **kwargs))
        except OSError as exc:
            logging.getLogger('storyboard_storage').exception('分镜存储写入失败')
            return SystemError('分镜文件未能保存，请检查磁盘或文件占用后重试。',
                               data={'cause': str(exc), 'operation': operation.__name__})
    return run


def _require_gateway(gateway, *operations):
    if not isinstance(gateway, dict):
        raise TypeError('分镜发布必须由 L3 注入 gateway')
    missing = [name for name in operations if not callable(gateway.get(name))]
    if missing:
        raise TypeError('分镜 gateway 缺少：' + '、'.join(missing))
    return gateway


def _publish_final_bundle(episodefile, assetfile, episode, assets, validate, *, gateway=None):
    """原子发布定稿双索引；校验失败时恢复本次之前的 JSON。"""
    gateway = _require_gateway(gateway, 'publish_json', 'publish_bytes', 'remove_temporary_file')
    publish_json, publish_bytes = gateway['publish_json'], gateway['publish_bytes']
    episodefile, assetfile = Path(episodefile), Path(assetfile)
    old_episode = episodefile.read_bytes() if episodefile.is_file() else None
    old_assets = assetfile.read_bytes() if assetfile.is_file() else None
    try:
        publish_json(assetfile, assets)
        publish_json(episodefile, episode)
        validate(read(episodefile), read(assetfile))
    except Exception:
        from infra.file_cache import remove_temporary_file
        for file, raw in ((episodefile, old_episode), (assetfile, old_assets)):
            if raw is not None:
                publish_bytes(file, raw)
            elif file.is_file():
                gateway['remove_temporary_file'](file)
        raise


@_storage_result
def publish_final_bundle(episodefile, assetfile, episode, assets, validate, *, gateway=None):
    return _publish_final_bundle(episodefile, assetfile, episode, assets, validate, gateway=gateway)


def working_roots(project):
    """当前分镜目录优先，旧英文目录仅作历史兼容读取。"""
    project = Path(project).resolve()
    return (storyboard(project) / '分镜拆分', project / 'storyboard' / '分镜拆分')


def default_source(project):
    """当前分镜来源的低层只读判定；不经过目录页或视频影响扫描。"""
    project = Path(project).resolve()
    prefs = read(project / 'ui_settings.json') if (project / 'ui_settings.json').is_file() else {}
    value = prefs.get('storyboard_file') if isinstance(prefs, dict) else None
    selected = (project / value).resolve() if value else None
    if selected and selected.is_relative_to(project) and selected.suffix == '.json' and selected.is_file():
        return selected
    for root in working_roots(project):
        candidates = sorted(root.glob('EP*_分镜.json'), key=lambda path: path.stat().st_mtime, reverse=True)
        if candidates:
            return candidates[0]
    working = working_roots(project)[0]
    for path in (working / 'episode.json', storyboard(project) / 'episode.json'):
        if path.is_file():
            return path
    return working / 'episode.json'


def resolve_source(project, path):
    """按别名与旧 episode 占位解析当前分镜来源；只读，不经过目录服务。"""
    project = Path(project).resolve()
    path = resolved_alias(project, Path(path))
    legacy_episode = project / 'storyboard' / 'episode.json'
    if not path.exists() and path in (storyboard(project) / 'episode.json', legacy_episode):
        return default_source(project).resolve()
    return path


def snapshot(path):
    data,raw,after=read_stable_json_snapshot(path)
    if not isinstance(data,dict) or not isinstance(data.get('shots'),list) or not data['shots']:raise ValueError('非分镜文件')
    if not isinstance(data.get('episode_id'),str) or not re.fullmatch(r'EP\d{3,}',data['episode_id']):raise ValueError('集号不明确')
    if not all(isinstance(s,dict) for s in data['shots']):raise ValueError('分镜尚未写完')
    digest=hashlib.sha256(json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return data,digest,raw,after

def canonical_name(data):
    from contract.file_naming import generate_existing
    return generate_existing('storyboard_working', episode_id=data['episode_id'], title=data.get('title'))

def resolved_alias(project,path):
    project=Path(project).resolve();path=(project/Path(path)).resolve()
    if path.exists():return path
    if not path.is_relative_to(project):return path
    for root in working_roots(project):
        file=root/ALIAS_FILE
        try:aliases=read(file) if file.is_file() else {}
        except (OSError,ValueError):continue
        if not isinstance(aliases,dict):continue
        target=aliases.get(path.relative_to(project).as_posix())
        if not target:continue
        dest=(project/target).resolve()
        if dest.is_relative_to(project) and dest.is_file():return dest
    return path

def _references(project,mapping, gateway=None):
    """兼容既有定稿退役链；新整理链必须由 L3 显式传入网关。"""
    if gateway is None:
        from agent.core import save
        gateway = {'publish_json': save}
    def replace(value):
        if isinstance(value,dict):return {k:replace(v) for k,v in value.items()}
        if isinstance(value,list):return [replace(v) for v in value]
        if isinstance(value,str) and value.lower().endswith('.json'):
            try:
                path=(project/value).resolve()
                if path in mapping:
                    target=mapping[path]
                    return str(target) if Path(value).is_absolute() else target.relative_to(project).as_posix()
            except (OSError,ValueError):pass
        return value
    configs=[project/'ui_settings.json',project/'config.json',
             *(project/'cloud_video').glob('*/config.json'),
             *(project/'episode').glob('assets/资产清单/来源.json')]
    main=project/'config.json'
    if main.is_file():
        main_cfg=read(main)
        value=main_cfg.get('episode_dir') if isinstance(main_cfg,dict) else None
        if value:
            base=(project/value).resolve()
            if base.is_relative_to(project):configs.append(base/'assets/资产清单/来源.json')
    for config in dict.fromkeys(configs):
        if not config.is_file() or config.is_symlink() or not config.resolve().is_relative_to(project):continue
        original=read(config);updated=replace(original)
        if updated.get('episode_file')!=original.get('episode_file') and updated.get('episode_file'):
            if config==main and not updated.get('asset_library_dir'):
                from contract.project_stages import assets
                updated['asset_library_dir']=str(assets(project))
            updated['episode_dir']=str((project/updated['episode_file']).resolve().parent)
        if updated!=original:gateway['publish_json'](config,updated)

def _normalize(project,min_age=3, *, gateway=None):
    gateway = _require_gateway(gateway, 'publish_json', 'publish_bytes_new', 'recycle_paths')
    project=Path(project).resolve();changed=[];now=time.time()
    for root in working_roots(project):
        if not root.is_dir() or root.is_symlink() or root.is_junction() or not root.resolve().is_relative_to(project):continue
        groups={}
        for path in root.glob('*.json'):
            if path.is_symlink() or not path.is_file() or path.name==ALIAS_FILE:continue
            try:
                snap=snapshot(path)
                # ``min_age=0`` is the explicit synchronous-maintenance mode.
                # Do not reject a file merely because ``now`` was sampled a few
                # clock ticks before its stat result.
                if min_age > 0 and now-snap[3].st_mtime < min_age:continue
                groups.setdefault(snap[1],[]).append((path,snap))
            except (OSError,ValueError):continue
        alias_file=root/ALIAS_FILE
        aliases=read(alias_file) if alias_file.exists() else {}
        if not isinstance(aliases,dict):aliases={}
        for digest,files in groups.items():
            data=files[0][1][0];target=root/canonical_name(data)
            if target.exists():
                try:
                    if snapshot(target)[1]!=digest:
                        target=target.with_name(target.stem+'_版本_'+digest[:8]+'.json')
                except (OSError,ValueError):continue
            source,snap=next(((p,s) for p,s in files if p==target),files[0])
            if target.is_symlink():continue
            try:
                if not target.exists():
                    if snapshot(source)[1]!=digest:continue
                    gateway['publish_bytes_new'](target,snap[2])
                    os.utime(target,ns=(snap[3].st_atime_ns,snap[3].st_mtime_ns))
                if snapshot(target)[1]!=digest:continue
                duplicates=[p for p,s in files if p!=target and snapshot(p)[1]==digest]
                mapping={p.resolve():target.resolve() for p in duplicates}
                if not mapping:continue
                _references(project,mapping,gateway)
                for old,new in mapping.items():aliases[old.relative_to(project).as_posix()]=new.relative_to(project).as_posix()
                gateway['publish_json'](alias_file,aliases)
                # Duplicate work files are user-visible: preserve them in the project recycle batch.
                moved=gateway['recycle_paths'](project, duplicates, '合并重复分镜')
                moved_sources={item['source'] for item in moved}
                for old in duplicates:
                    if old.resolve().relative_to(project).as_posix() in moved_sources:
                        changed.append((str(old),str(target)))
            except (OSError,ValueError):continue
    return changed


@_storage_result
def normalize(project,min_age=3, *, gateway=None):
    return _normalize(project, min_age, gateway=gateway)


def unique_entries(entries,project):
    """Read-only fallback for files too new to normalize; never merge final bundles."""
    root=(storyboard(project)/'分镜拆分').resolve();groups={};others=[]
    for entry in entries:
        path=entry['path']
        if path.parent!=root or path.suffix.lower()!='.json':others.append(entry);continue
        try:data,digest,_,_=snapshot(path)
        except (OSError,ValueError):others.append(entry);continue
        key=(data['episode_id'],digest)
        rank=(path.name==canonical_name(data),path.name!='episode.json',entry['created'])
        if key not in groups or rank>groups[key][0]:groups[key]=(rank,entry)
    result=others+[item[1] for item in groups.values()]
    counts={}
    for (episode,digest),(_,entry) in groups.items():counts[episode]=counts.get(episode,0)+1
    for (episode,digest),(_,entry) in groups.items():
        if counts[episode]>1:entry['title']+=' · 内容版本 '+digest[:8]
    return sorted(result,key=lambda e:(e['created'],str(e['path'])),reverse=True)


def _normalize_for_desktop(desktop, *, gateway=None):
    videos=list(getattr(desktop,'video_sessions',{}).values())
    if getattr(desktop,'worker',False) or any(getattr(v,'busy',False) for v in videos):return []
    changed=_normalize(desktop.root, gateway=gateway)
    mapping={Path(old).resolve():Path(new).resolve() for old,new in changed}
    studios=[getattr(desktop,'studio',None)]+[getattr(v,'studio',None) for v in videos]
    for studio in studios:
        if studio is None:continue
        path=getattr(studio,'episode_path',None)
        if path and Path(path).resolve() in mapping:studio.episode_path=mapping[Path(path).resolve()]
        cfg=getattr(studio,'cfg',{})
        value=cfg.get('episode_file')
        if value and (Path(desktop.root)/value).resolve() in mapping:cfg['episode_file']=str(mapping[(Path(desktop.root)/value).resolve()])
    return changed


@_storage_result
def normalize_for_desktop(desktop, *, gateway=None):
    return _normalize_for_desktop(desktop, gateway=gateway)
