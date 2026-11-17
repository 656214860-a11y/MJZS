# -*- coding: utf-8 -*-
"""项目文件停靠面板的阶段快捷图标列与筛选条（R3106，任务书 P1）。

自 ``desktop_files_panel.ProjectFilesPanel`` 拆出：类行数棘轮上限 600 行
（``test_complexity_ratchet``），筛选条与图标列是本轮新增的一块独立职责。
宿主须提供 ``page``／``script_box``／``script_tree``／``script_row_details``／
``script_row_category``／``_open`` 等已有成员。
"""
import tkinter as tk
from tkinter import ttk

from ui_tokens import SPACING
from ui_widgets import LineInput, SecondaryButton, SelectBox, Tooltip
from ui.desktop_files_panel_index import FilesPanelIndexMixin

# R3094（任务书 P1，Q8 补充需求）：停靠面板右缘的阶段快捷图标列，顺序＝pet_bus.STAGES。
# P1 用 Unicode 符号兜底（用户已确认先符号、后换 PNG 图标）；每个图标都带 Tooltip 中文名。
STAGE_RAIL_ICONS = {
    'script': '📝', 'script_structure': '🧾', 'storyboard': '🎬', 'animatic': '🎞',
    'assets': '🎨', 'continuity': '🧩', 'final': '✅', 'keyframe': '🖼',
    'previs': '🧊', 'video': '📹', 'audio': '🎙', 'edit': '✂', 'delivery': '📦',
}
STAGE_RAIL_ALL = '📁'          # 「全部」：全项目索引，按阶段分组
STAGE_FILTER_ROW_CATEGORY = 'index'   # 索引行在右键菜单里与剧本行区分

# 下拉框与输入框的宽度以「字符」计，从 token 派生，避免新增数字字面量（test_token_boundary）。
FILTER_STAGE_WIDTH = max(6, SPACING['sm'])
FILTER_BOX_WIDTH = max(4, SPACING['xs'])
FILTER_KEYWORD_WIDTH = max(4, SPACING['xs'])


def _retention_days():
    """回收站保留期（天）：唯一定义在 ``storage_maintenance``，这里只读不复制数字。"""
    from storage_maintenance import RECYCLE_RETENTION_DAYS
    return RECYCLE_RETENTION_DAYS


class FilesPanelFilterMixin(FilesPanelIndexMixin):
    """阶段图标列＋筛选条＋按索引填表。"""

    # ── 筛选条（R3106，任务书 P1，Q25）────────────────────────────────────
    def _build_filter_bar(self):
        """阶段／类型／状态下拉＋文件名关键字；空值一律表示「不限」。"""
        from contract.file_index_contract import STATUSES
        from contract.file_naming import KINDS
        from contract.pet_bus import STAGES, stage_name
        bar = ttk.Frame(self.script_box)
        bar.pack(side='top', fill='x', pady=(SPACING['none'], SPACING['xs']))
        self.filter_bar = bar
        # 两行摆放：下拉框的 width 以「字符」计，单行并排会把面板请求宽撑到 400+，
        # 让「按最长文件名收窄」的既有契约失效（R2998／test_file_list_width_fits_longest_filename）。
        row_one = ttk.Frame(bar)
        row_one.pack(side='top', fill='x')
        row_two = ttk.Frame(bar)
        row_two.pack(side='top', fill='x')
        row_three = ttk.Frame(bar)
        row_three.pack(side='top', fill='x')
        self.stage_labels = {'全部阶段': None}
        for stage in STAGES:
            self.stage_labels[stage_name(stage)] = stage
        self.kind_labels = {'全部类型': None}
        for kind in KINDS:
            self.kind_labels[kind] = kind
        self.status_labels = {'全部状态': None}
        for status in STATUSES:
            self.status_labels[status] = status
        self.stage_box = SelectBox(row_one, values=tuple(self.stage_labels), width=FILTER_STAGE_WIDTH)
        self.stage_box.pack(side='left', fill='x', expand=True)
        self.stage_box.bind('<<ComboboxSelected>>', lambda _event: self._apply_filters())
        Tooltip(self.stage_box, '按工作阶段筛选')
        self.kind_box = SelectBox(row_two, values=tuple(self.kind_labels), width=FILTER_BOX_WIDTH)
        self.kind_box.pack(side='left')
        self.kind_box.bind('<<ComboboxSelected>>', lambda _event: self._apply_filters())
        Tooltip(self.kind_box, '按文件类型筛选')
        self.status_box = SelectBox(row_two, values=tuple(self.status_labels), width=FILTER_BOX_WIDTH)
        self.status_box.pack(side='left', padx=(SPACING['xs'], SPACING['none']))
        self.status_box.bind('<<ComboboxSelected>>', lambda _event: self._apply_filters())
        Tooltip(self.status_box, '按状态筛选：草稿／已发布／已归档')
        self.keyword_var = tk.StringVar(value='')
        # 业务 UI 不得直接建 ttk.Entry（test_input_boundary）：统一走 LineInput。
        self.keyword_entry = LineInput(row_three, textvariable=self.keyword_var, width=FILTER_KEYWORD_WIDTH)
        self.keyword_entry.pack(side='left', fill='x', expand=True, padx=(SPACING['xs'], SPACING['none']))
        self.keyword_entry.bind('<KeyRelease>', self._keyword_changed)
        Tooltip(self.keyword_entry, '按文件名关键字筛选（回车立即生效）')
        row_four = ttk.Frame(bar)
        row_four.pack(side='top', fill='x')
        self.group_box = SelectBox(row_four, values=('阶段', '类型', '日期'), width=FILTER_BOX_WIDTH)
        self.group_box.pack(side='left')
        self.group_box.set('阶段')
        self.group_box.bind('<<ComboboxSelected>>', lambda _event: self._apply_filters())
        Tooltip(self.group_box, '分组方式：阶段／类型／日期（跨阶段归组）')
        self.sort_box = SelectBox(row_four, values=('类型', '修改时间'), width=FILTER_STAGE_WIDTH)
        self.sort_box.pack(side='left', padx=(SPACING['xs'], SPACING['none']))
        self.sort_box.set('类型')
        self.sort_box.bind('<<ComboboxSelected>>', lambda _event: self._apply_filters())
        Tooltip(self.sort_box, '组内按类型或修改时间排序（最新在前）')
        self.index_refresh_button = SecondaryButton(row_three, text='刷新', command=self.refresh_file_index)
        self.index_refresh_button.pack(side='left', padx=(SPACING['xs'], SPACING['none']))
        Tooltip(self.index_refresh_button, '后台重建索引，发现外部新增或修改的文件')
        self._reset_filter_boxes()

    def _reset_filter_boxes(self):
        """下拉框显示回「全部」，不触发回调。"""
        for box in (getattr(self, 'stage_box', None), getattr(self, 'kind_box', None),
                    getattr(self, 'status_box', None)):
            if box is not None:
                box.set(tuple(box.cget('values'))[0])
        if getattr(self, 'keyword_var', None) is not None:
            self.keyword_var.set('')

    def _reset_filters(self):
        """四个筛选条件与控件一起复位（换项目时用）。"""
        self.stage_filter = None
        self.kind_filter = None
        self.status_filter = None
        self.keyword_filter = ''
        self.library_view = False
        self.group_mode = '阶段'
        self.group_box.set('阶段')
        self._reset_filter_boxes()
        self._sync_stage_buttons()

    def _sync_view_filters(self):
        """全局库只支持类型/名称，避免展示无效的阶段和发布状态条件。"""
        state = 'disabled' if self.library_view else 'readonly'
        self.stage_box.configure(state=state)
        self.status_box.configure(state=state)

    def _keyword_changed(self, event=None):
        """关键字输入去抖 250ms：避免每个按键都全表筛一遍。"""
        if getattr(event, 'keysym', None) == 'Return':
            if self._filter_job is not None:
                self.page.win.after_cancel(self._filter_job)
            self._apply_filters()
            return
        self._schedule_filters()

    def _schedule_filters(self):
        win = getattr(self.page, 'win', None)
        if win is None:
            self._apply_filters()
            return
        if self._filter_job is not None:
            try:
                win.after_cancel(self._filter_job)
            except tk.TclError:
                pass
        self._filter_job = win.after(250, self._apply_filters)

    def _apply_filters(self):
        """把三项下拉与关键字收成筛选条件，再按条件重填列表。"""
        self._filter_job = None
        self.stage_filter = self.stage_labels.get(str(self.stage_box.get()))
        self.kind_filter = self.kind_labels.get(str(self.kind_box.get()))
        self.status_filter = self.status_labels.get(str(self.status_box.get()))
        if self.library_view:
            self.stage_filter = None
            self.status_filter = None
            self.stage_box.set('全部阶段')
            self.status_box.set('全部状态')
        self.keyword_filter = str(self.keyword_var.get()).strip()
        self.sort_mode = self.sort_box.get()
        self.group_mode = self.group_box.get()
        self._sync_stage_buttons()
        self._reload_current_view()

    def reference_from_library(self, row):
        """把全局素材库里的文件复制进当前项目（R3165，任务书 P3）。"""
        from domain import global_library_service
        from infra import file_index
        relative = str(row).split(':', 1)[1]
        library = file_index.read_global_dir()
        if library is None:
            self.page.status.set('尚未设置全局素材库目录，无法引用。')
            return
        root = getattr(self.page, 'root', None)
        if root is None:
            self.page.status.set('当前没有打开的项目，无法引用素材。')
            return
        try:
            target = global_library_service.copy_to_project(library, relative, root)
        except (OSError, ValueError) as exc:
            self.page.status.set('引用素材失败：' + str(exc))
            return
        self.page.status.set('已引用到当前项目：' + target.name)

    def configure_library(self):
        """选择用户素材库目录，登记后刷新当前库视图。"""
        from pathlib import Path
        from infra import file_index
        from ui_dialogs import FileDialog
        current = file_index.read_global_dir() or (Path.home() / 'Documents' / '漫剧助手素材库')
        selected = FileDialog(self.page.win).directory(title='选择全局素材库目录', initialdir=str(current))
        if not selected:
            return
        file_index.save_global_dir(selected)
        self.show_library()

    def add_to_library(self, row):
        """把选中的项目文件复制进共享库；配置未设时先完成目录选择。"""
        from pathlib import Path
        from domain import global_library_service
        from infra import file_index
        library = file_index.read_global_dir()
        if library is None:
            self.configure_library()
            library = file_index.read_global_dir()
        if library is None:
            return
        root = Path(self.page.root).resolve()
        source = Path(row)
        relative = source.resolve().relative_to(root).as_posix() if source.is_absolute() else str(row)
        target = global_library_service.copy_to_library(root, relative, library)
        self.page.status.set('已添加到全局素材库：' + target.name)

    def _filters_active(self):
        return any((self.stage_filter, self.kind_filter, self.status_filter, self.keyword_filter))

    def show_library(self):
        """切到全局素材库视图：只读库索引，不扫盘；未设置目录时提示用户先设置。"""
        from infra import file_index
        self._ensure_filter_state()
        self.library_view = True
        self._sync_view_filters()
        self.stage_filter = None
        self.status_filter = None
        self.keyword_filter = ''
        self._reset_filter_boxes()
        self.kind_box.set(next(text for text, value in self.kind_labels.items() if value == self.kind_filter))
        self._sync_stage_buttons()
        library = file_index.read_global_dir()
        if library is None:
            self.page.status.set('尚未设置全局素材库目录：请先指定一个跨项目共用的素材文件夹。')
            self._fill_global_list(None)
            return
        self._fill_global_list(library)

    def _fill_global_list(self, library):
        """全局库首次索引扫描同样在 Desktop 生命周期后台执行。"""
        self._request_index(library, library=True)

    # ── 阶段快捷图标列（R3094，任务书 P1）──────────────────────────────────
    def _ensure_filter_state(self):
        """首次装配前补齐筛选状态（宿主 ``__init__`` 不感知这些字段）。"""
        if not hasattr(self, 'stage_filter'):
            self.stage_filter = None
            self.kind_filter = None
            self.status_filter = None
            self.keyword_filter = ''
            self._filter_job = None
            self.library_view = False
            self.sort_mode = '类型'
            self.group_mode = '阶段'

    def _build_stage_rail(self):
        """建右缘阶段图标列：「全部」＋ 13 个阶段，顺序＝``pet_bus.STAGES``。"""
        from contract.pet_bus import STAGES, stage_name
        self._ensure_filter_state()
        self.stage_buttons = {}
        entries = [(None, STAGE_RAIL_ALL, '全部文件（剧本准备四类）')]
        entries += [(stage, STAGE_RAIL_ICONS.get(stage, '•'), stage_name(stage)) for stage in STAGES]
        for stage, glyph, tip in entries:
            button = SecondaryButton(self.stage_rail, text=glyph, width=0, style='RailIcon.TButton',
                                     command=lambda value=stage: self.show_stage(value))
            button.pack(side='top', pady=(SPACING['none'], SPACING['xs']))
            Tooltip(button, tip)
            self.stage_buttons[stage] = button
        self._sync_stage_buttons()
        # R3117（任务书 P2，Q5）：回收站入口放在图标列末尾——浏览／恢复走既有恢复窗，
        # 清空只删超过保留期的批次，物理删除仍只经 storage_maintenance。
        self._add_rail_action('♻', '回收站：浏览与恢复已删除的文件', 'open_recycle_recovery')
        self._add_rail_action('🗑', '清空过期回收站（保留 %d 天）' % _retention_days(), 'purge_expired_recycle')
        # R3143（任务书 P3，Q11）：全局素材库视图——跨项目的共享素材，按库相对路径列出。
        library = SecondaryButton(self.stage_rail, text='🗂', width=0, style='RailIcon.TButton',
                                  command=self.show_library)
        library.pack(side='top', pady=(SPACING['none'], SPACING['xs']))
        Tooltip(library, '全局素材库：跨项目的共享素材（可在设置里指定目录）')
        self.library_button = library
        settings = SecondaryButton(self.stage_rail, text='⚙', width=0, style='RailIcon.TButton',
                                   command=self.configure_library)
        settings.pack(side='top', pady=(SPACING['none'], SPACING['xs']))
        Tooltip(settings, '设置全局素材库目录')
        self.library_settings_button = settings

    def _add_rail_action(self, glyph, tip, method_name):
        """在图标列末尾追加一个动作钮；宿主没有该动作时只留按钮不绑回调。"""
        action = getattr(self.page, method_name, None)
        command = (lambda: self.page.safe(action)) if callable(action) else None
        button = SecondaryButton(self.stage_rail, text=glyph, width=0, style='RailIcon.TButton',
                                 command=command)
        button.pack(side='top', pady=(SPACING['none'], SPACING['xs']))
        Tooltip(button, tip)
        return button

    def _sync_stage_buttons(self):
        """当前阶段高亮：选中的图标换成按下风格，其余回到普通风格。"""
        for stage, button in getattr(self, 'stage_buttons', {}).items():
            style = 'Selected.RailIcon.TButton' if stage == self.stage_filter else 'RailIcon.TButton'
            try:
                button.configure(style=style)
            except tk.TclError:
                return

    def show_stage(self, stage=None):
        """点阶段图标：同步下拉框，再按筛选条件重填（``None``＝不限阶段）。"""
        self._ensure_filter_state()
        self.library_view = False
        self.stage_filter = stage
        label = next((text for text, value in self.stage_labels.items() if value == stage), '全部阶段')
        box = getattr(self, 'stage_box', None)
        if box is not None:
            box.set(label)
        self._sync_stage_buttons()
        self._reload_current_view()

    def _fill_index_list(self):
        """默认全部与筛选视图共用全项目索引，首次重建不阻塞主线程。"""
        self._request_index(getattr(self.page, 'root', None))
