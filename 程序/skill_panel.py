# 预设区（占位项常量与八个预设方法）在 skill_panel_presets；按原名转发，旧补丁点有效。
from skill_panel_workflow import (DIALOG_SCREEN_MARGIN_BOTTOM, DIALOG_SCREEN_MARGIN_TOP,
                                   DIALOG_SCREEN_MARGIN_X, NO_MASTER, NO_MASTER_LOCK_HINT, PanelWorkflowMixin, dialog_working_area)  # R1851 后迁出
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
from production_lock_fields import CompactLabel, FlowFields, label_pixel_width

import model_pool
import model_router
import edit_habits_dialog, skill_note_render
import skill_notes
from stage_model_picker import attach_stage_pickers, stage_button_for
from tk_timers import repeat
import skill_budget
import skill_orchestrator
import skill_registry
import stage_config
import stage_models
import ui_plugin_registry
from contract.pet_bus import STAGE_NAMES, read_json, stage_label as _bus_stage_label
from storage_maintenance import recycle_paths
from ui_tokens import (COLORS, FONTS, SPACING, NOTE_HEIGHT_COMPACT,
                       NOTE_HEIGHT_REGULAR, NOTE_LIST_MAX_WIDTH, NOTE_LIST_MIN_WIDTH,
                       NOTE_PADDING_X, NOTE_PADDING_Y, STAGE_PANEL_LAYOUT,
                       DIALOG_MIN_HEIGHT, DIALOG_MIN_WIDTH)
from ui_widgets import (SelectBox, BaseDialog, DescriptionBlock, HintLabel, PrimaryButton, ProgressLabel,
                        TextArea,
                        SecondaryButton, Tooltip, ask_confirmation, notify, _display_width)
from ui_dialogs import FileDialog
from ui_tokens import CHAR_WIDTH

TITLE = '阶段配置'
confirm = ask_confirmation

# 总控还没生效时制作锁为什么是灰的：锁解锁只发生在「确认套用」之后。



# 老页面上的流程名 → 新的制作阶段 id：面板两边都认，省得每个调用点各写一遍。
# 反过来查：阶段 id → 工作流名字。只收 workflow_settings 真正认得的七个流程——
# final／edit／delivery 那三个阶段本来就没有「调用设置」这一档，别凭空造出一个按钮来。
FLOW_NAMES = ('writing', 'storyboard', 'assets', 'frames', 'previs', 'video_prompt', 'audio')
STAGE_FLOW = {FLOW_STAGE[name]: name for name in FLOW_NAMES if name in FLOW_STAGE}
# 第 50 期第 1 条：原来那颗「手动配置模型与 SKILL」拆成两个入口，直接长在两个下拉框里——
# 「模型」那一格最后一项是「+ 添加模型…」（去模型管理里加一条自己的模型），「流程 SKILL」
# 那一格最后一项是「+ SKILL 入口…」（自己挑一个 SKILL.md 当这一流程的 SKILL）。
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


def stage_button(parent, desktop, index, text='阶段配置'):
    """各阶段页「手动XX」右边那颗「阶段配置」（第 32 期第 6 条）。

    面板此前只在剧本准备页挂着，用户到了别的阶段还得跑回去点；现在每页各留一颗，
    按页序号找阶段（stage_of_page），点开的就是这一页那一个阶段的模型与 SKILL。
    """
    stage = stage_of_page(index)
    button = stage_button_for(parent, lambda: None, text, desktop, stage)
    # 阶段配置只读取／编辑配置，不会启动生产任务；后台任务进行时仍须允许用户查看或调整它。
    button.configure(command=lambda: open_for_page(desktop, index, button))
    return button


class Panel(PanelWorkflowMixin, FormScrollMixin, PresetMixin, ttk.Frame):
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
        self.preset = tk.StringVar(value=PRESET_PLACEHOLDER)
        self.preset_action = tk.StringVar(value='选择操作')
        # 下拉的选项＝模型管理里那几条（第 43 期：不写死，池子加一条这里就多一项）。
        self.choices = model_choices(self.desktop, self.stage)
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
        if self.form_canvas.winfo_pixels(self.form_canvas.cget('height')) != height:  # Tk 9 的 cget 可能回 '7c' 这类带单位的值
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
        # 第一列标签列宽：预设／厂商／总控／SKILL／风格同宽，左侧下拉框上下对齐；
        # 制作锁其余各列按本列最宽标签收窄，第一列被撑宽时经 align_label_column 同步。
        label_texts = ['预设', '厂商', '总控', 'SKILL', '风格']
        self.label_px = max(label_pixel_width(self, label_texts, style=name)
                            for name in ('TLabel', 'Muted.TLabel'))
        select_width = STAGE_PANEL_LAYOUT['select_width']
        item_gap = STAGE_PANEL_LAYOUT['item_gap']
        # 卡片之间不留额外空隙：相邻卡片的 1px 边框就是分隔线，间距取 none 档。
        section_gap = SPACING['none']
        # 底栏（确认并关闭）先占位再排其余区域：Tk 按 pack 顺序分配空间，窗口压到
        # 800x460 时若最后才 pack 底栏，前面的表单会把它挤出可见区，用户就找不到确认按钮。
        # 底栏固定优先，其次是不可伸缩的阶段配置，最后是可伸缩的技能说明区。
        self.bottom_bar = ttk.Frame(self)
        self.bottom_bar.pack(side='bottom', fill='x', pady=(pad, SPACING['none']))
        self.state = ProgressLabel(self.bottom_bar, text='选择预设即可套用；确认保存本页。')
        self.state.pack(side='left')
        self.preset_hint = self.state
        self.confirm_button = PrimaryButton(self.bottom_bar, text='确认并关闭', width=CHAR_WIDTH['xl'],
                                            command=self.confirm)
        self.confirm_button.pack(side='right')
        body = self._build_form_body()
        # 预设决定整套配置，因此置于厂商／模型之前；与下方卡片使用同一左内边距，标签对齐。
        row = WrappingActionRow(body, padding=(pad, 0))
        row.pack(fill='x', pady=(SPACING['none'], section_gap))
        CompactLabel(row, text='预设', style='Muted.TLabel', min_px=self.label_px).pack(side='left')
        self.presets = SelectBox(row, textvariable=self.preset, width=select_width,
                                    values=[PRESET_PLACEHOLDER] + self.preset_names())
        self.presets.pack(side='left', padx=(STAGE_PANEL_LAYOUT['field_gap'], item_gap))
        self.presets.gap_after = item_gap
        self.presets.bind('<<ComboboxSelected>>', lambda event: self.apply_preset())
        self.preset_actions = SelectBox(
            row, textvariable=self.preset_action, width=select_width,
            values=['选择操作', '保存为预设', '删除预设', '重命名预设', '复制本预设到其他页面'])
        self.preset_actions.pack(side='left', padx=(SPACING['none'], item_gap))
        self.preset_actions.gap_after = item_gap
        self.preset_actions.bind('<<ComboboxSelected>>', lambda event: self.run_preset_action())
        self.restore_defaults_button = SecondaryButton(row, text='恢复默认', width=CHAR_WIDTH['xl'],
                                                       command=self.reset_defaults)
        self.restore_defaults_button.pack(side='left')
        HintLabel(row, text='勾选项与模型已自动保存').pack(side='left', padx=(SPACING['sm'], SPACING['none']))
        row._schedule_wrap()

        coordinator = ttk.Frame(body, padding=pad, relief='solid', borderwidth=1)
        coordinator.pack(fill='x', pady=(SPACING['none'], section_gap))
        self.build_workflow_coordinator(pad, coordinator)

        engine = ttk.Frame(body, padding=pad, relief='solid', borderwidth=1)
        # 只在用户改选模型后按需探测；构造／load 不调用，避免打开页面时扫描本机程序。
        self.engine_frame = engine
        self.route_hint = HintLabel(engine, text='')
        specific = ttk.Frame(body, padding=pad, relief='solid', borderwidth=1)
        self.route_anchor = specific
        specific.pack(fill='x', pady=(SPACING['none'], section_gap))
        self.build_writer_style_editor(pad, specific)
        self.build_interfaces(pad, specific)
        if not specific.winfo_children():
            specific.pack_forget()
        skill_section = ttk.Frame(body, padding=pad, relief='solid', borderwidth=1)
        skill_section.pack(fill='x', pady=(SPACING['none'], section_gap))
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
        CompactLabel(row, text='风格', style='Muted.TLabel',
                     min_px=getattr(self, 'label_px', 0)).pack(side='left')
        self.writer_style_button = SecondaryButton(row, text='编辑编剧风格', width=CHAR_WIDTH['2xl'],
                                                   command=self.open_writer_style_editor)
        self.writer_style_button.pack(side='left', padx=(SPACING['xs'], SPACING['sm']))
        self.edit_habits_button = edit_habits_dialog.entry_button(row, self)  # REQ-S01-60：跨项目修改习惯
        DescriptionBlock(row, text='编剧角色按此风格创作并审核五阶门控，例如参考好莱坞编剧；留空则不附加风格。').pack(side='left', padx=(SPACING['sm'], SPACING['none']))
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

        PrimaryButton(actions, text='保存风格', width=CHAR_WIDTH['xl'],
                      command=save_style).pack(side='left')
        SecondaryButton(actions, text='清空风格', width=CHAR_WIDTH['xl'],
                        command=clear_style).pack(side='left', padx=(SPACING['sm'], SPACING['none']))
        SecondaryButton(actions, text='取消', width=CHAR_WIDTH['xl'],
                        command=window.destroy).pack(side='right')
        return window


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
        self.flow_skill_label = CompactLabel(self.skill_action_row, text='SKILL', style='Muted.TLabel',
                                             min_px=getattr(self, 'label_px', 0))
        self.skill_action_row.add(self.flow_skill_label)
        self.skill_action = tk.StringVar(value='请选择')
        self.skill_action_box = SelectBox(
            self.skill_action_row, textvariable=self.skill_action,
            width=STAGE_PANEL_LAYOUT['select_width'],
            values=(MANAGE_ALL, MANAGE_NONE, MANAGE_ADD, MANAGE_DELETE))
        self.skill_action_box.gap_after = STAGE_PANEL_LAYOUT['item_gap']  # 下拉框与首个勾选框拉开
        self.skill_action_row.add(self.skill_action_box)
        self.skill_action_box.bind('<<ComboboxSelected>>', lambda event: self.choose_skill_action())
        self.external_package_hint = HintLabel(self.skill_action_row, text='')
        self.external_package_hint.configure(wraplength=0)
        count = len(self.skills)
        self.skill_scrollbar = None
        if self.uses_skill_scrollbar(count):
            self.skill_list_outer = ttk.Frame(parent)
            self.skill_list_outer.pack(fill='x', pady=(SPACING['none'], SPACING['xs']))
            self.skill_canvas = tk.Canvas(self.skill_list_outer, height=SPACING['sm'] * 20, highlightthickness=0, bd=0,
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
            widget.grid(row=row, column=column, sticky='w', padx=(SPACING['none'], SPACING['sm']), pady=(SPACING['none'], SPACING['xs']))
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
                source, self.registry.user_stage_directory_for(self.stage), self.stage, self.registry)
        except skill_import_service.ImportBlocked as exc:
            self.state.configure(text='新增 SKILL 失败：' + str(exc))
            return None
        if plan['problems']:
            message = ('导入前发现以下问题：\n\n' + '\n'.join('· ' + p for p in plan['problems'])
                       + '\n\n仍要导入吗？')
            if not confirm(self.winfo_toplevel(), TITLE, message, dangerous=True):
                return None
        try:
            # 回收站跟随程序目录（R2073：用户层在 程序/data/skills/<阶段>/）。
            result = skill_import_service.perform_import(plan, skill_import_service.program_of(plan['target_dir']))
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
        config = stage_config.path(project) if project else None
        data = read_json(config) if config and config.is_file() else {}
        wanted = {item.name for item in items}
        return sorted(name for name in wanted if name in str(data))

    def delete_checked_skills(self):
        """仅回收程序 skills/ 与用户层 data/skills/ 下已勾选的 .skill.md，绝不改项目配置。"""
        program = Path(__file__).resolve().parent
        roots = skill_registry.skill_roots(program)
        selected = [item for item in self.skills if self.vars.get(item.name) and self.vars[item.name].get()]
        paths = []
        for item in selected:
            path = Path(getattr(item, 'path', '')).resolve()
            if path.suffixes[-2:] == ['.skill', '.md'] and path.is_file() and any(path.is_relative_to(root) for root in roots):
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
            self.engine_frame.pack(fill='x', pady=(SPACING['none'], SPACING['none']),
                                   before=self.route_anchor)
            self.route_hint.pack(fill='x')
        else:
            self.route_hint.pack_forget()
            self.engine_frame.pack_forget()
        return notice

    def set_model(self, model):
        """按已保存的 id 记下当前模型；手填的本地 id 也必须原样保留。"""
        wanted = str(model or model_router.AUTO)
        for provider, options in self.groups.items():
            for model_id, label in options:
                if model_id == wanted:
                    self.provider.set(provider)
                    self.model.set(label)
                    return wanted
        if wanted == model_router.AUTO:
            return model_router.AUTO
        # 用户手写的本地模型尚未登记到模型池时，不替用户丢掉配置。
        provider = '自定义'
        self.groups.setdefault(provider, []).append((wanted, wanted))
        self.provider.set(provider)
        self.model.set(wanted)
        return wanted

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
                line.pack(fill='x', pady=(pad, SPACING['none']))
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
        box.pack(fill='both', expand=True, pady=(SPACING['none'], SPACING['none']))
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
        self.note_list_bar.grid(row=0, column=1, sticky='ns', padx=(SPACING['none'], pad))
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
        program, project = program_of(self.desktop), desktop_project(self.desktop)

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
            self.desktop.async_(lambda: skill_notes.translate(source, program, project=project), done,
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
        """模型池或阶段模型变了：换掉选项，当前这一档以项目配置为准（不在池里了就退回「自动」）。"""
        try:
            current = str(self.entry().get('model') or model_router.AUTO)
        except Exception:
            current = self.model_id()
        self.choices = model_choices(self.desktop, self.stage)
        self.groups = grouped_model_choices(self.desktop, self.stage)
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
