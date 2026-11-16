"""无 Tk 的首帧管理页行归属、路径和批次选择状态。"""
from __future__ import annotations

from pathlib import Path


class KeyframePageController:
    """让首帧页的 Tk 表格只消费已经归属明确的行状态。"""

    def __init__(self, source, episode, base, rows=()):
        self.source = Path(source).resolve()
        self.episode = episode
        self.base = Path(base).resolve()
        self.rows = []
        self.row_context = {}
        self.owners = {}
        self.replace_rows(rows)

    def replace_rows(self, rows):
        """原地更新行索引，供页面重建后继续复用同一状态容器。"""
        self.rows[:] = list(rows)
        self.row_context.clear()
        self.owners.clear()
        for iid, shot, item, base, episode in self.rows:
            item = Path(item).resolve()
            base = Path(base).resolve()
            self.row_context[iid] = (shot, item, base, episode)
            self.owners[id(shot)] = (item, base, episode)
        return self.rows

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
