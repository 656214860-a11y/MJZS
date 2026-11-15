"""Shared asset library and the explicitly adopted storyboard for a project."""
from pathlib import Path
import re
from agent.core import read
from contract.project_context import ProjectContext
import contract.pet_bus as pet_bus


def _project_root(project=None, *, context=None):
    """读取项目配置时消费 L3 注入的上下文，兼容旧路径调用。"""
    if context is None:
        return Path(project).resolve()
    if not isinstance(context, ProjectContext):
        raise TypeError('资产上下文需要由 L3 注入 ProjectContext。')
    root = context.root.resolve()
    if project is not None and Path(project).resolve() != root:
        raise ValueError('项目路径与注入的 ProjectContext 不一致。')
    return root


def generated_dir(base, *, create=True):
    """全部模型批量生成图片的统一存放目录。"""
    path=Path(base).resolve()/'生成资产'
    if create:path.mkdir(parents=True,exist_ok=True)
    return path


def ensure_browser_directory(base, kind, *, create=True):
    """创建并返回资产页面可浏览的分类目录，不涉及资产内容发布。"""
    base = Path(base).resolve()
    if kind not in ('all', 'scenes', 'characters', 'props'):
        raise ValueError('资产分类无效')
    path = base / 'assets'
    if kind != 'all':
        path /= kind
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path

def library_dir(project=None, fallback=None, *, context=None):
    project=_project_root(project, context=context)
    cfg=read(project/'config.json') if (project/'config.json').is_file() else {}
    from contract.stage_path_service import existing_dir, write_dir, LEGACY_NUMBERED
    standard=write_dir(project, 'assets')
    value=cfg.get('asset_library_dir')
    if (standard/'assets.json').is_file() or (standard/'assets/资产清单/assets.json').is_file():
        value=standard
    candidate=value or fallback or cfg.get('episode_dir')
    if not candidate or Path(candidate).name == LEGACY_NUMBERED['assets']:
        candidate=existing_dir(project, 'assets')
    base=(project/Path(candidate)).resolve()
    if not base.is_relative_to(project):raise ValueError('资产目录超出当前项目')
    return base


def active_source(project=None, storyboard=None, fallback=None, *, context=None):
    # Source resolution is catalog domain logic; depend on the headless service
    # rather than the legacy catalog facade to keep assets out of that cycle.
    from storyboard_catalog_service import resolve_source, default_source
    project=_project_root(project, context=context)
    prefs=read(project/'ui_settings.json') if (project/'ui_settings.json').is_file() else {}
    record=library_dir(project,fallback, context=context)/'assets/资产清单/来源.json'
    remembered=read(record).get('storyboard') if record.is_file() else None
    value=storyboard or prefs.get('frame_json') or remembered
    if value:
        path=resolve_source(context,value)
        if not path.is_file():raise ValueError('当前分镜JSON已移动或删除，请重新采用分镜：'+str(path))
        return path
    for path in (default_source(context),library_dir(project,fallback, context=context)/'episode.json'):
        if path.is_file():return path.resolve()
    raise ValueError('尚未采用分镜JSON，请先在'+pet_bus.stage_step('storyboard')+'点「手动采用分镜」')


def references(shot):
    """All declared assets, including assets visible only in the first frame."""
    from contract.prop_assets import normalize_shot
    shot=normalize_shot(shot)
    seen=set()
    for prefix,key in [('CHAR','characters'),('LOC','location'),('PROP','props'),(None,'first_frame_assets')]:
        values=shot.get(key,[])
        values=values if isinstance(values,list) else [values] if values else []
        for value in values:
            value=(value.get('id') or value.get('name')) if isinstance(value,dict) else value
            if not isinstance(value,str) or not value.strip():continue
            value=value.strip();kind=prefix
            if kind is None:
                match=re.fullmatch(r'(CHAR|LOC|PROP)_\d{3,}',value)
                if not match:continue
                kind=match[1]
            if (kind,value) not in seen:
                seen.add((kind,value));yield kind,value


def scope_sources(project=None,scope='all', *, context=None):
    from storyboard_adoption_contract import adopted
    project=_project_root(project, context=context)
    result=adopted(project)
    if scope=='current':
        if not result:return []
        current=active_source(project, context=context)
        return [current] if current in result else [result[0]]
    return result


_SHOT_REFERENCE_FIELDS = (('characters', 'CHAR'), ('props', 'PROP'),
                          ('first_frame_assets', ''), ('location', 'LOC'))


def _reference_fields(shot, aid):
    """这一项资产在这个镜头里从哪些字段被引用（找不到返回空列表）。"""
    target = str(aid or '').strip()
    fields = []
    for key, _prefix in _SHOT_REFERENCE_FIELDS:
        values = shot.get(key)
        values = values if isinstance(values, list) else [values] if values else []
        for value in values:
            value = (value.get('id') or value.get('name')) if isinstance(value, dict) else value
            if isinstance(value, str) and value.strip() == target:
                fields.append(key)
                break
    return fields


def referencing_shots(shots, aid):
    """哪些镜头引用了这一项资产：返回 ``[{'id', 'fields'}]``，fields 说明命中字段。

    与 :func:`references` 同口径（先 normalize_shot 再取声明资产）；用于「改动会影响哪些
    镜头」的只读影响视图，不写盘、不改镜头编号。
    """
    from contract.prop_assets import normalize_shot
    target = str(aid or '').strip()
    rows = []
    if not target:
        return rows
    for index, shot in enumerate(shots or [], 1):
        if not isinstance(shot, dict):
            continue
        normalized = normalize_shot(shot)
        if not any(value == target for _kind, value in references(normalized)):
            continue
        identifier = str(normalized.get('id') or shot.get('id') or '').strip() or '#%d' % index
        rows.append({'id': identifier, 'fields': _reference_fields(normalized, target)})
    return rows
