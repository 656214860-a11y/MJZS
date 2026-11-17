"""无 Tk 的剧本准备页文档列表加载状态。"""

from __future__ import annotations


class ScriptListLoadController:
    """管理一次列表刷新中的代次、批次与最终排序，不接触页面控件。"""

    def __init__(self, categories):
        self._categories = tuple(categories)
        self._generation = 0
        self._iterator = iter(())
        self._rows_by_category = {}

    def start(self, rows):
        self._generation += 1
        self._iterator = iter(rows)
        self._rows_by_category = {category: [] for category in self._categories}
        return self._generation

    def invalidate(self):
        self._generation += 1
        return self._generation

    def is_current(self, generation):
        return generation == self._generation

    def take_batch(self, limit):
        batch = []
        while len(batch) < limit:
            try:
                row = next(self._iterator)
            except StopIteration:
                return batch, True
            self._rows_by_category[row.category].append(row)
            batch.append(row)
        return batch, False

    def ordered_rows(self):
        return {
            category: sorted(rows, key=lambda row: row.modified_at, reverse=True)
            for category, rows in self._rows_by_category.items()
        }

    def item_ids(self):
        return {
            row.item_id
            for rows in self._rows_by_category.values()
            for row in rows
        }
