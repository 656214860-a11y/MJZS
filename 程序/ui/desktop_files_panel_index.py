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
RENDER_BATCH = SPACING['sm'] * 4
THUMB_SIZE = SPACING['lg']
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


def load_index(root, library=False, refresh=False):
    """只在 Desktop 后台任务执行；首次重建也在此线程。"""
    from infra import file_index
    if refresh:
        if library:
            file_index.rebuild_global(root)
        else:
            file_index.rebuild(root)
    rows = file_index.global_rows(root) if library else file_index.rows(root)
    categories = {}
    if not library:
        from domain.script_workspace_service import iter_script_documents
        known = {row.path for row in rows}
        for document in iter_script_documents(root):
            relative = document.path.resolve().relative_to(Path(root).resolve()).as_posix()
            categories[relative] = document.category
            if relative not in known:
                rows.append(FileRow(path=relative, stage='script', kind='剧本',
                                    mtime=document.modified_at))
                known.add(relative)
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
    selected = [row for row in rows
                if (library or not stage or row.stage == stage)
                and (not kind or row.kind == kind)
                and (library or not status or row.status == status)
                and (not keyword or keyword in row.path.casefold())]
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
            rows, categories, labels = load_index(root, library, refresh)
            return filtered_rows(rows, filters, library), categories, labels

        def done(result):
            if result is None or not self._index_current(generation, context):
                return
            self._index_loading = False
            found, categories, self._index_file_labels = result
            self._start_index_render(found, categories, root, library, generation, context)
            if hasattr(self, '_prefetch_media_thumbs'):
                self._prefetch_media_thumbs([Path(root) / row.path for row in found if not row.missing])

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
        self._index_rows = {}
        self._index_images = {}

    def _start_index_render(self, rows, categories, root, library, generation, context):
        self._clear_index_tree()
        self.script_tree.configure(show='tree headings')
        self.script_tree.heading('#0', text='')
        self.script_tree.column('#0', width=THUMB_SIZE + SPACING['xl'] * 2, stretch=False)
        self.script_tree.tag_configure('missing', foreground=COLORS['text_muted'])
        groups = grouped_rows(rows, getattr(self, 'group_mode', '阶段'), library)
        for group, label, _members in groups:
            self.script_tree.insert('', 'end', iid=group, open=True, values=(label, '', '', ''))
            self.script_row_category[group] = '__file_group__'
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
        metadata = '%s · %s · %s（%d 字节）· %s\n%s' % (
            name, row.kind, size_text, row.size, modified, row.path)
        self.script_row_details[item] = (row.title + '\n' if row.title else '') + metadata
        label = ('[缺失] ' if row.missing else '') + name
        if category != 'index' and not row.missing:
            path = Path(root) / row.path
            labels = getattr(self, '_index_file_labels', {})
            state = labels.get(str(path.resolve()), labels.get(category, ''))
            if state:
                label = '[' + state + '] ' + name
            document = SimpleNamespace(item_id=str(path), name=name)
            self.script_row_details[item] = script_row_card(document, state, modified, Path(root)) + '\n' + metadata
        image = None
        if not row.missing:
            if hasattr(self, '_row_preview'):
                image = self._row_preview(Path(root) / row.path)
            elif Path(row.path).suffix.lower() in ('.png', '.gif', '.jpg', '.jpeg', '.webp'):
                import asset_thumbs
                image = asset_thumbs.thumbnail(self.script_tree, Path(root) / row.path, THUMB_SIZE)
        options = {'image': image} if image is not None else {}
        if image is not None:
            self._index_images[item] = image
        metadata = self._row_meta_text(Path(root) / row.path) if hasattr(self, '_row_meta_text') else ''
        self.script_row_stage[item] = stage_name(row.stage) if row.stage in STAGES else ''
        self.script_tree.insert(group, 'end', iid=item, values=(label, row.kind, size_text, modified, metadata),
                                tags=('missing',) if row.missing else (), **options)

    def _finish_index_render(self):
        self._fit_script_width()
        count = len(getattr(self, '_index_rows', {})) + len(self.script_tree.get_children())
        self.script_tree.configure(height=max(1, min(SCRIPT_FILE_MAX_ROWS, count)))

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
        selected = [item for item in tree.selection() if not item.startswith(GROUP_PREFIX)]
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

