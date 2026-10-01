"""无 Tk 的资产管理页筛选、勾选状态和批量目标编排。"""
from __future__ import annotations


_PREFIXES = {'scenes': 'LOC_', 'characters': 'CHAR_', 'props': 'PROP_'}


class AssetPageController:
    """保存资产页当前类别的行集合与勾选目标；页面只负责控件呈现。"""

    def __init__(self, registry, checks, kind):
        self.registry = registry
        self.checks = checks
        self.kind = kind
        self.prefix = _PREFIXES.get(kind)

    def matches(self, asset_id):
        return self.prefix is None or str(asset_id).startswith(self.prefix)

    def rows(self):
        return [(asset_id, asset) for asset_id, asset in self.registry.items()
                if self.matches(asset_id)]

    def initialize_checks(self):
        for asset_id, asset in self.rows():
            self.checks.setdefault(asset_id, asset.get('status') != '已导入')

    def checked_ids(self, shown_ids=None):
        asset_ids = shown_ids if shown_ids is not None else (asset_id for asset_id, _ in self.rows())
        return [asset_id for asset_id in asset_ids
                if self.matches(asset_id) and self.checks.get(asset_id, False)]

    def has_pending(self):
        return any(asset.get('status') != '已导入' for _asset_id, asset in self.rows())

    def imported_ids(self, asset_ids):
        return [asset_id for asset_id in asset_ids
                if (self.registry.get(asset_id) or {}).get('status') == '已导入']

    def work_ids(self, shown_ids, selected_id):
        checked = self.checked_ids(shown_ids)
        if checked:
            return checked, 'checked'
        if selected_id and selected_id in shown_ids and self.matches(selected_id):
            return [selected_id], 'shown'
        return [], ''
