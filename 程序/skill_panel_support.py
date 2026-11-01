"""skill_panel 的纯函数支撑：技能流、阶段/模型选择、状态与报告文本。

R1620（Q9-3）从 skill_panel.py 拆出；公开名由 skill_panel 按原名转发，调用方不变。
"""
import re
from pathlib import Path
import tkinter as tk
from tkinter import ttk
import model_pool
import model_router
import skill_notes
import skill_orchestrator
import skill_registry
import stage_config
import stage_models
import ui_plugin_registry
from pet_bus import STAGE_NAMES, read_json, stage_label as _bus_stage_label
from ui_tokens import CHAR_WIDTH, COLORS, SPACING


FLOW_STAGE = {'writing': 'script', 'storyboard': 'storyboard', 'assets': 'assets',
              'frames': 'keyframe', 'previs': 'previs', 'video_prompt': 'video',
              'audio': 'audio', 'final': 'final', 'edit': 'edit', 'delivery': 'delivery'}


EXTERNAL_PACKAGE_API_HINT = (
    '外部包总入口：桌面引擎可完整执行；API 仅传入入口。'
)


SKILL_FLOW_ORDER = ('script', 'storyboard', 'asset', 'firstframe', 'whitemodel',
                    'video', 'voice', 'subtitle', 'edit', 'qa', 'delivery')


MANUAL_NAME = '阶段手动配置.json'          # 手动配的那一档落在项目里（与自动档的 skill_config.json 分开）


# 还开着的面板：模型池变了一次就把它们的下拉框都刷一遍（不用重开窗口）。
_LIVE_PANELS = []


def register_live(panel):
    """登记一个已打开的阶段配置面板。"""
    _LIVE_PANELS.append(panel)
    return panel


def unregister_live(panel):
    """面板销毁后从活动名单移除（重复移除不报错）。"""
    try:
        _LIVE_PANELS.remove(panel)
    except ValueError:
        pass
    return panel


def refresh_all():
    """模型管理里加／改／删了一条之后调它一次：还开着的面板跟着换选项。"""
    live = []
    for panel in _LIVE_PANELS:
        try:
            if panel.winfo_exists():
                live.append(panel)
        except Exception:
            continue
    _LIVE_PANELS[:] = live
    for panel in live:
        try:
            panel.refresh_models()
        except Exception:
            continue
    return len(live)


class WrappingActionRow(ttk.Frame):
    """动作栏：一行放不下时换行，控件至少保留文字所需的请求宽度。

    与 ``responsive_ui.FlowBar`` 同一套换行思路，但这里是阶段配置内部使用，且**不改**
    子标签的 ``wraplength``（外部包提示必须保持单行免撑高操作栏）。
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._wrap_job = None
        self.bind('<Configure>', self._schedule_wrap, add='+')
        self.bind('<Destroy>', self._cancel_wrap, add='+')

    def _schedule_wrap(self, event=None):
        if self._wrap_job is None:
            self._wrap_job = self.after_idle(self._wrap)

    def _cancel_wrap(self, event=None):
        if event is not None and event.widget is not self:
            return
        job = self._wrap_job
        self._wrap_job = None
        if job is not None:
            try:
                self.after_cancel(job)
            except tk.TclError:
                pass

    def _wrap(self):
        self._wrap_job = None
        if not self.winfo_exists():
            return
        available = self.winfo_width()
        if available <= 1:
            available = self.master.winfo_width() if self.master is not None else 1
        if available <= 1:
            return
        available = max(1, int(available))
        gap = SPACING['xs']
        x = y = row_height = 0
        for child in self.winfo_children():
            if child.winfo_manager() == 'pack':
                child.pack_forget()
            width = min(available, max(1, child.winfo_reqwidth()))
            height = max(1, child.winfo_reqheight())
            if x and x + width > available:
                y += row_height + gap
                x = 0
                row_height = 0
            child.place(x=x, y=y, width=width, height=height)
            x += width + getattr(child, 'gap_after', gap)  # 下拉框后留更大间距，和下一个标签分开
            row_height = max(row_height, height)
        height = y + row_height
        if int(self.cget('height')) != height:
            self.configure(height=height)


class FormScrollMixin:
    """阶段配置表单主体的纵向滚动兜底；底栏与技能说明区留在滚动区之外。

    说明区继续按窗口余量伸缩，底栏固定在底部；窗口低到表单放不下时（800×460），
    主体出现滚动条，SKILL 勾选区可以滚到完整可见。
    """

    def _build_form_body(self):
        if not getattr(self, 'scroll', False):
            self.form_body = self
            return self
        self.form_view = ttk.Frame(self)
        self.form_view.pack(fill='x')
        self.form_canvas = tk.Canvas(self.form_view, highlightthickness=0, bd=0,
                                     bg=COLORS['background_primary'])
        self.form_scroll = ttk.Scrollbar(self.form_view, orient='vertical',
                                         command=self.form_canvas.yview)
        self.form_canvas.configure(yscrollcommand=self.form_scroll.set)
        self.form_canvas.pack(side='left', fill='x', expand=True)
        self.form_body = ttk.Frame(self.form_canvas)
        self._form_window = self.form_canvas.create_window((0, 0), window=self.form_body,
                                                           anchor='nw')
        self.form_body.bind('<Configure>', self._sync_form_view, add='+')
        self.form_canvas.bind('<Configure>', self._resize_form_view, add='+')
        return self.form_body

    def _sync_form_view(self, event=None):
        """按表单请求高度同步滚动区；内容放得下时收起滚动条。"""
        if event is not None and event.widget is not self.form_body:
            return
        if self.form_canvas is None or not self.form_canvas.winfo_exists():
            return
        if not self.form_canvas.winfo_ismapped():
            return
        content = max(1, self.form_body.winfo_reqheight())
        width = max(1, self.form_canvas.winfo_width())
        self.form_canvas.itemconfigure(self._form_window, width=width)
        viewport = max(1, self.form_canvas.winfo_height())
        self.form_canvas.configure(scrollregion=(0, 0, width, max(content, viewport)))
        if int(self.form_canvas.cget('height')) != content:
            self.form_canvas.configure(height=content)
        need_scroll = content > viewport + 1
        has_scroll = bool(self.form_scroll.winfo_manager())
        if need_scroll == has_scroll:
            return
        if need_scroll:
            self.form_scroll.pack(side='right', fill='y', before=self.form_canvas)
        else:
            self.form_scroll.pack_forget()

    def _resize_form_view(self, event):
        if event.widget is not self.form_canvas:
            return
        self.form_canvas.itemconfigure(self._form_window, width=max(1, event.width))
        self._sync_form_view()

    def _form_wheel(self, event):
        """滚动区放到不整屏时，鼠标滚轮滚表单而不是整页。"""
        if self.form_canvas is None or not self.form_canvas.winfo_exists():
            return None
        first, last = self.form_canvas.yview()
        if last - first >= 0.999:
            return None
        self.form_canvas.yview_scroll(-1 if getattr(event, 'delta', 0) > 0 else 1, 'units')
        return 'break'

    def _bind_form_wheel(self, widget=None):
        if self.form_canvas is None:
            return
        target = self.form_body if widget is None else widget
        try:
            target.bind('<MouseWheel>', self._form_wheel, add='+')
        except tk.TclError:
            return
        for child in target.winfo_children():
            self._bind_form_wheel(child)


def skill_order(name):
    """一个 SKILL 在流程里的位置：先按功能分组（名前缀），同组再按名字（第 59 期第 6 条）。"""
    text = str(name or '').lower()
    for index, prefix in enumerate(SKILL_FLOW_ORDER):
        if text.startswith(prefix):
            return (index, text)
    return (len(SKILL_FLOW_ORDER), text)


def markdown_document(path):
    """优先读取中文说明；原始 SKILL 执行文件保持不变。"""
    return skill_notes.document(path)


def note_text(skill, *, localize=True):
    """读取注册 SKILL 的说明；默认返回阅读副本，缺失时使用注册表摘要。"""
    if skill is None:
        return ''
    content = markdown_document(getattr(skill, 'path', None))
    if not content:
        content = '\n'.join(line for line in (str(skill.displayName or skill.name or ''),
                                            str(skill.description or '')) if line)
    return skill_notes.preview(content)[0] if localize else content


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
    content = skill_notes.reading_text(markdown_document(path))
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
    """显示中文名称，保留 AIGC 缩写与中点分隔符，过滤路径等装饰。"""
    text = ''.join(re.findall(r'AIGC|[\u4e00-\u9fff·]', str(label or '')))
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


def manual_path(project):
    return Path(project) / MANUAL_NAME


def manual_entry(project, stage):
    """这一阶段手动配的模型 ID 与 SKILL 文件（没配过就是空的一份）。"""
    data = read_json(manual_path(project)) if project else {}
    entry = (data or {}).get(stage) if isinstance(data, dict) else None
    return dict(entry) if isinstance(entry, dict) else {}


def stage_for(value):
    """阶段 id 或老流程名 → 阶段 id（认不出的原样退回，面板照样画得出来）。"""
    text = str(value or '').strip()
    return FLOW_STAGE.get(text, text)


def stage_label(stage):
    """阶段 id → 「08 首帧管理」（认不出的原样退回，面板抬头用它）；权威实现见 pet_bus.stage_label。"""
    return _bus_stage_label(stage)


def panel_title(stage):
    """面板抬头：阶段 id → 「阶段配置 · 08 首帧管理」。"""
    return '阶段配置 · ' + stage_label(stage)


def stage_of_page(index, stages=None):
    """页序号 → 阶段 id（第 11 页参考网站没有阶段，返回空）。"""
    names = list(stages or STAGE_NAMES)
    return names[index] if 0 <= index < len(names) else ''


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
        data = model_pool.raw(program=program)
        # 用户在模型管理里删掉的不补（model_pool.remove 记下的删除记录）：否则阶段里还选着它，一开项目就复活成一条缺根地址的 API 记录。
        deleted = data.get('deleted_desktop_models') or []
        missing = [value for value in wanted if value not in records and value not in deleted]
        if not missing:
            return []
        for value in missing:
            data = model_pool.upsert(data, {'label': value, 'model': value})
        model_pool.store(data, program)
    except Exception:
        return []
    return missing


def build_orchestrator(desktop, project):
    """挂上本项目的一套编排器：总线／错误账本都用桌面现成的。

    路由器按程序目录读模型池（阶段配置挑中的那条要是模型管理里的自定义模型，也得发得出去）。
    """
    from stage_execution_service import build_orchestrator as _build_orchestrator
    return _build_orchestrator(desktop, project)


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
