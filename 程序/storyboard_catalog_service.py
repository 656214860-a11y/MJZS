"""无界面的分镜/剧本目录扫描服务。

页面只负责把扫描结果显示到 Treeview；这里负责安全地遍历阶段目录，拒绝链接逃逸、
空文件和内部目录。这样文件发现可在不创建 Tk 窗口的测试或后台任务中复用。
"""
import os
import re
from pathlib import Path
from project_context import ProjectContext


IGNORED = {'历史版本', '分镜历史', '剧本输入', 'frames', 'video_prompts', 'assets',
           '__pycache__', '首帧任务'}


def _context(value):
    if not isinstance(value, ProjectContext):
        raise TypeError('分镜目录项目路径需要由 L3 注入 ProjectContext。')
    return value


def working_dir(context):
    """Return the structured JSON storyboard workspace without creating it."""
    from project_stages import storyboard
    return storyboard(_context(context).root) / '分镜拆分'


def document_dir(context):
    """Return the user-readable storyboard document directory without creating it."""
    from project_stages import storyboard
    return storyboard(_context(context).root) / '分镜文档'


def discover_files(roots, suffixes, ignored, ignored_name=None):
    """逐一返回 ``(原路径, 解析路径, stat)``，不创建目录也不修改项目文件。"""
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
                    resolved = path.resolve()
                    stat = path.stat()
                except OSError:
                    continue
                if not resolved.is_relative_to(root) or not stat.st_size:
                    continue
                yield path, resolved, stat


def content_preview(path):
    """Return a compact file preview without requiring a Tk widget."""
    path = Path(path)
    try:
        if path.suffix.lower() == '.json':
            from file_cache import read_json
            data = read_json(path)
            if isinstance(data, dict):
                sid = data.get('episode_id', '')
                title = str(data.get('title', '')).strip()
                shots = data.get('shots')
                count = len(shots) if isinstance(shots, list) else 0
                label = ' · '.join(value for value in (sid, title) if value)
                return (label + ' · ' + str(count) + '镜') if label else path.stem
        text = ''
        try:
            from script_text_reader import script_text
            text = script_text(path)
        except Exception:
            text = path.read_text(encoding='utf-8-sig', errors='replace')
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return lines[0][:60] + ('…' if len(lines[0]) > 60 else '') if lines else path.stem
    except (OSError, ValueError, UnicodeError):
        return path.stem


def has_synced_assets(path):
    """Return whether a storyboard has the sibling asset registry required by final view."""
    try:
        return (Path(path).parent / 'assets.json').is_file()
    except OSError:
        return False


def file_snapshot(context, ignored=IGNORED):
    """Return a cheap, safe catalog change signature without parsing document content."""
    from project_stages import writing, storyboard
    from stage_path_service import read_dirs
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
    from project_stages import storyboard
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
    from storyboard_storage import resolved_alias
    from project_stages import storyboard
    project = _context(context).root.resolve()
    path = resolved_alias(project, Path(path))
    legacy_episode = project / 'storyboard' / 'episode.json'
    if not path.exists() and path in (storyboard(project) / 'episode.json', legacy_episode):
        return default_source(context).resolve()
    return path


def check_adoptable(paths):
    """Validate every selected storyboard before an adoption command mutates preferences."""
    from file_cache import read_json
    from storyboard_adoption_contract import problem_text
    from storyboard_paths import media_root
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


def _is_structured_name(path):
    from script_contract import is_structured_script_file_name
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
    project = _context(context).root.resolve()
    try:
        data = read_json(Path(board))
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    source = linked_path(context, data.get('source_script'))
    if source is None or source.name.casefold() != 'script.md':
        return source
    try:
        from script_contract import structured_script_path
        current = structured_script_path(project).resolve()
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


def catalog(context, kind, ignored=IGNORED):
    """Build the script/storyboard catalog without importing Tk page code."""
    from artifact_lineage import source_available
    from file_cache import read_json
    from project_stages import writing, structure, storyboard, stage
    from storyboard_paths import is_final_dir
    from writing import duration_gap
    project = _context(context).root.resolve()
    from stage_path_service import read_dirs, write_dir
    current_roots = ((writing(project).resolve(), structure(project).resolve()) if kind == 'script'
                     else (storyboard(project).resolve(), *read_dirs(project, 'final')))
    legacy_roots = ((project / 'writing').resolve(),) if kind == 'script' else ((project / 'storyboard').resolve(),)
    roots = tuple(dict.fromkeys((*current_roots, *legacy_roots)))
    suffixes = {'.md', '.txt', '.docx'} if kind == 'script' else {'.json'}
    current_structured = None
    if kind == 'script':
        try:
            from script_contract import structured_script_path
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
        if kind != 'script' and root in read_dirs(project, 'final')[1:]:
            current = write_dir(project, 'final') / resolved.relative_to(root)
            if current.is_file():
                continue
        if not (kind == 'script' and current_structured is not None and resolved == current_structured) and not is_deliverable(path, kind):
            continue
        if kind == 'script' and _is_structured_name(path) and resolved != current_structured:
            continue
        title = ('结构剧本（旧版）' if kind == 'script' and resolved == current_structured and path.name.casefold() == 'script.md' else path.stem)
        data = None
        if path.suffix.lower() == '.json':
            try:
                data = read_json(path)
                if not isinstance(data, dict) or not isinstance(data.get('shots'), list) or not data['shots']:
                    continue
                if _is_initial_storyboard(data):
                    continue
                final_candidate = any(is_final_dir(part) for part in path.relative_to(root).parts)
                if final_candidate and source_available(project, path) is False:
                    continue
                linked = board_source_script(context, path)
                if not final_candidate and str(data.get('source_script') or '').strip() and (not linked or not linked.is_file()):
                    continue
                title = f"{data.get('episode_id', '')} · {data.get('title', path.stem)}（{len(data['shots'])}镜）"
                title += ' · 定稿' if final_candidate else ' · 分镜工作稿'
                if duration_gap(data) is not None:
                    title += ' · 时长不符'
            except (OSError, ValueError):
                continue
        created = getattr(stat, 'st_birthtime', stat.st_mtime)
        entries.append({'path': resolved, 'title': title, 'created': created, 'order': file_order(path, data)})
    if kind != 'script':
        from storyboard_storage import unique_entries
        from storyboard_adoption_contract import adopted
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
        made = produced_scripts(context)
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
