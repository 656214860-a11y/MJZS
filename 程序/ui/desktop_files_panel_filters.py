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
from ui_widgets import LineInput, SecondaryButton, Tooltip
import ui.desktop_files_panel_index as files_panel_index
from ui.desktop_files_panel_index import (
    COLUMN_TITLES, DEFAULT_GROUP_MODE, FilesPanelIndexMixin,
    SCRIPT_NAME_CELL_PAD, SORTABLE_COLUMNS,
    append_kind_menu, cancel_auto_refresh, install_auto_refresh,
    schedule_auto_refresh, teardown_auto_refresh,
)


class _KeywordVarProxy:
    """兼容 ``keyword_var.get()/set()``，同时保持 ``LineInput`` 占位文字不被污染。"""

    def __init__(self, entry):
        self._entry = entry

    def get(self):
        return self._entry.get()

    def set(self, value):
        text = str(value or '')
        try:
            self._entry.delete(0, 'end')
            if text:
                self._entry.insert(0, text)
            elif hasattr(self._entry, '_restore_placeholder'):
                self._entry._restore_placeholder()
        except tk.TclError:
            pass

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


class FilesPanelFilterMixin(FilesPanelIndexMixin):
    """阶段图标列＋筛选条＋按索引填表。"""

    # ── 筛选条：半宽搜索框（占位“搜索文件”）＋ 同行分组下拉（带二级目录卡） ──
    def _build_filter_bar(self):
        """单行紧凑筛选条：左半「搜索文件」输入框，右半「分组」下拉（集成状态/阶段/类型/日期二级目录卡）。"""
        bar = ttk.Frame(self.script_box)
        bar.pack(side='top', fill='x', pady=(SPACING['none'], SPACING['xs']))
        self.filter_bar = bar
        row_one = ttk.Frame(bar)
        row_one.pack(side='top', fill='x')
        row_one.columnconfigure(0, weight=1, uniform='files_filter_half')
        row_one.columnconfigure(1, weight=1, uniform='files_filter_half')
        self.keyword_entry = LineInput(row_one, placeholder='搜索文件', width=FILTER_KEYWORD_WIDTH)
        self.keyword_entry.grid(row=0, column=0, sticky='ew')
        self.keyword_entry.bind('<KeyRelease>', self._keyword_changed)
        Tooltip(self.keyword_entry, '按文件名关键字筛选（回车立即生效）')
        self.keyword_var = _KeywordVarProxy(self.keyword_entry)
        tail = ttk.Frame(row_one)
        tail.grid(row=0, column=1, sticky='ew', padx=(SPACING['xs'], SPACING['none']))
        self.group_label = ttk.Label(tail, text='分组', style='Muted.TLabel')
        self.group_label.pack(side='left')
        self.group_button = SecondaryButton(tail, text=DEFAULT_GROUP_MODE + ' ▾',
                                            command=self._toggle_group_menu)
        self.group_button.pack(side='left', fill='x', expand=True, padx=(SPACING['xs'], SPACING['none']))
        Tooltip(self.group_button, '分组与筛选：类型／阶段／状态（草稿·定稿·归档）／日期（悬停右侧展开二级目录卡）')
        self.group_menu = files_panel_index.GroupMenuPopup(self)
        self._reset_filter_boxes()

    def _toggle_group_menu(self):
        menu = getattr(self, 'group_menu', None)
        if menu is not None:
            menu.toggle()

    def _close_group_menu(self):
        menu = getattr(self, 'group_menu', None)
        if menu is not None and menu.is_open():
            menu.close()
            return True
        return False

    def _sync_group_button_text(self):
        button = getattr(self, 'group_button', None)
        if button is None:
            return
        mode = getattr(self, 'group_mode', DEFAULT_GROUP_MODE)
        sub = None
        if mode == '类型':
            sub = getattr(self, 'kind_filter', None)
        elif mode == '阶段':
            stage = getattr(self, 'stage_filter', None)
            if stage:
                from contract.pet_bus import stage_name
                sub = stage_name(stage)
        elif mode == '状态':
            sub = getattr(self, 'status_filter', None)
        elif mode == '日期':
            sub = getattr(self, 'date_filter', None)
        text = ('%s · %s ▾' % (mode, sub)) if sub else ('%s ▾' % mode)
        try:
            button.configure(text=text)
        except tk.TclError:
            pass

    def _sync_sort_headings(self):
        """在可排序列的表头上显示当前排序方向；文件名与时长／分辨率无排序箭头。"""
        tree = getattr(self, 'script_tree', None)
        if tree is None:
            return
        active = getattr(self, 'sort_column', 'kind')
        desc = getattr(self, 'sort_desc', False)
        for key, base in COLUMN_TITLES.items():
            if key in SORTABLE_COLUMNS and key == active:
                label = base + (' ▼' if desc else ' ▲')
            else:
                label = base
            try:
                tree.heading(key, text=label)
            except tk.TclError:
                pass

    def sort_by_column(self, column):
        """点击可排序列表头切换排序；文件名与时长／分辨率不排序。"""
        if column not in SORTABLE_COLUMNS:
            return
        self._ensure_filter_state()
        if self.sort_column == column:
            self.sort_desc = not self.sort_desc
        else:
            self.sort_column = column
            self.sort_desc = column in ('mtime', 'size')
        self.sort_mode = '修改时间' if column == 'mtime' else COLUMN_TITLES.get(column, '类型')
        self._sync_sort_headings()
        self._reload_current_view()

    def select_group_option(self, mode, value=None):
        """选择分组主项或右侧二级目录卡条目：同步分组维度与筛选条件。"""
        self._ensure_filter_state()
        if mode not in files_panel_index.GROUP_MODES:
            mode = DEFAULT_GROUP_MODE
        self.group_mode = mode
        self.kind_filter = None
        self.status_filter = None
        self.date_filter = None
        if mode == '类型':
            self.kind_filter = value
        elif mode == '状态':
            if not self.library_view:
                self.status_filter = value
        elif mode == '日期':
            self.date_filter = value
        elif mode == '阶段':
            self.library_view = False
            self.stage_filter = value
            self._stage_filter_pinned = value is not None
            self._followed_page_stage = self._page_stage()
            self._sync_stage_title()
        self._sync_group_button_text()
        self._sync_stage_buttons()
        self._reload_current_view()

    def change_file_kind(self, row, kind):
        """右键手动更改文件类型（空串／None 恢复自动识别）并持久化。"""
        from infra import file_index
        path = self.index_file_path(row)
        file_index.record_kind(self.page.root, [path], kind)
        self._reload_current_view()
        if kind:
            self.page.status.set('已将 %s 类型设为「%s」' % (path.name, kind))
        else:
            self.page.status.set('已恢复 %s 的自动类型识别' % path.name)

    def _reset_filter_boxes(self):
        """搜索框回空并恢复占位提示，同步分组按钮文案。"""
        if getattr(self, 'keyword_var', None) is not None:
            self.keyword_var.set('')
        self._sync_group_button_text()

    def _reset_filters(self):
        """全部筛选与分组条件复位（换项目时用）：默认当前页＋按类型分组。"""
        self._close_group_menu()
        self.stage_filter = None
        self.kind_filter = None
        self.status_filter = None
        self.date_filter = None
        self.keyword_filter = ''
        self.library_view = False
        self.group_mode = DEFAULT_GROUP_MODE
        self.sort_column = 'kind'
        self.sort_desc = False
        self.sort_mode = '类型'
        self._stage_filter_pinned = False
        self._followed_page_stage = _FOLLOWED_STAGE_SENTINEL
        self._reset_filter_boxes()
        self._sync_sort_headings()
        self._sync_stage_buttons()
        title = getattr(self, 'script_title', None)
        if title is not None:
            title.configure(text='项目文件')

    def _sync_view_filters(self):
        """默认只显示当前页面阶段文件；手动跨阶段钉住或选「全部阶段」时保留，切页后跟随新页。"""
        if getattr(self, 'library_view', False):
            self._sync_group_button_text()
            return
        current = self._page_stage()
        if getattr(self, '_stage_filter_pinned', False) and self.stage_filter is not None:
            self._sync_stage_title()
            self._sync_stage_buttons()
            self._sync_group_button_text()
            return
        if current != getattr(self, '_followed_page_stage', _FOLLOWED_STAGE_SENTINEL):
            self.stage_filter = current
            self._followed_page_stage = current
            self._sync_stage_title()
            self._sync_stage_buttons()
        self._sync_group_button_text()

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
        """应用关键字与当前分组/状态条件并重填列表。"""
        self._filter_job = None
        if self.library_view:
            self.stage_filter = None
            self.status_filter = None
        self.keyword_filter = str(self.keyword_var.get()).strip()
        self._sync_group_button_text()
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
        return any((self.stage_filter, self.kind_filter, self.status_filter,
                    getattr(self, 'date_filter', None), self.keyword_filter))

    def show_library(self):
        """切到全局素材库视图：只读库索引，不扫盘；未设置目录时提示用户先设置。"""
        from infra import file_index
        self._ensure_filter_state()
        self._close_group_menu()
        self.library_view = True
        self._sync_view_filters()
        self.stage_filter = None
        self.status_filter = None
        self.date_filter = None
        self.keyword_filter = ''
        self._reset_filter_boxes()
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
            if len(values) > 5 and values[5]:
                continue
            path = self._row_abs_path(item)
            if path is None or asset_thumbs.media_kind(path) is None:
                continue
            text = self._row_meta_text(path)
            if not text:
                continue
            tree.item(item, values=tuple(values[:5]) + (text,))
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
            self.date_filter = None
            self.keyword_filter = ''
            self._filter_job = None
            self.library_view = False
            self.sort_column = 'kind'
            self.sort_desc = False
            self.sort_mode = '类型'
            self.group_mode = DEFAULT_GROUP_MODE
            self._meta_refresh_job = None
            self._library_root = None
            self.script_row_stage = {}      # iid → 阶段显示名（另存为预填名用）
            self._stage_filter_pinned = False
            self._followed_page_stage = _FOLLOWED_STAGE_SENTINEL
        if not hasattr(self, '_stage_filter_pinned'):
            self._stage_filter_pinned = False

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
        """S04 按阶段语义分组；其余视图按 group_mode 与表头排序方向归组。"""
        mode = getattr(self, 'group_mode', DEFAULT_GROUP_MODE)
        sort_col = getattr(self, 'sort_column', 'kind')
        sort_desc = getattr(self, 'sort_desc', False)
        if (not library and mode in ('阶段', '类型') and not getattr(self, 'kind_filter', None)
                and getattr(self, 'stage_filter', None) == 'animatic'):
            return files_panel_index.animatic_grouped_rows(rows)
        if library or mode != '阶段' or not self._stage_filter_is_followed():
            return files_panel_index.grouped_rows(rows, mode, library,
                                                  sort_col=sort_col, sort_desc=sort_desc)
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
    if root is None or not panel._open:
        panel._clear_index_tree()
        return
    generation = panel._index_generation
    panel._index_loading = True
    context = panel._index_context(root, library)
    if context != getattr(panel, '_displayed_index_context', None):
        panel._clear_index_tree()
    filters = (panel.stage_filter, panel.kind_filter, panel.status_filter,
               getattr(panel, 'date_filter', None), panel.keyword_filter,
               getattr(panel, 'sort_column', 'kind'), getattr(panel, 'sort_desc', False))
    refresh = getattr(panel, '_index_refresh', False)
    panel._index_refresh = False
    discover_stage = None if panel._stage_filter_is_followed() else filters[0]

    def work():
        if not panel._index_current_without_tk(generation, context):
            return None
        rows, categories, labels = files_panel_index.load_index(
            root, library, refresh, stage=discover_stage)
        return panel._filter_index_rows(rows, filters, library), categories, labels, tuple(rows)

    def done(result):
        if result is None or not panel._index_current(generation, context):
            return
        from infra import file_index
        panel._index_loading = False
        found, categories, panel._index_file_labels, panel._all_index_rows = result
        panel._last_rendered_rev = file_index.change_revision(root)
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
    panel._displayed_index_context = context
    panel.script_tree.tag_configure('missing', foreground=COLORS['text_muted'])
    groups = panel._index_groups(rows, library)
    show_groups = files_panel_index.should_show_groups(groups)
    panel._index_group_count = len(groups)
    files_panel_index.configure_tree_leading_column(
        panel.script_tree, groups, preview_width=PANEL_PREVIEW_COL_WIDTH)
    if show_groups:
        for group, label, _members in groups:
            opened = files_panel_index.group_default_open(group)
            panel.script_tree.insert('', 'end', iid=group, open=opened, values=(label, '', '', '', '', ''))
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
