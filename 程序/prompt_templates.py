# -*- coding: utf-8 -*-
"""提示词生成规则（第 61 期 v0.8 任务 12）：图片提示词与视频提示词分开，锚点逐字复用。

附件给了四条规矩，这一份把它们做成模板与函数，别的模块只管调用：

1. **图片提示词**＝锚点 ＋ 场景 ＋ 构图：从资产 JSON 读 character_anchor，从场景资产读
   spatial_anchors／lighting_direction，构图用一句固定的话。锚点**逐字复制**，不许 LLM 重写。
2. **视频提示词**只写动作、镜头运动、物理交互——决定「画面怎么动」，不重复长相和服装
   （长相与服装已经在图片提示词里定死了）。
3. **参考图职责显式声明**：每张参考图都要有一句「只负责什么、不继承什么」。
4. **多参考图冲突**在连贯性清单阶段声明优先级（见 continuity_ledger.conflicts／ask），
   不在生成阶段反复试错。

硬约束 5：图片提示词决定「画面是什么」，视频提示词只描述「画面怎么动」。
"""
from asset_contract import DEFAULT_EXCLUDE, DEFAULT_RESPONSIBILITY, merged_anchor

IMAGE_TEMPLATE = '{anchor}；场景：{scene}；构图：{composition}'
VIDEO_TEMPLATE = '{parts}'
ROLE_TEMPLATE = '{label}只负责{responsibility}，不继承其中的{exclude}'
DEFAULT_COMPOSITION = '中景、平视、面部清晰、画面稳定'
DEFAULT_CAMERA = '固定机位，轻微推进'
ANCHOR_TODO = '（锚点未定稿：请先在资产管理里锁定 character_anchor）'
SCENE_TODO = '（场景未登记：请先在资产管理里补 scene_id 与空间锚点）'


def image_template():
    """图片提示词模板：锚点 ＋ 场景 ＋ 构图。"""
    return IMAGE_TEMPLATE


def video_template():
    """视频提示词模板：只写动作、运镜、物理交互。"""
    return '动作：{action}；运镜：{camera}；物理交互：{physics}'


def role_template():
    """参考图职责声明模板（附件原句的样子）。"""
    return ROLE_TEMPLATE


def scene_line(asset):
    """场景资产压成一句：光源、空间锚点、尺度（没有就返回空串）。"""
    data = asset if isinstance(asset, dict) else {}
    parts = []
    name = str(data.get('name') or '').strip()
    if name:
        parts.append(name)
    if str(data.get('lighting_direction') or '').strip():
        parts.append('光源：' + str(data['lighting_direction']).strip())
    for entry in data.get('spatial_anchors') or []:
        if not isinstance(entry, dict):
            continue
        what = str(entry.get('object') or '').strip()
        if not what:
            continue
        where = str(entry.get('position') or '').strip()
        parts.append('%s@%s' % (what, where) if where else what)
    if str(data.get('scale_reference') or '').strip():
        parts.append('尺度：' + str(data['scale_reference']).strip())
    return '；'.join(parts)


def image_prompt(asset, scene=None, composition='', costume_id=''):
    """图片提示词：锚点（逐字复用）＋ 场景 ＋ 构图。缺哪一项就留一句待办，不编内容。"""
    anchor = merged_anchor(asset, costume_id) or ANCHOR_TODO
    text = scene_line(scene) or SCENE_TODO
    return IMAGE_TEMPLATE.format(anchor=anchor, scene=text,
                                 composition=composition or DEFAULT_COMPOSITION)


def video_prompt(action='', camera='', physics=''):
    """视频提示词：只写动作、运镜、物理交互（空的那一段直接不出现）。"""
    parts = []
    for label, text in (('动作', action), ('运镜', camera), ('物理交互', physics)):
        value = str(text or '').strip()
        if value:
            parts.append('%s：%s' % (label, value))
    return '；'.join(parts)


def strip_appearance(text, asset, costume_id=''):
    """把视频提示词里复述的长相／服装去掉（锚点整句出现就直接删）。

    视频提示词不该再说一遍锚点；这里只是兜底，正常情况由 Agent 按 video_prompt() 生成。
    """
    body = str(text or '')
    anchor = merged_anchor(asset, costume_id)
    if anchor and anchor in body:
        body = body.replace(anchor, '').strip('；; ')
    return body


def role_line(label, responsibility='', exclude=''):
    """一句参考图职责声明：@图片1只负责…，不继承其中的…。"""
    return ROLE_TEMPLATE.format(label=str(label or '').strip(),
                                responsibility=str(responsibility or '').strip()
                                or DEFAULT_RESPONSIBILITY,
                                exclude=str(exclude or '').strip() or DEFAULT_EXCLUDE)


def role_lines(shot, assets=None):
    """一镜里每张参考图的职责声明：按 character_refs 顺序输出（label, 那一句）。"""
    item = shot if isinstance(shot, dict) else {}
    known = assets if isinstance(assets, dict) else {}
    roles = item.get('reference_roles') if isinstance(item.get('reference_roles'), dict) else {}
    out = []
    for ref in item.get('character_refs') or []:
        role = roles.get(ref) or {}
        out.append((str(ref), role_line(ref, role.get('responsibility'), role.get('exclude'))))
    return tuple(out)


def common_lines():
    """要插进 asset_prompt_rules.COMMON 的约束句（图片提示词这一侧）。"""
    return ('图片提示词＝锚点＋场景＋构图：锚点从资产 JSON 的 character_anchor 逐字复制，不许重新描述。',
            '参考图职责要显式声明：%s。' % role_line('@图片1'),
            '多参考图抢同一件事时，先在连贯性清单里声明优先级，别在生成阶段反复试错。')


def contract_lines():
    """要插进分镜契约（storyboard_contract.rules）的约束句（视频提示词这一侧）。"""
    return ('视频提示词只写动作、镜头运动与物理交互，不重复长相和服装。',
            '图片提示词与视频提示词分开生成：图片决定「画面是什么」，视频只描述「画面怎么动」。')


def rows():
    """图片／视频／职责三份模板（交付物 12）。"""
    return (('图片提示词', image_template(), '锚点（逐字复用）＋场景＋构图'),
            ('视频提示词', video_template(), '只写动作、运镜、物理交互'),
            ('参考图职责声明', role_template(), '每张参考图一句「只负责什么、不继承什么」'))