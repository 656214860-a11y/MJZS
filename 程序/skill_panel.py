# 预设区（占位项常量与八个预设方法）在 skill_panel_presets；按原名转发，旧补丁点有效。
from skill_panel_presets import PRESET_PLACEHOLDER, PresetMixin
from skill_panel_support import (
    FLOW_STAGE,
    EXTERNAL_PACKAGE_API_HINT,
    SKILL_FLOW_ORDER,
    MANUAL_NAME,
    skill_order,
    markdown_document,
    note_text,
    external_package_api_hint,
    workflow_note_text,
    open_cloud_video,
    open_tts,
    interfaces_of,
    flow_skill_choices,
    flow_skill_display,
    chinese_skill_display,
    skill_checkbox_label,
    registered_skill_checkbox_label,
    flow_skill_match,
    flow_skill_paths,
    flow_skill_value,
    set_flow_skills,
    manual_path,
    manual_entry,
    stage_for,
    stage_label,
    panel_title,
    stage_of_page,
    stage_button_for,
    desktop_project,
    pet_of,
    status_of,
    run_report,
    waiting_reason,
    pool_records,
    stage_capabilities,
    model_fits_stage,
    model_choices,
    grouped_model_choices,
    sync_models,
    build_orchestrator,
    program_of,
    stage_context,
    panel_window_size,
    WrappingActionRow,
    FormScrollMixin,
    stage_button_label_for,
    refresh_all,
    register_live,
    unregister_live,
)
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

import tkinter as tk
from tkinter import messagebox, ttk
from production_lock_fields import CompactLabel, FlowFields

import model_pool
import model_router
import skill_note_render
import skill_notes
from tk_timers import repeat
import skill_budget
import skill_orchestrator
import skill_registry
import stage_config
import stage_models
import ui_plugin_registry
from pet_bus import STAGE_NAMES, read_json, stage_label as _bus_stage_label
from storage_maintenance import recycle_paths
from ui_tokens import (COLORS, FONTS, SPACING, NOTE_HEIGHT_COMPACT,
                       NOTE_HEIGHT_REGULAR, NOTE_LIST_MAX_WIDTH, NOTE_LIST_MIN_WIDTH,
                       NOTE_PADDING_X, NOTE_PADDING_Y, STAGE_PANEL_LAYOUT,
                       DIALOG_MIN_HEIGHT, DIALOG_MIN_WIDTH)
from ui_widgets import (SelectBox, BaseDialog, DescriptionBlock, HintLabel, PrimaryButton, ProgressLabel,
                        TextArea,
                        SecondaryButton, Tooltip, ask_confirmation, notify, _display_width)
from ui_dialogs import FileDialog

TITLE = '阶段配置'
confirm = ask_confirmation

# 「套用总控建议」对话框的屏幕留白：上留标题栏／拖动余量，下留任务栏余量，左右各留一档。
# 表体超高时只在对话框内部滚动，窗口本身永远不超过这块可用区。
DIALOG_SCREEN_MARGIN_X = SPACING['xl']
DIALOG_SCREEN_MARGIN_TOP = SPACING['2xl']
DIALOG_SCREEN_MARGIN_BOTTOM = SPACING['2xl'] + SPACING['lg']
# 总控还没生效时制作锁为什么是灰的：锁解锁只发生在「确认套用」之后。
NO_MASTER_LOCK_HINT = '先选择总控并点「确认套用」后才能设置制作锁。'


def dialog_working_area(widget):
    """返回对话框可用的屏幕工作区 ``(left, top, right, bottom)``。

    只按屏幕尺寸扣掉标题栏与任务栏余量，不去探测窗口管理器；测试用
    ``winfo_screenheight`` 的包装固定尺寸，不依赖本机真实分辨率。
    """
    try:
        width = int(widget.winfo_screenwidth())
        height = int(widget.winfo_screenheight())
    except tk.TclError:
        width, height = 1280, 800
    return (DIALOG_SCREEN_MARGIN_X,
            DIALOG_SCREEN_MARGIN_TOP,
            max(DIALOG_SCREEN_MARGIN_X + DIALOG_MIN_WIDTH, width - DIALOG_SCREEN_MARGIN_X),
            max(DIALOG_SCREEN_MARGIN_TOP + DIALOG_MIN_HEIGHT, height - DIALOG_SCREEN_MARGIN_BOTTOM))

# 老页面上的流程名 → 新的制作阶段 id：面板两边都认，省得每个调用点各写一遍。
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
NO_MASTER = '不使用总控'
MANAGE_DELETE = '删除已勾选 SKILL'
MANAGE_LABELS = (MANAGE_ALL, MANAGE_NONE, MANAGE_ADD, MANAGE_DELETE)
# 外部包只登记总入口；API 调用只会收到入口指针，不能假装会展开其中的本地子模块。
# 勾选框按「功能分组／流程先后」排（第 59 期第 6 条）：文件名前缀就是那条流程里的功能分组。


# 第 29 期第 1／4 条：页面上那些重复的「设置 Model + SKILL」「配置线上视频 API」入口并到这块
# 面板里——入口只留一处（标题栏的「阶段配置」），接口本身一个都不少：编排模型的「调用设置」、
# 线上视频 API、配音接口，都在下面这一行里点得到。


# ── 第 36 期第 1 条：编排流程自己的 SKILL（原来只在「调用设置」里挑） ──────────────


# ── 第 36 期第 4 条：每个阶段都有「手动配置模型与 SKILL」的入口 ──────────────────


# 第 50 期第 1 条：原来还有一小块「手动配置（自定义模型 ID＋SKILL 文件）」
# 的弹窗与它的写入口（manual_dialog／set_manual_entry／open_manual）：这两件事现在就在上面两个
# 下拉框里（「+ 添加模型…」／「+ SKILL 入口…」），再留一扇窗就是重复入口，整块删掉。
# manual_entry 留着读：旧项目里手动填过的模型 ID 仍然算数（见 Panel.context）。


def stage_button_label(desktop, stage, fallback='阶段配置'):
    """阶段入口显示实际会被派发的模型／引擎，避免按钮与三虎调用目标不一致。

    本模块既是公开入口，也是既有测试的补丁点：把当前模块全局显式传给实现，
    对 ``STAGE_FLOW``／``stage_for``／``desktop_project``／``pool_records`` 的补丁仍然有效。
    """
    return stage_button_label_for(
        desktop, stage, fallback, STAGE_FLOW,
        project_of=desktop_project, stage_of=stage_for, config=stage_config,
        models=stage_models, pool=model_pool, pool_records_of=pool_records)


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


class Panel(FormScrollMixin, PresetMixin, ttk.Frame):
    """一块阶段配置面板：模型 ＋ SKILL 勾选 ＋ 底部三个按钮。"""

    def __init__(self, master, desktop, stage, function=None, compact=True, scroll=False):
        ttk.Frame.__init__(self, master)
        self.desktop = desktop
        self.stage = stage_for(stage)
        self.function = function
        self.compact = bool(compact)
        # 弹窗形态才启用主体纵向滚动：底栏固定，表单与 SKILL 勾选区在 800×460 可滚动看全。
        self.scroll = bool(scroll)
        self.form_view = None
        self.form_canvas = None
        self.form_scroll = None
        self.form_body = self
        self.registry = skill_registry.default_registry()
        # SKILL 是用户可随时导入／移除的文件。阶段配置是用户主动打开的懒加载入口，
        # 此处强制刷新而非等启动缓存失效，保证新文件立刻出现、已删文件不再有勾选框。
        self.registry.scan(force=True)
        # 第 59 期第 6 条：勾选框按功能分组／流程先后排（原来按名字的字母序，几组混着跳）。
        # 兼容别名仍留在注册表供旧项目读取；配置面板只展示仍可单独执行的主 SKILL。
        self.skills = [item for item in self.registry.getByStage(self.stage) if not item.deprecated]
        self.vars = {}
        self.model = tk.StringVar(value=model_router.AUTO)
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
        self.workflow_choice = tk.StringVar(value=NO_MASTER)
        self._build()
        self.bind('<Destroy>', self.cancel_skill_layout, add='+')
        register_live(self)

    def destroy(self):
        """关掉就从「还开着的面板」名单里划掉（模型池变了不用再刷它）。"""
        self.cancel_skill_layout()
        unregister_live(self)
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

    def _sync_form_view(self, event=None):
        """表单高度按窗口余量封顶：矮窗口留出滚动兜底，正常窗口让说明区吃掉余量。"""
        if ((event is not None and event.widget is not self.form_body)
                or self.form_canvas is None or not self.form_canvas.winfo_exists()
                or not self.form_canvas.winfo_ismapped()):
            return
        content = max(1, self.form_body.winfo_reqheight())
        width = max(1, self.form_canvas.winfo_width())
        self.form_canvas.itemconfigure(self._form_window, width=width)
        notes = getattr(self, 'note_list', None)
        notes_floor = SPACING['2xl'] * 4
        notes_min = min(notes.winfo_reqheight(), notes_floor) if notes is not None else notes_floor
        chrome = self.bottom_bar.winfo_reqheight() if getattr(self, 'bottom_bar', None) else 0
        room = max(1, self.winfo_height() - chrome - notes_min)
        height = min(content, room)
        if int(self.form_canvas.cget('height')) != height:
            self.form_canvas.configure(height=height)
        self.form_canvas.configure(scrollregion=(0, 0, width, max(content, height)))
        need_scroll = content > height + 1
        has_scroll = bool(self.form_scroll.winfo_manager())
        if need_scroll == has_scroll:
            return
        if need_scroll:
            self.form_scroll.pack(side='right', fill='y', before=self.form_canvas)
        else:
            self.form_scroll.pack_forget()

    # ── 画界面 ──────────────────────────────────────────────────────────────
    def _build(self):
        # 阶段配置以连续表单阅读为主，统一使用最小设计间距和标签宽度，避免控件跳列。
        pad = SPACING['xs']
        # 卡片之间不留额外空隙：相邻卡片的 1px 边框就是分隔线，间距取 none 档。
        section_gap = SPACING['none']
        # 底栏（确认并关闭）先占位再排其余区域：Tk 按 pack 顺序分配空间，窗口压到
        # 800x460 时若最后才 pack 底栏，前面的表单会把它挤出可见区，用户就找不到确认按钮。
        # 底栏固定优先，其次是不可伸缩的阶段配置，最后是可伸缩的技能说明区。
        self.bottom_bar = ttk.Frame(self)
        self.bottom_bar.pack(side='bottom', fill='x', pady=(pad, 0))
        self.state = ProgressLabel(self.bottom_bar, text='选择预设即可套用；确认保存本页。')
        self.state.pack(side='left')
        self.preset_hint = self.state
        self.confirm_button = PrimaryButton(self.bottom_bar, text='确认并关闭', width=12,
                                            command=self.confirm)
        self.confirm_button.pack(side='right')
        body = self._build_form_body()
        # 预设决定整套配置，因此置于厂商／模型之前；与下方卡片使用同一左内边距，标签对齐。
        row = WrappingActionRow(body, padding=(pad, 0))
        row.pack(fill='x', pady=(0, section_gap))
        CompactLabel(row, text='预设', style='Muted.TLabel').pack(side='left')
        self.presets = SelectBox(row, textvariable=self.preset,
                                    values=[PRESET_PLACEHOLDER] + self.preset_names())
        self.presets.pack(side='left', padx=(STAGE_PANEL_LAYOUT['field_gap'], STAGE_PANEL_LAYOUT['field_gap']))
        self.presets.bind('<<ComboboxSelected>>', lambda event: self.apply_preset())
        self.preset_actions = SelectBox(
            row, textvariable=self.preset_action,
            values=['选择操作', '保存为预设', '删除预设', '重命名预设', '复制本预设到其他页面'])
        self.preset_actions.pack(side='left', padx=(0, STAGE_PANEL_LAYOUT['field_gap']))
        self.preset_actions.bind('<<ComboboxSelected>>', lambda event: self.run_preset_action())
        self.restore_defaults_button = SecondaryButton(row, text='恢复默认', width=12,
                                                       command=self.reset_defaults)
        self.restore_defaults_button.pack(side='left')
        HintLabel(row, text='勾选项与模型已自动保存').pack(side='left', padx=(SPACING['sm'], SPACING['none']))
        row._schedule_wrap()

        coordinator = ttk.Frame(body, padding=pad, relief='solid', borderwidth=1)
        coordinator.pack(fill='x', pady=(0, section_gap))
        self.build_workflow_coordinator(pad, coordinator)

        engine = ttk.Frame(body, padding=pad, relief='solid', borderwidth=1)
        engine.pack(fill='x', pady=(0, section_gap))
        top = WrappingActionRow(engine)
        top.pack(fill='x')
        CompactLabel(top, text='厂商', style='Muted.TLabel').pack(side='left')
        self.providers = SelectBox(top, textvariable=self.provider,
                                      values=list(self.groups))
        self.providers.pack(side='left', padx=(STAGE_PANEL_LAYOUT['field_gap'], STAGE_PANEL_LAYOUT['field_gap']))
        self.providers.bind('<<ComboboxSelected>>', lambda event: self.choose_provider())
        # 第 50 期第 1 条：最后一项是「+ 添加模型…」——原来那颗「手动配置模型与
        # SKILL」里的「自定义模型」入口，现在就在挑模型的那一格旁边。
        self.models = SelectBox(top, textvariable=self.model,
                                   values=self.provider_labels() + [ADD_MODEL_LABEL])
        self.models.pack(side='left', padx=(STAGE_PANEL_LAYOUT['field_gap'], 0))
        self.models.bind('<<ComboboxSelected>>', lambda event: self.choose_model())
        # 只在用户改选模型后按需探测；构造／load 不调用，避免打开页面时扫描本机程序。
        self.route_hint = HintLabel(engine, text='')
        specific = ttk.Frame(body, padding=pad, relief='solid', borderwidth=1)
        specific.pack(fill='x', pady=(0, section_gap))
        self.build_writer_style_editor(pad, specific)
        self.build_interfaces(pad, specific)
        if not specific.winfo_children():
            specific.pack_forget()
        skill_section = ttk.Frame(body, padding=pad, relief='solid', borderwidth=1)
        skill_section.pack(fill='x', pady=(0, section_gap))
        self.skill_content = ttk.Frame(skill_section)
        self.skill_content.pack(fill='x')
        self.build_flow_skill(self.skill_content)
        # 第 30 期第 7 条：跑完一批之后，除了三个数，还要说清「为什么不算做完」——
        # 得回页面按的和缺文件的分开讲，用户才知道下一步该去哪儿。
        # 执行编排时的细节仍独占一行，避免覆盖上面的结果摘要。
        self.reason = DescriptionBlock(skill_section, text='')
        self.build_notes(pad)
        self.load()
        if self.form_canvas is not None:
            self._sync_form_view()
            self._bind_form_wheel()

    def build_writer_style_editor(self, pad, parent=None):
        """仅剧本阶段提供编剧风格编辑，避免无关页面出现无效入口。"""
        if self.stage not in stage_config.WRITER_STYLE_STAGES:
            return None
        row = WrappingActionRow(parent or self)
        row.pack(fill='x', pady=(SPACING['none'], pad))
        ttk.Label(row, text='编剧风格', style='Muted.TLabel').pack(side='left')
        self.writer_style_button = SecondaryButton(row, text='编辑编剧风格', width=14,
                                                   command=self.open_writer_style_editor)
        self.writer_style_button.pack(side='left', padx=(SPACING['xs'], SPACING['sm']))
        DescriptionBlock(row, text='编剧角色按此风格创作并审核五阶门控，例如参考好莱坞编剧；留空则不附加风格。').pack(
            side='left', padx=(SPACING['sm'], SPACING['none']))
        row._schedule_wrap()
        return row

    def open_writer_style_editor(self):
        """在独立弹窗编辑项目级编剧风格；留空即不附加，不写程序内置 SKILL。"""
        project = desktop_project(self.desktop)
        if not project:
            notify(self.winfo_toplevel(), '请先选择项目。', title=TITLE,
                   status=getattr(self.desktop, 'status', None), modal=False)
            return None
        title = '编辑编剧风格'
        current = stage_config.writer_style(project, self.stage)
        window = BaseDialog(self.winfo_toplevel(), title + ' · ' + stage_label(self.stage),
                            minsize=(620, 430), modal=False, chrome=False)
        body = ttk.Frame(window, padding=SPACING['md'])
        body.pack(fill='both', expand=True)
        DescriptionBlock(body, text='项目级风格：保存后仅在本项目下一次创作自然剧本时生效。'
                                    '例如：参考好莱坞编剧，三幕结构清晰，每场戏有明确目标与阻碍，对白短促并带潜台词。').pack(
            anchor='w', pady=(SPACING['none'], SPACING['sm']))
        editor = TextArea(body, wrap='word', undo=True, font=FONTS['body'],
                         bg=COLORS['background_card'], fg=COLORS['text_primary'],
                         insertbackground=COLORS['primary'])
        editor.insert('1.0', current)
        scroll = ttk.Scrollbar(body, orient='vertical', command=editor.yview)
        editor.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        editor.pack(fill='both', expand=True)
        actions = ttk.Frame(body)
        actions.pack(fill='x', pady=(SPACING['sm'], SPACING['none']))

        def save_style():
            stage_config.put(project, self.stage, writer_style=editor.get('1.0', 'end-1c').strip())
            self.state.configure(text=title + '已保存；下一次自然剧本创作将使用此风格。')
            window.destroy()

        def clear_style():
            stage_config.put(project, self.stage, writer_style='')
            editor.delete('1.0', 'end')
            self.state.configure(text='编剧风格已清空，不再附加项目级风格。')

        PrimaryButton(actions, text='保存风格', width=12,
                      command=save_style).pack(side='left')
        SecondaryButton(actions, text='清空风格', width=12,
                        command=clear_style).pack(side='left', padx=(SPACING['sm'], SPACING['none']))
        SecondaryButton(actions, text='取消', width=12,
                        command=window.destroy).pack(side='right')
        return window

    def build_workflow_coordinator(self, pad, parent=None):
        """受控统筹入口；阶段勾选网格仍是唯一可编辑清单。"""
        import workflow_settings
        from production_lock_fields import ProductionLockFields
        from script_contract import PRODUCTION_LOCK_DEFINITIONS
        names = list(workflow_settings.refresh_workflow_presets()) + ['浏览本地…', NO_MASTER]
        coordinator = parent or self
        self.workflow_coordinator = coordinator
        self._optional_lock_keys = {'reference_mode', 'splice_mode', 'style_base', 'style_directors'}
        self._optional_locks_expanded = False
        def workflow_field(field):
            box = SelectBox(field, textvariable=self.workflow_choice, values=names)
            box.bind('<<ComboboxSelected>>', lambda event: self.choose_workflow())
            return box

        self.lock_fields = ProductionLockFields(
            coordinator, on_change=self.save_workflow_locks,
            definitions=PRODUCTION_LOCK_DEFINITIONS,
            leading=({'key': 'workflow', 'label': '总控', 'style': 'Muted.TLabel',
                      'factory': workflow_field},),
            visible_keys={item['key'] for item in PRODUCTION_LOCK_DEFINITIONS
                          if item['key'] not in self._optional_lock_keys})
        self.lock_fields.pack(fill='x')
        self.workflow_box = self.lock_fields.leading_inputs['workflow']
        self.lock_inputs = dict(self.lock_fields.inputs)
        self.more_locks_button = SecondaryButton(self.lock_fields, text='更多制作锁',
                                                 command=self.toggle_optional_locks)
        self.lock_fields.insert_after('material_source', self.more_locks_button, key='more_locks_button')
        self.lock_notice = ttk.Label(self.lock_fields, text='', style='Muted.TLabel')
        self.lock_fields.insert_after('more_locks_button', self.lock_notice, key='lock_notice')
        self._saved_workflow_locks = {}

    def toggle_optional_locks(self):
        self._optional_locks_expanded = not self._optional_locks_expanded
        for key in self._optional_lock_keys:
            self.lock_fields.set_visible(key, self._optional_locks_expanded)
        self.more_locks_button.configure(text='收起选填锁' if self._optional_locks_expanded else '更多制作锁')
        bind_wheel = getattr(self, '_bind_form_wheel', None)
        if self._optional_locks_expanded and callable(bind_wheel):
            bind_wheel(self.lock_fields)
        sync_form = getattr(self, '_sync_form_view', None)
        if callable(sync_form):
            sync_form()

    def save_workflow_locks(self):
        from stage_execution_service import save_writing_production_locks
        values = {key: entry.get() for key, entry in self.lock_inputs.items()}
        self.lock_fields.context_values = values
        self.lock_fields.refresh_states()
        if values == self._saved_workflow_locks:
            return 'break'
        try:
            save_writing_production_locks(self.project(), values)
        except (ValueError, OSError) as exc:
            self.lock_notice.configure(text='制作锁保存失败：' + str(exc))
            self.lock_fields.schedule()
            self.state.configure(text='制作锁保存失败：' + str(exc))
            return 'break'
        self._saved_workflow_locks = values
        self.lock_notice.configure(text='制作锁已保存；已生成文件不变，后续创作使用新参数。')
        self.lock_fields.schedule()
        return 'break'

    def refresh_workflow(self):
        import workflow_settings
        from stage_execution_service import sync_writing_attachment_locks
        lock_error = ''
        try:
            sync_writing_attachment_locks(self.project())
        except (ValueError, OSError) as exc:
            lock_error = '附档制作锁同步失败：' + str(exc)
        synced = self.sync_master_skill()
        workflow = stage_config.current_workflow(self.project())
        name = str(workflow.get('name') or '').strip()
        self.workflow_choice.set(name if name in workflow_settings.refresh_workflow_presets() else NO_MASTER)
        locks = stage_config.workflow_lock(self.project())
        for key, entry in self.lock_inputs.items():
            entry.state(['!disabled'])
            entry.delete(0, 'end')
            entry.insert(0, str(locks.get(key) or ''))
            if not name:
                entry.state(['disabled'])
        self.lock_fields.set_values(locks, enabled=bool(name))
        self._saved_workflow_locks = {key: entry.get() for key, entry in self.lock_inputs.items()}
        from script_contract import stage_lock_requirements
        required = stage_lock_requirements('script', stage_config.project_created_at(self.project()))
        legacy_missing = [label for key, label in (('track', '赛道'), ('material_source', '素材来源'))
                          if key not in required and not locks.get(key)]
        if getattr(self, 'lock_notice', None) is not None:
            if not name:
                notice = NO_MASTER_LOCK_HINT
            elif legacy_missing:
                notice = '旧项目兼容：' + '、'.join(legacy_missing) + '未选，仅提示不阻断。'
            else:
                notice = ''
            if lock_error:
                notice = notice + '\n' + lock_error if notice else lock_error
            self.lock_notice.configure(text=notice)
            self.lock_fields.schedule()
        if synced:
            self.state.configure(text=synced)

    def sync_master_skill(self, quiet=False):
        """打开阶段配置时检查总控是否更新；更新了就自动同步各阶段并返回提示文字。"""
        import master_skill
        project = self.project()
        if not project:
            return ''
        try:
            result = master_skill.sync(project, getattr(self, 'registry', None))
        except (OSError, ValueError, TypeError, KeyError) as exc:
            return '总控同步未完成：%s' % exc
        if result['stages'] and getattr(self, 'stage', None) in result['stages'] and getattr(self, 'vars', None):
            entry = stage_config.get(project, self.stage)
            for name, var in self.vars.items():
                var.set(name in entry['skills'])
        return ('；' if quiet and result['message'] else '') + result['message']

    def show_workflow_differences(self, preset):
        """偏离徽标只读展开，避免把用户本地勾选误当作可自动覆盖的数据。"""
        rows = stage_config.workflow_differences(self.project(), preset)
        changed = [(STAGE_NAMES.get(stage, stage), values) for stage, values in rows.items()
                   if values['current'] != values['suggested']]
        if not changed:
            return
        lines = ['总控建议与当前阶段勾选：']
        for label, values in changed:
            lines.append('%s\n当前：%s\n建议：%s' %
                         (label, '、'.join(values['current']) or '空',
                          '、'.join(values['suggested']) or '空'))
        notify(self.winfo_toplevel(), '\n\n'.join(lines), title='本地修改明细',
               status=getattr(self.desktop, 'status', None), modal=False)

    def workflow_apply_dialog(self, choice, preset, switching):
        """逐阶段选择“套用／保留”；默认不重写已有勾选。"""
        import workflow_settings
        old = stage_config.current_workflow(self.project())
        rows = stage_config.workflow_differences(self.project(), preset)
        old_preset = workflow_settings.WORKFLOW_PRESETS.get(str(old.get('name') or ''), {})
        # 取消、标题栏 ✕、Esc 都只关窗，不写总控；关闭后下拉框必须还原为已保存值。
        dialog = BaseDialog(self.winfo_toplevel(), '切换总控' if switching else '套用总控建议',
                            modal=False, chrome=False, on_close=self.refresh_workflow)
        dialog.resizable(True, True)
        # 动作区先占底部：Tk 按 pack 顺序分空间，最后才 pack 会被长表格挤出窗口。
        actions = ttk.Frame(dialog, padding=(SPACING['md'], 0, SPACING['md'], SPACING['md']))
        actions.pack(side='bottom', fill='x')
        body = ttk.Frame(dialog, padding=SPACING['md']); body.pack(fill='both', expand=True)
        DescriptionBlock(body, text=(
            '「' + choice + '」为每个制作阶段推荐了一组 SKILL（制作规范）。下表逐阶段对照'
            '「现在用的」和「总控建议」：\n'
            '· 勾选「用建议替换」→ 该阶段改用总控建议的 SKILL；\n'
            '· 不勾 → 该阶段保持现在的 SKILL 不变。\n'
            '还没选过 SKILL 的空阶段已默认勾选；点「确认套用」才会生效。')).pack(fill='x')
        names = {}
        def shown(skills, empty):
            """SKILL id 换成注册表里的中文显示名，用户不必认英文 id。"""
            labels = []
            for sid in skills:
                if sid not in names:
                    item = self.registry.getById(sid) if getattr(self, 'registry', None) else None
                    names[sid] = registered_skill_checkbox_label(item) if item else sid
                labels.append(names[sid])
            return '\n'.join(labels) or empty
        # 阶段对照表放进画布：表体超高时只在框内滚动，窗口高度不跟着长。
        table_view = ttk.Frame(body)
        table_view.pack(fill='both', expand=True, pady=(SPACING['md'], 0))
        canvas = tk.Canvas(table_view, highlightthickness=0, bd=0,
                           bg=COLORS['background_card'])
        scrollbar = ttk.Scrollbar(table_view, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side='left', fill='both', expand=True)
        table = ttk.Frame(canvas)
        table_window = canvas.create_window((0, 0), window=table, anchor='nw')
        def sync_table(_event=None):
            if not canvas.winfo_exists():
                return
            viewport_w = max(1, canvas.winfo_width())
            viewport_h = max(1, canvas.winfo_height())
            content_w = max(1, table.winfo_reqwidth())
            content_h = max(1, table.winfo_reqheight())
            width = max(viewport_w, content_w)
            canvas.itemconfigure(table_window, width=width)
            canvas.configure(scrollregion=(0, 0, width, max(content_h, viewport_h)))
            need_scroll = content_h > viewport_h + 1
            has_scroll = bool(scrollbar.winfo_manager())
            if need_scroll == has_scroll:
                return
            if need_scroll:
                scrollbar.pack(side='right', fill='y', before=canvas)
            else:
                scrollbar.pack_forget()
        table.bind('<Configure>', sync_table, add='+')
        canvas.bind('<Configure>', sync_table, add='+')
        def wheel(event):
            first, last = canvas.yview()
            if last - first >= 0.999:
                return None
            canvas.yview_scroll(-1 if getattr(event, 'delta', 0) > 0 else 1, 'units')
            return 'break'
        def bind_wheel(widget):
            widget.bind('<MouseWheel>', wheel, add='+')
            for child in widget.winfo_children():
                bind_wheel(child)
        headers = ['阶段', '现在用的 SKILL', '总控建议的 SKILL', '是否替换']
        if switching:
            headers.insert(1, '上一个总控的建议')
        for column, text in enumerate(headers):
            ttk.Label(table, text=text, style='Muted.TLabel').grid(
                row=0, column=column, sticky='w', padx=(0, SPACING['lg']), pady=(0, SPACING['xs']))
        table.columnconfigure(len(headers) - 2, weight=1)
        choices = {}
        for row, (stage, values) in enumerate(rows.items(), start=1):
            current, suggested = values['current'], values['suggested']
            # 默认保留已有选择，但允许用户显式选择替换。
            value = tk.BooleanVar(value=not current and bool(suggested))
            choices[stage] = value
            cells = [STAGE_NAMES.get(stage, stage), shown(current, '（空）'), shown(suggested, '（无建议）')]
            if switching:
                cells.insert(1, shown(old_preset.get('stage_skills', {}).get(stage, ()), '（无）'))
            for column, text in enumerate(cells):
                ttk.Label(table, text=text, justify='left').grid(
                    row=row, column=column, sticky='nw', padx=(0, SPACING['lg']), pady=SPACING['xs'])
            same = current == suggested
            ttk.Checkbutton(table, text='已一致，无需重复套用' if same else '用建议替换',
                            variable=value).grid(row=row, column=len(cells), sticky='nw', pady=SPACING['xs'])
        def apply_selected():
            workflow = dict(old)
            workflow.update({'name': choice, 'skill_ref': preset['package'],
                             'lock': dict(old.get('lock') or {})})
            # 逐项“套用”是用户显式决定；调用既有阶段保存入口，不碰未选项。
            for stage, value in choices.items():
                if value.get() and rows[stage]['current'] != rows[stage]['suggested']:
                    entry = stage_config.put(self.project(), stage, skills=rows[stage]['suggested'])
                    if stage == self.stage:
                        for name, var in self.vars.items():
                            var.set(name in entry['skills'])
            stage_config.put_workflow(self.project(), workflow)
            dialog.destroy(); self.refresh_workflow()
            self.refresh_notes()
            self.refresh_external_package_hint()
            self.state.configure(text='总控已更新；未选择的阶段勾选已保留。' + self.sync_master_skill(quiet=True))
        PrimaryButton(actions, text='确认套用', command=apply_selected).pack(side='left')
        SecondaryButton(actions, text='取消', command=dialog.close).pack(
            side='left', padx=(SPACING['sm'], 0))
        # 先按表体自然高度量出窗口，再压到屏幕可用区内；表体差多少由滚动条补。
        dialog.update_idletasks()
        left, top, right, bottom = dialog_working_area(self.winfo_toplevel())
        available_w = max(DIALOG_MIN_WIDTH, right - left)
        available_h = max(DIALOG_MIN_HEIGHT, bottom - top)
        chrome_h = max(0, dialog.winfo_reqheight() - canvas.winfo_reqheight())
        height = max(DIALOG_MIN_HEIGHT,
                     min(chrome_h + table.winfo_reqheight(), available_h))
        canvas.configure(height=max(1, height - chrome_h))
        dialog.update_idletasks()
        # 画布不会把内嵌表格的请求宽度传给窗口，宽度要按表体本身量，给滚动条留一档。
        chrome_w = max(0, dialog.winfo_reqwidth() - canvas.winfo_reqwidth())
        width = max(dialog.winfo_reqwidth(),
                    chrome_w + table.winfo_reqwidth() + scrollbar.winfo_reqwidth() + SPACING['xs'])
        width = max(DIALOG_MIN_WIDTH, min(width, available_w))
        x = max(left, min(self.winfo_rootx() + SPACING['2xl'], right - width))
        y = max(top, min(self.winfo_rooty() + SPACING['2xl'], bottom - height))
        dialog.geometry('%dx%d+%d+%d' % (width, height, x, y))
        bind_wheel(table)
        canvas.bind('<MouseWheel>', wheel, add='+')
        dialog.update_idletasks()
        sync_table()
        return dialog

    def choose_workflow(self):
        import workflow_settings
        choice = self.workflow_choice.get()
        if choice == NO_MASTER:
            stage_config.clear_workflow(self.project()); self.refresh_workflow(); return
        if choice == '浏览本地…':
            # 没有确认就没有写入；下拉框立即回到已保存的总控。
            self.refresh_workflow()
            self.state.configure(text='总控只认 skills/00全流程SKILL/总控.json 里登记的预设；要加新的总控请编辑该清单。'); return
        preset = workflow_settings.WORKFLOW_PRESETS.get(choice)
        if not preset: return
        previous = str(stage_config.current_workflow(self.project()).get('name') or '')
        self.workflow_apply_dialog(choice, preset, switching=bool(previous and previous != choice))


    def build_flow_skill(self, parent):
        """SKILL 操作行：标签＋按内容定宽的下拉框＋勾选框流式排布＋外部包提示。"""
        self.flow_skill_row = None
        self.registered_boxes = {}          # 注册 SKILL id → 勾选框，供删除后立即移除
        self.skill_controls = []
        self._skill_layout_job = None
        self._flow = STAGE_FLOW.get(self.stage)
        if not self._flow and not self.skills:
            return None
        self.skill_action_row = FlowFields(parent, fill_last=False)
        self.skill_action_row.pack(fill='x', pady=(SPACING['none'], SPACING['xs']))
        self.flow_skill_label = CompactLabel(self.skill_action_row, text='SKILL', style='Muted.TLabel')
        self.skill_action_row.add(self.flow_skill_label)
        self.skill_action = tk.StringVar(value='请选择')
        self.skill_action_box = SelectBox(
            self.skill_action_row, textvariable=self.skill_action,
            values=(MANAGE_ALL, MANAGE_NONE, MANAGE_ADD, MANAGE_DELETE))
        self.skill_action_row.add(self.skill_action_box)
        self.skill_action_box.bind('<<ComboboxSelected>>', lambda event: self.choose_skill_action())
        self.external_package_hint = HintLabel(self.skill_action_row, text='')
        self.external_package_hint.configure(wraplength=0)
        count = len(self.skills)
        self.skill_scrollbar = None
        if self.uses_skill_scrollbar(count):
            self.skill_list_outer = ttk.Frame(parent)
            self.skill_list_outer.pack(fill='x', pady=(SPACING['none'], SPACING['xs']))
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
            self.skill_canvas = self.skill_list_outer = None
            self.flow_skill_row = self.skill_action_row  # 勾选框紧跟下拉框，复用操作行引用
        for item in self.skills:
            var = tk.BooleanVar(value=True)
            self.vars[item.name] = var
            # 每个包里的入口通常都叫 SKILL.md；从路径取名会把所有项降级为
            # 「自定义技能」。注册表 displayName 才是已解析的用户可见名称。
            shown = registered_skill_checkbox_label(item)
            box = ttk.Checkbutton(self.flow_skill_row, text=shown,
                                  variable=var, command=self.save_and_refresh_notes)
            box._skill_full_name = shown
            box._skill_path = self.resolved_skill_path(item.path)
            self.registered_boxes[item.name] = box
            self.add_skill_control(box)
        if not self.skills:
            self.empty = HintLabel(self.flow_skill_row, text='这一阶段还没有附加 SKILL')
            self.add_skill_control(self.empty)
        self.skill_action_row.add(self.external_package_hint)
        self.schedule_skill_layout()
        self.skill_action_row._schedule_wrap()
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
        """登记一项勾选控件，并为被截断的名称保留悬停全文。"""
        self.skill_controls.append(widget)
        full = getattr(widget, '_skill_full_name', '')
        if full and len(str(full)) > 26:
            Tooltip(widget, full)
        if self.skill_canvas is None:
            self.skill_action_row.add(widget)  # 流式，FlowFields 负责按可用宽度换行
        else:
            self.schedule_skill_layout()
        return widget

    def skill_label(self, label, limit=26):
        """固定勾选框宽度；过长名称显示省略号，悬停仍可看全文。"""
        text = str(label or '')
        return text if len(text) <= limit else text[:max(1, limit - 3)] + '...'

    @staticmethod
    def uses_skill_scrollbar(count):
        """超过十项时使用滚动容器，三列排列保持不变。"""
        return count > 10

    def schedule_skill_layout(self, _event=None):
        """滚动容器排三列；流式布局由 FlowFields 在 idle 重排并跳过已销毁项。"""
        if self.skill_canvas is not None:
            return self.layout_skill_controls()
        self.skill_action_row.schedule()

    def layout_skill_controls(self):
        """滚动容器内的勾选项按三列网格排列。"""
        self._skill_layout_job = None
        if self.flow_skill_row is None or self.skill_canvas is None:
            return
        for widget in self.skill_controls:
            widget.grid_forget()
        columns = 3
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
        """显式导入 SKILL 到本阶段的受控注册目录：外部包整包导入，预检、试冻结、旧版进回收站。"""
        import skill_import_service
        source = FileDialog(self.winfo_toplevel()).open_file(title='新增 SKILL',
                                            filetypes=[('SKILL', ('*.skill.md', 'SKILL.md')), ('全部文件', '*.*')])
        if not source:
            return None
        try:
            plan = skill_import_service.plan_import(
                source, self.registry._stage_directory_for(self.stage), self.stage, self.registry)
        except skill_import_service.ImportBlocked as exc:
            self.state.configure(text='新增 SKILL 失败：' + str(exc))
            return None
        if plan['problems']:
            message = ('导入前发现以下问题：\n\n' + '\n'.join('· ' + p for p in plan['problems'])
                       + '\n\n仍要导入吗？')
            if not confirm(self.winfo_toplevel(), TITLE, message, dangerous=True):
                return None
        try:
            # 回收站跟随程序目录：阶段目录位于 程序/skills/<阶段>/。
            result = skill_import_service.perform_import(plan, plan['target_dir'].parents[1])
        except (skill_import_service.ImportBlocked, OSError, ValueError) as exc:
            self.state.configure(text='新增 SKILL 失败：' + str(exc))
            return None
        target = result['target']
        self.registry.scan(force=True)
        self.skills = list(self.registry.getByStage(self.stage))
        for child in self.skill_content.winfo_children():
            child.destroy()
        self.vars = {}
        self.build_flow_skill(self.skill_content)
        bind_wheel = getattr(self, '_bind_form_wheel', None)
        if callable(bind_wheel):
            bind_wheel(self.skill_content)
        sync_form = getattr(self, '_sync_form_view', None)
        if callable(sync_form):
            sync_form()
        self.load()
        label = target.parent.name if plan['kind'] == 'package' else target.name
        self.state.configure(text='已新增 SKILL：' + label + ('（整包导入）' if plan['kind'] == 'package' else ''))
        self.refresh_notes(str(target))
        return target

    def check_all_skills(self, value=True):
        """全选／取消全选只作用于唯一的阶段 SKILL 网格。"""
        for var in self.vars.values():
            var.set(bool(value))
        self.save(save_model=False)
        self.refresh_external_package_hint()
        return self.selected()

    def save_and_refresh_notes(self):
        """注册 SKILL 勾选变化后，说明目录与勾选状态同步。"""
        entry = self.save(save_model=False)
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
            notify(self.winfo_toplevel(), '没有可删除的程序 SKILL。', title=TITLE,
                   status=getattr(self.desktop, 'status', None), modal=False)
            return []
        refs = self._referenced_skills([item for item, _path in paths])
        names = '、'.join(item.displayName or item.name for item, _path in paths)
        reference_notice = ('\n\n以下 SKILL 仍被当前项目 skill_config.json 引用：' + '、'.join(refs)
                            + '。继续删除后，该配置会在下次读取时按既有失效项规则清理。') if refs else ''
        if not confirm(self.winfo_toplevel(), TITLE, '将把以下 SKILL 移入程序回收站，是否继续？\n' + names + reference_notice,
                       dangerous=True):
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
        """模型选择仅暂存到确认；「+ 添加模型…」打开模型管理。"""
        if self.model.get() != ADD_MODEL_LABEL:
            self._picked = self.model.get()
            self.show_desktop_route_notice()
            self.refresh_external_package_hint()
            return None
        self.model.set(self._picked or self.model_label(model_router.AUTO))
        return self.open_model_manager()

    def provider_labels(self):
        return [label for _model_id, label in self.groups.get(self.provider.get(), [])]

    def choose_provider(self):
        """先选供应商，再在右侧只显示该供应商的具体模型。"""
        labels = self.provider_labels()
        self.models.set_values(labels + [ADD_MODEL_LABEL])
        if labels:
            self.model.set(labels[0])
            self._picked = labels[0]
            self.show_desktop_route_notice()
            self.refresh_external_package_hint()
            return None
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
        if notice:
            self.route_hint.pack(fill='x')
        else:
            self.route_hint.pack_forget()
        return notice

    def set_model(self, model):
        """按已保存的 id 同步两级下拉；手填的本地 id 也必须原样保留。"""
        wanted = str(model or model_router.AUTO)
        for provider, options in self.groups.items():
            for model_id, label in options:
                if model_id == wanted:
                    self.provider.set(provider)
                    self.models.set_values([item_label for _item_id, item_label in options] + [ADD_MODEL_LABEL])
                    self.model.set(label)
                    self._picked = label
                    return wanted
        if wanted == model_router.AUTO:
            return model_router.AUTO
        # 用户手写的本地模型尚未登记到模型池时，不替用户丢掉配置。
        provider = '自定义'
        self.groups.setdefault(provider, []).append((wanted, wanted))
        self.providers.set_values(list(self.groups))
        self.provider.set(provider)
        self.models.set_values([wanted, ADD_MODEL_LABEL])
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
                line = WrappingActionRow(parent or self)
                line.pack(fill='x', pady=(pad, 0))
                ttk.Label(line, text='接口', style='Muted.TLabel').pack(side='left')
            button = SecondaryButton(line, text=label,
                                     command=lambda f=opener: self.open_interface(f))
            button.pack(side='left', padx=(SPACING['xs'], SPACING['none']))
            self.interface_buttons.append(button)
        if self.interface_buttons:
            line._schedule_wrap()
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
        box.pack(fill='both', expand=True, pady=(SPACING['none'], 0))
        # LabelFrame 默认会按子控件的请求高度收缩；锁定其几何传播后再按面板
        # 剩余高度分配，拖动阶段配置窗口才不会留下空白而说明区仍停在 12 行。
        box.grid_propagate(False)
        # 说明框占用面板剩余空间：窗口放大时目录和正文一起变高，优先露出更多 SKILL。
        box.columnconfigure(1, weight=0)
        box.rowconfigure(0, weight=1)
        height = NOTE_HEIGHT_COMPACT if self.compact else NOTE_HEIGHT_REGULAR
        self.note_list = tk.Listbox(box, height=height, width=NOTE_LIST_MIN_WIDTH,
                                    exportselection=False, activestyle='none',
                                    font=FONTS['body'], selectbackground=COLORS['selection_bg'],
                                    selectforeground=COLORS['selection_text'])
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
        self.note_text = TextArea(body, height=height, wrap='word', relief='flat',
                                 bg=COLORS['background_card'], fg=COLORS['text_primary'],
                                 font=FONTS['body'], padx=NOTE_PADDING_X, pady=NOTE_PADDING_Y,
                                 selectbackground=COLORS['selection_bg'],
                                 selectforeground=COLORS['selection_text'], yscrollcommand=bar.set)
        self.note_text.grid(row=0, column=0, sticky='nsew')
        bar.configure(command=self.note_text.yview)
        self.note_text.configure(state='disabled')

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
        old_path = (old[1].path if old and old[0] == 'registered'
                    else old[2] if old else None)
        target = str(preferred_path or old_path or '')
        self.note_items = self.note_entries()
        self.note_list.delete(0, 'end')
        selected = 0
        width = NOTE_LIST_MIN_WIDTH
        for index, entry in enumerate(self.note_items):
            label = (entry[1].displayName or entry[1].name
                     if entry[0] == 'registered' else entry[1])
            shown = chinese_skill_display(label)
            self.note_list.insert('end', shown)
            width = max(width, _display_width(shown))
            path = entry[1].path if entry[0] == 'registered' else entry[2]
            if str(path) == target:
                selected = index
        self.note_list.configure(width=min(NOTE_LIST_MAX_WIDTH, width))
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
        body = (note_text(entry[1], localize=False) if entry and entry[0] == 'registered'
                else workflow_note_text(entry[1], entry[2]) if entry else '')
        source = body
        body, pending = skill_notes.preview(source, program_of(self.desktop))
        self._note_source = source
        self.render_note(body)
        if pending:
            self.translate_note(source, body)
        if entry and entry[0] == 'registered':
            box = self.registered_boxes.get(entry[1].name)
            if box is not None:
                box.focus_set()
        return body

    def render_note(self, body):
        skill_note_render.apply(self.note_text, body)

    def translate_note(self, source, shown):
        """利用既有后台执行器翻译；忙时等待，切换条目后不回填旧内容。"""
        attempts = getattr(self, '_note_attempts', None)
        if attempts is None:
            attempts = self._note_attempts = {}
        if source in attempts:
            result = attempts[source]
            self.render_note(result if result else '正在生成中文说明…\n\n' + shown)
            return
        if not callable(getattr(self.desktop, 'async_', None)):
            self.render_note('中文翻译需要可用的 API 文本模型。\n\n' + shown)
            return
        attempts[source] = None
        self.render_note('正在生成中文说明…\n\n' + shown)
        program = program_of(self.desktop)

        def done(result):
            content = result['text']
            if not result['ok']:
                content = '中文翻译未完成：' + result['message'] + '\n\n' + content
            attempts[source] = content
            if self.winfo_exists() and getattr(self, '_note_source', None) == source:
                self.render_note(content)

        def start():
            if getattr(self.desktop, 'worker', False):
                return
            stop()
            self.desktop.async_(lambda: skill_notes.translate(source, program), done,
                                show_progress=False)

        stop = repeat(self, 200, start)

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
        self.providers.set_values(list(self.groups))
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

    def save(self, quiet=True, save_model=True):
        """保存阶段选择；SKILL 自动保存时用 save_model=False 保留已确认模型。"""
        project = self.project()
        names = self.selected()
        entry = stage_config.put(project, self.stage, model=self.model_id() if save_model else None,
                                 skills=names, registry=self.registry)
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
        if not confirm(self.winfo_toplevel(), TITLE, '恢复本阶段的默认模型和 SKILL？\n总控与制作锁不会改变。'):
            return None
        entry = stage_config.reset(self.project(), self.stage, registry=self.registry)
        self.load()
        self.state.configure(text='已恢复本阶段默认配置；总控与制作锁未改变。')
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
            notify(self.winfo_toplevel(), str(exc), title=TITLE,
                   status=getattr(self.desktop, 'status', None), modal=False)
            return None
        names = self.selected()
        if not names:
            notify(self.winfo_toplevel(), '先勾上要跑的 SKILL。', title=TITLE,
                   status=getattr(self.desktop, 'status', None), modal=False)
            return None
        self.save(save_model=False)
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
            notify(window, '这几个要花钱的活先排着队（现在不打扰您）：%s' % names,
                   title=TITLE, status=getattr(self.desktop, 'status', None), modal=False)
            return []
        if not confirm(window, TITLE, '这几个要花钱：%s\n\n现在做吗？' % names, dangerous=True):
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
        if self.reason.cget('text'):
            self.reason.pack(fill='x')
        else:
            self.reason.pack_forget()
        text = str(run.get('text') or '')
        status_of(self.desktop, text.splitlines()[0] if text else '')
        run_report(self.desktop, text)
        return run


def show(desktop, stage, function=None, launcher_button=None):
    """弹窗形式：页面上那颗「阶段配置」按钮走这里，只配它所在的那一个阶段。

    第 33 期第 3 条：抬头那个「阶段」下拉撤掉——每页都有自己的按钮了，再从面板里切到别的
    阶段只会让人分不清「我刚配的到底是哪一步」。
    """
    if desktop_project(desktop) is None:
        notify(getattr(desktop, 'win', None), '请先选择项目。', title=TITLE,
               status=getattr(desktop, 'status', None), modal=False)
        return None
    stage = stage_for(stage)
    parent = getattr(desktop, 'win', None)
    window = BaseDialog(parent, panel_title(stage), modal=False, chrome=False)
    # 主窗口只约束初始尺寸，不作为用户后续缩放的上限或下限。
    window.resizable(True, True)
    if parent is not None:
        width, height, max_width, max_height = panel_window_size(parent)
        window.geometry('%dx%d' % (width, height))
    else:
        window.geometry('880x720')
    # 最小窗口取令牌值；屏幕可用区比它小时按可用区收缩，不让窗口超出屏幕。
    window.minsize(min(STAGE_PANEL_LAYOUT['min_width'], window.winfo_screenwidth()),
                   min(STAGE_PANEL_LAYOUT['min_height'], window.winfo_screenheight()))
    body = ttk.Frame(window, padding=SPACING['md'])
    body.pack(fill='both', expand=True)
    head = ttk.Frame(body)
    head.pack(fill='x', pady=(SPACING['none'], SPACING['sm']))
    ttk.Label(head, text=panel_title(stage), style='Tokens.Title.TLabel').pack(side='left')
    host = ttk.Frame(body)
    host.pack(fill='both', expand=True)
    panel = Panel(host, desktop, stage, function=function, compact=False, scroll=True)
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
        notify(getattr(desktop, 'win', None), '这一页没有制作阶段。', title=TITLE,
               status=getattr(desktop, 'status', None), modal=False)
        return None
    return show(desktop, stage, launcher_button=launcher_button)
