# R878 B1 DataTable stash 判决

- 队列所称 `stash@{0}` 已随新 stash 入栈漂移；按消息内容定位到 `stash@{3}`（`fc240a3`，B1 DataTable 半成品）。
- 该草稿仅涉及 `desktop.py` 和 DataTable 边界断言；主干已有 R821–R829 逐页迁移及 R916 全局门禁，覆盖并强化其目标。
- 当前 `tests.architecture.test_data_table_boundary`：16 条／0 红。
- 因草稿已被后续主干实现替代，丢弃精确的 B1 stash；不处理其他 stash。
