# -*- coding: utf-8 -*-
"""剧本准备输入简报契约（自 script_contract 拆出，L0）。

简报是「剧本准备」阶段的输入形状：创意接收层（idea_chat）从用户原话提取字段并落盘，
本模块统一命名「哪些字段必须有」与「如何收敛成一份可确认的简报」，避免在调用方复制判断。

- 字段分级：BRIEF_REQUIRED_FIELDS（必填阻断）／BRIEF_RECOMMENDED_FIELDS（建议提示）／
  BRIEF_OPTIONAL_FIELDS（可选盘点）；BRIEF_REQUIREMENT_LEVELS 是分级汇总。
- normalize_brief 把任意 dict 收敛到唯一简报形状；missing_brief_fields 报缺项；
  brief_document 建立可确认简报，必填未齐时拒绝伪造完成态。
- workflow 投影（WORKFLOW_PROJECTION_KEY／WORKFLOW_LOCK_SCHEMA）只定义 skill_config.json
  顶层 workflow 键的 L0 数据形状，不参与本轮工作流运行。
- 节奏约束 RHYTHM_TEMPLATE_FIELD／RHYTHM_TEMPLATE_PATH 是 SKILL 输入模板引用，不是本阶段
  新增产物；编排器只通过字段引用模板，不复制路径字符串。
"""

# 剧本准备的节奏约束是 SKILL 输入模板，不是本阶段新增产物；因此不加入
# STAGE_OUTPUTS，避免被完整性检查误判成必须生成的 manifest。后续编排器只通过这个字段
# 引用模板，不复制路径字符串。
RHYTHM_TEMPLATE_FIELD = 'rhythm_template'
RHYTHM_TEMPLATE_PATH = 'skills/templates/rhythm_template.yaml'

# 剧本准备的输入简报同样由本契约统一命名；创意接收层只负责从用户原话提取并落盘，
# 不在 idea_chat.py 再复制一套“哪些字段必须有”的判断。
BRIEF_REQUIRED_FIELDS = ('story_summary', 'main_characters', 'genre', 'length')
BRIEF_RECOMMENDED_FIELDS = ('physical_features',)
BRIEF_PRODUCTION_LOCKS_FIELD = 'production_locks'
BRIEF_OPTIONAL_FIELDS = ('special_requirements',)
BRIEF_REQUIREMENT_LEVELS = {
    'required': BRIEF_REQUIRED_FIELDS,
    'recommended': BRIEF_RECOMMENDED_FIELDS + (BRIEF_PRODUCTION_LOCKS_FIELD,),
    'optional': BRIEF_OPTIONAL_FIELDS,
}
BRIEF_FIELDS = BRIEF_REQUIRED_FIELDS + BRIEF_RECOMMENDED_FIELDS + BRIEF_OPTIONAL_FIELDS
BRIEF_LABELS = {
    'story_summary': '故事梗概',
    'main_characters': '主要角色',
    'physical_features': '角色物理特征',
    'genre': '题材类型',
    'length': '篇幅',
    'special_requirements': '特殊要求',
    BRIEF_PRODUCTION_LOCKS_FIELD: '制作锁',
}

# 此投影只定义 skill_config.json 的 L0 数据形状，不参与本轮的工作流运行。
# lock 的第一层按统筹 SKILL 名称命名空间保存；第二层键和值由统筹定义，本契约不列举。
WORKFLOW_PROJECTION_KEY = 'workflow'
WORKFLOW_LOCK_SCHEMA = {
    WORKFLOW_PROJECTION_KEY: {
        'name': '<统筹名称>',
        'skill_ref': '<统筹 SKILL 注册引用>',
        'lock': {'<统筹名称>': {'<键>': '<值>'}},
    },
}


def normalize_brief(values=None):
    """将创意接收层的字段收敛到唯一的剧本准备输入简报形状。"""
    source = values if isinstance(values, dict) else {}
    brief = {field: str(source.get(field) or '').strip() for field in BRIEF_FIELDS}
    locks = source.get(BRIEF_PRODUCTION_LOCKS_FIELD)
    brief[BRIEF_PRODUCTION_LOCKS_FIELD] = dict(locks) if isinstance(locks, dict) else {}
    return brief


def missing_brief_fields(values, include_recommended=False, include_optional=False):
    """返回缺少项；必填阻断，建议只提示，可选仅按需盘点。"""
    brief = normalize_brief(values)
    fields = BRIEF_REQUIRED_FIELDS
    if include_recommended:
        fields += BRIEF_REQUIREMENT_LEVELS['recommended']
    if include_optional:
        fields += BRIEF_REQUIREMENT_LEVELS['optional']
    return tuple(field for field in fields if not brief.get(field))


def normalize_workflow_projection(values=None):
    """规范化顶层 workflow 投影，保留各统筹的锁命名空间。"""
    source = values if isinstance(values, dict) else {}
    workflow = source.get(WORKFLOW_PROJECTION_KEY, source)
    workflow = workflow if isinstance(workflow, dict) else {}
    name = str(workflow.get('name') or '').strip()
    skill_ref = str(workflow.get('skill_ref') or '').strip()
    raw_locks = workflow.get('lock')
    lock = {
        str(namespace): dict(lock_values)
        for namespace, lock_values in raw_locks.items()
        if isinstance(lock_values, dict)
    } if isinstance(raw_locks, dict) else {}
    if name:
        lock.setdefault(name, {})
    return {WORKFLOW_PROJECTION_KEY: {'name': name, 'skill_ref': skill_ref, 'lock': lock}}


def brief_document(values):
    """建立可供剧本准备读取的已确认简报，必填项未齐时拒绝伪造完成态。"""
    brief = normalize_brief(values)
    missing = missing_brief_fields(brief)
    if missing:
        raise ValueError('简报缺少：' + '、'.join(BRIEF_LABELS[field] for field in missing))
    return {
        'contract': 'script_brief',
        'version': 1,
        'brief': brief,
        'recommended_missing': list(missing_brief_fields(brief, include_recommended=True)),
        RHYTHM_TEMPLATE_FIELD: RHYTHM_TEMPLATE_PATH,
    }
