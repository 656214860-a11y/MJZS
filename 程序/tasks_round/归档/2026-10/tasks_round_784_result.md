# R784 结果｜UI 统一入口第二批第 11 项：Tooltip

本轮建立 `ui_widgets.Tooltip`，统一 400ms 延迟、鼠标悬停和键盘焦点触发，以及离开、失焦、控件销毁后的取消与清理。浮层不取得焦点或 grab。仅将 `skill_panel.Panel.add_skill_control()` 中截断 SKILL 名称的手写 `Toplevel` 全文提示首迁；名称全文、截断阈值和列表布局语义保持不变，其他悬停效果未迁移。

验证：默认冒烟 8/8；受影响冒烟 9/9；Tooltip 单元及首迁边界 5 条／0 红；架构清单一致性 10 条／0 红；架构门禁 150/150；完整安全全量 3,556 条／0 红。因本轮触及 `ui_widgets.py` 与 `skill_panel.py` 的 Tk 事件绑定，按 AGENTS.md §5 例外条款当轮执行完整安全全量，并将基线推进至 R784。

本轮已提交：否；commit hash：无。
