# -*- coding: utf-8 -*-
"""阶段配置：10 个阶段各自的「模型 ＋ SKILL 勾选」，以及按阶段隔离的预设。

存放位置：
- 项目级：项目的 skill_config.json，形状是 {阶段id: {'model': 'auto', 'skills': [id…]}}；
  规格里写作 project.skillConfig[stage]，落到文件就是这一份。
- 预设：程序目录下的 配置/SKILL/预设.json，形状是
  {'version': 2, 'stages': {阶段id: {预设名: {'model': …, 'skills': […]}}}}。
  每个阶段只显示自己的预设；共享时复制到用户选择的阶段，副本彼此独立。

默认值：模型「自动」，SKILL 勾上该阶段登记的全部 SKILL（规格里每个阶段预置 2 个核心 SKILL）。
"""
from pathlib import Path
import copy

from agent.core import save
from pet_bus import STAGES, STAGE_NAMES, read_json

import model_router
import skill_registry

PROGRAM = Path(__file__).resolve().parent
CONFIG_NAME = 'skill_config.json'
PRESET_PATH = ('配置', 'SKILL', '预设.json')
# 只有剧本阶段会读取「编剧风格」。它保存在项目配置，不改程序内置 SKILL，
# 确保一个项目的创作风格不会意外影响其他项目。
WRITER_STYLE_STAGES = ('script',)
WRITER_STYLE = 'writer_style'
# 旧版四角色协作的编剧规则字段；只读一次迁入编剧风格，下次保存即不再写出。
_LEGACY_WRITER_RULES = 'hollmwood_writer_rules'

# 启动建页会重复读取同一个项目阶段配置。缓存以落盘 mtime 为边界，返回副本，
# 因而不改变调用方可修改返回值而不落盘的旧语义。
_SYNCHRONIZE_CACHE = {}
_GET_CACHE = {}


def _cache_key(project, registry):
    if not project:
        return None
    target = path(project)
    try:
        stamp = target.stat().st_mtime_ns
    except OSError:
        stamp = None
    return (str(target.resolve()), stamp, id(registry))


def _invalidate_cache(project):
    if not project:
        return
    target = str(path(project).resolve())
    for cache in (_SYNCHRONIZE_CACHE, _GET_CACHE):
        for key in tuple(cache):
            if key[0] == target:
                cache.pop(key, None)


def path(project):
    return Path(project) / CONFIG_NAME


def preset_path(program=None):
    return Path(program or PROGRAM).joinpath(*PRESET_PATH)


def default_entry(stage, registry=None):
    """默认配置：模型「自动」，勾上这个阶段仍在维护的全部 SKILL。"""
    reg = registry or skill_registry.default_registry()
    entry = {'model': model_router.AUTO,
             'skills': [skill.name for skill in reg.getByStage(stage) if not skill.deprecated]}
    if stage in WRITER_STYLE_STAGES:
        entry.update(_writer_style_fields({}))
    return entry


def clean_writer_style(value):
    """编剧风格只接受文本；空值表示不附加项目级风格要求。"""
    return str(value or '').strip()


def _writer_style_fields(entry):
    if not isinstance(entry, dict):
        return {}
    style = entry.get(WRITER_STYLE)
    if style is None:
        style = entry.get(_LEGACY_WRITER_RULES)
    return {WRITER_STYLE: clean_writer_style(style)}


def clean_model(value):
    """模型 id 归一：空值与「自动」都记成「自动」，其余照原样留着。

    第 43 期：这里原先只认写死的那五档，模型管理里新加的模型一存进阶段配置就被抹成「自动」
    ——池子才是权威，所以清单不在这儿再定义一份；池里没有的 id 也留着（模型可能只是还没加
    回来，抹掉就等于把用户的选择吃掉了）。
    """
    text = str(value or '').strip()
    return model_router.AUTO if not text or text == model_router.AUTO else text


def clean_skills(values, stage=None, registry=None):
    """去掉不存在项并归一旧别名（顺序稳定，已有项目无需手工迁移）。"""
    reg = registry or skill_registry.default_registry()
    known = {skill.name for skill in (reg.getByStage(stage) if stage else reg.getAll())}
    out = []
    for value in values or ():
        name = str(value or '').strip()
        if name and name in known:
            canonical = reg.canonical_id(name)
            if canonical in known and canonical not in out:
                out.append(canonical)
    return out


def synchronize(project, registry=None):
    """按当前注册表同步配置，保留失效项供发送校验并归位错阶段 SKILL。

    不会把用户主动取消勾选的有效 SKILL 重新选中；仅迁移已经在配置中、
    但因目录重组而落在错误阶段的项。没有阶段项的项目继续由默认值动态补全。
    """
    if not project:
        return False
    reg = registry or skill_registry.default_registry()
    key = _cache_key(project, reg)
    if key in _SYNCHRONIZE_CACHE:
        return _SYNCHRONIZE_CACHE[key]
    target = path(project)
    data = read_json(target)
    if not isinstance(data, dict):
        return False
    payload, moved, changed = dict(data), {}, False
    for stage in STAGES:
        entry = data.get(stage)
        if not isinstance(entry, dict):
            continue
        kept = []
        for raw_name in entry.get('skills') or ():
            item = reg.getById(raw_name)
            if item is None:
                # 保留失效选择作为发送门禁依据；用户确认取消后才可移除。
                kept.append(raw_name)
                continue
            name = reg.canonical_id(raw_name)
            item = reg.getById(name)
            if item is None or item.deprecated:
                changed = True
                continue
            if item.stage != stage:
                moved.setdefault(item.stage, []).append(name)
                changed = True
                continue
            if name not in kept:
                kept.append(name)
            else:
                changed = True
        if kept != list(entry.get('skills') or ()):
            payload[stage] = dict(entry, skills=kept)
            changed = True
    for stage, names in moved.items():
        entry = payload.get(stage)
        entry = dict(entry) if isinstance(entry, dict) else {'model': model_router.AUTO, 'skills': []}
        skills = list(entry.get('skills') or ())
        for name in names:
            if name not in skills:
                skills.append(name)
        if skills != list(entry.get('skills') or ()):
            payload[stage] = dict(entry, skills=skills)
            changed = True
    if changed:
        save(target, payload)
        _invalidate_cache(project)
        key = _cache_key(project, reg)
    _SYNCHRONIZE_CACHE[key] = changed
    return changed


def load(project, registry=None):
    """读一份项目级配置：坏文件／缺项都按默认补齐，不让面板白屏。"""
    reg = registry or skill_registry.default_registry()
    data = read_json(path(project)) if project else {}
    data = data if isinstance(data, dict) else {}
    out = {}
    for stage in STAGES:
        entry = data.get(stage) if isinstance(data.get(stage), dict) else {}
        if entry:
            out[stage] = {'model': clean_model(entry.get('model')),
                          'skills': clean_skills(entry.get('skills'), stage, reg),
                          **(_writer_style_fields(entry) if stage in WRITER_STYLE_STAGES else {})}
        else:
            out[stage] = default_entry(stage, reg)
    return out


def _workflow_data(project):
    data = read_json(path(project)) if project else {}
    return data if isinstance(data, dict) else {}


def current_workflow(project):
    """返回项目统筹投影；缺失即自由模式，保持历史阶段配置行为。"""
    workflow = _workflow_data(project).get('workflow')
    return dict(workflow) if isinstance(workflow, dict) else {}


def project_created_at(project):
    """使用项目登记的创建时间；复制目录时间不能代表项目创建时间。"""
    if not project:
        return None
    root = Path(project if isinstance(project, (str, Path)) else project.root)
    registry = read_json(Path(__file__).resolve().parent / 'projects.json') or {}
    for record in registry.get('projects', ()):
        if Path(record.get('path', '')).resolve() == root.resolve() and record.get('created_at') is not None:
            return record['created_at']
    return None


def workflow_lock(project):
    workflow = current_workflow(project)
    name = str(workflow.get('name') or '').strip()
    locks = workflow.get('lock')
    value = dict(locks.get(name) or {}) if name and isinstance(locks, dict) and isinstance(locks.get(name), dict) else {}
    # 旧试验版曾把中文标签直接写成键；继续可读，但新写只使用受控英文键。
    aliases = {'画幅': 'aspect_ratio', '交付形态': 'delivery_format', '视频模型版本': 'video_model_version'}
    for legacy, canonical in aliases.items():
        if canonical not in value and value.get(legacy):
            value[canonical] = value[legacy]
    return value


def put_workflow(project, workflow):
    """原子写入顶层 workflow；相同 payload 不重写，避免产生无意义备份。"""
    data = _workflow_data(project)
    value = dict(workflow) if isinstance(workflow, dict) else {}
    if data.get('workflow') == value:
        return path(project)
    data['workflow'] = value
    save(path(project), data)
    _invalidate_cache(project)
    return path(project)


def clear_workflow(project):
    """退出统筹模式；保留其他阶段数据和历史锁投影。"""
    data = _workflow_data(project)
    if 'workflow' not in data:
        return path(project)
    workflow = data.get('workflow') or {}
    locks = workflow.get('lock') if isinstance(workflow, dict) else None
    if isinstance(locks, dict) and locks:
        # 退出统筹必须清掉 workflow 键；历史投影另存，供已跑阶段继续可读。
        data['workflow_lock_history'] = dict(locks)
    data.pop('workflow', None)
    save(path(project), data)
    _invalidate_cache(project)
    return path(project)


def workflow_differences(project, preset):
    """统筹建议与当前勾选的差异；只读，供 UI 对照确认。"""
    suggestions = (preset or {}).get('stage_skills') or {}
    data = load(project)
    return {stage: {'suggested': list(skills), 'current': list(data[stage].get('skills') or [])}
            for stage, skills in suggestions.items() if stage in STAGES}


def workflow_deviation_count(project, preset):
    """返回与统筹展开表不一致的阶段数，不改变用户阶段勾选。"""
    return sum(1 for row in workflow_differences(project, preset).values()
               if row['current'] != row['suggested'])


def apply_workflow_empty_stages(project, workflow, preset):
    """仅补显式空阶段并原子写入统筹，不覆盖或重整项目的其余字段。"""
    if not project:
        return load(project)
    target = path(project)
    original = read_json(target) or {}
    data = copy.deepcopy(original) if isinstance(original, dict) else {}
    for stage, skills in ((preset or {}).get('stage_skills') or {}).items():
        # 缺失阶段会在读取时使用既有默认值，不能误当作用户主动清空。
        entry = data.get(stage)
        if stage in STAGES and isinstance(entry, dict) and not entry.get('skills'):
            entry['skills'] = list(skills)
    if isinstance(workflow, dict):
        data['workflow'] = copy.deepcopy(workflow)
    if data != original:
        save(target, data)
        _invalidate_cache(project)
    return load(project)


def save_all(project, data, workflow=None):
    if not project:
        return None
    payload = {}
    for stage in STAGES:
        entry = data.get(stage) or {}
        payload[stage] = {'model': clean_model(entry.get('model')),
                          'skills': list(entry.get('skills') or [])}
        if stage in WRITER_STYLE_STAGES:
            payload[stage].update(_writer_style_fields(entry))
    old = _workflow_data(project)
    selected_workflow = old.get('workflow') if workflow is None else workflow
    if isinstance(selected_workflow, dict):
        payload['workflow'] = selected_workflow
    history = old.get('workflow_lock_history')
    if isinstance(history, dict):
        payload['workflow_lock_history'] = history
    target = path(project)
    save(target, payload)
    _invalidate_cache(project)
    return target


def get(project, stage, registry=None):
    """一个阶段的配置（读不到就是默认值）。"""
    reg = registry or skill_registry.default_registry()
    if stage not in STAGES:
        raise ValueError('没登记的阶段：' + str(stage))
    synchronize(project, reg)
    key = _cache_key(project, reg)
    cached = _GET_CACHE.get(key)
    if cached is not None and stage in cached:
        return copy.deepcopy(cached[stage])
    data = read_json(path(project)) if project else {}
    entry = (data or {}).get(stage) if isinstance(data, dict) else None
    if not isinstance(entry, dict):
        result = default_entry(stage, reg)
        if key is not None:
            _GET_CACHE.setdefault(key, {})[stage] = copy.deepcopy(result)
        return result
    result = {'model': clean_model(entry.get('model')),
              'skills': clean_skills(entry.get('skills'), stage, reg)}
    if stage in WRITER_STYLE_STAGES:
        result.update(_writer_style_fields(entry))
    if key is not None:
        _GET_CACHE.setdefault(key, {})[stage] = copy.deepcopy(result)
    return result


def put(project, stage, model=None, skills=None, registry=None, writer_style=None):
    """写一个阶段的配置：只改传进来的那几项，其余保持原样。"""
    reg = registry or skill_registry.default_registry()
    if stage not in STAGES:
        raise ValueError('没登记的阶段：' + str(stage))
    data = load(project, reg)
    entry = data.get(stage) or default_entry(stage, reg)
    if model is not None:
        entry['model'] = clean_model(model)
    if skills is not None:
        entry['skills'] = clean_skills(skills, stage, reg)
    if stage in WRITER_STYLE_STAGES and writer_style is not None:
        entry[WRITER_STYLE] = clean_writer_style(writer_style)
    data[stage] = entry
    save_all(project, data)
    return entry


def writer_style(project, stage='script', registry=None):
    """返回本项目的编剧风格；空文本表示没有项目级风格要求。"""
    return clean_writer_style(get(project, stage, registry).get(WRITER_STYLE, ''))


def reset(project, stage, registry=None):
    """恢复默认：模型「自动」＋勾上这一阶段的全部 SKILL。"""
    reg = registry or skill_registry.default_registry()
    entry = default_entry(stage, reg)
    return put(project, stage, entry['model'], entry['skills'], reg)


def problems(project, registry=None):
    """配置里指向了不存在的 SKILL／阶段之外的东西、或者这份配置本身读不出来——只报告，不拦（面板会显示默认值）。

    第 28 期：原来只报「认不识的 SKILL／阶段」，配置文件被写坏（或写成一个不是对象的 JSON）时
    read_json 只回 None，面板就惄惄退回默认值——用户以为自己勾的 SKILL 丢了。现在把这种情况也报出来。
    """
    reg = registry or skill_registry.default_registry()
    target = path(project) if project else None
    data = read_json(target) if target else {}
    out = []
    if not isinstance(data, dict):
        if target is not None and Path(target).exists():
            out.append('%s 读不出来（内容不是一份配置），先按默认值走' % CONFIG_NAME)
        return out
    for stage, entry in data.items():
        if stage not in STAGES:
            out.append('配置里有没登记的阶段：%s' % stage)
            continue
        if not isinstance(entry, dict):
            continue
        for name in entry.get('skills') or ():
            if reg.getById(name) is None:
                out.append('%s：SKILL %s 不存在' % (STAGE_NAMES.get(stage, stage), name))
    return out


# ── 预设 ────────────────────────────────────────────────────────────────────
# 预设按阶段分箱保存。每个页面只看自己的箱子；复制预设并不是共享同一条记录，
# 而是把当前预设复制到用户选中的其它阶段，之后各阶段仍可独立修改。
PRESET_VERSION = 3
# 预设按创作模式分组；旧预设没有模式，归入「未分类」排在最后。
PRESET_MODES = ('短视频', '短剧', '影视', '动画')
PRESET_MODE_NONE = '未分类'


def _preset_groups(program=None):
    """读取新旧预设文件，并把旧的扁平格式无损投影成按阶段的格式。"""
    raw = read_json(preset_path(program))
    if not isinstance(raw, dict):
        return {}
    groups = raw.get('stages')
    if isinstance(groups, dict):
        return {str(stage): dict(entries) for stage, entries in groups.items()
                if isinstance(entries, dict)}
    # 兼容已存在的 {名称: {stage, model, skills}} 文件；下次保存才会迁移落盘。
    out = {}
    for label, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        stage = str(entry.get('stage') or '').strip()
        if stage in STAGES:
            copied = dict(entry)
            copied.pop('stage', None)
            out.setdefault(stage, {})[str(label)] = copied
    return out


def _save_preset_groups(groups, program=None):
    save(preset_path(program), {'version': PRESET_VERSION, 'stages': groups})


def presets(program=None, stage=None):
    """返回一个阶段的预设；省略 stage 仅为兼容旧调用，返回扁平视图。"""
    groups = _preset_groups(program)
    if stage is not None:
        return dict(groups.get(str(stage), {}))
    # 旧 API 仍可读取单阶段数据。重名时保留先出现的一份，UI 从不走这条路径。
    flat = {}
    for entries in groups.values():
        for label, entry in entries.items():
            flat.setdefault(label, dict(entry))
    return flat


def _workflow_snapshot(workflow, lock):
    """预设里的总控快照：名称、总控包路径与制作锁；名称为空表示「不使用总控」。"""
    workflow = workflow if isinstance(workflow, dict) else {}
    name = str(workflow.get('name') or '').strip()
    if not name:
        return {}
    return {'name': name, 'skill_ref': str(workflow.get('skill_ref') or ''),
            'lock': {str(key): str(value) for key, value in (lock or {}).items() if value}}


def save_preset(name, model, skills, stage=None, program=None, extra=None):
    """存一份预设（同名覆盖）。名字空着就报错——预设列表里不出现没有名字的东西。

    整套预设 = 模型（含厂商）＋ SKILL ＋ 创作模式；传了 workflow 就连总控与制作锁一起记，
    剧本页传了 writer_style 就连风格一起记。没传的项不写入，套用时也就不会去动它们。
    这些可选项收在 extra 里：mode、workflow（项目总控）、lock（制作锁）、writer_style。
    """
    extra = extra or {}
    mode, workflow, writer_style = extra.get('mode'), extra.get('workflow'), extra.get('writer_style')
    label = ' '.join(str(name or '').split())
    if not label:
        raise ValueError('先给预设起个名字')
    stage = str(stage or '').strip()
    # 无 stage 是给旧的程序接口留的退路；面板永远传当前页面阶段。
    if not stage:
        stage = 'keyframe'
    if stage not in STAGES:
        raise ValueError('没有这个阶段：' + stage)
    if mode is not None and mode not in PRESET_MODES:
        raise ValueError('没有这个创作模式：' + str(mode))
    groups = _preset_groups(program)
    data = groups.setdefault(stage, {})
    entry = {'model': clean_model(model),
             'skills': [str(item) for item in (skills or []) if str(item).strip()]}
    mode = mode or (data.get(label) or {}).get('mode')
    if mode in PRESET_MODES:
        entry['mode'] = mode
    if workflow is not None:
        entry['workflow'] = _workflow_snapshot(workflow, extra.get('lock'))
    if writer_style is not None and stage in WRITER_STYLE_STAGES:
        entry[WRITER_STYLE] = clean_writer_style(writer_style)
    data[label] = entry
    _save_preset_groups(groups, program)
    return data[label]


def preset_mode(entry):
    """一份预设所属的创作模式；缺失或不认识的都归「未分类」。"""
    mode = (entry or {}).get('mode')
    return mode if mode in PRESET_MODES else PRESET_MODE_NONE


def preset_groups(program=None, stage=None):
    """按创作模式分好组的预设名：[(模式, [名称…])…]，空组不出现，「未分类」排最后。"""
    buckets = {}
    for label, entry in presets(program, stage).items():
        buckets.setdefault(preset_mode(entry), []).append(label)
    return [(mode, buckets[mode]) for mode in (*PRESET_MODES, PRESET_MODE_NONE) if buckets.get(mode)]


def rename_preset(old, new, program=None, stage=None):
    """给预设改个名字（第 51 期第 4 条）：内容与位置都不动。

    名字空着、原名不在、新名撞上别人的都当场报错——改名不该顺手覆盖掉另一份预设。
    顺序也照旧（字典按原样重排一遍），下拉框里那一份还站在原地。
    """
    stage = str(stage or 'keyframe')
    groups = _preset_groups(program)
    data = groups.get(stage, {})
    old, new = str(old or '').strip(), ' '.join(str(new or '').split())
    if old not in data:
        raise ValueError('没有这个预设：' + (old or '（空）'))
    if not new:
        raise ValueError('新名字不能空着')
    if new == old:
        return data[old]
    if new in data:
        raise ValueError('已经有同名的预设：' + new)
    moved = {}
    for name, entry in data.items():
        moved[new if name == old else name] = entry
    groups[stage] = moved
    _save_preset_groups(groups, program)
    return moved[new]


def drop_preset(name, program=None, stage=None):
    stage = str(stage or 'keyframe')
    groups = _preset_groups(program)
    data = groups.get(stage, {})
    if str(name) in data:
        data.pop(str(name), None)
        groups[stage] = data
        _save_preset_groups(groups, program)
        return True
    return False


def _model_names(names):
    return {str(name).strip().casefold() for name in names if str(name or '').strip()}


def preset_model_references(names, keep=(), program=None):
    """预设里模型指向 ``names``（ID／显示名／模型名，不分大小写）、又不指向 ``keep`` 的那些：[(阶段, 预设名)]。"""
    gone = _model_names(names) - _model_names(keep)
    return [(stage, label) for stage, entries in _preset_groups(program).items()
            for label, entry in entries.items()
            if isinstance(entry, dict) and str(entry.get('model') or '').strip().casefold() in gone]


def release_preset_model(names, keep=(), program=None):
    """模型从模型池删掉后，把指向它的预设模型改回「自动」；预设本身和 SKILL 勾选保留。返回改动的 [(阶段, 预设名)]。"""
    found = preset_model_references(names, keep, program)
    if found:
        groups = _preset_groups(program)
        for stage, label in found:
            groups[stage][label] = dict(groups[stage][label], model=model_router.AUTO)
        _save_preset_groups(groups, program)
    return found


def project_model_references(project, names, keep=(), registry=None):
    """本项目里模型指向 ``names``、又不指向 ``keep`` 的阶段（比对规则同预设）；没开项目时为空。"""
    gone = _model_names(names) - _model_names(keep)
    if not project or not gone:
        return []
    return [stage for stage in STAGES
            if str(get(project, stage, registry).get('model') or '').strip().casefold() in gone]


def release_project_model(project, names, keep=(), registry=None):
    """模型从模型池删掉后，把本项目里指向它的阶段模型改回「自动」；SKILL 勾选保留。返回改动的阶段。"""
    found = project_model_references(project, names, keep, registry)
    for stage in found:
        put(project, stage, model=model_router.AUTO, registry=registry)
    return found


def apply_preset(project, stage, name, program=None, registry=None, known_workflows=None):
    """把预设套到某个阶段上：模型（含厂商）、SKILL、风格与总控一起写进去。

    预设里没记的项（旧预设、非剧本页的风格）不动当前值；总控记成「不使用」就退出统筹；
    known_workflows 给了就只套用其中登记过的总控，缺失的总控跳过，不写半截数据。
    """
    entry = presets(program, stage).get(str(name))
    if not isinstance(entry, dict):
        raise ValueError('没有这个预设：' + str(name))
    style = entry.get(WRITER_STYLE) if stage in WRITER_STYLE_STAGES else None
    result = put(project, stage, entry.get('model'), entry.get('skills'), registry, writer_style=style)
    if isinstance(entry.get('workflow'), dict):
        _apply_preset_workflow(project, entry['workflow'], known_workflows)
    return result


def _apply_preset_workflow(project, snapshot, known=None):
    master = str(snapshot.get('name') or '').strip()
    if not master:
        clear_workflow(project)
        return True
    if known is not None and master not in known:
        return False
    current = current_workflow(project)
    locks = dict(current.get('lock') or {})
    locks[master] = dict(snapshot.get('lock') or {})
    put_workflow(project, {**current, 'name': master, 'skill_ref': snapshot.get('skill_ref', ''),
                           'lock': locks})
    return True


def share_preset(name, source_stage, target_stages, program=None):
    """复制当前页预设到指定页面；每份都是独立记录，不建立跨页共享引用。"""
    source_stage = str(source_stage)
    groups = _preset_groups(program)
    source = groups.get(source_stage, {}).get(str(name))
    if not isinstance(source, dict):
        raise ValueError('没有这个预设：' + str(name))
    targets = [str(stage) for stage in (target_stages or ())
               if str(stage) in STAGES and str(stage) != source_stage]
    for stage in dict.fromkeys(targets):
        groups.setdefault(stage, {})[str(name)] = dict(source)
    _save_preset_groups(groups, program)
    return tuple(dict.fromkeys(targets))
