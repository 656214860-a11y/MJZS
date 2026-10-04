"""无人值守自动粗剪的无界面派发决策。"""
from pathlib import Path
from functools import wraps
import logging
from service_contract import SystemError, success
from project_context import ProjectContext


def _project_root(project=None, *, context=None):
    if context is None:
        return Path(project).resolve()
    if not isinstance(context, ProjectContext):
        raise TypeError('剪辑清单需要由 L3 注入 ProjectContext。')
    root = context.root.resolve()
    if project is not None and Path(project).resolve() != root:
        raise ValueError('项目路径与注入的 ProjectContext 不一致。')
    return root


def _write_result(function):
    @wraps(function)
    def run(*args, **kwargs):
        try:
            return success(function(*args, **kwargs))
        except OSError:
            logging.getLogger(__name__).exception('剪辑记录保存失败')
            return SystemError('剪辑记录保存失败，请检查文件权限和磁盘空间。')
    return run


CHECKLIST_NAME = '剪辑优化清单.md'
AUTOMATIC_ASSEMBLE_MARKER_NAME = '自动粗剪.json'


@_write_result
def save_editing_checklist(project, text, *, publish=None, context=None):
    """发布用户维护的剪辑优化清单；正式发布器必须由 L3 注入。"""
    if not callable(publish):
        raise TypeError('剪辑优化清单需要由 L3 注入发布器。')
    from project_stages import editing
    target = editing(_project_root(project, context=context)) / CHECKLIST_NAME
    return publish(target, str(text or ''))


@_write_result
def save_automatic_assemble_marker(target, digest, master, completed_at, *, publish):
    """登记一次已完成的自动粗剪；正式发布器必须由 L3 注入。"""
    if not callable(publish):
        raise TypeError('自动粗剪标记需要由 L3 注入发布器。')
    target = Path(target)
    publish(target, {'digest': digest, 'master': str(master), 'at': completed_at})
    return target


def automatic_assemble_decision(signature, digest, previous_signature, completed_marker):
    """决定自动粗剪应等待、跳过已完成成果，还是启动一次拼接。"""
    if signature == previous_signature:
        return {'action': 'skip', 'signature': signature}
    if digest is None:
        return {'action': 'wait', 'signature': signature}
    if isinstance(completed_marker, dict) and completed_marker.get('digest') == digest:
        return {'action': 'complete', 'signature': signature}
    return {'action': 'dispatch', 'signature': signature}
