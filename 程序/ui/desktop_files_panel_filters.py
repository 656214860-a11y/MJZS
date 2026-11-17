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

# R3094（任务书 P1，Q8 补充需求）：停靠面板右缘的阶段快捷图标列，顺序＝pet_bus.STAGES。
# P1 用 Unicode 符号兜底（用户已确认先符号、后换 PNG 图标）；每个图标都带 Tooltip 中文名。
STAGE_RAIL_ICONS = {
    'script': '📝', 'script_structure': '🧾', 'storyboard': '🎬', 'animatic': '🎞',
    'assets': '🎨', 'continuity': '🧩', 'final': '✅', 'keyframe': '🖼',
    'previs': '🧊', 'video': '📹', 'audio': '🎙', 'edit': '✂', 'delivery': '📦',
}
STAGE_RAIL_ALL = '📁'          # 「全部」：回到剧本准备四类视图
STAGE_FILTER_ROW_CATEGORY = 'index'   # 索引行在右键菜单里与剧本行区分

# 下拉框与输入框的宽度以「字符」计，从 token 派生，避免新增数字字面量（test_token_boundary）。
FILTER_STAGE_WIDTH = max(6, SPACING['sm'])
FILTER_BOX_WIDTH = max(4, SPACING['xs'])
FILTER_KEYWORD_WIDTH = max(4, SPACING['xs'])


def _retention_days():
    """回收站保留期（天）：唯一定义在 ``storage_maintenance``，这里只读不复制数字。"""
    from storage_maintenance import RECYCLE_RETENTION_DAYS
    return RECYCLE_RETENTION_DAYS


class FilesPanelFilterMixin:
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
        self.keyword_entry = LineInput(row_two, textvariable=self.keyword_var, width=FILTER_KEYWORD_WIDTH)
        self.keyword_entry.pack(side='left', fill='x', expand=True, padx=(SPACING['xs'], SPACING['none']))
        self.keyword_entry.bind('<KeyRelease>', self._keyword_changed)
        Tooltip(self.keyword_entry, '按文件名关键字筛选（回车立即生效）')
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
        self._reset_filter_boxes()
        self._sync_stage_buttons()

    def _keyword_changed(self, event=None):
        """关键字输入去抖 250ms：避免每个按键都全表筛一遍。"""
        if getattr(event, 'keysym', None) not in (None, 'Return') and self._filter_job is not None:
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
        self.keyword_filter = str(self.keyword_var.get()).strip()
        self._sync_stage_buttons()
        self._reload_current_view()

    def _filters_active(self):
        return any((self.stage_filter, self.kind_filter, self.status_filter, self.keyword_filter))

    def show_library(self):
        """切到全局素材库视图：只读库索引，不扫盘；未设置目录时提示用户先设置。"""
        from infra import file_index
        self._ensure_filter_state()
        self.library_view = True
        self.stage_filter = None
        self.keyword_filter = ''
        library = file_index.read_global_dir()
        if library is None:
            self.page.status.set('尚未设置全局素材库目录：请先指定一个跨项目共用的素材文件夹。')
            self._fill_global_list(None)
            return
        self._fill_global_list(library)

    def _fill_global_list(self, library):
        """按全局库索引填表；行 id 用 ``库相对`` 路径，路径前带库根标记便于查看。"""
        from infra import file_index
        self.cancel_script_load()
        self.script_tree.delete(*self.script_tree.get_children())
        self.script_row_details.clear()
        self.script_row_category.clear()
        if library is None:
            return
        try:
            found = file_index.search_global(library, kind=self.kind_filter)
        except (OSError, ValueError):
            found = []
        for row in found:
            item_id = 'library:' + row.path
            self.script_row_details[item_id] = '%s · %s · %s' % (row.title or row.path, row.kind, str(library))
            self.script_row_category[item_id] = STAGE_FILTER_ROW_CATEGORY
            self.script_tree.insert('', 'end', iid=item_id, text='',
                                    values=('[素材库] ' + row.path.split('/')[-1],))

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
        """用项目文件索引填表：只读索引缓存，不扫盘；条件取自筛选条四项。"""
        from infra import file_index
        self.cancel_script_load()
        self.script_tree.delete(*self.script_tree.get_children())
        self.script_row_details.clear()
        self.script_row_category.clear()
        root = getattr(self.page, 'root', None)
        if root is None:
            return
        try:
            found = file_index.search(root, stage=self.stage_filter, kind=self.kind_filter,
                                      status=self.status_filter, name=self.keyword_filter)
        except (OSError, ValueError):
            found = []
        for row in found:
            name = row.path.split('/')[-1]
            label = '[缺失] ' if row.missing else ''
            self.script_row_details[row.path] = '%s · %s · %s' % (
                row.title or name, row.kind, row.path)
            self.script_row_category[row.path] = STAGE_FILTER_ROW_CATEGORY
            self.script_tree.insert('', 'end', iid=row.path, text='', values=(label + name,))
