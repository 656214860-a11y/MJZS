from skill_panel_workflow import PanelWorkflowMixin
from skill_panel_import import PanelImportMixin
from skill_panel_support import (
    FLOW_STAGE,
    EXTERNAL_PACKAGE_API_HINT,
    SKILL_FLOW_ORDER,
    MANUAL_NAME,
    skill_order,
    markdown_document,
    note_text,
    external_package_api_hint,
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
"""统一阶段配置面板（R2862）：SKILL 勾选 ＋ 技能说明 ＋ 制作锁弹窗预选。

总控预设与面板内模型选择已删除：模型选择移到共享输入框（轮 3），制作锁改为
弹窗预选（PanelWorkflowMixin.open_lock_dialog）。本面板只保留 skill 勾选与
技能说明查看——点击说明即渲染该 *.skill.md 完整文档。

SKILL 不绑定模型：面板只管把选择记下来、把选中的跑起来，不替模型说话。
"""
from pathlib import Path
import re

import tkinter as tk
from tkinter import messagebox, ttk
from production_lock_fields import CompactLabel, FlowFields, label_pixel_width

import model_pool
import model_router
import skill_note_render
import orchestrator.skill_notes as skill_notes
from tk_timers import repeat
import orchestrator.skill_budget as skill_budget
import orchestrator.skill_orchestrator as skill_orchestrator
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
from ui_tokens import CHAR_WIDTH

TITLE = '阶段配置'
confirm = ask_confirmation



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
MANAGE_ADD_REPO = '从仓库地址导入'
MANAGE_DELETE = '删除已勾选 SKILL'
MANAGE_LABELS = (MANAGE_ALL, MANAGE_NONE, MANAGE_ADD, MANAGE_ADD_REPO, MANAGE_DELETE)
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

# R2942：页面级「阶段配置」按钮＋其模型下拉框全部删除——模型选择收进共享输入框的
# 下拉框按钮，SKILL 走 ✦ 图标，制作锁在剧本准备页简报表单里编辑。本模块的 Panel／show
# 仍保留：手动制作的「修改配置」预检与资产/首帧弹窗里的入口还走它。


class Panel(PanelWorkflowMixin, PanelImportMixin, FormScrollMixin, ttk.Frame):
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
        # 模型选择已移到共享输入框（轮 3）；这里只留存档模型的只读查询。
        self.choices = model_choices(self.desktop, self.stage)
        # 第 36 期第 1／4 条：这一阶段对应的编排流程（没有就是 None）——流程 SKILL 与手动配置都要它。
        self._flow = STAGE_FLOW.get(self.stage)
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
        # 第一列标签列宽：SKILL／制作锁同宽，左侧控件上下对齐。
        label_texts = ['SKILL', '制作锁']
        self.label_px = max(label_pixel_width(self, label_texts, style=name)
                            for name in ('TLabel', 'Muted.TLabel'))
        item_gap = STAGE_PANEL_LAYOUT['item_gap']
        # 卡片之间不留额外空隙：相邻卡片的 1px 边框就是分隔线，间距取 none 档。
        section_gap = SPACING['none']
        # 底栏（确认并关闭）先占位再排其余区域：Tk 按 pack 顺序分配空间，窗口压到
        # 800x460 时若最后才 pack 底栏，前面的表单会把它挤出可见区，用户就找不到确认按钮。
        # 底栏固定优先，其次是不可伸缩的阶段配置，最后是可伸缩的技能说明区。
        self.bottom_bar = ttk.Frame(self)
        self.bottom_bar.pack(side='bottom', fill='x', pady=(pad, SPACING['none']))
        self.state = ProgressLabel(self.bottom_bar, text='勾选项已自动保存；确认保存本页。')
        self.state.pack(side='left')
        self.confirm_button = PrimaryButton(self.bottom_bar, text='确认并关闭', width=CHAR_WIDTH['xl'],
                                            command=self.confirm)
        self.confirm_button.pack(side='right')
        body = self._build_form_body()
        # 制作锁预选入口（R2862）：锁值是项目级事实，由弹窗统一编辑，不再铺进行内表单。
        locks = ttk.Frame(body, padding=pad, relief='solid', borderwidth=1)
        locks.pack(fill='x', pady=(SPACING['none'], section_gap))
        self.build_lock_entry(pad, locks)
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
            values=MANAGE_LABELS)
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
        if picked == MANAGE_ADD_REPO:
            self.skill_action.set(MANAGE_ALL)
            return self.add_skill_from_repo()
        if picked == MANAGE_ALL:
            return self.check_all_skills(True)
        if picked == MANAGE_NONE:
            return self.check_all_skills(False)
        return ''

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

    def manual(self):
        """项目里这一阶段手动配的那一档（没配过就是空的一份）。"""
        try:
            return manual_entry(self.project(), self.stage)
        except Exception:
            return {}

    # ── SKILL 说明（第 29 期第 4 条；R2916 删除：说明改由共享输入框技能列表的悬停卡片提供） ──
    def build_notes(self, pad):
        """说明区已删除：不再建目录与正文；refresh_notes／show_note 对空句柄自守卫。"""
        self.note_list = None
        self.note_text = None
        self.note_items = []
        return None

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
        body = note_text(entry[1], localize=False) if entry and entry[0] == 'registered' else ''
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
        """面板已无模型控件（轮 3 移到共享输入框）：返回项目里存的这一档模型。"""
        if text is not None:
            return model_pool.id_of_label(text, self.choices)
        try:
            return str(self.entry().get('model') or model_router.AUTO)
        except Exception:
            return model_router.AUTO

    def model_label(self, model=None):
        """模型 id → 池里的显示名（池里没有就照原样念）。"""
        return model_pool.label_of(model, pool_records(self.desktop))

    def refresh_models(self):
        """模型池或阶段模型变了：重查存档模型是否还属本页，并刷新勾选与提示。"""
        try:
            current = str(self.entry().get('model') or model_router.AUTO)
        except Exception:
            current = model_router.AUTO
        self.choices = model_choices(self.desktop, self.stage)
        self.drop_mismatched(current)
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
        chosen = set(entry.get('skills') or [])
        for name, var in self.vars.items():
            var.set(name in chosen)
        manual = self.manual()
        if manual.get('model') or manual.get('skill'):
            # 第 36 期第 4 条：手动配过就把这一档说出来，别让人猜「我配的生效了没有」。
            self.state.configure(text='手动：' + (manual.get('model') or '模型按上方选择')
                                 + ' · ' + (Path(manual['skill']).name if manual.get('skill') else 'SKILL 按上方勾选'))
        self.refresh_notes()
        self.refresh_external_package_hint()
        self.refresh_locks()
        self.refresh_lock_hint()
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
        """经确认后仅恢复本阶段模型与 SKILL 默认值；制作锁保持不变。"""
        if not confirm(self.winfo_toplevel(), TITLE, '恢复本阶段的默认模型和 SKILL？\n制作锁不会改变。'):
            return None
        entry = stage_config.reset(self.project(), self.stage, registry=self.registry)
        self.load()
        self.state.configure(text='已恢复本阶段默认配置；制作锁未改变。')
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
