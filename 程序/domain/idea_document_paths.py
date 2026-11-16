# -*- coding: utf-8 -*-
"""创意文档路径与命名策略：把模型身份映射为存储目录，并计算剧本准备阶段用户可见文件路径。

从 L2 ``idea_chat`` 拆出（R1313 结构治理轮）：``storage_identity``、``reply_path_parts``、
``reply_document_path``、``project_script_filename``、``project_document_directory``、
``PROJECT_DOCUMENT_DIRS`` 及其私有命名辅助。只做纯路径计算与命名，不读写、不发布项目数据；
发布仍由 L3 注入。``_context`` 沿用本项目各 L2 模块各自持有 ProjectContext 校验的惯例。
"""
from datetime import datetime
from pathlib import Path
import re

from contract.project_context import ProjectContext


def _context(value):
    if not isinstance(value, ProjectContext):
        raise TypeError('创意聊天项目路径需要由 L3 注入 ProjectContext。')
    return value


class ChatModel(str):
    """显示名携带稳定 ID；请求捕获后不再反查可能变化的模型池。"""
    def __new__(cls, label, model_id='', provider=''):
        value = super().__new__(cls, label)
        value.model_id, value.provider = model_id, provider
        return value


def _storage_name(value, fallback):
    """Provider／模型名转为安全且仍可辨认的 Windows 目录名。"""
    name = re.sub(r'[<>:"/\\\\|?*\x00-\x1f]+', '_', str(value or '').strip())
    name = re.sub(r'\s+', ' ', name).strip(' ._')
    return name[:80] or fallback


def storage_identity(model_label):
    """模型显示名对应的 Provider 与模型目录名；未知模型也不会混入根目录。"""
    if isinstance(model_label, ChatModel) and model_label.model_id:
        return _storage_name(model_label.provider, '未知Provider'), _storage_name(model_label, '未知模型')
    from legacy_compat import optional_model_identity
    provider, label = optional_model_identity(model_label, Path(__file__).resolve().parents[1])
    return _storage_name(provider, '未知Provider'), _storage_name(label, '未知模型')


def _file_day(at=None):
    """用户可见文件名只保留日期；会话记录仍保留精确时间供排序与显示。"""
    moment = datetime.fromtimestamp(at) if at is not None else datetime.now()
    return moment.strftime('%Y%m%d')


def _file_part(value, fallback):
    """把项目标题／集号收成一个可在 Windows 落盘的文件名片段。"""
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', str(value or '').strip())
    text = re.sub(r'\s+', ' ', text).strip(' ._')
    return text[:80] or fallback


def project_script_filename(context, at=None, file_type='自然剧本', content='模型输出'):
    """用户可见创作文件名：``项目名_文件类型_文件内容_年月日.md``。"""
    from contract.script_contract import stage_file_name
    return stage_file_name(_context(context).root, _file_part(file_type, '自然剧本'),
                           _file_part(content, '模型输出'), at=at)


PROJECT_DOCUMENT_DIRS = {
    '项目设定': '项目设定',
    '项目大纲': '项目大纲',
    '角色卡': '角色卡',
    '自然剧本': '项目剧本',
}


def project_document_directory(file_type):
    """返回剧本准备页用户可见文件的唯一分类目录。"""
    return PROJECT_DOCUMENT_DIRS.get(str(file_type), '项目剧本')


def reply_path_parts(root, at=None, provider='', model='', file_type='自然剧本'):
    """纯计算下载正式稿在剧本准备阶段内的逐段路径，不创建或发布文件。"""
    return (_storage_name(provider, '未知Provider'), _storage_name(model, '未知模型'),
            '创意_' + _file_day(at), project_document_directory(file_type),
            project_script_filename(_context(root), at=at, file_type=file_type, content=provider or (storage_identity(model)[0] if model else '模型输出')))


# 前三项（设定／大纲／角色卡）是审阅参考，不保留历史版本：同一阶段目录内始终
# 覆盖最新一份，不再按正文差异追加 (N) 序号副本。自然剧本是唯一正式交付，
# 仍保留版本，不在本集合内。
_OVERWRITE_FILE_TYPES = frozenset(('项目设定', '项目大纲', '角色卡'))


def reply_document_path(context, text, at=None, provider='', model='', file_type=None, *, reuse_latest=True):
    """自动保存与下载共用：相同正文复用；审阅参考覆盖，正式剧本异稿递增编号。

    ``reuse_latest=False`` 时审阅参考稿不回到跨批次的最新一份，按 ``at`` 的日期另存。"""
    from contract.stage_path_service import write_dir
    context = _context(context)
    file_type = file_type or _project_file_type(text)
    parts = reply_path_parts(context, at=at, provider=provider, model=model, file_type=file_type)
    target = write_dir(context.root, 'script').joinpath(*parts)
    value = str(text).replace('\r\n', '\n').strip()
    # 同目录的历史命名也可复用，避免旧自动保存稿再次下载产生副本。
    if target.parent.is_dir():
        for existing in sorted(target.parent.glob('*.md')):
            if existing.is_file() and existing.read_text(encoding='utf-8').strip() == value:
                return existing
    if file_type in _OVERWRITE_FILE_TYPES and reuse_latest:
        # 审阅参考稿放弃历史版本：始终覆盖该阶段最新一份，保持「一份＝最新」。
        # 跨 创意_日期 批次也回到同一份，不因跨天续改落到新批次产生副本。
        candidates = []
        model_dir = target.parents[2]
        try:
            batches = tuple(model_dir.iterdir()) if model_dir.is_dir() else ()
        except OSError:
            batches = ()
        for batch in batches:
            folder = batch / target.parent.name
            if not folder.is_dir():
                continue
            candidates.extend(path for path in folder.glob('*.md') if path.is_file())
        if candidates:
            return max(candidates, key=lambda path: path.stat().st_mtime)
        return target
    number = 0
    while target.exists():
        number += 1
        suffix = '(' + str(number) + ')'
        content = _file_part(provider or (storage_identity(model)[0] if model else ''), '模型输出')[:80 - len(suffix)] + suffix
        target = target.with_name(project_script_filename(
            context, at=at, file_type=file_type, content=content))
    return target


def delivery_document_path(context, file_type, at=None, provider='', model=''):
    """桌面 Agent 交付目标：本模型该类已有文件就沿用最新一份，没有才用当日新路径。

    用户手改过的设定／大纲／角色卡／剧本就在这份文件里；模型重新生成时读它、覆盖它，
    不因跨天或重试落到新的 创意_日期 批次。纯路径计算，不读写正文。
    """
    from contract.stage_path_service import write_dir
    context = _context(context)
    parts = reply_path_parts(context, at=at, provider=provider, model=model, file_type=file_type)
    target = write_dir(context.root, 'script').joinpath(*parts)
    model_dir = target.parents[2]
    candidates = []
    try:
        batches = tuple(model_dir.iterdir()) if model_dir.is_dir() else ()
    except OSError:
        batches = ()
    for batch in batches:
        folder = batch / target.parent.name
        try:
            if batch.name.startswith('创意_') and folder.is_dir():
                candidates.extend(path for path in folder.glob('*.md') if path.is_file())
        except OSError:
            continue
    if not candidates:
        return target
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _project_file_type(text):
    """按正文归类保存类型；未明确归类的模型正文仍按自然剧本保存。

    标题行（行首即类型标签，可带 ``#`` 等标记）优先；大纲另加正文兜底——
    模型回复常在正文直接写「纲要」「故事大纲」等（如「模型写的纲要：…」），
    不要求标题行。角色卡／项目设定仍只按标题行归类：回退确认等控制提示常
    顺带提到「角色卡」「项目设定」，放宽正文匹配会把它们误判成文档（REQ-S01-76）。
    """
    value = str(text or '')
    headings = [line.lstrip('# \t').strip() for line in value.split('\n') if line.strip()]
    for file_type, titles in (
            ('角色卡', ('人物设定', '角色卡')),
            ('项目设定', ('项目设定', '世界观', '需求梳理')),
            ('项目大纲', ('项目大纲', '剧本大纲', '故事大纲', '分集大纲', '纲要')),
            ('自然剧本', ('自然剧本', '项目剧本'))):
        if any(heading.startswith(title) for heading in headings for title in titles):
            return file_type
    if any(mark in value for mark in ('项目大纲', '故事大纲', '分集大纲', '纲要')):
        return '项目大纲'
    return '自然剧本'


# 简报文件的唯一命名：``brief_creation.md`` 是用户可见的唯一简报源，
# ``brief_raw.md`` 仅作旧项目只读兼容输入。
BRIEF_CREATION_NAME = 'brief_creation.md'
LEGACY_BRIEF_RAW_NAME = 'brief_raw.md'
BRIEF_RAW_NAME = BRIEF_CREATION_NAME
BRIEF_COMPLETE_NAME = 'brief_complete.json'


def brief_raw_path(context):
    """剧本准备的原始用户简报（唯一文件：brief_creation.md）。"""
    from contract.project_stages import writing
    return writing(_context(context).root) / BRIEF_RAW_NAME


def legacy_brief_raw_path(context):
    """旧项目的简报位置；仅在新文件尚未创建时导入读取。"""
    from contract.project_stages import writing
    return writing(_context(context).root) / LEGACY_BRIEF_RAW_NAME


def brief_complete_path(context):
    """经完整性检查后才会出现的剧本准备输入文件。"""
    from contract.project_stages import writing
    return writing(_context(context).root) / BRIEF_COMPLETE_NAME
