# R853 结果｜白模生命周期回归夹具与轮次接续

## 修复

- 白模自动派发的两个 UI 回归替身接纳生命周期关键字参数，匹配 R851 的 ticket 化启动接口。
- `project_status.md` 状态轮次按结果报告连续接续。

## 验证

- `tests/test_ui_edges.py` 两条白模自动派发回归：2／0 红。

`[TASK_COMPLETE]`：白模回归恢复覆盖；继续处理异常 AST 候选。
