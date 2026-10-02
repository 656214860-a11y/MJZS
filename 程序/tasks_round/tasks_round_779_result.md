# R779｜UI 统一入口第二批第 6 项：通知首迁｜功能轮

## 结论

验收通过。新增 `ui_widgets.NotificationDispatcher`，将通知的状态栏优先、级别与可选模态行为收敛到唯一组件；`Desktop.safe()` 成为本轮唯一迁移入口，仍先写既有诊断记录，再以既有“状态栏＋操作提示”呈现错误。

未批量迁移历史 `status.set`／`messagebox`，避免本轮改变页面业务语义；它们留待后续独立迁移轮。

## 改动

- `ui_widgets.py`：新增通知分发器，支持 `error`、`warning`、`success`、`info`；空文案不投递，未知级别显式拒绝。
- `desktop.py`：注入分发器，`safe()` 保持诊断采集优先并改由分发器显示失败。
- `ui_components.md`、`design_tokens.md`：登记组件职责与严重级别 token 复用规则。
- `tests/test_ui_notifications.py`、`tests/architecture/test_notification_boundary.py`：覆盖错误可见、非模态级别、非法输入和全局错误入口不得退回直连 `messagebox`。
- `tests/test_cloud_video.py`：把 1ms 的自动掩码观察窗调为确定性的 100ms；断言内容未弱化，仍覆盖显式显示与自动重新掩码。

## 验证

| 项目 | 结果 |
| --- | --- |
| 默认冒烟 | 8/8 |
| 受影响冒烟（desktop、ui_widgets） | 9/9（底层 27/0） |
| 通知／桌面定向安全自检 | 31/0 |
| cloud video 隔离回归 | 15/0 |
| 性能基线隔离复核 | 9/0 |
| 架构门禁 | 146/146，36.195 秒（台账／结果更新后二次复核） |
| 完整安全全量 | 3,540 条／0 红／885.2 秒 |

全量首跑暴露 `cloud_video` 测试的 1ms 事件循环竞态，调整为确定性观察窗后由隔离回归与最终全量共同验证。长列表性能门禁曾出现两次 150ms 阈值边缘样本，静置后同一隔离门禁 9/0；本轮没有修改性能阈值或产品逻辑，后续性能轮应以趋势台账继续跟踪。

本轮涉及 Tk 通知和模态事件边界，按 AGENTS.md §5 已执行完整安全全量；基线的 `last_full_safe_all_round` 推进至 R779。

## Git

已提交：否。commit hash：无。

建议提交信息：`feat(ui): add shared notification dispatcher`
