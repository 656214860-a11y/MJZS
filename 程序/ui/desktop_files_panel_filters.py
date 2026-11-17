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

# R3094（任务书 P1，Q8 补充需求）：停靠面板右缘的阶段快捷图标列，顺序＝pet_bus.STAGES。
# R3191（任务书 M3，REQ-S01-93）：图标优先用 assets/nav/<stage>_files.png（IconLoader.nav_icon），
# PNG 缺失退回本表 Unicode 符号；每个图标都带 Tooltip 中文名。
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

# 任务书 M5（REQ-S01-95/96）：预览列图元长边与列宽、时长／分辨率列宽全部 token 派生；
# 视频封面 16:9（40×22）与音频波形（40×13）落在字高行内，行高仍由字体 token 量。
PANEL_PREVIEW_SIZE = SPACING['2xl'] + SPACING['sm']            # 40：预览图长边上限
PANEL_PREVIEW_COL_WIDTH = PANEL_PREVIEW_SIZE + SPACING['sm']   # 48：预览列宽
PANEL_META_WIDTH = SPACING['xl'] * 5                            # 120：时长／分辨率列宽


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
        self.script_row_stage.clear()
        if library is None:
            return
        try:
            found = file_index.search_global(library, kind=self.kind_filter)
        except (OSError, ValueError):
            found = []
        self._library_root = library
        # 任务书 M5（REQ-S01-95）：素材库视图同样开预览列（封面／波形走 #0）。
        self.script_tree.configure(show='tree headings')
        for row in found:
            item_id = 'library:' + row.path
            self.script_row_details[item_id] = '%s · %s · %s' % (row.title or row.path, row.kind, str(library))
            self.script_row_category[item_id] = STAGE_FILTER_ROW_CATEGORY
            self.script_row_stage[item_id] = '素材库'
            path = Path(library) / row.path
            self.script_tree.insert('', 'end', iid=item_id, text='',
                                    image=self._row_preview(path) or '',
                                    values=('[素材库] ' + row.path.split('/')[-1],
                                            self._row_meta_text(path)))
        self._schedule_meta_refresh()
        # 任务书 M4：库里的视频／音频同样后台补封面，缺项下次打开自动重试。
        self._prefetch_media_thumbs([Path(library) / row.path for row in found])

    def _media_config(self):
        """项目 config.json 里的 ffmpeg/ffprobe 显式配置；没有读给 None（随包／PATH 兜底）。"""
        root = getattr(self.page, 'root', None)
        if root is None:
            return None
        try:
            from file_cache import read_json
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
        for item in tree.get_children():
            values = tree.item(item, 'values')
            if len(values) > 1 and values[1]:
                continue
            path = self._row_abs_path(item)
            if path is None or asset_thumbs.media_kind(path) is None:
                continue
            text = self._row_meta_text(path)
            if not text:
                continue
            tree.item(item, values=(values[0] if values else '', text))
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
    def _ensure_filter_state(self):
        """首次装配前补齐筛选状态（宿主 ``__init__`` 不感知这些字段）。"""
        if not hasattr(self, 'stage_filter'):
            self.stage_filter = None
            self.kind_filter = None
            self.status_filter = None
            self.keyword_filter = ''
            self._filter_job = None
            self.library_view = False
            self._meta_refresh_job = None
            self._library_root = None
            self.script_row_stage = {}      # iid → 阶段显示名（另存为预填名用）

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
        from contract.pet_bus import stage_name
        self.cancel_script_load()
        # 任务书 M5（REQ-S01-95）：索引视图开预览列（#0 挂封面／波形图元）。
        self.script_tree.configure(show='tree headings')
        self.script_tree.delete(*self.script_tree.get_children())
        self.script_row_details.clear()
        self.script_row_category.clear()
        self.script_row_stage.clear()
        self._library_root = None
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
            self.script_row_stage[row.path] = stage_name(row.stage)
            path = Path(root) / row.path
            image = self._row_preview(path) if not row.missing else None
            self.script_tree.insert('', 'end', iid=row.path, text='', image=image or '',
                                    values=(label + name, self._row_meta_text(path)))
        self._schedule_meta_refresh()
        # 任务书 M4：索引视图里的视频／音频后台预生成封面与波形（缺失文件跳过，
        # stat 不到本就不该排队）；启动路径不扫描，这里只在面板已打开、索引已填表时跑。
        self._prefetch_media_thumbs([Path(root) / row.path for row in found if not row.missing])
