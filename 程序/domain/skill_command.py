"""共享输入框的 ``/`` 命令解析（R2893，任务书轮 3）：纯标准库、无 Tk，可独立单测。

命令形态三者都支持（任务书 §4）：``/skill名``、``/阶段别名``、``/子引擎``。
输入不以 ``/`` 开头＝自由聊天，返回 ``None``。阶段别名来自
``contract.pet_bus.STAGES``／``STAGE_NAMES`` 的反向映射；子引擎名来自
``skills/00全流程SKILL/AIGC创作全流程/`` 下一层目录（含 SKILL.md 或 README 的包）。
"""
from __future__ import annotations

import os
from pathlib import Path

from contract import pet_bus

KINDS = ('skill', 'stage', 'engine')
_SUB_ENGINE_PARENT = Path('00全流程SKILL') / 'AIGC创作全流程'
_ENGINE_MARKERS = ('SKILL.md', 'README.md', 'readme.md')


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


def sub_engine_names(skills_root=None):
    """``AIGC创作全流程`` 下一层子引擎目录名（有 SKILL.md／README 的目录才算）。"""
    root = Path(skills_root) if skills_root else Path(__file__).resolve().parents[1] / 'skills'
    parent = root / _SUB_ENGINE_PARENT
    if not parent.is_dir():
        return ()
    names = []
    for child in sorted(parent.iterdir()):
        if not child.is_dir() or child.name.startswith('.'):
            continue
        if any((child / marker).is_file() for marker in _ENGINE_MARKERS):
            names.append(child.name)
    return tuple(names)


def _skill_name(item):
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

    ``skills`` 可为名字字符串或带 ``.name`` 的注册项；``engines`` 缺省时扫仓内目录。
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
    names = engines if engines is not None else sub_engine_names()
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


def completions(text, *, stage=None, skills=(), engines=None):
    """``/`` 补全候选：当前阶段已装 skill → 其余 skill → 阶段别名 → 子引擎，去重保序。"""
    raw = str(text or '')
    if not raw.startswith('/'):
        return ()
    prefix = raw[1:].strip()
    current = [item for item in (skills or ()) if getattr(item, 'stage', stage) in (None, stage)]
    others = [item for item in (skills or ()) if item not in current]
    names = engines if engines is not None else sub_engine_names()
    groups = (current, others,
              [alias for alias, target in stage_aliases().items()],
              list(names))
    seen, out = set(), []
    for group in groups:
        for item in group:
            name = _skill_name(item)
            if not name or name in seen or not _prefix_hit(name, prefix):
                continue
            seen.add(name)
            out.append('/' + name)
    return tuple(out)


def command_token(text):
    """输入框当前 ``/`` token（补全用）：非 ``/`` 开头返回空串。"""
    raw = str(text or '')
    if not raw.startswith('/'):
        return ''
    body = raw[1:]
    token = body.split(' ', 1)[0]
    return '/' + token if token else '/'
