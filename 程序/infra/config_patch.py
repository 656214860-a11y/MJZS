"""配置编辑的纯内存快照：区分未改字段与显式清空，不负责锁和落盘。"""
from copy import deepcopy


class ConfigSnapshot(dict):
    """兼容 dict 的编辑快照；基准和赋值记录只在内存中保存。"""
    def __init__(self, data):
        super().__init__(data)
        self._original = deepcopy(dict(data))
        self._assigned = set()

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._assigned.add(key)

    def update(self, *args, **kwargs):
        for key, value in dict(*args, **kwargs).items():
            self[key] = value

    def copy(self):
        copied = ConfigSnapshot(self)
        copied._original = deepcopy(self._original)
        copied._assigned = set(self._assigned)
        return copied

    def apply_to(self, current):
        """向最新配置应用顶层改动；嵌套字段仍整体替换，删除不复活。"""
        result = dict(current)
        for key in self._original.keys() - self.keys():
            result.pop(key, None)
        for key in self:
            if key in self._assigned or key not in self._original or self[key] != self._original[key]:
                result[key] = self[key]
        return result
