# R2245 请求生命周期的判定迁入 idea_chat_controller（J19 结构治理轮·执行）

## 来源
`tasks_round/tasks_round_2178_result.md` 候选 03 的 J19：「请求生命周期的状态与判定迁入 `idea_chat_controller`，`desktop_idea_chat` 只留控件与事件绑定」。

## 基线
分支 `codex/wip-R2245`，自 `codex/wip-R2243`。请求状态（`requesting`／`cancel_event`／令牌／清理回调）原已在控制器；本轮迁走仍留在 Tk 方法里的判定。

## 轮次类型／三套基线／债务
结构治理轮；行为等价（排队文案、200ms 轮询、取消语义、中断提示文字逐字不变）；无新增债务。

## 改动
- `idea_chat_controller.py`：新增 `slot_decision`（槽位回执→run／wait／refuse）、`queue_notice`、`has_interruptible`、`interrupt_notice`，以及 `IdeaChatController.accepts(token, cancelled, current_root, project)`。
- `desktop_idea_chat.py`：`submit_idea_api_request` 的槽位分支改为 `act(slot_decision(...))`，`current()` 委托 `accepts`；`interrupt_script_agent` 的「无可中断」判定与结束文案委托控制器。体量 1114→1113，上限同步降到 1113。

## 新增测试
`tests/test_idea_request_lifecycle.py`：槽位三态、排队位次文案、可中断判定、中断文案条件、`accepts`（项目切换／取消／已结束）。

## 测试
- 已跑（隐藏桌面）：`run_selftests.py -k idea_request_lifecycle idea_chat script_agent interrupt slowpage` 全过；`smoke_test.py --architecture` 412 条，仅两项已知环境红。
- 未运行：`--all --safe`；真机界面。既有测试断言未动。

## 回滚
`git revert` 本轮提交。

## 下一步
候选 03 完成。下一组：J20（候选 11，`page_navigation_controller` 一次接收状态快照、返回完整换页决策）。
