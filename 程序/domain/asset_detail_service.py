"""资产详情图片绑定的受控发布服务。

详情页只能选择文件并刷新；图片复制和资产清单索引必须作为一个可回滚的业务操作。
"""
import shutil
from pathlib import Path
from functools import wraps
import logging

from agent.core import replace, temporary_path
from domain.asset_context import library_dir
from domain.asset_plan import plan_file, _update_fields as update_fields
from infra.file_cache import remove_temporary_file
from contract.project_context import ProjectContext
from contract.service_contract import SystemError, UserError, success

_IMAGE_SUFFIXES = frozenset({'.png', '.jpg', '.jpeg', '.webp'})


def _project_root(project=None, *, context=None):
    if context is None:
        return Path(project).resolve()
    if not isinstance(context, ProjectContext):
        raise TypeError('资产详情服务需要由 L3 注入 ProjectContext。')
    root = context.root.resolve()
    if project is not None and Path(project).resolve() != root:
        raise ValueError('项目路径与注入的 ProjectContext 不一致。')
    return root


class _BindingInputError(ValueError):
    """仅标记本服务的输入校验，不捕获发布器的编程错误。"""


def _binding_result(function):
    @wraps(function)
    def run(*args, **kwargs):
        try:
            return success(function(*args, **kwargs))
        except _BindingInputError as exc:
            return UserError(str(exc))
        except OSError:
            logging.getLogger('asset_detail_service').exception('资产图片绑定失败')
            return SystemError('资产图片绑定失败，请检查文件权限和磁盘空间。')
    return run


def _source(path):
    path = Path(path).resolve()
    if not path.is_file() or path.stat().st_size <= 0:
        raise _BindingInputError('请选择存在且非空的图片文件')
    if path.suffix.lower() not in _IMAGE_SUFFIXES:
        raise _BindingInputError('请选择 PNG、JPG、JPEG 或 WEBP 图片')
    return path


def _safe_part(value, label):
    value = str(value or '').strip()
    if not value or Path(value).name != value or value in ('.', '..'):
        raise _BindingInputError(label + '不合法')
    return value


def _publish(project, episode_dir, aid, source, suffix, values, *, gateway=None, context=None):
    """先原子替换图片，再发布索引；索引失败时恢复两侧旧状态。"""
    publish_bytes = gateway.get('publish_bytes') if isinstance(gateway, dict) else None
    if not callable(publish_bytes):
        raise RuntimeError('资产详情发布必须由 L3 注入')
    project = _project_root(project, context=context)
    base = library_dir(project, episode_dir)
    aid = _safe_part(aid, '资产编号')
    source = _source(source)
    folder = base / 'assets' / '正典板'
    dest = (folder / (aid + '_' + suffix + source.suffix.lower())).resolve()
    if not dest.is_relative_to(base):
        raise _BindingInputError('正典板目录超出当前资产库')
    index = plan_file(project, episode_dir)
    old_index = index.read_bytes() if index.is_file() else None
    old_dest = dest.read_bytes() if dest.is_file() else None
    temporary = temporary_path(dest, '.binding')
    copied = source != dest
    try:
        if copied:
            folder.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, temporary)
            replace(temporary, dest)
        update_fields(project, episode_dir, aid, values, gateway=gateway)
    except Exception:
        if copied:
            if old_dest is None:
                remove_temporary_file(dest)
            else:
                publish_bytes(dest, old_dest)
        if old_index is None:
            remove_temporary_file(index)
        elif not index.is_file() or index.read_bytes() != old_index:
            publish_bytes(index, old_index)
        raise
    finally:
        remove_temporary_file(temporary)
    return dest


@_binding_result
def bind_canonical_view(project, episode_dir, aid, view, source, *, gateway=None, context=None):
    """绑定正典板视角，并让 front 同步成为默认正典板。"""
    view = _safe_part(view, '正典板视角')
    current = {}
    project = _project_root(project, context=context)
    index = plan_file(project, episode_dir)
    if index.is_file():
        from agent.core import read
        data = read(index)
        row = data.get(str(aid), {}) if isinstance(data, dict) else {}
        current = dict(row.get('canon_board_views', {})) if isinstance(row, dict) else {}
    relative = 'assets/正典板/' + str(aid).strip() + '_' + view + Path(source).suffix.lower()
    current[view] = relative
    values = {'canon_board_views': current}
    if view == 'front':
        values['canonical_board'] = relative
    return _publish(project, episode_dir, aid, source, view, values,
                    gateway=gateway, context=context)


@_binding_result
def bind_variant_thumbnail(project, episode_dir, aid, state_id, source, *, gateway=None, context=None):
    """绑定一个既有状态变体的缩略图。"""
    from agent.core import read
    from contract.asset_contract import state_variants
    state_id = _safe_part(state_id, '状态变体编号')
    project = _project_root(project, context=context)
    index = plan_file(project, episode_dir)
    data = read(index) if index.is_file() else {}
    asset = data.get(str(aid), {}) if isinstance(data, dict) else {}
    rows = [dict(item) for item in state_variants(asset)]
    target = next((item for item in rows if item.get('state_id') == state_id), None)
    if target is None:
        raise _BindingInputError('这一条状态变体已经不在了，请刷新')
    target['reference_image'] = 'assets/正典板/' + str(aid).strip() + '_' + state_id + '_变体' + Path(source).suffix.lower()
    return _publish(project, episode_dir, aid, source, state_id + '_变体',
                    {'state_variants': rows}, gateway=gateway, context=context)
