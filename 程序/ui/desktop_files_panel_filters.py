# -*- coding: utf-8 -*-
"""项目文件停靠面板的阶段快捷图标列与筛选条（R3106，任务书 P1）。

自 ``desktop_files_panel.ProjectFilesPanel`` 拆出：类行数棘轮上限 600 行
（``test_complexity_ratchet``），筛选条与图标列是本轮新增的一块独立职责。
宿主须提供 ``page``／``script_box``／``script_tree``／``script_row_details``／
``script_row_category``／``_open`` 等已有成员。
"""
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from ui_tokens import SPACING
from ui_widgets import LineInput, SecondaryButton, SelectBox, Tooltip
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
        asset_thumbs.prefetch_media(self.page.win, paths, configured=self._media_config())

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
            self._followed_page_stage = _FOLLOWED_STAGE_SENTINEL

    def _build_stage_rail(self):
        """建右缘阶段图标列：「全部」＋ 13 个阶段，顺序＝``pet_bus.STAGES``。

        R3191（任务书 M3，D10）：图标用 ``assets/nav/<stage>_files.png``（阶段字形＋右下角
        文件角标），PNG 缺失时退回 ``STAGE_RAIL_ICONS`` 的 emoji；高度不够时整列可滚轮滚动。
        """
        from contract.pet_bus import STAGES, stage_name
        from responsive_ui import ScrollForm
        from ui_icons import IconLoader
        from ui_tokens import COLORS
        self._ensure_filter_state()
        # R3971（任务书 L4-U1）：齿轮设置钮钉在列顶——pack 先于滚动画布，
        # 否则它落进滚动条与画布之间的中间腔，把画布挤成 1px 宽。
        settings = SecondaryButton(self.stage_rail, text='⚙', width=0, style='RailIcon.TButton',
                                   command=self.configure_library)
        settings.pack(side='top', pady=(SPACING['none'], SPACING['xs']))
        Tooltip(settings, '设置全局素材库目录')
        self.library_settings_button = settings
        # 图标列自身仍是 script_box 右缘的固定竖条；内部换成可滚动画布，矮窗口不再裁掉底部图标。
        self.stage_rail_scroller = ScrollForm(self.stage_rail, bg=COLORS['background_primary'])
        self.stage_rail_form = self.stage_rail_scroller.form
        self.stage_buttons = {}
        entries = [(None, 'project_files', STAGE_RAIL_ALL, '全部文件（剧本准备四类）')]
        entries += [(stage, stage + '_files', STAGE_RAIL_ICONS.get(stage, '•'), stage_name(stage))
                    for stage in STAGES]
        for stage, icon_name, glyph, tip in entries:
            image = IconLoader.nav_icon(self.page.win, icon_name)
            # 有 PNG 时 compound='image' 只显示图，text 仍留 emoji 作语义标签与缺图兜底。
            if image is not None:
                button = SecondaryButton(self.stage_rail_form, text=glyph, image=image,
                                         compound='image', width=0, style='RailIcon.TButton',
                                         command=lambda value=stage: self.show_stage(value))
            else:
                button = SecondaryButton(self.stage_rail_form, text=glyph, width=0,
                                         style='RailIcon.TButton',
                                         command=lambda value=stage: self.show_stage(value))
            button._rail_icon_name = icon_name
            button.pack(side='top', pady=(SPACING['none'], SPACING['xs']))
            Tooltip(button, tip)
            self.stage_buttons[stage] = button
        self._sync_stage_buttons()
        # R3117（任务书 P2，Q5）：回收站入口放在图标列末尾——浏览／恢复走既有恢复窗，
        # 清空只删超过保留期的批次，物理删除仍只经 storage_maintenance。
        self._add_rail_action('♻', '回收站：浏览与恢复已删除的文件', 'open_recycle_recovery')
        self._add_rail_action('🗑', '清空过期回收站（保留 %d 天）' % _retention_days(), 'purge_expired_recycle')
        # R3143（任务书 P3，Q11）：全局素材库视图——跨项目的共享素材，按库相对路径列出。
        library = SecondaryButton(self.stage_rail_form, text='🗂', width=0, style='RailIcon.TButton',
                                  command=self.show_library)
        library.pack(side='top', pady=(SPACING['none'], SPACING['xs']))
        Tooltip(library, '全局素材库：跨项目的共享素材（可在设置里指定目录）')
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

    def _add_rail_action(self, glyph, tip, method_name):
        """在图标列末尾追加一个动作钮；宿主没有该动作时只留按钮不绑回调。"""
        action = getattr(self.page, method_name, None)
        command = (lambda: self.page.safe(action)) if callable(action) else None
        button = SecondaryButton(self.stage_rail_form, text=glyph, width=0, style='RailIcon.TButton',
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

    def _sync_stage_title(self):
        """面板标题跟着当前阶段走：「项目文件 · <阶段名>」，全部＝「项目文件 · 全部阶段」。"""
        title = getattr(self, 'script_title', None)
        if title is None:
            return
        from contract.pet_bus import stage_name
        text = '全部阶段' if self.stage_filter is None else stage_name(self.stage_filter)
        try:
            title.configure(text='项目文件 · ' + text)
        except tk.TclError:
            pass

    def show_stage(self, stage=None):
        """点阶段图标：写当前阶段并同步面板标题，再按筛选条件重填（``None``＝不限阶段）。"""
        self._ensure_filter_state()
        self.library_view = False
        self.stage_filter = stage
        self._sync_stage_title()
        self._sync_stage_buttons()
        self._reload_current_view()

    def _fill_index_list(self):
        """默认全部与筛选视图共用全项目索引，首次重建不阻塞主线程。"""
        self._request_index(getattr(self.page, 'root', None))
