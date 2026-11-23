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
import infra.app_logging as app_logging
from infra import unit_of_work
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


def _image_content_ok(path):
    """导入候选按内容验真：后缀合法但内容不是对应格式的完整图片时返回 False。

    与 ``asset_reference_images.image_bytes`` 同一口径（PNG 看签名＋IHDR＋IEND，
    JPG 看 SOI＋EOI，WEBP 看 RIFF＋WEBP），只读头 16 字节与尾 8 字节，不把整图读进内存。
    """
    path = Path(path)
    suffix = path.suffix.lower()
    try:
        size = path.stat().st_size
        with open(path, 'rb') as handle:
            head = handle.read(16)
            handle.seek(max(0, size - 8))
            tail = handle.read(8)
    except OSError:
        return False
    if suffix == '.png':
        return (size >= 33 and head.startswith(b'\x89PNG\r\n\x1a\n')
                and head[12:16] == b'IHDR' and tail[:4] == b'IEND')
    if suffix in ('.jpg', '.jpeg'):
        return size >= 4 and head.startswith(b'\xff\xd8') and tail[-2:] == b'\xff\xd9'
    if suffix == '.webp':
        return size >= 12 and head[:4] == b'RIFF' and head[8:12] == b'WEBP'
    return False


def _source(path):
    path = Path(path).resolve()
    if not path.is_file() or path.stat().st_size <= 0:
        raise _BindingInputError('请选择存在且非空的图片文件')
    if path.suffix.lower() not in _IMAGE_SUFFIXES:
        raise _BindingInputError('请选择 PNG、JPG、JPEG 或 WEBP 图片')
    if not _image_content_ok(path):
        raise _BindingInputError('图片内容无效，请选择完整的 PNG、JPG 或 WebP 图片')
    return path


def _safe_part(value, label):
    value = str(value or '').strip()
    if not value or Path(value).name != value or value in ('.', '..'):
        raise _BindingInputError(label + '不合法')
    return value


def _publish(project, episode_dir, aid, source, suffix, values, *, gateway=None, context=None):
    """图片与资产清单索引作为一个事务发布；任一失败（含取消）恢复两侧旧状态。"""
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
    temporary = temporary_path(dest, '.binding')
    copied = source != dest
    # 图片文件与索引同进退；取消与进程中断也由事务 journal 恢复（R3310 轮 6）。
    token = unit_of_work.begin((dest, index))
    try:
        if copied:
            folder.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, temporary)
            replace(temporary, dest)
        update_fields(project, episode_dir, aid, values, gateway=gateway)
        unit_of_work.commit(token)
    except BaseException:
        try:
            unit_of_work.rollback(token)
        except Exception:
            app_logging.swallowed('asset_detail_service._publish.rollback')
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
