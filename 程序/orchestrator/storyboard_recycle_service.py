"""Headless planning, recycle, and restore operations for storyboard files."""
from pathlib import Path

import contract.stage_layout as stage_layout
from storage_maintenance import recycle_paths

RECYCLE_REASON = '分镜页删除'    # 写进批次清单，「恢复最近删除」据此认出本页自己的批次


def recycle_plan(project, kind, path):
    """Return the complete safe deletion group without moving any file.

    This is deliberately a planning command: the UI can show its impact before
    the existing recycle executor makes any filesystem mutation.
    """
    from agent.core import read
    from domain.storyboard_adoption_contract import adopted
    from stage_execution_service import storyboard_catalog as catalog
    from domain.storyboard_catalog_service import linked_path
    from stage_execution_service import project_context
    from contract.storyboard_paths import is_final_dir
    from contract.project_stages import writing, structure, storyboard
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
    from contract.project_stages import writing, structure, storyboard
    from domain.storyboard_catalog_service import linked_path
    from stage_execution_service import project_context
    from orchestrator.storyboard_selection import remember_many, selected_many
    project = Path(project).resolve()
    sources = [Path(path).resolve() for path in paths]
    targets = list(dict.fromkeys(
        item for source in sources for item in recycle_plan(project, kind, source)))
    selections = {group: selected_many(project, group) for group in ('script', 'storyboard')}
    moved = recycle_paths(project, targets, RECYCLE_REASON)
    if not moved:
        raise ValueError('回收路径无效')
    folder = project.joinpath(*Path(moved[0]['recycle_path']).parts[:3])
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
    base = stage_layout.workflow_dir(project, '回收站')
    if not base.is_dir():
        return None
    for folder in sorted((path for path in base.iterdir() if path.is_dir()),
                         key=lambda path: path.name, reverse=True):
        try:
            data = read(folder / '恢复位置.json')
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        if data.get('reason') == RECYCLE_REASON and isinstance(data.get('items'), list):
            names = [str(row.get('source') or '') for row in data['items'] if isinstance(row, dict)]
            if any(names):
                return folder, [name for name in names if name]
        if isinstance(data.get('files'), list):      # 早期批次（R2276 之前）清单格式
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
