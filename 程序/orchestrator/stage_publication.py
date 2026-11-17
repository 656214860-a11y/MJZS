"""阶段成果原子发布编排（L3）。

从 `stage_execution_service` 拆出（R1619／Q9）："校验 → 原子发布 → 索引更新"这套发布
契约、中断事务恢复与 `projects` 网关装配是一件事，也是其它 L3 编排共用的底层入口；
单独成模块后，各阶段编排可以只依赖它，不必再依赖整个阶段执行模块。

`stage_execution_service` 仍按原名转发本模块的公开名，既有 `stage_execution_service.X`
调用不必改。
"""
from __future__ import annotations

import logging
from pathlib import Path

import infra.file_cache as file_cache


logger = logging.getLogger(__name__)


def _check_publication_context(context, paths):
    """显式上下文只允许项目内目标；在发布事务开始前拒绝越界。"""
    if context is None:
        return
    from contract.project_context import ProjectContext
    if not isinstance(context, ProjectContext):
        raise TypeError('阶段成果发布需要 ProjectContext。')
    root = Path(context.root).resolve()
    if any(not Path(path).resolve().is_relative_to(root) for path in paths):
        raise ValueError('阶段成果目标不在项目目录内，未发布成果。')


def _update_file_index(paths, context=None, origin='系统生成'):
    """只增量同步已有有效缓存；首次全量创建留给后台，不影响真实发布。"""
    try:
        from infra import file_index
    except Exception:
        logger.warning('阶段成果已发布，文件索引不可用；等待后台重建。')
        return
    grouped = {}
    for path in paths:
        try:
            target = Path(path).resolve()
            roots = (Path(context.root).resolve(),) if context is not None else target.parents
            for root in roots:
                index = file_index.index_path(root).resolve()
                if context is None and not index.is_file():
                    continue
                if target != index:
                    grouped.setdefault(root, []).append(target)
                break
        except Exception:
            logger.warning('阶段成果已发布，文件索引定位失败；等待后台重建。')
    for root, targets in grouped.items():
        try:
            # 来源是独立事实；context 已知时即使缓存未创建也登记，绝不首次全扫。
            file_index.record_origin(root, targets, origin)
            if file_index.read(root) is not None:
                file_index.update(root, targets)
        except Exception:
            logger.warning('阶段成果已发布，文件索引增量同步失败；等待后台重建。')


def recover_stage_publications():
    """在打开项目、读取直接路径之前恢复中断的成果事务。"""
    from agent.publication import recover_pending
    recover_pending()


def publish_stage_text(target, text, validate, update_index, encoding='utf-8', *, allow_empty=False,
                       **publication_options):
    """按“校验 → 原子发布 → 索引更新”发布单份阶段文本成果。

    ``validate`` 和 ``update_index`` 都是调用方所属阶段的既有契约：前者必须在正式
    文件出现前拒绝不合格内容，后者只会在发布成功后执行。默认拒绝空正文；仅明确允许
    用户清空维护清单的 L3 编排入口可传 ``allow_empty=True``，L2 不得自行放宽。索引
    更新失败时恢复本次发布前的成果，并抛出异常；调用方因此不会取得成功返回值，也不得
    据此标记阶段完成。事务成功后另行尽力更新可再生文件索引；该缓存故障只记日志，
    不回滚已发布成果。``context`` 可提供项目根；旧调用按最近的已有有效索引定位项目。
    ``publication_options`` 只接受 context/origin，保持既有关键字调用兼容。
    """
    unknown = set(publication_options) - {'context', 'origin'}
    if unknown:
        raise TypeError('未知的阶段发布选项：' + ', '.join(sorted(unknown)))
    context = publication_options.get('context')
    origin = publication_options.get('origin', '系统生成')
    if not callable(validate):
        raise TypeError('阶段成果发布需要内容校验器。')
    if not callable(update_index):
        raise TypeError('阶段成果发布需要索引更新器。')
    target = Path(target)
    _check_publication_context(context, (target,))
    value = str(text)
    if not value.strip() and not allow_empty:
        raise ValueError('阶段成果正文不能为空，未发布成果。')
    verdict = validate(value)
    if verdict is False:
        raise ValueError('阶段成果内容校验未通过，未发布成果。')

    from agent.core import save_text
    from agent.publication import transaction
    from contract.platform_tools import execution_checkpoint
    with transaction():
        execution_checkpoint()
        save_text(target, value, encoding=encoding)
        update_index(target)
        execution_checkpoint()
    _update_file_index((target,), context, origin)
    return target


def publish_stage_bytes(target, data, validate, update_index, *, context=None, origin='系统生成'):
    """按文本成果同一编排契约发布二进制阶段成果。"""
    if not callable(validate):
        raise TypeError('阶段成果发布需要内容校验器。')
    if not callable(update_index):
        raise TypeError('阶段成果发布需要索引更新器。')
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError('二进制阶段成果必须是 bytes、bytearray 或 memoryview。')
    target = Path(target)
    _check_publication_context(context, (target,))
    value = bytes(data)
    if not value:
        raise ValueError('阶段成果二进制内容不能为空，未发布成果。')
    verdict = validate(value)
    if verdict is False:
        raise ValueError('阶段成果内容校验未通过，未发布成果。')

    from agent.core import save_bytes
    from agent.publication import transaction
    from contract.platform_tools import execution_checkpoint
    with transaction():
        execution_checkpoint()
        save_bytes(target, value)
        update_index(target)
        execution_checkpoint()
    _update_file_index((target,), context, origin)
    return target


def publish_stage_bundle(artifacts, validate, update_index, *, context=None, origin='系统生成'):
    """原子发布多份关联成果；任一写入或索引失败均恢复整包旧版本。"""
    if not callable(validate):
        raise TypeError('阶段成果发布需要内容校验器。')
    if not callable(update_index):
        raise TypeError('阶段成果发布需要索引更新器。')
    items = tuple((Path(path), bytes(data)) for path, data in artifacts.items())
    _check_publication_context(context, (path for path, _data in items))
    if not items:
        raise ValueError('阶段成果包不能为空，未发布成果。')
    if len({path for path, _data in items}) != len(items):
        raise ValueError('阶段成果包包含重复目标，未发布成果。')
    if any(not data for _path, data in items):
        raise ValueError('阶段成果包包含空内容，未发布成果。')
    verdict = validate(items)
    if verdict is False:
        raise ValueError('阶段成果包内容校验未通过，未发布成果。')

    from agent.core import save_bytes
    from agent.publication import transaction
    from contract.platform_tools import execution_checkpoint
    with transaction():
        execution_checkpoint()
        for path, data in items:
            save_bytes(path, data)
        update_index()
        execution_checkpoint()
    _update_file_index((path for path, _data in items), context, origin)
    return tuple(path for path, _data in items)


def project_registry_gateway():
    """为 ``projects`` 注入唯一的读取、发布及回滚边界。

    项目登记是 L2 业务规则；它不能自行导入底层读写或复制原语。这个小型
    网关由 L3 装配，保留原有缓存读取、原子发布与复制元数据语义。
    """
    from agent.core import restore_bytes, save, save_bytes
    from shutil import copy2, copytree
    return {
        'read_json': file_cache.read_json,
        'read_bytes': lambda path: Path(path).read_bytes(),
        'publish_json': save,
        'publish_bytes': save_bytes,
        'restore_bytes': restore_bytes,
        'copy_file': copy2,
        'copy_tree': copytree,
    }
