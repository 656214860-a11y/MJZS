"""页面快捷键的统一登记入口。"""
from __future__ import annotations


class ShortcutRegistry:
    """登记页面快捷键，并拒绝同一作用域中的重复绑定。"""

    def __init__(self):
        self._occupied = {}
        self._records = []

    def bind(self, widget, sequences, handler, *, scope, name, add='+'):
        """为一个语义动作登记一个或多个 Tk 快捷键序列。"""
        sequences = tuple(sequences)
        normalized = tuple(dict.fromkeys(sequence.lower() for sequence in sequences))
        for record in self._records:
            if (record['widget'] is widget and record['scope'] == scope and
                    record['name'] == name and record['sequences'] == sequences):
                # 页面可因切换或重建再次走到同一绑定点；同一控件、同一动作必须幂等。
                return record['tokens']
        replaced = [record for record in self._records
                    if record['scope'] == scope and record['name'] == name]
        for record in replaced:
            # 页面重建会产生新的控件；同一语义的旧控件不再占用此快捷键。
            for sequence in dict.fromkeys(item.lower() for item in record['sequences']):
                if self._occupied.get((scope, sequence)) == name:
                    del self._occupied[(scope, sequence)]
            self._records.remove(record)
        conflicts = [sequence for sequence in normalized if (scope, sequence) in self._occupied]
        if conflicts:
            raise ValueError('快捷键冲突：%s 已在%s登记' % (conflicts[0], scope))
        tokens = tuple(widget.bind(sequence, handler, add=add) for sequence in sequences)
        for sequence in normalized:
            self._occupied[(scope, sequence)] = name
        self._records.append({'widget': widget, 'scope': scope, 'name': name,
                              'sequences': sequences, 'tokens': tokens})
        return tokens

    def registered(self):
        """返回只读的登记快照，供帮助页和架构测试审计。"""
        return tuple({key: value for key, value in record.items() if key != 'widget'}
                     for record in self._records)
