# -*- coding: utf-8 -*-
"""外部 SKILL 包受控元数据（R3097／生命周期任务书 T9）。

从 ``skill_registry`` 拆出（模块行数棘轮）：``imported_package_meta`` 及其依赖的
``markdown_heading``／``markdown_summary``／``IMPORTED_PACKAGE_FLAG`` 本属注册表，
现集中在本模块；``skill_registry`` 原样 re-export，调用方路径不变。
阶段判定 ``stage_from_path`` 的唯一权威在 ``skill_project_layer``（L3 同层引用，
无循环）。
"""
import re

from skill_project_layer import stage_from_path

IMPORTED_PACKAGE_FLAG = '_imported_package'


def markdown_heading(body):
    """取 Markdown 首个一级标题，供无 frontmatter 的外部包显示。"""
    match = re.search(r'^\s*#\s+(.+?)\s*$', str(body or ''), flags=re.MULTILINE)
    return match.group(1).strip() if match else ''


def markdown_summary(body):
    """取 Markdown 的首句说明；外部资料没有简介时也能在面板里说明来源。"""
    for line in str(body or '').splitlines():
        text = line.strip()
        if text and not text.startswith(('#', '---', '```', '-', '*')):
            return text[:160]
    return ''


def _external_list(meta, *keys):
    """frontmatter 可选字段 → 扁平字符串列表：内联表、块列表与单值都认。"""
    for key in keys:
        value = (meta or {}).get(key)
        if value in (None, ''):
            continue
        if isinstance(value, (list, tuple)):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(value).strip()]
    return []


def imported_package_meta(source_meta, body, package, source, known_tools=()):
    """为阶段目录下的外部 SKILL 包建立一个受控总入口元数据。

    外部 ``SKILL.md`` 多为 Codex/Claude 的轻量格式，不满足本程序的完整 frontmatter
    契约；这里不信任其执行字段，仅复用可读名称/简介和正文，其余字段采用稳定默认值。
    T9：``license``／``compatibility`` 原样保留进 meta 供说明区展示；``allowed-tools``
    只把 ``known_tools``（内置层声明的工具名集）里的名字映射进 ``tools``，其余进
    ``constraints`` 提示——不硬猜、不放宽 17 字段契约。
    """
    source_meta = source_meta or {}
    title = (str(source_meta.get('displayName', '') or '').strip() or
             markdown_heading(body) or package.name)
    description = (str(source_meta.get('description', '') or '').strip() or
                   markdown_summary(body) or
                   '外部 SKILL 包总入口：%s' % title)
    constraints = ['这是外部 SKILL 包的总入口，不自动展开其内部子 SKILL。']
    allowed = _external_list(source_meta, 'allowed-tools', 'allowed_tools')
    known = {str(tool) for tool in known_tools or ()}
    mapped = [tool for tool in allowed if tool in known]
    unmapped = [tool for tool in allowed if tool not in known]
    if unmapped:
        constraints.append('外部包声明 allowed-tools：%s；本应用无对应工具，仅作提示不映射。'
                           % '、'.join(unmapped))
    meta = {
        'name': str(source_meta.get('name', '') or '').strip() or package.name,
        'displayName': title,
        'description': description,
        'stage': stage_from_path(source),
        'capabilities': ['creative-writing'],
        'preferredModels': [],
        'fallbackModels': [],
        'tools': mapped,
        'dependsOn': [],
        'conflictsWith': [],
        'parallelizable': False,
        'paid': False,
        'input': [],
        'output': [],
        'constraints': constraints,
        'feedback': [],
        'examples': [],
        IMPORTED_PACKAGE_FLAG: True,
    }
    for key in ('license', 'compatibility'):
        value = source_meta.get(key)
        if value not in (None, ''):
            meta[key] = value if isinstance(value, (list, tuple)) else str(value)
    return meta
