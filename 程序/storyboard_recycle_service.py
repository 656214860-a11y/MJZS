"""Headless planning, recycle, and restore operations for storyboard files."""
from datetime import datetime
from pathlib import Path
import uuid


def recycle_plan(project, kind, path):
    """Return the complete safe deletion group without moving any file.

    This is deliberately a planning command: the UI can show its impact before
    the existing recycle executor makes any filesystem mutation.
    """
    from agent.core import read
    from storyboard_adoption_contract import adopted
    from stage_execution_service import storyboard_catalog as catalog
    from storyboard_catalog_service import linked_path
    from stage_execution_service import project_context
    from storyboard_paths import is_final_dir
    from project_stages import writing, structure, storyboard
    project = Path(project).resolve()
    path = Path(path)
    if kind not in ('script', 'storyboard'):
        raise ValueError('只能删除当前项目的剧本或分镜文件')
    scopes = ((writing(project), structure(project), project / 'writing') if kind == 'script'
              else (storyboard(project), project / 'storyboard'))
    source = path.resolve()
    if not any(source.is_relative_to(scope.resolve()) for scope in scopes):
        raise ValueError('只能删除当前项目的剧本或分镜文件')
    if path.is_symlink() or path.is_junction() or not source.is_file():
        raise ValueError('所选文件已移动或不可删除，请刷新列表')
    listed = any(entry['path'] == source for entry in catalog(project, kind))
    legacy_script = (kind == 'script' and source.is_relative_to((project / 'writing').resolve())
                     and source.suffix.lower() in {'.md', '.txt', '.docx'})
    if not listed and not legacy_script:
        raise ValueError('所选文件不在当前列表中，请刷新后重试')
    storyboards = [entry['path'] for entry in catalog(project, 'storyboard')
                   if entry['path'].suffix.lower() == '.json']
    linked = []
    if kind == 'script':
        for candidate in storyboards:
            if linked_path(project_context(project), read(candidate).get('source_script')) == source and not is_final_dir(candidate.parent.name):
                linked.append(candidate)
    targets = list(dict.fromkeys([source, *linked]))
    for target in targets:
        if (not target.is_file() or not target.resolve().is_relative_to(project)
                or target.is_symlink() or target.is_junction()):
            raise ValueError('关联文件超出当前项目或包含链接，已停止删除')
    affected_json = [candidate for candidate in storyboards if candidate in targets]
    if affected_json and any(candidate in affected_json for candidate in adopted(project)):
        raise ValueError('关联 JSON 已用于后续制作，请先取消这些 JSON 的采用，再删除。')
    return targets


def detach_video_refs(project, targets):
    """Remove deleted-JSON source links while preserving generated videos."""
    from agent.core import read, save
    from stage_execution_service import storyboard_resolve_source as resolve_source
    project = Path(project).resolve()
    targets = {Path(target).resolve() for target in targets}
    configs = [project / 'config.json', *(project / 'cloud_video').glob('*/config.json')]
    touched = 0
    for config in configs:
        if not config.is_file():
            continue
        data = read(config)
        if not isinstance(data, dict):
            continue
        value = data.get('episode_file')
        if value and resolve_source(project, value) in targets:
            data.pop('episode_file', None)
            save(config, data)
            touched += 1
    return touched


def recycle_files(project, kind, paths):
    """Move verified files to one recoverable batch and repair related state."""
    from agent.core import read, save
    from project_stages import writing, structure, storyboard
    from storyboard_catalog_service import linked_path
    from stage_execution_service import project_context
    from storyboard_selection import remember_many, selected_many
    project = Path(project).resolve()
    sources = [Path(path).resolve() for path in paths]
    targets = list(dict.fromkeys(
        item for source in sources for item in recycle_plan(project, kind, source)))
    selections = {group: selected_many(project, group) for group in ('script', 'storyboard')}
    folder = project / '工作流任务' / '回收站' / (
        datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '_' + uuid.uuid4().hex[:6])
    moves = [(item, folder / item.relative_to(project)) for item in targets]
    if any(not dest.resolve().is_relative_to(project) or dest.exists() for _, dest in moves):
        raise ValueError('回收路径无效')
    save(folder / '恢复位置.json', {'files': [
        {'original': source.relative_to(project).as_posix(),
         'recycled': dest.relative_to(project).as_posix()}
        for source, dest in moves]})
    moved = []
    try:
        for source, dest in moves:
            dest.parent.mkdir(parents=True, exist_ok=True)
            source.rename(dest)
            moved.append((source, dest))
    except OSError:
        for source, dest in reversed(moved):
            source.parent.mkdir(parents=True, exist_ok=True)
            dest.rename(source)
        raise
    for group, chosen in selections.items():
        remember_many(project, group, [path for path in chosen if path not in targets])
    prefs_file = project / 'ui_settings.json'
    prefs = read(prefs_file) if prefs_file.is_file() else {}
    if not isinstance(prefs, dict):
        prefs = {}
    if linked_path(project_context(project), prefs.get('final_storyboard_json')) in targets:
        prefs['final_storyboard_json'] = ''
        save(prefs_file, prefs)
    detach_video_refs(project, targets)
    scopes = ((writing(project), structure(project), project / 'writing') if kind == 'script'
              else (storyboard(project), project / 'storyboard'))
    roots = {scope.resolve() for scope in scopes}
    for parent in {source.parent for source in sources}:
        if parent.resolve() not in roots and parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
    return folder


def latest_recycle_batch(project):
    """Return the newest manually-created storyboard recycle batch, if any."""
    from agent.core import read
    project = Path(project).resolve()
    base = project / '工作流任务' / '回收站'
    if not base.is_dir():
        return None
    for folder in sorted((path for path in base.iterdir() if path.is_dir()),
                         key=lambda path: path.name, reverse=True):
        try:
            data = read(folder / '恢复位置.json')
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and isinstance(data.get('files'), list):
            return folder, [str(row.get('original') or '') for row in data['files']
                            if isinstance(row, dict) and row.get('original')]
    return None


def restore_latest_recycled_files(project):
    """Restore the newest manual storyboard recycle batch."""
    candidate = latest_recycle_batch(project)
    if candidate is None:
        raise ValueError('没有可恢复的剧本或分镜删除记录')
    folder, names = candidate
    from storage_maintenance import restore_recycle_batch
    return names, restore_recycle_batch(project, folder)
