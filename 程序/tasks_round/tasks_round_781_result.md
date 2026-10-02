# R781｜UI 统一入口第二批第 8 项：右键菜单首迁｜功能轮

## 结论

验收通过。新增 `ui_widgets.ContextMenu`，并仅将 `Desktop.open_bubble_menu()` 的聊天气泡右键菜单首迁。组件统一构建菜单项、按事件坐标弹出和结束后释放 grab；复制、删除、恢复和右键事件返回 `break` 的既有语义保持不变。

新增架构门禁锁定该首迁页必须使用 `ContextMenu`、不得退回裸 `tk.Menu`。其他历史右键菜单没有批量迁移，仍按独立轮次处理。

## 验证

| 项目 | 结果 |
| --- | --- |
| 组件直接回归 | 5/0 |
| 默认冒烟 | 8/8 |
| 受影响冒烟（desktop、ui_widgets） | 9/9 |
| 定向安全自检（ui_notifications、idea_chat） | 82/0，40.5 秒 |
| 架构门禁 | 147/147，36.026 秒 |

架构基线由 146/146 同步至 147/147。R781−R779=2，未触发完整安全全量；本轮未改动 Tk 事件绑定或控件生命周期。

## Git

已提交：否。commit hash：无。

建议提交信息：`feat(ui): unify chat bubble context menu`
