"""受控读取剧本准备对话的文本附档。

模型不能访问用户电脑上的本地路径，因此附件必须在桌面端读成有边界的文本后才可提交。
这里刻意不解析二进制 Office/PDF/图片，避免把不确定的内容或超大文件塞进模型上下文。
"""
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile
from functools import wraps
import logging
from service_contract import SystemError, UserError, success
from project_context import ProjectContext


MAX_FILES = 5
MAX_FILE_BYTES = 1_000_000
MAX_TOTAL_CHARS = 24_000
TEXT_SUFFIXES = frozenset({'.txt', '.md', '.markdown', '.json', '.csv', '.yaml', '.yml', '.log'})
INPUT_FOLDER = '输入'


def _store_result(function):
    @wraps(function)
    def run(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except OSError:
            logging.getLogger(__name__).exception('创意附档归档失败')
            return SystemError('创意附档归档失败，请检查文件权限和磁盘空间。')
    return run


def _read_text(path):
    data = path.read_bytes()
    if len(data) > MAX_FILE_BYTES:
        raise ValueError('附档过大（单个文件最多 1 MB）：' + path.name)
    for encoding in ('utf-8-sig', 'utf-8', 'gb18030'):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError('附档不是可识别的文本编码：' + path.name)


def _read_docx(path):
    """只取 DOCX 的正文段落；不执行嵌入对象或宏。"""
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError('附档过大（单个文件最多 1 MB）：' + path.name)
    try:
        with zipfile.ZipFile(path) as archive:
            raw = archive.read('word/document.xml')
        root = ET.fromstring(raw)
    except (OSError, KeyError, zipfile.BadZipFile, ET.ParseError) as exc:
        raise ValueError('DOCX 无法读取：' + path.name) from exc
    ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    return '\n'.join(''.join(node.text or '' for node in paragraph.iter(ns + 't'))
                     for paragraph in root.iter(ns + 'p')).strip()


def read_source(path):
    path = Path(path)
    return _read_docx(path) if path.suffix.lower() == '.docx' else _read_text(path)


def input_folder(context):
    if not isinstance(context, ProjectContext):
        raise TypeError('创意附档需要由 L3 注入 ProjectContext。')
    return context.stage_resolver('script') / INPUT_FOLDER


@_store_result
def store(context, paths, now=None, *, publish=None):
    """将用户选择的文本转换为项目内可引用的 Markdown，结果携带存档路径。

    正式项目成果由 L3 注入发布器；这里不保留直写回退。
    """
    if not callable(publish):
        raise TypeError('创意附档归档需要由 L3 注入发布器。')
    selected = tuple(dict.fromkeys(Path(value) for value in (paths or ()) if str(value).strip()))
    if len(selected) > MAX_FILES:
        return UserError('一次最多附加 %d 个文件。' % MAX_FILES)
    folder = input_folder(context)
    folder.mkdir(parents=True, exist_ok=True)
    stamp = (now or datetime.now()).strftime('%Y%m%d_%H%M%S_%f')
    saved = []
    for index, path in enumerate(selected, 1):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES | {'.docx'}:
            return UserError('仅支持 .md、.txt、.docx：' + path.name)
        try:
            text = read_source(path).strip()
        except ValueError as exc:
            if isinstance(exc.__cause__, OSError):
                raise exc.__cause__ from exc
            return UserError(str(exc))
        if not text:
            return UserError('附档为空：' + path.name)
        target = folder / ('故事创意_%s%s.md' % (stamp, ('_%d' % index) if len(selected) > 1 else ''))
        saved.append(publish(target, text + '\n'))
    return success(tuple(saved))


def uploaded(context, limit=None):
    paths = sorted(input_folder(context).glob('故事创意_*.md'), key=lambda item: item.stat().st_mtime, reverse=True)
    return tuple(paths[:limit] if limit else paths)


def referenced(context, message='', selected_paths=()):
    """解析本轮可提交的入库创意，绝不回读用户电脑中的原始上传路径。"""
    available = uploaded(context)
    selected = tuple(Path(path) for path in selected_paths if Path(path).is_file())
    explicit = tuple(path for path in available if ('@' + path.name) in str(message or ''))
    # @ 指向的文件优先；没有显式指向时，带上本次选择并补足最近三份，
    # 让多轮对话中的创意不会在下一句提问时丢失。
    candidates = explicit or (selected + tuple(path for path in available if path not in selected)[:3])
    if not candidates:
        candidates = available[:3]
    unique = []
    for path in candidates:
        if path not in unique:
            unique.append(path)
    return prepare(tuple(unique[:3]))


def prepare(paths):
    """验证并编排一次模型提交所需的附档上下文。

    返回的 ``context`` 使用明确边界，提示词中的文件内容不能伪装为操作指令；
    ``names`` 仅供界面和聊天记录展示，绝不把本地绝对路径交给模型。
    """
    selected = tuple(dict.fromkeys(Path(value) for value in (paths or ()) if str(value).strip()))
    if len(selected) > MAX_FILES:
        raise ValueError('一次最多附加 %d 个文件。' % MAX_FILES)
    parts = []
    names = []
    details = []
    used = 0
    for path in selected:
        if not path.is_file():
            raise ValueError('附档不存在或不是文件：' + path.name)
        if path.suffix.lower() not in TEXT_SUFFIXES | {'.docx'}:
            raise ValueError('暂仅支持文本附档（.txt、.md、.docx、.json、.csv、.yaml、.log）：' + path.name)
        text = read_source(path).strip()
        if not text:
            raise ValueError('附档为空：' + path.name)
        remaining = MAX_TOTAL_CHARS - used
        if remaining <= 0:
            raise ValueError('附档总内容超过 %d 字，请减少文件或内容。' % MAX_TOTAL_CHARS)
        clipped = text[:remaining]
        used += len(clipped)
        names.append(path.name)
        details.append((path.name, len(clipped)))
        parts.append('【附档：%s】\n<attachment_text>\n%s\n</attachment_text>' % (path.name, clipped))
        if len(clipped) < len(text):
            raise ValueError('附档总内容超过 %d 字，请减少文件或内容。' % MAX_TOTAL_CHARS)
    return {'paths': selected, 'names': tuple(names), 'details': tuple(details),
            'context': '\n\n'.join(parts)}
