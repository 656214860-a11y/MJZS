# -*- coding: utf-8 -*-
"""正式 JSON 产物的版本与字段契约：唯一登记、五态分类、只读校验、STEPS 阶梯迁移。

项目里正式产物的版本此前各写各的——有的用 ``version``（队列、连续性台账、
Animatic 清单），多数根本没写，且没有集中登记、必备字段声明与迁移入口。
本模块是"新增写入"的版本权威：新产物写 ``schema_version``；读取侧对缺版本／
旧版本只给出可报告的结论（``classify`` 五态），**绝不自动改写用户数据**。
历史产物沿用旧键，由 ``migrate()`` 按 ``STEPS`` 阶梯显式抬升，只加键、不删数据；
抬升只发生在产物被正常写入时（G8/H5），``migrate_file()`` 提供带 ``.bak``
备份、失败回滚与落盘后版本断言的迁移写盘（§3c-2 InvokeAI 式）。
"""
from __future__ import annotations

import shutil
from pathlib import Path

VERSION_KEY = 'schema_version'
LEGACY_VERSION_KEY = 'version'
SCHEMA_VERSION = 1

# classify() 的五态闭集：当前／旧版／缺版本／未来／无法判定。
CLASSIFICATIONS = ('current', 'legacy', 'missing', 'future', 'invalid')

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
    # 产物来源关系（U11 核实：artifact_lineage 写 {'version': 1, 'entries': [...]}）。
    'artifact_lineage': {'version': 1, 'required': ('entries',), 'owner': 'artifact_lineage', 'legacy': 'version'},
    # 对标情报卡：采风产出的「来源」文件，不是阶段完成凭据（缺卡不影响 01 完成）。
    'recon_card': {'version': 1, 'required': ('target', 'sources'),
                   'owner': 'recon_service', 'legacy': None},
    # 修改习惯：项目级修改记录与本机规则（REQ-S01-58/60）。
    'edit_records': {'version': 1, 'required': ('records',), 'owner': 'edit_habits', 'legacy': None},
    'edit_habit_rules': {'version': 1, 'required': ('rules',), 'owner': 'edit_habits', 'legacy': None},
    # 桌面模型续发台账（REQ-S01-69）。
    'desktop_send_ledger': {'version': 1, 'required': ('entries',), 'owner': 'desktop_send_ledger', 'legacy': None},
}

# 版本阶梯（Flyway／InvokeAI 式）：``STEPS[kind][n]`` 是「第 n-1 版 → 第 n 版」的
# 纯函数（dict→dict，只做数据抬升、不写版本号；版本号由 ``migrate()`` 统一落到
# 登记版本）。现有产物全部登记在第 1 版、暂无阶梯；新版本落地时在此按级登记，
# 缺某一级时 ``migrate()`` 返回问题清单而不是 ``KeyError``（G8/H5 修订约束）。
STEPS = {}


def spec(kind):
    """返回产物契约；未登记类型抛 ``KeyError``。"""
    try:
        return REGISTRY[kind]
    except KeyError:
        raise KeyError('未登记的产物类型：%s（新产物须先在此登记版本与必备字段）' % kind)


def registered():
    """已登记产物类型，供清单文档与测试对齐。"""
    return tuple(sorted(REGISTRY))


def _version_number(value):
    """把版本字段值收成 int；bool、浮点、非数字字符串一律视为不可解析。"""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit():
            return int(text)
    return None


def _read_version(kind, payload):
    item = spec(kind)
    if VERSION_KEY in payload:
        return payload[VERSION_KEY]
    legacy = item.get('legacy')
    if legacy and legacy in payload:
        return payload[legacy]
    return None


def classify(kind, payload):
    """产物版本五态分类（只读、不抛异常、不改数据）。

    ``current`` 新键 ``schema_version`` 等于登记版本；``legacy`` 有旧版本信息
    但低于登记版本（含只靠旧键 ``version``、版本号却相同的产物——它仍缺
    ``schema_version``，下次正常写入时顺带补上，G8）；``missing`` 完全没有
    版本字段；``future`` 高于登记版本（可读，属主写入口拒写）；``invalid``
    无法判定（非对象／未登记 kind／版本值不可解析）。
    """
    try:
        item = spec(kind)
    except KeyError:
        return 'invalid'
    if not isinstance(payload, dict):
        return 'invalid'
    found = _read_version(kind, payload)
    if found is None:
        return 'missing'
    number = _version_number(found)
    if number is None:
        return 'invalid'
    target = item['version']
    if number > target:
        return 'future'
    if number < target:
        return 'legacy'
    # 版本号相同：只有新键在场才算 current；只靠旧键仍是 legacy。
    return 'current' if VERSION_KEY in payload else 'legacy'


def stamp(kind, payload, *, version=None):
    """返回写入用的副本：写入版本号，不修改入参。

    ``version`` 高于登记版本时拒绝（``ValueError``）——不允许把未来版本号写进
    产物；不高于登记版本照常写（缺省取登记版本）。
    """
    item = spec(kind)
    if not isinstance(payload, dict):
        raise TypeError('产物必须是对象：%s' % kind)
    target = int(version if version is not None else item['version'])
    if target > item['version']:
        raise ValueError('%s 版本 %r 高于登记版本 %r，拒绝写入' % (kind, target, item['version']))
    out = dict(payload)
    out[VERSION_KEY] = target
    return out


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
    """把历史产物按 ``STEPS`` 阶梯抬升到登记版本；返回 ``(新副本, 动作清单)``。

    只加键、不删数据；抬升只发生在产物被正常写入时（G8/H5），本函数不写盘。
    ``future``／无法识别的版本不抬升；``STEPS`` 缺某一级或步骤抛异常时把问题
    写进动作清单、版本号不前进（不抛 ``KeyError``）。无版本字段的产物视为
    第 1 版内容走完整阶梯。
    """
    item = spec(kind)
    if not isinstance(payload, dict):
        raise TypeError('产物必须是对象：%s' % kind)
    out = dict(payload)
    actions = []
    state = classify(kind, payload)
    target = item['version']
    if state == 'current':
        return out, actions
    if state == 'future':
        actions.append('%s 版本高于登记版本 %r，不抬升不回写' % (kind, target))
        return out, actions
    if state == 'invalid':
        actions.append('%s 版本字段无法识别，不抬升' % kind)
        return out, actions
    found = _read_version(kind, payload)
    # 走到这里 state ∈ {legacy, missing}：found 要么为 None（missing），
    # 要么是可解析的旧版本号（classify 已挡掉不可解析值）。
    current = 1 if found is None else _version_number(found)
    while current < target:
        step = STEPS.get(kind, {}).get(current + 1)
        if step is None:
            actions.append('%s 缺少 %s→%s 迁移步骤' % (kind, current, current + 1))
            return dict(payload), actions
        try:
            out = step(dict(out))
        except Exception as exc:
            actions.append('%s %s→%s 迁移步骤失败：%s' % (kind, current, current + 1, exc))
            return dict(payload), actions
        actions.append('%s %r→%r' % (VERSION_KEY, current, current + 1))
        current += 1
    out[VERSION_KEY] = target
    if found is None:
        actions.append('补写缺失的 %s=%s' % (VERSION_KEY, target))
    elif VERSION_KEY not in payload:
        actions.append('%s %r→%r' % (VERSION_KEY, found, target))
    return out, actions


# ── 读取侧分类计数（G8/D4-d）───────────────────────────────────────────────
# 属主在自己的读取点 ``classify`` 之后调 ``note_read_state`` 记一笔；计数只进
# 内存，``diagnostic_capture`` 落盘 ``latest.json`` 时并入 ``artifact_versions``
# 段。读取路径不写盘、不提示用户；L0 不能 import L1，所以计数先落在本模块，
# 由诊断层统一收走——这样 artifact_lineage 这类 L0 属主也走同一计数口径。
_READ_STATES: dict = {}


def note_read_state(kind, state):
    """记一次产物读取分类（内存计数；不抛异常、不写盘）。"""
    try:
        per = _READ_STATES.setdefault(str(kind), {})
        key = str(state)
        per[key] = per.get(key, 0) + 1
    except Exception:
        pass


def read_state_counts():
    """``{kind: {state: 次数}}`` 快照，供 ``diagnostic_capture`` 并入诊断账本。"""
    try:
        return {kind: dict(states) for kind, states in _READ_STATES.items()}
    except Exception:
        return {}


def _restore_backup(backup, path):
    """尽力把 ``.bak`` 拷回原路径；回滚本身失败返回 False（.bak 仍在盘上可人工恢复）。"""
    try:
        if backup.is_file():
            shutil.copyfile(backup, path)
            return True
    except OSError:
        pass
    return False


def _publish_migrated(kind, path, data, migrated, actions, *, publish, read):
    """``.bak`` 备份 → ``publish`` → 读回断言 → 失败回滚；返回 ``(status, payload, actions)``。"""
    actions = list(actions)
    backup = path.with_name(path.name + '.bak')
    try:
        shutil.copyfile(path, backup)
    except OSError as exc:
        return 'failed', data, actions + ['迁移前备份失败，未写盘：%s' % exc]
    try:
        publish(path, migrated)
        check = read(path)
        if not isinstance(check, dict) or classify(kind, check) != 'current':
            raise ValueError('读回版本断言失败')
    except Exception as exc:
        if _restore_backup(backup, path):
            note = '迁移写盘失败，已用 .bak 回滚：%s' % exc
        else:
            note = '迁移写盘失败，回滚也失败（.bak 仍在盘上）：%s' % exc
        return 'failed', data, actions + [note]
    return 'written', migrated, actions


def migrate_file(kind, path, *, publish, read):
    """把 ``path`` 上的产物迁移后写回；返回 ``(status, payload, actions)``。

    InvokeAI 式迁移写盘（任务书 §3c-2）：迁移前把旧文件复制为 ``<名>.bak`` →
    经调用方注入的 ``publish(path, payload)`` 原子发布 → ``read(path)`` 读回
    断言版本到位 → 任一环节失败用 ``.bak`` 回滚，原文件内容不变。``.bak`` 在
    成功后保留备查。抬升只在产物被正常写入时发生（H5），本函数由属主的写
    路径在需要落盘迁移结果时调用，不做独立迁移工具。

    ``publish``／``read`` 由属主注入既有 IO（生产侧为 ``agent.core.save``／
    ``read_json`` 的包装），本函数不 import 上层模块。

    status 闭集：``'written'`` 已发布且读回断言通过；``'skipped'`` 未写盘
    （已是当前版／未来版／无法识别／缺迁移步／读到的不是对象）；``'failed'``
    备份、发布或断言失败（已尽力回滚）。
    """
    path = Path(path)
    data = read(path)
    if not isinstance(data, dict):
        return 'skipped', None, ['%s 读到的不是对象，跳过迁移写盘' % kind]
    state = classify(kind, data)
    if state == 'current':
        return 'skipped', data, []
    if state == 'future':
        return 'skipped', data, ['%s 版本高于登记版本，不迁移不回写' % kind]
    if state == 'invalid':
        return 'skipped', data, ['%s 版本字段无法识别，不迁移' % kind]
    migrated, actions = migrate(kind, data)
    if classify(kind, migrated) != 'current':
        # 缺迁移步或步骤失败：版本没到位，绝不把半成品写盘。
        return 'skipped', data, actions
    return _publish_migrated(kind, path, data, migrated, actions, publish=publish, read=read)
