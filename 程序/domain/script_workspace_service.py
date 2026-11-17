# -*- coding: utf-8 -*-
"""剧本准备阶段的用户可见文件发现服务。

该模块刻意不依赖 Tk 或 ``desktop``，使目录规则可以独立测试并复用于其他入口。
"""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import logging
import os
import re
import stat
from contract.service_contract import SystemError, UserError, success

import contract.project_stages as project_stages
from contract.script_contract import RAW_SCRIPT_NAME

# R3153：日志器名保持包化前的稳定标识——失败路径的可追溯契约（用例与运维日志）按这个名字
# 断言，包化后 __name__ 会变成 domain.*，不能让它悄悄改名。
LOGGER = logging.getLogger('script_workspace_service')


SCRIPT_CATEGORIES = {
    'setting': '项目设定',
    'outline': '项目大纲',
    'character': '角色卡',
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


def _find_draft(writing_dir, writing_root):
    """本地 Agent 可只更新内部工作稿；返回 {'document', 'text'}，不是自然剧本或读不到时 document 为 None。

    只探测当前阶段的固定路径，不为首屏调用递归的自然剧本检索。
    """
    draft = writing_dir / RAW_SCRIPT_NAME
    state = {'document': None, 'text': ''}
    try:
        draft.resolve().relative_to(writing_root)
        if draft.is_file() and draft.stat().st_size:
            state['text'] = draft.read_text(encoding='utf-8', errors='ignore').strip()
            if state['text']:
                state['document'] = ScriptDocument('script', draft, draft.stat().st_mtime, RAW_SCRIPT_NAME)
    except (OSError, ValueError):
        pass
    return state


def _uploaded_idea_documents(writing_dir, writing_root):
    """用户上传的创意是剧本准备的项目设定来源，放在该列而不是混进模型生成的版本目录。"""
    input_dir = writing_dir / '输入'
    if not input_dir.is_dir():
        return
    for path in input_dir.glob('故事创意_*.md'):
        if not path.is_file():
            continue
        try:
            path.resolve().relative_to(writing_root)
            yield ScriptDocument('setting', path, path.stat().st_mtime,
                                 path.relative_to(writing_dir).as_posix())
        except (OSError, ValueError):
            continue


def _creative_batches(writing_dir):
    """创意批次的正式布局固定为 ``创意_*``（历史项目）或 ``Provider/Model/创意_*``（当前模型分区）。

    不要在启动期用 rglob：它会把用户自行放入 writing 的任意深层资料树也扫进 Tk 首屏。
    这个有界枚举同时保留两种已发布布局，并让未知深层目录保持用户按需打开时的惰性资源。
    """
    batches = []
    for first in writing_dir.iterdir():
        if not first.is_dir() or first.name == '输入':
            continue
        if first.name.startswith('创意_'):
            batches.append(first)
            continue
        for second in first.iterdir():
            if not second.is_dir():
                continue
            if second.name.startswith('创意_'):
                batches.append(second)
                continue
            batches.extend(batch for batch in second.iterdir()
                           if batch.is_dir() and batch.name.startswith('创意_'))
    return batches


def _batch_folder_documents(category, folder, writing_dir, writing_root, draft):
    """一个批次分类目录里的可见文件；与内部工作稿同内容的正式剧本出现时，工作稿不再单独展示。"""
    try:
        folder.resolve().relative_to(writing_root)
    except (OSError, ValueError):
        return
    # 目录级已确认 folder 在 writing_root 内。逐文件 resolve() 只剩「符号链接指向
    # 外部」这一个意义，却占发现总耗时过半（真实大项目实测 4098 次调用约 287ms，
    # 占 53.5%）。普通文件按构造必然在写作根内，只对符号链接补一次 resolve 即可
    # 守住安全边界，把 99% 的调用降为一次廉价的 lstat 判断。
    for path in folder.iterdir():
        if not path.is_file() or path.suffix.lower() not in VISIBLE_SUFFIXES:
            continue
        try:
            stat = path.stat()
            relative_path = path.relative_to(writing_dir).as_posix()
        except (OSError, ValueError):
            continue
        if path.is_symlink():
            try:
                path.resolve().relative_to(writing_root)
            except (OSError, ValueError):
                continue
        modified_at = stat.st_mtime
        if (draft['document'] is not None and category == 'script'
                and path.suffix.lower() in {'.md', '.txt'}):
            try:
                if path.read_text(encoding='utf-8').strip() == draft['text']:
                    draft['document'] = None
            except (OSError, UnicodeError):
                pass
        yield ScriptDocument(category, path, modified_at, relative_path)


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
    draft = _find_draft(writing_dir, writing_root)
    yield from _uploaded_idea_documents(writing_dir, writing_root)
    creative_batches = _creative_batches(writing_dir)
    for category, directory in SCRIPT_CATEGORIES.items():
        for batch in creative_batches:
            folder = batch / directory
            if not folder.is_dir() or not folder.parent.name.startswith('创意_'):
                continue
            yield from _batch_folder_documents(category, folder, writing_dir, writing_root, draft)
    if draft['document'] is not None:
        yield draft['document']


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
    import contract.script_contract as script_contract
    from contract.stage_path_service import write_dir

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


def script_structure_signature(project):
    """页面复用依据：文件增删、内容覆盖与采用来源变化均使缓存失效。"""
    import hashlib
    documents = script_structure_documents(project)
    versions = []
    for path in (*documents.source_documents, *documents.output_documents):
        try:
            versions.append((path, hashlib.sha256(path.read_bytes()).digest()))
        except OSError:
            versions.append((path, None))
    return documents.source, documents.target, tuple(versions)


def adopt_natural_script(project, source_path, *, publish):
    """采用明确选中的自然剧本内容版本，经 L3 发布台账。"""
    import hashlib
    import json
    import contract.script_contract as script_contract
    root = Path(project).resolve()
    source = selected_workspace_document(script_contract.natural_script_paths(root), source_path)
    record = {'path': source.relative_to(root).as_posix(),
              'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
    publish(script_contract.natural_script_selection_path(root),
            json.dumps(record, ensure_ascii=False, indent=2) + '\n',
            lambda text: json.loads(text) == record, lambda _path: None)
    return source


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
    """返回删除目标：表格里选中的各行；没有时回退到当前高亮项。"""
    checked = {str(path) for path in checked_paths}
    selected = [path for path in item_paths if str(path) in checked]
    if not selected:
        selected = list(active_paths)[:1]
    if not selected:
        raise ValueError('请先选择要删除的剧本文件')
    return selected_script_paths(project, selected, require_files=True)


def script_deletion_selection(project, item_paths, checked_paths, active_paths=()):
    """构建剧本删除计划，并标出是否会删掉当前列表中的全部文件。"""
    paths = batch_selected_script_paths(project, item_paths, checked_paths, active_paths)
    items = {str(path) for path in item_paths}
    selected = {str(path) for path in paths}
    return ScriptDeletionSelection(paths=paths, deletes_all=bool(items) and items == selected)


def renamed_script_path(project, source_path, requested_name):
    """校验剧本重命名请求，并返回尚未占用的同目录目标路径。

    R3110（任务书 P2，Q3／Q24-1）：非法字符、Windows 保留名（CON/PRN/…）、末尾点空格、
    超长名一律由 L0 命名中心 ``contract.file_naming.validate`` 拦下并给出可读原因；
    这里不再另写一套简化校验。
    """
    from contract.file_naming import validate as validate_file_name
    _plain_project_path(project, source_path)
    source = selected_script_paths(project, [source_path], require_files=True)[0]
    name = validate_file_name(requested_name)
    target = source.with_name(name)
    _plain_project_path(project, target)
    if source.suffix.lower() != target.suffix.lower():
        raise ValueError('改名不能更改扩展名，请保留原文件格式：' + source.suffix)
    if target == source:
        return source
    if target.exists():
        raise ValueError('目标文件名已存在：' + name)
    return target


def _plain_project_path(project, path):
    """保留词法路径检查每个祖先，拒绝包括内部跳转在内的 reparse point。"""
    root, path = Path(os.path.abspath(project)), Path(os.path.abspath(path))
    if not path.is_relative_to(root):
        raise ValueError('只能操作当前项目内的文件')
    for part in (path, *path.parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('路径包含符号链接或目录联接，无法安全改名：' + str(part))
    return path


def _rename_file(source, target):
    """排他发布完整正文；不能使用会覆盖竞争目标的 replace/rename。"""
    try:
        os.link(source, target)
    except OSError:
        LOGGER.exception('剧本文档重命名失败：%s -> %s', source, target)
        raise


def _rename_references(project, source, target):
    """只更正已知路径字段；其他 JSON 中命中源路径则停止，不猜测其语义。"""
    from contract.stage_path_service import read_dirs
    from contract.script_contract import natural_script_selection_path
    from file_cache import read_json
    root = Path(project).absolute()
    selection = natural_script_selection_path(root)
    stages = tuple(read_dirs(root, 'script'))
    known = {folder / 'preparation_state.json': folder for folder in stages}
    known[selection] = root
    paths = set(known) | set(root.glob('*.json'))
    for folder in stages:
        _plain_project_path(root, folder)
        for directory, children, files in os.walk(folder, followlinks=False):
            children[:] = [name for name in children
                           if not Path(directory, name).is_symlink()
                           and not getattr(Path(directory, name), 'is_junction', lambda: False)()]
            paths.update(Path(directory, name) for name in files if name.endswith('.json'))
    updates = []
    for path in sorted(paths):
        if not path.exists():
            continue
        _plain_project_path(root, path)
        try:
            payload = read_json(path)
        except (ValueError, UnicodeError) as exc:
            raise ValueError('引用记录无法读取，请修复后再改名：' + path.name) from exc
        if not isinstance(payload, (dict, list)) or (path in known and not isinstance(payload, dict)):
            raise ValueError('引用记录无法读取，请修复后再改名：' + path.name)
        base = known.get(path, root)
        changed = _rewrite_source_refs(payload, path, base, source, target, selection, (root, *stages))
        if changed:
            updates.append((path, payload))
    return updates


def _rewrite_source_refs(payload, record, base, source, target, selection, reference_bases):
    supported = {('path',)} if record == selection else set()
    if record.name == 'preparation_state.json' and record.parent in reference_bases[1:]:
        for prefix, box in (((), payload), (('revision',), payload.get('revision', {}))):
            if isinstance(box, dict):
                for index, _ in enumerate(box.get('documents') or ()):
                    supported.add(prefix + ('documents', index, 'path'))
        supported.add(('revision', 'source_path'))
        for index, _ in enumerate(payload.get('snapshots') or ()):
            supported.add(('snapshots', index, 'path'))
    changed = False
    def visit(value, trail=()):
        nonlocal changed
        if isinstance(value, (dict, list)):
            for key, item in (value.items() if isinstance(value, dict) else enumerate(value)):
                if isinstance(item, (dict, list)):
                    visit(item, trail + (key,))
                elif isinstance(item, str) and item:
                    candidate = Path(item.replace('\\', '/'))
                    bases = (base,) if trail + (key,) in supported else (*reference_bases, source.parent)
                    if not any(Path(os.path.abspath(parent / candidate)) == source for parent in bases):
                        continue
                    if trail + (key,) not in supported:
                        raise ValueError('发现无法安全更正的引用，请先解除引用：' + record.name
                                         + ' / ' + '.'.join(map(str, trail + (key,))))
                    value[key] = (str(target) if candidate.is_absolute()
                                  else target.relative_to(base).as_posix())
                    changed = True
    visit(payload)
    return changed


def _rename_transaction(project, source, target):
    from agent.core import rename_with_references

    def prepare():
        _plain_project_path(project, source)
        _plain_project_path(project, target)
        return _rename_references(project, source, target)

    try:
        rename_with_references(source, target, prepare)
    except BaseException:
        LOGGER.exception('剧本文档重命名失败：%s -> %s', source, target)
        raise


def rename_script_document(project, source_path, requested_name):
    """校验并执行当前剧本准备目录内的单文件重命名。"""
    try:
        try:
            source = selected_script_paths(project, [source_path], require_files=True)[0]
            _plain_project_path(project, source_path)
            target = renamed_script_path(project, source, requested_name)
        except ValueError as exc:
            if isinstance(exc.__cause__, OSError):
                raise exc.__cause__
            # R3153：被拒绝的改名也要留 ERROR 记录（既有契约：失败路径可追溯）。
            LOGGER.error('剧本文档重命名被拒绝：%s', exc)
            return UserError(str(exc))
        if target != source:
            _rename_transaction(project, source, target)
            _update_index_after_rename(project, source, target)
    except ValueError as exc:
        LOGGER.warning('剧本文档重命名被拒绝：%s', exc)
        return UserError(str(exc))
    except FileExistsError:
        return UserError('目标文件名已存在：' + target.name)
    except (OSError, RuntimeError):
        LOGGER.exception('剧本文档重命名失败')
        return SystemError('剧本文档重命名失败：目标文件可能正被其他程序占用，或当前账号没有权限。')
    return success(target)


def rename_project_file(project, source_path, requested_name):
    """任意项目文件的安全改名；未知引用明确阻止，不静默破坏采用状态。"""
    from contract.file_naming import validate as validate_file_name
    try:
        source = _plain_project_path(project, source_path)
        if not source.is_file():
            return UserError('所选文件缺失或已移动，请刷新后重试')
        target = source.with_name(validate_file_name(requested_name))
        _plain_project_path(project, target)
        if target.suffix.lower() != source.suffix.lower():
            return UserError('改名不能更改扩展名，请保留原文件格式：' + source.suffix)
        if target == source:
            return success(source)
        if target.exists():
            return UserError('目标文件名已存在：' + target.name)
        _rename_transaction(project, source, target)
        _update_index_after_rename(project, source, target)
        return success(target)
    except FileExistsError:
        return UserError('目标文件名已存在，请刷新后重试')
    except ValueError as exc:
        return UserError(str(exc))
    except (OSError, RuntimeError):
        LOGGER.exception('项目文件重命名失败')
        return SystemError('项目文件重命名失败，请关闭占用该文件的程序后重试。')


def _update_index_after_rename(project, source, target):
    """改名后增量更新项目文件索引；索引只是缓存，失败只记日志。"""
    try:
        from infra import file_index
        file_index.update(project, [source, target])
    except Exception:
        LOGGER.debug('改名后索引未更新，等待下次重建', exc_info=True)
