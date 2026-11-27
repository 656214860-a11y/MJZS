"""无 Tk 的首帧管理页行归属、分页、筛选、跨页选中、路径和批次选择状态。"""
from __future__ import annotations

from pathlib import Path

DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 100
_EMPTY_ROWS = '本页无镜头'
_EMPTY_FILTER = '筛选无结果'


def shot_scene(shot):
    """场次优先认 location，兼容 scene_id / scene。"""
    for key in ('location', 'scene_id', 'scene'):
        value = str(shot.get(key) or '').strip()
        if value:
            return value
    return ''


def shot_characters(shot):
    """角色列表；单数字符串 character 也认。"""
    raw = shot.get('characters')
    if raw is None:
        raw = shot.get('character')
    if raw is None or raw == '':
        return ()
    if isinstance(raw, str):
        text = raw.strip()
        return (text,) if text else ()
    return tuple(str(item).strip() for item in raw if str(item).strip())


def _duration_bound(value):
    if value is None or value == '':
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _duration_in_range(shot, low, high):
    try:
        duration = int(shot.get('duration'))
    except (TypeError, ValueError):
        return False
    if low is not None and duration < low:
        return False
    if high is not None and duration > high:
        return False
    return True


def frame_status(controller, shot):
    """与表格列一致：已导入 / 待重新生成 / 待生成 / 待导入。路径越界视为未导入。"""
    deleted = bool(shot.get('frame_deleted'))
    present = False
    if not deleted:
        try:
            present = controller.frame_exists(shot)
        except (ValueError, OSError, KeyError):
            present = False
    if present:
        return '已导入'
    if deleted:
        return '待重新生成'
    return '待生成 / 待导入'


class KeyframePageController:
    """让首帧页的 Tk 表格只消费已经归属明确且分页后的行状态。"""

    def __init__(self, source, episode, base, rows=(), *, page_size=DEFAULT_PAGE_SIZE):
        self.source = Path(source).resolve()
        self.episode = episode
        self.base = Path(base).resolve()
        self.page_size = max(1, min(MAX_PAGE_SIZE, int(page_size)))
        self.page_index = 0
        self.rows = []
        self.visible = []
        self.row_context = {}
        self.owners = {}
        self.selected_shot_ids = set()
        self.scene_filter = ''
        self.character_filter = ''
        self.status_filter = ''
        self.duration_min = None
        self.duration_max = None
        self.replace_rows(rows)

    def _filter_key(self):
        return (
            self.scene_filter, self.character_filter, self.status_filter,
            self.duration_min, self.duration_max,
        )

    def _row_matches(self, shot):
        if self.scene_filter and shot_scene(shot) != self.scene_filter:
            return False
        if self.character_filter and self.character_filter not in shot_characters(shot):
            return False
        if (self.duration_min is not None or self.duration_max is not None) and not _duration_in_range(
                shot, self.duration_min, self.duration_max):
            return False
        if self.status_filter and frame_status(self, shot) != self.status_filter:
            return False
        return True

    def _refresh_visible(self):
        self.visible = [row for row in self.rows if self._row_matches(row[1])]

    def replace_rows(self, rows):
        """原地更新行索引并按当前行集裁掉失效的跨页选中与页码。"""
        self.rows[:] = list(rows)
        self.row_context.clear()
        self.owners.clear()
        for iid, shot, item, base, episode in self.rows:
            item = Path(item).resolve()
            base = Path(base).resolve()
            self.row_context[iid] = (shot, item, base, episode)
            self.owners[id(shot)] = (item, base, episode)
        self._refresh_visible()
        self.selected_shot_ids &= set(self.row_context)
        self.page_index = max(0, min(self.page_index, self.total_pages - 1))
        return self.rows

    def set_filters(self, scene='', character='', status='', duration_min=None, duration_max=None):
        """按场次、角色、首帧状态与时长闭区间筛选。无参数时清空。筛选变化才回到第 1 页。"""
        previous = self._filter_key()
        self.scene_filter = str(scene or '').strip()
        self.character_filter = str(character or '').strip()
        self.status_filter = str(status or '').strip()
        self.duration_min = _duration_bound(duration_min)
        self.duration_max = _duration_bound(duration_max)
        self._refresh_visible()
        if self._filter_key() != previous:
            self.page_index = 0
        self.page_index = max(0, min(self.page_index, self.total_pages - 1))
        return self.visible

    def filtered_rows(self):
        return list(self.visible)

    @property
    def total_rows(self):
        return len(self.visible)

    @property
    def total_pages(self):
        return max(1, (len(self.visible) + self.page_size - 1) // self.page_size)

    @property
    def current_page(self):
        return self.page_index + 1

    def page_rows(self):
        start = self.page_index * self.page_size
        return self.visible[start:start + self.page_size]

    def page_ids(self):
        return [iid for iid, _shot, _item, _base, _episode in self.page_rows()]

    def set_page(self, page_number):
        target = max(1, min(self.total_pages, int(page_number)))
        self.page_index = target - 1
        return self.current_page

    def first_page(self):
        return self.set_page(1)

    def prev_page(self):
        return self.set_page(self.current_page - 1)

    def next_page(self):
        return self.set_page(self.current_page + 1)

    def last_page(self):
        return self.set_page(self.total_pages)

    def sync_page_selection(self, visible_selected):
        """按当前页可见选中回写跨页 shot_id 集合，其它页的选中保持不变。"""
        current_ids = set(self.page_ids())
        visible = {str(iid) for iid in (visible_selected or ()) if str(iid) in self.row_context}
        self.selected_shot_ids -= (current_ids - visible)
        self.selected_shot_ids |= visible
        return self.selected_on_page()

    def selected_on_page(self):
        return [iid for iid in self.page_ids() if iid in self.selected_shot_ids]

    def select_current_page(self):
        """Ctrl+A 语义：只选当前页，不跨页全选。"""
        ids = self.page_ids()
        self.selected_shot_ids = set(ids)
        return ids

    def locate_shot(self, target):
        key = str(target or '').strip()
        if not key:
            return None
        for index, (iid, shot, _item, _base, _episode) in enumerate(self.visible):
            if iid == key or str(shot.get('id') or '') == key:
                return (index // self.page_size) + 1, iid
        return None

    def jump_to_shot(self, target):
        located = self.locate_shot(target)
        if located is None:
            return None
        page_number, iid = located
        self.set_page(page_number)
        return iid

    def empty_message(self):
        if not self.rows:
            return _EMPTY_ROWS
        if not self.visible:
            return _EMPTY_FILTER
        return ''

    def page_summary(self):
        message = self.empty_message()
        if message:
            return message
        summary = f'第 {self.current_page} / {self.total_pages} 页（共 {self.total_rows} 镜）'
        if self.selected_shot_ids:
            summary += f' · 已选 {len(self.selected_shot_ids)} 镜'
        return summary

    @property
    def owned_sources(self):
        return sorted({str(item.resolve()) for _iid, _shot, item, _base, _episode in self.rows})

    @property
    def checks_key(self):
        owned = self.owned_sources
        return '|'.join(owned) if len(owned) > 1 else owned[0]

    @property
    def merged(self):
        return len(self.owned_sources) > 1

    def home(self, shot):
        return self.owners.get(id(shot), (self.source, self.base, self.episode))

    def iid_of(self, shot):
        for iid, row in self.row_context.items():
            if row[0] is shot:
                return iid
        return str(shot['id'])

    def frame_path(self, shot, required=True):
        _item, base, _episode = self.home(shot)
        path = (base / shot['frame']).resolve()
        if not path.is_relative_to(base) or (required and not path.is_file()):
            raise ValueError('此镜头首帧不存在，请先导入')
        return path

    def frame_exists(self, shot):
        return self.frame_path(shot, required=False).is_file()

    def pick_batch(self, ids, selected=()):
        """按所属分镜分组，优先提交当前高亮行所在的一份。"""
        if not ids:
            return self.source, None, 0
        groups = {}
        for iid in ids:
            row = self.row_context.get(iid)
            if row:
                groups.setdefault(str(row[1].resolve()), []).append(str(row[0]['id']))
        if not groups:
            return self.source, None, 0
        selected = tuple(selected)
        preferred = selected[0] if selected else ''
        aim = str(self.row_context[preferred][1].resolve()) if preferred in self.row_context else ''
        if aim not in groups:
            aim = sorted(groups)[0]
        remaining = sum(len(value) for key, value in groups.items() if key != aim)
        return Path(aim), groups[aim], remaining
