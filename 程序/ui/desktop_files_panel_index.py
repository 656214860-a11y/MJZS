# -*- coding: utf-8 -*-
"""项目文件索引视图：后台加载、阶段分组和有界 Tk 渲染。"""
from pathlib import Path
from datetime import datetime
from types import SimpleNamespace
import tkinter as tk

from contract.file_index_contract import FileRow
from contract.pet_bus import STAGES, stage_name
from ui_tokens import COLORS, SCRIPT_FILE_MAX_ROWS, SPACING
from ui.desktop_file_card import script_row_card

GROUP_PREFIX = 'stage-group:'
ANIMATIC_GROUP_PREFIX = GROUP_PREFIX + 'animatic:'
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
                        existing, stage='animatic', kind='资产',
                        size=size or existing.size, mtime=mtime or existing.mtime,
                        missing=False)
            else:
                positions[relative] = len(rows)
                rows.append(FileRow(
                    path=relative, stage='animatic', kind='资产',
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
                rows.append(FileRow(path=relative, stage='script', kind='剧本',
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


def filtered_rows(rows, filters, library=False):
    """全局库没有项目阶段/发布状态；项目筛选与索引 search 同一语义。"""
    stage, kind, status, keyword, sort = filters
    keyword = keyword.casefold()
    from infra import file_index
    selected = [row for row in rows
                if (library or not stage or row.stage == stage)
                and (not kind or row.kind == kind)
                and (library or not status or row.status == status)
                and (not keyword or keyword in row.path.casefold())
                and not file_index.is_functional(row.path)]
    if sort == '修改时间':
        selected.sort(key=lambda row: (-row.mtime, row.kind, row.path))
    else:
        selected.sort(key=lambda row: (row.kind, row.order, row.path))
    return selected


def row_metadata(row):
    """只格式化已缓存的索引字段，不为列表读取/解析媒体。"""
    size = max(0, row.size)
    amount = float(size)
    unit = 'B'
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if amount < 1024 or unit == 'TB':
            break
        amount /= 1024
    size_text = ('%d B' % size) if unit == 'B' else ('%.1f %s' % (amount, unit))
    modified = datetime.fromtimestamp(row.mtime).strftime('%Y-%m-%d %H:%M:%S') if row.mtime else '未知'
    return size_text, modified


def grouped_rows(rows, mode='阶段', library=False):
    """阶段按流程顺序，类型与日期在整个结果集归组。"""
    groups = {}
    for row in rows:
        if mode == '类型':
            key = row.kind or '其他'
        elif mode == '日期':
            key = row_metadata(row)[1].split(' ')[0]
        else:
            key = 'library' if library else (row.stage if row.stage in STAGES else '')
        groups.setdefault(key, []).append(row)
    if mode == '类型':
        return [('kind-group:' + key, key, groups[key]) for key in sorted(groups)]
    if mode == '日期':
        keys = sorted((key for key in groups if key != '未知'), reverse=True)
        keys += ['未知'] if '未知' in groups else []
        return [('date-group:' + key, key, groups[key]) for key in keys]
    keys = ['library'] if library else [*STAGES, '']
    return [(GROUP_PREFIX + key, '全局素材库' if library else (stage_name(key) if key else '其他文件'),
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
    """多分组或 S04 语义分组始终展示分组标题行；单分组平铺保持原样。"""
    return len(groups) > 1 or any(
        group_id.startswith(ANIMATIC_GROUP_PREFIX) for group_id, _label, _members in groups)


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
    """按是否存在缩略图与多分组收紧 #0 树列，使目录名与文件名紧贴左侧边界。"""
    from infra import file_index
    has_thumb = any(
        not row.missing and (row.kind in ('资产', '音频', '视频')
                             or Path(row.path).suffix.lower() in file_index.IMAGE_SUFFIXES)
        for _group, _label, members in groups for row in members)
    show_groups = should_show_groups(groups)
    if len(groups) == 1 and not show_groups and not has_thumb:
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
                   self.keyword_filter, getattr(self, 'sort_mode', '类型'))
        refresh = getattr(self, '_index_refresh', False)
        self._index_refresh = False

        def work():
            if not self._index_current_without_tk(generation, context):
                return None
            rows, categories, labels = load_index(root, library, refresh, stage=filters[0])
            return filtered_rows(rows, filters, library), categories, labels

        def done(result):
            if result is None or not self._index_current(generation, context):
                return
            self._index_loading = False
            found, categories, self._index_file_labels = result
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
        groups = grouped_rows(rows, getattr(self, 'group_mode', '阶段'), library)
        self._index_group_count = len(groups)
        configure_tree_leading_column(self.script_tree, groups)
        if len(groups) > 1:
            for group, label, _members in groups:
                self.script_tree.insert('', 'end', iid=group, open=True, values=(label, '', '', '', ''))
                self.script_row_category[group] = '__file_group__'
        if len(groups) == 1:
            pending = iter(('', row) for _group, _label, members in groups for row in members)
        else:
            pending = iter((group, row) for group, _label, members in groups for row in members)

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
        # 时长／分辨率列可整列隐藏（任务书 L4-U3）：内容进悬停提示。
        meta_text = self._row_meta_text(Path(root) / row.path) if hasattr(self, '_row_meta_text') else ''
        metadata = '%s · %s · %s（%d 字节）· %s\n%s' % (
            name, row.kind, size_text, row.size, modified, row.path)
        if meta_text:
            metadata += '\n时长／分辨率：' + meta_text
        self.script_row_details[item] = (row.title + '\n' if row.title else '') + metadata
        label = ('[缺失] ' if row.missing else '') + name
        if category != 'index' and not row.missing:
            path = Path(root) / row.path
            labels = getattr(self, '_index_file_labels', {})
            state = labels.get(str(path.resolve()), labels.get(category, ''))
            # LOST-04：文档名前不再出现「已确认」前缀；已确认稿与普通文件同名展示，
            # 未确认草稿仍标「待确认／重写待确认」，悬停卡片保留完整状态说明。
            if state and state != '已确认':
                label = '[' + state + '] ' + name
            document = SimpleNamespace(item_id=str(path), name=name)
            self.script_row_details[item] = script_row_card(document, state, modified, Path(root)) + '\n' + metadata
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
        self.script_tree.insert(group, 'end', iid=item, values=(label, row.kind, size_text, modified, meta_text),
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

