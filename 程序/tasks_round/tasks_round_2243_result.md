# R2243 首绘后回填的稳定判定迁入 idea_chat_controller（J18 结构治理轮·执行）

## 来源
`tasks_round/tasks_round_2178_result.md` 候选 03 的 J18：「`desktop_idea_deferred` 的稳定判定迁入 `idea_chat_controller`，时钟注入，Tk 只留 `after` 调度」。

## 基线
分支 `codex/wip-R2243`，自 `codex/wip-R2241`（已含 master R2238，行号按合并后文件复核）。

## 轮次类型／三套基线／债务
结构治理轮；行为等价（3 拍稳定、2 秒超时、16ms 轮询不变）；无新增债务。

## 改动
- `idea_chat_controller.py`：新增 `DeferredFill(clock, ticks, timeout).ready(fit_pending)`，持有稳定拍数与截止时刻；常量 `IDEA_UPDATE_STABLE_TICKS`、`IDEA_UPDATE_TIMEOUT_SECONDS` 迁入。
- `desktop_idea_deferred.py`：`defer_idea_page_updates` 只做取消旧 job、`after` 排拍、页面/退出守卫与回填调用；不再 import `time`。两常量从控制器再导出，旧测试导入路径不变。

## 新增测试
`tests/test_idea_deferred_fill.py`：连续稳定回填、布局变动清零计数、超时回填（时钟注入，不真等）。

## 测试
- 已跑（隐藏桌面）：`run_selftests.py -k idea_deferred idea_chat slowpage idea_history` 全过；`smoke_test.py --architecture` 412 条，仅两项已知环境红（`test_round_number_continuous`、`test_performance_history_is_declared_as_historical_only`）。
- 未运行：`--all --safe`；真机界面。既有测试断言未动。

## 回滚
`git revert` 本轮提交。

## 下一步
J19：请求生命周期的状态与判定迁入 `idea_chat_controller`，`desktop_idea_chat` 只留控件与事件绑定。
