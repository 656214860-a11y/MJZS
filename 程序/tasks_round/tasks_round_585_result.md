# R585 修复轮结果：UI 回归契约迁移

## 结果

完成 UI token 化后的 4 条过期测试契约迁移；另精确定位 1 条同页滚动恢复的真实 P0 阻塞，未提交未经验证的生产修复。

## 改动

- `tests/test_ui_edges.py`：分镜卡片断言从废弃 `Box.TFrame` 迁移为 `Tokens.Card.TFrame`；定稿选中镜头从旧 `Selected.Compact.TButton` 迁移为 `Tokens.Primary.TButton`。
- 剧本准备页发送按钮间距断言由“≤2px 贴紧”改为 `SPACING['xs']`（4px），与已确认的防误触需求一致。
- 滚动回归用例隔离桌面启动计时器，避免异步首帧干扰。

## 验证

- 上述卡片／导航／间距精确回归 4/4 通过。
- R584 根因派生回归：自动定稿、等待首帧、下游首帧、可见重试、无人值守链和端到端链均精确通过。
- `python smoke_test.py`：8/8 通过。

## P0 阻塞

`test_same_page_rebuild_keeps_scroll_offset` 仍失败：`desktop.py:3249` 先异步 `fit_content()`，随后 `restore_scroll()` 使用旧或中间 `scrollregion`；重建后画布从约 381px 回到 0。尝试以 `after_idle` 延迟恢复仍未稳定通过，已撤回该生产改动，避免引入未验证行为。需下一轮为稳定后的布局建立显式完成钩子，再修复。
