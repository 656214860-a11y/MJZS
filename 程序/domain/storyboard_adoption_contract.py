"""Read-only adopted-storyboard facts, independent of selection mutations."""
from pathlib import Path
from agent.core import read
from file_cache import read_json
from project_settings import read_prefs


def prefs(project):
    return read_prefs(Path(project) / 'ui_settings.json', read_json)


def paths(project, values):
    project = Path(project).resolve()
    result = []
    for value in values:
        path = resolve_source(project, value)
        if not path.is_relative_to(project) or not path.is_file():
            raise ValueError('已采用的分镜不存在或不在当前项目内：' + str(path))
        if path not in result:
            result.append(path)
    return result


def resolve_source(project, value):
    """Resolve an adopted storyboard without depending on the UI file catalog."""
    project = Path(project).resolve()
    path = Path(value)
    path = (project / path).resolve() if not path.is_absolute() else path.resolve()
    # Alias maps are optional migration data.  Their storage implementation is
    # loaded only for an actual lookup, keeping this read-only contract below
    # the catalog/selection command layers.
    from importlib import import_module
    path = import_module('domain.storyboard_storage').resolved_alias(project, path)
    from contract.project_stages import storyboard
    legacy_episode = project / 'storyboard' / 'episode.json'
    if not path.exists() and path in (storyboard(project) / 'episode.json', legacy_episode):
        current = storyboard(project) / 'episode.json'
        return current.resolve()
    return path


def adopted(project):
    data = prefs(project)
    values = data.get('adopted_storyboards')
    if values is None:
        values = [data['frame_json']] if data.get('frame_json') else []
    if not isinstance(values, list):
        raise ValueError('已采用分镜列表格式错误')
    return paths(project, values)


def problem_text(error):
    """Format validation errors for both file scanning and adoption commands."""
    return '；'.join(line.strip() for line in str(error).splitlines() if line.strip())
