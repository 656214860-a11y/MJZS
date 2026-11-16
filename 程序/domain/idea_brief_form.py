# -*- coding: utf-8 -*-
"""简报表单解析与校验：把用户填写的创作简报文本解析为契约字段，并做必填门禁。

从 L2 ``idea_chat`` 拆出（R1315 结构治理轮）：``extract_brief_creation``、
``merge_brief_creation``、``inline_required_missing``、``brief_creation_values``、
``format_brief_creation`` 及其解析辅助 ``_brief_plain_text``／``strip_inline_required_markers``／
``inline_template_labels``、字段契约 ``BRIEF_CREATION_FIELDS``。只做纯文本解析与字段校验：
不读 Tk、不发网络；简报文件路径沿用 L2 ``idea_document_paths`` 的既有权威，不重复实现命名。
"""
import re

from contract.script_contract import (
    INLINE_REQUIRED_LABELS, PRODUCTION_LOCK_DEFINITIONS, stage_lock_definitions, stage_lock_requirements)
from domain.idea_document_paths import brief_raw_path, legacy_brief_raw_path


def _brief_plain_text(text, labels):
    """把明确的 Markdown 字段表/标题转成标签行，不推测正文含义。"""
    names = '|'.join(re.escape(label) for label in labels)
    lines, pending = [], ''
    for line in str(text or '').replace('\r\r\n', '\n').splitlines():
        cells = [cell.strip().strip('*').strip() for cell in line.strip().strip('|').split('|')]
        if len(cells) == 2 and (cells[0] in labels or cells[0] == '设定'):
            line = cells[0] + '：' + cells[1]
        heading = re.fullmatch(r'\s*#{1,6}\s+(' + names + r')\s*[：:]?\s*', line)
        if pending:
            if not line.strip():
                continue
            if heading or re.match(r'\s*(?:[-*#]+\s*)?(?:' + names + r')[ *]*[：:\t]', line):
                lines.append(pending + '：')
            else:
                line = pending + '：' + line.strip()
            pending = ''
        if heading:
            pending = heading.group(1)
        else:
            lines.append(line)
    if pending:
        lines.append(pending + '：')
    value = '\n'.join(lines)
    # 只在已知字段之前还原单元格换行，不把任意正文当字段。
    value = re.sub(r'(?:\\n|<br\s*/?>|[；;\t])\s*(?=(?:' + names + r')[ *]*[：:])', '\n', value, flags=re.I)
    value = re.sub(r'(?m)^[ \t]*(?:设定|备注)[：:][ \t]*(?=(?:' + names + r')[ *]*[：:])', '', value)
    return value


# 表单字段写在这里而不是桌面层：直接输入、表格填写、后续剧本契约
# 都经由同一份 brief_creation.md，不会出现两套记忆或两份“原始简报”。
BRIEF_CREATION_FIELDS = (
    '故事集数', '单集时间', '故事画风', '故事梗概', '故事题材',
    '故事角色', '物理特征', '故事分集', '特殊要求', '内容补充',
)


def format_brief_creation(values):
    """将填写表格稳定地保存为人可读的简报文本。"""
    source = values if isinstance(values, dict) else {}
    labels = list(BRIEF_CREATION_FIELDS)
    labels.extend(label for label in source if label not in labels)
    return '\n'.join(label + '：' + str(source.get(label) or '').strip()
                     for label in labels).rstrip() + '\n'


def strip_inline_required_markers(text):
    """行尾必填提示只用于显示，不进入提取、模型输入或项目文件。"""
    return re.sub(r'[ \t]*（必填）[ \t]*(?=\r?$)', '', str(text or ''), flags=re.MULTILINE)


def inline_template_labels(text):
    """从示例的顶层行取得字段边界，缩进角色描述不另起字段。"""
    return tuple(dict.fromkeys(re.findall(r'^([^\s：:][^：:\n]{0,29})[：:]',
                                         str(text or ''), re.MULTILINE)))


def unlabeled_story_summary(text):
    """无标签的整段非空正文回退为故事梗概；有显式「故事梗概」标签（含别名）则只认标签值。"""
    value = str(text or '').strip()
    if not value:
        return ''
    fields = extract_brief_creation(value)
    if str(fields.get('故事梗概') or '').strip():
        return fields['故事梗概']
    if re.search(r'(?m)^[ \t]*(?:[-*#]+[ \t]*)?(?:故事梗概|故事主体|故事主线|故事概述|剧情)[ \t]*[：:\t]', value):
        return ''
    return value


def inline_required_missing(template_text, draft_text, required_labels=INLINE_REQUIRED_LABELS,
                            attachment_fields=None, *, stage='script',
                            lock_definitions=PRODUCTION_LOCK_DEFINITIONS, created_at=None):
    """故事字段与本阶段制作锁共用门禁；其他锁只保留为建议值。"""
    lock_definitions = stage_lock_definitions(stage, lock_definitions)
    lock_aliases = {item['label']: (item['label'], *item.get('aliases', ()), item['key'])
                    for item in lock_definitions}
    required_keys = stage_lock_requirements(stage, created_at)
    required_labels = tuple(dict.fromkeys((*required_labels,
        *(item['label'] for item in lock_definitions if item['key'] in required_keys))))
    labels = tuple(dict.fromkeys((*inline_template_labels(template_text), *required_labels,
                                 *(label for aliases in lock_aliases.values() for label in aliases))))
    template = extract_brief_creation(strip_inline_required_markers(template_text),
                                      extra_labels=labels, include_extra=True)
    draft = extract_brief_creation(strip_inline_required_markers(draft_text),
                                   extra_labels=labels, include_extra=True)
    if not str(draft.get('故事梗概') or '').strip():
        summary = unlabeled_story_summary(strip_inline_required_markers(draft_text))
        if summary:
            draft['故事梗概'] = summary
    def normalized(fields, label):
        return next((''.join(str(fields.get(alias) or '').split())
                     for alias in lock_aliases.get(label, (label,))
                     if str(fields.get(alias) or '').strip()), '')
    return tuple(label for label in required_labels
                 if not normalized(attachment_fields or {}, label)
                 and (not normalized(draft, label)
                      or normalized(draft, label) == normalized(template, label)))


def extract_brief_creation(text, *, extra_labels=(), include_extra=False):
    """只提取明确标注的字段，保留空值和多行；附件不会被当成指令执行。"""
    aliases = {'集数': '故事集数', '单集时长': '单集时间', '时长': '单集时间',
               '主要角色': '故事角色', '角色': '故事角色', '人物设定': '故事角色',
               '题材类型': '故事题材', '题材': '故事题材', '画风': '故事画风',
               '外貌特征': '物理特征', '故事概述': '故事梗概',
               '故事主线': '故事梗概', '故事主体': '故事梗概', '剧情': '故事梗概',
               '故事主题': '故事题材', '类型': '故事题材', '风格': '故事题材',
               '故事人物': '故事角色', '角色物理特征': '物理特征',
               '外貌': '物理特征', '形象': '物理特征', '额外要求': '特殊要求', '要求': '特殊要求'}
    # XLSX 转换稿保留列间制表符；字段可能在“设定”等说明列之后。
    lock_labels = tuple(label for item in PRODUCTION_LOCK_DEFINITIONS
                        for label in (item['label'], *item.get('aliases', ()), item['key']))
    labels = tuple(dict.fromkeys((*BRIEF_CREATION_FIELDS, '篇幅', *aliases, *extra_labels, *lock_labels)))
    label_pattern = '|'.join(re.escape(label) for label in labels)
    fields, active = {}, None
    for line in _brief_plain_text(text, labels).splitlines():
        match = re.search(r'(?:^|\t)[ ]*(?:[-*#]+[ \t]*)?(' + label_pattern
                          + r')[ *]*[：:\t][ \t]*(.*)$', line)
        if match:
            label = match.group(1).strip().strip('*').strip()
            canonical = aliases.get(label, label)
            if canonical in (*BRIEF_CREATION_FIELDS, '篇幅') or (include_extra and label in (*extra_labels, *lock_labels)):
                active = canonical
                fields[active] = match.group(2)
                nested = re.match(r'[ *]*(?:' + label_pattern + r')[ *]*[：:]', match.group(2))
                if nested:
                    fields.update(extract_brief_creation(match.group(2), extra_labels=extra_labels, include_extra=include_extra))
                    active = None
                continue
            if label in labels:
                active = None
                continue
        if active:
            fields[active] += '\n' + line
    length = fields.pop('篇幅', '')
    # 旧简报的篇幅可同时声明集数和单集时长；没有明确时长时不猜默认值。
    for label, pattern in (('故事集数', r'\d+\s*集'),
                           ('单集时间', r'(?:每集|单集)[：:\s]*(\d+(?:\.\d+)?\s*(?:分钟|秒|minutes?|min|s))')):
        match = re.search(pattern, length, re.I)
        if match:
            fields.setdefault(label, match.group(match.lastindex or 0))
    return {label: value.strip() for label, value in fields.items()}


def merge_brief_creation(text, values):
    """只补空字段，保留手填正文、别名、未知字段和原有布局。"""
    source = str(text or '')
    current = extract_brief_creation(source, extra_labels=tuple(values), include_extra=True)
    for label, raw in values.items():
        value = str(raw or '').strip()
        if not value or current.get(label):continue
        replaced = False
        for match in re.finditer(r'(?m)^([^\r\n：:]+)[：:][ \t]*(?=\r?$)', source):
            field = extract_brief_creation(match.group(1) + '：value', extra_labels=tuple(values), include_extra=True)
            if label in field:
                source = source[:match.end()] + value + source[match.end():]
                replaced = True
                break
        if not replaced:
            source += ('\n' if source and not source.endswith('\n') else '') + label + '：' + value
        current[label] = value
    return source


def brief_creation_values(root, extra_text='', *, attachment_values=None, extra_labels=(), attachment_reference=None):
    """读取上次填写内容；当前未发送文本可覆盖同名字段。"""
    path = brief_raw_path(root)
    if path.is_file():
        source = path.read_text(encoding='utf-8')
    else:
        legacy = legacy_brief_raw_path(root)
        source = legacy.read_text(encoding='utf-8') if legacy.is_file() else ''
    current = str(extra_text or '').strip()
    extracted = dict(attachment_values or {})
    for text in (attachment_reference or {}).get('brief_texts', ()):
        for label, value in extract_brief_creation(text, extra_labels=extra_labels).items():
            extracted.setdefault(label, value)
    values = {label: str(extracted.get(label, '')) for label in BRIEF_CREATION_FIELDS}
    values.update(extract_brief_creation(source, extra_labels=extra_labels))
    current_fields = extract_brief_creation(current, extra_labels=extra_labels)
    values.update(current_fields)
    if current and not current_fields and not any(values.values()):
        values['故事梗概'] = current
    return values
