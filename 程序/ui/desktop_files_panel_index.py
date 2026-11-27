# -*- coding: utf-8 -*-
"""项目文件索引视图：后台加载、阶段分组和有界 Tk 渲染。"""
from pathlib import Path
from datetime import datetime
from types import SimpleNamespace
import threading
import time
import tkinter as tk
from tkinter import ttk

from contract import file_naming
from contract.file_index_contract import (
    FileRow, STATUS_ARCHIVED, STATUS_DRAFT, STATUS_FINAL, STATUSES, normalize_status,
)
from contract.pet_bus import STAGES, stage_name
from ui_tokens import COLORS, SCRIPT_FILE_MAX_ROWS, SPACING
from ui.desktop_file_card import script_row_card

GROUP_PREFIX = 'stage-group:'
ANIMATIC_GROUP_PREFIX = GROUP_PREFIX + 'animatic:'
GROUP_MODES = ('类型', '阶段', '状态', '日期')
DEFAULT_GROUP_MODE = '类型'
SORTABLE_COLUMNS = ('status', 'kind', 'mtime', 'size')
COLUMN_TITLES = {
    'name': '文件名',
    'status': '状态',
    'kind': '类型',
    'mtime': '时间',
    'size': '大小',
    'meta': '时长／分辨率',
}
KIND_WORKFLOW_ORDER = {kind: idx for idx, kind in enumerate(file_naming.KINDS)}
STATUS_WORKFLOW_ORDER = {STATUS_FINAL: 0, STATUS_DRAFT: 1, STATUS_ARCHIVED: 2}
ANIMATIC_GROUP_SPECS = (
    ('refs', '参考图库', True),
    ('versions', '预演版本', True),
    ('shots', '镜头草图', False),
    ('audio', '临时声音', True),
    ('other', '其他预演文件', False),
)
_ANIMATIC_GROUP_OPEN = {ANIMATIC_GROUP_PREFIX + key: opened for key, _label, opened in ANIMATIC_GROUP_SPECS}
_MEDIA_PREFETCH_CAP = 40
RENDER_BATCH = SPACING['sm'] * 4
THUMB_SIZE = SPACING['lg']
TREE_DISCLOSURE_WIDTH = SPACING['lg'] + SPACING['xs']   # 20：无缩略图时仅留展开箭头宽，文件名紧贴左缘
TREE_PREVIEW_DEFAULT_WIDTH = SPACING['2xl'] + SPACING['lg']   # 48：与 PANEL_PREVIEW_COL_WIDTH 同宽
# R4005（任务书 L4-U3）：文件名列优先——只剩文件名列仍不够宽时文件名
# 中间省略；省略要量真实像素，测宽函数由调用方注入（ui_popup.measure_text_width）。
SCRIPT_NAME_CELL_PAD = SPACING['sm']             # 8：文件名单元格留白
SCRIPT_NAME_HEAD = SPACING['sm']                 # 8：中间省略至少保留的开头字符数
SCRIPT_CATEGORIES = {'项目设定': 'setting', '项目大纲': 'outline',
                     '剧本大纲': 'outline', '角色卡': 'character', '项目剧本': 'script'}


def script_category(row):
    """索引中的剧本四类沿用原操作；其他文件不暴露剧本专属动作。"""
    if row.stage != 'script' or Path(row.path).suffix.lower() not in ('.md', '.txt', '.docx'):
        return 'index'
    for part in reversed(Path(row.path).parts[:-1]):
        if part in SCRIPT_CATEGORIES:
            return SCRIPT_CATEGORIES[part]
    name = Path(row.path).stem
    for label, category in SCRIPT_CATEGORIES.items():
        if label in name:
            return category
    if row.kind == '剧本':
        return 'script'
    return 'index'


def _merge_animatic_references(root, rows):
    """S04 视图就地补齐共享参考图库：不写磁盘索引、不扫 .work/，同路径转正不重复。"""
    from dataclasses import replace
    import stage_execution_service
    try:
        library = stage_execution_service.animatic_reference_library(root) or {}
    except (OSError, ValueError):
        return
    base = Path(root).resolve()
    positions = {row.path: idx for idx, row in enumerate(rows)}
    for items in library.values():
        for item in items or ():
            raw_path = item.get('path') if isinstance(item, dict) else item
            if not raw_path:
                continue
            try:
                path = Path(raw_path).resolve()
                relative = path.relative_to(base).as_posix()
            except (OSError, ValueError):
                continue
            if '.work' in Path(relative).parts:
                continue
            try:
                info = path.stat()
                size, mtime = int(info.st_size), float(info.st_mtime)
            except OSError:
                size, mtime = 0, 0.0
            idx = positions.get(relative)
            if idx is not None:
                existing = rows[idx]
                if existing.stage != 'animatic' or existing.missing:
                    rows[idx] = replace(
                        existing, stage='animatic', kind='参考',
                        size=size or existing.size, mtime=mtime or existing.mtime,
                        missing=False)
            else:
                positions[relative] = len(rows)
                rows.append(FileRow(
                    path=relative, stage='animatic', kind='参考',
                    size=size, mtime=mtime))


def load_index(root, library=False, refresh=False, stage=None):
    """只在 Desktop 后台任务执行；首次重建也在此线程。"""
    from infra import file_index
    if refresh:
        if library:
            file_index.rebuild_global(root)
        else:
            file_index.rebuild(root)
    if (not library) and (not refresh):
        file_index.discover(root, stage)
    rows = file_index.global_rows(root) if library else file_index.rows(root)
    categories = {}
    if not library:
        from domain.script_workspace_service import iter_script_documents
        known = {row.path for row in rows}
        for document in iter_script_documents(root):
            try:
                relative = document.path.resolve().relative_to(Path(root).resolve()).as_posix()
            except (OSError, ValueError):
                continue
            categories[relative] = document.category
            if relative not in known:
                doc_kind = '剧本' if document.category == 'script' else '参考'
                rows.append(FileRow(path=relative, stage='script', kind=doc_kind,
                                    mtime=document.modified_at))
                known.add(relative)
        if stage == 'animatic':
            _merge_animatic_references(root, rows)
    if not library:
        from writing_api import preparation_file_labels
        labels = preparation_file_labels(root)
    else:
        labels = {}
    return rows, categories, labels


def sort_rows(rows, sort_col='kind', sort_desc=False):
    """按可排序列（状态／类型／时间／大小）排序；类型与状态按工作流顺序排列。"""
    def kind_rank(row):
        return KIND_WORKFLOW_ORDER.get(row.kind, len(KIND_WORKFLOW_ORDER))

    def status_rank(row):
        return STATUS_WORKFLOW_ORDER.get(normalize_status(row.status), len(STATUS_WORKFLOW_ORDER))

    if sort_col == 'status':
        rows.sort(key=lambda row: (-status_rank(row) if sort_desc else status_rank(row),
                                   kind_rank(row), row.order, row.path))
    elif sort_col == 'mtime':
        rows.sort(key=lambda row: (-row.mtime if sort_desc else row.mtime,
                                   kind_rank(row), row.path))
    elif sort_col == 'size':
        rows.sort(key=lambda row: (-row.size if sort_desc else row.size,
                                   kind_rank(row), row.path))
    else:
        rows.sort(key=lambda row: (-kind_rank(row) if sort_desc else kind_rank(row),
                                   row.order, row.path))
    return rows


def filtered_rows(rows, filters, library=False):
    """全局库没有项目阶段/状态；支持 7 元新签名与 5 元旧签名。"""
    if len(filters) >= 7:
        stage, kind, status, date_val, keyword, sort_col, sort_desc = filters[:7]
    else:
        stage, kind, status, keyword, sort = filters
        date_val = None
        sort_col = 'mtime' if sort == '修改时间' else 'kind'
        sort_desc = sort == '修改时间'
    wanted_status = normalize_status(status) if status else None
    keyword = str(keyword or '').casefold()
    from infra import file_index
    selected = [row for row in rows
                if (library or not stage or row.stage == stage)
                and (not kind or row.kind == kind)
                and (library or not wanted_status or normalize_status(row.status) == wanted_status)
                and (not date_val or row_metadata(row)[1] == date_val)
                and (not keyword or keyword in row.path.casefold())
                and not file_index.is_functional(row.path)]
    return sort_rows(selected, sort_col, sort_desc)


def row_metadata(row):
    """只格式化已缓存的索引字段；时间列只显示年月日（删除时分秒）。"""
    size = max(0, row.size)
    amount = float(size)
    unit = 'B'
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if amount < 1024 or unit == 'TB':
            break
        amount /= 1024
    size_text = ('%d B' % size) if unit == 'B' else ('%.1f %s' % (amount, unit))
    modified = datetime.fromtimestamp(row.mtime).strftime('%Y-%m-%d') if row.mtime else '未知'
    return size_text, modified


def grouped_rows(rows, mode=DEFAULT_GROUP_MODE, library=False, *, sort_col='kind', sort_desc=False):
    """按类型（默认）／阶段／状态／日期归组，组序与工作流顺序和表头排序方向对齐。"""
    groups = {}
    for row in rows:
        if mode == '类型':
            key = row.kind or '其他'
        elif mode == '状态':
            key = normalize_status(row.status) or STATUS_DRAFT
        elif mode == '日期':
            key = row_metadata(row)[1]
        else:
            key = 'library' if library else (row.stage if row.stage in STAGES else '')
        groups.setdefault(key, []).append(row)
    if mode == '类型':
        ordered = sorted(groups, key=lambda k: KIND_WORKFLOW_ORDER.get(k, len(KIND_WORKFLOW_ORDER)),
                         reverse=(sort_col == 'kind' and sort_desc))
        return [('kind-group:' + key, '%s (%d)' % (key, len(groups[key])), groups[key]) for key in ordered]
    if mode == '状态':
        ordered = sorted(groups, key=lambda k: STATUS_WORKFLOW_ORDER.get(k, len(STATUS_WORKFLOW_ORDER)),
                         reverse=(sort_col == 'status' and sort_desc))
        return [('status-group:' + key, '%s (%d)' % (key, len(groups[key])), groups[key]) for key in ordered]
    if mode == '日期':
        desc = not (sort_col == 'mtime' and not sort_desc)
        keys = sorted((key for key in groups if key != '未知'), reverse=desc)
        keys += ['未知'] if '未知' in groups else []
        return [('date-group:' + key, '%s (%d)' % (key, len(groups[key])), groups[key]) for key in keys]
    keys = ['library'] if library else [*STAGES, '']
    return [(GROUP_PREFIX + key,
             ('全局素材库 (%d)' % len(groups[key])) if library else (
                 '%s (%d)' % (stage_name(key), len(groups[key])) if key else '其他文件 (%d)' % len(groups[key])),
             groups[key]) for key in keys if key in groups]


def animatic_bucket(row):
    """S04 语义归类：参考图库／预演版本／镜头草图／临时声音／其他预演文件。"""
    from infra import file_index
    posix = str(row.path or '').replace('\\', '/')
    parts = Path(posix).parts
    parents = parts[:-1]
    suffix = Path(posix).suffix.lower()
    if posix.startswith('_shared/reference_images/') or '参考图' in parents:
        return 'refs'
    if '版本' in parents or suffix in file_index.VIDEO_SUFFIXES or row.kind == '视频':
        return 'versions'
    if '镜头' in parents or any(part.lower() == 'shots' for part in parents):
        return 'shots'
    if '声音' in parents or suffix in file_index.AUDIO_SUFFIXES or row.kind == '音频':
        return 'audio'
    return 'other'


def animatic_grouped_rows(rows):
    """仅用于 S04（stage_filter == 'animatic' 且按阶段分组）的语义分组。"""
    buckets = {}
    for row in rows:
        buckets.setdefault(animatic_bucket(row), []).append(row)
    return [
        (ANIMATIC_GROUP_PREFIX + key, '%s (%d)' % (label, len(buckets[key])), buckets[key])
        for key, label, _opened in ANIMATIC_GROUP_SPECS
        if key in buckets
    ]


def group_default_open(group_id):
    """S04 折叠组默认收起；其他分组沿用默认展开。"""
    return _ANIMATIC_GROUP_OPEN.get(group_id, True)


def should_show_groups(groups):
    """只要存在分组（含单阶段／单类型／单状态／单日期）就展示可折叠分组标题行与三角图标。"""
    return bool(groups)


def prefetch_media_paths(groups, root, cap=_MEDIA_PREFETCH_CAP):
    """只收集默认展开组的非缺失文件路径，且上限 cap 项，防止几百镜冲爆缩略图队列。"""
    paths = []
    for group_id, _label, members in groups:
        if not group_default_open(group_id):
            continue
        for row in members:
            if row.missing:
                continue
            paths.append(Path(root) / row.path)
            if len(paths) >= cap:
                return paths
    return paths


def _load_group_previews(panel, tree, item, base):
    """展开默认折叠组时按需补齐前 _MEDIA_PREFETCH_CAP 项缩略图并预取媒体封面。"""
    try:
        children = tree.get_children(item) if item and panel.is_file_group(item) else ()
    except tk.TclError:
        return
    if not children:
        return
    paths = []
    for child in children[:_MEDIA_PREFETCH_CAP]:
        row = getattr(panel, '_index_rows', {}).get(child)
        if row is None or row.missing:
            continue
        path = Path(base) / row.path
        paths.append(path)
        if child not in getattr(panel, '_index_images', {}) and hasattr(panel, '_row_preview'):
            image = panel._row_preview(path)
            if image is not None:
                panel._index_images[child] = image
                try:
                    tree.item(child, image=image)
                except tk.TclError:
                    pass
    if paths and hasattr(panel, '_prefetch_media_thumbs'):
        panel._prefetch_media_thumbs(paths)


def bind_lazy_group_previews(panel, root):
    """仅绑定一次 <<TreeviewOpen>>，展开折叠组时按需补图。"""
    tree = getattr(panel, 'script_tree', None)
    if tree is None:
        return
    tree._lazy_preview_root = root
    if getattr(tree, '_lazy_preview_bound', False):
        return
    tree._lazy_preview_bound = True

    def on_open(_event=None):
        base = getattr(tree, '_lazy_preview_root', None)
        if base is None:
            return
        try:
            item = tree.focus()
        except tk.TclError:
            return
        _load_group_previews(panel, tree, item, base)

    try:
        tree.bind('<<TreeviewOpen>>', on_open, add='+')
    except tk.TclError:
        pass


def configure_tree_leading_column(tree, groups, *, preview_width=None):
    """按是否存在分组与缩略图配置 #0 树列；有分组时始终显示折叠三角图标。"""
    from infra import file_index
    has_thumb = any(
        not row.missing and (row.kind in ('资产', '音频', '视频')
                             or Path(row.path).suffix.lower() in file_index.IMAGE_SUFFIXES)
        for _group, _label, members in groups for row in members)
    show_groups = should_show_groups(groups)
    if not show_groups and not has_thumb:
        tree.configure(show='headings')
        tree.column('#0', width=SPACING['none'], minwidth=SPACING['none'], stretch=False)
        return
    tree.configure(show='tree headings')
    tree.heading('#0', text='')
    thumb_col = preview_width if preview_width is not None else TREE_PREVIEW_DEFAULT_WIDTH
    if not has_thumb:
        width = TREE_DISCLOSURE_WIDTH
    elif show_groups:
        width = thumb_col + SPACING['sm']
    else:
        width = thumb_col
    tree.column('#0', width=width, minwidth=width, stretch=False)


class GroupMenuPopup:
    """分组下拉卡片＋右侧同步二级目录卡（纯 ttk 样式，零原生配色债）。

    主卡列出「类型／阶段／状态／日期」，悬停或打开时右侧联动弹出二级目录卡，
    同步展示当前项目/阶段下有哪些阶段、类型、状态或日期及计数，点击即生效。
    """

    def __init__(self, panel):
        self.panel = panel
        self.open = False
        self.hovered_mode = None
        top = panel.page.win
        self.primary = ttk.Frame(top, style='MenuCard.TFrame', padding=SPACING['xs'])
        self.secondary = ttk.Frame(top, style='MenuCard.TFrame', padding=SPACING['xs'])
        self._primary_labels = {}
        self._secondary_items = ()

    def is_open(self):
        return bool(self.open) and self.primary.winfo_exists()

    def contains_widget(self, widget):
        if widget is None or not self.is_open():
            return False
        targets = (self.primary, self.secondary, getattr(self.panel, 'group_button', None))
        node = widget
        for _ in range(16):
            if node is None:
                break
            if node in targets:
                return True
            node = getattr(node, 'master', None)
        return False

    def toggle(self):
        if self.is_open():
            self.close()
        else:
            self.show()

    def close(self):
        self.open = False
        self.hovered_mode = None
        for card in (self.primary, self.secondary):
            try:
                card.place_forget()
            except tk.TclError:
                pass

    def secondary_items(self, mode):
        """返回指定分组维度在右侧二级目录卡中展示的 ``[(文案, 筛选值, 计数), ...]``。"""
        from infra import file_index
        library = bool(getattr(self.panel, 'library_view', False))
        all_rows = [r for r in (getattr(self.panel, '_all_index_rows', ()) or ())
                    if not file_index.is_functional(r.path)]
        stage = getattr(self.panel, 'stage_filter', None)
        scoped = all_rows if (library or not stage) else [r for r in all_rows if r.stage == stage]
        if mode == '阶段':
            if library:
                return (('全局素材库', None, len(all_rows)),)
            counts = {}
            for row in all_rows:
                counts[row.stage] = counts.get(row.stage, 0) + 1
            items = [('全部阶段', None, len(all_rows))]
            current = self.panel._page_stage() if hasattr(self.panel, '_page_stage') else None
            for st in STAGES:
                cnt = counts.get(st, 0)
                if cnt > 0 or st == current or st == stage:
                    items.append((stage_name(st), st, cnt))
            return tuple(items)
        if mode == '状态':
            counts = {st: 0 for st in STATUSES}
            for row in scoped:
                st = normalize_status(row.status)
                counts[st] = counts.get(st, 0) + 1
            items = [('全部状态', None, len(scoped))]
            for st in (STATUS_FINAL, STATUS_DRAFT, STATUS_ARCHIVED):
                items.append((st, st, counts.get(st, 0)))
            return tuple(items)
        if mode == '日期':
            counts = {}
            for row in scoped:
                day = row_metadata(row)[1]
                counts[day] = counts.get(day, 0) + 1
            days = sorted((d for d in counts if d != '未知'), reverse=True)
            if '未知' in counts:
                days.append('未知')
            items = [('全部日期', None, len(scoped))]
            items.extend((day, day, counts[day]) for day in days)
            return tuple(items)
        counts = {}
        for row in scoped:
            counts[row.kind] = counts.get(row.kind, 0) + 1
        items = [('全部类型', None, len(scoped))]
        for kind in file_naming.KINDS:
            if counts.get(kind, 0) > 0:
                items.append((kind, kind, counts[kind]))
        return tuple(items)

    def _active_value(self, mode):
        if mode == '阶段':
            return getattr(self.panel, 'stage_filter', None)
        if mode == '状态':
            return getattr(self.panel, 'status_filter', None)
        if mode == '日期':
            return getattr(self.panel, 'date_filter', None)
        return getattr(self.panel, 'kind_filter', None)

    def show(self):
        self.open = True
        self._rebuild_primary()
        self._place_primary()
        current_mode = getattr(self.panel, 'group_mode', DEFAULT_GROUP_MODE)
        if current_mode not in GROUP_MODES:
            current_mode = DEFAULT_GROUP_MODE
        self.show_secondary(current_mode)

    def _rebuild_primary(self):
        for child in self.primary.winfo_children():
            child.destroy()
        self._primary_labels = {}
        current = getattr(self.panel, 'group_mode', DEFAULT_GROUP_MODE)
        for mode in GROUP_MODES:
            style = 'MenuItemActive.TLabel' if mode == current else 'MenuItem.TLabel'
            lbl = ttk.Label(self.primary, text='%s  ▸' % mode, style=style, anchor='w', cursor='hand2')
            lbl.pack(fill='x')
            lbl.bind('<Enter>', lambda _e, m=mode: self._on_primary_hover(m))
            lbl.bind('<Button-1>', lambda _e, m=mode: self._pick(m, None))
            self._primary_labels[mode] = lbl

    def _on_primary_hover(self, mode):
        current = getattr(self.panel, 'group_mode', DEFAULT_GROUP_MODE)
        for key, lbl in self._primary_labels.items():
            if key == mode:
                lbl.configure(style='MenuItemHover.TLabel')
            elif key == current:
                lbl.configure(style='MenuItemActive.TLabel')
            else:
                lbl.configure(style='MenuItem.TLabel')
        self.show_secondary(mode)

    def show_secondary(self, mode):
        if not self.is_open():
            return
        self.hovered_mode = mode
        for child in self.secondary.winfo_children():
            child.destroy()
        items = self.secondary_items(mode)
        self._secondary_items = items
        active_val = self._active_value(mode)
        same_mode = getattr(self.panel, 'group_mode', DEFAULT_GROUP_MODE) == mode
        for label_text, value, count in items:
            selected = same_mode and active_val == value
            style = 'MenuItemActive.TLabel' if selected else 'MenuItem.TLabel'
            text = '%s (%d)' % (label_text, count)
            lbl = ttk.Label(self.secondary, text=text, style=style, anchor='w', cursor='hand2')
            lbl.pack(fill='x')
            lbl.bind('<Enter>', lambda _e, w=lbl: w.configure(style='MenuItemHover.TLabel'))
            lbl.bind('<Leave>', lambda _e, w=lbl, s=style: w.configure(style=s))
            lbl.bind('<Button-1>', lambda _e, m=mode, v=value: self._pick(m, v))
        self._place_secondary()

    def _pick(self, mode, value):
        self.close()
        self.panel.select_group_option(mode, value)

    def _place_primary(self):
        try:
            top = self.panel.page.win
            anchor = self.panel.group_button
            self.primary.update_idletasks()
            pw = max(self.primary.winfo_reqwidth(), anchor.winfo_width())
            ph = self.primary.winfo_reqheight()
            win_w = max(top.winfo_width(), pw + SPACING['md'])
            win_h = max(top.winfo_height(), ph + SPACING['md'])
            x = anchor.winfo_rootx() - top.winfo_rootx()
            y = anchor.winfo_rooty() - top.winfo_rooty() + anchor.winfo_height() + SPACING['xs'] // 2
            if y + ph > win_h - SPACING['xs']:
                y = max(SPACING['xs'], anchor.winfo_rooty() - top.winfo_rooty() - ph - SPACING['xs'] // 2)
            x = max(SPACING['xs'], min(x, win_w - pw - SPACING['xs']))
            self.primary.place(x=x, y=y, width=pw)
            self.primary.lift()
        except tk.TclError:
            pass

    def _place_secondary(self):
        try:
            top = self.panel.page.win
            self.primary.update_idletasks()
            self.secondary.update_idletasks()
            sw = self.secondary.winfo_reqwidth()
            sh = self.secondary.winfo_reqheight()
            win_w = max(top.winfo_width(), sw + SPACING['md'])
            win_h = max(top.winfo_height(), sh + SPACING['md'])
            px = self.primary.winfo_rootx() - top.winfo_rootx()
            py = self.primary.winfo_rooty() - top.winfo_rooty()
            pw = self.primary.winfo_width() or self.primary.winfo_reqwidth()
            gap = SPACING['xs'] // 2
            x = px + pw + gap
            if x + sw > win_w - SPACING['xs']:
                x = px - sw - gap
            x = max(SPACING['xs'], min(x, win_w - sw - SPACING['xs']))
            y = max(SPACING['xs'], min(py, win_h - sh - SPACING['xs']))
            self.secondary.place(x=x, y=y, width=sw)
            self.secondary.lift()
        except tk.TclError:
            pass


SCRIPT_AUTO_REFRESH_MS = 1500
SCRIPT_FOCUS_REFRESH_SECONDS = 2.0


def append_kind_menu(panel, menu, row):
    """右键菜单追加「更改类型」子菜单，允许用户自选文件类型或恢复自动识别。"""
    sub = menu.submenu()
    current_row = getattr(panel, '_index_rows', {}).get(row)
    current_kind = current_row.kind if current_row is not None else ''
    for kind in file_naming.KINDS:
        label = ('✓ ' + kind) if kind == current_kind else kind
        sub.command(label, lambda k=kind, r=row: panel.page.safe(lambda: panel.change_file_kind(r, k)))
    sub.separator()
    sub.command('恢复自动识别', lambda r=row: panel.page.safe(lambda: panel.change_file_kind(r, '')))
    menu.cascade('改类型', sub)


def cancel_auto_refresh(panel):
    job = getattr(panel, '_auto_refresh_job', None)
    panel._auto_refresh_job = None
    if job is not None:
        try:
            panel.page.win.after_cancel(job)
        except tk.TclError:
            pass


def schedule_auto_refresh(panel):
    """面板打开期间按需监听索引变更（O(1) 计数比对，无盘扫描），关闭即停。"""
    cancel_auto_refresh(panel)
    if not panel._open:
        return
    win = getattr(panel.page, 'win', None)
    if win is None:
        return

    def poll():
        panel._auto_refresh_job = None
        if not panel._open or getattr(panel, 'library_view', False):
            return
        root = getattr(panel.page, 'root', None)
        if root is not None and not getattr(panel, '_index_loading', False):
            from infra import file_index
            if file_index.change_revision(root) != getattr(panel, '_last_rendered_rev', -1):
                panel._reload_current_view()
        if panel._open:
            try:
                panel._auto_refresh_job = win.after(SCRIPT_AUTO_REFRESH_MS, poll)
            except tk.TclError:
                panel._auto_refresh_job = None

    try:
        panel._auto_refresh_job = win.after(SCRIPT_AUTO_REFRESH_MS, poll)
    except tk.TclError:
        panel._auto_refresh_job = None


def install_auto_refresh(panel):
    """订阅 file_index 变更通知与窗口获焦自动增量刷新，替代手动刷新按钮。"""
    from infra import file_index

    def on_index_changed(changed_root):
        if not panel._open or getattr(panel, 'library_view', False):
            return
        current = getattr(panel.page, 'root', None)
        if current is None:
            return
        try:
            if Path(changed_root).resolve() != Path(current).resolve():
                return
        except OSError:
            return
        if threading.current_thread() is threading.main_thread() and getattr(panel, '_index_change_job', None) is None:
            def fire():
                panel._index_change_job = None
                if panel._open and not getattr(panel, '_index_loading', False):
                    panel._reload_current_view()
            try:
                panel._index_change_job = panel.page.win.after(120, fire)
            except tk.TclError:
                panel._index_change_job = None

    def on_focus_in(_event=None):
        if not panel._open or getattr(panel, 'library_view', False) or getattr(panel, '_index_loading', False):
            return
        now = time.monotonic()
        if now - getattr(panel, '_last_focus_refresh', 0.0) < SCRIPT_FOCUS_REFRESH_SECONDS:
            return
        panel._last_focus_refresh = now
        panel._reload_current_view()

    panel._auto_refresh_listener = file_index.subscribe_changes(on_index_changed)
    panel._focus_refresh_bind = panel.page.win.bind('<FocusIn>', on_focus_in, add='+')
    panel._index_change_job = None
    panel._last_focus_refresh = 0.0


def teardown_auto_refresh(panel):
    from infra import file_index
    cancel_auto_refresh(panel)
    job = getattr(panel, '_index_change_job', None)
    panel._index_change_job = None
    if job is not None:
        try:
            panel.page.win.after_cancel(job)
        except tk.TclError:
            pass
    listener = getattr(panel, '_auto_refresh_listener', None)
    if listener is not None:
        file_index.unsubscribe_changes(listener)
        panel._auto_refresh_listener = None
    bind = getattr(panel, '_focus_refresh_bind', None)
    if bind:
        try:
            panel.page.win.unbind('<FocusIn>', bind)
        except tk.TclError:
            pass
        panel._focus_refresh_bind = None


class FilesPanelIndexMixin:
    """宿主仅维护 UI 状态；文件发现与首次索引重建都通过 Desktop.async_。"""

    def is_file_group(self, item):
        """所有分组共享非文件标记，不以阶段前缀猜测文件身份。"""
        return getattr(self, 'script_row_category', {}).get(item) == '__file_group__'

    def _invalidate_index_load(self):
        self._index_generation = getattr(self, '_index_generation', 0) + 1
        job = getattr(self, '_index_render_job', None)
        if job is not None:
            try:
                self.page.win.after_cancel(job)
            except tk.TclError:
                pass
        self._index_render_job = None
        self._index_loading = False

    def refresh_file_index(self):
        """用户明确刷新时后台重建索引，发现外部新增或修改的文件。"""
        self._index_refresh = True
        self._reload_current_view()

    def _index_context(self, root, library):
        return (str(Path(root).resolve()), library,
                str(getattr(self.page, 'root', '') or ''))

    def _index_current(self, generation, context):
        if generation != getattr(self, '_index_generation', 0) or not self._open:
            return False
        if bool(getattr(self, 'library_view', False)) != context[1]:
            return False
        if str(getattr(self.page, 'root', '') or '') != context[2]:
            return False
        try:
            return bool(self.script_tree.winfo_exists())
        except tk.TclError:
            return False

    def _request_index(self, root, library=False):
        self.cancel_script_load()
        self._clear_index_tree()
        if root is None or not self._open:
            return
        generation = self._index_generation
        self._index_loading = True
        context = self._index_context(root, library)
        filters = (self.stage_filter, self.kind_filter, self.status_filter,
                   getattr(self, 'date_filter', None), self.keyword_filter,
                   getattr(self, 'sort_column', 'kind'), getattr(self, 'sort_desc', False))
        refresh = getattr(self, '_index_refresh', False)
        self._index_refresh = False

        def work():
            if not self._index_current_without_tk(generation, context):
                return None
            rows, categories, labels = load_index(root, library, refresh, stage=filters[0])
            return filtered_rows(rows, filters, library), categories, labels, tuple(rows)

        def done(result):
            if result is None or not self._index_current(generation, context):
                return
            self._index_loading = False
            found, categories, self._index_file_labels, self._all_index_rows = result
            self._start_index_render(found, categories, root, library, generation, context)
            if hasattr(self, '_prefetch_media_thumbs'):
                self._prefetch_media_thumbs(
                    [Path(root) / row.path for row in found if not row.missing][:_MEDIA_PREFETCH_CAP])

        submit = getattr(self.page, 'async_queued', self.page.async_)
        submit(work, done, show_progress=False, label='加载全局素材库' if library else '加载项目文件索引')

    def _index_current_without_tk(self, generation, context):
        return (generation == getattr(self, '_index_generation', 0) and self._open
                and bool(getattr(self, 'library_view', False)) == context[1]
                and str(getattr(self.page, 'root', '') or '') == context[2])

    def _clear_index_tree(self):
        self.script_tree.delete(*self.script_tree.get_children())
        self.script_row_details.clear()
        self.script_row_category.clear()
        stages = getattr(self, 'script_row_stage', None)
        if isinstance(stages, dict):
            stages.clear()
        self._index_rows = {}
        self._index_images = {}
        self._full_labels = {}

    def _start_index_render(self, rows, categories, root, library, generation, context):
        self._clear_index_tree()
        self.script_tree.tag_configure('missing', foreground=COLORS['text_muted'])
        groups = grouped_rows(rows, getattr(self, 'group_mode', DEFAULT_GROUP_MODE), library,
                              sort_col=getattr(self, 'sort_column', 'kind'),
                              sort_desc=getattr(self, 'sort_desc', False))
        self._index_group_count = len(groups)
        show_groups = should_show_groups(groups)
        configure_tree_leading_column(self.script_tree, groups)
        if show_groups:
            for group, label, _members in groups:
                self.script_tree.insert('', 'end', iid=group, open=True, values=(label, '', '', '', '', ''))
                self.script_row_category[group] = '__file_group__'
        pending = (iter((group, row) for group, _label, members in groups for row in members)
                   if show_groups else iter(('', row) for _group, _label, members in groups for row in members))

        def batch():
            self._index_render_job = None
            if not self._index_current(generation, context):
                return
            for _ in range(RENDER_BATCH):
                entry = next(pending, None)
                if entry is None:
                    self._finish_index_render()
                    return
                group, row = entry
                self._insert_index_row(row, categories, root, library, group)
            self._index_render_job = self.page.win.after(1, batch)

        batch()

    def _insert_index_row(self, row, categories, root, library, group):
        item = ('library:' if library else '') + row.path
        name = Path(row.path).name
        from contract.script_contract import RAW_SCRIPT_NAME
        if not library and name == RAW_SCRIPT_NAME:
            name = '[内部工作稿] ' + name
        category = 'index' if library else categories.get(row.path, script_category(row))
        self._index_rows[item] = row
        self.script_row_category[item] = category
        size_text, modified = row_metadata(row)
        modified_full = datetime.fromtimestamp(row.mtime).strftime('%Y-%m-%d %H:%M:%S') if row.mtime else '未知'
        # 时长／分辨率列可整列隐藏（任务书 L4-U3）：内容进悬停提示。
        meta_text = self._row_meta_text(Path(root) / row.path) if hasattr(self, '_row_meta_text') else ''
        status_text = normalize_status(row.status) or STATUS_DRAFT
        metadata = '%s · %s · %s · %s（%d 字节）· %s\n%s' % (
            name, status_text, row.kind, size_text, row.size, modified_full, row.path)
        if meta_text:
            metadata += '\n时长／分辨率：' + meta_text
        self.script_row_details[item] = (row.title + '\n' if row.title else '') + metadata
        label = ('[缺失] ' if row.missing else '') + name
        if category != 'index' and not row.missing:
            path = Path(root) / row.path
            labels = getattr(self, '_index_file_labels', {})
            state = labels.get(str(path.resolve()), labels.get(category, ''))
            # 顺序确认门禁已取消：名称前不再加「待确认／已确认／重写待确认」，状态只看状态列。
            if state in ('待确认', '已确认', '重写待确认'):
                state = ''
            document = SimpleNamespace(item_id=str(path), name=name)
            self.script_row_details[item] = script_row_card(document, state or status_text, modified_full, Path(root)) + '\n' + metadata
        self._full_labels[item] = label
        image = None
        if not row.missing and group_default_open(group):
            if hasattr(self, '_row_preview'):
                image = self._row_preview(Path(root) / row.path)
            elif Path(row.path).suffix.lower() in ('.png', '.gif', '.jpg', '.jpeg', '.webp'):
                import asset_thumbs
                image = asset_thumbs.thumbnail(self.script_tree, Path(root) / row.path, THUMB_SIZE)
        options = {'image': image} if image is not None else {}
        if image is not None:
            self._index_images[item] = image
        self.script_row_stage[item] = stage_name(row.stage) if row.stage in STAGES else ''
        self.script_tree.insert(group, 'end', iid=item,
                                values=(label, status_text, row.kind, modified, size_text, meta_text),
                                tags=('missing',) if row.missing else (), **options)

    def _finish_index_render(self):
        self._fit_script_width()
        files = len(getattr(self, '_index_rows', {}))
        try:
            headers = sum(1 for item in self.script_tree.get_children() if self.is_file_group(item))
        except tk.TclError:
            groups = getattr(self, '_index_group_count', 0)
            headers = groups if groups > 1 else 0
        count = files + headers
        self.script_tree.configure(height=max(1, min(SCRIPT_FILE_MAX_ROWS, count)))
        table = getattr(self, 'script_list', None)
        if table is not None and hasattr(table, 'empty_label'):
            if files:
                hint = ''
            elif getattr(self, 'library_view', False):
                hint = '全局素材库暂无文件'
            elif any((getattr(self, 'kind_filter', None), getattr(self, 'status_filter', None),
                      getattr(self, 'keyword_filter', ''))):
                hint = '没有匹配筛选条件的文件'
            else:
                hint = '当前阶段暂无文件'
            try:
                table.empty_label.configure(text=hint)
                table.refresh_empty_state()
            except tk.TclError:
                pass

    def _apply_name_labels(self, name_px, widths, measure):
        """按文件名列可见宽写回显示文字：放得下写全名，放不下中间省略。"""
        tree = self.script_tree
        full_labels = getattr(self, '_full_labels', {})
        budget = max(0, name_px - SCRIPT_NAME_CELL_PAD)
        for item, full in full_labels.items():
            display = full if widths[full] <= budget else self._elide_label(full, budget, measure)
            if tree.set(item, 'name') != display:
                tree.set(item, 'name', display)

    def _elide_label(self, label, budget, measure):
        """中间省略：保留开头至少 ``SCRIPT_NAME_HEAD`` 个字符与扩展名，中间用「…」。"""
        import re
        font = self._script_list_font()
        match = re.match(r'^(\[[^\]]*\]\s*)+', label)
        prefix = match.group(0) if match else ''
        body = label[len(prefix):]
        stem, dot, ext = body.rpartition('.')
        core, suffix = (stem, dot + ext) if dot else (body, '')
        best = None
        lo, hi = SCRIPT_NAME_HEAD, len(core)
        while lo <= hi:
            mid = (lo + hi) // 2
            candidate = prefix + core[:mid] + '…' + suffix
            if measure(font, [candidate]) <= budget:
                best = candidate
                lo = mid + 1
            else:
                hi = mid - 1
        return best if best is not None else prefix + core[:SCRIPT_NAME_HEAD] + '…' + suffix

    def index_file_path(self, item, require_file=True):
        """拒绝组节点、库节点、绝对路径/越界/符号链接；删除只认当前索引行。"""
        if item not in getattr(self, '_index_rows', {}) or item.startswith('library:'):
            raise ValueError('请先选择当前项目的文件')
        row = self._index_rows[item]
        relative = Path(row.path)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('只能操作当前项目内的文件')
        root = Path(self.page.root).resolve()
        candidate = root / relative
        for part in (candidate, *candidate.parents):
            if part == root:
                break
            if part.is_symlink() or part.is_junction():
                raise ValueError('不能通过链接删除项目文件')
        path = candidate.resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ValueError('只能操作当前项目内的文件') from exc
        if path == root or (require_file and not path.is_file()):
            raise ValueError('所选文件缺失或已移动，请刷新后重试')
        return path

    def rename_index_file(self, item):
        from domain.script_workspace_service import rename_project_file
        from ui_widgets import ask_string
        source = self.index_file_path(item)
        name = ask_string(self.page.win, '重命名文件', '新文件名（保留扩展名）：', initialvalue=source.name)
        if not name:
            return
        result = rename_project_file(self.page.root, source, name)
        if not result.ok:
            raise ValueError(result.reason)
        self._reload_current_view()
        self.page.status.set('已重命名：' + result.data.name)

    def delete_index_files(self):
        tree = self.script_tree
        selected = [item for item in tree.selection() if not self.is_file_group(item)]
        if not selected:
            raise ValueError('请先选择要删除的项目文件')
        paths = [self.index_file_path(item) for item in selected]
        prompt = '确定将选中的 %d 个项目文件移入回收站吗？\n\n%s' % (
            len(paths), '\n'.join(path.name for path in paths))
        if not self.page.writing_page_services.confirm(self.page.win, '移入回收站', prompt, dangerous=True):
            return
        from infra.storage_maintenance import recycle_paths
        recycled = recycle_paths(self.page.root, paths, '删除选中的项目文件')
        from infra import file_index
        succeeded = [record['source'] for record in recycled if isinstance(record, dict) and record.get('source')]
        file_index.update(self.page.root, succeeded, removed=True)
        self._reload_current_view()
        if len(recycled) != len(paths):
            raise OSError('部分文件未能移入回收站，请刷新后重试')
        self.page.status.set('已移入回收站 %d 个项目文件' % len(recycled))

