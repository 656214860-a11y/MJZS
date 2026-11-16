"""无界面的分镜/剧本目录扫描服务。

页面只负责把扫描结果显示到 Treeview；这里负责安全地遍历阶段目录，拒绝链接逃逸、
空文件和内部目录。这样文件发现可在不创建 Tk 窗口的测试或后台任务中复用。
"""
import os
import re
from pathlib import Path
from contract.project_context import ProjectContext


IGNORED = {'历史版本', '分镜历史', '剧本输入', 'frames', 'video_prompts', 'assets',
           '__pycache__', '首帧任务'}


def _context(value):
    if not isinstance(value, ProjectContext):
        raise TypeError('分镜目录项目路径需要由 L3 注入 ProjectContext。')
    return value


def working_dir(context):
    """Return the structured JSON storyboard workspace without creating it."""
    from contract.project_stages import storyboard
    return storyboard(_context(context).root) / '分镜拆分'


def document_dir(context):
    """Return the user-readable storyboard document directory without creating it."""
    from contract.project_stages import storyboard
    return storyboard(_context(context).root) / '分镜文档'


def discover_files(roots, suffixes, ignored, ignored_name=None):
    """逐一返回 ``(原路径, 解析路径, stat)``，不创建目录也不修改项目文件。

    ``解析路径`` 不再逐文件 ``Path.resolve()``：``os.walk(followlinks=False)`` 已排除链接目录，
    上面的循环又排除了符号链接／联接点目录与符号链接文件，且 ``root`` 在进入循环前已 resolve，
    因此 ``path`` 不含任何符号链接／联接点分量，逐文件 ``realpath`` 只是重复做 root 已做过的事。
    仍保留 ``is_relative_to(root)`` 的越界保护（此时等价于词法边界，实际隔离由链接排除承担）。
    """
    suffixes = {str(value).lower() for value in suffixes}
    ignored = set(ignored)
    for root in roots:
        root = Path(root).resolve()
        for base, directories, files in os.walk(root, followlinks=False):
            directories[:] = [name for name in directories
                              if name not in ignored
                              and not (Path(base) / name).is_symlink()
                              and not (Path(base) / name).is_junction()]
            for name in files:
                path = Path(base) / name
                if path.suffix.lower() not in suffixes or path.is_symlink():
                    continue
                if callable(ignored_name) and ignored_name(name):
                    continue
                try:
                    stat = path.stat()
                except OSError:
                    continue
                if not path.is_relative_to(root) or not stat.st_size:
                    continue
                yield path, path, stat


def content_preview(path):
    """Return a compact file preview without requiring a Tk widget."""
    path = Path(path)
    try:
        if path.suffix.lower() == '.json':
            from file_cache import read_json
            data = read_json(path)
            if isinstance(data, dict):
                return _board_preview(path, data)
        text = ''
        try:
            from infra.script_text_reader import script_text
            text = script_text(path)
        except Exception:
            text = path.read_text(encoding='utf-8-sig', errors='replace')
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return lines[0][:60] + ('…' if len(lines[0]) > 60 else '') if lines else path.stem
    except (OSError, ValueError, UnicodeError):
        return path.stem


def _board_preview(path, data):
    sid = data.get('episode_id', '')
    title = str(data.get('title', '')).strip()
    shots = data.get('shots')
    count = len(shots) if isinstance(shots, list) else 0
    try:
        label = ' · '.join(value for value in (sid, title) if value)
    except TypeError:
        return path.stem
    return (label + ' · ' + str(count) + '镜') if label else path.stem


def has_synced_assets(path):
    """Return whether a storyboard has the sibling asset registry required by final view."""
    try:
        return (Path(path).parent / 'assets.json').is_file()
    except OSError:
        return False


def file_snapshot(context, ignored=IGNORED):
    """Return a cheap, safe catalog change signature without parsing document content."""
    from contract.project_stages import writing, storyboard
    from contract.stage_path_service import read_dirs
    project = _context(context).root.resolve()
    roots = (writing(project).resolve(), storyboard(project).resolve(),
             (project / 'writing').resolve(), (project / 'storyboard').resolve(),
             *read_dirs(project, 'final'))
    rows = []
    for path, _resolved, stat in discover_files(
        tuple(dict.fromkeys(roots)), {'.md', '.txt', '.docx', '.json'}, ignored
    ):
        rows.append((str(path), stat.st_mtime_ns, stat.st_size))
    return tuple(sorted(rows))


def default_source(context):
    """Find the current storyboard source without loading the file-picker page."""
    from agent.core import read
    from contract.project_stages import storyboard
    project = _context(context).root
    prefs = read(project / 'ui_settings.json') if (project / 'ui_settings.json').is_file() else {}
    value = prefs.get('storyboard_file') if isinstance(prefs, dict) else None
    selected = (project / value).resolve() if value else None
    if selected and selected.is_relative_to(project.resolve()) and selected.suffix == '.json' and selected.is_file():
        return selected
    working = storyboard(project) / '分镜拆分'
    candidates = sorted(working.glob('EP*_分镜.json'), key=lambda path: path.stat().st_mtime, reverse=True)
    if candidates:
        return candidates[0]
    legacy = project / 'storyboard' / '分镜拆分'
    candidates = sorted(legacy.glob('EP*_分镜.json'), key=lambda path: path.stat().st_mtime, reverse=True)
    if candidates:
        return candidates[0]
    for path in (working / 'episode.json', storyboard(project) / 'episode.json'):
        if path.is_file():
            return path
    return working / 'episode.json'


def resolve_source(context, path):
    """Resolve aliases and legacy episode placeholders to a current storyboard source."""
    from domain.storyboard_storage import resolved_alias
    from contract.project_stages import storyboard
    project = _context(context).root.resolve()
    path = resolved_alias(project, Path(path))
    legacy_episode = project / 'storyboard' / 'episode.json'
    if not path.exists() and path in (storyboard(project) / 'episode.json', legacy_episode):
        return default_source(context).resolve()
    return path


def check_adoptable(paths):
    """Validate every selected storyboard before an adoption command mutates preferences."""
    from file_cache import read_json
    from domain.storyboard_adoption_contract import problem_text
    from contract.storyboard_paths import media_root
    from writing import validate_episode
    problems = []
    for path in paths:
        path = Path(path)
        try:
            validate_episode(read_json(path), media_root(path))
        except (OSError, ValueError) as exc:
            problems.append(f'{path.name}：' + problem_text(exc))
    if problems:
        raise ValueError('以下几份分镜还不能采用：\n' + '\n'.join(problems))


def _shot_assets(shot):
    """镜头引用的角色／场景／道具编号，用于判断「替换资产」。"""
    def name(value):
        if isinstance(value, dict):
            return str(value.get('id') or value.get('name') or value.get('编号') or '')
        return str(value)

    def group(value):
        values = value if isinstance(value, list) else [value] if value else []
        return tuple(sorted(item for item in (name(v) for v in values) if item))

    return (group(shot.get('characters')), group(shot.get('location')),
            group(shot.get('props')), group(shot.get('first_frame_assets')))


def _shot_dialogue(shot):
    lines = shot.get('dialogue')
    lines = lines if isinstance(lines, list) else []
    rows = []
    for line in lines:
        if isinstance(line, dict):
            rows.append((str(line.get('speaker') or line.get('character') or ''),
                         str(line.get('text') or ''),
                         str(line.get('start')), str(line.get('end'))))
        else:
            rows.append(('', str(line), '', ''))
    return tuple(rows)


def _shot_signature(shot):
    return {'duration': shot.get('duration'),
            'dialogue': _shot_dialogue(shot),
            'assets': _shot_assets(shot),
            'frame': str(shot.get('frame') or ''),
            'video_prompt': str(shot.get('video_prompt') or ''),
            'title': str(shot.get('title') or '')}


def _shot_rows(data):
    shots = data.get('shots') if isinstance(data, dict) else None
    shots = shots if isinstance(shots, list) else []
    return [(str(shot.get('id') or ''), shot, _shot_signature(shot))
            for shot in shots if isinstance(shot, dict)]


def _generated_video_shots(project):
    """已生成过视频的镜头编号：项目本地与云端工作集的任务状态文件（只读）。"""
    from file_cache import read_json
    project = Path(project)
    roots = [project]
    try:
        roots += [folder for folder in sorted((project / 'cloud_video').glob('*')) if folder.is_dir()]
    except OSError:
        pass
    found = set()
    for root in roots:
        db = root / 'data/state.json'
        try:
            data = read_json(db) if db.is_file() else {}
        except (OSError, ValueError):
            continue
        shots = data.get('shots') if isinstance(data, dict) else None
        if isinstance(shots, dict):
            found.update(str(sid) for sid, versions in shots.items() if versions)
    return found


def _impact_summary(episodes, frames, videos):
    added = sum(len(row['added']) for row in episodes)
    removed = sum(len(row['removed']) for row in episodes)
    changed = sum(len(row['changed']) for row in episodes)
    moved = sum(len(row['reordered']) for row in episodes)
    parts = []
    if added:
        parts.append('+%d 镜' % added)
    if removed:
        parts.append('-%d 镜' % removed)
    if changed:
        parts.append('改 %d 镜' % changed)
    if moved:
        parts.append('重排 %d 镜' % moved)
    if frames:
        parts.append('%d 个首帧将失效' % len(set(frames)))
    if videos:
        parts.append('%d 段视频将失效' % len(set(videos)))
    if parts:
        return '；'.join(parts)
    return '与已采用分镜一致' if episodes else ''


def adoption_impact(context, paths):
    """采用前的只读影响预览：候选分镜相对同集已采用分镜的新增／删除／改动与将失效媒体。

    基线按「同路径优先、否则同 episode_id」匹配；没有基线时全部镜头算新增。逐镜用
    稳定镜头编号对比，重排只报告、不换号。返回
    ``{'episodes': [...], 'frames': [...], 'videos': [...], 'summary': str}``。
    只读：不改采用清单、不改资产、不删文件、不改镜头编号。
    """
    from file_cache import read_json
    from domain.storyboard_adoption_contract import adopted as adopted_paths
    from contract.storyboard_paths import media_root
    project = _context(context).root.resolve()
    try:
        baseline_paths = list(adopted_paths(project))
    except (OSError, ValueError):
        baseline_paths = []
    baseline = []
    for path in baseline_paths:
        try:
            data = read_json(path)
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            baseline.append((Path(path).resolve(), data))
    generated = _generated_video_shots(project)
    episodes, frames, videos = [], [], []
    for raw in paths:
        try:
            candidate = Path(raw).resolve()
            data = read_json(candidate)
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict) or not isinstance(data.get('shots'), list):
            continue
        base_path, base = None, None
        for path, other in baseline:
            if path == candidate:
                base_path, base = path, other
                break
        if base is None:
            episode_id = str(data.get('episode_id') or '')
            for path, other in baseline:
                if episode_id and str(other.get('episode_id') or '') == episode_id:
                    base_path, base = path, other
                    break
        base_rows = _shot_rows(base) if base is not None else []
        candidate_rows = _shot_rows(data)
        base_ids = [sid for sid, _shot, _sig in base_rows if sid]
        candidate_ids = [sid for sid, _shot, _sig in candidate_rows if sid]
        base_index = {sid: (shot, sig) for sid, shot, sig in base_rows if sid}
        added = [sid for sid in candidate_ids if sid not in base_index]
        removed = [sid for sid in base_ids if sid not in set(candidate_ids)]
        changed = []
        for sid, _shot, sig in candidate_rows:
            if not sid or sid not in base_index:
                continue
            fields = [field for field, value in sig.items() if value != base_index[sid][1][field]]
            if fields:
                changed.append({'id': sid, 'fields': fields})
        common_base = [sid for sid in base_ids if sid in set(candidate_ids)]
        common_candidate = [sid for sid in candidate_ids if sid in base_index]
        reordered = [sid for index, sid in enumerate(common_candidate)
                     if index >= len(common_base) or common_base[index] != sid]
        invalid = set(removed)
        invalid.update(row['id'] for row in changed
                       if {'frame', 'assets', 'duration'} & set(row['fields']))
        for sid in sorted(invalid):
            shot = base_index.get(sid, ({}, {}))[0]
            name = str((shot or {}).get('frame') or '')
            if not name:
                continue
            try:
                frame = (media_root(base_path or candidate) / name).resolve()
            except OSError:
                continue
            if frame.is_file():
                frames.append(str(frame))
        videos.extend(sid for sid in invalid if sid in generated)
        episodes.append({'candidate': str(candidate),
                         'base': str(base_path) if base_path else '',
                         'episode_id': str(data.get('episode_id') or ''),
                         'added': added, 'removed': removed,
                         'changed': changed, 'reordered': reordered})
    return {'episodes': episodes,
            'frames': sorted(set(frames)),
            'videos': sorted(set(videos)),
            'summary': _impact_summary(episodes, frames, videos)}


def _is_structured_name(path):
    from contract.script_contract import is_structured_script_file_name
    return is_structured_script_file_name(path)


def is_deliverable(path, kind):
    """Return whether a discovered file can be shown as a script or storyboard."""
    path = Path(path)
    if kind != 'script':
        return path.suffix.lower() == '.json'
    if path.suffix.lower() not in {'.md', '.txt', '.docx'} or path.name.casefold() == 'script.md':
        return False
    if _is_structured_name(path):
        return True
    name = path.stem
    if any(word in name for word in ('创意', '设定', '大纲', '梗概', '需求', '脑洞', '规划', '说明', '提示词', '任务', '草稿', '初稿', '备份')):
        return False
    return bool(re.search(r'第[0-9零一二三四五六七八九十百]+集|(?i:EP)[0-9]+|最终剧本|剧本定稿|正式剧本|成稿', name))


def file_order(path, data=None):
    path = Path(path)
    text = str(data.get('episode_id', '')) if data else path.stem
    episode = re.search(r'(?i)EP(\d+)|第(\d+)集', text)
    number = int(next(value for value in episode.groups() if value)) if episode else 10 ** 9
    shots = [int(match[1]) for shot in (data or {}).get('shots', [])
             if (match := re.search(r'SH(\d+)', str(shot.get('id', ''))))]
    return (number, min(shots) if shots else 0, path.name, str(path))


def linked_path(context, value):
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value)
    project = _context(context).root
    return (project / path).resolve() if not path.is_absolute() else path.resolve()


def board_source_script(context, board):
    """Return a board's real source script, including the legacy generic-name bridge."""
    from file_cache import read_json
    context = _context(context)
    try:
        data = read_json(Path(board))
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    return _source_script_from_data(context, data)


def _source_script_from_data(context, data):
    source = linked_path(context, data.get('source_script'))
    if source is None or source.name.casefold() != 'script.md':
        return source
    try:
        from contract.script_contract import structured_script_path
        current = structured_script_path(_context(context).root.resolve()).resolve()
    except (OSError, ValueError):
        return None
    return current if current.is_file() else None


def _is_initial_storyboard(data):
    """Recognize the untouched Projects.create seed, including renamed legacy files."""
    return (set(data) <= {'episode_id', 'title', 'shots'}
            and data.get('episode_id') == 'EP001'
            and data.get('shots') == [{
                'id': 'SH001', 'title': '待编写', 'duration': 5,
                'characters': ['CHAR_001'], 'location': 'LOC_001',
                'frame': 'frames/SH001.png',
                'video_prompt': '待填写镜头画面、动作和对白', 'dialogue': [],
            }])


def catalog(context, kind, ignored=IGNORED, completed=None):
    """Build the script/storyboard catalog without importing Tk page code.

    ``completed`` 是已制作分镜的剧本路径集合，供 script 目录复用：调用方已经拿到该集合
    （如 catalog_snapshot，或 prune 只需剧本路径集合、不需要“已制作分镜”标记）时传入，
    _catalog 就不必再经 produced_scripts 多扫一遍分镜目录。
    """
    return _catalog(context, kind, ignored, completed=completed)


def catalog_snapshot(context, ignored=IGNORED):
    """Read both catalogs once, including previews and the completed-script set."""
    context = _context(context)
    sources = {}
    boards = _catalog(context, 'storyboard', ignored, sources=sources, previews=True)
    completed = {sources[entry['path']] for entry in boards} - {None}
    scripts = _catalog(context, 'script', ignored, completed=completed, previews=True)
    return {'script': scripts, 'storyboard': boards, 'completed_scripts': completed}


def _catalog(context, kind, ignored, *, completed=None, sources=None, previews=False):
    from contract.artifact_lineage import MISSING, STALE, check
    from file_cache import read_json
    from contract.project_stages import writing, structure, storyboard, stage
    from contract.storyboard_paths import is_final_dir
    from writing import duration_gap
    project = _context(context).root.resolve()
    from contract.stage_path_service import read_dirs, write_dir
    final_dirs = read_dirs(project, 'final') if kind != 'script' else ()
    current_roots = ((writing(project).resolve(), structure(project).resolve()) if kind == 'script'
                     else (storyboard(project).resolve(), *final_dirs))
    legacy_roots = ((project / 'writing').resolve(),) if kind == 'script' else ((project / 'storyboard').resolve(),)
    roots = tuple(dict.fromkeys((*current_roots, *legacy_roots)))
    suffixes = {'.md', '.txt', '.docx'} if kind == 'script' else {'.json'}
    current_structured = None
    if kind == 'script':
        try:
            from contract.script_contract import structured_script_path
            candidate = structured_script_path(project).resolve()
            current_structured = candidate if candidate.is_file() else None
        except (OSError, ValueError):
            pass
    entries = []
    def ignored_name(name):
        return name.startswith(('目录说明', 'README', '共用技能位置')) or '.bak' in name or '.history_' in name
    for path, resolved, stat in discover_files(roots, suffixes, ignored, ignored_name):
        root = next((candidate for candidate in roots if resolved.is_relative_to(candidate)), None)
        if root is None:
            continue
        if kind != 'script' and root in final_dirs[1:]:
            current = write_dir(project, 'final') / resolved.relative_to(root)
            if current.is_file():
                continue
        if not (kind == 'script' and current_structured is not None and resolved == current_structured) and not is_deliverable(path, kind):
            continue
        if kind == 'script' and _is_structured_name(path) and resolved != current_structured:
            continue
        title = ('结构剧本（旧版）' if kind == 'script' and resolved == current_structured and path.name.casefold() == 'script.md' else path.stem)
        if kind == 'script' and current_structured is not None and resolved == current_structured:
            # 原稿改动只把下游结构稿标成过期，不隐藏、不改写用户成品。
            if check(project, resolved)['status'] == STALE:
                title += ' · 原稿已变更'
        data = None
        if path.suffix.lower() == '.json':
            try:
                data = read_json(path)
                if not isinstance(data, dict) or not isinstance(data.get('shots'), list) or not data['shots']:
                    continue
                if _is_initial_storyboard(data):
                    continue
                final_candidate = any(is_final_dir(part) for part in path.relative_to(root).parts)
                report = check(project, path) if final_candidate else None
                if report is not None and report['status'] == MISSING:
                    continue
                linked = _source_script_from_data(context, data)
                if not final_candidate and str(data.get('source_script') or '').strip() and (not linked or not linked.is_file()):
                    continue
                title = f"{data.get('episode_id', '')} · {data.get('title', path.stem)}（{len(data['shots'])}镜）"
                title += ' · 定稿' if final_candidate else ' · 分镜工作稿'
                if duration_gap(data) is not None:
                    title += ' · 时长不符'
                if report is not None and report['status'] == STALE:
                    title += ' · 来源已变更'
            except (OSError, ValueError):
                continue
        created = getattr(stat, 'st_birthtime', stat.st_mtime)
        entry = {'path': resolved, 'title': title, 'created': created, 'order': file_order(path, data)}
        if previews:
            entry['preview'] = _board_preview(path, data) if data is not None else content_preview(path)
        if sources is not None:
            sources[resolved] = linked
        entries.append(entry)
    if kind != 'script':
        from domain.storyboard_storage import unique_entries
        from domain.storyboard_adoption_contract import adopted
        entries = unique_entries(entries, project)
        try:
            used = set(adopted(project))
        except (OSError, ValueError):
            used = set()
        for entry in entries:
            entry['done'] = entry['path'] in used
            if entry['done']:
                entry['title'] += ' · 已采用'
    else:
        made = produced_scripts(context) if completed is None else completed
        for entry in entries:
            entry['done'] = entry['path'] in made
            if entry['done']:
                entry['title'] += ' · 已制作分镜'
    return sorted(entries, key=lambda entry: (entry.get('done', False), entry['order']))


def produced_scripts(context, entries=None):
    context = _context(context)
    entries = catalog(context, 'storyboard') if entries is None else entries
    return {board_source_script(context, entry['path']) for entry in entries} - {None}


def produced_episodes(context, entries=None):
    context = _context(context)
    entries = catalog(context, 'storyboard') if entries is None else entries
    return {entry.get('order', (10 ** 9,))[0] for entry in entries
            if entry.get('order', (10 ** 9,))[0] < 10 ** 9}
