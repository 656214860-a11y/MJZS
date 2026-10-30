# -*- coding: utf-8 -*-
"""正式 JSON 产物的版本与字段契约：唯一登记、只读校验、显式迁移。

项目里正式产物的版本此前各写各的——有的用 ``version``（队列、连续性台账、
Animatic 清单），多数根本没写，且没有集中登记、必备字段声明与迁移入口。
本模块是"新增写入"的版本权威：新产物写 ``schema_version``；读取侧对缺版本／
旧版本只给出可报告的结论，**绝不自动改写用户数据**。历史产物沿用旧键，
由 ``migrate()`` 显式抬升，只加键、不删数据。
"""
from __future__ import annotations

VERSION_KEY = 'schema_version'
LEGACY_VERSION_KEY = 'version'
SCHEMA_VERSION = 1

# kind -> 当前版本、必备字段、写入模块、历史键（None 表示无）。
REGISTRY = {
    'desktop_queue': {'version': 1, 'required': ('tasks',),
                      'owner': 'desktop_automation_service', 'legacy': 'version'},
    'continuity_ledger': {'version': 1, 'required': ('stage',),
                          'owner': 'continuity_ledger', 'legacy': 'version'},
    'continuity_issues': {'version': 1, 'required': ('issues',),
                          'owner': 'continuity_ledger', 'legacy': 'version'},
    'animatic_manifest': {'version': 1, 'required': ('kind', 'source'),
                          'owner': 'animatic_service', 'legacy': 'version'},
    # 对标情报卡：采风产出的「来源」文件，不是阶段完成凭据（缺卡不影响 01 完成）。
    'recon_card': {'version': 1, 'required': ('target', 'sources'),
                   'owner': 'recon_service', 'legacy': None},
    # 修改习惯：项目级修改记录与本机规则（REQ-S01-58/60）。
    'edit_records': {'version': 1, 'required': ('records',), 'owner': 'edit_habits', 'legacy': None},
    'edit_habit_rules': {'version': 1, 'required': ('rules',), 'owner': 'edit_habits', 'legacy': None},
}


def spec(kind):
    """返回产物契约；未登记类型抛 ``KeyError``。"""
    try:
        return REGISTRY[kind]
    except KeyError:
        raise KeyError('未登记的产物类型：%s（新产物须先在此登记版本与必备字段）' % kind)


def registered():
    """已登记产物类型，供清单文档与测试对齐。"""
    return tuple(sorted(REGISTRY))


def stamp(kind, payload, *, version=None):
    """返回写入用的副本：写入版本号，不修改入参。"""
    item = spec(kind)
    if not isinstance(payload, dict):
        raise TypeError('产物必须是对象：%s' % kind)
    out = dict(payload)
    out[VERSION_KEY] = int(version if version is not None else item['version'])
    return out


def _read_version(kind, payload):
    item = spec(kind)
    if VERSION_KEY in payload:
        return payload[VERSION_KEY]
    legacy = item.get('legacy')
    if legacy and legacy in payload:
        return payload[legacy]
    return None


def validate(kind, payload):
    """返回问题清单（空列表＝通过）；只读，不抛异常、不改数据。"""
    try:
        item = spec(kind)
    except KeyError as error:
        return [str(error)]
    if not isinstance(payload, dict):
        return ['%s 必须是对象' % kind]
    problems = []
    found = _read_version(kind, payload)
    if found is None:
        problems.append('%s 缺少版本字段 %s' % (kind, VERSION_KEY))
    elif found != item['version']:
        problems.append('%s 版本 %r 与本模块 %r 不一致，需迁移' % (kind, found, item['version']))
    missing = [key for key in item['required'] if key not in payload]
    if missing:
        problems.append('%s 缺少必备字段：%s' % (kind, ', '.join(missing)))
    return problems


def migrate(kind, payload):
    """把历史产物抬升到当前版本；返回 ``(新副本, 动作清单)``。只加键，不删数据。"""
    item = spec(kind)
    if not isinstance(payload, dict):
        raise TypeError('产物必须是对象：%s' % kind)
    out = dict(payload)
    actions = []
    current = out.get(VERSION_KEY)
    if current is None:
        legacy = item.get('legacy')
        found = out.get(legacy) if legacy else None
        if found is None:
            actions.append('补写缺失的 %s=%s' % (VERSION_KEY, item['version']))
        else:
            actions.append('%s %r→%r' % (VERSION_KEY, found, item['version']))
        out[VERSION_KEY] = item['version']
    elif current != item['version']:
        actions.append('%s %r→%r' % (VERSION_KEY, current, item['version']))
        out[VERSION_KEY] = item['version']
    return out, actions