# -*- coding: utf-8 -*-
"""剧本准备阶段的用户可见文件发现服务。

该模块刻意不依赖 Tk 或 ``desktop``，使目录规则可以独立测试并复用于其他入口。
"""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import logging
import re
from service_contract import SystemError, UserError, success

import project_stages
from script_contract import RAW_SCRIPT_NAME, is_natural_script

LOGGER = logging.getLogger(__name__)


SCRIPT_CATEGORIES = {
    'setting': '项目设定',
    'outline': '项目大纲',
    'script': '项目剧本',
}
VISIBLE_SUFFIXES = frozenset({'.md', '.txt', '.docx'})


@dataclass(frozen=True)
class ScriptDocument:
    category: str
    path: Path
    modified_at: float
    relative_path: str


@dataclass(frozen=True)
class ScriptDeletionSelection:
    paths: tuple[Path, ...]
    deletes_all: bool


@dataclass(frozen=True)
class ScriptDocumentRow:
    category: str
    item_id: str
    name: str
    modified_label: str
    modified_at: float


@dataclass(frozen=True)
class ScriptStructureDocuments:
    source_directory: Path
    output_directory: Path
    source: Path | None
    target: Path
    source_documents: tuple[Path, ...]
    output_documents: tuple[Path, ...]


def ensure_script_workspace(project):
    """创建并返回剧本准备阶段目录，供页面在渲染前显式初始化。"""
    try:
        writing_dir = project_stages.writing(project)
        writing_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        LOGGER.exception('剧本工作区初始化失败')
        return SystemError('剧本工作区初始化失败，请检查文件权限和磁盘空间。')
    return success(writing_dir)


def iter_script_documents(project):
    """逐项发现可见剧本文档，供 UI 在空闲批次中渐进消费。

    本函数不收集完整列表，也不导入 Tk。调用方可以在项目切换时停止消费，
    从而不会因为尚未显示的后续目录而继续提交 UI 工作。
    """
    writing_dir = project_stages.writing(project)
    if not writing_dir.is_dir():
        return
    try:
        writing_root = writing_dir.resolve()
    except OSError:
        return

    # 本地 Agent 可只更新内部工作稿；展示真实文件但不将它改名为正式交付。
    # 只探测当前阶段的固定路径，不为首屏调用递归的自然剧本检索。
    draft = writing_dir / RAW_SCRIPT_NAME
    try:
        draft.resolve().relative_to(writing_root)
        if (draft.is_file() and draft.stat().st_size
                and is_natural_script(draft.read_text(encoding='utf-8', errors='ignore'))):
            yield ScriptDocument('script', draft, draft.stat().st_mtime, RAW_SCRIPT_NAME)
    except (OSError, ValueError):
        pass

    # 用户上传的创意是剧本准备的项目设定来源，放在该列而不是混进模型生成的版本目录。
    input_dir = writing_dir / '输入'
    if input_dir.is_dir():
        for path in input_dir.glob('故事创意_*.md'):
            if not path.is_file():
                continue
            try:
                path.resolve().relative_to(writing_root)
                yield ScriptDocument('setting', path, path.stat().st_mtime,
                                     path.relative_to(writing_dir).as_posix())
            except (OSError, ValueError):
                continue
    # 创意批次的正式布局固定为 ``创意_*``（历史项目）或
    # ``Provider/Model/创意_*``（当前模型分区）。不要在启动期用 rglob：
    # 它会把用户自行放入 writing 的任意深层资料树也扫进 Tk 首屏。下面的
    # 有界枚举同时保留两种已发布布局，并让未知深层目录保持用户按需打开时
    # 的惰性资源，而不是启动负担。
    creative_batches = []
    for first in writing_dir.iterdir():
        if not first.is_dir() or first.name == '输入':
            continue
        if first.name.startswith('创意_'):
            creative_batches.append(first)
            continue
        for second in first.iterdir():
            if not second.is_dir():
                continue
            if second.name.startswith('创意_'):
                creative_batches.append(second)
                continue
            for batch in second.iterdir():
                if batch.is_dir() and batch.name.startswith('创意_'):
                    creative_batches.append(batch)
    for category, directory in SCRIPT_CATEGORIES.items():
        for batch in creative_batches:
            folder = batch / directory
            if not folder.is_dir() or not folder.parent.name.startswith('创意_'):
                continue
            try:
                folder.resolve().relative_to(writing_root)
            except (OSError, ValueError):
                continue
            for path in folder.iterdir():
                if not path.is_file() or path.suffix.lower() not in VISIBLE_SUFFIXES:
                    continue
                try:
                    path.resolve().relative_to(writing_root)
                    modified_at = path.stat().st_mtime
                    relative_path = path.relative_to(writing_dir).as_posix()
                except (OSError, ValueError):
                    continue
                yield ScriptDocument(category, path, modified_at, relative_path)


def discover_script_documents(project):
    """返回分类文档、上传创意及有效内部工作稿，按最新修改时间排序。"""
    return tuple(sorted(iter_script_documents(project),
                        key=lambda row: row.modified_at, reverse=True))


def script_document_rows(project):
    """将剧本文件发现结果转换成 UI 可直接渲染的稳定行数据。"""
    return tuple(ScriptDocumentRow(
        category=document.category,
        item_id=str(document.path),
        name=_document_display_name(document.path),
        modified_label=datetime.fromtimestamp(document.modified_at).strftime('%m-%d'),
        modified_at=document.modified_at,
    ) for document in discover_script_documents(project))


def iter_script_document_rows(project):
    """Yield UI rows without first enumerating the complete project workspace."""
    for document in iter_script_documents(project):
        yield ScriptDocumentRow(
            category=document.category,
            item_id=str(document.path),
            name=_document_display_name(document.path),
            modified_label=datetime.fromtimestamp(document.modified_at).strftime('%m-%d'),
            modified_at=document.modified_at,
        )


def _document_display_name(path):
    if path.name == RAW_SCRIPT_NAME:
        return path.name + '（内部工作稿）'
    # 历史文件只调整展示，保留真实路径和阶段确认记录的关联。
    if (path.parent.name in SCRIPT_CATEGORIES.values()
            and path.parent.parent.name.startswith('创意_')):
        model_dir = path.parent.parent.parent
        provider = model_dir.parent.name
        match = re.fullmatch(
            r'(.+_(?:项目设定|项目大纲|剧本大纲|角色卡|自然剧本)_)'
            + re.escape(model_dir.name) + r'(\(\d+\))?(_\d{8}\.[^.]+)', path.name)
        if match and provider and provider != '未知Provider':
            return match[1] + provider + (match[2] or '') + match[3]
    return path.name


def script_structure_documents(project):
    """返回剧本结构页所需的阶段目录、当前来源与可见文件列表。"""
    import script_contract
    from stage_path_service import write_dir

    source_directory = write_dir(project, 'script').resolve()
    output_directory = write_dir(project, 'structure').resolve()

    def inside(path, directory):
        try:
            Path(path).resolve().relative_to(directory)
            return True
        except (OSError, ValueError):
            return False

    source = script_contract.resolve_script_source(project)
    target = script_contract.structured_script_path(project)
    all_source = tuple(script_contract.natural_script_paths(project))
    sources = tuple(path for path in all_source if inside(path, source_directory)) or all_source
    if source is not None and source not in sources:
        sources = (source,) + sources
    all_output = tuple(script_contract.structured_script_paths(project))
    outputs = tuple(path for path in all_output if inside(path, output_directory)) or all_output
    return ScriptStructureDocuments(source_directory, output_directory, source, target, sources, outputs)


def selected_workspace_document(available_paths, selected_path):
    """校验页面树控件的文件选择仍属于当前可见工作区文件集。"""
    if not selected_path:
        raise ValueError('请先选择要删除的剧本文档。')
    available = {Path(path).resolve() for path in available_paths if Path(path).is_file()}
    try:
        selected = Path(selected_path).resolve()
    except OSError as exc:
        raise ValueError('当前选择的剧本文档已不存在，请刷新页面。') from exc
    if selected not in available or not selected.is_file():
        raise ValueError('当前选择的剧本文档已不存在，请刷新页面。')
    return selected


def selected_script_paths(project, paths, require_files=False):
    """校验剧本列表选项，并返回位于当前创意目录内的绝对路径。

    ``paths`` 来自界面 Treeview 的 item id；在文件被移动、或 item id 被意外
    替换时，不能让重命名、删除等操作越出当前项目的剧本准备目录。
    """
    writing_dir = project_stages.writing(project)
    try:
        writing_root = writing_dir.resolve()
    except OSError as exc:
        raise ValueError('当前剧本目录不可访问，请刷新后重试') from exc

    selected = []
    for raw_path in paths:
        try:
            path = Path(raw_path).resolve()
            path.relative_to(writing_root)
        except (OSError, ValueError) as exc:
            raise ValueError('只能操作当前剧本目录内的文件') from exc
        if require_files and not path.is_file():
            raise ValueError('所选文件已移动或不在当前剧本目录，请刷新后重试')
        selected.append(path)
    return tuple(selected)


def batch_selected_script_paths(project, item_paths, checked_paths, active_paths=()):
    """返回批量删除目标：优先勾选项，未勾选时回退到当前高亮项。"""
    checked = {str(path) for path in checked_paths}
    selected = [path for path in item_paths if str(path) in checked]
    if not selected:
        selected = list(active_paths)[:1]
    if not selected:
        raise ValueError('请先勾选要删除的剧本文件')
    return selected_script_paths(project, selected, require_files=True)


def script_deletion_selection(project, item_paths, checked_paths, active_paths=()):
    """构建剧本删除计划，并标出是否会删掉当前列表中的全部文件。"""
    paths = batch_selected_script_paths(project, item_paths, checked_paths, active_paths)
    items = {str(path) for path in item_paths}
    selected = {str(path) for path in paths}
    return ScriptDeletionSelection(paths=paths, deletes_all=bool(items) and items == selected)


def renamed_script_path(project, source_path, requested_name):
    """校验剧本重命名请求，并返回尚未占用的同目录目标路径。"""
    source = selected_script_paths(project, [source_path], require_files=True)[0]
    name = str(requested_name or '').strip()
    if not name or '/' in name or '\\' in name or ':' in name:
        raise ValueError('文件名不能为空或包含 / \\ :')
    target = source.with_name(name)
    if target == source:
        return source
    if target.exists():
        raise ValueError('目标文件名已存在：' + name)
    return target


def rename_script_document(project, source_path, requested_name):
    """校验并执行当前剧本准备目录内的单文件重命名。"""
    try:
        try:
            source = selected_script_paths(project, [source_path], require_files=True)[0]
            target = renamed_script_path(project, source, requested_name)
        except ValueError as exc:
            if isinstance(exc.__cause__, OSError):
                raise exc.__cause__
            return UserError(str(exc))
        if target != source:
            source.rename(target)
    except OSError:
        LOGGER.exception('剧本文档重命名失败')
        return SystemError('剧本文档重命名失败，请检查文件权限后重试。')
    return success(target)
