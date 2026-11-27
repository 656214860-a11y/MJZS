# -*- coding: utf-8 -*-
"""主界面「项目文件」全局入口与右侧停靠面板（R2962，自 ``_WritingPage`` 迁入，REQ-S01-90）。

原「剧本准备」页内 ``script_box`` 文件栏改为全局固定目录：R2998 起入口从
标题行迁到内容区右缘独立图标列（``rail``，聊天区滑块右侧、与画布同高，
图标在列顶、下方留白给后续图标功能），点击后右侧停靠面板向左展开、主内容
区收窄；默认隐藏，切页／切项目自动收起，面板外按下或 Esc 关闭。文件名列宽
按最长文件名动态调整（``script_width_sizer`` 驱动面板宽）。默认通过后台项目
索引按阶段分组；索引加载与批次渲染在 ``desktop_files_panel_index``，剧本四类
沿用采用、确认和历史操作。``self.page`` 即 ``Desktop`` 实例。
"""
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from ui.desktop_files_panel_filters import (
    COLUMN_TITLES, FilesPanelFilterMixin, FilesPanelStageViewMixin,
    SORTABLE_COLUMNS, STAGE_FILTER_ROW_CATEGORY, STAGE_RAIL_ALL,
    append_kind_menu, cancel_auto_refresh, import_into_stage, import_suffixes,
    install_auto_refresh, schedule_auto_refresh, teardown_auto_refresh,
    PANEL_META_WIDTH, PANEL_PREVIEW_COL_WIDTH, SCRIPT_NAME_CELL_PAD,
)

from ui.desktop_file_card import TreeRowCard, script_row_card
from ui.desktop_page_registry import PAGE_ACCOUNT, PAGE_SITES
from ui.desktop_writing_snapshots import WritingSnapshotsMixin
from responsive_ui import fit_row_height, row_toggle_target
from ui.ui_icons import IconLoader
from ui.ui_popup import measure_text_width
from ui_tokens import SCRIPT_FILE_FONT, SCRIPT_FILE_MAX_ROWS, SPACING
from ui_widgets import (BaseDialog, DataTable, DescriptionBlock, SecondaryButton,
                        Tooltip, ask_string)
from ui.writing_page_controller import ScriptListLoadController

# R3150：入口钮左右 padding 收 0——右 padding 再收半档图标再右移半步贴边，
# 左 padding 同步收 0 使图标与左侧聊天框间距减半（实测 8px→4px，余量即按钮内边距）。

# R2998：文件名列宽不再写死——面板宽度由 0 高 sizer 驱动，按最长文件名量宽。
SCRIPT_LIST_MIN_WIDTH = SPACING['sm'] * 23      # 沿用原固定列宽下限（184）
SCRIPT_PANEL_MAX_SHARE = 0.5                     # 面板最多占内容区一半宽
SCRIPT_PANEL_USER_MAX_SHARE = 0.7                # 手动拖动时面板最多占内容区 70% 宽
SCRIPT_PANEL_DEFAULT_WIDTH = SPACING['sm'] * 38
SCRIPT_PANEL_MAX_WIDTH = SPACING['sm'] * 60      # 480：更长的文件名靠悬停看全
SCRIPT_CELL_OVERHEAD = SPACING['md'] * 4         # 48：格内边距＋滚动条＋面板留白
# R4005（任务书 L4-U3，Q3）：文件名列优先——属性列放不进面板内宽时按
# meta→size→kind→mtime 顺序整列隐藏（displaycolumns，列定义与行数据不动），
# 只剩文件名列仍不够宽时文件名中间省略；隐藏列的内容经悬停提示查看。
# 省略实现（_apply_name_labels/_elide_label 与留白常量）在 index mixin。
SCRIPT_NAME_MIN_WIDTH = SPACING['sm'] * 12       # 96：与 name 列 minwidth 一致
SCRIPT_PANEL_EDGE = SPACING['xs']                # 4：表格边框与取整余量
SCRIPT_VSCROLL_WIDTH = SPACING['lg']             # 16：竖滚动条预留宽
SCRIPT_AUX_HIDE_ORDER = (('meta', PANEL_META_WIDTH), ('size', SPACING['sm'] * 10),
                         ('mtime', SPACING['sm'] * 14), ('kind', SPACING['sm'] * 9),
                         ('status', SPACING['sm'] * 8))


def _configure_panel_columns(panel):
    """列序：文件名 | 状态 | 类型 | 时间 | 大小 | 时长／分辨率；除文件名与时长／分辨率外其余列支持表头排序。"""
    tree = panel.script_tree
    tree.configure(columns=('name', 'status', 'kind', 'mtime', 'size', 'meta'))
    columns = (('name', COLUMN_TITLES['name'], SCRIPT_LIST_MIN_WIDTH),
               ('status', COLUMN_TITLES['status'], SPACING['sm'] * 8),
               ('kind', COLUMN_TITLES['kind'], SPACING['sm'] * 9),
               ('mtime', COLUMN_TITLES['mtime'], SPACING['sm'] * 14),
               ('size', COLUMN_TITLES['size'], SPACING['sm'] * 10),
               ('meta', COLUMN_TITLES['meta'], PANEL_META_WIDTH))
    for key, title, width in columns:
        cmd = (lambda c=key: panel.sort_by_column(c)) if key in SORTABLE_COLUMNS else ''
        tree.heading(key, text=title, anchor='center', command=cmd)
        tree.column(key, width=width, minwidth=SCRIPT_NAME_MIN_WIDTH if key == 'name' else width,
                    anchor='w', stretch=(key == 'name'))


def _popup_script_menu(panel, tree, event):
    """文件行右键：按使用频率排列，字数接近；删除放最后。状态只有定稿，没有「按段落采用」。"""
    row = tree.identify_row(event.y)
    if not row or panel.is_file_group(row):
        return None
    if row not in tree.selection():
        tree.selection_set(row)
    panel.keep_one_selection(tree)
    menu = panel.page.writing_page_services.context_menu(panel.page.win)
    if len(tree.selection()) > 1 and panel.script_row_category.get(row) != STAGE_FILTER_ROW_CATEGORY:
        menu.command('删除', lambda: panel.page.safe(panel.delete_script))
        return menu.popup(event)
    menu.command('查看', lambda: panel.page.safe(panel.open_script_file))
    if panel.script_row_category.get(row) == STAGE_FILTER_ROW_CATEGORY:
        if str(row).startswith('library:'):
            menu.command('引用', lambda: panel.page.safe(lambda: panel.reference_from_library(row)))
        elif len(tree.selection()) == 1:
            menu.command('改名', lambda: panel.page.safe(lambda: panel.rename_index_file(row)))
            append_kind_menu(panel, menu, row)
            menu.command('入库', lambda: panel.page.safe(lambda: panel.add_to_library(row)))
        else:
            menu.command('入库', lambda: panel.page.safe(lambda: panel.add_to_library(row)))
        menu.command('定位', lambda: panel.page.safe(panel.show_in_folder))
        menu.command('另存', lambda: panel.page.safe(panel.save_as_file))
        if len(tree.selection()) == 1:
            panel._offer_menu_hooks(menu, panel._row_abs_path(row))
        if not str(row).startswith('library:'):
            menu.command('删除', lambda: panel.page.safe(panel.delete_index_files))
        return menu.popup(event)
    category = panel.script_row_category.get(row, 'script')
    if category == 'script':
        menu.command('定稿', lambda: panel.page.safe(panel.adopt_script))
    else:
        stages = {'setting': '项目设定', 'outline': '剧本大纲', 'character': '角色卡'}
        stage = stages[category]
        from orchestrator.writing_unconfirm import preparation_confirmed_stages
        if stage in preparation_confirmed_stages(panel.page.root):
            menu.command('撤定稿', lambda: panel.page.safe(lambda: panel.unconfirm_preparation(stage)))
        menu.command('定稿', lambda: panel.page.safe(lambda: panel.confirm_document(stage)))
        menu.command('快照', lambda: panel.page.safe(lambda: panel.show_preparation_snapshots(stage)))
    menu.command('改名', lambda: panel.page.safe(panel.rename_script))
    append_kind_menu(panel, menu, row)
    menu.command('定位', lambda: panel.page.safe(panel.show_in_folder))
    menu.command('另存', lambda: panel.page.safe(panel.save_as_file))
    menu.command('入库', lambda: panel.page.safe(lambda: panel.add_to_library(row)))
    menu.command('删除', lambda: panel.page.safe(panel.delete_script))
    return menu.popup(event)
# R3196 后续（任务书 M5，REQ-S01-95/96）：预览列图元长边与列宽、时长／分辨率列宽都从 token 派生；
# 定义在 desktop_files_panel_filters（本模块自它导入），视频封面 16:9（40×22）与音频波形
# （40×13）落在字高行内，行高仍由字体 token 量。


class FilesPanelResizeMixin:
    """右侧「项目文件」停靠面板的鼠标拖动调宽逻辑（混入 ProjectFilesPanel）。

    只读写 self 上的拖动状态与 _user_panel_width，不直接触碰 Tk 几何之外的业务。
    """

    _user_panel_width = None
    _resize_start = None

    def _manual_cap(self):
        """手动宽度上限：内容区宽的 70%，至少 SCRIPT_LIST_MIN_WIDTH。"""
        try:
            host = getattr(self.page, 'panel_area', None) or self.script_box.master
            content_width = int(host.winfo_width())
        except (tk.TclError, AttributeError, TypeError, ValueError):
            content_width = 0
        if content_width > 0:
            return max(SCRIPT_LIST_MIN_WIDTH, int(content_width * SCRIPT_PANEL_USER_MAX_SHARE))
        return max(SCRIPT_LIST_MIN_WIDTH, getattr(self, '_user_panel_width', None) or SCRIPT_LIST_MIN_WIDTH)

    def _start_resize(self, event):
        sizer = getattr(self, 'script_width_sizer', None)
        width = SCRIPT_LIST_MIN_WIDTH
        if sizer is not None:
            try:
                width = int(sizer.cget('width'))
            except (tk.TclError, ValueError):
                width = SCRIPT_LIST_MIN_WIDTH
        self._resize_start = (width, getattr(event, 'x_root', 0))
        return None

    def _do_resize(self, event):
        start = getattr(self, '_resize_start', None)
        if not start:
            return None
        start_width, start_x = start
        try:
            new_width = start_width + (start_x - getattr(event, 'x_root', start_x))
        except (TypeError, ValueError):
            return None
        cap = self._manual_cap()
        new_width = max(SCRIPT_LIST_MIN_WIDTH, min(new_width, cap))
        self._user_panel_width = new_width
        sizer = getattr(self, 'script_width_sizer', None)
        if sizer is not None:
            try:
                sizer.configure(width=new_width)
            except tk.TclError:
                pass
        return None

    def _end_resize(self, event):
        self._resize_start = None
        try:
            self._fit_script_width()
        except tk.TclError:
            pass
        fit = getattr(self.page, 'fit_content', None)
        if callable(fit):
            try:
                fit()
            except tk.TclError:
                pass
        return None

    def _restore_auto_width(self, event):
        self._user_panel_width = None
        self._resize_start = None
        try:
            self._fit_script_width()
        except tk.TclError:
            pass
        fit = getattr(self.page, 'fit_content', None)
        if callable(fit):
            try:
                fit()
            except tk.TclError:
                pass
        return 'break'


def _build_stage_rail_state(panel):
    """右缘阶段图标列的装配实现（REQ-UI-SIDEBAR-1：列部件抽为 ExpandIconColumn）。

    返回要落到 ``panel`` 上的属性字典；``ProjectFilesPanel._build_stage_rail``
    经 ``vars(self).update`` 落位——这些属性名与 ``FilesPanelFilterMixin``
    历史构建路径一致，写者登记只计 mixin 单侧，避免双写者棘轮误报。
    全部动作位于同一滚动列；
    ``frame=panel.stage_rail`` 收养既有停靠框，宽度钉法不变。
    """
    from contract.pet_bus import STAGES, stage_name
    from ui.desktop_expand_column import ExpandIconColumn, align_stage_rows
    from ui.desktop_files_panel_filters import STAGE_RAIL_ICONS
    from ui_tokens import COLORS, NAV_PRIMARY_ICON_SIZE
    panel._ensure_filter_state()
    column = ExpandIconColumn(panel.script_box, panel.page.win,
                              bg=COLORS['background_primary'],
                              frame=panel.stage_rail, scrollbar=False,
                              keys=True, icon_size=NAV_PRIMARY_ICON_SIZE)
    state = {'_rail_column': column}

    def rail_action(key, icon_name, glyph, tip, method_name):
        action = getattr(panel.page, method_name, None)
        command = (lambda: panel.page.safe(action)) if callable(action) else None
        return column.add(key, icon_name, glyph, tip, command)

    stage_buttons = {}
    for stage in STAGES:
        stage_buttons[stage] = column.add(
            stage, stage + '_files', STAGE_RAIL_ICONS.get(stage, '•'),
            stage_name(stage) + '：查看该阶段文件；再点已选图标恢复跟随当前页',
            lambda value=stage: panel.show_stage(value))
    state['stage_buttons'] = stage_buttons
    state['recycle_button'] = rail_action(
        'recycle', 'recycle', '♻', '回收站：浏览与恢复已删除的文件',
        'open_recycle_recovery')
    state['library_button'] = column.add(
        'library', 'library', '🗂',
        '全局素材库：跨项目的共享素材（可在设置里指定目录）',
        panel.show_library)
    state['library_settings_button'] = column.add(
        'library_settings', 'library_settings', '📂',
        '设置全局素材库目录', panel.configure_library)
    column.finalize()
    align_stage_rows(panel.page, column, stage_buttons['script'])
    state['stage_rail_scroller'] = column.scroller
    state['stage_rail_form'] = column.form
    return state


# ── REQ-S01-103：「导入文件」（UX-FP-IMPORT）─────────────────────────────────

class _ImportConflictDialog(BaseDialog):
    """同名三选窗：覆盖（危险）／保留两份／取消；关闭与 Esc 一律按取消。"""

    def __init__(self, parent, name):
        self.result = 'cancel'
        super().__init__(parent, '同名文件')
        DescriptionBlock(self.content, text=('目标目录已有同名文件「%s」。'
                         '覆盖会替换现有文件；保留两份自动改名导入；取消不改动。' % name)).pack(fill='x')
        self.add_action('取消', lambda: self._pick('cancel'))
        self.add_action('保留两份', lambda: self._pick('rename'))
        self.add_action('覆盖', lambda: self._pick('overwrite'), dangerous=True)

    def _pick(self, value):
        self.result = value
        self.close()

    def close(self):
        if self.result is None:
            self.result = 'cancel'
        super().close()


def _ask_import_conflict(parent, name):
    """同步问一次同名决策；父窗在询问期间销毁一律按取消处理。"""
    dialog = _ImportConflictDialog(parent, name)
    try:
        dialog.wait_window()
    except tk.TclError:
        return 'cancel'
    return dialog.result


def _import_status_text(result):
    """导入结果的状态栏文案：成功、同名跳过与被拒的都点名。"""
    parts = []
    imported = result.get('imported') or ()
    if imported:
        parts.append('已导入 %d 份：%s' % (len(imported), '、'.join(path.name for path in imported)))
    skipped = result.get('skipped') or ()
    if skipped:
        parts.append('同名取消 %d 份：%s' % (len(skipped), '、'.join(skipped)))
    rejected = result.get('rejected') or ()
    if rejected:
        parts.append('未导入 %d 份：%s' % (len(rejected),
                     '；'.join('%s（%s）' % item for item in rejected)))
    return '；'.join(parts) or '没有可导入的文件'


class FilesPanelImportMixin:
    """REQ-S01-103：面板头部「导入文件」——本机文件复制进当前阶段写入目录。"""

    def _import_stage(self):
        """导入目标阶段：面板当前显示的阶段优先；素材库／全部视图回落当前页阶段。"""
        if getattr(self, 'library_view', False):
            return self._page_stage()
        return getattr(self, 'stage_filter', None) or self._page_stage()

    def _ask_import_conflict(self, name):
        return _ask_import_conflict(getattr(self.page, 'win', None), name)

    def set_import_handler(self, stage, handler):
        """阶段页登记的导入分流：``handler(路径列表) -> 结果 dict``，随页码失效。

        DES-S04-25：只登记当前页；``page_index`` 变化后登记自动视为失效，
        行为回落到 ``import_into_stage`` 默认导入，其他阶段完全不变。
        """
        if not hasattr(self, '_import_handlers'):
            self._import_handlers = {}
        if handler is None:
            self._import_handlers.pop(stage, None)
        else:
            self._import_handlers[stage] = (getattr(self.page, 'page_index', None), handler)

    def set_menu_handler(self, stage, hook):
        """阶段页登记的文件右键挂钩：``hook(menu, 绝对路径)``，同样随页码失效。"""
        if not hasattr(self, '_menu_handlers'):
            self._menu_handlers = {}
        if hook is None:
            self._menu_handlers.pop(stage, None)
        else:
            self._menu_handlers[stage] = (getattr(self.page, 'page_index', None), hook)

    def _registered_hook(self, kind, key):
        """当前页登记的挂钩：登记页码与当前页不一致时视为已失效。"""
        entry = getattr(self, '_' + kind + '_handlers', {}).get(key)
        if entry is None or entry[0] != getattr(self.page, 'page_index', None):
            return None
        return entry[1]

    def _offer_menu_hooks(self, menu, path):
        """索引行右键：把当前页登记的文件挂钩逐个放行，挂钩自己判定路径范围。"""
        if path is None:
            return
        for entry in (getattr(self, '_menu_handlers', None) or {}).values():
            if entry[0] == getattr(self.page, 'page_index', None):
                entry[1](menu, path)

    def import_files(self):
        """入口动作：多选本机文件，复制进当前阶段写入目录，走面板现有索引刷新。"""
        root = getattr(self.page, 'root', None)
        if root is None:
            self.page.status.set('当前没有打开的项目，无法导入文件')
            return
        stage = self._import_stage()
        allowed = import_suffixes(stage) if stage else frozenset()
        if not stage or not allowed:
            self.page.status.set('请先点选要导入的阶段图标')
            return
        from contract.pet_bus import stage_name
        patterns = ' '.join('*' + suffix for suffix in sorted(allowed))
        paths = self.page.file_dialog.open_files(
            parent=getattr(self.page, 'win', None),
            title='导入文件到「%s」' % stage_name(stage),
            filetypes=[('可导入文件', patterns), ('全部文件', '*.*')])
        if not paths:
            return
        handler = self._registered_hook('import', stage)
        if handler is not None:
            result = handler(list(paths))
        else:
            result = import_into_stage(root, stage, paths, conflict=self._ask_import_conflict)
        if getattr(self, 'library_view', False):
            self.show_stage(stage)
        else:
            self.fill_script_list()
        self.page.status.set(_import_status_text(result))


def _append_delete_command(menu, safe, action):
    """REQ-UI-UNIFY-1：右键菜单底部危险操作统一前置分隔线。"""
    menu.separator()
    menu.command('删除', lambda: safe(action))


class ProjectFilesPanel(FilesPanelResizeMixin, FilesPanelStageViewMixin, FilesPanelImportMixin, FilesPanelFilterMixin, WritingSnapshotsMixin):
    """内容区右缘图标列「项目文件」入口＋右侧停靠文件列表；``page`` 是 ``Desktop`` 实例。"""

    def __init__(self, page):
        self.page = page
        self._open = False
        self._panel_root = None
        self._button_bind = self._escape_bind = None
        self._fit_width_job = None

    def build(self):
        """建入口图标列与停靠面板；初始收起，文件列表默认隐藏（REQ-S01-90）。"""
        page = self.page
        image = IconLoader.nav_icon(page.win, 'project_files')
        # R3060：图标列挂 panel_area（panel_dock 的父级）而非画布列——面板打开时
        # 停靠列从图标列左侧让位，图标恒为内容区最右竖条。
        area = getattr(page, 'panel_area', None) or page.canvas.master
        # R2998：入口从标题行迁到内容区右缘独立图标列——先于任何停靠面板 pack，
        # 恒为该容器最右竖条（与画布同高，图标在列顶、下方留白给后续图标）。
        self.rail = ttk.Frame(area)
        self.rail.pack(side='right', fill='y')
        # Tk 空 frame 的请求宽度只增不收：常驻一个 0 尺寸占位子件，让列在
        # 按钮隐藏时塌回约 1px，而不是卡住上次的宽度。
        self.rail_sizer = tk.Frame(self.rail, width=0, height=0)
        self.rail_sizer.pack(side='bottom')
        self.button = SecondaryButton(self.rail, text='', image=image,
                                      compound='image' if image is not None else 'text',
                                      command=self.toggle, style='RailIcon.TButton')
        import_image = IconLoader.nav_icon(page.win, 'project_new')
        if import_image is not None:
            self.import_button = SecondaryButton(
                self.rail, text='', image=import_image, compound='image', width=0,
                command=lambda: page.safe(self.import_files), style='RailIcon.TButton')
        else:
            self.import_button = SecondaryButton(
                self.rail, text=STAGE_RAIL_ALL, width=0,
                command=lambda: page.safe(self.import_files), style='RailIcon.TButton')
        Tooltip(self.import_button, '导入文件到当前阶段目录')
        self._pack_button()
        if getattr(page, 'nav', None):
            source = page.nav[0]
            def align_entry(_event=None):
                if self.button.winfo_ismapped() and source.winfo_ismapped():
                    top = (source.winfo_rooty() + page.sidebar_canvas.canvasy(0)
                           + (source.winfo_height() - self.button.winfo_reqheight()) / 2)
                    offset = max(0, round(top - self.rail.winfo_rooty()))
                    current = self.button.tk.splitlist(self.button.pack_info()['pady'])
                    if offset != int(current[0]):
                        self.button.pack_configure(pady=(offset, SPACING['xs']))
            page.sidebar_scroll.form.bind('<Configure>', align_entry, add='+')
            self.rail.bind('<Configure>', align_entry, add='+')
            source.bind('<Configure>', align_entry, add='+')
            source.bind('<Map>', align_entry, add='+')
            self.button.bind('<Configure>', align_entry, add='+')
            self.button.bind('<Map>', align_entry, add='+')
        Tooltip(self.button, '项目文件')
        page.files_button = self.button

        # R3060：面板停靠列独立于画布列（canvas.master 已是 stage_area），输入框与聊天框同宽收窄；
        # 停靠框/分隔线都进 panel_dock，面板宽度不再与 stage_area 竞争需求宽度。
        dock = getattr(page, 'panel_dock', None)
        area = dock or getattr(page, 'panel_area', None) or page.canvas.master
        self._dock = dock if dock is area else None
        self.script_box = ttk.Frame(area, padding=(SPACING['none'], SPACING['xs'], SPACING['xs'], SPACING['xs']))
        self.sep = ttk.Separator(area, orient='vertical')
        self.resize_grip = ttk.Frame(area, width=SPACING['xs'], cursor='sb_h_double_arrow')
        Tooltip(self.resize_grip, '拖动调整面板宽度，双击恢复默认宽度')
        self.resize_grip.bind('<Button-1>', self._start_resize, add='+')
        self.resize_grip.bind('<B1-Motion>', self._do_resize, add='+')
        self.resize_grip.bind('<ButtonRelease-1>', self._end_resize, add='+')
        self.resize_grip.bind('<Double-Button-1>', self._restore_auto_width, add='+')
        # R3137（任务书 P1）：阶段快捷图标列在停靠面板**右缘**、按 pet_bus.STAGES 垂直排列；
        # 先于列表 pack，右缘竖条优先占整列高，列表随后吃剩余区域。
        self.stage_rail = ttk.Frame(self.script_box)
        self.stage_rail.pack(side='right', fill='y', padx=(SPACING['xs'], SPACING['none']))
        self._build_stage_rail()
        self.script_header = ttk.Frame(self.script_box)
        self.script_header.pack(fill='x', pady=(SPACING['none'], SPACING['xs']))
        self.script_title = ttk.Label(self.script_header, text='项目文件', style='Muted.TLabel')
        self.script_title.pack(side='left')
        # 筛选条（半宽搜索框＋分组下拉与二级目录卡）与阶段快捷图标列由 FilesPanelFilterMixin 提供。
        self._build_filter_bar()
        self.script_row_details = {}
        self.script_row_category = {}
        tips = lambda item: self.script_row_details.get(item, '')
        table = DataTable(
            self.script_box,
            columns=[('name', '文件名', SCRIPT_LIST_MIN_WIDTH),
                     ('status', '状态', SPACING['sm'] * 8),
                     ('kind', '类型', SPACING['sm'] * 9),
                     ('mtime', '时间', SPACING['sm'] * 14),
                     ('size', '大小', SPACING['sm'] * 10)],
            show='headings', height=1, selectmode='extended', style='Script.Treeview',
            auto_hide_scrollbars=True, empty_text='', horizontal=True)
        self.script_list = table
        self.script_tree = table.tree
        self.script_tree.heading('name', text='文件名', anchor='center')
        self.script_tree.column('name', width=SCRIPT_LIST_MIN_WIDTH,
                                minwidth=SPACING['sm'] * 12, anchor='w', stretch=True)
        for column in ('status', 'kind', 'mtime', 'size'):
            self.script_tree.column(column, stretch=False)
        self._apply_columns(True)
        self._sync_sort_headings()
        self.script_tree.heading('#0', text='分组／预览')
        self.script_tree.column('#0', width=PANEL_PREVIEW_COL_WIDTH, minwidth=SPACING['none'], stretch=False)
        self.page.script_file_tips = TreeRowCard(self.script_tree, tips)
        self.script_list.pack(fill='both', expand=True, pady=(SPACING['none'], SPACING['xs']))
        self.script_list.grid_propagate(False)
        self.script_width_sizer = tk.Frame(self.script_box, width=SCRIPT_PANEL_DEFAULT_WIDTH, height=0)
        self.script_width_sizer.pack()
        ttk.Style(self.script_tree).configure('Script.Treeview', font=SCRIPT_FILE_FONT, indent=SPACING['sm'])
        fit_row_height(self.script_tree, style='Script.Treeview')
        area.bind('<Configure>', self._on_files_area_resize, add='+')
        self.script_tree.bind('<Configure>', self._on_files_area_resize, add='+')
        self.script_loader = ScriptListLoadController(('setting', 'outline', 'character', 'script'))
        self.script_load_job = None
        self.script_box.bind('<Destroy>', self.cancel_script_load, add='+')
        self.script_tree.bind('<Double-1>', self.open_script_file)
        self.script_tree.bind('<Return>', self.open_script_file)
        self.script_tree.bind('<<TreeviewSelect>>', self.keep_one_selection, add='+')
        self.script_tree.bind('<<TreeviewSelect>>', self._notify_file_select, add='+')
        self.script_tree.bind('<Button-3>', lambda event, tree=self.script_tree: self.script_menu(tree, event))
        install_auto_refresh(self)
        page.script_box = self.script_box
        page.script_tree = self.script_tree
        page.script_title = self.script_title
        page.script_row_category = self.script_row_category
        page.refresh_script_list = self.fill_script_list
        page.open_script_file = self.open_script_file
        self.sync_entry()

    # ── 阶段快捷图标列（REQ-UI-SIDEBAR-1：列部件抽为 ui.desktop_expand_column.ExpandIconColumn）──
    def _build_stage_rail(self):
        """建右缘阶段图标列：13 个阶段＋回收站／清空／素材库动作（装配在模块级函数）。"""
        vars(self).update(_build_stage_rail_state(self))
        self._sync_stage_buttons()

    # ── 入口显隐与开合（REQ-S01-90）────────────────────────────────────────
    def _apply_columns(self, media):
        _configure_panel_columns(self)

    def _entry_allowed(self):
        """有项目且当前页不是会员账户／参考网站时才显示入口。"""
        if getattr(self.page, 'root', None) is None:
            return False
        return getattr(self.page, 'page_index', None) not in (PAGE_SITES, PAGE_ACCOUNT)

    def _pack_button(self):
        """「项目文件」与正下方「导入文件到当前阶段目录」一起挂进最右外轨。"""
        if not self.button.winfo_manager():
            self.button.pack(side='top', fill='x', padx=SPACING['none'],
                             pady=(SPACING['sm'], SPACING['xs']))
        imp = getattr(self, 'import_button', None)
        if imp is not None and not imp.winfo_manager():
            imp.pack(side='top', fill='x', padx=SPACING['none'],
                     pady=(SPACING['none'], SPACING['xs']))

    def sync_entry(self):
        """按当前项目与页码显隐外轨入口钮；不满足时收起面板（列随钮塌缩）。"""
        if not self._entry_allowed():
            self.collapse()
            for btn in (self.button, getattr(self, 'import_button', None)):
                if btn is not None and btn.winfo_manager():
                    btn.pack_forget()
            return
        self._pack_button()

    def project_changed(self):
        """``_show_reset_page`` 每次换页调用：项目根变化时收起并允许下次打开重扫。"""
        self._sync_select_page()
        root = getattr(self.page, 'root', None)
        if root == self._panel_root:
            self.sync_entry()
            if self._open:
                self.fill_script_list()
            return
        self._panel_root = root
        # R3137（任务书 P1，Q25）：换项目时阶段／类型／状态／关键字筛选全部复位。
        self._reset_filters()
        self.collapse()
        self.sync_entry()

    def _reload_current_view(self):
        """默认全部、筛选与全局库统一采用后台索引视图。"""
        self._sync_view_filters()
        if getattr(self, 'library_view', False):
            from infra import file_index
            self._fill_global_list(file_index.read_global_dir())
        else:
            self._fill_index_list()

    def toggle(self):
        if self._open:
            self.collapse()
        else:
            self.open_panel()

    def open_panel(self):
        """向左侧打开右侧停靠面板：主内容区收窄，列表立即重扫。"""
        if self._open or not self._entry_allowed():
            return
        self._open = True
        # R3060：分隔线贴停靠列左缘、文件框吃满列宽；停靠列此刻才打包进 panel_area
        # （常驻空包会让 Tk 卡住需求宽度，画布被永久挤窄）。
        if self._dock is not None:
            # 先把子件装进未映射的停靠列（需求宽度先算好），再把整列打包进 panel_area，
            # 避免空列先占位、内容装入后需求宽度在小窗下传不进来。
            self.sep.pack(side='left', fill='y')
            self.resize_grip.pack(side='left', fill='y')
            self.script_box.pack(side='left', fill='both', expand=True)
            if not self._dock.winfo_manager():
                self._dock.pack(side='right', fill='y')
        else:
            self.script_box.pack(side='right', fill='both', expand=True)
            self.resize_grip.pack(side='right', fill='y')
            self.sep.pack(side='right', fill='y')
        self._bind_outside()
        self._reload_current_view()
        schedule_auto_refresh(self)
        fit = getattr(self.page, 'fit_content', None)
        if callable(fit):
            fit()

    def collapse(self):
        """收起停靠面板：停批次、摘监听、让出宽度并重排。"""
        if not self._open:
            return
        self._open = False
        self._close_group_menu()
        cancel_auto_refresh(self)
        self._displayed_index_context = None
        self.cancel_script_load()
        self._clear_index_tree()
        self._unbind_outside()
        self.script_box.pack_forget()
        self.sep.pack_forget()
        self.resize_grip.pack_forget()
        if self._dock is not None and self._dock.winfo_manager():
            self._dock.pack_forget()
        fit = getattr(self.page, 'fit_content', None)
        if callable(fit):
            fit()

    def _on_escape(self, _event=None):
        """Esc 优先收起分组下拉卡片，再次 Esc 收起停靠面板。"""
        if self._close_group_menu():
            return 'break'
        self.collapse()
        return None

    def _bind_outside(self):
        """打开期间挂面板外按下／Esc 监听（仿 ``_open_sidebar_popup`` 的 funcid 模式）。"""
        win = self.page.win
        self._button_bind = win.bind('<Button-1>', self._outside_press, add='+')
        self._escape_bind = win.bind('<Escape>', self._on_escape, add='+')

    def _unbind_outside(self):
        win = self.page.win
        for tag, bind in (('<Button-1>', self._button_bind), ('<Escape>', self._escape_bind)):
            if bind:
                try:
                    win.unbind(tag, bind)
                except tk.TclError:
                    pass
        self._button_bind = self._escape_bind = None

    def _outside_press(self, event):
        """面板外按下左键即收起；分组卡片与面板内部及外轨图标的点击放行。"""
        if not self._open:
            return
        node = getattr(event, 'widget', None)
        menu = getattr(self, 'group_menu', None)
        if menu is not None and menu.contains_widget(node):
            return
        if menu is not None and menu.is_open():
            menu.close()
        try:
            for _ in range(32):
                if node is None or node is self.page.win:
                    break
                if node in (self.script_box, self.sep, self.button, self.rail, self.resize_grip):
                    return
                node = getattr(node, 'master', None)
        except tk.TclError:
            pass
        self.collapse()

    # ── 文件列表（自 _WritingPage 原样迁入，方法体未改）────────────────────
    def cancel_script_load(self, event=None):
        """面板销毁时撤销尚未提交的目录批次与自动刷新监听。"""
        if event is not None and getattr(event, 'widget', None) is not self.script_box:
            return None
        if event is not None:
            teardown_auto_refresh(self)
        self.script_loader.invalidate()
        self._invalidate_index_load()
        if self.script_load_job is not None:
            try:
                self.page.win.after_cancel(self.script_load_job)
            except tk.TclError:
                pass
            self.script_load_job = None
        return None

    def fill_script_list(self):
        """刷新当前项目/素材库索引；全部视图同样后台加载。"""
        if self._open:
            self._reload_current_view()

    # ── 文件名列宽自适应（R2998）───────────────────────────────────────────
    def _script_list_font(self):
        """列表实际渲染字体：与 ``Script.Treeview`` 样式同一份 ``SCRIPT_FILE_FONT``。"""
        font = getattr(self, '_script_list_font_obj', None)
        if font is None:
            from tkinter import font as tkfont
            font = self._script_list_font_obj = tkfont.Font(root=self.script_tree, font=SCRIPT_FILE_FONT)
        return font

    def _fit_script_width(self):
        """按默认或手动宽度排布文件列。

        R4005（任务书 L4-U3）：文件名列优先——属性列放不进面板内宽时按
        ``SCRIPT_AUX_HIDE_ORDER`` 整列隐藏（displaycolumns），只剩文件名列仍
        不够宽时文件名中间省略，表格不再横向滚动。
        """
        tree = getattr(self, 'script_tree', None)
        sizer = getattr(self, 'script_width_sizer', None)
        if tree is None or sizer is None or not tree.winfo_exists():
            return
        full_labels = getattr(self, '_full_labels', {})
        roots = tree.get_children()
        group_labels = [tree.set(item, 'name') for item in roots if item not in full_labels]
        font = self._script_list_font()
        widths = {label: measure_text_width(font, (label,))
                  for label in set(full_labels.values()).union(group_labels)}
        widest = max(widths.values(), default=0)
        name_need = max(SCRIPT_NAME_MIN_WIDTH, widest + SCRIPT_NAME_CELL_PAD)
        preview_w = (int(tree.column('#0', 'width'))
                     if 'tree' in str(tree.cget('show')) else 0)
        preferred = getattr(self, '_user_panel_width', None) or SCRIPT_PANEL_DEFAULT_WIDTH
        panel_width = max(SCRIPT_LIST_MIN_WIDTH, min(preferred, self._manual_cap()))
        # sizer 只是请求宽：窄窗时停靠列被内容区挤到请求宽之下，stretch 的
        # name 列随 Treeview 实宽收缩，所以隐藏判定与省略预算都按实宽算；
        # 实宽变化（<Configure>→本函数重跑）会逐级收敛到稳定值。
        realized = tree.winfo_width()
        inner = realized if realized > 1 else panel_width - SCRIPT_VSCROLL_WIDTH
        inner = max(1, inner - preview_w - SCRIPT_PANEL_EDGE)
        if int(sizer.cget('width')) != panel_width:
            sizer.configure(width=panel_width)
        # 面板内宽放不下属性列时按 meta→size→kind→mtime 整列隐藏，直到文件名列
        # 的可见宽度够显示最长文件名，或者只剩文件名列；不允许半露的列。
        hidden = []
        for column, _width in SCRIPT_AUX_HIDE_ORDER:
            extra = sum(w for c, w in SCRIPT_AUX_HIDE_ORDER if c not in hidden)
            if name_need <= inner - extra:
                break
            hidden.append(column)
        shown = [column for column in ('status', 'kind', 'mtime', 'size', 'meta')
                 if column not in hidden]
        display = ('name',) + tuple(shown)
        if tuple(tree['displaycolumns']) != display:
            tree.configure(displaycolumns=display)
        # stretch 的 name 列实得「内宽 − 已显示属性列」；省略预算按它算。
        name_visible = max(SCRIPT_NAME_MIN_WIDTH, inner - sum(
            w for c, w in SCRIPT_AUX_HIDE_ORDER if c in shown))
        col_width = min(name_need, name_visible)
        if int(tree.column('name', 'width')) != col_width:
            tree.column('name', width=col_width)
        self._apply_name_labels(name_visible, widths, measure_text_width)
        self._fit_whole_file_rows()

    def _fit_whole_file_rows(self):
        """表体按完整行收尾，让 Tk 9 的 Treeview 直接绘制，避免每次滚动额外复制整块位图。"""
        tree = self.script_tree
        padding = 0
        if len(getattr(self, '_full_labels', {})) > SCRIPT_FILE_MAX_ROWS:
            cell_height = self.script_list.grid_bbox(0, 0)[3]
            row = tree.identify_row(tree.winfo_height() // 2)
            box = tree.bbox(row) if row else ()
            if box and box[3] > 0 and box[0] >= 0 and cell_height > 2 * box[3]:
                # 当前样式的四边内框等宽；任一可见行的顶边与表体顶边相差整行。
                padding = (cell_height - box[1] - box[0]) % box[3]
        if padding != getattr(self, '_file_row_padding', 0):
            self._file_row_padding = padding
            tree.grid_configure(pady=(SPACING['none'], padding))

    def _on_files_area_resize(self, event=None):
        """内容区宽度变化（窗口缩放）时去抖重算面板宽；只在面板开着时跑。"""
        if not self._open or self._fit_width_job is not None:
            return
        if event is not None and getattr(event, 'widget', None) not in (
                self.script_box.master, self.script_tree):
            return
        try:
            self._fit_width_job = self.page.win.after_idle(self._fit_script_width_debounced)
        except tk.TclError:
            self._fit_width_job = None

    def _fit_script_width_debounced(self):
        self._fit_width_job = None
        self._fit_script_width()

    def all_script_items(self):
        """返回文件叶子，不把阶段/类型/日期组当成可操作文件。"""
        if hasattr(self, '_index_rows'):
            return [item for item in self._index_rows if self.script_tree.exists(item)]
        return list(self.script_tree.get_children())

    def current_script_tree(self):
        return self.script_tree if self.script_tree.selection() else None

    def keep_one_selection(self, _tree=None):
        """单条「项目文件」列表共用一个「当前行」；多选由 Treeview 自身维持。"""
        return None

    def open_script_file(self, event=None):
        # 表头（分类名）与列宽分隔线也在 Treeview 的 <Double-1> 范围内；
        # 此时 selection() 仍保留着上次高亮的行，不能直接拿它打开文件。
        # 鼠标双击只认落点所在的行；键盘 Enter 仍打开当前高亮行。
        event_type = getattr(getattr(event, 'type', None), 'name', getattr(event, 'type', None))
        if event_type == 'ButtonPress':
            tree = event.widget
            if not isinstance(tree, ttk.Treeview):
                return
            row = row_toggle_target(tree, event.x, event.y)
        else:
            tree = self.current_script_tree()
            selected = tree.selection() if tree else ()
            row = selected[0] if selected else ''
        if not row or self.is_file_group(row):
            return
        if row.startswith('library:'):
            from infra import file_index
            library = file_index.read_global_dir()
            if library is None:
                raise ValueError('尚未设置全局素材库目录')
            path = (Path(library) / row.split(':', 1)[1]).resolve()
            if not path.is_relative_to(Path(library).resolve()):
                raise ValueError('素材路径超出全局素材库')
        else:
            path = Path(row)
            if not path.is_absolute():
                # R3137：阶段筛选视图的行是项目相对 posix 路径；无项目（测试替身）时按原样处理。
                root = getattr(self.page, 'root', None)
                if root is not None:
                    path = Path(root) / path
        if path is not None and path.is_file():
            self.page.writing_page_services.open_path(path)

    def selected_script(self):
        tree = self.current_script_tree()
        selected = tree.selection() if tree else ()
        if not selected:
            raise ValueError('请先选择剧本文件')
        from domain.script_workspace_service import selected_script_paths
        item = selected[0]
        path = self.index_file_path(item) if item in getattr(self, '_index_rows', {}) else item
        return selected_script_paths(self.page.root, [path])[0]

    def selected_scripts(self):
        """当前表里选中的各行（Ctrl／Shift 多选），并标出是否选中了列表里的全部文件。"""
        tree = self.current_script_tree()
        from domain.script_workspace_service import script_deletion_selection
        return script_deletion_selection(self.page.root, self.all_script_items(), tree.selection() if tree else ())

    def rename_script(self):
        path = self.selected_script()
        new = ask_string(self.page.win, '重命名文件', '新文件名：', initialvalue=path.name)
        if not new:
            return
        from domain.script_workspace_service import rename_script_document
        result = rename_script_document(self.page.root, path, new)
        if not result.ok:
            raise ValueError(result.reason)
        dest = result.data
        if dest == path:
            return
        self.fill_script_list()
        self.page.status.set('已重命名：' + dest.name)

    def confirmed_note(self, paths):
        # 删掉已确认阶段文件会让剧本准备的确认失效，删前点明。
        import writing_api
        confirmed = writing_api.confirmed_preparation_files(self.page.root)
        hits = [confirmed[p.resolve()] + '：' + p.name for p in paths if p.resolve() in confirmed]
        if not hits:
            return ''
        return '\n\n注意：以下是剧本准备已确认的阶段文件，删除后该阶段确认失效，需要恢复或重新确认才能继续：\n' + '\n'.join(hits)

    def delete_script(self):
        """删除仅作用于选中文件，列表全选绝不升级为删除整个项目。"""
        if getattr(self, '_index_rows', None) is not None:
            return self.delete_index_files()
        selection = self.selected_scripts()
        paths = list(selection.paths)
        one = len(paths) == 1
        if one:
            prompt = f'确定将 {paths[0].name} 移入项目回收站吗？\n\n可在对应页面恢复最近删除。' + self.confirmed_note(paths)
        else:
            names = '\n'.join(path.name for path in paths)
            prompt = '确定将选中的 ' + str(len(paths)) + ' 份剧本文件移入项目回收站吗？\n\n' + names + '\n\n可在对应页面恢复最近删除。' + self.confirmed_note(paths)
        if not self.page.writing_page_services.confirm(self.page.win, '移入回收站', prompt, dangerous=True):
            return
        from infra.storage_maintenance import recycle_paths
        recycled = recycle_paths(self.page.root, paths, '删除项目剧本' if one else '批量删除项目剧本')
        self.fill_script_list()                  # 部分成功时已进回收站的那些也要从列表消失：先刷新再报错
        if len(recycled) != len(paths):
            raise OSError('文件未能移入回收站，请刷新后重试' if one else '部分文件未能移入回收站，请刷新后重试')
        self.page.status.set('已移入回收站：' + paths[0].name if one else '已移入回收站 ' + str(len(paths)) + ' 份剧本文件')

    def adopt_script(self):
        from stage_execution_service import adopt_natural_script
        adopted = adopt_natural_script(self.page.root, self.selected_script())
        self.fill_script_list()
        self.page.status.set('已采用自然剧本：' + adopted.name + '；后续结构化使用此版本')

    def unconfirm_preparation(self, stage):
        """右键「取消已确认」：取消该阶段确认并把准备流程回退到该阶段；只改台账、不删文件。"""
        from writing_api import PREPARATION_STAGES
        from orchestrator.writing_unconfirm import preparation_confirmed_stages
        confirmed = preparation_confirmed_stages(self.page.root)
        if stage not in confirmed:
            return
        index = PREPARATION_STAGES.index(stage)
        downstream = tuple(s for s in confirmed if PREPARATION_STAGES.index(s) > index)
        prompt = ('确定取消「' + stage + '」的确认吗？\n\n'
                  '取消后剧本准备流程回到「' + stage + '」，您需要重新确认该阶段。')
        if downstream:
            prompt += '\n\n已确认的「' + '」「'.join(downstream) + '」会一并取消。'
        prompt += '\n\n不会删除或覆盖任何文件，原稿保留。'
        if not self.page.writing_page_services.confirm(self.page.win, '取消已确认', prompt):
            return
        from stage_execution_service import unconfirm_writing_preparation
        invalidated = unconfirm_writing_preparation(self.page.root, stage)
        self.fill_script_list()
        note = ('，「' + '」「'.join(invalidated) + '」的确认一并取消' if invalidated else '')
        self.page.status.set('已取消「' + stage + '」的确认' + note + '，当前回到「' + stage + '」')

    def confirm_document(self, stage):
        """把用户改过的当前文件设为该阶段定稿；之后各阶段的定稿会失效。"""
        path = self.selected_script()
        from stage_execution_service import confirm_writing_preparation
        if not self.page.writing_page_services.confirm(self.page.win, '设为' + stage + '定稿',
                                                      '把这份文件设为「' + stage + '」的定稿？\n\n' + path.name +
                                                      '\n\n以文件当前内容为准；「' + stage + '」之后已定稿的阶段需要重新确认。'):
            return
        invalidated = confirm_writing_preparation(self.page.root, stage, path)
        self.fill_script_list()
        self.page.status.set('已把' + path.name + '设为「' + stage + '」定稿' +
                             ('；「' + '」「'.join(invalidated) + '」需要重新确认' if invalidated else ''))

    def script_menu(self, tree, event):
        row = tree.identify_row(event.y)
        if not row or self.is_file_group(row):
            return
        # 右键落在已选中的行上时保留 Ctrl／Shift 多选；落在别的行上改选这一行。
        if row not in tree.selection():
            tree.selection_set(row)
        self.keep_one_selection(tree)
        menu = self.page.writing_page_services.context_menu(self.page.win)
        # REQ-UI-UNIFY-1：右键菜单统一按「打开→改名→流转/入库→路径/另存→挂钩→分隔线→删除」排列。
        if self.script_row_category.get(row) == STAGE_FILTER_ROW_CATEGORY:
            menu.command('打开', lambda: self.page.safe(self.open_script_file))
            # R3165（任务书 P3）：全局素材库视图的行可「引用到当前项目」。
            is_library = str(row).startswith('library:')
            if is_library:
                menu.command('引用到当前项目', lambda: self.page.safe(lambda: self.reference_from_library(row)))
            else:
                if len(tree.selection()) == 1:
                    menu.command('重命名', lambda: self.page.safe(lambda: self.rename_index_file(row)))
                menu.command('添加到全局素材库', lambda: self.page.safe(lambda: self.add_to_library(row)))
            menu.command('在文件夹中显示', lambda: self.page.safe(self.show_in_folder))
            menu.command('另存为…', lambda: self.page.safe(self.save_as_file))
            # DES-S04-25：阶段页登记的文件右键挂钩（如 S04 参考图改分类），仅单选放行。
            if len(tree.selection()) == 1:
                self._offer_menu_hooks(menu, self._row_abs_path(row))
            if not is_library:
                _append_delete_command(menu, self.page.safe, self.delete_index_files)
            return menu.popup(event)
        if len(tree.selection()) > 1:
            # 多选时只给「删除」：查看、改名、定稿都只针对一份文件。
            menu.command('删除', lambda: self.page.safe(self.delete_script))
            return menu.popup(event)
        # 第 46 期第 1 条 ＋ REQ-UI-UNIFY-1：查看→重命名→流转→路径→分隔线→删除。
        menu.command('查看', lambda: self.page.safe(self.open_script_file))
        menu.command('重命名', lambda: self.page.safe(self.rename_script))
        menu.command('添加到全局素材库', lambda: self.page.safe(lambda: self.add_to_library(row)))
        category = self.script_row_category.get(row, 'script')
        if category == 'script':
            menu.command('采用此剧本', lambda: self.page.safe(self.adopt_script))
        else:
            stages = {'setting': '项目设定', 'outline': '剧本大纲', 'character': '角色卡'}
            stage = stages[category]
            from orchestrator.writing_unconfirm import preparation_confirmed_stages
            if stage in preparation_confirmed_stages(self.page.root):
                menu.command('取消已确认', lambda: self.page.safe(lambda: self.unconfirm_preparation(stage)))
            menu.command('设为' + stage + '定稿', lambda: self.page.safe(lambda: self.confirm_document(stage)))
            menu.command('按段落采用…', lambda: self.page.safe(lambda: self.show_partial_adoption(stage)))
            menu.command('历史快照／对比', lambda: self.page.safe(lambda: self.show_preparation_snapshots(stage)))
        # 任务书 M5（REQ-S01-96）：剧本四类行也提供文件级「在文件夹中显示／另存为…」。
        menu.command('在文件夹中显示', lambda: self.page.safe(self.show_in_folder))
        menu.command('另存为…', lambda: self.page.safe(self.save_as_file))
        _append_delete_command(menu, self.page.safe, self.delete_script)
        return menu.popup(event)

ProjectFilesPanel.script_menu = lambda self, tree, event: _popup_script_menu(self, tree, event)
