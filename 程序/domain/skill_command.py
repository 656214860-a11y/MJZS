"""共享输入框的 ``/`` 命令解析（R2893，任务书轮 3）：纯标准库、无 Tk，可独立单测。

命令形态三者都支持（任务书 §4）：``/skill名``、``/阶段别名``、``/子引擎``。
输入不以 ``/`` 开头＝自由聊天，返回 ``None``。阶段别名来自
``contract.pet_bus.STAGES``／``STAGE_NAMES`` 的反向映射；引擎候选由调用方注入
统一注册器已发现的用户／项目 SKILL 包，不自行扫描目录或加载脚本。
"""
from __future__ import annotations

import os
from pathlib import Path

from contract import pet_bus

KINDS = ('skill', 'stage', 'engine')
_ENGINE_MARKERS = ('SKILL.md', 'README.md', 'readme.md')
# token 右界：空白之外的中英文句读也截断，避免光标在 ``/name，后文`` 中间时
# 选中候选把标点和后文一起吃掉（R2980）。
_TOKEN_END_BREAKS = frozenset('，。、；：？！…—·,.;:!?()[]{}"\'“”‘’《》')


def _norm(text):
    return str(text or '').strip().lstrip('/').strip()


def stage_aliases():
    """阶段别名 → 阶段 id：id、中文名、``NN``、``NN 名称`` 都认，先注册先匹配。"""
    out = {}
    for index, stage in enumerate(pet_bus.STAGES):
        name = pet_bus.STAGE_NAMES[stage]
        for alias in (stage, name, '%02d' % (index + 1), '%02d %s' % (index + 1, name)):
            out.setdefault(alias, stage)
    return out


def stage_alias_for(token):
    """单个 token → 阶段 id：先精确别名，再按阶段顺序取名字包含该 token 的第一步。"""
    text = _norm(token)
    if not text:
        return ''
    exact = stage_aliases().get(text)
    if exact:
        return exact
    folded = text.lower()
    for stage in pet_bus.STAGES:
        name = pet_bus.STAGE_NAMES[stage]
        if folded in (stage.lower(), name.lower()) or folded in name:
            return stage
    return ''


def sub_engine_names(skills=()):
    """从注册器快照投影用户／项目包；不做文件 I/O，扁平 SKILL 沿用 skill 类别。"""
    names = set()
    for item in skills or ():
        field = item.get if isinstance(item, dict) else lambda key, default=None: getattr(item, key, default)
        name = _skill_name(item)
        path = field('path')
        if (field('layer') not in ('user', 'project') or not path
                or Path(path).name not in _ENGINE_MARKERS
                or not name or name.startswith('.')
                or any(char.isspace() or char in '/\\\\' for char in name)):
            continue
        names.add(name)
    return tuple(sorted(names))


def _skill_name(item):
    if isinstance(item, dict):
        return str(item.get('name') or '').strip()
    return str(getattr(item, 'name', item) or '').strip()


def _match_skill(token, skills):
    """skill 名精确匹配（ASCII 名忽略大小写）；返回规范名，未命中返回空串。"""
    text = _norm(token)
    if not text:
        return ''
    names = [_skill_name(item) for item in skills or ()]
    for name in names:
        if name == text:
            return name
    folded = text.lower()
    for name in names:
        if name.lower() == folded:
            return name
    return ''


def parse_command(text, *, stage=None, skills=(), engines=None):
    """``/`` 开头文本 → ``{'kind', 'name', 'stage', 'rest'}``；自由聊天返回 ``None``。

    ``skills`` 可为名字字符串或带 ``.name`` 的注册项；``engines`` 缺省时从注册项投影。
    ``rest`` 是命令 token 之后的剩余正文（可为空串）。
    """
    raw = str(text or '')
    if not raw.startswith('/'):
        return None
    body = raw[1:].lstrip()
    if not body.strip():
        return None
    token, _, rest = body.partition(' ')
    token = token.strip()
    rest = rest.strip()
    if not token:
        return None
    names = engines if engines is not None else sub_engine_names(skills)
    packages = sub_engine_names(skills)
    package = next((name for name in packages if name.casefold() == token.casefold()), '')
    if package and package in names:
        return {'kind': 'engine', 'name': package, 'stage': stage, 'rest': rest}
    skill = _match_skill(token, skills)
    if skill:
        return {'kind': 'skill', 'name': skill, 'stage': stage, 'rest': rest}
    target = stage_alias_for(token)
    if target:
        return {'kind': 'stage', 'name': target, 'stage': target, 'rest': rest}
    for name in names:
        if str(name) == token or str(name).lower() == token.lower():
            return {'kind': 'engine', 'name': str(name), 'stage': stage, 'rest': rest}
    return None


def _prefix_hit(name, prefix):
    text = _norm(prefix).lower()
    if not text:
        return True
    return text in str(name).lower()


def trigger_token(text, offset):
    """光标处的 ``/``／``@`` 触发 token（R2980）：返回 ``{'kind','query','start','end'}`` 或 ``None``。

    ``offset`` 是 ``text`` 的字符偏移（0 基）。向左扫到行首找最近的 ``/`` 或 ``@``；
    触发符前一个字符必须是行首或空白（``str.isspace()``，含全角空格），因此
    ``a/b``、``https://``、``a@b.com`` 都不触发。``query`` 是触发符到光标之间的
    原文（去前导空白、保留尾部与中间空格——阶段别名 ``03 初步分镜`` 需要）；
    ``end`` 从光标向右扫到下一个空白／换行，光标落在 token 中间也能整体替换。
    同一行上离光标最近的触发符生效（``/a @b`` 解析为 mention）。
    """
    raw = str(text or '')
    try:
        offset = max(0, min(int(offset), len(raw)))
    except (TypeError, ValueError):
        offset = len(raw)
    line_start = raw.rfind('\n', 0, offset) + 1
    trigger = -1
    for i in range(offset - 1, line_start - 1, -1):
        if raw[i] in '/@':
            trigger = i
            break
    if trigger < 0:
        return None
    if trigger > line_start and not raw[trigger - 1].isspace():
        return None
    end = offset
    while end < len(raw) and not raw[end].isspace() and raw[end] not in _TOKEN_END_BREAKS:
        end += 1
    return {'kind': 'command' if raw[trigger] == '/' else 'mention',
            'query': raw[trigger + 1:offset].lstrip(),
            'start': trigger, 'end': end}


def _item_stage(item, default):
    """技能条目的阶段归属：Skill 对象读 ``.stage``、字典读 ``stage`` 键、字符串视为当前阶段。"""
    if isinstance(item, dict):
        return item.get('stage') or default
    return getattr(item, 'stage', None) or default


def _item_description(item):
    """候选用途说明（REQ-S01-106）：对象读 ``.description``、字典读 ``description`` 键，
    字符串条目无描述得空串。只消费已取得的注册对象，不读盘、不推测；去掉首尾空白
    但保留内部换行（多行描述原样进说明卡）。"""
    if isinstance(item, dict):
        desc = item.get('description')
    else:
        desc = getattr(item, 'description', None)
    return str(desc or '').strip()


def completion_entries(query, *, stage=None, skills=(), engines=None):
    """``/`` 候选结构化条目（R2980）：当前阶段 skill → 其余 skill → 阶段别名 → 子引擎，
    子串过滤、去重保序。条目 ``{'kind','name','label','insert','hint'}``；
    ``insert`` 是含触发符与末尾空格的完整替换文本，``hint`` 是用途说明（REQ-S01-106，
    取已取得注册对象／字典 ``description``，engine 按名回查包说明，无描述得空串）。"""
    skills = tuple(skills or ())
    names = engines if engines is not None else sub_engine_names(skills)
    packages = set(sub_engine_names(skills)).intersection(names)
    # engine 只传名字：按名回查同一份注册快照的包说明，重名按快照先后
    # （项目＞用户＞内置）取第一条，精确名优先、忽略大小写兜底。
    desc_exact, desc_fold = {}, {}
    for item in skills:
        name = _skill_name(item)
        if not name:
            continue
        desc = _item_description(item)
        desc_exact.setdefault(name, desc)
        desc_fold.setdefault(name.lower(), desc)
    current, others = [], []
    for item in skills:
        if _skill_name(item) in packages:
            continue
        (current if _item_stage(item, stage) == stage else others).append(item)
    groups = (('skill', current), ('skill', others),
              ('stage', [alias for alias, _target in stage_aliases().items()]),
              ('engine', list(names)))
    seen, out = set(), []
    for kind, group in groups:
        for item in group:
            name = _skill_name(item)
            if not name or name in seen or not _prefix_hit(name, query):
                continue
            seen.add(name)
            if kind == 'skill':
                hint = _item_description(item)
            elif kind == 'engine':
                hint = desc_exact.get(name) or desc_fold.get(name.lower(), '')
            else:
                hint = ''
            out.append({'kind': kind, 'name': name,
                        'label': '/' + name, 'insert': '/' + name + ' ',
                        'hint': hint})
    return tuple(out)
