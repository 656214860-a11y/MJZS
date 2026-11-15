# -*- coding: utf-8 -*-
"""首帧管理的镜头勾选状态：批量、指定、选中三个入口共用同一份，并与首帧状态双向同步。

- 页面内容框点击某行、按空格、表头全选框、右键菜单 → 勾选／取消（记成用户手动选择）；
- 「选中镜头」下拉框 → 只移动选中行，不动批量勾选（浏览某一镜不该把已勾好的批次清空）；
- 刷新列表 → 按最新首帧状态对齐：首帧刚就位的镜头自动取消勾选，缺首帧的新镜头默认勾选，
  用户手动改过的待生成镜头一律保持不动，于是无人值守轮询刷新不会悄悄改掉用户的选择；
- 「首帧制作」弹窗提交时 → 把最终那一批回写进来（keep），页面与弹窗始终同一份状态。

接口故意做成和 dict 一样（get／__setitem__／setdefault），页面上的旧写法不用改。
"""


class FrameChecks:
    """一份按镜头编号存的勾选表；manual 记住用户亲手改过哪些镜头。"""

    def __init__(self, values=None):
        self.values = {str(key): bool(value) for key, value in dict(values or {}).items()}
        self.manual = set()

    # ── 与 dict 兼容：页面上的 get／[]／setdefault 写法原样可用 ──────────────
    def get(self, sid, default=None):
        return self.values.get(str(sid), default)

    def __getitem__(self, sid):
        return self.values[str(sid)]

    def __setitem__(self, sid, value):
        self.set(sid, value)

    def __contains__(self, sid):
        return str(sid) in self.values

    def __len__(self):
        return len(self.values)

    def setdefault(self, sid, value=False):
        """对齐用的兼容入口：只在缺记录时填默认值，不记成手动选择。"""
        sid = str(sid)
        if sid not in self.values:
            self.values[sid] = bool(value)
        return self.values[sid]

    # ── 勾选 ───────────────────────────────────────────────────────────────
    def set(self, sid, value, manual=True):
        sid = str(sid)
        value = bool(value)
        if manual:
            self.manual.add(sid)
        if self.values.get(sid) != value:
            self.values[sid] = value
        return value

    def toggle(self, sid):
        """单击整行／空格：勾选这一行，再点一次取消。"""
        return self.set(sid, not bool(self.values.get(str(sid), False)))

    def checked(self, sids):
        """按给定顺序取已勾选的编号，页面和弹窗都从这里拿清单。"""
        return [sid for sid in sids if self.values.get(str(sid), False)]

    def keep(self, sids):
        """把勾选收敛为这批编号（首帧制作弹窗提交的那一批），其余取消。"""
        keep = {str(sid) for sid in sids}
        for sid in list(self.values):
            if self.values[sid] and sid not in keep:
                self.values[sid] = False
                self.manual.add(sid)
        for sid in keep:
            self.values[sid] = True
            self.manual.add(sid)
        return [sid for sid in sids if self.values.get(str(sid), False)]

    def sync(self, rows):
        """按最新首帧状态对齐一次，返回 (新勾上的, 新取消的)。

        rows 是 (镜头编号, 已有首帧, 已删除) 三元组。已导入或已删除的镜头一律取消勾选，并清掉
        手动标记——将来它重新缺首帧时又能按默认规则自动勾上；待生成且没被手动碰过的默认勾选。
        """
        checked_now, unchecked_now = [], []
        for sid, present, deleted in rows:
            sid = str(sid)
            if present or deleted:
                self.manual.discard(sid)
                value = False
            elif sid in self.manual:
                continue
            else:
                value = True
            previous = self.values.get(sid)
            if previous == value:
                continue
            self.values[sid] = value
            if value:
                checked_now.append(sid)
            elif previous:
                unchecked_now.append(sid)     # 只报「本来勾着、被首帧状态取消」的镜头，首次建表不算
        return checked_now, unchecked_now
