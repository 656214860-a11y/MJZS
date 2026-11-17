# -*- coding: utf-8 -*-
"""SKILL 外部包安全提示（R3097／生命周期任务书 T9）：可执行内容扫描与不可信来源文案。

从 ``skill_import_service`` 拆出（模块行数棘轮）。只读扫描、有条目上限；
清单是提示材料——本应用不执行包内任何内容，也不做恶意代码判定。
"""
from pathlib import Path

# 外部 SKILL 会成为发给模型的指令内容（提示注入面）；确认框统一带来源行与
# 注入警示，包内 ``scripts/`` 与可执行扩展名追加警告行。只提示不执行、不扫描内容。
EXECUTABLE_ALERT_SUFFIXES = frozenset({'.exe', '.dll', '.ps1', '.bat'})
ALERT_DIR_NAMES = frozenset({'scripts'})
_ALERT_SCAN_LIMIT = 20000


def package_alerts(root):
    """包根 → 可执行内容清单：``scripts/`` 目录与 ``.exe/.dll/.ps1/.bat`` 文件相对路径。

    只读扫描、有条目上限；清单是单文件不产生警示。大小写不敏感。
    """
    root = Path(root)
    if not root.is_dir():
        return []
    found = []
    for count, path in enumerate(root.rglob('*'), 1):
        if count > _ALERT_SCAN_LIMIT:
            break
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            continue
        if path.is_dir() and path.name.casefold() in ALERT_DIR_NAMES:
            found.append(rel + '/')
        elif path.is_file() and path.suffix.casefold() in EXECUTABLE_ALERT_SUFFIXES:
            found.append(rel)
    return sorted(found)


def import_alerts(plans):
    """计划列表 → ``{计划名: 警示相对路径}``；仅 ``package`` 类计划会产生警示。"""
    alerts = {}
    for plan in plans or ():
        if not isinstance(plan, dict) or plan.get('kind') != 'package':
            continue
        source = plan.get('source')
        if source is None:
            continue
        found = package_alerts(Path(source).parent)
        if found:
            alerts[str(plan.get('name') or Path(source).parent.name)] = found
    return alerts


def untrusted_source_notice(label, plans=None):
    """外部来源确认提示块：来源行＋指令注入警示＋（有警示时）可执行内容警告行。"""
    lines = ['来源：%s' % (label or '—'),
             '外部内容将作为指令注入模型请求，请确认来源可信。']
    alerts = import_alerts(plans) if plans else {}
    if alerts:
        lines.append('包内检测到可执行文件或脚本目录（本应用不会运行，但请知悉）：')
        for name, items in alerts.items():
            shown = '、'.join(items[:5]) + ('…' if len(items) > 5 else '')
            lines.append('· %s：%s' % (name, shown))
    return '\n'.join(lines)
