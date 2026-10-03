# -*- coding: utf-8 -*-
"""统一阶段配置面板：模型下拉 ＋ SKILL 勾选 ＋ 接口 ＋ SKILL 说明 ＋ 保存为预设／重置。

规格（第 28 期第 4 条）要一块面板管住全部 10 个制作阶段：
- 第 43 期起模型下拉的选项全部从「模型管理」里的模型池长出来（「自动」在最前面），默认
  「自动」——面板这里不另存一份模型清单，模型管理里加一条，这里就多一个选项；
- SKILL 勾选支持多选、全选、重置，还能存成预设、下次一键套用；
- 数据源就是 skill_registry.getByStage(stage)，勾选写进 project.skillConfig[stage]
  ＝ skill_config.json 里的 {'model': ..., 'skills': [...]}；
- 第 54 期附件一：面板只做配置（模型／SKILL／预设／说明），**不留执行入口**——
  「执行选中」那颗按钮删掉了，和每页那颗「手动制作XX」重复。要跑就跑页面上的
  「手动制作XX」，那一条路同样走 skill_orchestrator（Panel.run 留着当可编程入口，
  自检与外部调用照旧能用）。

SKILL 不绑定模型：这里挑的模型是「用户偏好」，model_router 还得看 SKILL 声明的 preferredModels
与能力才定得下来。面板只管把选择记下来、把选中的跑起来，不替模型说话。
"""
from pathlib import Path
import re
import shutil

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

import model_pool
import model_router
import skill_budget
import skill_orchestrator
import skill_registry
import stage_config
import stage_models
import ui_plugin_registry
from pet_bus import STAGE_NAMES, read_json
from storage_maintenance import recycle_paths
from ui_tokens import COLORS, FONTS, SPACING
from ui_widgets import (DescriptionBlock, HintLabel, PrimaryButton, ProgressLabel,
                        SecondaryButton, Tooltip)

TITLE = '阶段配置'
_LIVE = []            # 还开着的面板：模型池变了一次就把它们的下拉框都刷一遍（不用重开窗口）
# 老页面上的流程名 → 新的制作阶段 id：面板两边都认，省得每个调用点各写一遍。
FLOW_STAGE = {'writing': 'script', 'storyboard': 'storyboard', 'assets': 'assets',
              'frames': 'keyframe', 'previs': 'previs', 'video_prompt': 'video',
              'audio': 'audio', 'final': 'final', 'edit': 'edit', 'delivery': 'delivery'}
# 反过来查：阶段 id → 工作流名字。只收 workflow_settings 真正认得的七个流程——
# final／edit／delivery 那三个阶段本来就没有「调用设置」这一档，别凭空造出一个按钮来。
FLOW_NAMES = ('writing', 'storyboard', 'assets', 'frames', 'previs', 'video_prompt', 'audio')
STAGE_FLOW = {FLOW_STAGE[name]: name for name in FLOW_NAMES if name in FLOW_STAGE}
# 第 50 期第 1 条：原来那颗「手动配置模型与 SKILL」拆成两个入口，直接长在两个下拉框里——
# 「模型」那一格最后一项是「+ 添加模型…」（去模型管理里加一条自己的模型），「流程 SKILL」
# 那一格最后一项是「+ SKILL 入口…」（自己挑一个 SKILL.md 当这一流程的 SKILL）。
ADD_MODEL_LABEL = '+ 添加模型…'
# 第 64 期任务 14：这颗下拉框直称「SKILL」，默认停在「全选」；原来摆在格子里让你挑的那几份
# 常用 SKILL 挪到外面的勾选框里按顺序排（与这一步自己的 SKILL 同排），格子只留三件事：
# 全选／取消全选／新增（新增＝原来那条「+ SKILL 入口…」，自己挑一份 SKILL.md）。
# 「不使用 SKILL」这一项删掉了：一份都不勾就是不用。
MANAGE_ALL = '全选'
MANAGE_NONE = '取消'
MANAGE_ADD = '新增'
MANAGE_DELETE = '删除已勾选 SKILL'
MANAGE_LABELS = (MANAGE_ALL, MANAGE_NONE, MANAGE_ADD, MANAGE_DELETE)
# 外部包只登记总入口；API 调用只会收到入口指针，不能假装会展开其中的本地子模块。
EXTERNAL_PACKAGE_API_HINT = (
    '外部包总入口：桌面引擎可完整执行；API 仅传入入口。'
)
# 预设不是必填项；用明确的占位项避免刚打开面板就误把第一份预设当作当前选择。
PRESET_PLACEHOLDER = '请选择'
# 勾选框按「功能分组／流程先后」排（第 59 期第 6 条）：文件名前缀就是那条流程里的功能分组。
SKILL_FLOW_ORDER = ('script', 'storyboard', 'asset', 'firstframe', 'whitemodel',
                    'video', 'voice', 'subtitle', 'edit', 'qa', 'delivery')


def skill_order(name):
    """一个 SKILL 在流程里的位置：先按功能分组（名前缀），同组再按名字（第 59 期第 6 条）。"""
    text = str(name or '').lower()
    for index, prefix in enumerate(SKILL_FLOW_ORDER):
        if text.startswith(prefix):
            return (index, text)
    return (len(SKILL_FLOW_ORDER), text)


# 第 29 期第 1／4 条：页面上那些重复的「设置 Model + SKILL」「配置线上视频 API」入口并到这块
# 面板里——入口只留一处（标题栏的「阶段配置」），接口本身一个都不少：编排模型的「调用设置」、
# 线上视频 API、配音接口，都在下面这一行里点得到。
def markdown_document(path):
    """读取配置项说明：优先同目录 README，缺失时才读取 SKILL。"""
    source = Path(path) if path else None
    if source is None:
        return ''

    def sibling(name):
        """按大小写无关的文件名寻找说明，兼容 readme.MD 等写法。"""
        try:
            return next((item for item in source.parent.iterdir()
                         if item.is_file() and item.name.casefold() == name), None)
        except OSError:
            return None

    readme = sibling('readme.md')
    skill = sibling('skill.md')
    candidates = [readme, skill, source]
    seen = set()
    for candidate in candidates:
        if candidate is None:
            continue
        marker = str(candidate).casefold()
        if marker in seen:
            continue
        seen.add(marker)
        try:
            content = candidate.read_text(encoding='utf-8-sig').strip()
        except OSError:
            continue
        if content:
            return content
    return ''


def note_text(skill):
    """显示注册 SKILL 对应 Markdown 文件的完整内容，缺失时才使用注册表摘要。"""
    if skill is None:
        return ''
    content = markdown_document(getattr(skill, 'path', None))
    if content:
        return content
    return '\n'.join(line for line in (str(skill.displayName or skill.name or ''),
                                        str(skill.description or '')) if line)


def external_package_api_hint(skills, model_id):
    """仅用注册表元数据提示 API 模型：外部包总入口不会在远端展开。"""
    if model_pool.desktop_engine(model_id):
        return ''
    if any(bool(getattr(skill, 'meta', {}).get(skill_registry.IMPORTED_PACKAGE_FLAG, False))
           for skill in skills or ()):
        return EXTERNAL_PACKAGE_API_HINT
    return ''


def workflow_note_text(label, path):
    """读取工作流说明：README.md 优先，缺失时回退 SKILL.md。"""
    content = markdown_document(path)
    return label + ('\n\n' + content if content else '\n\n未找到该工作流的说明文件。')


def open_cloud_video(desktop):
    """线上视频 API（万相 / Seedance）的设置窗口。"""
    return ui_plugin_registry.module('cloud_video').settings_window(desktop)


def open_tts(window):
    """配音接口（TTS）的设置窗口。"""
    import tts_settings
    return tts_settings.show(window)


def interfaces_of(desktop, stage, function=None):
    """面板上「接口」那一行的内容：这一阶段还能用得上的连接入口。

    没有接口的阶段（比如质检与交付）返回空表——那一行干脆不画，省得占地方。

    第 36 期第 1 条：这里原来还挂着一颗「调用设置」（编排模型的程序位置／自定义模型 ID／
    SKILL 文件）。用户要的是「删除调用设置按钮」，还要把里面那个 SKILL 挪到 SKILL 勾选行
    （视频阶段就摆在「视频质检」右边，见 Panel.build_flow_skill）。第 50 期第 1 条起模型与
    SKILL 就在面板的两个下拉框里挑；第 51 期第 3 条再把剩下那颗「引擎设置」也删掉——那扇窗里
    能配的东西（模型、SKILL）现在都在本面板上，用户判它重复。视频阶段那颗「线上视频 API」按
    用户要求改名「调用设置」，是付费接口，另一码事；「配音接口（TTS）」同理。
    """
    rows = []
    stage = stage_for(stage)                  # 认老流程名（video_prompt → video）
    if stage == 'video':
        rows.append(('调用设置', lambda: open_cloud_video(desktop)))
    if stage == 'audio':
        rows.append(('配音接口（TTS）', lambda: open_tts(getattr(desktop, 'win', None))))
    return rows


# ── 第 36 期第 1 条：编排流程自己的 SKILL（原来只在「调用设置」里挑） ──────────────
def flow_skill_choices(flow):
    """这一流程能用的常用 SKILL：[(显示名, SKILL.md 路径)]（第 59 期第 5 条：没有「不使用」那一项）。

    名单来自 workflow_settings 的预设表（万能剧本工作流／鲸剧工作流／Drama 分镜…），
    只留这一流程登记过、并且文件真在本地的那几个——摆出来让人挑的必须是点得动的。
    顺序就是预设表的顺序，勾选框按它排。
    """
    import workflow_settings as ws
    rows = []
    allowed = ws.FLOW_SKILLS.get(flow, ())
    for label, folder in ws.SKILL_PRESETS:
        if folder not in allowed:
            continue
        try:
            path = ws.preset_skill(folder)
        except Exception:
            continue
        if path.is_file():
            rows.append((label, str(path)))
    return rows


def flow_skill_display(skill):
    """写进配置的那条 SKILL → 下拉框里显示什么（预设给显示名，自定义文件给「文件夹/SKILL.md」）。

    第 50 期第 1 条：「+ SKILL 入口…」选的是自己的 SKILL.md，总得让人看见自己挑的是哪一份——
    原来一律写「自定义 Skill」，看不出挑了什么。自定义文件按引擎的规矩都叫 SKILL.md，光看
    文件名还是分不出来，所以带上它所在的文件夹。
    """
    text = str(skill or '')
    if not text:
        return ''
    import workflow_settings as ws
    label = ws.preset_label(text)
    if label != '自定义 Skill':
        return label
    path = Path(text)
    return (path.parent.name + '/' + path.name) if path.parent.name else path.name


def chinese_skill_display(label):
    """阶段配置面板只向用户显示中文名称，不泄露路径或装饰符号。"""
    text = ''.join(char for char in str(label or '') if '\u4e00' <= char <= '\u9fff')
    return text or '自定义技能'


def skill_checkbox_label(path):
    """勾选框只显示该 SKILL 文件名的纯中文部分。"""
    return chinese_skill_display(Path(str(path or '')).name)


def registered_skill_checkbox_label(skill):
    """注册 SKILL 的勾选项优先显示注册表名称，而不是通用的 SKILL.md 文件名。"""
    label = (getattr(skill, 'displayName', '') or getattr(skill, 'name', '') or
             getattr(skill, 'path', ''))
    return chinese_skill_display(label)


def flow_skill_match(text, flow, current=()):
    """勾选框／文件框里的那一条 → 要写进配置的值（预设给路径／自己挑的文件给路径／原来那份原样留着）。"""
    text = str(text or '').strip()
    if not text:
        return ''
    if Path(text).is_file():
        return str(Path(text).resolve())
    known = dict(flow_skill_choices(flow))
    if text in known:
        return known[text]
    old = [current] if isinstance(current, str) else list(current or ())
    for item in old:
        if text == flow_skill_display(item):
            return str(item)          # 选回自己那一份：原样留着，别把配好的抹掉
    return ''


def flow_skill_paths(project, flow):
    """这一流程当前勾了哪几份 SKILL（第 59 期第 5 条起是一张清单；没存过就是这一流程的默认那份）。

    直读项目里那一份设置；失效路径由面板加载时过滤并回写，避免已删除文件继续出现在勾选区。
    """
    import workflow_settings as ws
    try:
        path = ws.settings_path(project)
        data = read_json(path) if path.is_file() else {}
        draft = ((data or {}).get('flows') or {}).get(flow) or {}
        engine = draft.get('engine') if draft.get('engine') in ws.ENGINES else 'codex'
        profile = (draft.get('profiles') or {}).get(engine) or {}
        if not profile:
            return ws.skills_of(ws.defaults(flow)['profiles'][engine])
        return ws.skills_of(profile)
    except Exception:
        return []


def flow_skill_value(project, flow):
    """这一流程当前勾了哪几份 SKILL 的显示名（预设给显示名，自己挑的给「文件夹/SKILL.md」）。"""
    return [flow_skill_display(item) for item in flow_skill_paths(project, flow)]


def set_flow_skills(project, flow, values):
    """把勾中的那几份 SKILL 写进这一流程当前的引擎档（与「调用设置」里是同一处），返回写下的路径清单。"""
    import workflow_settings as ws
    path = ws.settings_path(project)
    data = read_json(path) if path.is_file() else {}
    data = data if isinstance(data, dict) else {}
    draft = (data.get('flows') or {}).get(flow)
    if not isinstance(draft, dict):
        draft = ws.load(project, flow)
    engine = draft.get('engine') if draft.get('engine') in ws.ENGINES else 'codex'
    profile = (draft.get('profiles') or {}).get(engine)
    if not isinstance(profile, dict):
        profile = dict(ws.defaults(flow)['profiles'][engine])
    current = ws.skills_of(profile)
    # 第 50 期第 1 条：「新增 SKILL」给的是一个文件路径，预设名单里找不到就原样用它。
    picked = []
    for value in values or ():
        item = flow_skill_match(value, flow, current)
        if item and item not in picked:
            picked.append(item)
    ws.set_skills(profile, picked)
    draft.setdefault('profiles', {})[engine] = profile
    draft['engine'] = engine
    data.setdefault('flows', {})[flow] = draft
    ws.save(path, data)
    return picked


# ── 第 36 期第 4 条：每个阶段都有「手动配置模型与 SKILL」的入口 ──────────────────
MANUAL_NAME = '阶段手动配置.json'          # 手动配的那一档落在项目里（与自动档的 skill_config.json 分开）


def manual_path(project):
    return Path(project) / MANUAL_NAME


def manual_entry(project, stage):
    """这一阶段手动配的模型 ID 与 SKILL 文件（没配过就是空的一份）。"""
    data = read_json(manual_path(project)) if project else {}
    entry = (data or {}).get(stage) if isinstance(data, dict) else None
    return dict(entry) if isinstance(entry, dict) else {}


# 第 50 期第 1 条：原来还有一小块「手动配置（自定义模型 ID＋SKILL 文件）」
# 的弹窗与它的写入口（manual_dialog／set_manual_entry／open_manual）：这两件事现在就在上面两个
# 下拉框里（「+ 添加模型…」／「+ SKILL 入口…」），再留一扇窗就是重复入口，整块删掉。
# manual_entry 留着读：旧项目里手动填过的模型 ID 仍然算数（见 Panel.context）。


def stage_for(value):
    """阶段 id 或老流程名 → 阶段 id（认不出的原样退回，面板照样画得出来）。"""
    text = str(value or '').strip()
    return FLOW_STAGE.get(text, text)


def stage_label(stage):
    """阶段 id → 「06 首帧管理」（认不出的原样退回，面板抬头用它）。"""
    index = list(STAGE_NAMES).index(stage) + 1 if stage in STAGE_NAMES else 0
    name = STAGE_NAMES.get(stage, stage)
    return '%02d %s' % (index, name) if index else str(name)


def panel_title(stage):
    """面板抬头：阶段 id → 「阶段配置 · 06 首帧管理」。"""
    return '阶段配置 · ' + stage_label(stage)


def stage_of_page(index, stages=None):
    """页序号 → 阶段 id（第 11 页参考网站没有阶段，返回空）。"""
    names = list(stages or STAGE_NAMES)
    return names[index] if 0 <= index < len(names) else ''

def stage_button_for(parent, command, text='阶段配置'):
    """造一颗统一次级操作「阶段配置」，与发送键形成明确主次层级。"""
    button = SecondaryButton(parent, text=text, command=command, width=16)
    # 这是语义标记而非视觉样式；回归可据此找到入口，不再耦合已废弃的暖色样式名。
    button._stage_config_entry = True
    return button


def stage_button_label(desktop, stage, fallback='阶段配置'):
    """阶段入口显示实际会被派发的模型／引擎，避免按钮与三虎调用目标不一致。"""
    project = desktop_project(desktop)
    if not project:
        return fallback
    try:
        chosen = str(stage_config.get(project, stage_for(stage)).get('model') or '').strip()
    except Exception:
        return fallback
    if not chosen or chosen == model_router.AUTO:
        # 「自动」不是没有模型：三虎仍会按该流程当前有效引擎启动。按钮直接说出
        # 实际目标，避免用户看到“阶段配置”却发现启动了 Codex／Claude。
        flow = STAGE_FLOW.get(stage_for(stage))
        if not flow:
            return fallback
        try:
            import workflow_settings
            config = workflow_settings.current(project, flow)
            actual = workflow_settings.effective_model(project, flow)
            records = pool_records(desktop)
            for model_id, record in records.items():
                if str(record.get('model') or '').strip() == str(actual).strip():
                    return model_pool.provider_name(model_id, record) or fallback
            return {'codex': 'Codex', 'claude': 'Anthropic', 'qwen': 'Qwen'}.get(
                config.get('engine'), fallback)
        except Exception:
            return fallback
    # 资产／首帧的本地生产模型不会登记到 API 模型池；此前直接查模型池会得到空名称，
    # 使阶段配置按钮错误回退为“阶段配置”。优先从该页面的生产模型清单取显示名。
    try:
        for model_id, label in stage_models.production_choices(stage_for(stage), project):
            if str(model_id) == chosen:
                return str(label) or fallback
    except Exception as exc:
        return fallback + '（生产模型读取失败：%s）' % exc
    record = pool_records(desktop).get(chosen, {})
    return model_pool.provider_name(chosen, record) or fallback


def stage_button(parent, desktop, index, text='阶段配置'):
    """各阶段页「手动XX」右边那颗「阶段配置」（第 32 期第 6 条）。

    面板此前只在剧本准备页挂着，用户到了别的阶段还得跑回去点；现在每页各留一颗，
    按页序号找阶段（stage_of_page），点开的就是这一页那一个阶段的模型与 SKILL。
    """
    stage = stage_of_page(index)
    button = stage_button_for(parent, lambda: None, stage_button_label(desktop, stage, text))
    # 阶段配置只读取／编辑配置，不会启动生产任务；后台任务进行时仍须允许用户查看或调整它。
    button.configure(command=lambda: open_for_page(desktop, index, button))
    return button


def desktop_project(desktop):
    return getattr(desktop, 'root', None)


def pet_of(desktop):
    return getattr(desktop, 'pet', None)


def status_of(desktop, text):
    setter = getattr(desktop, 'status', None)
    if setter is not None and hasattr(setter, 'set'):
        try:
            setter.set(text)
            return text
        except Exception:
            return ''
    return ''


def run_report(desktop, text):
    """把一句结论说给三虎（说不出去也不能让面板崩）。"""
    pet = pet_of(desktop)
    if pet is None or not hasattr(pet, 'say'):
        return ''
    try:
        pet.say(text)
    except Exception:
        return ''
    return text


def waiting_reason(rows):
    """「要回页面按」的那几个为什么不算做完（第 30 期第 7 条）。

    用户报的是「点击执行选中，提示成了 2 个，没成 0 个」——查下来是那 2 个 SKILL 的 tools
    全落在页面上（要 ComfyUI、要付费接口、要人判断），编排器把它们判成 page／input 收场，
    原先那一行把这两种也算「成了」，于是什么都没动手却报「成了 2 个」。这一行把原因写出来。
    """
    lines = []
    for row in rows or []:
        name = row.get('name') or row.get('skill') or '这个 SKILL'
        if row.get('status') == skill_orchestrator.PAGE:
            lines.append('%s：只能回「%s」页面上按（%s）'
                         % (name, row.get('pageTitle') or row.get('page') or '对应页面',
                            row.get('detail') or '页面上对应的按钮'))
        else:
            lines.append('%s：还缺您手上的文件——%s' % (name, row.get('detail') or '请先补上'))
    if not lines:
        return ''
    return '这几个不算做完：编排器不替您在界面上按按钮。' + '；'.join(lines)


def pool_records(desktop):
    """模型池：优先问宠物（它认的那一份全局配置），没有宠物时按程序目录读一次。

    规格里的「模型选项不硬编码，全部来自模型管理」就落在这里：面板不另存一份清单。
    """
    pet = pet_of(desktop)
    getter = getattr(pet, 'agent_model_records', None)
    if callable(getter):
        try:
            return getter()
        except Exception:
            return model_pool.pool(program=program_of(desktop))
    return model_pool.pool(program=program_of(desktop))


def stage_capabilities(stage, registry=None):
    """这一阶段的 SKILL 要模型会些什么（capabilities 的并集，第 58 期第 5 条）。

    判据不另写一份表：skills/*.skill.md 抬头里的 capabilities 就是唯一出处——
    阶段要什么、模型会什么，两边同一个词表（model_pool.CAPABILITY_TAGS）。
    """
    reg = registry or skill_registry.default_registry()
    try:
        items = reg.getByStage(stage)
    except Exception:
        return ()
    caps = []
    for item in items:
        for cap in getattr(item, 'capabilities', None) or ():
            if cap and str(cap) not in caps:
                caps.append(str(cap))
    return tuple(caps)


def model_fits_stage(value, stage, registry=None):
    """这条模型对不对得上这一阶段的功能（第 58 期第 5 条）。

    规矩：这一阶段要的能力里模型会一样就算对口；模型一个能力标签都没登记
    （比如用户自己加的本地模型）就不替他判死，照旧摆出来；纯工具活的阶段（剪辑）什么模型都行。
    """
    needed = stage_capabilities(stage, registry)
    if not needed:
        return True
    raw = value.get('capabilities') if isinstance(value, dict) else value
    tags = model_pool.capabilities_of(raw)
    return not tags or any(tag in needed for tag in tags)


def model_choices(desktop, stage=None):
    """面板下拉的选项：(id, 文案)——「自动」在前，后面是模型管理里的每一条。

    第 46 期第 7／8 条：首帧与资产这两个阶段还要接上它们的**生产模型**（本地 ComfyUI／云端生图／
    首帧 Agent 引擎）——原来这几条各长在「手动制作首帧」「手动制作资产」窗口自己的下拉框里，
    同一件事两处挑、还互相看不见；现在都并到这一处，制作窗口只读它。

    API 统一配置是模型池唯一来源：用户保存一条模型后，它必须能在每个阶段配置中选到。
    能力标签只供路由器挑选自动模型，不能把用户刚保存的 GPT‑6 一类模型从手动下拉中藏掉。
    页面专用的生产模型仍由 ``stage_models`` 按所属阶段追加。
    """
    records = pool_records(desktop)
    import workflow_settings
    options = list(model_pool.options(records, with_auto=True,
                                      labeler=workflow_settings.desktop_model_label))
    seen = {label for _model_id, label in options}
    for value, label in stage_models.production_choices(stage, desktop_project(desktop)):
        if label not in seen:
            seen.add(label)
            options.append((value, label))
    return tuple(options)


def grouped_model_choices(desktop, stage=None):
    """模型下拉的两级数据：供应商 → 具体模型，第二级仍保存稳定的模型 id。"""
    records = pool_records(desktop)
    groups = {}
    for model_id, label in model_choices(desktop, stage):
        if model_id == model_router.AUTO:
            provider = '自动选择'
        elif model_id in records:
            provider = model_pool.provider_name(model_id, records[model_id])
        else:
            provider = '本机制作'
        groups.setdefault(provider, []).append((model_id, label))
    return groups


def sync_models(project, program=None):
    """第 59 期第 12 条：把各页面阶段配置里已经挑过的模型补进模型池。

    用户的话：「每个页面阶段配置中已有的模型，自动同步到配置中；每个页面配置的模型下拉框，
    也自动新增设置中统一配置的可用大模型」。后一句本来就成立（下拉全部从池里长出来，见
    model_choices）；前一句靠这一下：项目里存着、池里还没有的那几条补成最小记录
    （显示名＝模型 ID），于是每个页面的下拉与「设置 → 模型配置」里都看得到、也改得动。
    生产模型（本地 ComfyUI／云端生图）与「自动」不是要发请求的模型 id，不往池子里搬。

    返回这一次补进去的 id 清单（没有就是空表）。
    """
    if not project:
        return []
    wanted = []
    try:
        from pet_bus import STAGES
        for stage in STAGES:
            value = str(stage_config.get(project, stage).get('model') or '').strip()
            if value and value != model_router.AUTO and not stage_models.is_production(stage, value):
                if value not in wanted:
                    wanted.append(value)
    except Exception:
        return []
    try:
        records = model_pool.pool(program=program)
        missing = [value for value in wanted if value not in records]
        if not missing:
            return []
        data = model_pool.raw(program=program)
        for value in missing:
            data = model_pool.upsert(data, {'label': value, 'model': value})
        model_pool.store(data, program)
    except Exception:
        return []
    return missing


def refresh_all():
    """模型管理里加／改／删了一条之后调它一次：还开着的面板跟着换选项（不用重开软件）。"""
    live = []
    for panel in _LIVE:
        try:
            if panel.winfo_exists():
                live.append(panel)
        except Exception:
            continue
    _LIVE[:] = live
    for panel in live:
        try:
            panel.refresh_models()
        except Exception:
            continue
    return len(live)


def build_orchestrator(desktop, project):
    """挂上本项目的一套编排器：总线／错误账本都用桌面现成的。

    路由器按程序目录读模型池（阶段配置挑中的那条要是模型管理里的自定义模型，也得发得出去）。
    """
    from stage_execution_service import build_orchestrator as _build_orchestrator
    return _build_orchestrator(desktop, project)


class Panel(ttk.Frame):
    """一块阶段配置面板：模型 ＋ SKILL 勾选 ＋ 底部三个按钮。"""

    def __init__(self, master, desktop, stage, function=None, compact=True):
        ttk.Frame.__init__(self, master)
        self.desktop = desktop
        self.stage = stage_for(stage)
        self.function = function
        self.compact = bool(compact)
        self.registry = skill_registry.default_registry()
        # SKILL 是用户可随时导入／移除的文件。阶段配置是用户主动打开的懒加载入口，
        # 此处强制刷新而非等启动缓存失效，保证新文件立刻出现、已删文件不再有勾选框。
        self.registry.scan(force=True)
        # 第 59 期第 6 条：勾选框按功能分组／流程先后排（原来按名字的字母序，几组混着跳）。
        # 兼容别名仍留在注册表供旧项目读取；配置面板只展示仍可单独执行的主 SKILL。
        self.skills = [item for item in self.registry.getByStage(self.stage) if not item.deprecated]
        self.vars = {}
        self.model = tk.StringVar(value=model_router.AUTO)
        self.hollmwood_enabled_var = tk.BooleanVar(value=True)
        self.hollmwood_editor_choice = tk.StringVar(value='选择要编辑的内容')
        self._picked = ''              # 刚才选着的那一格（点「+ 添加模型…」要退回来）
        self.preset = tk.StringVar(value=PRESET_PLACEHOLDER)
        self.preset_action = tk.StringVar(value='选择操作')
        # 下拉的选项＝模型管理里那几条（第 43 期：不写死，池子加一条这里就多一项）。
        self.choices = model_choices(self.desktop, self.stage)
        self.labels = [label for _model_id, label in self.choices]
        self.groups = grouped_model_choices(self.desktop, self.stage)
        self.provider = tk.StringVar(value=next(iter(self.groups), '自动选择'))
        # 第 36 期第 1／4 条：这一阶段对应的编排流程（没有就是 None）——流程 SKILL 与手动配置都要它。
        self._flow = STAGE_FLOW.get(self.stage)
        self.workflow_choice = tk.StringVar(value='不使用统筹')
        self._build()
        self.bind('<Destroy>', self.cancel_skill_layout, add='+')
        _LIVE.append(self)

    def destroy(self):
        """关掉就从「还开着的面板」名单里划掉（模型池变了不用再刷它）。"""
        self.cancel_skill_layout()
        try:
            _LIVE.remove(self)
        except ValueError:
            pass
        return ttk.Frame.destroy(self)

    def cancel_skill_layout(self, event=None):
        """销毁面板或其顶层窗口时撤销待执行的换行回调。"""
        if event is not None and event.widget is not self:
            return
        job = getattr(self, '_skill_layout_job', None)
        if job is not None:
            try:
                self.after_cancel(job)
            except tk.TclError:
                pass
            self._skill_layout_job = None

    # ── 画界面 ──────────────────────────────────────────────────────────────
    def _build(self):
        # 阶段配置以连续表单阅读为主，统一使用最小设计间距和标签宽度，避免控件跳列。
        pad = SPACING['xs']
        label_width = 10
        # 预设决定整套配置，因此置于厂商／模型之前。
        row = ttk.Frame(self)
        row.pack(fill='x', pady=(0, pad))
        ttk.Label(row, text='预设', style='Muted.TLabel', width=label_width).pack(side='left')
        self.presets = ttk.Combobox(row, textvariable=self.preset, state='readonly', width=14,
                                    values=[PRESET_PLACEHOLDER] + self.preset_names())
        self.presets.pack(side='left', padx=(SPACING['xs'], SPACING['xs']))
        self.presets.bind('<<ComboboxSelected>>', lambda event: self.apply_preset())
        self.preset_actions = ttk.Combobox(
            row, textvariable=self.preset_action, state='readonly', width=12,
            values=['选择操作', '保存为预设', '删除预设', '重命名预设', '复制本预设到其他页面'])
        self.preset_actions.pack(side='left', padx=(0, SPACING['xs']))
        self.preset_actions.bind('<<ComboboxSelected>>', lambda event: self.run_preset_action())
        self.restore_defaults_button = SecondaryButton(row, text='恢复默认', width=12,
                                                       command=self.reset_defaults)
        self.restore_defaults_button.pack(side='left')
        HintLabel(row, text='勾选项与模型已自动保存').pack(side='left', padx=(SPACING['sm'], SPACING['none']))

        coordinator = ttk.LabelFrame(self, text='统筹 SKILL', padding=pad)
        coordinator.pack(fill='x', pady=(0, pad))
        self.build_workflow_coordinator(pad, coordinator)

        engine = ttk.LabelFrame(self, text='由谁执行', padding=pad)
        engine.pack(fill='x', pady=(0, pad))
        top = ttk.Frame(engine)
        top.pack(fill='x')
        ttk.Label(top, text='厂商', style='Muted.TLabel', width=label_width).pack(side='left')
        self.providers = ttk.Combobox(top, textvariable=self.provider, state='readonly', width=14,
                                      values=list(self.groups))
        self.providers.pack(side='left', padx=(SPACING['xs'], SPACING['xs']))
        self.providers.bind('<<ComboboxSelected>>', lambda event: self.choose_provider())
        # 第 50 期第 1 条：最后一项是「+ 添加模型…」——原来那颗「手动配置模型与
        # SKILL」里的「自定义模型」入口，现在就在挑模型的那一格旁边。
        self.models = ttk.Combobox(top, textvariable=self.model, state='readonly',
                                   width=14,
                                   values=self.provider_labels() + [ADD_MODEL_LABEL])
        self.models.pack(side='left', padx=(SPACING['xs'], 0))
        self.models.bind('<<ComboboxSelected>>', lambda event: self.choose_model())
        # 只在用户改选模型后按需探测；构造／load 不调用，避免打开页面时扫描本机程序。
        self.route_hint = HintLabel(engine, text='')
        self.route_hint.pack(fill='x', pady=(0, SPACING['none']))
        skill_section = ttk.LabelFrame(self, text='怎么执行', padding=pad)
        skill_section.pack(fill='x', pady=(0, pad))
        self.skill_content = ttk.Frame(skill_section)
        self.skill_content.pack(fill='x')
        self.build_flow_skill(self.skill_content)
        # 第 30 期第 7 条：跑完一批之后，除了三个数，还要说清「为什么不算做完」——
        # 得回页面按的和缺文件的分开讲，用户才知道下一步该去哪儿。
        # 执行编排时的细节仍独占一行，避免覆盖上面的结果摘要。
        self.reason = DescriptionBlock(skill_section, text='')
        self.reason.pack(fill='x', pady=(0, pad))
        specific = ttk.LabelFrame(self, text='本页专属', padding=pad)
        specific.pack(fill='x', pady=(0, pad))
        self.build_hollmwood_editors(pad, specific)
        self.build_interfaces(pad, specific)
        self.bottom_bar = ttk.Frame(self)
        self.bottom_bar.pack(side='bottom', fill='x', pady=(pad, 0))
        self.state = ProgressLabel(self.bottom_bar, text='选择预设即可套用；确认保存本页。')
        self.state.pack(side='left')
        self.preset_hint = self.state
        self.confirm_button = PrimaryButton(self.bottom_bar, text='确认并关闭', width=12,
                                            command=self.confirm)
        self.confirm_button.pack(side='right')
        self.build_notes(pad)
        self.load()

    def build_hollmwood_editors(self, pad, parent=None):
        """仅在真正调用 HOLLMWOOD 的阶段提供规则编辑，避免无关页面出现无效入口。"""
        if self.stage not in stage_config.HOLLMWOOD_STAGES:
            return None
        row = ttk.Frame(parent or self)
        row.pack(fill='x', pady=(SPACING['none'], pad))
        ttk.Label(row, text='HOLLMWOOD', style='Muted.TLabel', width=10).pack(side='left')
        ttk.Checkbutton(row, text='四角色协作', variable=self.hollmwood_enabled_var).pack(
            side='left', padx=(SPACING['xs'], SPACING['sm']))
        self.hollmwood_editor = ttk.Combobox(
            row, textvariable=self.hollmwood_editor_choice, state='readonly', width=18,
            values=['选择要编辑的内容', '节奏模板', '导演规则', '编剧规则', '编辑规则', '演员规则'])
        self.hollmwood_editor.pack(side='left', padx=(SPACING['xs'], SPACING['sm']))
        self.hollmwood_editor.bind('<<ComboboxSelected>>', lambda event: self.choose_hollmwood_editor())
        DescriptionBlock(row, text='关闭时按所选 SKILL 直发；SKILL 指令仅作用于编剧角色。').pack(
            side='left', padx=(SPACING['sm'], SPACING['none']))
        return row

    def choose_hollmwood_editor(self):
        """下拉项只是编辑入口；选中后打开对应页面并复位，允许重复编辑同一项。"""
        fields = {
            '节奏模板': stage_config.HOLLMWOOD_RHYTHM,
            '导演规则': stage_config.HOLLMWOOD_DIRECTOR,
            '编剧规则': stage_config.HOLLMWOOD_WRITER,
            '编辑规则': stage_config.HOLLMWOOD_EDITOR,
            '演员规则': stage_config.HOLLMWOOD_ACTOR,
        }
        field = fields.get(self.hollmwood_editor_choice.get())
        if field is None:
            return None
        self.hollmwood_editor_choice.set('选择要编辑的内容')
        return self.open_hollmwood_editor(field)

    def open_hollmwood_editor(self, field):
        """在独立弹窗编辑项目级覆盖；不写程序内置模板，便于恢复默认。"""
        project = desktop_project(self.desktop)
        if not project:
            messagebox.showinfo(TITLE, '请先选择项目。', parent=self.winfo_toplevel())
            return None
        import hollmwood_roles
        is_rhythm = field == stage_config.HOLLMWOOD_RHYTHM
        labels = {stage_config.HOLLMWOOD_DIRECTOR: '导演规则', stage_config.HOLLMWOOD_WRITER: '编剧规则',
                  stage_config.HOLLMWOOD_EDITOR: '编辑规则', stage_config.HOLLMWOOD_ACTOR: '演员规则'}
        title = '编辑节奏模板' if is_rhythm else labels.get(field, '角色规则')
        default = (hollmwood_roles.load_rhythm_template()
                   if is_rhythm else hollmwood_roles.default_role_rules(next(role for role, key in {
                       'director': stage_config.HOLLMWOOD_DIRECTOR, 'writer': stage_config.HOLLMWOOD_WRITER,
                       'editor': stage_config.HOLLMWOOD_EDITOR, 'actor': stage_config.HOLLMWOOD_ACTOR}.items() if key == field)))
        current = stage_config.get(project, self.stage).get(field, '') or default
        window = tk.Toplevel(self.winfo_toplevel())
        window.title(title + ' · ' + stage_label(self.stage))
        window.transient(self.winfo_toplevel())
        window.minsize(620, 430)
        body = ttk.Frame(window, padding=SPACING['md'])
        body.pack(fill='both', expand=True)
        DescriptionBlock(body, text='项目级规则：保存后仅在本项目下一次 HOLLMWOOD 四角色运行时生效。').pack(
            anchor='w', pady=(SPACING['none'], SPACING['sm']))
        editor = tk.Text(body, wrap='word', undo=True, font=FONTS['body'],
                         bg=COLORS['background_card'], fg=COLORS['text_primary'],
                         insertbackground=COLORS['primary'])
        editor.insert('1.0', current)
        scroll = ttk.Scrollbar(body, orient='vertical', command=editor.yview)
        editor.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        editor.pack(fill='both', expand=True)
        actions = ttk.Frame(body)
        actions.pack(fill='x', pady=(SPACING['sm'], SPACING['none']))

        def save_override():
            value = editor.get('1.0', 'end-1c').strip()
            kwargs = ({'hollmwood_rhythm_template': value} if is_rhythm else {field: value})
            stage_config.put(project, self.stage, **kwargs)
            self.state.configure(text=title + '已保存；下一次 HOLLMWOOD 创作将使用此规则。')
            window.destroy()

        def restore_default():
            kwargs = ({'hollmwood_rhythm_template': ''} if is_rhythm else {field: ''})
            stage_config.put(project, self.stage, **kwargs)
            editor.delete('1.0', 'end')
            editor.insert('1.0', default)
            self.state.configure(text=title + '已恢复内置默认规则。')

        PrimaryButton(actions, text='保存规则', width=12,
                      command=save_override).pack(side='left')
        SecondaryButton(actions, text='恢复内置默认', width=14,
                        command=restore_default).pack(side='left', padx=(SPACING['sm'], SPACING['none']))
        SecondaryButton(actions, text='取消', width=12,
                        command=window.destroy).pack(side='right')
        return window

    def build_workflow_coordinator(self, pad, parent=None):
        """受控统筹入口；阶段勾选网格仍是唯一可编辑清单。"""
        import workflow_settings
        row = ttk.Frame(parent or self)
        row.pack(fill='x')
        ttk.Label(row, text='统筹 SKILL', style='Muted.TLabel', width=10).pack(side='left')
        names = list(workflow_settings.WORKFLOW_PRESETS) + ['浏览本地…', '不使用统筹']
        self.workflow_box = ttk.Combobox(row, textvariable=self.workflow_choice, state='readonly', width=18, values=names)
        self.workflow_box.pack(side='left', padx=(SPACING['xs'], SPACING['sm']))
        self.workflow_box.bind('<<ComboboxSelected>>', lambda event: self.choose_workflow())
        self.workflow_summary = ProgressLabel(row, text='自由模式')
        self.workflow_summary.pack(side='left', padx=(0, SPACING['sm']))
        ttk.Button(row, text='去填写', command=self.open_workflow_brief).pack(side='left')
        if self.stage != 'script':
            HintLabel(row, text='锁在剧本页采集简报时填写最顺').pack(side='left', padx=(SPACING['sm'], 0))

    def refresh_workflow(self):
        import workflow_settings
        workflow = stage_config.current_workflow(self.project())
        name = str(workflow.get('name') or '').strip()
        self.workflow_choice.set(name if name in workflow_settings.WORKFLOW_PRESETS else '不使用统筹')
        locks = stage_config.workflow_lock(self.project())
        if not name:
            self.workflow_summary.configure(text='自由模式')
            self.workflow_summary.unbind('<Button-1>')
            return
        preset = workflow_settings.WORKFLOW_PRESETS[name]
        missing = [item['label'] for item in preset.get('locks', ()) if not str(locks.get(item['key']) or '').strip()]
        deviation = stage_config.workflow_deviation_count(self.project(), preset)
        status = '锁未填齐，下游页面将使用各自默认值' if missing else '制作锁已填写'
        if deviation:
            status += ' · %d 个阶段已本地修改' % deviation
        self.workflow_summary.configure(text=status)
        if deviation:
            self.workflow_summary.bind('<Button-1>',
                                       lambda _event: self.show_workflow_differences(preset))
        else:
            self.workflow_summary.unbind('<Button-1>')

    def show_workflow_differences(self, preset):
        """偏离徽标只读展开，避免把用户本地勾选误当作可自动覆盖的数据。"""
        rows = stage_config.workflow_differences(self.project(), preset)
        changed = [(STAGE_NAMES.get(stage, stage), values) for stage, values in rows.items()
                   if values['current'] != values['suggested']]
        if not changed:
            return
        lines = ['统筹建议与当前阶段勾选：']
        for label, values in changed:
            lines.append('%s\n当前：%s\n建议：%s' %
                         (label, '、'.join(values['current']) or '空',
                          '、'.join(values['suggested']) or '空'))
        messagebox.showinfo('本地修改明细', '\n\n'.join(lines), parent=self.winfo_toplevel())

    def workflow_apply_dialog(self, choice, preset, switching):
        """逐阶段选择“套用／保留”；默认不重写已有勾选。"""
        import workflow_settings
        old = stage_config.current_workflow(self.project())
        rows = stage_config.workflow_differences(self.project(), preset)
        old_preset = workflow_settings.WORKFLOW_PRESETS.get(str(old.get('name') or ''), {})
        dialog = tk.Toplevel(self); dialog.title('切换统筹' if switching else '套用统筹建议')
        dialog.transient(self.winfo_toplevel()); dialog.resizable(True, True)
        body = ttk.Frame(dialog, padding=12); body.pack(fill='both', expand=True)
        DescriptionBlock(body, text=('逐项选择是否套用建议；已有阶段勾选默认保留，不会自动覆盖。'
                                     if switching else '仅显式空阶段默认勾选套用；已有勾选保持不覆盖。')).pack(fill='x')
        choices = {}
        for stage, values in rows.items():
            current, suggested = values['current'], values['suggested']
            # 首次套用仅可填补显式空阶段；切换时才由用户逐项决定是否覆盖。
            may_apply = switching or not current
            value = tk.BooleanVar(value=not current)
            choices[stage] = value
            old_suggested = old_preset.get('stage_skills', {}).get(stage, ())
            label = '%s｜旧建议：%s｜当前：%s｜新建议：%s' % (
                STAGE_NAMES.get(stage, stage), '、'.join(old_suggested) or '无',
                '、'.join(current) or '空', '、'.join(suggested) or '空')
            ttk.Checkbutton(body, text=label + '（套用）', variable=value,
                            state='normal' if may_apply else 'disabled').pack(
                                anchor='w', pady=(SPACING['xs'], 0))
        actions = ttk.Frame(body); actions.pack(fill='x', pady=(SPACING['md'], 0))
        def apply_selected():
            workflow = dict(old)
            workflow.update({'name': choice, 'skill_ref': preset['package'],
                             'lock': dict(old.get('lock') or {})})
            # 逐项“套用”是用户显式决定；调用既有阶段保存入口，不碰未选项。
            for stage, value in choices.items():
                if value.get() and (switching or not rows[stage]['current']):
                    stage_config.put(self.project(), stage, skills=rows[stage]['suggested'])
            stage_config.put_workflow(self.project(), workflow)
            dialog.destroy(); self.refresh_workflow()
            self.state.configure(text='统筹已更新；未选择的阶段勾选已保留。')
        PrimaryButton(actions, text='确认套用', command=apply_selected).pack(side='left')
        SecondaryButton(actions, text='全部保留', command=lambda: (dialog.destroy(), self.refresh_workflow())).pack(side='left', padx=(SPACING['sm'], 0))
        dialog.update_idletasks()
        dialog.geometry('+%d+%d' % (self.winfo_rootx() + 30, self.winfo_rooty() + 30))
        return dialog

    def choose_workflow(self):
        import workflow_settings
        choice = self.workflow_choice.get()
        if choice == '不使用统筹':
            stage_config.clear_workflow(self.project()); self.refresh_workflow(); return
        if choice == '浏览本地…':
            self.workflow_choice.set('不使用统筹'); self.state.configure(text='本轮仅支持受控登记的统筹 SKILL。'); return
        preset = workflow_settings.WORKFLOW_PRESETS.get(choice)
        if not preset: return
        previous = str(stage_config.current_workflow(self.project()).get('name') or '')
        self.workflow_apply_dialog(choice, preset, switching=bool(previous and previous != choice))

    def open_workflow_brief(self):
        if self.stage != 'script':
            self.state.configure(text='请先去 01 剧本准备填写制作锁。'); return
        opener = getattr(self.desktop, 'open_brief_creation_form', None)
        if callable(opener): opener()

    def build_flow_skill(self, parent):
        """三段式 SKILL 面板：操作栏、固定列勾选列表、说明区。"""
        self.flow_skill_row = None
        self.registered_boxes = {}          # 注册 SKILL id → 勾选框，供删除后立即移除
        self.skill_controls = []
        self._skill_layout_job = None
        self._flow = STAGE_FLOW.get(self.stage)
        if not self._flow and not self.skills:
            return None
        # 区域一：操作栏只放标签与 SKILL 操作下拉，不与勾选框混排。
        self.skill_action_row = ttk.Frame(parent)
        self.skill_action_row.pack(fill='x', pady=(SPACING['none'], SPACING['xs']))
        self.flow_skill_label = ttk.Label(self.skill_action_row, text='SKILL', style='Muted.TLabel', width=10)
        self.flow_skill_label.pack(side='left')
        self.skill_action = tk.StringVar(value=MANAGE_ALL)
        action = ttk.Combobox(self.skill_action_row, textvariable=self.skill_action,
                              values=(MANAGE_ALL, MANAGE_NONE, MANAGE_ADD, MANAGE_DELETE), state='readonly', width=12)
        action.pack(side='left', padx=(SPACING['xs'], SPACING['sm']))
        action.bind('<<ComboboxSelected>>', lambda event: self.choose_skill_action())
        # 外部包的引擎说明从独占行收进 SKILL 操作行，保持表单行高与上方栏一致。
        self.external_package_hint = HintLabel(self.skill_action_row, text='')
        self.external_package_hint.pack(side='left', padx=(SPACING['sm'], SPACING['none']))
        # 区域二：所有勾选项独占列表容器；注册表顺序是主顺序，不再按自然宽度散排。
        count = len(self.skills)
        self.skill_list_outer = ttk.Frame(parent)
        self.skill_list_outer.pack(fill='x', pady=(SPACING['none'], SPACING['xs']))
        self.skill_scrollbar = None
        if self.uses_skill_scrollbar(count):
            self.skill_canvas = tk.Canvas(self.skill_list_outer, height=156, highlightthickness=0, bd=0,
                                          bg=COLORS['background_card'])
            self.skill_scrollbar = ttk.Scrollbar(self.skill_list_outer, orient='vertical', command=self.skill_canvas.yview)
            self.skill_canvas.configure(yscrollcommand=self.skill_scrollbar.set)
            self.skill_scrollbar.pack(side='right', fill='y')
            self.skill_canvas.pack(side='left', fill='x', expand=True)
            self.flow_skill_row = ttk.Frame(self.skill_canvas)
            self._skill_canvas_window = self.skill_canvas.create_window((0, 0), window=self.flow_skill_row, anchor='nw')
            self.flow_skill_row.bind('<Configure>', lambda event: self.skill_canvas.configure(scrollregion=self.skill_canvas.bbox('all')))
            self.skill_canvas.bind('<Configure>', lambda event: self.skill_canvas.itemconfigure(self._skill_canvas_window,
                                                                                                  width=event.width))
        else:
            self.skill_canvas = None
            self.flow_skill_row = ttk.Frame(self.skill_list_outer)
            self.flow_skill_row.pack(fill='x')

        for item in self.skills:
            var = tk.BooleanVar(value=True)
            self.vars[item.name] = var
            # 每个包里的入口通常都叫 SKILL.md；从路径取名会把所有项降级为
            # 「自定义技能」。注册表 displayName 才是已解析的用户可见名称。
            shown = registered_skill_checkbox_label(item)
            box = ttk.Checkbutton(self.flow_skill_row, text=shown, width=28,
                                  variable=var, command=self.save_and_refresh_notes)
            box._skill_full_name = shown
            box._skill_path = self.resolved_skill_path(item.path)
            self.registered_boxes[item.name] = box
            self.add_skill_control(box)
        if not self.skills:
            self.empty = HintLabel(self.flow_skill_row, text='这一阶段还没有附加 SKILL')
            self.add_skill_control(self.empty)
        self.schedule_skill_layout()
        return self.flow_skill_row

    @staticmethod
    def resolved_skill_path(path):
        """用同一把尺比较工作流设置路径与注册表路径。"""
        try:
            return str(Path(path).resolve())
        except (OSError, TypeError, ValueError):
            return str(path or '')

    def registered_skill_paths(self):
        """当前页面已由注册表渲染的 SKILL.md 绝对路径。"""
        return {self.resolved_skill_path(item.path) for item in self.skills
                if self.resolved_skill_path(item.path)}

    def add_skill_control(self, widget):
        """登记一项列表勾选控件，并为被截断的名称保留悬停全文。"""
        self.skill_controls.append(widget)
        full = getattr(widget, '_skill_full_name', '')
        if full and len(str(full)) > 26:
            Tooltip(widget, full)
        self.schedule_skill_layout()
        return widget

    def skill_label(self, label, limit=26):
        """固定勾选框宽度；过长名称显示省略号，悬停仍可看全文。"""
        text = str(label or '')
        return text if len(text) <= limit else text[:max(1, limit - 3)] + '...'

    @staticmethod
    def uses_skill_scrollbar(count):
        """超过十项时切换为单列滚动列表，避免把最后一项挤出页面。"""
        return count > 10

    def schedule_skill_layout(self, _event=None):
        """固定列布局不依赖容器宽度，创建控件后立即排入本区域。"""
        self.layout_skill_controls()

    def layout_skill_controls(self):
        """小列表用两列固定网格；长列表使用单列滚动容器。"""
        self._skill_layout_job = None
        if self.flow_skill_row is None:
            return
        for widget in self.skill_controls:
            widget.grid_forget()
        columns = 1 if self.skill_scrollbar is not None else 2
        for widget in self.skill_controls:
            index = self.skill_controls.index(widget)
            row, column = divmod(index, columns)
            widget.grid(row=row, column=column, sticky='w', padx=(0, SPACING['sm']), pady=(0, SPACING['xs']))
        for column in range(columns):
            self.flow_skill_row.grid_columnconfigure(column, weight=1)

    def choose_skill_action(self):
        """唯一阶段网格的批量操作；旧引擎档清单只读保留，不再形成第二套勾选。"""
        picked = self.skill_action.get()
        if picked == MANAGE_DELETE:
            try:
                return self.delete_checked_skills()
            finally:
                # 删除是一次性动作，不能让下拉框停在危险选项上。
                self.skill_action.set(MANAGE_ALL)
        if picked == MANAGE_ADD:
            self.skill_action.set(MANAGE_ALL)
            return self.add_skill_from_file()
        if picked == MANAGE_ALL:
            return self.check_all_skills(True)
        if picked == MANAGE_NONE:
            return self.check_all_skills(False)
        return ''

    def add_skill_from_file(self):
        """显式导入单个 SKILL 到本阶段的受控注册目录。"""
        source = filedialog.askopenfilename(parent=self.winfo_toplevel(), title='新增 SKILL',
                                            filetypes=[('SKILL', ('*.skill.md', 'SKILL.md')), ('全部文件', '*.*')])
        if not source:
            return None
        target_dir = self.registry._stage_directory_for(self.stage)
        if target_dir is None:
            self.state.configure(text='新增 SKILL 失败：未找到本阶段注册目录')
            return None
        target = target_dir / Path(source).name
        try:
            shutil.copy2(source, target)
            self.registry.scan(force=True)
            self.skills = list(self.registry.getByStage(self.stage))
            for child in self.skill_content.winfo_children():
                child.destroy()
            self.vars = {}
            self.build_flow_skill(self.skill_content)
            self.load()
            self.state.configure(text='已新增 SKILL：' + target.name)
            self.refresh_notes(str(target))
            return target
        except OSError as exc:
            self.state.configure(text='新增 SKILL 失败：' + str(exc))
            return None

    def check_all_skills(self, value=True):
        """全选／取消全选只作用于唯一的阶段 SKILL 网格。"""
        for var in self.vars.values():
            var.set(bool(value))
        self.save()
        self.refresh_external_package_hint()
        return self.selected()

    def save_and_refresh_notes(self):
        """注册 SKILL 勾选变化后，说明目录与勾选状态同步。"""
        entry = self.save()
        self.refresh_notes()
        self.refresh_external_package_hint()
        return entry

    def _referenced_skills(self, items):
        """只读检查当前项目配置是否仍引用将删除的注册 id。"""
        project = self.project()
        config = Path(project) / 'skill_config.json' if project else None
        data = read_json(config) if config and config.is_file() else {}
        wanted = {item.name for item in items}
        return sorted(name for name in wanted if name in str(data))

    def delete_checked_skills(self):
        """仅回收程序自带 skills/ 下已勾选的 .skill.md，绝不改项目配置。"""
        program = Path(__file__).resolve().parent
        skills_root = (program / 'skills').resolve()
        selected = [item for item in self.skills if self.vars.get(item.name) and self.vars[item.name].get()]
        paths = []
        for item in selected:
            path = Path(getattr(item, 'path', '')).resolve()
            if path.suffixes[-2:] == ['.skill', '.md'] and path.is_file() and path.is_relative_to(skills_root):
                paths.append((item, path))
        if not paths:
            messagebox.showinfo(TITLE, '没有可删除的程序 SKILL。', parent=self.winfo_toplevel())
            return []
        refs = self._referenced_skills([item for item, _path in paths])
        names = '、'.join(item.displayName or item.name for item, _path in paths)
        reference_notice = ('\n\n以下 SKILL 仍被当前项目 skill_config.json 引用：' + '、'.join(refs)
                            + '。继续删除后，该配置会在下次读取时按既有失效项规则清理。') if refs else ''
        if not messagebox.askyesno(TITLE, '将把以下 SKILL 移入程序回收站，是否继续？\n' + names + reference_notice,
                                   parent=self.winfo_toplevel()):
            return []
        records = recycle_paths(program, [path for _item, path in paths], '阶段配置删除 SKILL')
        if not records:
            self.state.configure(text='SKILL 未删除：回收服务未返回记录')
            return []
        removed = {item.name for item, _path in paths}
        self.skills = [item for item in self.skills if item.name not in removed]
        for name in removed:
            box = self.registered_boxes.pop(name, None)
            if box is not None:
                box.destroy()
            self.vars.pop(name, None)
        self.skill_controls = [widget for widget in self.skill_controls if widget.winfo_exists()]
        self.registry.scan(force=True)
        self.refresh_notes()
        self.refresh_external_package_hint()
        self.schedule_skill_layout()
        self.state.configure(text='已移入回收站：' + names)
        return records

    def choose_model(self):
        """模型那一格挑了一项：挑的是「+ 添加模型…」就去模型管理里加一条。"""
        if self.model.get() != ADD_MODEL_LABEL:
            self._picked = self.model.get()
            entry = self.save()
            self.show_desktop_route_notice()
            self.refresh_external_package_hint()
            return entry
        self.model.set(self._picked or self.model_label(model_router.AUTO))
        return self.open_model_manager()

    def provider_labels(self):
        return [label for _model_id, label in self.groups.get(self.provider.get(), [])]

    def choose_provider(self):
        """先选供应商，再在右侧只显示该供应商的具体模型。"""
        labels = self.provider_labels()
        self.models.configure(values=labels + [ADD_MODEL_LABEL])
        if labels:
            self.model.set(labels[0])
            self._picked = labels[0]
            entry = self.save()
            self.show_desktop_route_notice()
            self.refresh_external_package_hint()
            return entry
        return None

    def show_desktop_route_notice(self):
        """模型由用户主动改选后，才按需查询本机优先路由；不改变保存或执行。"""
        notice = ''
        if self._flow:
            try:
                import workflow_settings
                notice = workflow_settings.desktop_route_notice(
                    self.project(), self._flow, self.model_id(), pool_records(self.desktop))
            except Exception:
                notice = ''
        self.route_hint.configure(text=notice)
        return notice

    def set_model(self, model):
        """按已保存的 id 同步两级下拉；手填的本地 id 也必须原样保留。"""
        wanted = str(model or model_router.AUTO)
        for provider, options in self.groups.items():
            for model_id, label in options:
                if model_id == wanted:
                    self.provider.set(provider)
                    self.models.configure(values=[item_label for _item_id, item_label in options] + [ADD_MODEL_LABEL])
                    self.model.set(label)
                    self._picked = label
                    return wanted
        if wanted == model_router.AUTO:
            return model_router.AUTO
        # 用户手写的本地模型尚未登记到模型池时，不替用户丢掉配置。
        provider = '自定义'
        self.groups.setdefault(provider, []).append((wanted, wanted))
        self.providers.configure(values=list(self.groups))
        self.provider.set(provider)
        self.models.configure(values=[wanted, ADD_MODEL_LABEL])
        self.model.set(wanted)
        self._picked = wanted
        return wanted

    def open_model_manager(self):
        """「+ 添加模型…」：模型池只有这一扇门（模型管理），加完这里就多一个选项。"""
        pet = pet_of(self.desktop)
        if pet is None:
            self.state.configure(text='模型管理没打开：这一版没接上三虎')
            return ''
        import pet_models_ui
        try:
            result = pet_models_ui.open_manager(pet)
        except Exception as exc:
            self.state.configure(text='模型管理没打开：' + str(exc))
            return ''
        self.state.configure(text='模型管理已打开：加完一条，这里就多一个选项')
        return result

    def manual(self):
        """项目里这一阶段手动配的那一档（没配过就是空的一份）。"""
        try:
            return manual_entry(self.project(), self.stage)
        except Exception:
            return {}

    # ── 接口与 SKILL 说明（第 29 期第 1／2／4 条） ──────────────────────────
    def build_interfaces(self, pad, parent=None):
        """「接口」那一行：点开还是原来那个窗口，只是不再每页各放一份。"""
        self.interface_buttons = []
        for label, opener in interfaces_of(self.desktop, self.stage, self.function):
            if not self.interface_buttons:
                line = ttk.Frame(parent or self)
                line.pack(fill='x', pady=(pad, 0))
                ttk.Label(line, text='接口', style='Muted.TLabel').pack(side='left')
            button = SecondaryButton(line, text=label,
                                     command=lambda f=opener: self.open_interface(f))
            button.pack(side='left', padx=(SPACING['xs'], SPACING['none']))
            self.interface_buttons.append(button)
        return self.interface_buttons

    def open_interface(self, opener):
        """点接口按钮：出错就写在面板的提示行上，不往用户脸上抛。"""
        try:
            result = opener()
        except Exception as exc:
            self.state.configure(text='接口没打开：' + str(exc))
            return None
        self.state.configure(text='接口已打开')
        return result

    def build_notes(self, pad):
        """左侧目录、右侧正文：选择 SKILL 后在同一行阅读说明。"""
        self.note_list = None
        self.note_text = None
        self.note_items = self.note_entries()
        if not self.note_items:
            return None
        box = ttk.LabelFrame(self, text='技能说明', padding=pad)
        box.pack(side='bottom', fill='both', expand=True, pady=(pad, 0))
        # LabelFrame 默认会按子控件的请求高度收缩；锁定其几何传播后再按面板
        # 剩余高度分配，拖动阶段配置窗口才不会留下空白而说明区仍停在 12 行。
        box.grid_propagate(False)
        # 说明框占用面板剩余空间：窗口放大时目录和正文一起变高，优先露出更多 SKILL。
        box.columnconfigure(1, weight=1)
        box.rowconfigure(0, weight=1)
        height = 5 if self.compact else 12
        self.note_list = tk.Listbox(box, height=height, width=18, exportselection=False,
                                    activestyle='none', font=FONTS['caption'])
        self.note_list.grid(row=0, column=0, sticky='ns')
        self.note_list.bind('<<ListboxSelect>>', lambda event: self.show_note())
        self.note_list_bar = ttk.Scrollbar(box, orient='vertical', command=self.note_list.yview)
        self.note_list_bar.grid(row=0, column=1, sticky='ns', padx=(0, pad))
        self.note_list.configure(yscrollcommand=self.note_list_bar.set)
        body = ttk.Frame(box)
        body.grid(row=0, column=2, sticky='nsew')
        box.columnconfigure(2, weight=1)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)
        bar = ttk.Scrollbar(body, orient='vertical')
        bar.grid(row=0, column=1, sticky='ns')
        self.note_text = tk.Text(body, height=height, wrap='word', relief='flat', bg=COLORS['background_card'],
                                 fg=COLORS['text_primary'], font=FONTS['caption'], padx=SPACING['sm'], pady=SPACING['xs'],
                                 yscrollcommand=bar.set)
        self.note_text.grid(row=0, column=0, sticky='nsew')
        bar.configure(command=self.note_text.yview)
        self.note_text.configure(state='disabled')

        def resize_note_rows(event):
            """按说明框实际高度换算可见行数，窗口拖拽时尽可能多显示目录。"""
            rows = max(1, (event.height - pad * 2) // 15)
            if int(self.note_list.cget('height')) != rows:
                self.note_list.configure(height=rows)
                self.note_text.configure(height=rows)

        box.bind('<Configure>', resize_note_rows, add='+')
        self._note_box_top = None

        def place_note_box(event=None):
            # 先借 pack 得到上方控件的实际底边，再交给 place 占据余下区域。
            # 这样底部说明区不会因自身的 Text/Listbox 请求高度而停止伸缩。
            if self._note_box_top is None:
                top = box.winfo_y()
                if top <= 0:
                    self.after_idle(place_note_box)
                    return
                self._note_box_top = top
            bottom_height = self.bottom_bar.winfo_height() if hasattr(self, 'bottom_bar') else 0
            box.place(x=0, y=self._note_box_top, relwidth=1,
                      height=max(1, self.winfo_height() - self._note_box_top - bottom_height))

        box.bind('<Map>', place_note_box, add='+')
        self.bind('<Configure>', place_note_box, add='+')
        self.bottom_bar.bind('<Configure>', place_note_box, add='+')
        self.refresh_notes()
        return self.note_list

    def note_entries(self):
        """说明目录与唯一的阶段勾选网格保持一致。"""
        return [('registered', item) for item in self.skills]

    def refresh_notes(self, preferred_path=None):
        """重新生成说明目录；新增 SKILL 后立即选中并显示其 Markdown。"""
        if self.note_list is None:
            return []
        old = self.current_note()
        old_path = old[2] if old and old[0] == 'workflow' else None
        target = str(preferred_path or old_path or '')
        self.note_items = self.note_entries()
        self.note_list.delete(0, 'end')
        selected = 0
        for index, entry in enumerate(self.note_items):
            label = (entry[1].displayName or entry[1].name
                     if entry[0] == 'registered' else entry[1])
            self.note_list.insert('end', chinese_skill_display(label))
            if entry[0] == 'workflow' and str(entry[2]) == target:
                selected = index
        if self.note_items:
            self.note_list.selection_set(selected)
        self.show_note()
        return self.note_items

    def current_skill(self):
        """说明框这会儿在讲哪一个 SKILL（列表还选着的话就是它，否则第一条）。"""
        entry = self.current_note()
        return entry[1] if entry and entry[0] == 'registered' else None

    def current_note(self):
        """说明框当前选中的注册 SKILL 或工作流 SKILL。"""
        if self.note_list is None:
            return None
        picked = self.note_list.curselection()
        index = int(picked[0]) if picked else 0
        return self.note_items[index] if 0 <= index < len(self.note_items) else None

    def show_note(self):
        """把选中的那个 SKILL 的 Markdown 说明排进右边那块只读文本框。"""
        if self.note_text is None:
            return ''
        entry = self.current_note()
        body = (note_text(entry[1]) if entry and entry[0] == 'registered'
                else workflow_note_text(entry[1], entry[2]) if entry else '')
        self.note_text.configure(state='normal')
        self.note_text.delete('1.0', 'end')
        self.note_text.insert('1.0', body)
        self.note_text.configure(state='disabled')
        if entry and entry[0] == 'registered':
            box = self.registered_boxes.get(entry[1].name)
            if box is not None:
                box.focus_set()
        return body

    # ── 读写 ────────────────────────────────────────────────────────────────
    def project(self):
        project = desktop_project(self.desktop)
        if project is None:
            raise ValueError('请先选择项目')
        return project

    def model_id(self, text=None):
        """下拉框里那一格 → 模型 id（「自动」与认不出来的文案都原样退回）。"""
        return model_pool.id_of_label(self.model.get() if text is None else text, self.choices)

    def model_label(self, model=None):
        """模型 id → 下拉框那一格的文案（池里的显示名，池里没有就照原样念）。"""
        return model_pool.label_of(model, pool_records(self.desktop))

    def refresh_models(self):
        """模型池变了：换掉选项，当前这一档尽量留住（不在池里了就退回「自动」）。"""
        current = self.model_id()
        self.choices = model_choices(self.desktop, self.stage)
        self.labels = [label for _model_id, label in self.choices]
        self.groups = grouped_model_choices(self.desktop, self.stage)
        self.providers.configure(values=list(self.groups))
        kept = [model_id for model_id, _label in self.choices if model_id == current]
        self.set_model(kept[0] if kept else model_router.AUTO)
        self.refresh_external_package_hint()
        return self.choices

    def entry(self, project=None):
        return stage_config.get(project or self.project(), self.stage, registry=self.registry)

    def drop_mismatched(self, model, skills=None):
        """只撤跨阶段误用的页面专用生产模型，API 模型一律保留。

        API 统一配置保存的模型在所有阶段都可被人工选择；能力标签是自动路由的提示，
        不是删除用户阶段配置的依据。只有首帧／资产等页面专用生产模型被套到别的
        阶段时，才改回「自动」。
        """
        text = str(model or '').strip()
        if not text or text == model_router.AUTO:
            return text
        if not stage_models.belongs_to_other_stage(self.stage, text):
            return text
        try:
            stage_config.put(self.project(), self.stage, model=model_router.AUTO,
                             skills=skills if skills is not None else self.selected(),
                             registry=self.registry)
        except Exception:
            return text                     # 写不回去就先照旧摆着，别把面板搞崩
        self.state.configure(text='「%s」是其他页面的专用生产模型，已改回「自动」。'
                                  % self.model_label(text))
        return ''

    def load(self):
        """按项目里存的配置摆好勾选与模型（没存过就是「自动」＋全部勾上）。

        第 58 期第 5 条：存的模型跟这一阶段的功能对不上就自动撤掉（见 drop_mismatched）。
        """
        try:
            entry = self.entry()
        except Exception:
            return None
        kept = self.drop_mismatched(entry.get('model') or model_router.AUTO, entry.get('skills'))
        self.set_model(kept or model_router.AUTO)
        if self.stage in stage_config.HOLLMWOOD_STAGES:
            self.hollmwood_enabled_var.set(bool(entry.get(stage_config.HOLLMWOOD_ENABLED, True)))
        chosen = set(entry.get('skills') or [])
        for name, var in self.vars.items():
            var.set(name in chosen)
        self.show_presets(self.preset.get())
        self.refresh_workflow()
        manual = self.manual()
        if manual.get('model') or manual.get('skill'):
            # 第 36 期第 4 条：手动配过就把这一档说出来，别让人猜「我配的生效了没有」。
            self.state.configure(text='手动：' + (manual.get('model') or '模型按上方选择')
                                 + ' · ' + (Path(manual['skill']).name if manual.get('skill') else 'SKILL 按上方勾选'))
        self.refresh_notes()
        self.refresh_external_package_hint()
        return entry

    def selected(self):
        return [item.name for item in self.skills if self.vars.get(item.name) is not None
                and self.vars[item.name].get()]

    def selected_skill_items(self):
        """本面板已勾选的注册 SKILL；只读其元数据，不重新扫描目录。"""
        return [item for item in self.skills if self.vars.get(item.name) is not None
                and self.vars[item.name].get()]

    def refresh_external_package_hint(self):
        """把外部包/API 的兼容性提示同步到 SKILL 区状态行。"""
        hint = external_package_api_hint(self.selected_skill_items(), self.model_id())
        self.external_package_hint.configure(text=hint)
        return hint

    def save(self, quiet=True):
        """把面板上的选择写进 project.skillConfig[stage]（＝skill_config.json）。"""
        project = self.project()
        names = self.selected()
        kwargs = {}
        if self.stage in stage_config.HOLLMWOOD_STAGES:
            kwargs['hollmwood_enabled'] = self.hollmwood_enabled_var.get()
        entry = stage_config.put(project, self.stage, model=self.model_id(),
                                 skills=names, registry=self.registry, **kwargs)
        if not quiet:
            self.state.configure(text='已保存：%d 个 SKILL' % len(names))
        return entry

    def confirm(self):
        """保存当前页面的阶段配置，再关闭该阶段配置窗口。"""
        entry = self.save(quiet=False)
        launcher = getattr(self, 'launcher_button', None)
        if launcher is not None:
            try:
                if launcher.winfo_exists():
                    launcher.configure(text=stage_button_label(self.desktop, self.stage))
            except tk.TclError:
                pass
        if self.stage == 'script':
            refresh = getattr(self.desktop, 'refresh_script_chat_for_selected_model', None)
            if callable(refresh):
                refresh()
        self.winfo_toplevel().destroy()
        return entry

    def reset_defaults(self):
        """经确认后仅恢复本阶段模型与 SKILL 默认值；统筹和制作锁保持不变。"""
        if not messagebox.askyesno(TITLE, '恢复本阶段的默认模型和 SKILL？\n统筹与制作锁不会改变。',
                                   parent=self.winfo_toplevel()):
            return None
        entry = stage_config.reset(self.project(), self.stage, registry=self.registry)
        self.load()
        self.state.configure(text='已恢复本阶段默认配置；统筹与制作锁未改变。')
        return entry

    def run_preset_action(self):
        """执行预设操作下拉框当前选择，并在操作后回到占位项。"""
        action = str(self.preset_action.get() or '').strip()
        actions = {
            '保存为预设': self.save_preset,
            '删除预设': self.drop_preset,
            '重命名预设': self.rename_preset,
            '复制本预设到其他页面': self.share_preset_copy,
        }
        callback = actions.get(action)
        if callback is None:
            self.state.configure(text='请先选择预设操作')
            return None
        try:
            return callback()
        finally:
            self.preset_action.set('选择操作')

    # ── 跨页面共享预设 ────────────────────────────────────────────────────
    def share_preset_copy(self):
        """把当前页面的预设复制到用户勾选的页面，不再把预设混成全局共用一份。"""
        name = str(self.preset.get() or '').strip()
        if not name or name == PRESET_PLACEHOLDER:
            self.state.configure(text='先在上方选一个预设')
            return None
        dialog = tk.Toplevel(self.winfo_toplevel())
        dialog.title('复制预设：选择共享页面')
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        DescriptionBlock(dialog, text='将预设「%s」复制到以下页面：\n各页面获得独立副本，之后互不影响。' % name).pack(
            anchor='w', padx=SPACING['lg'], pady=(SPACING['md'], SPACING['sm']))
        body = ttk.Frame(dialog)
        body.pack(fill='both', expand=True, padx=SPACING['lg'])
        choices = []
        for stage in STAGE_NAMES:
            if stage == self.stage:
                continue
            variable = tk.BooleanVar(value=False)
            ttk.Checkbutton(body, text=STAGE_NAMES.get(stage, stage), variable=variable).pack(anchor='w', pady=2)
            choices.append((stage, variable))

        def submit():
            targets = [stage for stage, variable in choices if variable.get()]
            if not targets:
                self.state.configure(text='未选择共享页面，预设仍只属于当前页面')
                dialog.destroy()
                return
            try:
                copied = stage_config.share_preset(name, self.stage, targets,
                                                    program=program_of(self.desktop))
            except Exception as exc:
                self.state.configure(text='共享预设失败：' + str(exc))
            else:
                labels = '、'.join(STAGE_NAMES.get(stage, stage) for stage in copied)
                self.state.configure(text='已复制预设「%s」到：%s' % (name, labels))
            dialog.destroy()

        buttons = ttk.Frame(dialog)
        buttons.pack(fill='x', padx=SPACING['lg'], pady=SPACING['md'])
        SecondaryButton(buttons, text='取消', command=dialog.destroy).pack(side='right')
        PrimaryButton(buttons, text='共享到所选页面', command=submit).pack(side='right', padx=(SPACING['none'], SPACING['sm']))
        dialog.resizable(False, False)
        return dialog

    # ── 预设 ────────────────────────────────────────────────────────────────
    def preset_names(self):
        try:
            return sorted(str(name) for name in stage_config.presets(program_of(self.desktop), self.stage))
        except Exception:
            return []

    def show_presets(self, picked=''):
        """把预设下拉框的选项与选中的那一份对齐（第 62 期任务 1／4：三处调用合成一处）。

        存／删／改名之后都要做同一件事，各写一遍迟早走偏（下拉框里留着一份已经不存在的
        预设，或者删完了还选着它）。
        """
        names = self.preset_names()
        self.presets.configure(values=[PRESET_PLACEHOLDER] + names)
        self.preset.set(picked if picked in names else PRESET_PLACEHOLDER)
        return names

    def save_preset(self):
        """存一份预设；默认填当前预设，保留同名即可覆盖它。"""
        current = str(self.preset.get() or '').strip()
        if current == PRESET_PLACEHOLDER:
            current = ''
        name = simpledialog.askstring('保存为预设', '预设名称（同名将覆盖）：', initialvalue=current,
                                      parent=self.winfo_toplevel())
        name = str(name or '').strip()
        if not name:
            return ''
        replaced = name in self.preset_names()
        stage_config.save_preset(name, self.model_id(), self.selected(),
                                 stage=self.stage, program=program_of(self.desktop))
        self.show_presets(name)
        self.state.configure(text=('已覆盖预设：' if replaced else '已存预设：') + name)
        return name

    def drop_preset(self):
        """删掉下拉框里挑中的那份预设（第 62 期任务 1）；没挑就明说一句，别猜。"""
        name = str(self.preset.get() or '').strip()
        if not name or name == PRESET_PLACEHOLDER:
            self.state.configure(text='先在下拉框里挑一份预设，再删除')
            return ''
        if not stage_config.drop_preset(name, program_of(self.desktop), stage=self.stage):
            self.state.configure(text='没找到这份预设：' + name)
            self.show_presets()
            return ''
        self.show_presets()
        self.state.configure(text='已删除预设：' + name)
        return name

    def rename_preset(self):
        """给下拉框里挑中的那份预设改个名字（第 51 期第 4 条）。

        没挑就明说「先挑一份」；改完下拉框里那份跟着变成新名字，还选着它。
        """
        old = str(self.preset.get() or '').strip()
        if not old or old == PRESET_PLACEHOLDER:
            self.state.configure(text='先在下拉框里挑一份预设，再改名')
            return ''
        name = simpledialog.askstring('重命名预设', '把「%s」改成：' % old, initialvalue=old,
                                      parent=self.winfo_toplevel())
        name = ' '.join(str(name or '').split())
        if not name or name == old:
            return ''
        try:
            stage_config.rename_preset(old, name, program_of(self.desktop), stage=self.stage)
        except Exception as exc:
            self.state.configure(text='没改成：' + str(exc))
            return ''
        self.show_presets(name)
        self.state.configure(text='预设已改名：%s → %s' % (old, name))
        return name

    def apply_preset(self):
        name = str(self.preset.get() or '').strip()
        if not name or name == PRESET_PLACEHOLDER:
            return None
        entry = stage_config.apply_preset(self.project(), self.stage, name, registry=self.registry,
                                          program=program_of(self.desktop))
        self.load()
        self.state.configure(text='已套用预设：' + name)
        self.show_desktop_route_notice()
        return entry

    # ── 执行 ────────────────────────────────────────────────────────────────
    def context(self):
        """这一次执行的上下文：面板上选的那一档算「单次」覆盖。

        第 36 期第 4 条：手动配置里填了模型 ID 就它说了算（用户自己填的那个最具体）。
        """
        model = self.model_id()
        manual = self.manual()
        if manual.get('model'):
            model = manual['model']
        return stage_context(self.desktop, self.stage, self.function, {'model': model})

    def run(self):
        """跑勾上的 SKILL（第 54 期起不再挂按钮，留着当可编程入口）：校验 → 分层 → 跑 → 汇总。"""
        try:
            project = self.project()
        except Exception as exc:
            messagebox.showinfo(TITLE, str(exc), parent=self.winfo_toplevel())
            return None
        names = self.selected()
        if not names:
            messagebox.showinfo(TITLE, '先勾上要跑的 SKILL。', parent=self.winfo_toplevel())
            return None
        self.save()
        orch = build_orchestrator(self.desktop, project)
        run = orch.run(names, self.context())
        self.confirmed(orch, run)
        return self.report(run)

    def confirmed(self, orch, run):
        """付费 SKILL 合并确认：一个气泡问完，用户点头就接着做（免打扰时段只排队）。"""
        pending = list(run.get('pending') or [])
        if not pending:
            return []
        names = '、'.join(row.get('name') or row['skill'] for row in pending)
        window = self.winfo_toplevel()
        if any(row.get('queued') for row in pending):
            messagebox.showinfo(TITLE, '这几个要花钱的活先排着队（现在不打扰您）：%s' % names,
                                parent=window)
            return []
        if not messagebox.askyesno(TITLE, '这几个要花钱：%s\n\n现在做吗？' % names, parent=window):
            orch.confirm_all(False)
            return []
        orch.confirm_all(True)
        again = orch.run([row['skill'] for row in pending], self.context())
        run['retry'] = again
        run['text'] = str(run.get('text') or '') + '\n' + str(again.get('text') or '')
        return list(run['results'])

    def report(self, run):
        """这一批的收场分成三档（第 30 期第 7 条）：真做完的 ／ 要回页面按的 ／ 没成的。

        原先这里数的是 ok（＝编排器认的「不算失败」：done＋page＋input 三种），于是两个 SKILL
        全落在页面上时也报「成了 2 个」——用户看得莫名其妙。现在三档各数各的，下面那行写原因。
        """
        rows = list(run.get('results') or [])
        done = [row for row in rows if row.get('status') == skill_orchestrator.DONE]
        waiting = [row for row in rows
                   if row.get('status') in (skill_orchestrator.PAGE, skill_orchestrator.INPUT)]
        failed = [row for row in rows
                  if row.get('status') in (skill_orchestrator.FAILED, skill_orchestrator.MISSING)]
        self.state.configure(text='做完了 %d 个，%d 个要回页面按，没成 %d 个'
                                  % (len(done), len(waiting), len(failed)))
        self.reason.configure(text=waiting_reason(waiting))
        text = str(run.get('text') or '')
        status_of(self.desktop, text.splitlines()[0] if text else '')
        run_report(self.desktop, text)
        return run


def program_of(desktop):
    """这套程序装在哪儿：预设落在这个目录下。

    desktop.app 就是程序目录（真机上就是 漫剧制作助手\程序）；拿不到时退回
    stage_config 自己那个默认根，自检里因此可以喂一个临时目录进来。"""
    app = getattr(desktop, 'app', None)
    return app if app else None


def stage_context(desktop, stage, function=None, extra=None):
    """跑一个阶段用的上下文：两级模型覆盖（单次 ＞ 项目）。

    页面上的「手动制作XX」与三虎那边都走这一份；都是「自动」时路由器自己挑。"""
    from stage_execution_service import stage_context as _stage_context
    return _stage_context(desktop, stage, function, extra)


def panel_window_size(parent):
    """返回小于主界面的阶段配置窗口初始尺寸与上限。"""
    parent.update_idletasks()
    available_width = max(1, parent.winfo_width() - SPACING['xl'] * 2)
    available_height = max(1, parent.winfo_height() - SPACING['xl'] * 2)
    width = min(880, available_width)
    height = min(720, available_height)
    return width, height, available_width, available_height


def show(desktop, stage, function=None, launcher_button=None):
    """弹窗形式：页面上那颗「阶段配置」按钮走这里，只配它所在的那一个阶段。

    第 33 期第 3 条：抬头那个「阶段」下拉撤掉——每页都有自己的按钮了，再从面板里切到别的
    阶段只会让人分不清「我刚配的到底是哪一步」。
    """
    if desktop_project(desktop) is None:
        messagebox.showinfo(TITLE, '请先选择项目。', parent=getattr(desktop, 'win', None))
        return None
    stage = stage_for(stage)
    window = tk.Toplevel(getattr(desktop, 'win', None))
    window.title(panel_title(stage))
    parent = getattr(desktop, 'win', None)
    window.transient(parent or None)
    # 第 29 期第 2 条：面板里多了「接口」与「SKILL 说明」两块，窗口要能放大、也有个下限，
    # 说明文字才排得开（原先定死大小，MD 一长就被挤成一条）。
    window.resizable(True, True)
    if parent is not None:
        width, height, max_width, max_height = panel_window_size(parent)
        window.geometry('%dx%d' % (width, height))
        window.maxsize(max_width, max_height)
        window.minsize(min(560, max_width), min(420, max_height))
    else:
        window.geometry('880x720')
        window.minsize(560, 420)
    body = ttk.Frame(window, padding=SPACING['md'])
    body.pack(fill='both', expand=True)
    head = ttk.Frame(body)
    head.pack(fill='x', pady=(SPACING['none'], SPACING['sm']))
    ttk.Label(head, text=panel_title(stage), style='Tokens.Title.TLabel').pack(side='left')
    host = ttk.Frame(body)
    host.pack(fill='both', expand=True)
    panel = Panel(host, desktop, stage, function=function, compact=False)
    panel.launcher_button = launcher_button
    panel.pack(fill='both', expand=True)

    window.bind('<Escape>', lambda event: window.destroy())
    try:
        window.attributes('-topmost', True)
        # 延迟取消置顶也必须随窗口销毁撤销；复用阶段弹窗已有的登记器，
        # 避免窗口先关后 Tcl 再寻找这个 lambda。
        stage_models._schedule_popup_job(window, 1200,
                                         lambda: window.attributes('-topmost', False))
    except tk.TclError:
        # 弹窗已销毁时取消置顶无须提示，其他错误继续抛。
        pass
    return panel


def open_for_page(desktop, index=None, launcher_button=None):
    """给标题栏按钮用：按当前页找阶段，弹对应的面板。"""
    page = getattr(desktop, 'page_index', index)
    stage = stage_of_page(int(page or 0))
    if not stage:
        messagebox.showinfo(TITLE, '这一页没有制作阶段。', parent=getattr(desktop, 'win', None))
        return None
    return show(desktop, stage, launcher_button=launcher_button)
