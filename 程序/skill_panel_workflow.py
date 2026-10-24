"""阶段配置面板的工作流锁定、差异与套用（R1851 后从 skill_panel 迁出，方法体未改）。"""
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
from ui_tokens import (BUTTON_GAP, COLORS, FONTS, SPACING, NOTE_HEIGHT_COMPACT,
                       NOTE_HEIGHT_REGULAR, NOTE_LIST_MAX_WIDTH, NOTE_LIST_MIN_WIDTH,
                       NOTE_PADDING_X, NOTE_PADDING_Y, STAGE_PANEL_LAYOUT,
                       DIALOG_MIN_HEIGHT, DIALOG_MIN_WIDTH)
from ui_widgets import (SelectBox, BaseDialog, DescriptionBlock, HintLabel, PrimaryButton, ProgressLabel,
                        TextArea,
                        SecondaryButton, Tooltip, ask_confirmation, notify, _display_width)
from ui_dialogs import FileDialog


NO_MASTER_LOCK_HINT = '先选择总控并点「确认套用」后才能设置制作锁。'

# 「套用总控建议」对话框的屏幕留白：上留标题栏／拖动余量，下留任务栏余量，左右各留一档。
# 表体超高时只在对话框内部滚动，窗口本身永远不超过这块可用区。
DIALOG_SCREEN_MARGIN_X = SPACING['xl']
DIALOG_SCREEN_MARGIN_TOP = SPACING['2xl']
DIALOG_SCREEN_MARGIN_BOTTOM = SPACING['2xl'] + SPACING['lg']

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

NO_MASTER = '不使用总控'


class PanelWorkflowMixin:
    """Panel 的方法集（见模块说明）。"""

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
        table_view.pack(fill='both', expand=True, pady=(SPACING['md'], SPACING['none']))
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
                row=0, column=column, sticky='w', padx=(SPACING['none'], SPACING['lg']), pady=(SPACING['none'], SPACING['xs']))
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
                    row=row, column=column, sticky='nw', padx=(SPACING['none'], SPACING['lg']), pady=SPACING['xs'])
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
        PrimaryButton(actions, text='确认套用', command=apply_selected).pack(side='right')
        SecondaryButton(actions, text='取消', command=dialog.close).pack(
            side='right', padx=(SPACING['none'], BUTTON_GAP))
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
