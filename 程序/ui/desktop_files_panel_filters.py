# -*- coding: utf-8 -*-
"""项目文件停靠面板的阶段快捷图标列与筛选条（R3106，任务书 P1）。

自 ``desktop_files_panel.ProjectFilesPanel`` 拆出：类行数棘轮上限 600 行
（``test_complexity_ratchet``），筛选条与图标列是本轮新增的一块独立职责。
宿主须提供 ``page``／``script_box``／``script_tree``／``script_row_details``／
``script_row_category``／``_open`` 等已有成员。
"""
import tkinter as tk
from pathlib import Path, PureWindowsPath
from tkinter import ttk

from ui_tokens import COLORS, SPACING
from ui_widgets import LineInput, SecondaryButton, SelectBox, Tooltip
import ui.desktop_files_panel_index as files_panel_index
from ui.desktop_files_panel_index import FilesPanelIndexMixin, SCRIPT_NAME_CELL_PAD

_FOLLOWED_STAGE_SENTINEL = object()

# R3094（任务书 P1，Q8 补充需求）：停靠面板右缘的阶段快捷图标列，顺序＝pet_bus.STAGES。
# R3191（任务书 M3，REQ-S01-93）：图标优先用 assets/nav/<stage>_files.png（IconLoader.nav_icon），
# PNG 缺失退回本表 Unicode 符号；每个图标都带 Tooltip 中文名。
STAGE_RAIL_ICONS = {
    'script': '📝', 'script_structure': '🧾', 'storyboard': '🎬', 'animatic': '🎞',
    'assets': '🎨', 'continuity': '🧩', 'final': '✅', 'keyframe': '🖼',
    'previs': '🧊', 'video': '📹', 'audio': '🎙', 'edit': '✂', 'delivery': '📦',
}
STAGE_RAIL_ALL = '📁'          # 「全部」：全项目索引，按阶段分组
STAGE_FILTER_ROW_CATEGORY = 'index'   # 索引行在右键菜单里与剧本行区分

# 关键字输入框的宽度以「字符」计，从 token 派生，避免新增数字字面量（test_token_boundary）。
FILTER_KEYWORD_WIDTH = max(4, SPACING['xs'])

# 任务书 M5（REQ-S01-95/96）：预览列图元长边与列宽、时长／分辨率列宽全部 token 派生；
# 视频封面 16:9（40×22）与音频波形（40×13）落在字高行内，行高仍由字体 token 量。
PANEL_PREVIEW_SIZE = SPACING['2xl'] + SPACING['sm']            # 40：预览图长边上限
PANEL_PREVIEW_COL_WIDTH = PANEL_PREVIEW_SIZE + SPACING['sm']   # 48：预览列宽
PANEL_META_WIDTH = SPACING['xl'] * 5                            # 120：时长／分辨率列宽


def _retention_days():
    """回收站保留期（天）：唯一定义在 ``storage_maintenance``，这里只读不复制数字。"""
    from infra.storage_maintenance import RECYCLE_RETENTION_DAYS
    return RECYCLE_RETENTION_DAYS


class FilesPanelFilterMixin(FilesPanelIndexMixin):
    """阶段图标列＋筛选条＋按索引填表。"""

    # ── 筛选条（R3106，任务书 P1，Q25）────────────────────────────────────
    def _build_filter_bar(self):
        """类型／状态／分组／排序下拉＋文件名关键字；空值一律表示「不限」。

        R3983（任务书 L4-U2，Q1/Q2）：阶段选择由右缘图标列承担，去掉重复的阶段
        下拉框；第一行关键字＋刷新，第二行四个下拉框——面板内宽放不下时
        「分组」「排序」连同名称经 FlowBar 整体换到第三行。下拉框不写死字符宽：
        只读 SelectBox 按全部取值实测像素宽自适应，完整显示当前取值。
        """
        from contract.file_index_contract import STATUSES
        from contract.file_naming import KINDS
        from responsive_ui import FlowBar
        bar = ttk.Frame(self.script_box)
        bar.pack(side='top', fill='x', pady=(SPACING['none'], SPACING['xs']))
        self.filter_bar = bar
        self.kind_labels = {'全部类型': None}
        for kind in KINDS:
            self.kind_labels[kind] = kind
        self.status_labels = {'全部状态': None}
        for status in STATUSES:
            self.status_labels[status] = status
        row_one = ttk.Frame(bar)
        row_one.pack(side='top', fill='x')
        self.keyword_var = tk.StringVar(value='')
        # 业务 UI 不得直接建 ttk.Entry（test_input_boundary）：统一走 LineInput。
        self.keyword_entry = LineInput(row_one, textvariable=self.keyword_var, width=FILTER_KEYWORD_WIDTH)
        self.keyword_entry.pack(side='left', fill='x', expand=True)
        self.keyword_entry.bind('<KeyRelease>', self._keyword_changed)
        Tooltip(self.keyword_entry, '按文件名关键字筛选（回车立即生效）')
        self.index_refresh_button = SecondaryButton(row_one, text='刷新', command=self.refresh_file_index)
        self.index_refresh_button.pack(side='left', padx=(SPACING['xs'], SPACING['none']))
        Tooltip(self.index_refresh_button, '后台重建索引，发现外部新增或修改的文件')
        row_two = FlowBar(bar)
        row_two.pack(side='top', fill='x')
        self._build_import_button()
        self.kind_box = SelectBox(row_two, values=tuple(self.kind_labels))
        self.kind_box.pack(side='left')
        self.kind_box.bind('<<ComboboxSelected>>', lambda _event: self._apply_filters())
        Tooltip(self.kind_box, '按文件类型筛选')
        self.status_box = SelectBox(row_two, values=tuple(self.status_labels))
        self.status_box.pack(side='left')
        self.status_box.bind('<<ComboboxSelected>>', lambda _event: self._apply_filters())
        Tooltip(self.status_box, '按状态筛选：草稿／已发布／已归档')
        # 「分组」「排序」连同名称装进同一个子框：内宽不够时 FlowBar 把它整体
        # 换到下一行（R2），名称跟着框走不拆散；fill='y' 让名称与下拉框顶边齐平。
        tail = ttk.Frame(row_two)
        tail.pack(side='left')
        self.group_label = ttk.Label(tail, text='分组', style='Muted.TLabel')
        self.group_label.pack(side='left', fill='y')
        self.group_box = SelectBox(tail, values=('阶段', '类型', '日期'))
        self.group_box.pack(side='left', padx=(SPACING['xs'], SPACING['none']))
        self.group_box.set('阶段')
        self.group_box.bind('<<ComboboxSelected>>', lambda _event: self._apply_filters())
        Tooltip(self.group_box, '分组方式：阶段／类型／日期（跨阶段归组）')
        self.sort_label = ttk.Label(tail, text='排序', style='Muted.TLabel')
        self.sort_label.pack(side='left', fill='y', padx=(SPACING['md'], SPACING['none']))
        self.sort_box = SelectBox(tail, values=('类型', '修改时间'))
        self.sort_box.pack(side='left', padx=(SPACING['xs'], SPACING['none']))
        self.sort_box.set('类型')
        self.sort_box.bind('<<ComboboxSelected>>', lambda _event: self._apply_filters())
        Tooltip(self.sort_box, '组内按类型或修改时间排序（最新在前）')
        self._reset_filter_boxes()

    def _build_import_button(self):
        """REQ-S01-103：标题行导入钮，收起钮左侧；PNG 优先，缺图退回 📁 文本。"""
        from ui_icons import IconLoader
        image = IconLoader.nav_icon(self.page.win, 'project_new')
        if image is not None:
            button = SecondaryButton(self.script_header, text=STAGE_RAIL_ALL, image=image,
                                     compound='image', width=0, style='Tokens.Composer.Icon.TButton',
                                     command=lambda: self.page.safe(self.import_files))
        else:
            button = SecondaryButton(self.script_header, text=STAGE_RAIL_ALL, width=0,
                                     style='Tokens.Composer.Icon.TButton',
                                     command=lambda: self.page.safe(self.import_files))
        button.pack(side='right', padx=(SPACING['none'], SPACING['xs']))
        Tooltip(button, '导入文件到当前阶段目录')
        self.import_button = button

    def _reset_filter_boxes(self):
        """下拉框显示回「全部」，不触发回调。"""
        for box in (getattr(self, 'kind_box', None), getattr(self, 'status_box', None)):
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
        self._stage_filter_pinned = False
        self._followed_page_stage = _FOLLOWED_STAGE_SENTINEL
        self._reset_filter_boxes()
        self._sync_stage_buttons()
        title = getattr(self, 'script_title', None)
        if title is not None:
            title.configure(text='项目文件')

    def _sync_view_filters(self):
        """全局库只支持类型/名称，避免展示无效的发布状态条件。"""
        self.status_box.configure(state='disabled' if self.library_view else 'readonly')
        if getattr(self, 'library_view', False):
            return
        current = self._page_stage()
        if getattr(self, '_stage_filter_pinned', False) and self.stage_filter is not None:
            # 手动点选的阶段是跨阶段排查视图：换页不抢回筛选；标题仍按当前状态重同步。
            self._sync_stage_title()
            self._sync_stage_buttons()
            return
        if current != getattr(self, '_followed_page_stage', _FOLLOWED_STAGE_SENTINEL):
            self.stage_filter = current
            self._followed_page_stage = current
            self._sync_stage_title()
            self._sync_stage_buttons()

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
        """把类型／状态／分组／排序与关键字收成筛选条件，再按条件重填列表。"""
        self._filter_job = None
        self.kind_filter = self.kind_labels.get(str(self.kind_box.get()))
        self.status_filter = self.status_labels.get(str(self.status_box.get()))
        if self.library_view:
            self.stage_filter = None
            self.status_filter = None
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
        title = getattr(self, 'script_title', None)
        if title is not None:
            title.configure(text='项目文件 · 全局素材库')
        library = file_index.read_global_dir()
        if library is None:
            self.page.status.set('尚未设置全局素材库目录：请先指定一个跨项目共用的素材文件夹。')
            self._fill_global_list(None)
            return
        self._fill_global_list(library)

    def _fill_global_list(self, library):
        """全局库首次索引扫描同样在 Desktop 生命周期后台执行。"""
        self._library_root = library
        self._request_index(library, library=True)

    def _media_config(self):
        """项目 config.json 里的 ffmpeg/ffprobe 显式配置；没有读给 None（随包／PATH 兜底）。"""
        root = getattr(self.page, 'root', None)
        if root is None:
            return None
        try:
            from infra.file_cache import read_json
            cfg = read_json(Path(root) / 'config.json')
        except Exception:
            return None
        if not isinstance(cfg, dict):
            return None
        return {'ffmpeg': cfg.get('ffmpeg'), 'ffprobe': cfg.get('ffprobe')}

    def _prefetch_media_thumbs(self, paths):
        """列表里的视频／音频后台预生成封面（任务书 M4）；项目显式 ffmpeg 配置透传给后台。"""
        import asset_thumbs
        capped = list(paths)[:files_panel_index._MEDIA_PREFETCH_CAP]
        asset_thumbs.prefetch_media(self.page.win, capped, configured=self._media_config())

    # ── 预览列与文件动作（任务书 M5，REQ-S01-95/96）────────────────────────
    def _row_preview(self, path):
        """行预览图：视频／音频走 M4 媒体通道，图片走原缩略图；拿不到图返回 None。

        先返回空盒／占位图（PhotoImage 常驻内存缓存），后台封面落地后像素原位替换，
        列表一行代码都不用改。
        """
        import asset_thumbs
        from infra import file_index
        size = PANEL_PREVIEW_SIZE
        if asset_thumbs.media_kind(path) is not None:
            return asset_thumbs.media_thumbnail(self.page.win, path, size=size,
                                                configured=self._media_config())
        if Path(path).suffix.lower() in file_index.IMAGE_SUFFIXES:
            return asset_thumbs.thumbnail(self.page.win, path, size)
        return None

    def _row_meta_text(self, path):
        """时长／分辨率列：读 M4 的封面同键旁路记录，不读 FileRow。"""
        import asset_thumbs
        if asset_thumbs.media_kind(path) is None:
            return ''
        info = asset_thumbs.media_info(path, PANEL_PREVIEW_SIZE)
        if not info:
            return ''
        parts = []
        if info.get('duration'):
            parts.append('%.1fs' % info['duration'])
        if info.get('width') and info.get('height'):
            parts.append('%d×%d' % (info['width'], info['height']))
        return ' · '.join(parts)

    def _schedule_meta_refresh(self):
        """旁路记录通常跟封面同到：延迟一拍把空着的时长／分辨率格补齐。"""
        if getattr(self, '_meta_refresh_job', None) is not None:
            try:
                self.page.win.after_cancel(self._meta_refresh_job)
            except tk.TclError:
                pass
        try:
            self._meta_refresh_job = self.page.win.after(1500, self._refresh_media_meta)
        except tk.TclError:
            self._meta_refresh_job = None

    def _refresh_media_meta(self):
        """旁路记录补齐：把仍空着的时长／分辨率格重写一遍（一次，不递归排期）。"""
        self._meta_refresh_job = None
        import asset_thumbs
        tree = getattr(self, 'script_tree', None)
        if tree is None or not tree.winfo_exists() or not self._open:
            return
        base = getattr(self, '_library_root', None) or getattr(self.page, 'root', None)
        if base is None:
            return
        changed = False
        for item in self.all_script_items():
            values = tree.item(item, 'values')
            if len(values) > 4 and values[4]:
                continue
            path = self._row_abs_path(item)
            if path is None or asset_thumbs.media_kind(path) is None:
                continue
            text = self._row_meta_text(path)
            if not text:
                continue
            tree.item(item, values=tuple(values[:4]) + (text,))
            details = self.script_row_details.get(item, '')
            if text not in details:
                self.script_row_details[item] = details + ('\n' if details else '') + '时长／分辨率：' + text
            changed = True
        if changed:
            fit = getattr(self, '_fit_script_width', None)
            if callable(fit):
                fit()

    def _row_abs_path(self, row):
        """行 iid 对应的绝对路径：index 行项目相对、library: 前缀行素材库相对。"""
        if row.startswith('library:'):
            library = getattr(self, '_library_root', None)
            return (Path(library) / row[len('library:'):]) if library else None
        path = Path(row)
        if not path.is_absolute():
            root = getattr(self.page, 'root', None)
            if root is None:
                return None
            path = Path(root) / path
        return path

    _SAVE_AS_STAGES = {
        'setting': '项目设定', 'outline': '剧本大纲', 'character': '角色卡', 'script': '剧本',
    }

    def _save_as_name(self, path, row):
        """另存为预填名：``项目名_阶段名_原文件名``（任务书 M5，REQ-S01-96）。"""
        root = getattr(self.page, 'root', None)
        project = Path(root).name if root else '导出文件'
        stage = (self.script_row_stage.get(row)
                 or self._SAVE_AS_STAGES.get(self.script_row_category.get(row), ''))
        return '_'.join(part for part in (project, stage, path.name) if part)

    def save_as_file(self):
        """另存为：复制到用户选定位置（不移动原件）；目标已存在先询问，取消零写入。"""
        selected = self.script_tree.selection()
        if not selected:
            raise ValueError('请先选择文件')
        path = self._row_abs_path(selected[0])
        if path is None or not path.is_file():
            raise ValueError('文件不存在或已缺失：' + selected[0])
        target = self.page.file_dialog.save_file(
            parent=self.page.win, title='另存为',
            initialfile=self._save_as_name(path, selected[0]), defaultextension=path.suffix)
        if not target:
            return                                       # 用户取消：零写入
        target = Path(target)
        if target.exists() and not self.page.writing_page_services.confirm(
                self.page.win, '目标已存在',
                '目标文件已存在，要覆盖吗？\n\n' + str(target), dangerous=True):
            return                                       # 覆盖前询问：不同意不写
        try:
            import shutil
            shutil.copy2(path, target)
        except OSError as exc:
            raise OSError('另存为失败：' + str(exc))      # 复制失败给出原因
        self.page.status.set('已另存为：' + str(target))

    def show_in_folder(self):
        """在系统文件管理器中定位选中文件（Windows 选中它本身）。"""
        selected = self.script_tree.selection()
        if not selected:
            raise ValueError('请先选择文件')
        path = self._row_abs_path(selected[0])
        if path is None:
            raise ValueError('文件不存在或已缺失：' + selected[0])
        from contract.platform_tools import reveal_in_folder
        reveal_in_folder(path)

    # ── 阶段快捷图标列（R3094，任务书 P1）──────────────────────────────────
    def _page_stage(self):
        from contract.pet_bus import STAGES
        page_index = getattr(self.page, 'page_index', None)
        if isinstance(page_index, int) and 0 <= page_index < len(STAGES):
            return STAGES[page_index]
        return None

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
            self._meta_refresh_job = None
            self._library_root = None
            self.script_row_stage = {}      # iid → 阶段显示名（另存为预填名用）
            self._stage_filter_pinned = False
            self._followed_page_stage = _FOLLOWED_STAGE_SENTINEL
        if not hasattr(self, '_stage_filter_pinned'):
            self._stage_filter_pinned = False

    def _build_stage_rail(self):
        """建右缘阶段图标列：13 个阶段（顺序＝``pet_bus.STAGES``）＋回收站／素材库动作。

        UX-C1：面板内不再放与入口重复的「全部文件」图标；全项目视图由入口打开／
        ``show_stage(None)`` 复位。R3191：阶段图标用 ``assets/nav/<stage>_files.png``，
        PNG 缺失时退回 ``STAGE_RAIL_ICONS`` 的 emoji；高度不够时整列可滚轮滚动。
        """
        from contract.pet_bus import STAGES, stage_name
        from responsive_ui import ScrollForm
        from ui_icons import IconLoader
        from ui_tokens import COLORS
        self._ensure_filter_state()
        # R3971（任务书 L4-U1）：齿轮设置钮钉在列顶——pack 先于滚动画布，
        # 否则它落进滚动条与画布之间的中间腔，把画布挤成 1px 宽。
        # UX-C1：与侧栏同套 PNG（library_settings），缺图退回 ⚙。
        settings = self._make_rail_icon_button(
            self.stage_rail, 'library_settings', '⚙', '设置全局素材库目录',
            self.configure_library)
        settings.pack(side='top', pady=(SPACING['none'], SPACING['xs']))
        self.library_settings_button = settings
        # 图标列自身仍是 script_box 右缘的固定竖条；内部换成可滚动画布，矮窗口不再裁掉底部图标。
        self.stage_rail_scroller = ScrollForm(self.stage_rail, bg=COLORS['background_primary'])
        self.stage_rail_form = self.stage_rail_scroller.form
        self.stage_buttons = {}
        for stage in STAGES:
            icon_name = stage + '_files'
            glyph = STAGE_RAIL_ICONS.get(stage, '•')
            button = self._make_rail_icon_button(
                self.stage_rail_form, icon_name, glyph, stage_name(stage),
                lambda value=stage: self.show_stage(value))
            button.pack(side='top', pady=(SPACING['none'], SPACING['xs']))
            self.stage_buttons[stage] = button
        self._sync_stage_buttons()
        # R3117（任务书 P2，Q5）：回收站入口放在图标列末尾——浏览／恢复走既有恢复窗，
        # 清空只删超过保留期的批次，物理删除仍只经 storage_maintenance。
        self.recycle_button = self._add_rail_action(
            '♻', '回收站：浏览与恢复已删除的文件', 'open_recycle_recovery',
            icon_name='recycle')
        self.recycle_purge_button = self._add_rail_action(
            '🗑', '清空过期回收站（保留 %d 天）' % _retention_days(),
            'purge_expired_recycle', icon_name='recycle_purge')
        # R3143（任务书 P3，Q11）：全局素材库视图——跨项目的共享素材，按库相对路径列出。
        library = self._make_rail_icon_button(
            self.stage_rail_form, 'library', '🗂',
            '全局素材库：跨项目的共享素材（可在设置里指定目录）', self.show_library)
        library.pack(side='top', pady=(SPACING['none'], SPACING['xs']))
        self.library_button = library
        # 滚轮绑定要等全部子件建完再递归挂一次（见 ScrollForm.bind_wheel 说明）。
        self.stage_rail_scroller.bind_wheel()
        # tk.Canvas 默认请求宽约 378px，会把整条图标列撑成宽面板；钉成内容实际宽度。
        # 不许在这里 update_idletasks——构建期泵事件会让已挂的 after_idle 作业提前执行，
        # 与正在构建中的窗口状态形成再入（实测 Desktop.__init__ 在 _register 挂死）。
        content_w = max((child.winfo_reqwidth() for child in self.stage_rail_form.winfo_children()),
                        default=0)
        if content_w:
            # R3971（任务书 L4-U1）：外框钉固定宽＝内容宽＋竖滚动条宽，画布在其中填满；
            # 关掉 pack 传播后画布的请求宽不再参与外层几何协商——
            # 与 R3214「画布钉 1px」等价地切断振荡回路，但图标列恢复可见。
            scroll_w = self.stage_rail_scroller.scroll.winfo_reqwidth()
            self.stage_rail.configure(width=max(content_w, settings.winfo_reqwidth()) + scroll_w)
            self.stage_rail.pack_propagate(False)
            self.stage_rail_scroller.canvas.configure(width=content_w)

    def _make_rail_icon_button(self, parent, icon_name, glyph, tip, command):
        """建一枚右缘图标钮：优先 ``assets/nav/<icon_name>.png``，缺图退回 glyph 文本。"""
        from ui_icons import IconLoader
        image = IconLoader.nav_icon(self.page.win, icon_name)
        if image is not None:
            button = SecondaryButton(parent, text=glyph, image=image, compound='image',
                                     width=0, style='RailIcon.TButton', command=command)
        else:
            button = SecondaryButton(parent, text=glyph, width=0, style='RailIcon.TButton',
                                     command=command)
        button._rail_icon_name = icon_name
        Tooltip(button, tip)
        return button

    def _add_rail_action(self, glyph, tip, method_name, icon_name=None):
        """在图标列末尾追加一个动作钮；宿主没有该动作时只留按钮不绑回调。"""
        action = getattr(self.page, method_name, None)
        command = (lambda: self.page.safe(action)) if callable(action) else None
        if icon_name:
            button = self._make_rail_icon_button(self.stage_rail_form, icon_name, glyph, tip,
                                                 command)
        else:
            button = SecondaryButton(self.stage_rail_form, text=glyph, width=0,
                                     style='RailIcon.TButton', command=command)
            Tooltip(button, tip)
        button.pack(side='top', pady=(SPACING['none'], SPACING['xs']))
        return button

    def _sync_stage_buttons(self):
        """当前阶段／全局素材库高亮：选中的图标换成按下风格，其余回到普通风格。"""
        in_library = bool(getattr(self, 'library_view', False))
        for stage, button in getattr(self, 'stage_buttons', {}).items():
            style = 'Selected.RailIcon.TButton' if (not in_library and stage == self.stage_filter) else 'RailIcon.TButton'
            try:
                button.configure(style=style)
            except tk.TclError:
                return
        library_button = getattr(self, 'library_button', None)
        if library_button is not None:
            try:
                library_button.configure(style='Selected.RailIcon.TButton' if in_library else 'RailIcon.TButton')
            except tk.TclError:
                pass

    def _sync_stage_title(self):
        """面板标题跟着当前阶段走；手动钉住的跨阶段视图标出来，避免误以为仍在跟随当前页。"""
        title = getattr(self, 'script_title', None)
        if title is None:
            return
        from contract.pet_bus import stage_name
        text = '全部阶段' if self.stage_filter is None else stage_name(self.stage_filter)
        if (getattr(self, '_stage_filter_pinned', False) and self.stage_filter is not None
                and self.stage_filter != self._page_stage()):
            text += ' · 跨阶段查看'
        try:
            title.configure(text='项目文件 · ' + text)
        except tk.TclError:
            pass

    def show_stage(self, stage=None):
        """点阶段图标查看该阶段文件；手动选择跨页钉住，再点已选图标恢复跟随当前页。"""
        self._ensure_filter_state()
        self.library_view = False
        if stage is not None and stage == self.stage_filter and getattr(self, '_stage_filter_pinned', False):
            self._stage_filter_pinned = False
            stage = self._page_stage()
        else:
            self._stage_filter_pinned = stage is not None
        self.stage_filter = stage
        # 同步记录当前页阶段，避免从全局素材库或换页后点选某阶段图标时被 _sync_view_filters 覆写回页面阶段。
        self._followed_page_stage = self._page_stage()
        self._sync_stage_title()
        self._sync_stage_buttons()
        self._reload_current_view()

    def _fill_index_list(self):
        """默认全部与筛选视图共用全项目索引，首次重建不阻塞主线程。"""
        self._request_index(getattr(self.page, 'root', None))


class FilesPanelStageViewMixin:
    """REQ-S01-101/102（UX-FP-NOTIFY）：跟随页「来源文档＋本阶段产物」视图与点选通知。

    ``ProjectFilesPanel`` 把本 mixin 排在 ``FilesPanelFilterMixin``（继承
    ``FilesPanelIndexMixin``）之前：``_request_index``／``_start_index_render``／
    ``_finish_index_render`` 接管索引 mixin 的同名方法，``super()`` 沿 MRO 落到
    ``FilesPanelIndexMixin`` 的原实现。
    """

    # ── REQ-S01-101：跟随页视图＝来源阶段＋本阶段 ──────────────────────────
    def _dep_source_stages(self, stage):
        """来源阶段取 ``stage_flow.DEPENDS`` 的直接依赖；读不到按空处理。"""
        if not stage:
            return ()
        try:
            import orchestrator.stage_flow as stage_flow
            return tuple(dep for dep in (stage_flow.DEPENDS.get(stage) or ()) if dep)
        except Exception:
            return ()

    def _sync_view_filters(self):
        super()._sync_view_filters()
        if not getattr(self, 'library_view', False):
            self._followed_source_stages = self._dep_source_stages(
                getattr(self, '_followed_page_stage', None))

    def _stage_filter_is_followed(self):
        """每个阶段文件图标下只显示本阶段文件，不再把上游 DEPENDS 阶段的文件混入当前阶段目录。"""
        return False

    def _filter_index_rows(self, rows, filters, library):
        """跟随页视图把阶段条件放宽为来源＋本阶段；其余条件与排序不变。"""
        if library or not self._stage_filter_is_followed():
            return files_panel_index.filtered_rows(rows, filters, library)
        _stage, kind, status, keyword, sort = filters
        view_stages = set(self._followed_source_stages) | {self.stage_filter}
        scoped = [row for row in rows if row.stage in view_stages]
        return files_panel_index.filtered_rows(
            scoped, (None, kind, status, keyword, sort), library)

    def _index_groups(self, rows, library):
        """S04 按 4 语义分组；其余视图沿用 grouped_rows。"""
        mode = getattr(self, 'group_mode', '阶段')
        if not library and mode == '阶段' and getattr(self, 'stage_filter', None) == 'animatic':
            return files_panel_index.animatic_grouped_rows(rows)
        if library or mode != '阶段' or not self._stage_filter_is_followed():
            return files_panel_index.grouped_rows(rows, mode, library)
        sources = [row for row in rows if row.stage in self._followed_source_stages]
        own = [row for row in rows if row.stage == self.stage_filter]
        groups = []
        if sources:
            groups.append((files_panel_index.GROUP_PREFIX + '__source__', '来源文档', sources))
        if own:
            groups.append((files_panel_index.GROUP_PREFIX + '__own__', '本阶段产物', own))
        return groups

    def _request_index(self, root, library=False):
        """跟随页视图扩现索引发现范围与行口径；实现见模块级 ``_stage_view_request_index``。"""
        _stage_view_request_index(self, root, library)

    def _start_index_render(self, rows, categories, root, library, generation, context):
        """与 ``FilesPanelIndexMixin`` 同，仅分组来源换成 ``_index_groups``。"""
        _stage_view_index_render(self, rows, categories, root, library, generation, context)

    def _finish_index_render(self):
        super()._finish_index_render()
        self._apply_default_select()

    # ── REQ-S01-102：点选通知当前页 ────────────────────────────────────────
    def _ensure_select_state(self):
        """首次登记前补齐点选状态（宿主 ``__init__`` 不感知这些字段）。"""
        if not hasattr(self, '_select_handlers'):
            self._select_handlers = {}
            self._select_page_index = None
            self._programmatic_select = False

    def _sync_select_page(self):
        """页码变化时清掉非当前页的点选登记（REQ-S01-102）。"""
        self._ensure_select_state()
        current = getattr(self.page, 'page_index', None)
        previous = self._select_page_index
        if previous == current:
            return
        self._select_page_index = current
        for key in [key for key in self._select_handlers if key != current]:
            self._select_handlers.pop(key, None)

    def set_select_handler(self, page_key, fn, default=None):
        """当前页登记点选回调：``fn(文件绝对路径)``；``default`` 为要预选的行 iid。

        ``page_key``＝``page.page_index``；换页由 ``_sync_select_page`` 清掉旧页登记。
        """
        self._ensure_select_state()
        if fn is None:
            self._select_handlers.pop(page_key, None)
        else:
            self._select_handlers[page_key] = (fn, default)

    def clear_select_handler(self, page_key=None):
        """清掉登记：给 ``page_key`` 只清那一页，不给清全部。"""
        self._ensure_select_state()
        if page_key is None:
            self._select_handlers.clear()
        else:
            self._select_handlers.pop(page_key, None)

    def _notify_file_select(self, event=None):
        """``<<TreeviewSelect>>``：保持单选之外通知当前页登记的回调。"""
        if getattr(self, '_programmatic_select', False):
            self._programmatic_select = False
            return
        self._sync_select_page()
        try:
            selected = self.script_tree.selection()
        except tk.TclError:
            return
        if not selected:
            return
        row = selected[0]
        if self.is_file_group(row):
            return
        entry = self._select_handlers.get(getattr(self.page, 'page_index', None))
        if entry is None:
            return
        path = self._row_abs_path(row)
        if path is None or self._is_media_row(path):
            return
        entry[0](path)

    def _is_media_row(self, path):
        """文本类判定沿用面板口径：视频／音频媒体与图片后缀不进回调。"""
        import asset_thumbs
        from infra import file_index
        if asset_thumbs.media_kind(path) is not None:
            return True
        return Path(path).suffix.lower() in file_index.IMAGE_SUFFIXES

    def _apply_default_select(self):
        """渲染收尾应用当前页登记的默认选中；该次选择不触发点选回调。"""
        self._sync_select_page()
        entry = self._select_handlers.get(getattr(self.page, 'page_index', None))
        if entry is None or not entry[1]:
            return
        tree = self.script_tree
        try:
            if not tree.exists(entry[1]):
                return
            self._programmatic_select = True
            tree.selection_set(entry[1])
            tree.see(entry[1])
        except tk.TclError:
            self._programmatic_select = False
            return
        win = getattr(self.page, 'win', None)
        if win is not None:
            try:
                win.after_idle(self._release_programmatic_select)
            except tk.TclError:
                pass

    def _release_programmatic_select(self):
        self._programmatic_select = False


def _stage_view_request_index(panel, root, library=False):
    """``_request_index`` 的跟随页变体：发现范围与行口径扩成「来源＋本阶段」。

    实现放模块级函数：类内 ``self.X`` 赋值会被共享状态棘轮按类归因，
    ``panel.X`` 形式不计入 Mixin 组合类的多写者统计。
    """
    panel.cancel_script_load()
    panel._clear_index_tree()
    if root is None or not panel._open:
        return
    generation = panel._index_generation
    panel._index_loading = True
    context = panel._index_context(root, library)
    filters = (panel.stage_filter, panel.kind_filter, panel.status_filter,
               panel.keyword_filter, getattr(panel, 'sort_mode', '类型'))
    refresh = getattr(panel, '_index_refresh', False)
    panel._index_refresh = False
    discover_stage = None if panel._stage_filter_is_followed() else filters[0]

    def work():
        if not panel._index_current_without_tk(generation, context):
            return None
        rows, categories, labels = files_panel_index.load_index(
            root, library, refresh, stage=discover_stage)
        return panel._filter_index_rows(rows, filters, library), categories, labels

    def done(result):
        if result is None or not panel._index_current(generation, context):
            return
        panel._index_loading = False
        found, categories, panel._index_file_labels = result
        groups = panel._start_index_render(found, categories, root, library, generation, context)
        if hasattr(panel, '_prefetch_media_thumbs'):
            target = groups if groups is not None else panel._index_groups(found, library)
            panel._prefetch_media_thumbs(files_panel_index.prefetch_media_paths(target, root))

    submit = getattr(panel.page, 'async_queued', panel.page.async_)
    submit(work, done, show_progress=False,
           label='加载全局素材库' if library else '加载项目文件索引')


def _stage_view_index_render(panel, rows, categories, root, library, generation, context):
    """``_start_index_render`` 的跟随页变体：分组来自 ``_index_groups``，按组默认展开。"""
    panel._clear_index_tree()
    panel.script_tree.tag_configure('missing', foreground=COLORS['text_muted'])
    groups = panel._index_groups(rows, library)
    show_groups = files_panel_index.should_show_groups(groups)
    panel._index_group_count = len(groups)
    files_panel_index.configure_tree_leading_column(
        panel.script_tree, groups, preview_width=PANEL_PREVIEW_COL_WIDTH)
    if show_groups:
        for group, label, _members in groups:
            opened = files_panel_index.group_default_open(group)
            panel.script_tree.insert('', 'end', iid=group, open=opened, values=(label, '', '', '', ''))
            panel.script_row_category[group] = '__file_group__'
        files_panel_index.bind_lazy_group_previews(panel, root)
    pending = (iter((group, row) for group, _label, members in groups for row in members)
               if show_groups else iter(('', row) for _g, _l, members in groups for row in members))

    def batch():
        panel._index_render_job = None
        if not panel._index_current(generation, context):
            return
        for _ in range(files_panel_index.RENDER_BATCH):
            entry = next(pending, None)
            if entry is None:
                panel._finish_index_render()
                return
            group, row = entry
            panel._insert_index_row(row, categories, root, library, group)
        panel._index_render_job = panel.page.win.after(1, batch)

    batch()
    return groups


# ── REQ-S01-103：面板「导入文件」（UX-FP-IMPORT）─────────────────────────────

def import_suffixes(stage):
    """该阶段面板允许导入的本机文件后缀，全部取自现有文件类型判定表。"""
    from domain.delivery_import_service import ALLOWED_SUFFIXES
    from domain.script_workspace_service import VISIBLE_SUFFIXES
    from infra import file_index
    docs = frozenset(VISIBLE_SUFFIXES)
    # 文档类阶段收 VISIBLE_SUFFIXES；图像阶段收 IMAGE_SUFFIXES；音频阶段加收字幕后缀；
    # 视频链路收 VIDEO_SUFFIXES（animatic 另加图与音、previs 另加图）；交付与
    # delivery_import_service 同一份。功能 JSON 不进面板列表，仍走各阶段专用入口。
    tables = {
        'script': docs, 'script_structure': docs, 'storyboard': docs,
        'continuity': docs, 'final': docs,
        'animatic': file_index.IMAGE_SUFFIXES | file_index.AUDIO_SUFFIXES | file_index.VIDEO_SUFFIXES,
        'assets': file_index.IMAGE_SUFFIXES,
        'keyframe': file_index.IMAGE_SUFFIXES,
        'previs': file_index.IMAGE_SUFFIXES | file_index.VIDEO_SUFFIXES,
        'video': file_index.VIDEO_SUFFIXES,
        'audio': file_index.AUDIO_SUFFIXES | frozenset({'.srt', '.ass'}),
        'edit': file_index.VIDEO_SUFFIXES,
        'delivery': frozenset(ALLOWED_SUFFIXES),
    }
    return frozenset(tables.get(str(stage or ''), ()))


def _import_target(root, stage, name):
    """导入落点：``write_dir`` 目录＋合法单段文件名；剥离目录段、越界即拒绝。"""
    from contract import file_naming, stage_path_service
    target_dir = stage_path_service.write_dir(root, stage)
    safe = file_naming.validate(PureWindowsPath(str(name)).name)
    target = target_dir / safe
    if not target.resolve().is_relative_to(Path(root).resolve()):
        raise ValueError('导入目标越出项目目录：' + safe)
    return target_dir, target


def _check_importable(source, stage, allowed):
    """源必须是已存在的普通文件，且后缀落在本阶段允许表内。"""
    from contract.pet_bus import stage_name
    if not source.is_file():
        raise ValueError('源文件不存在或不是普通文件')
    if source.suffix.lower() not in allowed:
        raise ValueError('「%s」阶段不支持该类型；可导入：%s' % (
            stage_name(stage), ' '.join(sorted(allowed))))


def _default_import_copier(target, source, overwrite):
    """原子发布副本：覆盖＝临时文件原子替换；新建＝排他硬链接，绝不静默覆盖。"""
    from agent.core import copy_file_new, save_file
    if overwrite:
        save_file(target, source)
    else:
        copy_file_new(target, source, lambda _temp: True)


def _clean_import_temp(target):
    """复制失败兜底：同前缀 ``*.tmp`` 残留经 ``file_cache`` 清理（L4 不直接删文件）。"""
    from infra.file_cache import remove_temporary_file
    prefix = target.name + '.'
    try:
        strays = [entry for entry in target.parent.iterdir()
                  if entry.name.startswith(prefix) and entry.name.endswith('.tmp') and entry.is_file()]
    except OSError:
        strays = []
    for stray in strays:
        remove_temporary_file(stray)


def _import_publish(candidate, source, copier, overwrite):
    """发布一份副本；失败时清本轮残留，未存在过的目标不留半文件。"""
    from infra.file_cache import remove_temporary_file
    existed = candidate.exists()
    try:
        copier(candidate, source, overwrite)
    except Exception:
        _clean_import_temp(candidate)
        if not existed:
            remove_temporary_file(candidate)
        raise
    return candidate


def _import_candidates(target):
    """「保留两份」的改名序列：``stem(2).ext``、``stem(3).ext``……递增。"""
    for number in range(2, 1000):
        yield target.with_name('%s(%d)%s' % (target.stem, number, target.suffix))


def _import_one(target, source, conflict, copier):
    """单份导入：同名先经 ``conflict`` 决策（覆盖／保留两份／取消），缺省不覆盖。"""
    if not target.exists():
        _import_publish(target, source, copier, False)
        return 'imported', target
    decision = conflict(target.name) if callable(conflict) else 'cancel'
    if decision == 'rename':
        for candidate in _import_candidates(target):
            try:
                _import_publish(candidate, source, copier, False)
                return 'imported', candidate
            except FileExistsError:
                continue
        raise ValueError('无法生成不重名的导入文件名')
    if decision != 'overwrite':
        return 'skipped', target.name
    _import_publish(target, source, copier, True)
    return 'imported', target


def import_into_stage(root, stage, sources, *, conflict=None, copier=None):
    """把本机文件复制进 ``write_dir(root, stage)``，并写索引增量与来源登记。

    ``conflict(文件名) -> 'overwrite'|'rename'|'cancel'``；缺省按取消——绝不静默覆盖。
    ``copier(target, source, overwrite)`` 是复制器注入点，默认 ``agent.core`` 原子发布。
    原文件只读不动；单份失败记 ``rejected`` 并继续，不留半个文件。
    """
    from infra import file_index
    copier = copier or _default_import_copier
    allowed = import_suffixes(stage)
    result = {'imported': [], 'skipped': [], 'rejected': []}
    for raw in sources:
        name = PureWindowsPath(str(raw)).name or str(raw)
        try:
            _dir, target = _import_target(root, stage, raw)
            _check_importable(Path(raw), stage, allowed)
        except (OSError, ValueError) as exc:
            result['rejected'].append((name, str(exc)))
            continue
        try:
            outcome, path = _import_one(target, Path(raw), conflict, copier)
        except (OSError, ValueError) as exc:
            result['rejected'].append((target.name, '复制失败：' + str(exc)))
            continue
        if outcome == 'skipped':
            result['skipped'].append(path)
        else:
            result['imported'].append(path)
    if result['imported']:
        from contract.file_index_contract import ORIGIN_USER
        file_index.update(root, result['imported'])
        file_index.record_origin(root, result['imported'], ORIGIN_USER)
    return result
