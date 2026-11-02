# -*- coding: utf-8 -*-
"""创意对话：剧本准备页的创意栏改成跟模型对话的那一扇窗。

用户原话：「把创意内容栏改为打开 agent 后与 LLM 的对话框；保存创意按钮改为提交创意，
本地再保存提交创意的文件，通过 agent 与 LLM 对话，只保存 LLM 输出文本」。

落地口径（三件事各自只有一个归属）：
- 整段对话按轮次记在 writing/创意对话/对话.json（界面重建后照样看得见，翻页不丢）；
- **只有模型的输出**落成下游读的那个创意文件：writing/<Provider>/<模型名>/创意_<日期>/<项目>_<集数>_<日期>.md
  （模型回复设定／大纲／角色卡／剧本时自动存档，手改过的不覆盖；每个 Provider 和模型各自保留目录）。

这一份只做文件与人话：不碰 Tk、不发网络。问模型那一趟由界面注入（自检传假函数），离线可跑。
"""
import re
from collections import namedtuple
from pathlib import Path
from idea_script_heuristic import looks_like_script
from project_context import ProjectContext
from script_contract import INLINE_REQUIRED_LABELS, PRODUCTION_LOCK_DEFINITIONS, stage_lock_requirements, stage_lock_definitions
from idea_brief_form import (
    BRIEF_CREATION_FIELDS, brief_creation_values, extract_brief_creation, format_brief_creation,
    inline_required_missing, inline_template_labels, merge_brief_creation,
    strip_inline_required_markers, _brief_plain_text)
from idea_document_paths import (
    PROJECT_DOCUMENT_DIRS, ChatModel, brief_complete_path, brief_raw_path, legacy_brief_raw_path,
    project_document_directory, project_script_filename, reply_document_path, reply_path_parts,
    storage_identity, _file_day, _file_part, _project_file_type, _storage_name)
from idea_transcript import (
    CHAT_NAME, FOLDER, _HISTORY_CACHE_LIMIT, _all_rows, _history_cache, _read_rows, _row_indexes,
    _stamp, _visible_claude_text, append, chat_model, compact_context, deleted_history_path,
    history_path, load, model_history_path, remove, remove_all, remove_message, repair_internal_replies, replace,
    restore_latest_removed, save_rows)

RAW_SCRIPT_NAME = 'script_raw.md'
REPLY_LIMIT = 20000          # 一次回复最多留这么多字：模型跑飞时不至于把文件写爆
PROJECT_CONTENT_MARKS = ('项目设定', '人物设定', '角色卡', '世界观', '需求梳理', '项目大纲', '大纲', '纲要', '分集', '剧本', '场景', '镜头', '台词')


def _context(value):
    if not isinstance(value, ProjectContext):
        raise TypeError('创意聊天项目路径需要由 L3 注入 ProjectContext。')
    return value


def _require_gateway(gateway):
    """创意聊天的正式读写只能由 L3 注入，避免 L2 自行落盘。"""
    required = ('read_json', 'publish_json', 'publish_text')
    if not isinstance(gateway, dict) or any(not callable(gateway.get(name)) for name in required):
        raise TypeError('创意聊天读写需要由 L3 注入发布与读取网关。')
    return gateway


def folder(context):
    from project_stages import writing
    return writing(_context(context).root) / FOLDER


def has_history(context, *, gateway=None):
    """项目里是否已有任一模型的聊天记录；只读，复用历史文件的 mtime 缓存，不做迁移。"""
    return bool(_all_rows(_context(context), gateway=gateway))


def skill_injection_summary(row):
    """请求记录显示已勾选与实际加载；不把历史记录伪装成有加载凭据。"""
    snapshot = row.get('skill_injection')
    if not isinstance(snapshot, dict):
        return ''
    selected = snapshot.get('selected') or []
    loaded = snapshot.get('loaded') or []
    names = '、'.join(str(item.get('name') or '') for item in loaded)
    return f"SKILL：已勾选 {len(selected)} 项，本次已加载 {len(loaded)} 项" + ('（' + names + '）' if names else '')


def usage_summary(rows):
    """仅概述当前模型最近一次已保存回复；缺报不能伪装成零消耗。"""
    row = next((row for row in reversed(rows) if row.get('role') == 'assistant'), {})
    budget, usage = row.get('context_budget') or {}, row.get('request_usage') or {}
    if not budget and not usage:
        return '本模型暂无用量记录'
    def shown(value):
        return str(value) if value is not None else '未提供'
    return ('上次请求：输入估算 ' + shown(budget.get('input_tokens')) + ' token / 容量 '
            + shown(budget.get('context_limit')) + '；输出预留 ' + shown(budget.get('output_reserved'))
            + '；API 实报输入/输出/缓存：' + '/'.join(shown(usage.get(key)) for key in
                ('prompt_tokens', 'completion_tokens', 'cached_tokens')))


def usage_compact(rows):
    """状态栏可见的一行用量：没有记录照旧说没有；有记录只留输入/输出。"""
    row = next((row for row in reversed(rows) if row.get('role') == 'assistant'), {})
    budget, usage = row.get('context_budget') or {}, row.get('request_usage') or {}
    if not budget and not usage:
        return '本模型暂无用量记录'
    def shown(value):
        return str(value) if value is not None else '未提供'
    if usage:
        return ('上次 ' + shown(usage.get('prompt_tokens')) + '/'
                + shown(usage.get('completion_tokens')) + ' token')
    return '上次 输入 ' + shown(budget.get('input_tokens')) + ' token'


def save_reply(root, text, at=None, provider='', model='', *, publish=None, reuse_latest=True):
    """组织要存档的模型创意（自动存档走这里）；发布由调用方注入的 L3 完成。"""
    context = _context(root)
    value = str(text or '').replace('\r\n', '\n').strip()
    if not value:
        raise ValueError('模型没有输出文字，未写入创意文件')
    if not is_project_document_text(value):
        raise ValueError('模型回复不是项目设定、大纲、角色卡或剧本，未写入项目文件')
    if not callable(publish):
        raise TypeError('模型创意文件需要由 L3 注入发布器。')
    file_type = _project_file_type(value)
    if file_type == '自然剧本':
        from script_contract import require_natural_script
        value = require_natural_script(value)
    from stage_path_service import write_dir
    path = reply_document_path(context, value, at=at, provider=provider, model=model, file_type=file_type,
                               reuse_latest=reuse_latest)
    # 正文与既有文件一致才复用；审阅参考稿（设定／大纲／角色卡）正文变了要覆盖写入。
    if path.is_file() and path.read_text(encoding='utf-8', errors='ignore').strip() == value:
        return path
    parts = path.relative_to(write_dir(context.root, 'script')).parts
    folder = '/'.join(parts[:-2])
    name = '/'.join(parts)
    return publish(context.root, ({'name': name, 'data': value.encode('utf-8'),
                           'directories': tuple(folder + '/' + directory
                                                for directory in PROJECT_DOCUMENT_DIRS.values())},))[name]


_DOWNLOAD_COPY_SUFFIX = re.compile(r'\s*\(\d+\)(?=\.md$)', re.I)
DOWNLOAD_IMPORT_MAX_AGE = 3 * 24 * 3600   # 只收回近三天下载的文件，不翻旧账
_DOCUMENT_PROJECT_FIELD = re.compile(
    r'(?im)^[ \t]*(?:[-*#]+[ \t]*)?(?:项目名(?:称)?|剧名|片名)[ \t]*[：:][ \t]*([^\r\n]*)')
_DOCUMENT_TITLE_LABELS = ('项目设定', '世界观', '需求梳理', '项目大纲', '剧本大纲', '故事大纲',
                          '分集大纲', '纲要', '角色卡', '人物设定', '自然剧本', '项目剧本')


def _document_project_name(text):
    "从创作正文中取项目名；只认明确字段或首行标题里的类型标签，取不到返回空串。"
    value = str(text or '').replace('\r\n', '\n')
    match = _DOCUMENT_PROJECT_FIELD.search(value)
    if match:
        raw = match.group(1).strip()
        found = re.search(r'《([^》]+)》', raw)
        candidate = found.group(1) if found else raw.strip('《》')
        candidate = candidate.strip()
        if candidate and candidate not in _DOCUMENT_TITLE_LABELS:
            return candidate
    heading = next((line.strip() for line in value.split('\n') if line.strip()), '')
    heading = heading.lstrip('# \t').strip()
    if not heading:
        return ''
    found = re.search(r'《([^》]+)》', heading)
    if found and any(label in heading for label in _DOCUMENT_TITLE_LABELS):
        candidate = found.group(1).strip()
        if candidate not in _DOCUMENT_TITLE_LABELS:
            return candidate
    for label in sorted(_DOCUMENT_TITLE_LABELS, key=len, reverse=True):
        position = heading.find(label)
        if position < 0:
            continue
        candidate = (heading[:position] + heading[position + len(label):]).strip(' \t：:｜|-—·_')
        if candidate and candidate not in _DOCUMENT_TITLE_LABELS:
            return candidate
    return ''


def _same_project_name(candidate, expected):
    def normalize(value):
        return re.sub(r'\s+', ' ', str(value or '').replace('《', '').replace('》', '')).strip().casefold()
    return bool(normalize(candidate)) and normalize(candidate) == normalize(expected)


def _filename_day(filename):
    "四段式 .md 文件名末尾的日期段（规则同下载收回），不是合法日期返回空串。"
    from download_inbox import filename_day
    name = Path(str(filename or '')).name
    return filename_day(name) if name.lower().endswith('.md') else ''


_FILENAME_PROJECT_SPLIT = re.compile(r'[\s_\-—·｜|,，、;；:：()（）\[\]【】]+')


def _filename_names_project(filename, expected):
    "文件名兜底：去掉浏览器副本后缀与 .md 后，任一完整段等于当前项目名才认。"
    name = _DOWNLOAD_COPY_SUFFIX.sub('', Path(str(filename or '')).name)
    name = re.sub(r'\.md$', '', name, flags=re.I)
    return any(_same_project_name(part, expected)
               for part in _FILENAME_PROJECT_SPLIT.split(name) if part)


def import_downloaded_documents(root, folder, provider='', model='', *, publish=None, now=None, backups=None):
    """收回用户从桌面 Agent 窗口（如 Claude Desktop）下载到「下载」文件夹的创作文件。

    桌面窗口有时只给出下载文件而不直接写入任务书指定的路径；四段式文件名
    ``项目名_文件类型_内容_年月日.md``（浏览器追加的「 (N)」也认）按项目／类型／
    Provider 内容段找回；文件名不合格式时改为按正文判类，并用正文里的项目名与当前
    项目核对；正文没写项目名时，由文件名中的完整项目名段兜底。每类只取最新一份，
    且必须比本模型该类已保存的最新文件更新；落盘复用
    ``save_reply``：设定／大纲／角色卡覆盖同一份，自然剧本同稿复用、异稿编号。
    下载目录里的原文件保持不动。覆盖已有且内容不同的文件前，先把原文件复制到项目
    「覆盖前备份」（用户可能手改过它）；备份失败就不覆盖这一份。传入 ``backups``
    列表时，追加 ``(原文件, 备份副本)``。

    返回 ``[(文件类型, 已写入路径), ...]``；没有可收回的文件时返回空列表。
    """
    context = _context(root)
    if not callable(publish):
        raise TypeError('收回下载文件需要由 L3 注入发布器。')
    import time
    import storage_maintenance
    from script_contract import project_name, stage_file_info
    from stage_path_service import write_dir
    source = Path(folder)
    try:
        entries = tuple(source.glob('*.md')) if source.is_dir() else ()
    except OSError:
        entries = ()
    now = time.time() if now is None else now
    expected_project = project_name(context.root)
    expected_provider = str(provider or '').strip()
    newest = {}
    for path in entries:
        try:
            if not path.is_file():
                continue
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if now - mtime > DOWNLOAD_IMPORT_MAX_AGE:
            continue
        body = None
        info = stage_file_info(_DOWNLOAD_COPY_SUFFIX.sub('', path.name))
        if info and info.get('format') == 'stage-v1':
            file_type = info.get('file_type')
            if info.get('project') != expected_project or file_type not in PROJECT_DOCUMENT_DIRS:
                continue
            content = re.sub(r'\(\d+\)$', '', str(info.get('content') or '')).strip()
            if expected_provider and content != expected_provider:
                continue
        else:
            try:
                body = path.read_text(encoding='utf-8-sig')
            except (OSError, UnicodeDecodeError):
                continue
            if not is_project_document_text(body):
                continue
            file_type = _project_file_type(body)
            if file_type not in PROJECT_DOCUMENT_DIRS:
                continue
            body_project = _document_project_name(body)
            if body_project:
                if not _same_project_name(body_project, expected_project):
                    continue
            elif not _filename_names_project(path.name, expected_project):
                continue
        if file_type not in newest or mtime > newest[file_type][0]:
            newest[file_type] = (mtime, path, body)
    if not newest:
        return []
    model_dir = write_dir(context.root, 'script') / _storage_name(provider, '未知Provider') / _storage_name(model, '未知模型')
    imported = []
    for file_type, (mtime, path, body) in sorted(newest.items()):
        latest = 0
        category = project_document_directory(file_type)
        try:
            batches = tuple(model_dir.iterdir()) if model_dir.is_dir() else ()
        except OSError:
            batches = ()
        for batch in batches:
            try:
                for existing in (batch / category).glob('*.md'):
                    latest = max(latest, existing.stat().st_mtime)
            except OSError:
                continue
        if mtime <= latest:
            continue
        if body is None:
            try:
                text = path.read_text(encoding='utf-8-sig')
            except (OSError, UnicodeDecodeError):
                continue
        else:
            text = body
        if not is_project_document_text(text) or _project_file_type(text) != file_type:
            continue
        value = text.replace('\r\n', '\n').strip()
        try:
            # 下载件文件名日期比已有那份新（桌面应用按当天命名）时另存到新日期批次，旧版本保留。
            at, reuse_latest = None, True
            day = _filename_day(path.name)
            latest_path = reply_document_path(context, value, provider=provider, model=model, file_type=file_type)
            if day and latest_path.is_file() and day > (_filename_day(latest_path.name) or day):
                from datetime import datetime
                at, reuse_latest = datetime.strptime(day + '12', '%Y%m%d%H').timestamp(), False
            # 正文与将覆盖的文件一致时 save_reply 不会重写；只报告真正更新的文件。
            target = reply_document_path(context, value, at=at, provider=provider, model=model,
                                         file_type=file_type, reuse_latest=reuse_latest)
            unchanged = target.is_file() and target.read_text(encoding='utf-8', errors='ignore').strip() == value
            backup = None if unchanged else storage_maintenance.backup_before_overwrite(context.root, target)
            saved = save_reply(context, text, at=at, provider=provider, model=model, publish=publish,
                               reuse_latest=reuse_latest)
        except (OSError, ValueError):
            continue
        if backup is not None and backups is not None:
            backups.append((target, backup))
        if not unchanged:
            imported.append((file_type, Path(saved)))
    return imported


def save_manual_creative(root, text, at=None, *, publish=None):
    """组织用户手写创意；发布由调用方注入的 L3 完成。"""
    context = _context(root)
    value = str(text or '')
    if not value.strip():
        raise ValueError('请先填写自己的创意。')
    if not callable(publish):
        raise TypeError('手动创意文件需要由 L3 注入发布器。')
    day = _file_day(at)
    from script_contract import require_natural_script
    require_natural_script(value)
    name = '/'.join(('创意_' + day, project_document_directory('自然剧本'),
                     project_script_filename(context, at=at, file_type='自然剧本',
                                          content='手动创意')))
    return publish(context.root, ({'name': name, 'data': value.encode('utf-8'),
                           'directories': tuple('创意_' + day + '/' + directory
                                                for directory in PROJECT_DOCUMENT_DIRS.values())},))[name]


# 自动存档的类型短名：保存类型 → 状态栏里的叫法。
DOWNLOAD_LABELS = {'项目设定': '设定', '项目大纲': '大纲', '角色卡': '角色卡', '自然剧本': '剧本'}


def download_kind(text):
    """当前模型输出能存成哪一类文件（设定／大纲／角色卡／剧本）；不能存返回空串。

    剧本仍要求完整剧本结构；设定、大纲、角色卡按标题归类即可存档审阅。
    """
    value = str(text or '').strip()
    if not is_project_document_text(value):
        return ''
    file_type = _project_file_type(value)
    if file_type == '自然剧本' and not looks_like_script(value):
        return ''
    return DOWNLOAD_LABELS.get(file_type, '')


def is_project_document_text(text):
    """仅让可归入项目设定、大纲、角色卡或剧本的模型正文进入项目文件。"""
    value = str(text or '').strip()
    return bool(value and any(mark in value for mark in PROJECT_CONTENT_MARKS))


# 自动存档结果：kept 是正文与本对话任一回复都对不上（多半手改过）而没被覆盖的旧文件；
# new_script 表示这是本模型对话里第一份剧本，三虎只在这时问要不要进分镜。
AutoSaved = namedtuple('AutoSaved', 'kind path kept new_script')


def _script_reply(text):
    """会存成项目剧本的模型回复：剧本结构完整，且过得了自然剧本闸门。"""
    from script_contract import is_natural_script
    return download_kind(text) == '剧本' and is_natural_script(text)


def auto_save_reply(root, model='', *, publish=None, gateway=None, at=None):
    """把本模型最新一条回复存成设定／大纲／角色卡／剧本；不是这四类返回 None。

    设定／大纲／角色卡照旧覆盖本模型最新一份；那份正文与本对话任一回复都对不上时视为
    手改过，不覆盖，按 ``at`` 的日期另存一份。剧本一向另存新版本，同稿复用原文件。
    """
    context = _context(root)
    replies = [str(row.get('text') or '').replace('\r\n', '\n').strip()
               for row in load(context, model=model, gateway=gateway) if str(row.get('role')) != 'user']
    reply = replies[-1] if replies else ''
    kind = download_kind(reply)
    if not kind:
        return None
    provider, name = storage_identity(model)
    file_type = _project_file_type(reply)
    value = reply
    if file_type == '自然剧本':
        from script_contract import require_natural_script
        value = require_natural_script(reply)
    current = reply_document_path(context, value, at=at, provider=provider, model=name, file_type=file_type)
    existing = (current.read_text(encoding='utf-8', errors='ignore').replace('\r\n', '\n').strip()
                if current.is_file() else '')
    kept = current if existing and existing != value and existing not in replies else None
    path = save_reply(context, reply, at, provider, name, publish=publish, reuse_latest=kept is None)
    new_script = kind == '剧本' and not existing and not any(_script_reply(text) for text in replies[:-1])
    return AutoSaved(kind, path, kept, new_script)


def import_local_document(root, text, filename, at=None, *, publish=None):
    """「添加剧本」：本地文件按正文归入设定／大纲／角色卡／剧本，认不出的归剧本。

    返回 ``(保存类型, 路径)``。同目录已有同样正文时复用那份；同名不覆盖，文件内容段递增 (N)。
    """
    context = _context(root)
    value = str(text or '').replace('\r\n', '\n').strip()
    if not value:
        raise ValueError('文件里没有文字')
    if not callable(publish):
        raise TypeError('添加的剧本文件需要由 L3 注入发布器。')
    from script_contract import project_name, require_natural_script, stage_file_info
    from stage_path_service import write_dir
    file_type = _project_file_type(value)
    if file_type == '自然剧本':
        value = require_natural_script(value)
    stem = Path(filename).stem
    label = (stage_file_info(stem + '.md') or {}).get('content') or stem
    title = project_name(context.root)
    if label.startswith(title) and label[len(title):].startswith((' ', '-', '_')):
        label = label[len(title):].lstrip(' -_') or label
    label = _file_part(label, '添加文件')
    batch, directory = '创意_' + _file_day(at), project_document_directory(file_type)
    folder = write_dir(context.root, 'script') / batch / directory
    if folder.is_dir():
        for existing in sorted(folder.glob('*.md')):
            if existing.is_file() and existing.read_text(encoding='utf-8', errors='ignore').strip() == value:
                return file_type, existing
    content, number = label, 0
    while (folder / project_script_filename(context, at=at, file_type=file_type, content=content)).exists():
        number += 1
        suffix = '(' + str(number) + ')'
        content = label[:80 - len(suffix)] + suffix
    name = '/'.join((batch, directory, project_script_filename(context, at=at, file_type=file_type, content=content)))
    return file_type, publish(context.root, ({'name': name, 'data': value.encode('utf-8'),
                                              'directories': tuple(batch + '/' + folder_name for folder_name
                                                                   in PROJECT_DOCUMENT_DIRS.values())},))[name]


def _brief_value(text, labels):
    """从用户常见的“字段：内容”写法中取值，不猜测未明说的信息。"""
    names = '|'.join(re.escape(label) for label in labels)
    match = re.search(r'(?im)(?:^|\t)[ ]*(?:[-*#]+[ \t]*)?(?:' + names + r')[ *]*[：:\t][ \t]*([^\r\n]*)',
                      _brief_plain_text(text, (*BRIEF_CREATION_FIELDS, *INLINE_REQUIRED_LABELS, *labels)))
    value = match.group(1).strip() if match else ''
    labels = BRIEF_CREATION_FIELDS + ('故事主体', '故事主题', '题材类型', '题材', '类型', '风格', '集数',
        '单集时长', '时长', '篇幅', '主要角色', '角色', '故事人物', '人物设定',
        '故事主线', '故事概述', '剧情', '角色物理特征', '外貌特征', '外貌', '形象', '额外要求', '要求')
    if value and any(value in label or label in value for label in labels):
        return ''
    return value


def _brief_fields(raw):
    """把累计的用户原话提取为契约字段；无标签的整段创意仍是故事梗概。"""
    text = str(raw or '').strip()
    from script_contract import normalize_brief
    genre_words = ('都市', '悬疑', '奇幻', '科幻', '仙侠', '武侠', '校园', '爱情', '喜剧', '恐怖', '冒险', '现实')
    genre = _brief_value(text, ('故事题材', '故事主题', '题材类型', '题材', '类型', '风格'))
    if not genre:
        genre = next((word for word in genre_words if word in text), '')
    episodes = _brief_value(text, ('故事集数', '集数'))
    duration = _brief_value(text, ('单集时间', '单集时长', '时长'))
    length = _brief_value(text, ('篇幅',)) or '；'.join(
        part for part in (('故事集数：' + episodes) if episodes else '',
                          ('单集时间：' + duration) if duration else '') if part)
    if not length:
        found = re.search(r'\d+\s*(?:集|分钟|min|字)', text, re.I)
        length = found.group(0) if found else ''
    characters = _brief_value(text, ('故事角色', '主要角色', '角色', '故事人物', '人物设定'))
    if not characters:
        candidate = re.search(r'(?m)^.*(?:主角|男主|女主).+$', text)
        characters = candidate.group(0).strip() if candidate else ''
    fields = {
        'story_summary': _brief_value(text, ('故事梗概', '故事主体', '故事主线', '故事概述', '剧情')) or (
            '' if re.search(r'(?m)^[ \t]*(?:[-*#]+[ \t]*)?(?:故事梗概|故事主体|故事主线|故事概述|剧情)[ \t]*[：:\t]', text) else text),
        'main_characters': characters,
        'physical_features': _brief_value(text, ('物理特征', '角色物理特征', '外貌特征', '外貌', '形象')),
        'genre': genre,
        'length': length,
        'special_requirements': _brief_value(text, ('特殊要求', '内容补充', '额外要求', '要求')),
    }
    return normalize_brief(fields)


def _append_raw_brief(root, text, *, gateway=None):
    """把多轮补充汇总为一个原始简报，供完整性检查读取。"""
    gateway = _require_gateway(gateway)
    path = brief_raw_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    value = str(text or '').strip()
    if path.is_file():
        previous = path.read_text(encoding='utf-8')
    else:
        old = legacy_brief_raw_path(root)
        previous = old.read_text(encoding='utf-8') if old.is_file() else ''
    if value and value not in previous:
        gateway['publish_text'](path, previous.rstrip() + ('\n\n' if previous.strip() else '') + value + '\n')
    return path


def save_brief_creation(root, values, *, gateway=None):
    """保存表格内容到唯一简报文件，并返回可直接发送的文本。"""
    text = strip_inline_required_markers(values) if isinstance(values, str) else format_brief_creation(values)
    path = brief_raw_path(root)
    _require_gateway(gateway)['publish_text'](path, text)
    return path, text


def _brief_source_text(root, raw, *, gateway=None):
    """合并项目内用户已发送的对话，供简报完整性检查复用。"""
    sources = [str(raw or '').strip()]
    seen = {source for source in sources if source}
    for row in _all_rows(root, gateway=gateway):
        if str(row.get('role') or '').strip() != 'user':
            continue
        value = str(row.get('text') or '').strip()
        if value and value not in seen:
            sources.append(value)
            seen.add(value)
    return '\n\n'.join(source for source in sources if source)


def brief_followup(fields):
    """一次性询问所有仍缺的必填信息，不重复索要已提供的内容。"""
    from script_contract import BRIEF_LABELS, missing_brief_fields
    missing = missing_brief_fields(fields)
    if not missing:
        return ''
    labels = '、'.join(BRIEF_LABELS[field] for field in missing)
    return '为了开始创作，请一次补充以下信息：' + labels + '。已提供的内容无需重复。'


BRIEF_ATTACHMENT_NOTICE = '引用附档无本地可读转换稿,请补充填写或改用 .md/.txt 重新上传'


def receive_brief(root, text, workflow=None, lock_definitions=(), *, gateway=None, attachment_reference=None,
                  inline_text=None, inline_template=None, stage='script', created_at=None):
    """接收用户创意，落盘原始简报；满足必填项时才生成 brief_complete.json。"""
    lock_definitions = stage_lock_definitions(stage, lock_definitions)
    value = str(text or '').strip()
    if not value:
        raise ValueError('请先输入创意')
    gateway = _require_gateway(gateway)
    if inline_text is None:
        raw_path = _append_raw_brief(root, value, gateway=gateway)
        raw = raw_path.read_text(encoding='utf-8')
    else:
        # 当前模板优先；发送启动成功后由调用方覆盖保存，失败不吞掉上一份简报。
        raw_path = brief_raw_path(root)
        raw = strip_inline_required_markers(inline_text)
    extraction_text = '\n'.join((_brief_source_text(root, raw, gateway=gateway),
                                 *(attachment_reference or {}).get('brief_texts', ())))
    lock_sources = [raw, *(attachment_reference or {}).get('brief_texts', ())]
    if inline_text is not None:
        values = extract_brief_creation(raw, extra_labels=inline_template_labels(raw), include_extra=True)
        missing = inline_required_missing(inline_template, raw, tuple(values), stage=None, lock_definitions=lock_definitions) if inline_template is not None else ()
        current = '\n'.join(label + '：' + ' '.join(value.splitlines()) for label, value in values.items()
                            if value.strip() and label not in missing)
        lock_sources = [current, *(attachment_reference or {}).get('brief_texts', ())]
        extraction_text = '\n'.join(lock_sources)
    fields = _brief_fields(extraction_text)
    workflow = dict(workflow or {})
    selected_locks = {}
    name = str(workflow.get('name') or '').strip()
    # 已同步附档与手动配置优先于历史简报；本轮明确填写仍可覆盖。
    configured = (workflow.get('lock') or {}).get(name, {})
    for item in lock_definitions:
        labels = (item['label'], *item.get('aliases', ()), item['key'])
        selected_locks[item['key']] = (_brief_value(str(text or ''), labels)
            or configured.get(item['key'], '')
            or next((value for source in lock_sources
                     if (value := _brief_value(source, labels))), ''))
    fields['production_locks'] = {key: value for key, value in selected_locks.items() if value}
    from script_contract import validate_production_locks
    validate_production_locks(fields['production_locks'])
    from script_contract import brief_document, missing_brief_fields
    missing_locks = tuple(item for item in lock_definitions
                          if item['key'] in stage_lock_requirements(stage, created_at)
                          and not selected_locks.get(item['key']))
    missing = missing_brief_fields(fields) + tuple(item['key'] for item in missing_locks)
    followup = brief_followup(fields)
    if missing_locks:
        followup += ('\n' if followup else '') + '请补充本阶段制作锁：' + '、'.join(item['label'] for item in missing_locks) + '。'
    result = {'raw_path': raw_path, 'fields': fields, 'missing': missing,
              'followup': followup, 'complete_path': None,
              'attachment_notice': BRIEF_ATTACHMENT_NOTICE if (attachment_reference or {}).get('brief_unreadable') else ''}
    if missing:
        return result
    document = brief_document(fields)
    # 统筹锁在简报和项目投影中各保留一份：前者供人/模型阅读，后者供页面程序查询。
    if name:
        locks = fields['production_locks']
        if locks:
            document['brief']['production_locks'] = locks
            document['recommended_missing'] = [item for item in document['recommended_missing']
                                               if item != 'production_locks']
        namespaces = dict(workflow.get('lock') or {})
        namespaces[name] = locks
        workflow['lock'] = namespaces
    path = brief_complete_path(root)
    gateway['publish_json'](path, document)
    result['complete_path'] = path
    # L2 只形成投影数据；L4 调用方经 stage_config 的原子写入口落盘，避免领域服务反向依赖阶段编排层。
    result['workflow_projection'] = workflow if name else None
    return result


def latest_reply(root):
    """最近一份创意文件（模型的输出落的就是这一份）；一份都没有给 None。"""
    files = creative_documents(root)
    return files[-1] if files else None


def initial_brief_document(root):
    """剧本准备页首次打开时应编辑的创意文件。

    优先采用分类创意目录中最新的一份；老项目仍可从剧本准备根目录的 Markdown
    文件恢复，完全没有历史内容时则返回页面可首次保存的默认路径。
    """
    from project_stages import writing
    context = _context(root)
    writing_dir = writing(context.root)
    versions = creative_documents(root)
    if versions:
        return versions[-1]
    legacy = sorted((path for path in writing_dir.glob('*.md') if path.is_file()),
                    key=lambda path: path.stat().st_mtime)
    return legacy[-1] if legacy else default_brief_document(context)


def default_brief_document(root):
    """没有创意历史时，剧本准备页可首次保存的默认路径。"""
    from project_stages import writing
    return writing(_context(root).root) / '创意与剧本.md'


def creative_documents(root):
    """剧本准备阶段可见的创意文件，兼容旧文件但只把新文件写入分类目录。"""
    from project_stages import writing
    writing = writing(_context(root).root)
    # 新文件名不再依赖“创意与剧本”字样；目录本身才是下载版本的唯一归属。
    # 同时保留旧命名文件，让升级后仍能打开历史剧本。
    categories = set(PROJECT_DOCUMENT_DIRS.values())
    batches = []
    try:
        first_level = tuple(writing.iterdir())
    except OSError:
        first_level = ()
    # 当前布局固定为 writing/[Provider]/[Model]/创意_日期；同时兼容没有
    # Provider 或 Model 的历史项目。只枚举这一受控层级，首屏不能 rglob 整个项目。
    for first in first_level:
        try:
            if not first.is_dir() or first.name == '输入':
                continue
        except OSError:
            continue
        if first.name.startswith('创意_'):
            batches.append(first)
            continue
        try:
            second_level = tuple(first.iterdir())
        except OSError:
            continue
        for second in second_level:
            try:
                if not second.is_dir():
                    continue
            except OSError:
                continue
            if second.name.startswith('创意_'):
                batches.append(second)
                continue
            try:
                third_level = tuple(second.iterdir())
            except OSError:
                continue
            batches.extend(path for path in third_level
                           if path.is_dir() and path.name.startswith('创意_'))

    files = []
    for batch in batches:
        try:
            entries = tuple(batch.iterdir())
        except OSError:
            continue
        for path in entries:
            try:
                if path.is_file() and path.suffix.lower() == '.md':
                    # 升级前直系文件只用于读取历史，不参与新的保存和页面分类。
                    files.append(path)
                elif path.is_dir() and path.name in categories:
                    files.extend(item for item in path.iterdir()
                                 if item.is_file() and item.suffix.lower() == '.md')
            except OSError:
                continue
    return tuple(sorted(files,
                        key=lambda path: path.stat().st_mtime if path.exists() else 0))


def history_text(rows, limit=6):
    """最近几轮对话拼成一段（给模型看的上下文；只留最近几轮，前缀别越滚越长）。"""
    lines = []
    for row in list(rows or [])[-limit:]:
        who = '用户' if str(row.get('role')) == 'user' else '模型'
        lines.append(who + '：' + str(row.get('text') or '').strip())
    return '\n'.join(lines)


def history_context(rows, recent_limit=6, char_limit=12000, summary_limit=1800):
    """给模型的有界会话上下文：保留近况，并摘录较早的关键信息。

    聊天原文始终完整保存在本地；这里的“摘要”不调用模型、不落盘，只从较早
    消息的开头抽取有限片段，避免每次请求把长会话全文重新带上。
    """
    clean = [row for row in list(rows or [])
             if isinstance(row, dict) and str(row.get('text') or '').strip()]
    recent_limit = max(1, int(recent_limit))
    char_limit = max(1, int(char_limit))
    compacted = [row for row in clean if row.get('context_compacted') is True]
    if compacted:
        summary = _history_excerpt(compacted, min(summary_limit, char_limit // 3))
        pending = [row for row in clean if row.get('context_compacted') is not True]
        remaining = char_limit - len(summary) - 2
        if not pending or remaining <= 0:
            return summary[:char_limit]
        return summary + '\n\n' + history_context(pending, recent_limit, remaining, summary_limit)
    recent_rows = clean[-recent_limit:]
    early_rows = clean[:-recent_limit]
    recent = history_text(recent_rows, limit=recent_limit)
    if not early_rows:
        return recent[-char_limit:]

    summary = _history_excerpt(early_rows, min(summary_limit, char_limit // 3))
    remaining = max(0, char_limit - len(summary) - 2)
    if not remaining:
        return summary[:char_limit]
    return summary + '\n\n' + recent[-remaining:]


def _history_excerpt(rows, char_limit):
    excerpts = []
    # 早期设定和最近一次已确认内容通常都具有延续价值；中段细节由完整本地历史保留。
    sample = rows[:2] + rows[-4:]
    for row in sample:
        who = '用户' if str(row.get('role')) == 'user' else '模型'
        text = ' '.join(str(row.get('text') or '').split())
        if len(text) > 260:
            text = text[:257] + '…'
        item = who + '：' + text
        if item not in excerpts:
            excerpts.append(item)
    summary = '较早对话摘录（完整记录保存在本地）：\n' + '\n'.join(excerpts)
    return summary[:max(0, char_limit)]


def latest_text(root, model=None, *, gateway=None):
    """最近一条模型的回复正文（定稿时保存的就是它）；没有就是空串。"""
    for row in reversed(load(root, model=model, gateway=gateway)):
        if str(row.get('role')) != 'user':
            return str(row.get('text') or '').strip()
    return ''


def why_empty(result):
    """第 65 期任务 10：模型回了、正文却一个字都没有时，给一句能照做的话。

    用户报过「返回模型没有会话:空回复」——推理型的模型把 max_tokens 全花在思考上时，
    content 就是空的（finish_reason=length）。这跟「网络没通」是两回事，说清楚。
    """
    reason = ''
    data = (result or {}).get('data')
    if isinstance(data, dict):
        choices = data.get('choices')
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            reason = str(choices[0].get('finish_reason') or '')
    if reason == 'length':
        return '模型把这一次的输出额度用完了，正文一个字都没剩下；请把想问的写短一点再发一次。'
    return '模型未返回可显示正文：' + str((result or {}).get('error') or '空回复')


def prompt_for(text, rows=None):
    """提交给模型的整段：先前的对话 ＋ 这一次提交的创意 ＋ 一句要求。"""
    parts = []
    history = history_text(rows)
    if history:
        parts.append('（先前对话）\n' + history)
    parts.append('（本次提交的创意）\n' + str(text or '').strip())
    parts.append('请据此把这份创意写成能直接开拍的漫剧纲要，并指出还缺什么。')
    return '\n\n'.join(parts)


def reply_text(result):
    """从一次调用的返回里取出模型写的字（chat 与 responses 两种回法都认）。"""
    visible_text = str((result or {}).get('text') or '').strip()
    if visible_text:
        return visible_text
    data = (result or {}).get('data')
    if isinstance(data, dict) and isinstance(data.get('content'), (list, tuple)):
        # Messages 的 thinking／signature 从不属于聊天正文。
        from token_saver import anthropic_text
        return anthropic_text(data)
    value = ''
    try:
        from pet_agent import extract_content
        value = extract_content(data)
    except Exception:
        value = ''
    if not value and isinstance(data, dict):
        choices = data.get('choices')
        if isinstance(choices, list) and choices:
            first = choices[0] if isinstance(choices[0], dict) else {}
            message = first.get('message') if isinstance(first.get('message'), dict) else {}
            value = message.get('content') or first.get('text') or ''
        value = value or data.get('output_text') or ''
    return str(value or '').strip()
